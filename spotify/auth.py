"""
Autenticação OAuth 2.0 para Streamlit.

Diferente do script de terminal (que usava webbrowser + servidor local),
aqui o fluxo usa o próprio Streamlit como receptor do callback:

  1. Usuário clica "Login com Spotify"
     → redirecionado para accounts.spotify.com/authorize
  2. Spotify redireciona para REDIRECT_URI?code=XYZ
     → Streamlit carrega com st.query_params["code"] = "XYZ"
  3. Trocamos o código pelo access_token via POST /api/token
  4. Armazenamos o token em st.session_state["token"]

REDIRECT_URI deve ser a URL do próprio app Streamlit:
  - Local: http://127.0.0.1:8501
  - Streamlit Cloud: https://<nome>.streamlit.app
"""

import time
import json
import os

import requests
import streamlit as st

from config.constants import SCOPES


def _token_valido(token: dict) -> bool:
    """Retorna True se o token ainda é válido (com margem de 60s)."""
    return time.time() < token.get("expires_at", 0) - 60


def _enriquecer_token(token: dict) -> dict:
    """Adiciona o campo expires_at ao token recebido da API."""
    token["expires_at"] = time.time() + token.get("expires_in", 3600)
    return token


def _renovar_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    """Renova o access_token usando o refresh_token (sem interação do usuário)."""
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
            "client_id":     client_id,
            "client_secret": client_secret,
        },
        timeout=10,
    )
    resp.raise_for_status()
    novo = resp.json()
    if "refresh_token" not in novo:
        novo["refresh_token"] = refresh_token
    return _enriquecer_token(novo)


def _trocar_codigo_por_token(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Troca o código de autorização pelo access_token + refresh_token."""
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type":   "authorization_code",
            "code":          code,
            "redirect_uri":  redirect_uri,
            "client_id":     client_id,
            "client_secret": client_secret,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return _enriquecer_token(resp.json())


def construir_url_auth(client_id: str, redirect_uri: str) -> str:
    """Retorna a URL de autorização do Spotify para o botão de login."""
    import urllib.parse
    params = urllib.parse.urlencode({
        "client_id":     client_id,
        "response_type": "code",
        "redirect_uri":  redirect_uri,
        "scope":         SCOPES,
    })
    return f"https://accounts.spotify.com/authorize?{params}"


def handle_oauth_callback(client_id: str, client_secret: str, redirect_uri: str) -> bool:
    """
    Verifica se há um código OAuth nos query params do Streamlit.
    Se sim, troca pelo token e armazena em session_state.
    Retorna True se o callback foi processado com sucesso.
    """
    params = st.query_params
    code = params.get("code")

    if not code:
        return False

    try:
        token = _trocar_codigo_por_token(code, client_id, client_secret, redirect_uri)
        st.session_state["token"] = token
        # Limpa o código da URL para não reprocessar
        st.query_params.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao completar autenticação: {e}")
        st.query_params.clear()
        return False


def get_token(client_id: str, client_secret: str) -> str | None:
    """
    Retorna o access_token atual (renovando se necessário).
    Retorna None se o usuário não estiver autenticado.
    """
    token = st.session_state.get("token")
    if not token:
        return None

    if _token_valido(token):
        return token["access_token"]

    # Token expirado → renova
    refresh = token.get("refresh_token")
    if not refresh:
        st.session_state.pop("token", None)
        return None

    try:
        novo_token = _renovar_token(refresh, client_id, client_secret)
        st.session_state["token"] = novo_token
        return novo_token["access_token"]
    except Exception:
        st.session_state.pop("token", None)
        return None


def logout():
    """Remove o token da sessão (logout)."""
    st.session_state.pop("token", None)
    st.session_state.pop("user_info", None)
    st.session_state.pop("dados_treino", None)
