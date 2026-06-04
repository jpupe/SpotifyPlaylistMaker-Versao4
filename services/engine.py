"""
Motor de geração de playlist — Two-Stage Pipeline:

  Estágio 1 — Filtragem por gênero:
    Busca artistas por gênero via /search → coleta top-tracks → forma pool.

  Estágio 2 — Random Forest Ranking:
    Treina RF com top tracks/liked songs do usuário como positivos.
    Ranqueia o pool por P(gosta) × purpose_score.

Todas as funções recebem `token` explicitamente (sem globais).
"""

import re
import math
import time
from typing import Generator

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score

from config.constants import MAPA_ESTILOS, PERFIS_FINALIDADE, TOP_N_GENEROS_ONE_HOT
from spotify.api import api_get, extrair_track_info, buscar_info_artistas


# ── Helpers de gênero ─────────────────────────────────────────────────────────

def _termos_genero(estilo: str) -> list[str]:
    """Retorna os termos Spotify para um estilo informado pelo usuário."""
    return MAPA_ESTILOS.get(estilo.lower(), [estilo.lower()])


def calcular_genre_match_score(generos_artista: list[str], estilos: list[str]) -> float:
    """Fração dos termos dos estilos presentes nos gêneros do artista (0.0–1.0)."""
    if not generos_artista or not estilos:
        return 0.0
    termos: set[str] = set()
    for e in estilos:
        for t in _termos_genero(e):
            termos.add(t.lower())
    gen_lower = [g.lower() for g in generos_artista]
    matches = sum(1 for t in termos if any(t in g or g in t for g in gen_lower))
    return min(1.0, matches / max(1, len(termos)))


def calcular_purpose_score(
    generos_artista: list[str],
    popularidade_artista: int,
    finalidade: str,
) -> float:
    """Score de aderência à finalidade: combina gêneros ideais + popularidade."""
    perfil = PERFIS_FINALIDADE.get(finalidade, PERFIS_FINALIDADE["geral"])
    ideais = perfil.get("generos_ideais", [])
    peso_pop = perfil.get("peso_pop", 0.2)
    gen_lower = [g.lower() for g in generos_artista]

    if ideais:
        matches = sum(1 for gi in ideais if any(gi in g or g in gi for g in gen_lower))
        score_genero = min(1.0, matches / max(1, len(ideais) * 0.3))
    else:
        score_genero = 0.5

    score_pop = popularidade_artista / 100.0
    return round(float((1 - peso_pop) * score_genero + peso_pop * score_pop), 4)


# ── Estágio 1 ─────────────────────────────────────────────────────────────────

def buscar_artistas_por_genero(estilo: str, token: str, limit: int = 12) -> list[str]:
    """Busca artist_ids cujos gêneros batem com o estilo informado."""
    termos = _termos_genero(estilo)
    ids: list[str] = []
    vistos: set[str] = set()

    for termo in termos[:3]:
        dados = api_get("/search", token, {
            "q":      f'genre:"{termo}"',
            "type":   "artist",
            "limit":  min(limit, 10),   # search limit máx = 10 em Dev Mode fev/2026
            "market": "BR",
        })
        for a in dados.get("artists", {}).get("items", []) or []:
            aid = a.get("id")
            if aid and aid not in vistos:
                vistos.add(aid)
                ids.append(aid)

    return ids[:limit]


def buscar_artista_por_nome(nome: str, token: str) -> dict | None:
    """Busca um artista pelo nome. Retorna o primeiro match ou None."""
    dados = api_get("/search", token, {"q": nome, "type": "artist", "limit": 5})
    artistas = dados.get("artists", {}).get("items", []) or []
    if not artistas:
        return None
    for a in artistas:
        if a.get("name", "").lower() == nome.lower():
            return a
    return artistas[0]


def buscar_tracks_artista(artist_id: str, artist_name: str, token: str) -> list[dict]:
    """
    Busca top-tracks de um artista.
    /artists/{id}/top-tracks foi removido em Dev Mode (fev/2026 → mar/2026).
    Usa /search como alternativa robusta.
    """
    # Tenta top-tracks primeiro (funciona em Extended Quota Mode)
    dados = api_get(f"/artists/{artist_id}/top-tracks", token, {"market": "BR"})
    tracks_raw = dados.get("tracks", [])

    # Fallback: search por tracks do artista
    if not tracks_raw:
        dados = api_get("/search", token, {
            "q":      f'artist:"{artist_name}"',
            "type":   "track",
            "limit":  10,
            "market": "BR",
        })
        tracks_raw = dados.get("tracks", {}).get("items", []) or []

    return [t for t in (extrair_track_info(r) for r in tracks_raw) if t]


def montar_pool_candidatas(
    params: dict,
    token: str,
    progress_callback=None,
) -> tuple[list[dict], set[str]]:
    """
    Estágio 1: monta o pool de faixas candidatas.
    progress_callback(mensagem, pct) é chamado para atualizar a UI.

    Retorna (pool_filtrado, ids_obrigatorios).
    """
    estilos        = params["estilos"]
    artistas_obrig = params["artistas_obrig"]
    finalidade     = params["finalidade"]
    perfil         = PERFIS_FINALIDADE[finalidade]

    pool: list[dict] = []
    ids_vistos: set[str] = set()
    ids_obrigatorios: set[str] = set()

    def adicionar(info: dict, obrigatorio: bool = False):
        if not info or info["track_id"] in ids_vistos:
            return
        ids_vistos.add(info["track_id"])
        pool.append(info)
        if obrigatorio:
            ids_obrigatorios.add(info["track_id"])

    # ── a) Tracks por estilo ─────────────────────────────────────────────────
    total_estilos = len(estilos)
    for i, estilo in enumerate(estilos):
        if progress_callback:
            pct = int(10 + (i / total_estilos) * 40)
            progress_callback(f"Buscando artistas de '{estilo}'...", pct)

        artist_ids = buscar_artistas_por_genero(estilo, token, limit=12)
        for aid in artist_ids:
            # Precisa do nome para o fallback de busca
            info_a = api_get(f"/artists/{aid}", token)
            nome_a = info_a.get("name", "")
            tracks = buscar_tracks_artista(aid, nome_a, token)
            for t in tracks:
                adicionar(t)
        time.sleep(0.2)

    # ── b) Artistas obrigatórios ─────────────────────────────────────────────
    for i, nome_artista in enumerate(artistas_obrig):
        if progress_callback:
            progress_callback(f"Incluindo artista obrigatório: {nome_artista}...", 55)
        artista = buscar_artista_por_nome(nome_artista, token)
        if artista:
            tracks = buscar_tracks_artista(artista["id"], artista["name"], token)
            for t in tracks:
                adicionar(t, obrigatorio=True)

    # ── c) Filtragem básica ──────────────────────────────────────────────────
    dur_min = perfil["duracao_min"]
    dur_max = perfil["duracao_max"]
    pop_min = perfil["pop_min"]

    pool_filtrado = [
        t for t in pool
        if t["track_id"] in ids_obrigatorios
        or (dur_min <= t["duracao_min"] <= dur_max and t["popularidade"] >= pop_min)
    ]

    # Relaxa filtros se pool muito pequeno
    if len(pool_filtrado) < 30:
        pool_filtrado = [
            t for t in pool if dur_min <= t["duracao_min"] <= dur_max
        ]
    if len(pool_filtrado) < 20:
        pool_filtrado = pool

    return pool_filtrado, ids_obrigatorios


def enriquecer_com_artistas(
    tracks: list[dict],
    estilos: list[str],
    finalidade: str,
    token: str,
    progress_callback=None,
) -> list[dict]:
    """
    Para cada track, busca gêneros e popularidade do artista principal
    e calcula genre_match_score e purpose_score.
    """
    if progress_callback:
        progress_callback("Enriquecendo tracks com dados de artistas...", 60)

    artist_ids = list({t["artista_id_principal"] for t in tracks if t.get("artista_id_principal")})
    info_map   = buscar_info_artistas(artist_ids, token)

    for t in tracks:
        aid  = t.get("artista_id_principal")
        info = info_map.get(aid, {}) if aid else {}
        generos    = info.get("genres", [])
        pop_art    = info.get("popularity", 0)
        t["generos"]           = generos
        t["artista_pop"]       = pop_art
        t["genre_match_score"] = calcular_genre_match_score(generos, estilos)
        t["purpose_score"]     = calcular_purpose_score(generos, pop_art, finalidade)

    return tracks


# ── Estágio 2 ─────────────────────────────────────────────────────────────────

def preparar_features(
    tracks: list[dict],
    top_generos: list[str] | None = None,
) -> tuple[np.ndarray, list[str], list[str]]:
    """Transforma lista de tracks em matriz de features para o RF."""
    df = pd.DataFrame(tracks)

    colunas_base = [
        "popularidade", "artista_pop", "duracao_min",
        "explicita", "ano", "genre_match_score", "purpose_score",
    ]
    for col in colunas_base:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float)

    # One-hot de gêneros
    if top_generos is None:
        todos = df["generos"].explode() if "generos" in df.columns else pd.Series([])
        top_generos = todos.value_counts().head(TOP_N_GENEROS_ONE_HOT).index.tolist()

    colunas_onehot = []
    if "generos" in df.columns:
        for g in top_generos:
            col = f"gen_{re.sub(r'[^a-z0-9]', '_', g.lower())}"
            df[col] = df["generos"].apply(
                lambda lst: int(g in lst) if isinstance(lst, list) else 0
            )
            colunas_onehot.append(col)

    todas = colunas_base + colunas_onehot
    return df[todas].values.astype(float), todas, top_generos


def rodar_random_forest(
    dados_treino: list[dict],
    pool: list[dict],
    finalidade: str,
    progress_callback=None,
) -> list[dict]:
    """
    Pipeline completo do Estágio 2:
      1. Monta positivos (dados_treino) e negativos (piores do pool)
      2. Treina RandomForest
      3. Ranqueia pool por P(gosta) × purpose_score
    """
    if progress_callback:
        progress_callback("Treinando modelo Random Forest...", 75)

    ids_positivos = {t["track_id"] for t in dados_treino}
    pool_sem_pos  = sorted(
        [t for t in pool if t["track_id"] not in ids_positivos],
        key=lambda t: t["genre_match_score"],
    )
    n_neg    = max(20, int(len(pool_sem_pos) * 0.40))
    negativos = pool_sem_pos[:n_neg] or pool_sem_pos

    todos_g = [g for t in dados_treino + negativos for g in t.get("generos", [])]
    top_g   = pd.Series(todos_g).value_counts().head(TOP_N_GENEROS_ONE_HOT).index.tolist()

    X_pos, colunas, _ = preparar_features(dados_treino, top_generos=top_g)
    X_neg, _,       _ = preparar_features(negativos,    top_generos=top_g)

    X = np.vstack([X_pos, X_neg])
    y = np.array([1] * len(dados_treino) + [0] * len(negativos))

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=3,
        max_features="sqrt", class_weight="balanced",
        random_state=42, n_jobs=-1,
    )
    rf.fit(X_scaled, y)

    # Ranqueia pool
    if progress_callback:
        progress_callback("Ranqueando músicas por compatibilidade...", 85)

    X_pool, _, _ = preparar_features(pool, top_generos=top_g)
    X_pool_s     = scaler.transform(X_pool)
    proba        = rf.predict_proba(X_pool_s)[:, 1]

    pool_rankeado = []
    for i, track in enumerate(pool):
        t = dict(track)
        t["rf_proba"]    = round(float(proba[i]), 4)
        t["score_final"] = round((float(proba[i]) ** 0.6) * (t.get("purpose_score", 0.5) ** 0.4), 4)
        pool_rankeado.append(t)

    pool_rankeado.sort(key=lambda t: t["score_final"], reverse=True)
    return pool_rankeado


# ── Montagem final ─────────────────────────────────────────────────────────────

def montar_playlist_final(
    pool_rankeado: list[dict],
    ids_obrigatorios: set[str],
    params: dict,
) -> list[dict]:
    """
    Seleciona as faixas finais:
      1. Garante 1 faixa por artista obrigatório (melhor score)
      2. Preenche com ranking RF (máx. 3 faixas por artista)
      3. Corta pelo critério de tamanho (duração ou quantidade)
      4. Shuffle suave por blocos
    """
    import random

    tipo  = params["tipo_tamanho"]
    valor = params["valor_tamanho"]

    # Artistas obrigatórios
    obrig_rankeadas = [t for t in pool_rankeado if t["track_id"] in ids_obrigatorios]
    vistos_artistas: set[str] = set()
    obrigatorias = []
    for t in obrig_rankeadas:
        aid = t.get("artista_id_principal", "")
        if aid not in vistos_artistas:
            obrigatorias.append(t)
            vistos_artistas.add(aid)

    ids_inclusos = {t["track_id"] for t in obrigatorias}

    # Preenche com ranking
    n_max = math.ceil((valor * 60 * 1000) / (3.5 * 60 * 1000)) + 10 if tipo == "duracao" else int(valor)
    contagem_artista: dict[str, int] = {}
    complementares = []

    for t in pool_rankeado:
        if len(complementares) >= n_max:
            break
        if t["track_id"] in ids_inclusos:
            continue
        aid = t.get("artista_id_principal", t["track_id"])
        contagem_artista.setdefault(aid, 0)
        if contagem_artista[aid] >= 3:
            continue
        complementares.append(t)
        ids_inclusos.add(t["track_id"])
        contagem_artista[aid] += 1

    todas = obrigatorias + complementares

    # Corta pelo critério de tamanho
    if tipo == "duracao":
        alvo_ms = valor * 60 * 1000
        selecionadas, acum = [], 0
        for t in todas:
            if acum >= alvo_ms * 1.10:
                break
            selecionadas.append(t)
            acum += t.get("duracao_ms", 0)
    else:
        selecionadas = todas[:int(valor)]

    # Shuffle suave (mantém obrigatórias no início)
    n_o = len(obrigatorias)
    resto = selecionadas[n_o:]
    random.shuffle(resto)
    return selecionadas[:n_o] + resto


def criar_playlist_no_spotify(
    tracks: list[dict],
    params: dict,
    token: str,
    publica: bool = False,
) -> dict:
    """Cria a playlist vazia e adiciona as faixas em lotes de 100."""
    from spotify.api import api_get, api_post

    usuario      = api_get("/me", token)
    display_name = usuario.get("display_name", "você")
    nome         = params["nome_playlist"]
    estilos      = params["estilos"]
    finalidade   = params["finalidade"]
    tipo_tam     = params["tipo_tamanho"]
    valor_tam    = params["valor_tamanho"]

    tam_str  = f"~{int(valor_tam)} min" if tipo_tam == "duracao" else f"{int(valor_tam)} músicas"
    descricao = (
        f"Gerada pelo SpotifyPlaylistMaker V4 · "
        f"Estilos: {', '.join(estilos)} · "
        f"Finalidade: {finalidade} · "
        f"{tam_str} · Método: Two-Stage RF"
    )[:300]

    playlist = api_post("/me/playlists", token, {
        "name":        nome,
        "public":      publica,
        "description": descricao,
    })
    playlist_id  = playlist["id"]
    playlist_url = playlist["external_urls"]["spotify"]

    uris = [t["uri"] for t in tracks if t.get("uri")]
    for i in range(0, len(uris), 100):
        api_post(f"/playlists/{playlist_id}/items", token, {"uris": uris[i:i+100]})

    duracao_ms = sum(t.get("duracao_ms", 0) for t in tracks)
    score_med  = sum(t.get("score_final", 0) for t in tracks) / max(1, len(tracks))

    return {
        "playlist_id":  playlist_id,
        "url":          playlist_url,
        "nome":         nome,
        "total_faixas": len(tracks),
        "duracao_min":  round(duracao_ms / 60000, 1),
        "score_medio":  round(score_med, 4),
        "tracks":       tracks,
    }
