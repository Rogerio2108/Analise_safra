"""
================================================================================
ANÁLISE DE SAFRA - SIMULAÇÃO DE PREÇOS E PRODUÇÃO
================================================================================
Este módulo simula preços de açúcar, etanol e USD/BRL considerando:
- Volatilidade e correlação entre commodities
- Impacto da produção (moagem, ATR, mix) nos preços
- Paridade etanol/açúcar (ajusta mix dinamicamente)
- Choques externos (safra e preços)

PARÂMETROS DE CONVERSÃO AÇÚCAR VHP → FOB:
- DESCONTO_VHP_FOB: 0.10 (desconto/prêmio em cents/lb)
- TAXA_POL: 0.045 (taxa de polarização fixa: 4,5%)
  → Definidos em Dados_base.py (fácil alteração)
  → Fórmula: FOB = NY11 - DESCONTO_VHP_FOB * (1 + TAXA_POL)

================================================================================
"""

import pandas as pd
import streamlit as st
from pathlib import Path
import numpy as np
from datetime import date
from Dados_base import (
    DATA_FILES, 
    DESCONTO_VHP_FOB, 
    TAXA_POL,
    ICMS_ETANOL,
    PIS_COFINS_ETANOL,
    FRETE_R_T,
    TERMINAL_USD_T,
    PERFIL_ATR,
    PERFIL_MIX
)


# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

def fmt_br(valor, casas=2):
    """Formata número no padrão brasileiro: 1.234.567,89"""
    if valor is None:
        return ""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ============================================================================
# CONFIGURAÇÃO STREAMLIT
# ============================================================================

st.set_page_config(page_title="Análise de Safra", layout="wide")


# ============================================================================
# FUNÇÕES DE CARREGAMENTO DE DADOS
# ============================================================================

@st.cache_data
def load_historico_safra(path: Path | str = DATA_FILES["Historico_safra"]):
    return pd.read_excel(path)


# ============================================================================
# CONSTANTES DE PRODUÇÃO
# ============================================================================

FATOR_ACUCAR = 0.95275
FATOR_ETANOL = 0.595

# ============================================================================
# FUNÇÕES DE CÁLCULO DE PRODUÇÃO
# ============================================================================

def calcular_producao(moagem, atr, mix_acucar):
    """Calcula produção de açúcar (t) e etanol (m³)"""
    mix = mix_acucar / 100
    acucar = ((moagem * mix * atr) * FATOR_ACUCAR) / 1000
    etanol = (moagem * atr * ((1 - mix) * FATOR_ETANOL) / 1000)
    return acucar, etanol


def calcular_producao_quinzenal(moagem, atr, mix):
    """Calcula produção quinzenal de açúcar (t) e etanol (m³)"""
    mix_decimal = mix / 100 if isinstance(mix, (int, float)) and mix > 1 else mix
    acucar = ((moagem * mix_decimal * atr) * FATOR_ACUCAR) / 1000
    etanol = (moagem * atr * ((1 - mix_decimal) * FATOR_ETANOL) / 1000)
    return acucar, etanol


def calcular_etanol_detalhado(etanol_total_cana, quinzena, n_quinzenas_total):
    """
    Calcula distribuição de etanol de cana (anidro e hidratado) baseado no perfil da safra.

    Regra:
    - Anidro começa em 20% e aumenta 2 pontos percentuais até chegar em 44%
    - Depois diminui 2 pontos percentuais
    - Hidratado = Total - Anidro
    """
    # Calcula percentual de anidro baseado na quinzena
    # Aproximadamente no meio da safra (quinzena 12 de 24) atinge 44%
    meio_safra = n_quinzenas_total / 2

    if quinzena <= meio_safra:
        # Fase crescente: 20% até 44%
        pct_anidro = 0.20 + (quinzena - 1) * 0.02
        pct_anidro = min(pct_anidro, 0.44)
    else:
        # Fase decrescente: diminui 2 pontos percentuais
        pct_anidro = 0.44 - (quinzena - meio_safra) * 0.02
        pct_anidro = max(pct_anidro, 0.20)

    etanol_anidro_cana = etanol_total_cana * pct_anidro
    etanol_hidratado_cana = etanol_total_cana - etanol_anidro_cana

    return etanol_anidro_cana, etanol_hidratado_cana


def calcular_etanol_milho(etanol_total, quinzena, n_quinzenas_total, 
                          etanol_anidro_cana=None, etanol_hidratado_cana=None):
    """
    Calcula produção de etanol de milho (30% do total) e distribui entre anidro e hidratado.
    Ajusta baseado em correlações com produção de cana.
    
    Args:
        etanol_total: Total de etanol (cana + milho)
        quinzena: Número da quinzena
        n_quinzenas_total: Total de quinzenas
        etanol_anidro_cana: Produção de etanol anidro de cana (para correlação)
        etanol_hidratado_cana: Produção de etanol hidratado de cana (para correlação)
    """
    PERCENTUAL_ETANOL_MILHO = 0.30  # 30% do total de etanol é de milho
    etanol_total_milho = etanol_total * PERCENTUAL_ETANOL_MILHO
    
    # Ajusta baseado em correlações com produção de cana
    # Correlação Produção Anidro milho vs Produção Anidro: 0.215098
    # Correlação Produção Hidratado milho vs Produção Anidro: -0.117124
    if etanol_anidro_cana is not None and etanol_anidro_cana > 0:
        # Ajusta anidro milho baseado em correlação positiva com anidro cana
        fator_correlacao_anidro = 1.0 + (0.215098 * (etanol_anidro_cana / etanol_total_milho - 1.0) * 0.1)
        etanol_total_milho = etanol_total_milho * fator_correlacao_anidro
    
    etanol_anidro_milho, etanol_hidratado_milho = calcular_etanol_detalhado(
        etanol_total_milho, quinzena, n_quinzenas_total
    )
    
    # Ajusta hidratado milho baseado em correlação negativa com anidro cana
    if etanol_anidro_cana is not None and etanol_anidro_cana > 0 and etanol_hidratado_milho > 0:
        # Correlação negativa: quando anidro cana aumenta, hidratado milho tende a diminuir
        fator_correlacao_hidratado = 1.0 - (0.117124 * (etanol_anidro_cana / etanol_total_milho - 1.0) * 0.1)
        etanol_hidratado_milho = etanol_hidratado_milho * fator_correlacao_hidratado
    
    return etanol_anidro_milho, etanol_hidratado_milho


def simular_producao_etanol_com_volatilidade(etanol_base, tipo, seed=None, 
                                             preco_anidro=None, preco_hidratado=None,
                                             etanol_anidro_cana=None, etanol_hidratado_cana=None):
    """
    Simula produção de etanol adicionando ruído baseado em volatilidade e desvio padrão.
    Ajusta produção baseado em correlações com preços e produção de cana.

    Args:
        etanol_base: Valor base da produção (m³)
        tipo: Tipo de etanol ('anidro_cana', 'hidratado_cana', 'anidro_milho', 'hidratado_milho')
        seed: Semente para reprodutibilidade (opcional)
        preco_anidro: Preço do etanol anidro (R$/m³) para ajuste por correlação
        preco_hidratado: Preço do etanol hidratado (R$/m³) para ajuste por correlação
        etanol_anidro_cana: Produção de etanol anidro de cana (para correlação milho)
        etanol_hidratado_cana: Produção de etanol hidratado de cana (para correlação milho)

    Returns:
        float: Valor simulado com ruído e ajustes de correlação
    """
    try:
        from Dados_base import (
            VOLATILIDADE_ETANOL_ANIDRO_CANA,
            VOLATILIDADE_ETANOL_HIDRATADO_CANA,
            VOLATILIDADE_ETANOL_ANIDRO_MILHO,
            VOLATILIDADE_ETANOL_HIDRATADO_MILHO,
            DESVIO_PADRAO_ETANOL_ANIDRO_CANA,
            DESVIO_PADRAO_ETANOL_HIDRATADO_CANA,
            DESVIO_PADRAO_ETANOL_ANIDRO_MILHO,
            DESVIO_PADRAO_ETANOL_HIDRATADO_MILHO
        )
    except ImportError:
        # Se não conseguir importar, retorna valor base sem simulação
        return etanol_base

    if etanol_base <= 0:
        return 0.0

    rng = np.random.default_rng(seed)

    # Seleciona parâmetros baseado no tipo
    if tipo == 'anidro_cana':
        volatilidade = VOLATILIDADE_ETANOL_ANIDRO_CANA
        desvio_padrao = DESVIO_PADRAO_ETANOL_ANIDRO_CANA
    elif tipo == 'hidratado_cana':
        volatilidade = VOLATILIDADE_ETANOL_HIDRATADO_CANA
        desvio_padrao = DESVIO_PADRAO_ETANOL_HIDRATADO_CANA
    elif tipo == 'anidro_milho':
        volatilidade = VOLATILIDADE_ETANOL_ANIDRO_MILHO
        desvio_padrao = DESVIO_PADRAO_ETANOL_ANIDRO_MILHO
    elif tipo == 'hidratado_milho':
        volatilidade = VOLATILIDADE_ETANOL_HIDRATADO_MILHO
        desvio_padrao = DESVIO_PADRAO_ETANOL_HIDRATADO_MILHO
    else:
        # Tipo desconhecido, retorna valor base
        return etanol_base

    # Adiciona ruído usando distribuição normal
    # Usa desvio padrão absoluto ou volatilidade relativa, o que for mais apropriado
    # Para valores grandes, usa volatilidade relativa; para valores pequenos, usa desvio padrão
    if etanol_base > desvio_padrao * 2:
        # Usa volatilidade relativa (percentual)
        ruido = rng.normal(0, volatilidade)
        etanol_simulado = etanol_base * (1 + ruido)
    else:
        # Usa desvio padrão absoluto
        ruido = rng.normal(0, desvio_padrao)
        etanol_simulado = etanol_base + ruido
    
    # Ajusta produção baseado em correlações com preços
    # Normaliza preços para ter base de comparação (preço médio esperado ~2500 R$/m³)
    preco_referencia = 2500.0
    
    if tipo == 'anidro_cana' and preco_anidro is not None:
        # Correlação Produção Anidro vs À vista Anidro R$: 0.027573 (muito baixa, mas consideramos)
        variacao_preco = (preco_anidro - preco_referencia) / preco_referencia
        fator_preco = 1.0 + (0.027573 * variacao_preco * 0.5)  # Ajuste suave
        etanol_simulado = etanol_simulado * fator_preco
    
    elif tipo == 'hidratado_cana' and preco_hidratado is not None:
        # Correlação Hidratado vs À vista Hidratado R$: 0.148969
        variacao_preco = (preco_hidratado - preco_referencia) / preco_referencia
        fator_preco = 1.0 + (0.148969 * variacao_preco * 0.5)  # Ajuste moderado
        etanol_simulado = etanol_simulado * fator_preco
    
    elif tipo == 'anidro_milho':
        # Correlação Produção Anidro milho vs À vista Anidro R$: 0.403616 (moderada)
        if preco_anidro is not None:
            variacao_preco = (preco_anidro - preco_referencia) / preco_referencia
            fator_preco = 1.0 + (0.403616 * variacao_preco * 0.5)
            etanol_simulado = etanol_simulado * fator_preco
        
        # Correlação Produção Anidro milho vs Produção Anidro: 0.215098
        if etanol_anidro_cana is not None and etanol_base > 0:
            variacao_cana = (etanol_anidro_cana - etanol_base * 0.7) / (etanol_base * 0.7)
            fator_cana = 1.0 + (0.215098 * variacao_cana * 0.3)
            etanol_simulado = etanol_simulado * fator_cana
    
    elif tipo == 'hidratado_milho':
        # Correlação Produção Hidratado milho vs À vista Hidratado R$: 0.661373 (alta)
        # Correlação Produção Hidratado milho vs À vista Anidro R$: 0.661109 (alta)
        if preco_hidratado is not None:
            variacao_preco = (preco_hidratado - preco_referencia) / preco_referencia
            fator_preco = 1.0 + (0.661373 * variacao_preco * 0.5)  # Ajuste forte
            etanol_simulado = etanol_simulado * fator_preco
        elif preco_anidro is not None:
            variacao_preco = (preco_anidro - preco_referencia) / preco_referencia
            fator_preco = 1.0 + (0.661109 * variacao_preco * 0.5)  # Ajuste forte
            etanol_simulado = etanol_simulado * fator_preco
        
        # Correlação Produção Hidratado milho vs Produção Anidro: -0.117124 (negativa)
        if etanol_anidro_cana is not None and etanol_base > 0:
            variacao_cana = (etanol_anidro_cana - etanol_base * 0.7) / (etanol_base * 0.7)
            fator_cana = 1.0 - (0.117124 * variacao_cana * 0.3)  # Negativa
            etanol_simulado = etanol_simulado * fator_cana

    # Garante que não seja negativo
    return max(0.0, etanol_simulado)


# ============================================================================
# FUNÇÕES DE CONVERSÃO DE PREÇOS (ETANOL E AÇÚCAR)
# ============================================================================

def converter_etanol_para_fob_cents_lb(preco_etanol_pvu_m3, cambio_usd_brl):
    """
    Converte preço do etanol PVU (R$/m³) para equivalente FOB em cents/lb.
    
    IMPORTANTE: O preço de entrada é o preço BRUTO (com impostos).
    Primeiro retira os impostos, depois converte para FOB usando a fórmula exata.
    
    Fórmula Excel: =((((((L7)/31,504)*20)+$C$32+($C$30*$C$4))/22,0462/$C$4)/1,042)
    Onde:
    - L7 = preço líquido PVU (após retirar impostos)
    - C32 = frete em R$/t (202)
    - C30 = terminal em USD/t (12,5)
    - C4 = câmbio
    
    Passos:
    1. Retira ICMS: preco_sem_icms = preco_bruto * (1 - ICMS_ETANOL)
    2. Retira PIS/COFINS: preco_liquido = preco_sem_icms - PIS_COFINS_ETANOL
    3. Aplica fórmula: ((((preco_liquido/31.504)*20) + FRETE_R_T + (TERMINAL_USD_T*cambio)) / 22.0462 / cambio) / 1.042
    
    Parâmetros:
    - preco_etanol_pvu_m3: Preço BRUTO do etanol PVU em R$/m³ (com impostos)
    - cambio_usd_brl: Taxa de câmbio USD/BRL
    
    Retorna: Preço equivalente FOB em cents/lb
    
    Nota: ICMS_ETANOL, PIS_COFINS_ETANOL, FRETE_R_T e TERMINAL_USD_T são constantes de Dados_base.py
    """
    if cambio_usd_brl <= 0 or preco_etanol_pvu_m3 <= 0:
        return 0.0
    
    # Passo 1: Retira ICMS (12%)
    preco_sem_icms = preco_etanol_pvu_m3 * (1 - ICMS_ETANOL)
    
    # Passo 2: Retira PIS e COFINS (R$ 192,2)
    preco_liquido_pvu = preco_sem_icms - PIS_COFINS_ETANOL
    
    # Garante que não seja negativo
    if preco_liquido_pvu <= 0:
        return 0.0
    
    # Passo 3: Aplica fórmula exata do Excel
    # =((((((L7)/31,504)*20)+$C$32+($C$30*$C$4))/22,0462/$C$4)/1,042)
    # Onde:
    # - (preco_liquido/31.504)*20 = equivalente VHP em R$/saco
    # - + FRETE_R_T = adiciona frete em R$/t
    # - + (TERMINAL_USD_T*cambio) = adiciona terminal em R$/t
    # - /22.0462/cambio = converte para cents/lb
    # - /1.042 = ajuste de qualidade
    
    # Aplica fórmula exata: =((((((L7)/31,504)*20)+$C$32+($C$30*$C$4))/22,0462/$C$4)/1,042)
    # Ordem: divide por 22.0462, depois divide por cambio
    equivalente_vhp_r_por_saco = (preco_liquido_pvu / FATOR_CONVERSAO_ETANOL_VHP) * SACAS_POR_TONELADA
    numerador = equivalente_vhp_r_por_saco + FRETE_R_T + (TERMINAL_USD_T * cambio_usd_brl)
    # Divide por 22.0462, depois divide por cambio (equivalente a dividir por 22.0462*cambio)
    preco_fob_cents_lb = (numerador / CENTS_LB_POR_TON / cambio_usd_brl) / FATOR_AJUSTE_QUALIDADE
    
    return preco_fob_cents_lb


def converter_acucar_vhp_para_fob(preco_ny11_cents_lb):
    """
    Converte preço do açúcar VHP (NY11) para FOB em cents/lb.
    
    Fórmula: FOB = (NY11 - DESCONTO_VHP_FOB) * (1 + TAXA_POL)
    Primeiro subtrai o desconto, depois aplica o prêmio de polarização.
    
    ⚠️ IMPORTANTE: Para alterar o desconto ou taxa de pol, edite Dados_base.py:
       - DESCONTO_VHP_FOB = 0.10  (desconto em cents/lb)
       - TAXA_POL = 0.045          (taxa de polarização: 4,5%)
    
    Parâmetros:
    - preco_ny11_cents_lb: Preço NY11 em USc/lb (preço puro da bolsa)
    
    Retorna: Preço FOB em cents/lb
    """
    if preco_ny11_cents_lb <= 0:
        return 0.0
    
    # Aplica fórmula: FOB = (NY11 - DESCONTO_VHP_FOB) * (1 + TAXA_POL)
    # Primeiro subtrai o desconto (0.10), depois multiplica por (1 + 0.045)
    preco_fob = (preco_ny11_cents_lb - DESCONTO_VHP_FOB) * (1 + TAXA_POL)
    return max(0.0, preco_fob)  # Garante que não seja negativo


def calcular_paridade_etanol_acucar(preco_etanol_pvu_m3, preco_ny11_cents_lb, cambio_usd_brl):
    """
    Calcula paridade etanol/açúcar comparando equivalentes FOB em cents/lb.
    Retorna relação: > 1 = etanol mais atrativo, < 1 = açúcar mais atrativo
    
    Converte ambos (etanol e açúcar) para FOB em cents/lb antes de comparar.
    
    IMPORTANTE:
    - Etanol: preço de entrada é BRUTO (com impostos). Retira ICMS e PIS/COFINS antes de converter.
    - Açúcar: preço de entrada é o preço PURO da bolsa (NY11). Aplica desconto e prêmio de pol.
    
    Parâmetros:
    - preco_etanol_pvu_m3: Preço BRUTO do etanol PVU em R$/m³ (com impostos)
    - preco_ny11_cents_lb: Preço NY11 em USc/lb (preço puro da bolsa)
    - cambio_usd_brl: Taxa de câmbio USD/BRL
    
    Nota: 
    - Etanol usa ICMS_ETANOL, PIS_COFINS_ETANOL, FRETE_R_T e TERMINAL_USD_T de Dados_base.py
    - Açúcar usa DESCONTO_VHP_FOB e TAXA_POL de Dados_base.py
    """
    if preco_ny11_cents_lb <= 0:
        return 1.0
    
    # Converte etanol para FOB cents/lb
    preco_etanol_fob_cents_lb = converter_etanol_para_fob_cents_lb(preco_etanol_pvu_m3, cambio_usd_brl)
    
    if preco_etanol_fob_cents_lb <= 0:
        return 1.0
    
    # Converte açúcar VHP para FOB cents/lb (usa TAXA_POL fixa de 4,5%)
    preco_acucar_fob_cents_lb = converter_acucar_vhp_para_fob(preco_ny11_cents_lb)
    
    if preco_acucar_fob_cents_lb <= 0:
        return 1.0
    
    # Paridade: quanto maior, mais atrativo o etanol
    paridade = preco_etanol_fob_cents_lb / preco_acucar_fob_cents_lb
    
    return paridade


# ============================================================================
# CONSTANTES E PARÂMETROS
# ============================================================================

LB_POR_TON = 2204.62
CENTS_LB_POR_TON = 22.0462  # 2204.62 / 100

# Fatores de conversão etanol
FATOR_CONVERSAO_ETANOL_VHP = 31.504
SACAS_POR_TONELADA = 20
FATOR_AJUSTE_QUALIDADE = 1.042

# Volatilidades e correlações padrão
DEFAULT_PRICE_VOLS = {
    "sugar": 0.282222,
    "usdbrl": 0.15098,
    "ethanol": 0.25126,
}

RHO_SUGAR_ETHANOL = 0.502463893713162
RHO_SUGAR_USDBRL = 0.786767236856384
RHO_ETHANOL_USDBRL = 0.452409814996351

DEFAULT_CORR_MATRIX = np.array([
    [1.0, RHO_SUGAR_ETHANOL, RHO_SUGAR_USDBRL],
    [RHO_SUGAR_ETHANOL, 1.0, RHO_ETHANOL_USDBRL],
    [RHO_SUGAR_USDBRL, RHO_ETHANOL_USDBRL, 1.0]
])


def ny11_para_brl(cents_lb: float, usdbrl: float) -> float:
    """Converte NY11 (USc/lb) e USD/BRL em R$/t"""
    usd_per_ton = (cents_lb / 100.0) * LB_POR_TON
    return usd_per_ton * usdbrl


def gerar_simulacao_quinzenal(moagem_total, atr_medio, mix_medio, n_quinzenas=24, 
                               data_inicio=None, choques_safra=None, seed=42):
    """
    Gera distribuição quinzenal de moagem, ATR e MIX baseado em perfis históricos.
    
    Usa perfis históricos (PERFIL_ATR e PERFIL_MIX) e aplica fatores de correção
    baseados nos valores totais desejados, seguindo a lógica:
    - ATR: valor_simulado * SOMA(Moagem) / SOMARPRODUTO(Moagem_distribuída; Perfil_ATR)
    - Mix: valor_simulado * moagem_total / SOMARPRODUTO(Moagem_distribuída; Perfil_mix)
    """
    if data_inicio is None:
        data_inicio = date(date.today().year, 4, 1)

    rng = np.random.default_rng(seed)
    
    # Curva de distribuição (formato sino - mais moagem no meio da safra)
    x = np.linspace(-2, 2, n_quinzenas)
    pesos = np.exp(-x ** 2 / 0.8)
    pct_moagem = pesos / pesos.sum()
    
    datas = pd.date_range(start=data_inicio, periods=n_quinzenas, freq="15D")
    
    # Primeiro, calcula moagem distribuída (sem choques ainda)
    moagem_distribuida = [moagem_total * pct_moagem[i] for i in range(n_quinzenas)]
    soma_moagem = sum(moagem_distribuida)
    
    # Usa perfis históricos (cicla se necessário)
    n_perfil = len(PERFIL_ATR)
    perfil_atr_ajustado = [PERFIL_ATR[i % n_perfil] for i in range(n_quinzenas)]
    perfil_mix_ajustado = [PERFIL_MIX[i % n_perfil] for i in range(n_quinzenas)]
    
    # Calcula SOMARPRODUTO para ATR e Mix
    somarproduto_atr = sum(moagem_distribuida[i] * perfil_atr_ajustado[i] for i in range(n_quinzenas))
    somarproduto_mix = sum(moagem_distribuida[i] * perfil_mix_ajustado[i] for i in range(n_quinzenas))
    
    # Calcula fatores de correção
    # ATR: valor_simulado * SOMA(Moagem) / SOMARPRODUTO(Moagem; Perfil_ATR)
    fator_atr = (atr_medio * soma_moagem) / somarproduto_atr if somarproduto_atr > 0 else 1.0
    
    # Mix: valor_simulado * moagem_total / SOMARPRODUTO(Moagem; Perfil_mix)
    fator_mix = (mix_medio * moagem_total) / somarproduto_mix if somarproduto_mix > 0 else 1.0
    
    linhas = []
    for i in range(n_quinzenas):
        quinzena = i + 1
        
        # Calcula valores base usando perfis ajustados
        moagem_q = moagem_distribuida[i]
        atr_q = perfil_atr_ajustado[i] * fator_atr
        mix_q = perfil_mix_ajustado[i] * fator_mix
        
        # Aplica choques de safra se houver (suporta múltiplos choques por quinzena)
        if choques_safra and quinzena in choques_safra:
            choques_quinzena = choques_safra[quinzena]
            # Suporta tanto formato antigo (dict único) quanto novo (lista de dicts)
            if isinstance(choques_quinzena, dict):
                choques_quinzena = [choques_quinzena]
            
            for choque in choques_quinzena:
                tipo = choque.get('tipo', '')
                magnitude = choque.get('magnitude', 0.0)
                
                if tipo == 'Moagem':
                    moagem_q = moagem_q * (1 + magnitude / 100)
                elif tipo == 'ATR':
                    atr_q = atr_q * (1 + magnitude / 100)
                elif tipo == 'MIX':
                    mix_q = mix_q * (1 + magnitude / 100)
        
        # Garante limites razoáveis
        mix_q = max(0, min(100, mix_q))
        atr_q = max(0, atr_q)
        
        linhas.append({
            "Quinzena": quinzena,
            "Mês": datas[i].month,
            "Data": datas[i].date(),
            "Moagem": moagem_q,
            "ATR": atr_q,
            "MIX": mix_q,
        })
    
    return pd.DataFrame(linhas)


# ============================================================================
# FUNÇÕES DE AJUSTE DE MIX POR PARIDADE
# ============================================================================

def ajustar_mix_por_paridade(mix_atual, paridade, sensibilidade=0.20):
    """
    Ajusta mix baseado na paridade etanol/açúcar.
    Se etanol mais atrativo (paridade > 1.0), reduz mix açúcar.
    Se açúcar mais atrativo (paridade < 1.0), aumenta mix açúcar.
    
    sensibilidade: quanto maior, mais o mix reage à paridade (padrão 20%)
    """
    # Paridade > 1.0 = etanol mais atrativo → reduz mix açúcar
    # Paridade < 1.0 = açúcar mais atrativo → aumenta mix açúcar
    if paridade > 1.0:
        # Etanol mais atrativo: reduz mix proporcionalmente
        ajuste = -sensibilidade * (paridade - 1.0) * 10  # Multiplica por 10 para ter impacto visível
    elif paridade < 1.0:
        # Açúcar mais atrativo: aumenta mix proporcionalmente
        ajuste = sensibilidade * (1.0 - paridade) * 10
    else:
        ajuste = 0
    
    mix_ajustado = mix_atual + ajuste
    return max(0, min(100, mix_ajustado))


# ============================================================================
# FUNÇÕES DE SIMULAÇÃO DE PREÇOS
# ============================================================================

def simular_precos(ny11_inicial, usd_inicial, etanol_inicial, n_quinzenas, 
                   df_producao, preco_ref=15.0, sensibilidade=0.10, 
                   choques_precos=None, usar_paridade=True, seed=123,
                   estoques_globais="Neutro", nivel_estoques=0.0):
    """
    Simula preços considerando:
    - Volatilidade e correlação entre commodities
    - Impacto da oferta (produção informada) nos preços
    - Interação preço inicial vs produção
    - Paridade etanol/açúcar (ajusta mix dinamicamente)
    - Choques externos (opcional)
    - Estoques globais (déficit/superávit) que impactam preços
    """
    rng = np.random.default_rng(seed)
    
    # Volatilidades
    vols = np.array([DEFAULT_PRICE_VOLS["sugar"], DEFAULT_PRICE_VOLS["ethanol"], DEFAULT_PRICE_VOLS["usdbrl"]])
    dt = 1.0 / 24.0
    cov_annual = np.outer(vols, vols) * DEFAULT_CORR_MATRIX
    cov_step = cov_annual * dt
    
    # Retornos correlacionados
    rets = rng.multivariate_normal(mean=[0.0, 0.0, 0.0], cov=cov_step, size=n_quinzenas)
    
    # Calcula produção total informada
    producao_total = 0
    for _, row in df_producao.iterrows():
        mix = row["MIX"] / 100
        producao_total += ((row["Moagem"] * mix * row["ATR"]) * FATOR_ACUCAR) / 1000
    
    producao_media = producao_total / n_quinzenas
    
    # Classifica preço inicial (alto/baixo) apenas para lógica de interação
    desvio_preco = (ny11_inicial - preco_ref) / preco_ref if preco_ref > 0 else 0
    
    # Calcula fator de oferta baseado na produção informada
    # Usa produção média por quinzena para calcular impacto proporcional
    # Produção maior → mais oferta → pressiona preços
    # Aplica sensibilidade proporcionalmente à produção média
    # Normaliza para produção média típica (~1.5M ton/quinzena) para ter impacto razoável
    producao_normalizada = producao_media / 1_500_000  # Normaliza para ter base de comparação
    fator_oferta_base = 1.0 - ((producao_normalizada - 1.0) * sensibilidade)
    
    # Aplica impacto dos estoques globais
    fator_estoques = 1.0
    if estoques_globais == "Déficit":
        # Déficit: suporta preços (tendência de alta)
        # Quanto maior o déficit, mais suporte aos preços
        # Déficit + alta produção = suporte ainda maior (escassez)
        fator_estoques = 1.0 + (nivel_estoques / 100) * 0.5  # Até 25% de suporte adicional
        if producao_normalizada > 1.0:  # Alta produção com déficit
            # Déficit + alta produção = forte suporte aos preços
            fator_estoques *= 1.1
    elif estoques_globais == "Superávit":
        # Superávit: pressiona preços (tendência de queda)
        # Quanto maior o superávit, mais pressão nos preços
        # Superávit + grande produção = pressão ainda maior
        fator_estoques = 1.0 - (nivel_estoques / 100) * 0.5  # Até 25% de pressão adicional
        if producao_normalizada > 1.0:  # Grande produção com superávit
            # Superávit + grande produção = forte pressão nos preços
            fator_estoques *= 0.9
    
    # Ajusta baseado na interação preço inicial vs produção vs estoques
    if desvio_preco < -0.05:  # Preço baixo
        if producao_normalizada > 1.0:  # Produção acima da normalizada
            fator_oferta = fator_oferta_base * 0.9 * fator_estoques
            direcao = "queda" if fator_estoques < 1.0 else "alta"
        else:  # Produção abaixo da normalizada
            fator_oferta = fator_oferta_base * 1.1 * fator_estoques
            direcao = "alta"
    elif desvio_preco > 0.05:  # Preço alto
        if producao_normalizada > 1.0:  # Produção acima da normalizada
            fator_oferta = fator_oferta_base * 1.05 * fator_estoques
            direcao = "alta" if fator_estoques > 1.0 else "queda"
        else:  # Produção abaixo da normalizada
            fator_oferta = fator_oferta_base * 1.15 * fator_estoques
            direcao = "alta"
    else:  # Preço neutro
        fator_oferta = fator_oferta_base * fator_estoques
        direcao = "alta" if fator_oferta > 1.0 else "queda" if fator_oferta < 1.0 else "neutro"
    
    fator_oferta = np.clip(fator_oferta, 0.5, 1.5)  # Amplia range para permitir maior impacto dos estoques
    
    # Simula trajetória
    ny11 = [ny11_inicial]
    etanol = [etanol_inicial]
    usd = [usd_inicial]
    
    choques_aplicados = []
    mix_dinamico = df_producao.iloc[0]["MIX"] if len(df_producao) > 0 else 48.0
    
    # Armazena mix ajustado por quinzena para recalcular produção
    mix_ajustado_por_quinzena = []
    
    for i in range(n_quinzenas):
        quinzena = i + 1
        r_sugar, r_eth, r_usd = rets[i]
        
        # Verifica choques de preços
        if choques_precos and quinzena in choques_precos:
            choque = choques_precos[quinzena]
            tipo = choque.get('tipo', '')
            magnitude = choque.get('magnitude', 0.0)
            
            if tipo == 'NY11':
                ny11[-1] = ny11[-1] * (1 + magnitude / 100)
                choques_aplicados.append(f"Q{quinzena}: NY11 {magnitude:+.1f}%")
            elif tipo == 'USD':
                usd[-1] = usd[-1] * (1 + magnitude / 100)
                choques_aplicados.append(f"Q{quinzena}: USD {magnitude:+.1f}%")
        
        # Calcula paridade etanol/açúcar e ajusta mix dinamicamente
        mix_base = df_producao.iloc[i]["MIX"] if i < len(df_producao) else mix_dinamico
        
        # Ajusta mix baseado em estoques globais e paridade
        mix_dinamico = mix_base
        
        # Impacto dos estoques globais no mix
        # Superávit + grande produção pode pressionar preços e ocasionar variação no mix
        if estoques_globais == "Superávit" and producao_normalizada > 1.0:
            # Superávit + grande produção: reduz mix (menos açúcar, mais etanol)
            # Quanto maior o superávit e produção, maior a redução
            reducao_mix_estoques = (nivel_estoques / 100) * (producao_normalizada - 1.0) * 5.0
            mix_dinamico = mix_dinamico - reducao_mix_estoques
        elif estoques_globais == "Déficit" and producao_normalizada < 1.0:
            # Déficit + baixa produção: aumenta mix (mais açúcar, menos etanol)
            # Quanto maior o déficit e menor a produção, maior o aumento
            aumento_mix_estoques = (nivel_estoques / 100) * (1.0 - producao_normalizada) * 3.0
            mix_dinamico = mix_dinamico + aumento_mix_estoques
        
        if usar_paridade:
            # Calcula paridade: etanol FOB vs açúcar FOB (ambos em cents/lb)
            # Nota: TAXA_POL fixa (4,5%) e DESCONTO_VHP_FOB (0,10) definidos em Dados_base.py
            paridade = calcular_paridade_etanol_acucar(etanol[-1], ny11[-1], usd[-1])
            
            # Ajusta mix baseado na paridade (impacto direto na produção)
            # Combina ajuste de estoques com ajuste de paridade
            mix_dinamico = ajustar_mix_por_paridade(mix_dinamico, paridade)
        
        # Garante limites
        mix_dinamico = max(0, min(100, mix_dinamico))
        
        mix_ajustado_por_quinzena.append(mix_dinamico)
        
        # Ajusta fator de oferta se mix foi alterado por paridade
        if usar_paridade and mix_dinamico != mix_base:
            # Mix alterado → produção alterada → ajusta fator de oferta
            # Mix menor = menos açúcar = oferta menor = preço melhor
            if mix_dinamico < mix_base:
                fator_oferta_ajustado = fator_oferta * 1.05  # Reduz oferta
            else:
                fator_oferta_ajustado = fator_oferta * 0.95  # Aumenta oferta
            fator_oferta_ajustado = np.clip(fator_oferta_ajustado, 0.7, 1.3)
        else:
            fator_oferta_ajustado = fator_oferta
        
        # Aplica impacto da oferta no açúcar
        r_sugar_ajustado = r_sugar * fator_oferta_ajustado
        drift = (fator_oferta_ajustado - 1.0) * 0.12
        
        ny11.append(ny11[-1] * (1 + r_sugar_ajustado + drift))
        etanol.append(etanol[-1] * (1 + r_eth))
        usd.append(usd[-1] * (1 + r_usd))
    
    df_precos = pd.DataFrame({
        "Quinzena": np.arange(1, n_quinzenas + 1),
        "NY11_cents": ny11[1:],
        "Etanol_R$m3": etanol[1:],
        "USD_BRL": usd[1:],
    })
    
    # Retorna também os mix ajustados para uso na produção final
    return df_precos, direcao, fator_oferta, choques_aplicados, mix_ajustado_por_quinzena


# ============================================================================
# FUNÇÕES AUXILIARES DE INTERFACE
# ============================================================================

def agrupar_choques(choques_dict):
    """Agrupa choques consecutivos do mesmo tipo e magnitude"""
    if not choques_dict:
        return []
    
    # Expande choques que estão em listas
    choques_expandidos = []
    for q, choque_data in sorted(choques_dict.items()):
        # Suporta tanto formato antigo (dict único) quanto novo (lista de dicts)
        if isinstance(choque_data, list):
            for choque in choque_data:
                choques_expandidos.append((q, choque))
        else:
            choques_expandidos.append((q, choque_data))
    
    grupos = []
    grupo_atual = None
    
    for q, choque in choques_expandidos:
        chave = (choque['tipo'], choque['magnitude'])
        if grupo_atual is None or grupo_atual['chave'] != chave or q != grupo_atual['fim'] + 1:
            if grupo_atual:
                grupos.append(grupo_atual)
            grupo_atual = {'chave': chave, 'tipo': choque['tipo'], 'magnitude': choque['magnitude'],
                          'inicio': q, 'fim': q, 'quinzenas': [q]}
        else:
            grupo_atual['fim'] = q
            grupo_atual['quinzenas'].append(q)
    
    if grupo_atual:
        grupos.append(grupo_atual)
    
    return grupos


def criar_widget_choques(titulo, caption, tipos_choque, session_key, n_quinzenas, permitir_multiplos=True):
    """
    Cria widget genérico para gerenciar choques (safra ou preços)
    
    Args:
        permitir_multiplos: Se True, permite múltiplos choques na mesma quinzena (útil para safra)
    """
    with st.sidebar.expander(titulo, expanded=False):
        st.caption(caption)
        
        if session_key not in st.session_state:
            st.session_state[session_key] = {}
        
        col_periodo1, col_periodo2 = st.columns(2)
        with col_periodo1:
            quinzena_inicio = st.number_input("Quinzena início", min_value=1, max_value=n_quinzenas, 
                                             value=12, step=1, key=f"{session_key}_inicio")
        with col_periodo2:
            quinzena_fim = st.number_input("Quinzena fim", min_value=1, max_value=n_quinzenas, 
                                         value=12, step=1, key=f"{session_key}_fim")
        
        periodo_valido = quinzena_fim >= quinzena_inicio
        if not periodo_valido:
            st.warning("⚠️ Quinzena fim deve ser >= quinzena início")
        
        tipo_choque = st.selectbox("Tipo de choque", tipos_choque, key=f"{session_key}_tipo")
        magnitude_choque = st.number_input("Magnitude (%)", min_value=-50.0, max_value=50.0, 
                                          value=0.0, step=1.0, format="%.1f", key=f"{session_key}_magnitude")
        
        if magnitude_choque != 0 and periodo_valido:
            periodo_texto = f"Q{quinzena_inicio}" if quinzena_inicio == quinzena_fim else f"Q{quinzena_inicio}-{quinzena_fim}"
            if magnitude_choque > 0:
                st.success(f"✅ {tipo_choque} +{abs(magnitude_choque):.1f}% na {periodo_texto}")
            else:
                st.error(f"❌ {tipo_choque} {magnitude_choque:.1f}% na {periodo_texto}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Aplicar", use_container_width=True, disabled=not periodo_valido, key=f"btn_aplicar_{session_key}"):
                novo_choque = {
                    'tipo': tipo_choque,
                    'magnitude': magnitude_choque
                }
                
                for q in range(quinzena_inicio, quinzena_fim + 1):
                    if permitir_multiplos:
                        # Permite múltiplos choques por quinzena
                        if q not in st.session_state[session_key]:
                            st.session_state[session_key][q] = []
                        elif not isinstance(st.session_state[session_key][q], list):
                            # Converte formato antigo para lista
                            st.session_state[session_key][q] = [st.session_state[session_key][q]]
                        st.session_state[session_key][q].append(novo_choque.copy())
                    else:
                        # Substitui choque existente (comportamento antigo para preços)
                        st.session_state[session_key][q] = novo_choque.copy()
                st.rerun()
        with col2:
            if st.button("🗑️ Remover Todos", use_container_width=True, key=f"btn_remover_{session_key}"):
                st.session_state[session_key] = {}
                st.rerun()
        
        # Lista choques ativos (agrupados)
        if st.session_state[session_key]:
            st.write("**Choques ativos:**")
            grupos = agrupar_choques(st.session_state[session_key])
            
            for idx, grupo in enumerate(grupos):
                periodo_display = f"Q{grupo['inicio']}" if grupo['inicio'] == grupo['fim'] else f"Q{grupo['inicio']}-{grupo['fim']}"
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    mag = grupo['magnitude']
                    if mag > 0:
                        st.success(f"{periodo_display}: {grupo['tipo']} **+{mag:.1f}%**")
                    elif mag < 0:
                        st.error(f"{periodo_display}: {grupo['tipo']} **{mag:.1f}%**")
                    else:
                        st.write(f"{periodo_display}: {grupo['tipo']} {mag:.1f}%")
                with col_b:
                    # Usa índice, tipo e magnitude para garantir chave única
                    # Remove caracteres especiais da magnitude para evitar problemas na chave
                    mag_str = str(grupo['magnitude']).replace('.', '_').replace('-', 'neg')
                    chave_unica = f"remove_{session_key}_{idx}_{grupo['tipo']}_{mag_str}_{grupo['inicio']}_{grupo['fim']}"
                    if st.button("❌", key=chave_unica, use_container_width=True):
                        # Remove choques do período
                        for q in grupo['quinzenas']:
                            if q in st.session_state[session_key]:
                                if isinstance(st.session_state[session_key][q], list):
                                    # Remove choques do tipo e magnitude específicos
                                    st.session_state[session_key][q] = [
                                        ch for ch in st.session_state[session_key][q]
                                        if not (ch['tipo'] == grupo['tipo'] and ch['magnitude'] == grupo['magnitude'])
                                    ]
                                    # Remove a quinzena se não houver mais choques
                                    if not st.session_state[session_key][q]:
                                        del st.session_state[session_key][q]
                                else:
                                    del st.session_state[session_key][q]
                        st.rerun()


def calcular_producao_total_quinzenal(df_base, mix_ajustado=None):
    """Calcula produção total a partir de dados quinzenais"""
    acucar_total = 0
    etanol_total = 0
    
    for i, row in df_base.iterrows():
        if mix_ajustado and i < len(mix_ajustado):
            mix_q = mix_ajustado[i] / 100
        else:
            mix_q = row["MIX"] / 100
        
        acucar_q, etanol_q = calcular_producao_quinzenal(row["Moagem"], row["ATR"], mix_q * 100)
        acucar_total += acucar_q
        etanol_total += etanol_q
    
    return acucar_total, etanol_total


# ============ INTERFACE ============

st.markdown("<h1 style='text-align: center; margin-bottom: 5px;'>Análise de Safra 🌾</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="text-align: center; color: #666; font-size: 0.9em; margin-top: 0px; margin-bottom: 20px;">Desenvolvido por Rogério Guilherme Jr.</p>',
    unsafe_allow_html=True
)

try:
    df_hist = load_historico_safra()
except:
    df_hist = pd.DataFrame()

# ============ SIDEBAR ============
st.sidebar.header("📊 Parâmetros da Safra")

# Inicializa parâmetros de simulação no session_state se não existirem
if 'analise_moagem' not in st.session_state:
    st.session_state.analise_moagem = 600_000_000
if 'analise_atr' not in st.session_state:
    st.session_state.analise_atr = 135.0
if 'analise_mix' not in st.session_state:
    st.session_state.analise_mix = 48.0
if 'analise_n_quinz' not in st.session_state:
    st.session_state.analise_n_quinz = 24
if 'analise_data_start' not in st.session_state:
    st.session_state.analise_data_start = date(date.today().year, 4, 1)
if 'analise_ny11_inicial' not in st.session_state:
    st.session_state.analise_ny11_inicial = 14.90
if 'analise_usd_inicial' not in st.session_state:
    st.session_state.analise_usd_inicial = 4.90
if 'analise_etanol_inicial' not in st.session_state:
    st.session_state.analise_etanol_inicial = 2500.0
if 'analise_preco_ref' not in st.session_state:
    st.session_state.analise_preco_ref = 15.0
if 'analise_sensibilidade' not in st.session_state:
    st.session_state.analise_sensibilidade = 10.0
if 'analise_usar_paridade' not in st.session_state:
    st.session_state.analise_usar_paridade = False
if 'analise_estoques_globais' not in st.session_state:
    st.session_state.analise_estoques_globais = "Neutro"  # "Déficit", "Superávit", "Neutro"
if 'analise_nivel_estoques' not in st.session_state:
    st.session_state.analise_nivel_estoques = 0.0  # Nível de déficit/superávit em %

moagem = st.sidebar.number_input(
    "Moagem total (ton)",
    value=st.session_state.analise_moagem,
    step=10_000_000,
    key="input_analise_moagem"
)
atr = st.sidebar.number_input(
    "ATR médio (kg/t)",
    value=st.session_state.analise_atr,
    step=1.0,
    format="%.1f",
    key="input_analise_atr"
)
mix = st.sidebar.number_input(
    "Mix açúcar (%)",
    value=st.session_state.analise_mix,
    step=1.0,
    format="%.1f",
    key="input_analise_mix"
)

# Salva valores no session_state quando alterados
st.session_state.analise_moagem = moagem
st.session_state.analise_atr = atr
st.session_state.analise_mix = mix

st.sidebar.divider()

st.sidebar.subheader("💰 Preços Iniciais")
st.sidebar.caption("💡 **Preço inicial** = o preço REAL que você acredita que vai começar a safra")
ny11_inicial = st.sidebar.number_input(
    "NY11 inicial (USc/lb)",
    value=st.session_state.analise_ny11_inicial,
    step=0.10,
    format="%.2f",
    help="Preço REAL de início da safra",
    key="input_analise_ny11"
)
usd_inicial = st.sidebar.number_input(
    "USD/BRL inicial",
    value=st.session_state.analise_usd_inicial,
    step=0.01,
    format="%.2f",
    key="input_analise_usd"
)
etanol_inicial = st.sidebar.number_input(
    "Etanol inicial (R$/m³)",
    value=st.session_state.analise_etanol_inicial,
    step=50.0,
    format="%.0f",
    key="input_analise_etanol"
)

# Salva valores no session_state quando alterados
st.session_state.analise_ny11_inicial = ny11_inicial
st.session_state.analise_usd_inicial = usd_inicial
st.session_state.analise_etanol_inicial = etanol_inicial

st.sidebar.divider()

st.sidebar.subheader("⚙️ Simulação")
n_quinz = st.sidebar.number_input(
    "Nº de quinzenas",
    value=st.session_state.analise_n_quinz,
    min_value=4,
    max_value=24,
    step=1,
    key="input_analise_n_quinz"
)
data_start = st.sidebar.date_input(
    "Início da safra",
    value=st.session_state.analise_data_start,
    key="input_analise_data_start"
)

# Salva valores no session_state quando alterados
st.session_state.analise_n_quinz = n_quinz
st.session_state.analise_data_start = data_start

with st.sidebar.expander("🔧 Parâmetros Avançados", expanded=False):
    st.caption("⚙️ Ajustes finos da simulação (opcional)")
    st.markdown("**📊 Preço Referência NY11**")
    st.caption("Parâmetro de CALIBRAÇÃO para classificar se preço inicial está 'alto' ou 'baixo'")
    preco_ref = st.number_input(
        "Preço referência NY11 (USc/lb)",
        value=st.session_state.analise_preco_ref,
        step=0.5,
        format="%.1f",
        key="input_analise_preco_ref"
    )
    
    st.markdown("**📈 Sensibilidade Oferta → Preço**")
    sensibilidade = st.slider(
        "Sensibilidade oferta → preço (%)",
        0.0, 30.0,
        st.session_state.analise_sensibilidade,
        1.0,
        key="input_analise_sensibilidade"
    )
    
    st.markdown("**🔄 Paridade Etanol/Açúcar**")
    usar_paridade = st.checkbox(
        "Usar paridade etanol/açúcar",
        value=st.session_state.analise_usar_paridade,
        help="Ajusta mix dinamicamente baseado na atratividade relativa",
        key="input_analise_usar_paridade"
    )
    
    # Salva valores no session_state quando alterados
    st.session_state.analise_preco_ref = preco_ref
    st.session_state.analise_sensibilidade = sensibilidade
    st.session_state.analise_usar_paridade = usar_paridade

st.sidebar.divider()

st.sidebar.subheader("📦 Estoques Globais")
st.sidebar.caption("💡 Configure o cenário de estoques globais de açúcar para impactar os preços")
estoques_globais = st.sidebar.selectbox(
    "Situação dos Estoques",
    ["Neutro", "Déficit", "Superávit"],
    index=["Neutro", "Déficit", "Superávit"].index(st.session_state.analise_estoques_globais),
    key="input_analise_estoques_globais"
)

if estoques_globais != "Neutro":
    nivel_estoques = st.sidebar.slider(
        f"Nível de {estoques_globais} (%)",
        min_value=0.0,
        max_value=50.0,
        value=st.session_state.analise_nivel_estoques,
        step=1.0,
        format="%.1f",
        key="input_analise_nivel_estoques",
        help=f"Quanto maior o {estoques_globais.lower()}, maior o impacto nos preços"
    )
    st.session_state.analise_nivel_estoques = nivel_estoques
else:
    st.session_state.analise_nivel_estoques = 0.0

st.session_state.analise_estoques_globais = estoques_globais

# Choques de SAFRA (permite múltiplos choques por quinzena)
criar_widget_choques("🌾 Choques de Safra", "Simule eventos que afetam a PRODUÇÃO (moagem, ATR, mix)",
                     ["Moagem", "ATR", "MIX"], "choques_safra", int(n_quinz), permitir_multiplos=True)

st.sidebar.divider()

# Choques de PREÇOS (substitui choque existente na mesma quinzena)
criar_widget_choques("⚡ Choques de Preços", "Simule eventos que afetam PREÇOS (NY11, USD)",
                     ["NY11", "USD"], "choques", int(n_quinz), permitir_multiplos=False)

# ============ CÁLCULOS ============

choques_safra = st.session_state.get('choques_safra', {})
df_base = gerar_simulacao_quinzenal(moagem, atr, mix, int(n_quinz), data_start, 
                                    choques_safra if choques_safra else None)

acucar_total_base, etanol_total_base = calcular_producao(moagem, atr, mix)
acucar_total_com_choques, etanol_total_com_choques = calcular_producao_total_quinzenal(df_base)

acucar_total = acucar_total_com_choques if choques_safra else acucar_total_base
etanol_total = etanol_total_com_choques if choques_safra else etanol_total_base

choques_precos = st.session_state.get('choques', {})
df_precos, direcao, fator_oferta, choques_aplicados, mix_ajustado = simular_precos(
    ny11_inicial, usd_inicial, etanol_inicial, int(n_quinz),
    df_base, preco_ref, sensibilidade / 100, 
    choques_precos if choques_precos else None, usar_paridade,
    seed=123,
    estoques_globais=estoques_globais,
    nivel_estoques=st.session_state.analise_nivel_estoques
)

# Recalcula produção final considerando mix ajustado por paridade
if usar_paridade and mix_ajustado:
    acucar_total_paridade, etanol_total_paridade = calcular_producao_total_quinzenal(df_base, mix_ajustado)
    if acucar_total_paridade > 0:
        acucar_total = acucar_total_paridade
        etanol_total = etanol_total_paridade

df_completo = df_base.merge(df_precos, on="Quinzena")

# Calcula produção quinzenal de açúcar e etanol
producao_acucar_quinzenal = []
producao_etanol_quinzenal = []
producao_etanol_anidro_cana = []
producao_etanol_hidratado_cana = []
producao_etanol_anidro_milho = []
producao_etanol_hidratado_milho = []

for i, row in df_completo.iterrows():
    # Usa mix ajustado por paridade se disponível, senão usa o mix original
    if usar_paridade and mix_ajustado and i < len(mix_ajustado):
        mix_quinzena = mix_ajustado[i]
    else:
        mix_quinzena = row["MIX"]
    
    acucar_q, etanol_q = calcular_producao_quinzenal(row["Moagem"], row["ATR"], mix_quinzena)
    producao_acucar_quinzenal.append(acucar_q)
    producao_etanol_quinzenal.append(etanol_q)
    
    # Calcula etanol detalhado (cana e milho)
    quinzena = row["Quinzena"]
    etanol_anidro_cana_base, etanol_hidratado_cana_base = calcular_etanol_detalhado(
        etanol_q, quinzena, int(n_quinz)
    )
    
    # Obtém preços da quinzena (se disponíveis)
    preco_anidro = row.get("Etanol_Anidro_R$m3", None)
    preco_hidratado = row.get("Etanol_Hidratado_R$m3", None)
    
    # Aplica simulação com volatilidade para cana (primeiro, sem dependência de milho)
    etanol_anidro_cana = simular_producao_etanol_com_volatilidade(
        etanol_anidro_cana_base, 'anidro_cana', seed=42 + quinzena,
        preco_anidro=preco_anidro, preco_hidratado=preco_hidratado
    )
    etanol_hidratado_cana = simular_producao_etanol_com_volatilidade(
        etanol_hidratado_cana_base, 'hidratado_cana', seed=42 + quinzena + 1000,
        preco_anidro=preco_anidro, preco_hidratado=preco_hidratado
    )
    
    # Calcula etanol de milho considerando produção de cana (correlações)
    etanol_anidro_milho_base, etanol_hidratado_milho_base = calcular_etanol_milho(
        etanol_q, quinzena, int(n_quinz),
        etanol_anidro_cana=etanol_anidro_cana,
        etanol_hidratado_cana=etanol_hidratado_cana
    )
    
    # Aplica simulação com volatilidade para milho (com dependência de cana e preços)
    etanol_anidro_milho = simular_producao_etanol_com_volatilidade(
        etanol_anidro_milho_base, 'anidro_milho', seed=42 + quinzena + 2000,
        preco_anidro=preco_anidro, preco_hidratado=preco_hidratado,
        etanol_anidro_cana=etanol_anidro_cana, etanol_hidratado_cana=etanol_hidratado_cana
    )
    etanol_hidratado_milho = simular_producao_etanol_com_volatilidade(
        etanol_hidratado_milho_base, 'hidratado_milho', seed=42 + quinzena + 3000,
        preco_anidro=preco_anidro, preco_hidratado=preco_hidratado,
        etanol_anidro_cana=etanol_anidro_cana, etanol_hidratado_cana=etanol_hidratado_cana
    )
    
    producao_etanol_anidro_cana.append(etanol_anidro_cana)
    producao_etanol_hidratado_cana.append(etanol_hidratado_cana)
    producao_etanol_anidro_milho.append(etanol_anidro_milho)
    producao_etanol_hidratado_milho.append(etanol_hidratado_milho)

# Adiciona colunas de produção quinzenal ao DataFrame
df_completo["Açúcar (t)"] = producao_acucar_quinzenal
df_completo["Etanol (m³)"] = producao_etanol_quinzenal
df_completo["Etanol Anidro Cana (m³)"] = producao_etanol_anidro_cana
df_completo["Etanol Hidratado Cana (m³)"] = producao_etanol_hidratado_cana
df_completo["Etanol Anidro Milho (m³)"] = producao_etanol_anidro_milho
df_completo["Etanol Hidratado Milho (m³)"] = producao_etanol_hidratado_milho

# Calcula etanol total quinzena (soma de todos os tipos)
df_completo["Etanol Total Quinzena (m³)"] = (
    df_completo["Etanol Anidro Cana (m³)"] +
    df_completo["Etanol Hidratado Cana (m³)"] +
    df_completo["Etanol Anidro Milho (m³)"] +
    df_completo["Etanol Hidratado Milho (m³)"]
)

# Adiciona colunas acumuladas
df_completo["Açúcar Acumulado (t)"] = df_completo["Açúcar (t)"].cumsum()
df_completo["Etanol Acumulado (m³)"] = df_completo["Etanol (m³)"].cumsum()
df_completo["Etanol Total Acumulado (m³)"] = df_completo["Etanol Total Quinzena (m³)"].cumsum()
df_completo["Moagem Acumulada (ton)"] = df_completo["Moagem"].cumsum()

ny11_final = df_precos.iloc[-1]["NY11_cents"]
usd_final = df_precos.iloc[-1]["USD_BRL"]
preco_brl_t_final = ny11_para_brl(ny11_final, usd_final)
preco_saca_final = preco_brl_t_final / 20

variacao_ny11 = ny11_final - ny11_inicial
variacao_pct = (variacao_ny11 / ny11_inicial) * 100

# ============ EXIBIÇÃO ============

st.divider()
st.subheader("📈 Resultados da Simulação")

# Calcula totais de cada tipo de etanol
etanol_anidro_cana_total = df_completo["Etanol Anidro Cana (m³)"].sum()
etanol_hidratado_cana_total = df_completo["Etanol Hidratado Cana (m³)"].sum()
etanol_anidro_milho_total = df_completo["Etanol Anidro Milho (m³)"].sum()
etanol_hidratado_milho_total = df_completo["Etanol Hidratado Milho (m³)"].sum()
etanol_total_quinzena = df_completo["Etanol Total Quinzena (m³)"].sum()

col1, col2, col3, col4 = st.columns(4)

col1.metric("Açúcar estimado", fmt_br(acucar_total, 0) + " t")
col2.metric("Etanol de Cana", fmt_br(etanol_total, 0) + " m³")
col3.metric("Etanol Total (Cana + Milho)", fmt_br(etanol_total_quinzena, 0) + " m³")
col4.metric("Preço final NY11", f"{ny11_final:.2f} USc/lb",
           delta=f"{variacao_ny11:+.2f} ({variacao_pct:+.2f}%)",
           delta_color="inverse" if variacao_ny11 < 0 else "normal")

st.write("")
col5, col6, col7, col8 = st.columns(4)
col5.metric("Preço final (R$/saca)", fmt_br(preco_saca_final, 2))
col6.metric("USD/BRL final", f"{usd_final:.2f}", 
           delta=f"{usd_final - usd_inicial:+.2f}",
           delta_color="inverse" if (usd_final - usd_inicial) < 0 else "normal")
col7.metric("Tendência esperada", direcao.upper(), delta=f"{variacao_pct:+.2f}%",
           delta_color="inverse" if variacao_ny11 < 0 else "normal")
col8.metric("Moagem Total", fmt_br(df_completo["Moagem"].sum(), 0) + " ton")

st.divider()
st.subheader("🍯 Detalhamento de Etanol")

col_et1, col_et2, col_et3, col_et4 = st.columns(4)
col_et1.metric("Etanol Anidro Cana", fmt_br(etanol_anidro_cana_total, 0) + " m³")
col_et2.metric("Etanol Hidratado Cana", fmt_br(etanol_hidratado_cana_total, 0) + " m³")
col_et3.metric("Etanol Anidro Milho", fmt_br(etanol_anidro_milho_total, 0) + " m³")
col_et4.metric("Etanol Hidratado Milho", fmt_br(etanol_hidratado_milho_total, 0) + " m³")

st.write("")
col_et5, col_et6 = st.columns(2)
col_et5.metric("Etanol Total Cana", fmt_br(etanol_total, 0) + " m³")
col_et6.metric("Etanol Total Milho", fmt_br(etanol_anidro_milho_total + etanol_hidratado_milho_total, 0) + " m³")

# Comparação se houver choques de safra
if choques_safra:
    st.divider()
    st.subheader("📊 Comparação: Cenário Base vs Cenário com Choques")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🌾 Cenário Base")
        st.metric("Moagem total", fmt_br(moagem, 0) + " ton")
        st.metric("ATR médio", fmt_br(atr, 2) + " kg/t")
        st.metric("Mix açúcar", fmt_br(mix, 2) + "%")
        st.metric("Açúcar estimado", fmt_br(acucar_total_base, 0) + " t")
        st.metric("Etanol estimado", fmt_br(etanol_total_base, 0) + " m³")
    
    with col2:
        st.markdown("### ⚡ Cenário com Choques")
        moagem_final = moagem
        atr_final = atr
        mix_final = mix
        
        for q, choque_data in sorted(st.session_state.choques_safra.items()):
            # Suporta tanto formato antigo (dict único) quanto novo (lista de dicts)
            choques_quinzena = choque_data if isinstance(choque_data, list) else [choque_data]
            
            for choque in choques_quinzena:
                tipo = choque['tipo']
                magnitude = choque['magnitude']
                if tipo == 'Moagem':
                    moagem_final = moagem_final * (1 + magnitude / 100)
                elif tipo == 'ATR':
                    atr_final = atr_final * (1 + magnitude / 100)
                elif tipo == 'MIX':
                    mix_final = mix_final * (1 + magnitude / 100)
        
        st.metric("Moagem total", fmt_br(moagem_final, 0) + " ton",
                 delta=f"{((moagem_final - moagem) / moagem * 100):+.2f}%")
        st.metric("ATR médio", fmt_br(atr_final, 2) + " kg/t",
                 delta=f"{((atr_final - atr) / atr * 100):+.2f}%")
        st.metric("Mix açúcar", fmt_br(mix_final, 2) + "%",
                 delta=f"{((mix_final - mix) / mix * 100):+.2f}%")
        st.metric("Açúcar estimado", fmt_br(acucar_total_com_choques, 0) + " t",
                 delta=f"{((acucar_total_com_choques - acucar_total_base) / acucar_total_base * 100):+.2f}%")
        st.metric("Etanol estimado", fmt_br(etanol_total_com_choques, 0) + " m³",
                 delta=f"{((etanol_total_com_choques - etanol_total_base) / etanol_total_base * 100):+.2f}%")
    
    with col3:
        st.markdown("### 📈 Impacto")
        dif_acucar = acucar_total_com_choques - acucar_total_base
        dif_etanol = etanol_total_com_choques - etanol_total_base
        pct_acucar = ((acucar_total_com_choques - acucar_total_base) / acucar_total_base * 100) if acucar_total_base > 0 else 0
        pct_etanol = ((etanol_total_com_choques - etanol_total_base) / etanol_total_base * 100) if etanol_total_base > 0 else 0
        
        st.metric("Diferença açúcar", fmt_br(dif_acucar, 0) + " t", 
                 delta=f"{pct_acucar:+.2f}%",
                 delta_color="inverse" if dif_acucar < 0 else "normal")
        st.metric("Diferença etanol", fmt_br(dif_etanol, 0) + " m³",
                 delta=f"{pct_etanol:+.2f}%",
                 delta_color="inverse" if dif_etanol < 0 else "normal")

st.divider()
st.subheader("📅 Evolução Quinzenal")

# Formata DataFrame para exibição
colunas_formatacao = {
    "Moagem": (0, fmt_br),
    "Moagem Acumulada (ton)": (0, fmt_br),
    "ATR": (2, fmt_br),
    "MIX": (2, fmt_br),
    "NY11_cents": (2, lambda x: f"{x:.2f}"),
    "Etanol_R$m3": (0, fmt_br),
    "USD_BRL": (2, lambda x: f"{x:.2f}"),
    "Açúcar (t)": (0, fmt_br),
    "Açúcar Acumulado (t)": (0, fmt_br),
    "Etanol (m³)": (0, fmt_br),
    "Etanol Acumulado (m³)": (0, fmt_br),
    "Etanol Anidro Cana (m³)": (0, fmt_br),
    "Etanol Hidratado Cana (m³)": (0, fmt_br),
    "Etanol Anidro Milho (m³)": (0, fmt_br),
    "Etanol Hidratado Milho (m³)": (0, fmt_br),
    "Etanol Total Quinzena (m³)": (0, fmt_br),
    "Etanol Total Acumulado (m³)": (0, fmt_br)
}

df_mostrar = df_completo.copy()
for coluna, (casas, func) in colunas_formatacao.items():
    if coluna in df_mostrar.columns:
        df_mostrar[coluna] = df_mostrar[coluna].apply(func)

# Seleciona colunas para exibição organizadas
colunas_exibir = [
    "Quinzena", "Data",
    "Moagem", "Moagem Acumulada (ton)",
    "ATR", "MIX",
    "Açúcar (t)", "Açúcar Acumulado (t)",
    "Etanol (m³)", "Etanol Acumulado (m³)",
    "Etanol Anidro Cana (m³)", "Etanol Hidratado Cana (m³)",
    "Etanol Anidro Milho (m³)", "Etanol Hidratado Milho (m³)",
    "Etanol Total Quinzena (m³)", "Etanol Total Acumulado (m³)",
    "NY11_cents", "Etanol_R$m3", "USD_BRL"
]

# Filtra apenas colunas que existem no DataFrame
colunas_exibir = [col for col in colunas_exibir if col in df_mostrar.columns]

st.dataframe(df_mostrar[colunas_exibir],
             use_container_width=True, height=400, hide_index=True)

# Análise final
st.divider()
st.subheader("💡 Análise de Impacto")

producao_atual = acucar_total

choques_info = ""
if choques_aplicados:
    choques_info = f"\n\n**⚡ Choques de preços:**\n" + "\n".join(f"- {c}" for c in choques_aplicados)

# Calcula produção normalizada para análise de estoques
producao_total_calc = df_completo["Açúcar (t)"].sum()
producao_media_calc = producao_total_calc / int(n_quinz) if int(n_quinz) > 0 else 0
producao_normalizada_calc = producao_media_calc / 1_500_000 if producao_media_calc > 0 else 1.0

estoques_info = ""
if estoques_globais != "Neutro":
    estoques_info = f"\n\n**📦 Estoques Globais:** {estoques_globais} ({st.session_state.analise_nivel_estoques:.1f}%)\n"
    if estoques_globais == "Déficit":
        estoques_info += f"→ Déficit de estoques suporta preços (tendência de alta)\n"
        if producao_normalizada_calc > 1.0:
            estoques_info += f"→ Déficit + alta produção = forte suporte aos preços\n"
    elif estoques_globais == "Superávit":
        estoques_info += f"→ Superávit de estoques pressiona preços (tendência de queda)\n"
        if producao_normalizada_calc > 1.0:
            estoques_info += f"→ Superávit + grande produção = forte pressão nos preços\n"
            estoques_info += f"→ Pode ocasionar variação no mix (redução de açúcar, aumento de etanol)\n"

choques_safra_info = ""
if choques_safra:
    choques_safra_info = f"\n\n**🌾 Choques de safra:**\n"
    for q, choque_data in sorted(st.session_state.choques_safra.items()):
        # Suporta tanto formato antigo (dict único) quanto novo (lista de dicts)
        if isinstance(choque_data, list):
            for choque in choque_data:
                choques_safra_info += f"- Q{q}: {choque['tipo']} {choque['magnitude']:+.1f}%\n"
        else:
            choques_safra_info += f"- Q{q}: {choque_data['tipo']} {choque_data['magnitude']:+.1f}%\n"

paridade_info = ""
if usar_paridade:
    etanol_final = df_precos.iloc[-1]["Etanol_R$m3"]
    
    # Calcula paridade comparando ambos em cents/lb FOB
    # Nota: Usa TAXA_POL fixa (4,5%) e DESCONTO_VHP_FOB (0,10) de Dados_base.py
    paridade_final = calcular_paridade_etanol_acucar(etanol_final, ny11_final, usd_final)
    
    # Converte ambos para FOB cents/lb para exibição
    etanol_fob_cents_lb = converter_etanol_para_fob_cents_lb(etanol_final, usd_final)
    acucar_fob_cents_lb = converter_acucar_vhp_para_fob(ny11_final)
    
    # Calcula mix médio ajustado
    mix_medio_ajustado = np.mean(mix_ajustado) if mix_ajustado else mix
    mix_medio_original = mix
    
    paridade_info = f"\n\n**🔄 Paridade Etanol/Açúcar (final):** {paridade_final:.3f}\n"
    paridade_info += f"**Etanol FOB:** {etanol_fob_cents_lb:.2f} cents/lb | **Açúcar FOB:** {acucar_fob_cents_lb:.2f} cents/lb (NY11: {ny11_final:.2f} cents/lb)\n"
    paridade_info += f"**Mix médio:** {mix_medio_original:.1f}% → {mix_medio_ajustado:.1f}% (ajustado por paridade)\n"
    
    # Calcula a diferença real do mix
    diferenca_mix = mix_medio_ajustado - mix_medio_original
    
    # Determina a mensagem baseada na mudança real do mix e na paridade
    if abs(diferenca_mix) < 0.1:  # Praticamente sem mudança
        paridade_info += "Paridade equilibrada → mix mantido próximo ao original"
    elif diferenca_mix > 0:  # Mix aumentou
        if paridade_final < 1.0:
            paridade_info += f"✅ Açúcar mais atrativo → mix aumentado em {diferenca_mix:.1f} p.p. → mais açúcar produzido → preço do açúcar tende a ser pressionado"
        else:
            paridade_info += f"⚠️ Mix aumentado em {diferenca_mix:.1f} p.p. apesar da paridade favorável ao etanol → mais açúcar produzido → preço do açúcar tende a ser pressionado"
    else:  # Mix diminuiu
        if paridade_final > 1.0:
            paridade_info += f"✅ Etanol mais atrativo → mix reduzido em {abs(diferenca_mix):.1f} p.p. → menos açúcar produzido → preço do açúcar tende a melhorar"
        else:
            paridade_info += f"⚠️ Mix reduzido em {abs(diferenca_mix):.1f} p.p. apesar da paridade favorável ao açúcar → menos açúcar produzido → preço do açúcar tende a melhorar"

# Determina se produção é alta ou baixa (baseado em threshold simples)
producao_alta = producao_atual > 35_000_000  # Threshold: 35M ton

st.info(
    f"""
    **Cenário simulado:**
    - **Produção estimada:** {fmt_br(producao_atual, 0)} t de açúcar
    - **Fator de oferta aplicado:** {fator_oferta:.4f}
    
    **Evolução do preço:**
    - **Inicial:** {ny11_inicial:.2f} USc/lb → **Final:** {ny11_final:.2f} USc/lb
    - **Variação:** {variacao_ny11:+.2f} USc/lb ({variacao_pct:+.2f}%)
    - **Tendência:** {direcao.upper()}
    {choques_info}{choques_safra_info}{estoques_info}{paridade_info}
    
    {'🔴 **Alta produção:** Maior oferta tende a pressionar preços' if producao_alta else '🟢 **Baixa produção:** Menor oferta tende a suportar preços'}
    
    💡 *Altere os parâmetros no sidebar para testar diferentes cenários. Use "Choques de Safra" para simular eventos que afetam produção e "Choques de Preços" para eventos que afetam preços.*
    """
)
