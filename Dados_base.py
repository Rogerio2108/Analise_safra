"""
Módulo com dados base para análise de safra.
"""
from pathlib import Path

# Caminhos dos arquivos de dados (ajuste conforme necessário)
DATA_FILES = {
    "Historico_safra": Path("dados/historico_safra.xlsx"),  # Ajuste o caminho conforme necessário
    "Volatilidades": Path("dados/volatilidades.xlsx"),      # Ajuste o caminho conforme necessário
}

# Volatilidades padrão (caso não tenha arquivo)
DEFAULT_VOLS = {
    "sugar": 0.282222,
    "usdbrl": 0.15098,
    "ethanol": 0.25126,
}

# ============================================================================
# PARÂMETROS DE CONVERSÃO AÇÚCAR VHP → FOB
# ============================================================================
# Fórmula: FOB = (NY11 - DESCONTO_VHP_FOB) * (1 + TAXA_POL)
# Primeiro subtrai o desconto, depois aplica o prêmio de polarização
DESCONTO_VHP_FOB = 0.10  # Desconto em cents/lb (altere aqui se necessário)
TAXA_POL = 0.045  # Taxa de polarização fixa: 4,5% (altere aqui se necessário)
# ============================================================================

# ============================================================================
# PARÂMETROS DE IMPOSTOS - ETANOL
# ============================================================================
# Impostos aplicados ao preço bruto do etanol antes da conversão FOB
ICMS_ETANOL = 0.12  # ICMS: 12% (altere aqui se necessário)
PIS_COFINS_ETANOL = 192.2  # PIS e COFINS: R$ 192,2 (altere aqui se necessário)
# Fórmula: preco_sem_impostos = (preco_bruto * (1 - ICMS_ETANOL)) - PIS_COFINS_ETANOL
# ============================================================================

# ============================================================================
# PARÂMETROS DE CONVERSÃO ETANOL → FOB
# ============================================================================
# Valores fixos usados na conversão de etanol para FOB
# Fórmula: =((((((L7)/31,504)*20)+$C$32+($C$30*$C$4))/22,0462/$C$4)/1,042)
FRETE_R_T = 202.0  # Frete em R$/t (C32) - altere aqui se necessário
TERMINAL_USD_T = 12.5  # Terminal em USD/t (C30) - altere aqui se necessário
# ============================================================================

# ============================================================================
# PERFIS HISTÓRICOS ATR E MIX
# ============================================================================
# Perfis históricos de distribuição quinzenal (22 quinzenas)
# Valores são fatores multiplicadores que variam ao longo da safra
PERFIL_ATR = [
    0.81, 0.87, 0.94, 0.98, 1.00, 1.03, 1.06, 1.10, 1.13, 1.15, 1.18, 1.19,
    1.15, 1.12, 1.04, 1.01, 0.97, 1.03, 0.90, 1.03, 0.88, 0.85
]

PERFIL_MIX = [
    0.96, 1.11, 1.19, 1.19, 1.22, 1.24, 1.25, 1.26, 1.24, 1.24, 1.23, 1.19,
    1.16, 1.13, 1.11, 1.02, 0.87, 0.73, 0.72, 0.65, 0.57, 0.38
]
# ============================================================================
