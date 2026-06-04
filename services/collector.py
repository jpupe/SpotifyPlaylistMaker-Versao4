"""
Coleta de dados do usuário no Spotify:
- Top tracks (3 horizontes temporais)
- Liked Songs (amostra)

Estas tracks servem como exemplos positivos para treinar o Random Forest.
"""

from spotify.api import api_get, buscar_todas_paginas, extrair_track_info


def buscar_top_tracks(token: str) -> list[dict]:
    """
    Retorna top tracks do usuário em 3 janelas temporais combinadas.
    Remove duplicatas por track_id.
    """
    tops = []
    for janela in ("short_term", "medium_term", "long_term"):
        dados = api_get("/me/top/tracks", token, {"time_range": janela, "limit": 50})
        tops.extend(dados.get("items", []))

    # Deduplica
    vistas: set[str] = set()
    unicas = []
    for t in tops:
        tid = t.get("id")
        if tid and tid not in vistas:
            vistas.add(tid)
            info = extrair_track_info(t)
            if info:
                unicas.append(info)

    return unicas


def buscar_liked_songs(token: str, max_tracks: int = 100) -> list[dict]:
    """Retorna uma amostra das músicas curtidas do usuário."""
    itens = buscar_todas_paginas("/me/tracks", token, max_items=max_tracks)
    tracks = []
    for item in itens:
        t = item.get("track")
        if t:
            info = extrair_track_info(t)
            if info:
                tracks.append(info)
    return tracks


def coletar_dados_treino(token: str) -> list[dict]:
    """
    Combina top tracks + liked songs como exemplos positivos para o RF.
    Remove duplicatas finais por track_id.
    """
    top   = buscar_top_tracks(token)
    liked = buscar_liked_songs(token, max_tracks=100)

    vistas: set[str] = set()
    positivos = []
    for t in top + liked:
        if t["track_id"] not in vistas:
            vistas.add(t["track_id"])
            positivos.append(t)

    return positivos


def buscar_perfil_usuario(token: str) -> dict:
    """Retorna nome, foto e id do usuário autenticado."""
    from spotify.api import api_get
    dados = api_get("/me", token)
    imagens = dados.get("images", [])
    foto = imagens[0]["url"] if imagens else None
    return {
        "id":           dados.get("id", ""),
        "nome":         dados.get("display_name", "Usuário"),
        "foto":         foto,
        "email":        dados.get("email", ""),
    }
