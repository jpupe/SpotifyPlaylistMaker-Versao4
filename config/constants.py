"""
Constantes globais: mapeamento de estilos e perfis de finalidade.
Extraídos do playlist_maker.py da Versao3 sem modificações de lógica.
"""

# Mapeamento de estilos PT/coloquial → termos de gênero do Spotify
MAPA_ESTILOS: dict[str, list[str]] = {
    "rock":          ["rock"],
    "rock clássico": ["classic rock", "rock"],
    "rock classico": ["classic rock", "rock"],
    "metal":         ["metal"],
    "alternativo":   ["alternative", "grunge", "post-punk"],
    "indie":         ["indie"],
    "punk":          ["punk"],
    "grunge":        ["grunge"],
    "pop":           ["pop"],
    "k-pop":         ["k-pop", "korean"],
    "kpop":          ["k-pop", "korean"],
    "j-pop":         ["j-pop", "japanese"],
    "eletrônica":    ["electronic", "edm", "house", "techno", "trance", "electro"],
    "eletronica":    ["electronic", "edm", "house", "techno", "trance", "electro"],
    "edm":           ["edm", "electronic dance"],
    "house":         ["house"],
    "techno":        ["techno"],
    "drum and bass": ["drum and bass", "dnb"],
    "dnb":           ["drum and bass", "dnb"],
    "hip-hop":       ["hip hop", "rap", "trap"],
    "hip hop":       ["hip hop", "rap", "trap"],
    "rap":           ["rap", "hip hop"],
    "trap":          ["trap", "hip hop"],
    "r&b":           ["r&b", "soul", "neo soul"],
    "soul":          ["soul", "r&b"],
    "sertanejo":     ["sertanejo"],
    "funk":          ["funk carioca", "funk brasileiro", "funk ostentação", "funk"],
    "pagode":        ["pagode", "samba"],
    "mpb":           ["mpb", "música popular brasileira"],
    "axé":           ["axé", "axe"],
    "axe":           ["axé", "axe"],
    "forró":         ["forró", "forro"],
    "forro":         ["forró", "forro"],
    "bossa nova":    ["bossa nova"],
    "samba":         ["samba", "pagode"],
    "jazz":          ["jazz"],
    "blues":         ["blues"],
    "clássica":      ["classical", "orchestral", "opera", "chamber"],
    "classica":      ["classical", "orchestral", "opera"],
    "reggae":        ["reggae"],
    "reggaeton":     ["reggaeton", "latin"],
    "latina":        ["latin", "reggaeton", "salsa", "bachata", "cumbia"],
    "country":       ["country", "americana"],
    "gospel":        ["gospel", "christian", "ccm"],
    "folk":          ["folk", "singer-songwriter"],
    "acústico":      ["acoustic", "singer-songwriter", "folk"],
    "acustico":      ["acoustic", "singer-songwriter", "folk"],
    "ambient":       ["ambient", "new age"],
    "lo-fi":         ["lo-fi", "lofi", "chill"],
    "chill":         ["chill", "lo-fi", "downtempo"],
}

# Perfis de finalidade: gêneros ideais e parâmetros de filtragem
PERFIS_FINALIDADE: dict[str, dict] = {
    "malhar": {
        "label":          "🏋️ Malhar / Treinar",
        "sinonimos":      ["malhar", "academia", "treino", "treinar", "workout", "exercício", "exercicio"],
        "generos_ideais": ["hip hop", "electronic", "edm", "pop", "rock", "funk", "dance", "trap",
                           "house", "drum and bass", "metal", "rap"],
        "pop_min":        40,
        "duracao_min":    2.0,
        "duracao_max":    6.0,
        "peso_pop":       0.35,
    },
    "relaxar": {
        "label":          "😌 Relaxar / Descansar",
        "sinonimos":      ["relaxar", "relaxamento", "descansar", "descanso", "calmo", "tranquilo",
                           "meditação", "meditacao", "dormir", "sono"],
        "generos_ideais": ["acoustic", "ambient", "folk", "classical", "bossa nova", "jazz",
                           "indie folk", "singer-songwriter", "new age", "lo-fi", "chill"],
        "pop_min":        10,
        "duracao_min":    2.5,
        "duracao_max":    9.0,
        "peso_pop":       0.05,
    },
    "focar": {
        "label":          "🎯 Focar / Estudar",
        "sinonimos":      ["focar", "foco", "concentrar", "concentração", "concentracao",
                           "estudar", "estudo", "trabalhar", "trabalho", "produtividade"],
        "generos_ideais": ["ambient", "classical", "lo-fi", "lofi", "instrumental", "new age",
                           "post-rock", "electronic", "chill"],
        "pop_min":        15,
        "duracao_min":    2.0,
        "duracao_max":    10.0,
        "peso_pop":       0.05,
    },
    "dançar": {
        "label":          "🕺 Dançar / Festa",
        "sinonimos":      ["dançar", "festa", "balada", "dance", "agitado", "animado", "animar"],
        "generos_ideais": ["dance pop", "edm", "house", "disco", "pop", "electronic", "funk",
                           "reggaeton", "latin", "hip hop"],
        "pop_min":        50,
        "duracao_min":    2.5,
        "duracao_max":    6.0,
        "peso_pop":       0.40,
    },
    "viagem": {
        "label":          "🚗 Viagem / Road Trip",
        "sinonimos":      ["viagem", "carro", "estrada", "road trip", "dirigir", "viajar"],
        "generos_ideais": ["rock", "pop", "country", "indie", "alternative", "classic rock",
                           "folk", "americana", "singer-songwriter"],
        "pop_min":        30,
        "duracao_min":    2.5,
        "duracao_max":    7.0,
        "peso_pop":       0.20,
    },
    "cantar": {
        "label":          "🎤 Cantar / Karaokê",
        "sinonimos":      ["cantar", "karaokê", "karaoke", "voz", "letra"],
        "generos_ideais": ["pop", "rock", "mpb", "sertanejo", "pagode", "r&b", "soul",
                           "singer-songwriter", "indie pop"],
        "pop_min":        40,
        "duracao_min":    2.5,
        "duracao_max":    6.0,
        "peso_pop":       0.35,
    },
    "romântico": {
        "label":          "❤️ Romântico / Jantar",
        "sinonimos":      ["romântico", "romantico", "romance", "amor", "namorar", "casal", "jantar"],
        "generos_ideais": ["r&b", "soul", "neo soul", "bossa nova", "jazz", "pop",
                           "singer-songwriter", "acoustic", "mpb"],
        "pop_min":        20,
        "duracao_min":    2.5,
        "duracao_max":    7.0,
        "peso_pop":       0.15,
    },
    "manhã": {
        "label":          "☀️ Manhã / Acordar",
        "sinonimos":      ["manhã", "manha", "acordar", "despertar", "bom dia", "café", "cafe"],
        "generos_ideais": ["pop", "indie pop", "folk", "acoustic", "bossa nova", "mpb",
                           "singer-songwriter", "jazz"],
        "pop_min":        20,
        "duracao_min":    2.0,
        "duracao_max":    6.0,
        "peso_pop":       0.15,
    },
    "geral": {
        "label":          "🎵 Geral / Sem preferência",
        "sinonimos":      [],
        "generos_ideais": [],
        "pop_min":        20,
        "duracao_min":    1.0,
        "duracao_max":    10.0,
        "peso_pop":       0.20,
    },
}

# Scopes OAuth necessários
SCOPES = (
    "user-library-read "
    "user-top-read "
    "playlist-modify-public "
    "playlist-modify-private "
    "playlist-read-private"
)

# Número de gêneros para one-hot encoding no Random Forest
TOP_N_GENEROS_ONE_HOT = 40
