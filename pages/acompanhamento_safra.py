"""
================================================================================
ACOMPANHAMENTO DE SAFRA - SIMULAÇÃO COM DADOS REAIS
================================================================================
Este módulo permite acompanhar a safra inserindo dados reais acumulados da Unica
e ajustando projeções baseadas no perfil histórico da safra.

Funcionalidades:
- Inserção de dados reais acumulados por quinzena
- Projeção automática baseada em perfis históricos
- Simulação de choques apenas em quinzenas futuras
- Cálculo automático de etanol (hidratado/anidro de cana e milho)
- Ajuste automático de projeções conforme dados reais são inseridos

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
    if valor is None or pd.isna(valor):
        return ""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ============================================================================
# CONFIGURAÇÃO STREAMLIT
# ============================================================================

st.set_page_config(page_title="Acompanhamento de Safra", layout="wide")


# ============================================================================
# CONSTANTES DE PRODUÇÃO
# ============================================================================

FATOR_ACUCAR = 0.95275
FATOR_ETANOL = 0.595
PERCENTUAL_ETANOL_MILHO = 0.30  # 30% do total de etanol é de milho

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


def calcular_etanol_milho(etanol_total, quinzena, n_quinzenas_total):
    """
    Calcula produção de etanol de milho (30% do total) e distribui entre anidro e hidratado.
    Usa as mesmas proporções do etanol de cana.
    """
    etanol_total_milho = etanol_total * PERCENTUAL_ETANOL_MILHO
    etanol_anidro_milho, etanol_hidratado_milho = calcular_etanol_detalhado(
        etanol_total_milho, quinzena, n_quinzenas_total
    )
    return etanol_anidro_milho, etanol_hidratado_milho


# ============================================================================
# FUNÇÕES DE CONVERSÃO DE PREÇOS
# ============================================================================

def converter_etanol_para_fob_cents_lb(preco_etanol_pvu_m3, cambio_usd_brl):
    """Converte preço do etanol PVU (R$/m³) para equivalente FOB em cents/lb"""
    if cambio_usd_brl <= 0 or preco_etanol_pvu_m3 <= 0:
        return 0.0

    preco_sem_icms = preco_etanol_pvu_m3 * (1 - ICMS_ETANOL)
    preco_liquido_pvu = preco_sem_icms - PIS_COFINS_ETANOL

    if preco_liquido_pvu <= 0:
        return 0.0

    FATOR_CONVERSAO_ETANOL_VHP = 31.504
    SACAS_POR_TONELADA = 20
    CENTS_LB_POR_TON = 22.0462
    FATOR_AJUSTE_QUALIDADE = 1.042

    equivalente_vhp_r_por_saco = (preco_liquido_pvu / FATOR_CONVERSAO_ETANOL_VHP) * SACAS_POR_TONELADA
    numerador = equivalente_vhp_r_por_saco + FRETE_R_T + (TERMINAL_USD_T * cambio_usd_brl)
    preco_fob_cents_lb = (numerador / CENTS_LB_POR_TON / cambio_usd_brl) / FATOR_AJUSTE_QUALIDADE

    return preco_fob_cents_lb


def converter_acucar_vhp_para_fob(preco_ny11_cents_lb):
    """Converte preço do açúcar VHP (NY11) para FOB em cents/lb"""
    if preco_ny11_cents_lb <= 0:
        return 0.0
    preco_fob = (preco_ny11_cents_lb - DESCONTO_VHP_FOB) * (1 + TAXA_POL)
    return max(0.0, preco_fob)


def calcular_paridade_etanol_acucar(preco_etanol_pvu_m3, preco_ny11_cents_lb, cambio_usd_brl):
    """Calcula paridade etanol/açúcar comparando equivalentes FOB em cents/lb"""
    if preco_ny11_cents_lb <= 0:
        return 1.0

    preco_etanol_fob_cents_lb = converter_etanol_para_fob_cents_lb(preco_etanol_pvu_m3, cambio_usd_brl)
    if preco_etanol_fob_cents_lb <= 0:
        return 1.0

    preco_acucar_fob_cents_lb = converter_acucar_vhp_para_fob(preco_ny11_cents_lb)
    if preco_acucar_fob_cents_lb <= 0:
        return 1.0

    paridade = preco_etanol_fob_cents_lb / preco_acucar_fob_cents_lb
    return paridade


def ny11_para_brl(cents_lb: float, usdbrl: float) -> float:
    """Converte NY11 (USc/lb) e USD/BRL em R$/t"""
    LB_POR_TON = 2204.62
    usd_per_ton = (cents_lb / 100.0) * LB_POR_TON
    return usd_per_ton * usdbrl


# ============================================================================
# FUNÇÕES DE SIMULAÇÃO E AJUSTE
# ============================================================================

def gerar_projecao_quinzenal(moagem_total, atr_medio, mix_medio, n_quinzenas=24,
                              data_inicio=None, dados_reais=None, choques_safra=None, seed=42):
    """
    Gera projeção quinzenal ajustada com dados reais.

    Se houver dados reais, ajusta a projeção baseada no perfil histórico.
    """
    if data_inicio is None:
        data_inicio = date(date.today().year, 4, 1)

    rng = np.random.default_rng(seed)

    # Curva de distribuição (formato sino - mais moagem no meio da safra)
    x = np.linspace(-2, 2, n_quinzenas)
    pesos = np.exp(-x ** 2 / 0.8)
    pct_moagem = pesos / pesos.sum()

    datas = pd.date_range(start=data_inicio, periods=n_quinzenas, freq="15D")

    # Calcula moagem distribuída
    moagem_distribuida = [moagem_total * pct_moagem[i] for i in range(n_quinzenas)]
    soma_moagem = sum(moagem_distribuida)

    # Usa perfis históricos
    n_perfil = len(PERFIL_ATR)
    perfil_atr_ajustado = [PERFIL_ATR[i % n_perfil] for i in range(n_quinzenas)]
    perfil_mix_ajustado = [PERFIL_MIX[i % n_perfil] for i in range(n_quinzenas)]

    # Calcula SOMARPRODUTO para ATR e Mix
    somarproduto_atr = sum(moagem_distribuida[i] * perfil_atr_ajustado[i] for i in range(n_quinzenas))
    somarproduto_mix = sum(moagem_distribuida[i] * perfil_mix_ajustado[i] for i in range(n_quinzenas))

    # Calcula fatores de correção
    fator_atr = (atr_medio * soma_moagem) / somarproduto_atr if somarproduto_atr > 0 else 1.0
    fator_mix = (mix_medio * moagem_total) / somarproduto_mix if somarproduto_mix > 0 else 1.0

    # Identifica última quinzena com dados reais
    ultima_quinzena_real = 0
    if dados_reais:
        for q in sorted(dados_reais.keys(), reverse=True):
            if dados_reais[q].get('moagem_real') is not None:
                ultima_quinzena_real = q
                break

    # Ajusta fatores se houver dados reais
    # Nota: dados_reais contém valores ACUMULADOS
    if ultima_quinzena_real > 0:
        # Pega o valor acumulado real da última quinzena
        moagem_real_acum = dados_reais[ultima_quinzena_real].get('moagem_real', 0)
        # Calcula projeção acumulada até a última quinzena
        moagem_proj_acum = sum(moagem_distribuida[i] for i in range(ultima_quinzena_real))

        if moagem_proj_acum > 0 and moagem_real_acum > 0:
            fator_ajuste = moagem_real_acum / moagem_proj_acum
            # Ajusta projeção futura baseada no desvio observado
            for i in range(ultima_quinzena_real, n_quinzenas):
                moagem_distribuida[i] = moagem_distribuida[i] * fator_ajuste

    linhas = []
    for i in range(n_quinzenas):
        quinzena = i + 1

        # Verifica se há dados reais para esta quinzena
        tem_dados_reais = dados_reais and quinzena in dados_reais and dados_reais[quinzena].get('moagem_real') is not None

        if tem_dados_reais:
            # Dados reais são ACUMULADOS, então calcula a diferença
            moagem_acum_atual = dados_reais[quinzena].get('moagem_real', 0)
            if quinzena == 1:
                # Primeira quinzena: usa o valor acumulado diretamente
                moagem_q = moagem_acum_atual
            else:
                # Quinzenas seguintes: diferença entre acumulado atual e anterior
                moagem_acum_anterior = dados_reais[quinzena - 1].get('moagem_real', 0) if (quinzena - 1) in dados_reais else 0
                moagem_q = moagem_acum_atual - moagem_acum_anterior

            # ATR e Mix são médios, usa o valor real se disponível
            atr_q = dados_reais[quinzena].get('atr_real', perfil_atr_ajustado[i] * fator_atr)
            mix_q = dados_reais[quinzena].get('mix_real', perfil_mix_ajustado[i] * fator_mix)
        else:
            # Usa projeção
            moagem_q = moagem_distribuida[i]
            atr_q = perfil_atr_ajustado[i] * fator_atr
            mix_q = perfil_mix_ajustado[i] * fator_mix

        # Aplica choques de safra apenas em quinzenas futuras (sem dados reais)
        if not tem_dados_reais and choques_safra and quinzena in choques_safra:
            choques_quinzena = choques_safra[quinzena]
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

        # Calcula produção
        acucar_q, etanol_q = calcular_producao_quinzenal(moagem_q, atr_q, mix_q)

        # Calcula etanol detalhado
        etanol_anidro_cana, etanol_hidratado_cana = calcular_etanol_detalhado(
            etanol_q, quinzena, n_quinzenas
        )
        etanol_anidro_milho, etanol_hidratado_milho = calcular_etanol_milho(
            etanol_q, quinzena, n_quinzenas
        )

        # Verifica se há dados reais de etanol
        if tem_dados_reais:
            etanol_anidro_cana = dados_reais[quinzena].get('etanol_anidro_cana_real', etanol_anidro_cana)
            etanol_hidratado_cana = dados_reais[quinzena].get('etanol_hidratado_cana_real', etanol_hidratado_cana)
            etanol_anidro_milho = dados_reais[quinzena].get('etanol_anidro_milho_real', etanol_anidro_milho)
            etanol_hidratado_milho = dados_reais[quinzena].get('etanol_hidratado_milho_real', etanol_hidratado_milho)

        # Etanol total da quinzena (cana + milho)
        etanol_total_quinzena = etanol_anidro_cana + etanol_hidratado_cana + etanol_anidro_milho + etanol_hidratado_milho

        linhas.append({
            "Quinzena": quinzena,
            "Mês": datas[i].month,
            "Data": datas[i].date(),
            "Moagem": moagem_q,
            "ATR": atr_q,
            "MIX": mix_q,
            "Açúcar (t)": acucar_q,
            "Etanol Total (m³)": etanol_q,
            "Etanol Anidro Cana (m³)": etanol_anidro_cana,
            "Etanol Hidratado Cana (m³)": etanol_hidratado_cana,
            "Etanol Anidro Milho (m³)": etanol_anidro_milho,
            "Etanol Hidratado Milho (m³)": etanol_hidratado_milho,
            "Etanol Total Quinzena (m³)": etanol_total_quinzena,
            "Tem Dados Reais": tem_dados_reais
        })

    df = pd.DataFrame(linhas)

    # Calcula acumulado progressivo
    df["Etanol Total Acumulado (m³)"] = df["Etanol Total Quinzena (m³)"].cumsum()

    return df


# ============================================================================
# FUNÇÕES DE SIMULAÇÃO DE PREÇOS
# ============================================================================

def simular_precos(ny11_inicial, usd_inicial, etanol_inicial, n_quinzenas,
                   df_producao, preco_ref=15.0, sensibilidade=0.10,
                   choques_precos=None, usar_paridade=False, dados_reais=None, seed=123):
    """
    Simula preços considerando:
    - Volatilidade e correlação entre commodities
    - Impacto da oferta (produção informada) nos preços
    - Choques externos (opcional)
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

    # Classifica preço inicial (alto/baixo)
    desvio_preco = (ny11_inicial - preco_ref) / preco_ref if preco_ref > 0 else 0

    # Calcula fator de oferta
    producao_normalizada = producao_media / 1_500_000
    fator_oferta_base = 1.0 - ((producao_normalizada - 1.0) * sensibilidade)

    # Ajusta baseado na interação preço inicial vs produção
    if desvio_preco < -0.05:  # Preço baixo
        if producao_normalizada > 1.0:
            fator_oferta = fator_oferta_base * 0.9
            direcao = "queda"
        else:
            fator_oferta = fator_oferta_base * 1.1
            direcao = "alta"
    elif desvio_preco > 0.05:  # Preço alto
        if producao_normalizada > 1.0:
            fator_oferta = fator_oferta_base * 1.05
            direcao = "alta"
        else:
            fator_oferta = fator_oferta_base * 1.15
            direcao = "alta"
    else:  # Preço neutro
        fator_oferta = fator_oferta_base
        direcao = "alta" if fator_oferta > 1.0 else "queda" if fator_oferta < 1.0 else "neutro"

    fator_oferta = np.clip(fator_oferta, 0.7, 1.3)

    # Simula trajetória
    ny11 = [ny11_inicial]
    etanol = [etanol_inicial]
    usd = [usd_inicial]

    choques_aplicados = []

    for i in range(n_quinzenas):
        quinzena = i + 1
        r_sugar, r_eth, r_usd = rets[i]

        # Verifica se há dados reais de preços para esta quinzena
        tem_precos_reais = dados_reais and quinzena in dados_reais

        if tem_precos_reais:
            # Usa valores reais se disponíveis
            if dados_reais[quinzena].get('ny11_real'):
                ny11.append(dados_reais[quinzena]['ny11_real'])
            else:
                # Simula se não houver valor real
                r_sugar_ajustado = r_sugar * fator_oferta
                drift = (fator_oferta - 1.0) * 0.12
                ny11.append(ny11[-1] * (1 + r_sugar_ajustado + drift))

            if dados_reais[quinzena].get('usd_real'):
                usd.append(dados_reais[quinzena]['usd_real'])
            else:
                usd.append(usd[-1] * (1 + r_usd))

            # Para etanol, usa média ponderada se houver preços reais
            if dados_reais[quinzena].get('etanol_anidro_preco_real') and dados_reais[quinzena].get('etanol_hidratado_preco_real'):
                # Média ponderada (aproximação: 50% anidro, 50% hidratado)
                etanol_medio = (dados_reais[quinzena]['etanol_anidro_preco_real'] +
                               dados_reais[quinzena]['etanol_hidratado_preco_real']) / 2
                etanol.append(etanol_medio)
            else:
                etanol.append(etanol[-1] * (1 + r_eth))
        else:
            # Verifica choques de preços apenas se não houver dados reais
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

            # Aplica impacto da oferta no açúcar
            r_sugar_ajustado = r_sugar * fator_oferta
            drift = (fator_oferta - 1.0) * 0.12

            ny11.append(ny11[-1] * (1 + r_sugar_ajustado + drift))
            etanol.append(etanol[-1] * (1 + r_eth))
            usd.append(usd[-1] * (1 + r_usd))

    df_precos = pd.DataFrame({
        "Quinzena": np.arange(1, n_quinzenas + 1),
        "NY11_cents": ny11[1:],
        "Etanol_R$m3": etanol[1:],
        "USD_BRL": usd[1:],
    })

    # Adiciona colunas de preços reais de etanol se disponíveis
    if dados_reais:
        etanol_anidro_preco = []
        etanol_hidratado_preco = []
        for quinzena in range(1, n_quinzenas + 1):
            if quinzena in dados_reais:
                etanol_anidro_preco.append(dados_reais[quinzena].get('etanol_anidro_preco_real', None))
                etanol_hidratado_preco.append(dados_reais[quinzena].get('etanol_hidratado_preco_real', None))
            else:
                etanol_anidro_preco.append(None)
                etanol_hidratado_preco.append(None)

        df_precos["Etanol Anidro Preço (R$/m³)"] = etanol_anidro_preco
        df_precos["Etanol Hidratado Preço (R$/m³)"] = etanol_hidratado_preco

    return df_precos, direcao, fator_oferta, choques_aplicados


# ============================================================================
# INTERFACE
# ============================================================================

st.markdown("<h1 style='text-align: center; margin-bottom: 5px;'>Acompanhamento de Safra 📊</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="text-align: center; color: #666; font-size: 0.9em; margin-top: 0px; margin-bottom: 20px;">Desenvolvido por Rogério Guilherme Jr.</p>',
    unsafe_allow_html=True
)

# ============ SIDEBAR ============
st.sidebar.header("📊 Parâmetros da Safra")

moagem = st.sidebar.number_input("Moagem total estimada (ton)", value=600_000_000, step=10_000_000)
atr = st.sidebar.number_input("ATR médio estimado (kg/t)", value=135.0, step=1.0, format="%.1f")
mix = st.sidebar.number_input("Mix açúcar estimado (%)", value=48.0, step=1.0, format="%.1f")

st.sidebar.divider()

st.sidebar.subheader("⚙️ Simulação")
n_quinz = st.sidebar.number_input("Nº de quinzenas", value=24, min_value=4, max_value=24, step=1)
data_start = st.sidebar.date_input("Início da safra", value=date(date.today().year, 4, 1))

st.sidebar.divider()

st.sidebar.subheader("💰 Preços Iniciais")
ny11_inicial = st.sidebar.number_input("NY11 inicial (USc/lb)", value=14.90, step=0.10, format="%.2f")
usd_inicial = st.sidebar.number_input("USD/BRL inicial", value=4.90, step=0.01, format="%.2f")
etanol_inicial = st.sidebar.number_input("Etanol inicial (R$/m³)", value=2500.0, step=50.0, format="%.0f")

with st.sidebar.expander("🔧 Parâmetros Avançados", expanded=False):
    st.caption("⚙️ Ajustes finos da simulação (opcional)")
    preco_ref = st.number_input("Preço referência NY11 (USc/lb)", value=15.0, step=0.5, format="%.1f")
    sensibilidade = st.slider("Sensibilidade oferta → preço (%)", 0.0, 30.0, 10.0, 1.0)

# Inicializa dados reais no session_state
if 'dados_reais' not in st.session_state:
    st.session_state.dados_reais = {}

# Inicializa choques de safra
if 'choques_safra' not in st.session_state:
    st.session_state.choques_safra = {}

# Inicializa choques de preços
if 'choques_precos' not in st.session_state:
    st.session_state.choques_precos = {}

# ============ INSERÇÃO DE DADOS REAIS ============
st.divider()
st.subheader("📥 Inserção de Dados Reais (Unica)")

st.caption("💡 Insira os dados acumulados conforme recebe da Unica. A projeção será ajustada automaticamente.")

col1, col2, col3 = st.columns(3)
with col1:
    quinzena_inserir = st.number_input("Quinzena", min_value=1, max_value=int(n_quinz), value=1, step=1)
with col2:
    moagem_real = st.number_input("Moagem acumulada (ton)", value=0, step=1000, format="%d")
with col3:
    atr_real = st.number_input("ATR (kg/t)", value=0.0, step=0.1, format="%.1f")

col4, col5 = st.columns(2)
with col4:
    mix_real = st.number_input("Mix açúcar (%)", value=0.0, step=0.1, format="%.1f")
with col5:
    usar_etanol_manual = st.checkbox("Inserir etanol manualmente", value=False)

st.markdown("**💲 Preços no Fim da Quinzena:**")
col_preco1, col_preco2, col_preco3, col_preco4 = st.columns(4)
with col_preco1:
    usd_real = st.number_input("USD/BRL", value=0.0, step=0.01, format="%.2f", key="usd_real_input")
with col_preco2:
    ny11_real = st.number_input("NY11 (USc/lb)", value=0.0, step=0.10, format="%.2f", key="ny11_real_input")
with col_preco3:
    etanol_anidro_preco_real = st.number_input("Etanol Anidro (R$/m³)", value=0.0, step=10.0, format="%.0f", key="etanol_anidro_preco")
with col_preco4:
    etanol_hidratado_preco_real = st.number_input("Etanol Hidratado (R$/m³)", value=0.0, step=10.0, format="%.0f", key="etanol_hidratado_preco")

etanol_anidro_cana_real = None
etanol_hidratado_cana_real = None
etanol_anidro_milho_real = None
etanol_hidratado_milho_real = None

if usar_etanol_manual:
    st.markdown("**Dados de Etanol (m³):**")
    col6, col7, col8, col9 = st.columns(4)
    with col6:
        etanol_anidro_cana_real = st.number_input("Anidro Cana", value=0.0, step=100.0, format="%.0f")
    with col7:
        etanol_hidratado_cana_real = st.number_input("Hidratado Cana", value=0.0, step=100.0, format="%.0f")
    with col8:
        etanol_anidro_milho_real = st.number_input("Anidro Milho", value=0.0, step=100.0, format="%.0f")
    with col9:
        etanol_hidratado_milho_real = st.number_input("Hidratado Milho", value=0.0, step=100.0, format="%.0f")

col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("➕ Adicionar/Atualizar Dados", use_container_width=True, type="primary"):
        if quinzena_inserir > 0:
            st.session_state.dados_reais[quinzena_inserir] = {
                'moagem_real': moagem_real if moagem_real > 0 else None,
                'atr_real': atr_real if atr_real > 0 else None,
                'mix_real': mix_real if mix_real > 0 else None,
                'etanol_anidro_cana_real': etanol_anidro_cana_real if usar_etanol_manual and etanol_anidro_cana_real > 0 else None,
                'etanol_hidratado_cana_real': etanol_hidratado_cana_real if usar_etanol_manual and etanol_hidratado_cana_real > 0 else None,
                'etanol_anidro_milho_real': etanol_anidro_milho_real if usar_etanol_manual and etanol_anidro_milho_real > 0 else None,
                'etanol_hidratado_milho_real': etanol_hidratado_milho_real if usar_etanol_manual and etanol_hidratado_milho_real > 0 else None,
                'usd_real': usd_real if usd_real > 0 else None,
                'ny11_real': ny11_real if ny11_real > 0 else None,
                'etanol_anidro_preco_real': etanol_anidro_preco_real if etanol_anidro_preco_real > 0 else None,
                'etanol_hidratado_preco_real': etanol_hidratado_preco_real if etanol_hidratado_preco_real > 0 else None,
            }
            st.success(f"✅ Dados da Q{quinzena_inserir} adicionados/atualizados!")
            st.rerun()

with col_btn2:
    if st.button("🗑️ Limpar Todos os Dados Reais", use_container_width=True):
        st.session_state.dados_reais = {}
        st.rerun()

# Lista dados reais inseridos
if st.session_state.dados_reais:
    st.markdown("**📋 Dados reais inseridos:**")
    for q in sorted(st.session_state.dados_reais.keys()):
        dados = st.session_state.dados_reais[q]
        info = f"Q{q}: "
        if dados.get('moagem_real'):
            info += f"Moagem: {fmt_br(dados['moagem_real'], 0)} ton"
        if dados.get('atr_real'):
            info += f" | ATR: {dados['atr_real']:.1f} kg/t"
        if dados.get('mix_real'):
            info += f" | Mix: {dados['mix_real']:.1f}%"
        if dados.get('ny11_real'):
            info += f" | NY11: {dados['ny11_real']:.2f} USc/lb"
        if dados.get('usd_real'):
            info += f" | USD: {dados['usd_real']:.2f}"
        st.caption(info)

# ============ CHOQUES DE SAFRA ============
st.sidebar.divider()
with st.sidebar.expander("🌾 Choques de Safra (Apenas Futuras)", expanded=False):
    st.caption("⚠️ Choques só podem ser aplicados em quinzenas sem dados reais")

    col_periodo1, col_periodo2 = st.columns(2)
    with col_periodo1:
        quinzena_inicio = st.number_input("Quinzena início", min_value=1, max_value=int(n_quinz),
                                         value=12, step=1, key="choque_inicio")
    with col_periodo2:
        quinzena_fim = st.number_input("Quinzena fim", min_value=1, max_value=int(n_quinz),
                                       value=12, step=1, key="choque_fim")

    periodo_valido = quinzena_fim >= quinzena_inicio

    # Verifica se há dados reais no período
    tem_dados_no_periodo = False
    if periodo_valido:
        for q in range(quinzena_inicio, quinzena_fim + 1):
            if q in st.session_state.dados_reais and st.session_state.dados_reais[q].get('moagem_real'):
                tem_dados_no_periodo = True
                break

    if tem_dados_no_periodo:
        st.warning("⚠️ Não é possível aplicar choques em quinzenas com dados reais!")

    tipo_choque = st.selectbox("Tipo de choque", ["Moagem", "ATR", "MIX"], key="tipo_choque")
    magnitude_choque = st.number_input("Magnitude (%)", min_value=-50.0, max_value=50.0,
                                      value=0.0, step=1.0, format="%.1f", key="magnitude_choque")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Aplicar", use_container_width=True,
                    disabled=not periodo_valido or tem_dados_no_periodo or magnitude_choque == 0,
                    key="btn_aplicar_choque"):
            novo_choque = {
                'tipo': tipo_choque,
                'magnitude': magnitude_choque
            }
            for q in range(quinzena_inicio, quinzena_fim + 1):
                # Só aplica se não houver dados reais
                if q not in st.session_state.dados_reais or not st.session_state.dados_reais[q].get('moagem_real'):
                    if q not in st.session_state.choques_safra:
                        st.session_state.choques_safra[q] = []
                    elif not isinstance(st.session_state.choques_safra[q], list):
                        st.session_state.choques_safra[q] = [st.session_state.choques_safra[q]]
                    st.session_state.choques_safra[q].append(novo_choque.copy())
            st.rerun()

    with col_btn2:
        if st.button("🗑️ Remover Todos", use_container_width=True, key="btn_remover_choques"):
            st.session_state.choques_safra = {}
            st.rerun()

# ============ CHOQUES DE PREÇOS ============
st.sidebar.divider()
with st.sidebar.expander("⚡ Choques de Preços", expanded=False):
    st.caption("Simule eventos que afetam PREÇOS (NY11, USD)")

    col_periodo1, col_periodo2 = st.columns(2)
    with col_periodo1:
        quinzena_inicio_preco = st.number_input("Quinzena início", min_value=1, max_value=int(n_quinz),
                                              value=12, step=1, key="choque_preco_inicio")
    with col_periodo2:
        quinzena_fim_preco = st.number_input("Quinzena fim", min_value=1, max_value=int(n_quinz),
                                            value=12, step=1, key="choque_preco_fim")

    periodo_valido_preco = quinzena_fim_preco >= quinzena_inicio_preco
    if not periodo_valido_preco:
        st.warning("⚠️ Quinzena fim deve ser >= quinzena início")

    tipo_choque_preco = st.selectbox("Tipo de choque", ["NY11", "USD"], key="tipo_choque_preco")
    magnitude_choque_preco = st.number_input("Magnitude (%)", min_value=-50.0, max_value=50.0,
                                             value=0.0, step=1.0, format="%.1f", key="magnitude_choque_preco")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Aplicar", use_container_width=True,
                    disabled=not periodo_valido_preco or magnitude_choque_preco == 0,
                    key="btn_aplicar_choque_preco"):
            for q in range(quinzena_inicio_preco, quinzena_fim_preco + 1):
                st.session_state.choques_precos[q] = {
                    'tipo': tipo_choque_preco,
                    'magnitude': magnitude_choque_preco
                }
            st.rerun()

    with col_btn2:
        if st.button("🗑️ Remover Todos", use_container_width=True, key="btn_remover_choques_precos"):
            st.session_state.choques_precos = {}
            st.rerun()

    # Lista choques ativos
    if st.session_state.choques_precos:
        st.write("**Choques ativos:**")
        for q in sorted(st.session_state.choques_precos.keys()):
            choque = st.session_state.choques_precos[q]
            mag = choque['magnitude']
            if mag > 0:
                st.success(f"Q{q}: {choque['tipo']} **+{mag:.1f}%**")
            elif mag < 0:
                st.error(f"Q{q}: {choque['tipo']} **{mag:.1f}%**")
            else:
                st.write(f"Q{q}: {choque['tipo']} {mag:.1f}%")

# ============ CÁLCULOS ============
df_projecao = gerar_projecao_quinzenal(
    moagem, atr, mix, int(n_quinz), data_start,
    st.session_state.dados_reais if st.session_state.dados_reais else None,
    st.session_state.choques_safra if st.session_state.choques_safra else None
)

# Simula preços
df_precos, direcao, fator_oferta, choques_aplicados = simular_precos(
    ny11_inicial, usd_inicial, etanol_inicial, int(n_quinz),
    df_projecao[["Quinzena", "Moagem", "ATR", "MIX"]].rename(columns={"MIX": "MIX"}),
    preco_ref, sensibilidade / 100,
    st.session_state.choques_precos if st.session_state.choques_precos else None,
    False,  # usar_paridade = False
    st.session_state.dados_reais if st.session_state.dados_reais else None
)

# Merge com preços
df_completo = df_projecao.merge(df_precos, on="Quinzena")

# Calcula totais
acucar_total = df_completo["Açúcar (t)"].sum()
etanol_total = df_completo["Etanol Total (m³)"].sum()
etanol_anidro_cana_total = df_completo["Etanol Anidro Cana (m³)"].sum()
etanol_hidratado_cana_total = df_completo["Etanol Hidratado Cana (m³)"].sum()
etanol_anidro_milho_total = df_completo["Etanol Anidro Milho (m³)"].sum()
etanol_hidratado_milho_total = df_completo["Etanol Hidratado Milho (m³)"].sum()
etanol_total_acum = df_completo["Etanol Total Acumulado (m³)"].iloc[-1] if len(df_completo) > 0 else 0

ny11_final = df_precos.iloc[-1]["NY11_cents"]
usd_final = df_precos.iloc[-1]["USD_BRL"]
preco_brl_t_final = ny11_para_brl(ny11_final, usd_final)
preco_saca_final = preco_brl_t_final / 20
variacao_ny11 = ny11_final - ny11_inicial
variacao_pct = (variacao_ny11 / ny11_inicial) * 100 if ny11_inicial > 0 else 0

# ============ EXIBIÇÃO ============
st.divider()
st.subheader("📈 Resultados da Projeção")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Açúcar estimado", fmt_br(acucar_total, 0) + " t")
col2.metric("Etanol total estimado", fmt_br(etanol_total, 0) + " m³")
col3.metric("Preço final NY11", f"{ny11_final:.2f} USc/lb",
           delta=f"{variacao_ny11:+.2f} ({variacao_pct:+.2f}%)",
           delta_color="inverse" if variacao_ny11 < 0 else "normal")
col4.metric("Preço final (R$/saca)", fmt_br(preco_saca_final, 2))

st.write("")
col5, col6, col7, col8 = st.columns(4)
col5.metric("Etanol Anidro Cana", fmt_br(etanol_anidro_cana_total, 0) + " m³")
col6.metric("Etanol Hidratado Cana", fmt_br(etanol_hidratado_cana_total, 0) + " m³")
col7.metric("Etanol Anidro Milho", fmt_br(etanol_anidro_milho_total, 0) + " m³")
col8.metric("Etanol Hidratado Milho", fmt_br(etanol_hidratado_milho_total, 0) + " m³")

st.write("")
col9, col10 = st.columns(2)
col9.metric("Etanol Total Acumulado", fmt_br(etanol_total_acum, 0) + " m³")
col10.metric("USD/BRL final", f"{usd_final:.2f}",
           delta=f"{usd_final - usd_inicial:+.2f}",
           delta_color="inverse" if (usd_final - usd_inicial) < 0 else "normal")

st.divider()
st.subheader("📅 Evolução Quinzenal")

# Formata DataFrame para exibição
df_mostrar = df_completo.copy()
colunas_formatacao = {
    "Moagem": (0, fmt_br),
    "ATR": (2, fmt_br),
    "MIX": (2, fmt_br),
    "Açúcar (t)": (0, fmt_br),
    "Etanol Total (m³)": (0, fmt_br),
    "Etanol Anidro Cana (m³)": (0, fmt_br),
    "Etanol Hidratado Cana (m³)": (0, fmt_br),
    "Etanol Anidro Milho (m³)": (0, fmt_br),
    "Etanol Hidratado Milho (m³)": (0, fmt_br),
    "Etanol Total Quinzena (m³)": (0, fmt_br),
    "Etanol Total Acumulado (m³)": (0, fmt_br),
    "NY11_cents": (2, lambda x: f"{x:.2f}"),
    "Etanol_R$m3": (0, fmt_br),
    "USD_BRL": (2, lambda x: f"{x:.2f}"),
    "Etanol Anidro Preço (R$/m³)": (0, lambda x: fmt_br(x, 0) if x is not None and not pd.isna(x) else ""),
    "Etanol Hidratado Preço (R$/m³)": (0, lambda x: fmt_br(x, 0) if x is not None and not pd.isna(x) else "")
}

for coluna, (casas, func) in colunas_formatacao.items():
    if coluna in df_mostrar.columns:
        df_mostrar[coluna] = df_mostrar[coluna].apply(func)

# Remove coluna interna
df_mostrar_display = df_mostrar.drop(columns=["Tem Dados Reais"])

# Destaca linhas com dados reais
def highlight_real_data(row):
    if row.get("Tem Dados Reais", False):
        return ['background-color: #e8f5e9'] * len(row)
    return [''] * len(row)

# Seleciona colunas para exibição
colunas_exibir = [
    "Quinzena", "Data", "Moagem", "ATR", "MIX",
    "Açúcar (t)", "Etanol Total (m³)",
    "Etanol Anidro Cana (m³)", "Etanol Hidratado Cana (m³)",
    "Etanol Anidro Milho (m³)", "Etanol Hidratado Milho (m³)",
    "Etanol Total Quinzena (m³)", "Etanol Total Acumulado (m³)",
    "NY11_cents", "Etanol_R$m3", "USD_BRL"
]

# Adiciona colunas de preços de etanol se existirem
if "Etanol Anidro Preço (R$/m³)" in df_mostrar_display.columns:
    colunas_exibir.extend(["Etanol Anidro Preço (R$/m³)", "Etanol Hidratado Preço (R$/m³)"])

st.dataframe(
    df_mostrar_display[colunas_exibir],
    use_container_width=True,
    height=400,
    hide_index=True
)

# Informações adicionais
st.divider()
st.subheader("💡 Informações")

n_quinzenas_reais = sum(1 for q in st.session_state.dados_reais.values() if q.get('moagem_real'))
n_quinzenas_projetadas = int(n_quinz) - n_quinzenas_reais

choques_info = ""
if choques_aplicados:
    choques_info = f"\n\n**⚡ Choques de preços aplicados:**\n" + "\n".join(f"- {c}" for c in choques_aplicados)

st.info(
    f"""
    **Status da Projeção:**
    - **Quinzenas com dados reais:** {n_quinzenas_reais} de {int(n_quinz)}
    - **Quinzenas projetadas:** {n_quinzenas_projetadas} de {int(n_quinz)}
    - **Última quinzena com dados reais:** {max(st.session_state.dados_reais.keys()) if st.session_state.dados_reais else 'Nenhuma'}
    - **Tendência esperada:** {direcao.upper()}
    {choques_info}
    
    💡 *A projeção é ajustada automaticamente baseada nos dados reais inseridos. Choques só podem ser aplicados em quinzenas futuras (sem dados reais).*
    """
)