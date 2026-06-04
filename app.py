"""
Spotify Playlist Maker — Versao4
Interface Streamlit com design inspirado no Spotify.

Para rodar:
    streamlit run app.py

Variáveis necessárias no .env (pasta pai):
    SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET
    SPOTIFY_REDIRECT_URI   (ex: http://127.0.0.1:8501)
"""

import os
import sys

# Garante que os módulos locais sejam encontrados
sys.path.insert(0, os.path.dirname(__file__))

# Carrega .env da pasta pai (raiz do projeto, compartilhada entre versões)
from dotenv import load_dotenv
_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(_DIR), ".env"))

import streamlit as st

# ── Configuração da página (deve vir antes de qualquer st.*) ──────────────────
st.set_page_config(
    page_title="Spotify Playlist Maker",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Imports internos ──────────────────────────────────────────────────────────
from spotify.auth import construir_url_auth, handle_oauth_callback, get_token, logout
from services.collector import coletar_dados_treino, buscar_perfil_usuario
from services.engine import (
    montar_pool_candidatas,
    enriquecer_com_artistas,
    rodar_random_forest,
    montar_playlist_final,
    criar_playlist_no_spotify,
)
from config.constants import MAPA_ESTILOS, PERFIS_FINALIDADE

# ── Credenciais ───────────────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8501")


# ── CSS customizado ───────────────────────────────────────────────────────────
def _load_css():
    css_path = os.path.join(_DIR, "styles", "main.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

_load_css()


# ── Helpers de formatação ─────────────────────────────────────────────────────

def _fmt_duration(ms: float) -> str:
    total_s = int(ms / 1000)
    return f"{total_s // 60}:{total_s % 60:02d}"


def _render_track_card(i: int, track: dict):
    img_tag = (
        f'<img class="track-img" src="{track["album_img"]}" />'
        if track.get("album_img")
        else '<div class="track-img-placeholder">🎵</div>'
    )
    score = track.get("score_final", 0)
    dur   = _fmt_duration(track.get("duracao_ms", 0))
    nome  = track.get("nome", "")[:45]
    art   = track.get("artista", "")[:35]
    alb   = track.get("album", "")[:35]

    st.markdown(f"""
    <div class="track-card">
        <span class="track-num">{i}</span>
        {img_tag}
        <div class="track-info">
            <div class="track-name">{nome}</div>
            <div class="track-artist">{art}</div>
        </div>
        <span class="track-album">{alb}</span>
        <span class="track-duration">{dur}</span>
        <span class="track-score">⚡ {score:.2f}</span>
    </div>
    """, unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(token: str | None):
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header">
            <div class="sidebar-logo">🎵</div>
            <p class="sidebar-title">Playlist Maker</p>
            <p class="sidebar-subtitle">Powered by Spotify API + ML</p>
        </div>
        """, unsafe_allow_html=True)

        if token:
            # Perfil do usuário
            user = st.session_state.get("user_info") or {}
            nome = user.get("nome", "Usuário")
            foto = user.get("foto")

            if foto:
                avatar = f'<img src="{foto}" />'
            else:
                inicial = nome[0].upper() if nome else "U"
                avatar  = f'<div class="user-avatar-initials">{inicial}</div>'

            st.markdown(f"""
            <div class="user-avatar">
                {avatar}
                <span class="user-name">{nome}</span>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**⚙️ Configurações da Playlist**")

            # Visibilidade
            publica = st.toggle("Playlist pública", value=False)

            st.markdown("---")

            if st.button("🚪 Sair"):
                logout()
                st.rerun()

            return {"publica": publica}

        return {}


# ── Tela de login ─────────────────────────────────────────────────────────────

def render_landing():
    auth_url = construir_url_auth(CLIENT_ID, REDIRECT_URI)

    st.markdown(f"""
    <div class="landing-hero">
        <span class="landing-icon">🎵</span>
        <h1 class="landing-title">Spotify <span>Playlist</span> Maker</h1>
        <p class="landing-subtitle">
            Crie playlists personalizadas com Machine Learning.<br>
            Nosso algoritmo aprende com seu gosto musical e gera
            playlists perfeitas para cada momento.
        </p>

        <div class="feature-grid">
            <div class="feature-card">
                <span class="feature-icon">🎯</span>
                <div class="feature-title">Personalizado</div>
                <div class="feature-desc">Aprende com suas top tracks e músicas curtidas para entender seu gosto.</div>
            </div>
            <div class="feature-card">
                <span class="feature-icon">🤖</span>
                <div class="feature-title">Machine Learning</div>
                <div class="feature-desc">Random Forest ranqueia candidatas pela probabilidade de você gostar.</div>
            </div>
            <div class="feature-card">
                <span class="feature-icon">⚡</span>
                <div class="feature-title">Finalidade</div>
                <div class="feature-desc">Malhar, relaxar, focar, dançar — cada finalidade tem um perfil de seleção.</div>
            </div>
        </div>

        <a href="{auth_url}" target="_self" class="spotify-login-btn">
            ▶ Entrar com Spotify
        </a>
    </div>
    """, unsafe_allow_html=True)

    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("⚠️ Credenciais não encontradas. Configure o arquivo .env na raiz do projeto.")


# ── Formulário de geração ─────────────────────────────────────────────────────

def render_form(config: dict) -> dict | None:
    """Renderiza o formulário e retorna os params quando o usuário submete."""

    st.markdown('<h2 class="section-title">🎵 Criar Nova Playlist</h2>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        # ── Nome da playlist ────────────────────────────────────────────────
        nome_playlist = st.text_input(
            "📝 Nome da playlist",
            placeholder="Deixe em branco para nome automático",
            help="O nome aparecerá na sua conta do Spotify.",
        )

        # ── Estilos musicais ─────────────────────────────────────────────────
        estilos_disponiveis = sorted(MAPA_ESTILOS.keys())
        estilos_selecionados = st.multiselect(
            "🎸 Estilos musicais",
            options=estilos_disponiveis,
            default=["pop"],
            help="Selecione um ou mais estilos. Você pode combinar vários.",
        )

        # ── Artistas obrigatórios ─────────────────────────────────────────────
        artistas_input = st.text_input(
            "🎤 Artistas obrigatórios (máx. 3)",
            placeholder="Ex: Radiohead, Portishead, Björk",
            help="Músicas desses artistas serão garantidas na playlist. Separe por vírgula.",
        )

    with col2:
        # ── Finalidade ───────────────────────────────────────────────────────
        finalidade_labels = {k: v["label"] for k, v in PERFIS_FINALIDADE.items()}
        finalidade_key = st.selectbox(
            "🎯 Finalidade",
            options=list(finalidade_labels.keys()),
            format_func=lambda k: finalidade_labels[k],
            help="Define o perfil de seleção das músicas.",
        )

        # ── Tamanho ──────────────────────────────────────────────────────────
        st.markdown("**⏱️ Tamanho da playlist**")
        tipo_tamanho = st.radio(
            "Controlar por:",
            options=["Duração (minutos)", "Quantidade de músicas"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if tipo_tamanho == "Duração (minutos)":
            valor_tamanho = st.slider(
                "Duração alvo (min)", min_value=10, max_value=180, value=45, step=5
            )
            tipo_key = "duracao"
        else:
            valor_tamanho = st.slider(
                "Número de músicas", min_value=5, max_value=100, value=20, step=1
            )
            tipo_key = "quantidade"

    st.markdown("---")

    # ── Botão de geração ─────────────────────────────────────────────────────
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        gerar = st.button("🚀 Criar Playlist", use_container_width=True)

    with col_info:
        if not estilos_selecionados:
            st.warning("Selecione pelo menos um estilo musical.")

    if not gerar:
        return None

    if not estilos_selecionados:
        st.error("Selecione ao menos um estilo musical antes de continuar.")
        return None

    # Processa artistas obrigatórios
    artistas_obrig = [
        a.strip() for a in artistas_input.split(",") if a.strip()
    ][:3]

    # Nome automático se não fornecido
    if not nome_playlist.strip():
        partes = [finalidade_key.capitalize()]
        if estilos_selecionados:
            partes.append(" · ".join(e.capitalize() for e in estilos_selecionados[:2]))
        nome_playlist = " — ".join(partes)

    return {
        "estilos":       estilos_selecionados,
        "finalidade":    finalidade_key,
        "tipo_tamanho":  tipo_key,
        "valor_tamanho": float(valor_tamanho),
        "artistas_obrig":artistas_obrig,
        "nome_playlist": nome_playlist,
        "publica":       config.get("publica", False),
    }


# ── Geração com progresso ─────────────────────────────────────────────────────

def gerar_playlist(params: dict, token: str):
    """
    Executa o pipeline completo de geração com feedback visual.
    """
    progress_bar = st.progress(0)
    status_text  = st.empty()

    def atualizar(msg: str, pct: int):
        progress_bar.progress(pct / 100)
        status_text.markdown(f"**{msg}**")

    try:
        # Etapa 1 — dados de treino
        atualizar("📊 Coletando seu histórico de escuta...", 5)
        if "dados_treino" not in st.session_state:
            dados_treino = coletar_dados_treino(token)
            st.session_state["dados_treino"] = dados_treino
        else:
            dados_treino = st.session_state["dados_treino"]

        atualizar(f"✅ {len(dados_treino)} músicas do histórico carregadas.", 10)

        # Etapa 2 — pool de candidatas (Estágio 1)
        atualizar("🔍 Buscando músicas candidatas por gênero...", 15)
        pool, ids_obrig = montar_pool_candidatas(params, token, progress_callback=atualizar)
        atualizar(f"✅ {len(pool)} candidatas encontradas.", 58)

        # Etapa 3 — enriquecimento com dados de artista
        atualizar("🎸 Analisando artistas e gêneros...", 60)
        pool = enriquecer_com_artistas(
            pool, params["estilos"], params["finalidade"], token,
            progress_callback=atualizar,
        )
        dados_treino = enriquecer_com_artistas(
            dados_treino, params["estilos"], params["finalidade"], token,
        )
        atualizar("✅ Enriquecimento concluído.", 72)

        # Etapa 4 — Random Forest (Estágio 2)
        pool_rankeado = rodar_random_forest(
            dados_treino, pool, params["finalidade"],
            progress_callback=atualizar,
        )
        atualizar(f"✅ {len(pool_rankeado)} músicas ranqueadas.", 88)

        # Etapa 5 — montagem final
        atualizar("🎼 Montando playlist final...", 90)
        playlist_final = montar_playlist_final(pool_rankeado, ids_obrig, params)
        atualizar(f"✅ {len(playlist_final)} músicas selecionadas.", 93)

        # Etapa 6 — criação no Spotify
        atualizar("🚀 Criando playlist no Spotify...", 95)
        resultado = criar_playlist_no_spotify(
            playlist_final, params, token, publica=params.get("publica", False)
        )

        progress_bar.progress(1.0)
        status_text.empty()

        return resultado

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"❌ Erro durante a geração: {e}")
        return None


# ── Resultado ─────────────────────────────────────────────────────────────────

def render_resultado(resultado: dict):
    """Exibe os resultados da playlist criada."""
    tracks = resultado.get("tracks", [])

    # Card principal
    st.markdown(f"""
    <div class="result-card">
        <div class="result-title">✅ {resultado['nome']}</div>
        <div class="result-meta">Criada com sucesso no seu Spotify</div>
        <div class="result-stats">
            <div class="result-stat">
                <span class="result-stat-value">{resultado['total_faixas']}</span>
                <span class="result-stat-label">Músicas</span>
            </div>
            <div class="result-stat">
                <span class="result-stat-value">{resultado['duracao_min']:.0f} min</span>
                <span class="result-stat-label">Duração</span>
            </div>
            <div class="result-stat">
                <span class="result-stat-value">{resultado['score_medio']:.2f}</span>
                <span class="result-stat-label">Score médio</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Botão para abrir no Spotify
    st.link_button(
        "▶ Abrir no Spotify",
        url=resultado["url"],
        help="Abre a playlist diretamente no Spotify.",
    )

    # Lista de músicas
    st.markdown('<div class="section-title">🎧 Músicas da Playlist</div>', unsafe_allow_html=True)

    # Cabeçalho da lista
    st.markdown("""
    <div style="display:flex; gap:1rem; padding:0.4rem 1rem; color:#B3B3B3; font-size:0.78rem; font-weight:600;">
        <span style="width:20px">#</span>
        <span style="width:44px"></span>
        <span style="flex:1">TÍTULO</span>
        <span style="max-width:200px">ÁLBUM</span>
        <span style="min-width:38px; text-align:right">DURAÇÃO</span>
        <span style="min-width:60px; text-align:right">SCORE</span>
    </div>
    <hr style="margin:0.2rem 0 0.5rem; border-color:#404040;">
    """, unsafe_allow_html=True)

    for i, track in enumerate(tracks, 1):
        _render_track_card(i, track)

    # Botão de nova playlist
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Criar Outra Playlist"):
        st.session_state.pop("resultado", None)
        st.rerun()


# ── App principal ─────────────────────────────────────────────────────────────

def main():
    # Valida credenciais
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error(
            "⚠️ Credenciais do Spotify não encontradas.\n\n"
            "Configure o arquivo `.env` na raiz do projeto com:\n"
            "```\nSPOTIFY_CLIENT_ID=...\nSPOTIFY_CLIENT_SECRET=...\n"
            "SPOTIFY_REDIRECT_URI=http://127.0.0.1:8501\n```"
        )
        return

    # Processa callback OAuth (se Spotify redirecionou de volta)
    if handle_oauth_callback(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI):
        st.rerun()

    # Obtém token atual
    token = get_token(CLIENT_ID, CLIENT_SECRET)

    # ── Não autenticado: tela de landing ─────────────────────────────────────
    if not token:
        render_sidebar(None)
        render_landing()
        return

    # ── Autenticado ───────────────────────────────────────────────────────────

    # Carrega perfil do usuário (uma vez por sessão)
    if "user_info" not in st.session_state:
        with st.spinner("Carregando perfil..."):
            try:
                st.session_state["user_info"] = buscar_perfil_usuario(token)
            except Exception:
                st.session_state["user_info"] = {"nome": "Usuário", "foto": None}

    config  = render_sidebar(token)

    # Resultado já gerado → exibe
    if "resultado" in st.session_state:
        render_resultado(st.session_state["resultado"])
        return

    # Formulário
    params = render_form(config)

    if params:
        with st.spinner("Iniciando geração..."):
            resultado = gerar_playlist(params, token)

        if resultado:
            st.session_state["resultado"] = resultado
            st.balloons()
            st.rerun()


if __name__ == "__main__" or True:
    main()
