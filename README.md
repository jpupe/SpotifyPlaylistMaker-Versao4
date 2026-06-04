# 🎵 Spotify Playlist Maker — Versao4

Interface web moderna para geração automática de playlists personalizadas usando Machine Learning.

## Arquitetura

```
Versao4/
├── app.py              ← Streamlit — ponto de entrada
├── config/
│   └── constants.py    ← MAPA_ESTILOS, PERFIS_FINALIDADE, SCOPES
├── spotify/
│   ├── auth.py         ← OAuth 2.0 adaptado para Streamlit
│   └── api.py          ← Chamadas à Spotify Web API
├── services/
│   ├── collector.py    ← Coleta de dados do usuário (top tracks, liked songs)
│   └── engine.py       ← Pipeline ML: Estágio 1 (filtragem) + Estágio 2 (RF)
├── styles/
│   └── main.css        ← Tema escuro inspirado no Spotify
└── requirements.txt
```

## Instalação

```bash
cd Versao4
pip install -r requirements.txt
```

## Configuração

O arquivo `.env` fica na **raiz do projeto** (pasta pai), compartilhado entre versões:

```env
SPOTIFY_CLIENT_ID=seu_client_id
SPOTIFY_CLIENT_SECRET=seu_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8501
```

### No Spotify Developer Dashboard

1. Acesse [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Abra seu app → **Edit Settings**
3. Em **Redirect URIs**, adicione: `http://127.0.0.1:8501`
4. Salve

> Para Streamlit Cloud, substitua pelo URL do app: `https://<nome>.streamlit.app`

## Como rodar (local)

```bash
streamlit run app.py
```

O app abre em `http://127.0.0.1:8501`.

## Deploy no Streamlit Cloud

1. Faça push para o GitHub
2. Acesse [share.streamlit.io](https://share.streamlit.io)
3. Conecte o repositório e aponte para `Versao4/app.py`
4. Em **Secrets**, adicione as variáveis do `.env`
5. Adicione a URL do app como Redirect URI no Spotify Dashboard

## Como funciona

### Fluxo de autenticação (OAuth 2.0)
1. Usuário clica "Entrar com Spotify"
2. Spotify autentica e redireciona para o app com `?code=...`
3. O app troca o código pelo access token (armazenado na sessão)
4. Token é renovado automaticamente quando expira

### Pipeline de geração

**Estágio 1 — Filtragem por gênero**
- Busca artistas via `/search?type=artist&q=genre:"{termo}"`
- Coleta top-tracks de cada artista
- Inclui tracks de artistas obrigatórios
- Filtra por duração e popularidade mínima (definidos pelo perfil de finalidade)

**Estágio 2 — Random Forest**
- Positivos: top tracks + liked songs do usuário
- Negativos: tracks do pool com menor genre_match_score
- Features: popularidade, duração, ano, explicitidade, genre_match_score, purpose_score, one-hot de gêneros
- Score final: `P(gosta)^0.6 × purpose_score^0.4`

**Montagem**
- 1 faixa garantida por artista obrigatório
- Resto preenchido pelo ranking RF (máx. 3 faixas por artista)
- Corte por duração ou quantidade
- Shuffle suave por blocos

## Nota sobre a API do Spotify (fev/2026)

Apps em **Development Mode** têm restrições desde março/2026:
- ❌ `/audio-features` — desativado (substituído por gêneros de artistas)
- ❌ `/artists?ids=...` — batch removido (usamos requisições individuais)
- ❌ `/artists/{id}/top-tracks` — removido (fallback para `/search`)
- ✅ `/search`, `/me/top/tracks`, `/me/tracks`, `/me/playlists` — disponíveis
