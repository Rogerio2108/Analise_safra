"""
Módulo com dados base para análise de safra.
"""
from pathlib import Path

# Caminhos dos arquivos de dados (ajuste conforme necessário)
DATA_FILES = {
    "Historico_safra": Path("Data_base/Historico_safra.xlsx"),  # Ajuste o caminho conforme necessário
    "Volatilidades": Path("Data_base/Volatilidades.xlsx"),      # Ajuste o caminho conforme necessário
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
# PERFIS HISTÓRICOS - REPRESENTATIVIDADE E DISTRIBUIÇÃO
# ============================================================================
# Perfil de representatividade de moagem (percentual de cada quinzena na safra total)
# Valores em percentual (ex: 2.67 = 2.67%)
PERFIL_MOAGEM_PCT = [
    2.67, 4.83, 6.86, 6.99, 6.98, 7.52, 7.73, 8.42, 7.23, 7.50, 7.08, 6.11,
    5.45, 5.02, 3.69, 2.50, 1.37, 0.34, 0.07, 0.06, 0.06, 0.09, 0.40, 1.03
]

# Perfis históricos de distribuição quinzenal ATR e MIX (24 quinzenas)
# Valores são fatores multiplicadores que variam ao longo da safra
PERFIL_ATR = [
    0.81, 0.87, 0.94, 0.98, 1.00, 1.03, 1.06, 1.10, 1.13, 1.15, 1.18, 1.19,
    1.15, 1.12, 1.04, 1.01, 0.97, 1.03, 0.90, 1.03, 0.88, 0.85, 0.76, 0.81
]

PERFIL_MIX = [
    0.96, 1.11, 1.19, 1.19, 1.22, 1.24, 1.25, 1.26, 1.24, 1.24, 1.23, 1.19,
    1.16, 1.13, 1.11, 1.02, 0.87, 0.73, 0.72, 0.65, 0.57, 0.38, 0.56, 0.78
]
# ============================================================================

# ============================================================================
# VOLATILIDADES DE ETANOL - PRODUÇÃO
# ============================================================================
# Volatilidades relativas (percentuais) para simulação de produção de etanol
# Valores baseados em dados históricos de variação quinzenal
VOLATILIDADE_ETANOL_ANIDRO_CANA = 0.15      # 15% de volatilidade
VOLATILIDADE_ETANOL_HIDRATADO_CANA = 0.18   # 18% de volatilidade
VOLATILIDADE_ETANOL_ANIDRO_MILHO = 0.20     # 20% de volatilidade
VOLATILIDADE_ETANOL_HIDRATADO_MILHO = 0.22  # 22% de volatilidade

# Desvios padrão absolutos (m³) para valores pequenos
DESVIO_PADRAO_ETANOL_ANIDRO_CANA = 1000.0      # m³
DESVIO_PADRAO_ETANOL_HIDRATADO_CANA = 1200.0   # m³
DESVIO_PADRAO_ETANOL_ANIDRO_MILHO = 500.0      # m³
DESVIO_PADRAO_ETANOL_HIDRATADO_MILHO = 600.0   # m³
# ============================================================================

# ============================================================================
# VOLATILIDADES DE ETANOL - PREÇOS
# ============================================================================
# Volatilidades para simulação de preços de etanol
VOLATILIDADE_ETANOL_ANIDRO = 0.25      # 25% de volatilidade
VOLATILIDADE_ETANOL_HIDRATADO = 0.28   # 28% de volatilidade
# ============================================================================

