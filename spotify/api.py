"""
Helpers para chamadas à Spotify Web API.
Todas as funções recebem o access_token como parâmetro explícito
(sem globais) para funcionar corretamente com o session_state do Streamlit.
"""

import time
import urllib.parse

import requests


BASE_URL = "https://api.spotify.com/v1"


# ── Primitivas HTTP ────────────────────────────────────────────────────────────

def api_get(endpoint: str, token: str, params: dict | None = None) -> dict:
    """
    GET na Spotify Web API com retry automático para rate limit (429).
    Retorna {} em caso de 404 (recurso não encontrado).
    Levanta RuntimeError para 401 (token inválido).
    """
    url = f"{BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(6):
        resp = requests.get(url, headers=headers, params=params, timeout=15)

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 3))
            time.sleep(wait)
            continue

        if resp.status_code == 401:
            raise RuntimeError("Token inválido ou expirado. Faça login novamente.")

        if resp.status_code == 404:
            return {}

        if resp.status_code == 403:
            # Endpoint desativado em Dev Mode — retorna dict vazio sem travar
            return {}

        resp.raise_for_status()
        return resp.json()

    raise RuntimeError("Máximo de tentativas atingido. API do Spotify instável.")


def api_post(endpoint: str, token: str, corpo: dict) -> dict:
    """POST na Spotify Web API."""
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    resp = requests.post(url, headers=headers, json=corpo, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── Paginação ─────────────────────────────────────────────────────────────────

def buscar_todas_paginas(
    endpoint: str,
    token: str,
    params: dict | None = None,
    max_items: int = 500,
) -> list:
    """
    Percorre todas as páginas de um endpoint paginado e retorna todos os items.
    Limita a max_items para evitar chamadas excessivas.
    """
    todos: list = []
    params = dict(params or {})
    params.setdefault("limit", 50)

    pagina = api_get(endpoint, token, params)

    while True:
        itens = pagina.get("items", [])
        todos.extend(itens)

        if len(todos) >= max_items:
            break

        proxima = pagina.get("next")
        if not proxima:
            break

        parsed = urllib.parse.urlparse(proxima)
        proximos_params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        proximo_endpoint = parsed.path.replace("/v1", "")
        pagina = api_get(proximo_endpoint, token, proximos_params)

    return todos[:max_items]


# ── Helpers de artista ─────────────────────────────────────────────────────────

def buscar_info_artista(artist_id: str, token: str) -> dict:
    """
    Busca gêneros e popularidade de UM artista via GET /artists/{id}.
    O endpoint batch GET /artists?ids=... foi removido em fev/2026 para Dev Mode.
    """
    dados = api_get(f"/artists/{artist_id}", token)
    return {
        "genres":     dados.get("genres", []),
        "popularity": dados.get("popularity", 0),
        "name":       dados.get("name", ""),
    }


def buscar_info_artistas(artist_ids: list[str], token: str) -> dict[str, dict]:
    """
    Busca gêneros e popularidade de múltiplos artistas.
    Faz requisições individuais (batch removido em fev/2026).
    Retorna {artist_id: {"genres": [...], "popularity": int, "name": str}}.
    """
    resultado = {}
    for aid in set(artist_ids):
        if aid:
            resultado[aid] = buscar_info_artista(aid, token)
    return resultado


# ── Extração de track info ─────────────────────────────────────────────────────

def extrair_track_info(track: dict) -> dict | None:
    """
    Extrai campos relevantes de um track object da API do Spotify.
    Retorna None se o track for inválido (sem ID).
    """
    if not track or not track.get("id"):
        return None

    artistas = track.get("artists", [])
    artista_ids = [a["id"] for a in artistas if a.get("id")]

    release_date = track.get("album", {}).get("release_date", "")
    try:
        ano = int(release_date[:4])
    except (ValueError, TypeError):
        ano = 2000

    # Imagem do álbum (maior disponível)
    imagens = track.get("album", {}).get("images", [])
    album_img = imagens[0]["url"] if imagens else None

    return {
        "track_id":              track["id"],
        "uri":                   track.get("uri", f"spotify:track:{track['id']}"),
        "nome":                  track.get("name", ""),
        "artista":               ", ".join(a["name"] for a in artistas),
        "artista_ids":           artista_ids,
        "artista_id_principal":  artista_ids[0] if artista_ids else None,
        "album":                 track.get("album", {}).get("name", ""),
        "album_img":             album_img,
        "duracao_ms":            track.get("duration_ms", 0),
        "duracao_min":           track.get("duration_ms", 0) / 60000,
        "explicita":             int(track.get("explicit", False)),
        "popularidade":          track.get("popularity", 0),
        "ano":                   ano,
        # Preenchido depois pelo engine
        "generos":               [],
        "artista_pop":           0,
        "genre_match_score":     0.0,
        "purpose_score":         0.0,
    }
