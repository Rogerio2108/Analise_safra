"""
================================================================================
ANÁLISE DE PARIDADES E ARBITRAGEM
================================================================================
Este módulo calcula paridades entre diferentes rotas de produção (etanol anidro,
hidratado, açúcar) considerando preços de mercado, impostos, CBIO, custos
logísticos e convertendo tudo para equivalente VHP para comparação.

================================================================================
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# ============================================================================
# CONSTANTES E PARÂMETROS CONFIGURÁVEIS
# ============================================================================

# Conversão açúcar
SACAS_POR_TON = 20
KG_POR_SACA = 50

# Conversão ton ↔ lb (cwt)
FATOR_CWT_POR_TON = 22.0462

# Fator de conversão entre ANIDRO e HIDRATADO
FATOR_CONV_ANIDRO_HIDRATADO = 0.0769  # 7,69%

# CBIO - Parâmetros tributários e participação
ALIQUOTA_IR_CBIO = 0.15  # 15% IR
ALIQUOTA_PIS_COFINS_CBIO = 0.0925  # 9,25% PIS/COFINS
SHARE_PRODUTOR_CBIO = 0.60  # 60% do valor líquido do CBIO fica na usina

# Fatores CBIO por produto (litros/CBIO)
FC_ANIDRO_LITROS_POR_CBIO = 712.40
FC_HIDRATADO_LITROS_POR_CBIO = 749.75

# Crédito tributário hidratado
CREDITO_TRIBUTARIO_HIDRATADO_POR_LITRO = 0.24  # R$/L

# Fatores de conversão etanol → VHP (parametrizados)
# Valores iniciais - devem ser calibrados com a planilha
FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP = 32.669  # m³ anidro export → saca VHP
FATOR_M3_HIDRATADO_EXPORT_PARA_SACA_VHP = 32.669  # m³ hidratado export → saca VHP
FATOR_M3_ANIDRO_INTERNO_PARA_SACA_VHP = 32.669  # m³ anidro interno → saca VHP
FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP = 32.669  # m³ hidratado interno → saca VHP

# ============================================================================
# FUNÇÕES DE CÁLCULO DE CBIO
# ============================================================================

def calcular_cbio_liquido_por_m3(
    preco_cbio_bruto_brl, 
    tipo='anidro',
    aliquota_ir=None,
    aliquota_pis_cofins=None,
    share_produtor=None,
    fc_anidro=None,
    fc_hidratado=None
):
    """
    Calcula valor líquido do CBIO por m³ de etanol.
    
    Args:
        preco_cbio_bruto_brl: Preço bruto do CBIO (R$/CBIO)
        tipo: 'anidro' ou 'hidratado'
        aliquota_ir: Alíquota IR (usa padrão se None)
        aliquota_pis_cofins: Alíquota PIS/COFINS (usa padrão se None)
        share_produtor: Share do produtor (usa padrão se None)
        fc_anidro: Fator conversão anidro (usa padrão se None)
        fc_hidratado: Fator conversão hidratado (usa padrão se None)
    
    Returns:
        float: Valor líquido do CBIO por m³ (R$/m³)
    """
    # Usa valores padrão se não fornecidos
    if aliquota_ir is None:
        aliquota_ir = ALIQUOTA_IR_CBIO
    if aliquota_pis_cofins is None:
        aliquota_pis_cofins = ALIQUOTA_PIS_COFINS_CBIO
    if share_produtor is None:
        share_produtor = SHARE_PRODUTOR_CBIO
    
    # Valor líquido por CBIO
    valor_cbio_liquido_por_cbio = (
        preco_cbio_bruto_brl 
        * (1 - aliquota_ir - aliquota_pis_cofins) 
        * share_produtor
    )
    
    # Valor líquido por litro
    if tipo == 'anidro':
        fc = fc_anidro if fc_anidro is not None else FC_ANIDRO_LITROS_POR_CBIO
    else:
        fc = fc_hidratado if fc_hidratado is not None else FC_HIDRATADO_LITROS_POR_CBIO
    
    valor_cbio_liquido_por_litro = valor_cbio_liquido_por_cbio / fc
    
    # Valor líquido por m³
    valor_cbio_liquido_por_m3 = valor_cbio_liquido_por_litro * 1000
    
    return valor_cbio_liquido_por_m3

# ============================================================================
# FUNÇÕES DE CONVERSÃO
# ============================================================================

def converter_cents_lb_para_usd_ton(cents_lb):
    """Converte cents/lb para USD/ton."""
    return (cents_lb / 100) * FATOR_CWT_POR_TON

def converter_usd_ton_para_cents_lb(usd_ton):
    """Converte USD/ton para cents/lb."""
    return (usd_ton * 100) / FATOR_CWT_POR_TON

def converter_brl_saca_para_usd_ton(brl_saca, cambio_usd_brl):
    """Converte R$/saca para USD/ton."""
    return (brl_saca * SACAS_POR_TON) / cambio_usd_brl

def converter_usd_ton_para_brl_saca(usd_ton, cambio_usd_brl):
    """Converte USD/ton para R$/saca."""
    return (usd_ton * cambio_usd_brl) / SACAS_POR_TON

# ============================================================================
# FUNÇÕES DE CÁLCULO DE PARIDADES
# ============================================================================

def calc_paridade_anidro_exportacao(
    preco_anidro_fob_usd_m3,
    cambio_usd_brl,
    frete_porto_usina_brl_m3,
    terminal_brl_m3,
    supervisao_doc_brl_m3,
    custos_adicionais_demurrage_brl_m3=0
):
    """
    Calcula paridade de etanol anidro para exportação.
    
    Returns:
        dict: Dicionário com todos os valores calculados
    """
    # Preço bruto PVU em R$/m³
    preco_bruto_pvu_brl_m3 = preco_anidro_fob_usd_m3 * cambio_usd_brl
    
    # Preço líquido PVU em R$/m³
    preco_liquido_pvu_brl_m3 = (
        preco_bruto_pvu_brl_m3
        - frete_porto_usina_brl_m3
        - terminal_brl_m3
        - supervisao_doc_brl_m3
        - custos_adicionais_demurrage_brl_m3
    )
    
    # Equivalente VHP BRL/saca PVU
    vhp_pvu_brl_saca = preco_liquido_pvu_brl_m3 / FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP
    
    # Equivalente VHP USD/ton PVU
    vhp_pvu_usd_ton = converter_brl_saca_para_usd_ton(vhp_pvu_brl_saca, cambio_usd_brl)
    
    # Equivalente VHP cents/lb PVU
    vhp_pvu_cents_lb = converter_usd_ton_para_cents_lb(vhp_pvu_usd_ton)
    
    # FOB equivalente (ajustando custos de volta)
    custos_totais_brl_m3 = (
        frete_porto_usina_brl_m3 + terminal_brl_m3 + 
        supervisao_doc_brl_m3 + custos_adicionais_demurrage_brl_m3
    )
    preco_fob_equivalente_brl_m3 = preco_liquido_pvu_brl_m3 + custos_totais_brl_m3
    vhp_fob_brl_saca = preco_fob_equivalente_brl_m3 / FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP
    vhp_fob_usd_ton = converter_brl_saca_para_usd_ton(vhp_fob_brl_saca, cambio_usd_brl)
    vhp_fob_cents_lb = converter_usd_ton_para_cents_lb(vhp_fob_usd_ton)
    
    return {
        'rota': 'Anidro Exportação',
        'preco_bruto_pvu_brl_m3': preco_bruto_pvu_brl_m3,
        'preco_liquido_pvu_brl_m3': preco_liquido_pvu_brl_m3,
        'vhp_pvu_brl_saca': vhp_pvu_brl_saca,
        'vhp_pvu_usd_ton': vhp_pvu_usd_ton,
        'vhp_pvu_cents_lb': vhp_pvu_cents_lb,
        'vhp_fob_cents_lb': vhp_fob_cents_lb
    }

def calc_paridade_hidratado_exportacao(
    preco_hidratado_fob_usd_m3,
    cambio_usd_brl,
    frete_porto_usina_brl_m3,
    terminal_brl_m3,
    supervisao_doc_brl_m3,
    custos_adicionais_demurrage_brl_m3=0
):
    """
    Calcula paridade de etanol hidratado para exportação.
    
    Returns:
        dict: Dicionário com todos os valores calculados
    """
    # Preço bruto PVU em R$/m³
    preco_bruto_pvu_brl_m3 = preco_hidratado_fob_usd_m3 * cambio_usd_brl
    
    # Preço líquido PVU em R$/m³
    preco_liquido_pvu_brl_m3 = (
        preco_bruto_pvu_brl_m3
        - frete_porto_usina_brl_m3
        - terminal_brl_m3
        - supervisao_doc_brl_m3
        - custos_adicionais_demurrage_brl_m3
    )
    
    # Equivalente VHP BRL/saca PVU
    vhp_pvu_brl_saca = preco_liquido_pvu_brl_m3 / FATOR_M3_HIDRATADO_EXPORT_PARA_SACA_VHP
    
    # Equivalente VHP USD/ton PVU
    vhp_pvu_usd_ton = converter_brl_saca_para_usd_ton(vhp_pvu_brl_saca, cambio_usd_brl)
    
    # Equivalente VHP cents/lb PVU
    vhp_pvu_cents_lb = converter_usd_ton_para_cents_lb(vhp_pvu_usd_ton)
    
    # FOB equivalente
    custos_totais_brl_m3 = (
        frete_porto_usina_brl_m3 + terminal_brl_m3 + 
        supervisao_doc_brl_m3 + custos_adicionais_demurrage_brl_m3
    )
    preco_fob_equivalente_brl_m3 = preco_liquido_pvu_brl_m3 + custos_totais_brl_m3
    vhp_fob_brl_saca = preco_fob_equivalente_brl_m3 / FATOR_M3_HIDRATADO_EXPORT_PARA_SACA_VHP
    vhp_fob_usd_ton = converter_brl_saca_para_usd_ton(vhp_fob_brl_saca, cambio_usd_brl)
    vhp_fob_cents_lb = converter_usd_ton_para_cents_lb(vhp_fob_usd_ton)
    
    return {
        'rota': 'Hidratado Exportação',
        'preco_bruto_pvu_brl_m3': preco_bruto_pvu_brl_m3,
        'preco_liquido_pvu_brl_m3': preco_liquido_pvu_brl_m3,
        'vhp_pvu_brl_saca': vhp_pvu_brl_saca,
        'vhp_pvu_usd_ton': vhp_pvu_usd_ton,
        'vhp_pvu_cents_lb': vhp_pvu_cents_lb,
        'vhp_fob_cents_lb': vhp_fob_cents_lb
    }

def calc_paridade_anidro_interno(
    preco_anidro_interno_com_impostos_brl_m3,
    pis_cofins_brl_m3,
    aliquota_icms,
    contribuicao_agroindustria_brl_m3,
    preco_cbio_bruto_brl,
    aliquota_ir_cbio=None,
    aliquota_pis_cofins_cbio=None,
    share_produtor_cbio=None,
    fc_anidro=None
):
    """
    Calcula paridade de etanol anidro para mercado interno.
    
    Returns:
        dict: Dicionário com todos os valores calculados
    """
    # ICMS
    icms_brl_m3 = preco_anidro_interno_com_impostos_brl_m3 * aliquota_icms
    
    # Preço líquido PVU sem CBIO
    preco_liquido_pvu_brl_m3 = (
        preco_anidro_interno_com_impostos_brl_m3
        - pis_cofins_brl_m3
        - icms_brl_m3
        - contribuicao_agroindustria_brl_m3
    )
    
    # CBIO - valor líquido por m³
    valor_cbio_liquido_por_m3 = calcular_cbio_liquido_por_m3(
        preco_cbio_bruto_brl, 
        'anidro',
        aliquota_ir_cbio,
        aliquota_pis_cofins_cbio,
        share_produtor_cbio,
        fc_anidro,
        None
    )
    
    # Preço PVU + CBIO
    preco_pvu_mais_cbio_brl_m3 = preco_liquido_pvu_brl_m3 + valor_cbio_liquido_por_m3
    
    # Equivalente HIDRATADO (fator 7,69%)
    preco_hid_equivalente_brl_m3 = preco_pvu_mais_cbio_brl_m3 * (1 - FATOR_CONV_ANIDRO_HIDRATADO)
    
    # Equivalente VHP BRL/saca PVU
    vhp_pvu_brl_saca = preco_pvu_mais_cbio_brl_m3 / FATOR_M3_ANIDRO_INTERNO_PARA_SACA_VHP
    
    # Para conversão para USD/ton e cents/lb, precisamos do câmbio
    # (será calculado na função principal)
    
    return {
        'rota': 'Anidro Mercado Interno',
        'preco_liquido_pvu_brl_m3': preco_liquido_pvu_brl_m3,
        'valor_cbio_liquido_por_m3': valor_cbio_liquido_por_m3,
        'preco_pvu_mais_cbio_brl_m3': preco_pvu_mais_cbio_brl_m3,
        'preco_hid_equivalente_brl_m3': preco_hid_equivalente_brl_m3,
        'vhp_pvu_brl_saca': vhp_pvu_brl_saca
    }

def calc_paridade_hidratado_interno(
    preco_hidratado_interno_com_impostos_brl_m3,
    pis_cofins_brl_m3,
    aliquota_icms,
    contribuicao_agroindustria_brl_m3,
    preco_cbio_bruto_brl,
    aliquota_ir_cbio=None,
    aliquota_pis_cofins_cbio=None,
    share_produtor_cbio=None,
    fc_hidratado=None
):
    """
    Calcula paridade de etanol hidratado para mercado interno.
    
    Returns:
        dict: Dicionário com todos os valores calculados
    """
    # ICMS
    icms_brl_m3 = preco_hidratado_interno_com_impostos_brl_m3 * aliquota_icms
    
    # Preço líquido PVU sem CBIO
    preco_liquido_pvu_brl_m3 = (
        preco_hidratado_interno_com_impostos_brl_m3
        - pis_cofins_brl_m3
        - icms_brl_m3
        - contribuicao_agroindustria_brl_m3
    )
    
    # CBIO - valor líquido por m³
    valor_cbio_liquido_por_m3 = calcular_cbio_liquido_por_m3(
        preco_cbio_bruto_brl, 
        'hidratado',
        aliquota_ir_cbio,
        aliquota_pis_cofins_cbio,
        share_produtor_cbio,
        None,
        fc_hidratado
    )
    
    # Preço PVU + CBIO
    preco_pvu_mais_cbio_brl_m3 = preco_liquido_pvu_brl_m3 + valor_cbio_liquido_por_m3
    
    # Crédito Tributário (0,24 R$/L = 240 R$/m³)
    credito_tributario_brl_m3 = CREDITO_TRIBUTARIO_HIDRATADO_POR_LITRO * 1000
    
    # Preço PVU + CBIO + Crédito Tributário
    preco_pvu_cbio_credito_brl_m3 = preco_pvu_mais_cbio_brl_m3 + credito_tributario_brl_m3
    
    # Equivalente ANIDRO (7,69%)
    preco_anidro_equivalente_brl_m3 = preco_pvu_mais_cbio_brl_m3 / (1 - FATOR_CONV_ANIDRO_HIDRATADO)
    
    # Equivalente VHP BRL/saca PVU (usando preço com crédito tributário)
    vhp_pvu_brl_saca = preco_pvu_cbio_credito_brl_m3 / FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP
    
    return {
        'rota': 'Hidratado Mercado Interno',
        'preco_liquido_pvu_brl_m3': preco_liquido_pvu_brl_m3,
        'valor_cbio_liquido_por_m3': valor_cbio_liquido_por_m3,
        'preco_pvu_mais_cbio_brl_m3': preco_pvu_mais_cbio_brl_m3,
        'credito_tributario_brl_m3': credito_tributario_brl_m3,
        'preco_pvu_cbio_credito_brl_m3': preco_pvu_cbio_credito_brl_m3,
        'preco_anidro_equivalente_brl_m3': preco_anidro_equivalente_brl_m3,
        'vhp_pvu_brl_saca': vhp_pvu_brl_saca
    }

def calc_paridade_acucar(
    ny_sugar_fob_cents_lb,
    premio_fisico_usd_ton_esq,
    premio_fisico_usd_ton_dir,
    cambio_usd_brl,
    fobizacao_container_brl_ton,
    frete_export_sugar_brl_ton,
    preco_sugar_cristal_esalq_brl_saca,
    preco_sugar_cristal_export_malha30_brl_saca
):
    """
    Calcula paridade de açúcar (NY11 + prêmios, Esalq, Cristal Export).
    
    Returns:
        dict: Dicionário com todos os valores calculados
    """
    # NY11 → USD/ton
    ny_usd_ton = converter_cents_lb_para_usd_ton(ny_sugar_fob_cents_lb)
    
    # FOB USD/ton (esquerda e direita)
    sugar_fob_usd_ton_esq = ny_usd_ton + premio_fisico_usd_ton_esq
    sugar_fob_usd_ton_dir = ny_usd_ton + premio_fisico_usd_ton_dir
    
    # FOB R$/ton
    sugar_fob_brl_ton_esq = sugar_fob_usd_ton_esq * cambio_usd_brl
    sugar_fob_brl_ton_dir = sugar_fob_usd_ton_dir * cambio_usd_brl
    
    # PVU R$/ton (descontando fobização e frete)
    sugar_pvu_brl_ton_esq = (
        sugar_fob_brl_ton_esq 
        - fobizacao_container_brl_ton 
        - frete_export_sugar_brl_ton
    )
    sugar_pvu_brl_ton_dir = (
        sugar_fob_brl_ton_dir 
        - fobizacao_container_brl_ton 
        - frete_export_sugar_brl_ton
    )
    
    # PVU R$/saca
    sugar_pvu_brl_saca_esq = sugar_pvu_brl_ton_esq / SACAS_POR_TON
    sugar_pvu_brl_saca_dir = sugar_pvu_brl_ton_dir / SACAS_POR_TON
    
    # PVU USD/ton
    sugar_pvu_usd_ton_esq = sugar_pvu_brl_ton_esq / cambio_usd_brl
    sugar_pvu_usd_ton_dir = sugar_pvu_brl_ton_dir / cambio_usd_brl
    
    # PVU cents/lb
    sugar_pvu_cents_lb_esq = converter_usd_ton_para_cents_lb(sugar_pvu_usd_ton_esq)
    sugar_pvu_cents_lb_dir = converter_usd_ton_para_cents_lb(sugar_pvu_usd_ton_dir)
    
    # FOB cents/lb
    sugar_fob_cents_lb_esq = converter_usd_ton_para_cents_lb(sugar_fob_usd_ton_esq)
    sugar_fob_cents_lb_dir = converter_usd_ton_para_cents_lb(sugar_fob_usd_ton_dir)
    
    return {
        'rota_esq': 'Açúcar Exportação (Esquerda)',
        'rota_dir': 'Açúcar Exportação (Direita/Malha 30)',
        'sugar_pvu_brl_saca_esq': sugar_pvu_brl_saca_esq,
        'sugar_pvu_brl_saca_dir': sugar_pvu_brl_saca_dir,
        'sugar_pvu_cents_lb_esq': sugar_pvu_cents_lb_esq,
        'sugar_pvu_cents_lb_dir': sugar_pvu_cents_lb_dir,
        'sugar_fob_cents_lb_esq': sugar_fob_cents_lb_esq,
        'sugar_fob_cents_lb_dir': sugar_fob_cents_lb_dir,
        'preco_sugar_cristal_esalq_brl_saca': preco_sugar_cristal_esalq_brl_saca,
        'preco_sugar_cristal_export_malha30_brl_saca': preco_sugar_cristal_export_malha30_brl_saca
    }

# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

st.set_page_config(page_title="Análise de Paridades e Arbitragem", layout="wide")

st.title("📊 Análise de Paridades e Arbitragem")
st.markdown("""
Esta ferramenta calcula paridades entre diferentes rotas de produção (etanol anidro, 
hidratado, açúcar) considerando preços de mercado, impostos, CBIO, custos logísticos 
e convertendo tudo para equivalente VHP para comparação.
""")

# ============================================================================
# SIDEBAR - PARÂMETROS CONFIGURÁVEIS
# ============================================================================

st.sidebar.header("⚙️ Parâmetros Técnicos")

with st.sidebar.expander("🔧 Fatores de Conversão Etanol → VHP", expanded=False):
    fator_anidro_export = st.number_input(
        "Fator m³ Anidro Export → Saca VHP",
        value=FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP,
        step=0.1,
        format="%.3f"
    )
    fator_hidratado_export = st.number_input(
        "Fator m³ Hidratado Export → Saca VHP",
        value=FATOR_M3_HIDRATADO_EXPORT_PARA_SACA_VHP,
        step=0.1,
        format="%.3f"
    )
    fator_anidro_interno = st.number_input(
        "Fator m³ Anidro Interno → Saca VHP",
        value=FATOR_M3_ANIDRO_INTERNO_PARA_SACA_VHP,
        step=0.1,
        format="%.3f"
    )
    fator_hidratado_interno = st.number_input(
        "Fator m³ Hidratado Interno → Saca VHP",
        value=FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP,
        step=0.1,
        format="%.3f"
    )

with st.sidebar.expander("📋 Parâmetros CBIO", expanded=False):
    aliquota_ir_cbio = st.number_input(
        "Alíquota IR CBIO (%)",
        value=ALIQUOTA_IR_CBIO * 100,
        step=0.1,
        format="%.2f"
    ) / 100
    aliquota_pis_cofins_cbio = st.number_input(
        "Alíquota PIS/COFINS CBIO (%)",
        value=ALIQUOTA_PIS_COFINS_CBIO * 100,
        step=0.1,
        format="%.2f"
    ) / 100
    share_produtor_cbio = st.number_input(
        "Share Produtor CBIO (%)",
        value=SHARE_PRODUTOR_CBIO * 100,
        step=1.0,
        format="%.0f"
    ) / 100
    fc_anidro = st.number_input(
        "FC Anidro (litros/CBIO)",
        value=FC_ANIDRO_LITROS_POR_CBIO,
        step=0.1,
        format="%.2f"
    )
    fc_hidratado = st.number_input(
        "FC Hidratado (litros/CBIO)",
        value=FC_HIDRATADO_LITROS_POR_CBIO,
        step=0.1,
        format="%.2f"
    )

# ============================================================================
# INPUTS DE MERCADO
# ============================================================================

st.header("💰 Preços de Mercado")

col1, col2 = st.columns(2)

with col1:
    st.subheader("💱 Câmbio e CBIO")
    cambio_usd_brl = st.number_input(
        "Câmbio USD/BRL",
        value=4.90,
        step=0.01,
        format="%.4f"
    )
    preco_cbio_bruto_brl = st.number_input(
        "Preço CBIO Bruto (R$/CBIO)",
        value=50.0,
        step=1.0,
        format="%.2f"
    )

with col2:
    st.subheader("🌾 Açúcar")
    ny_sugar_fob_cents_lb = st.number_input(
        "NY11 FOB (cents/lb)",
        value=14.50,
        step=0.10,
        format="%.2f"
    )
    premio_fisico_usd_ton_esq = st.number_input(
        "Prêmio Físico USD/ton (Esquerda)",
        value=0.0,
        step=1.0,
        format="%.2f"
    )
    premio_fisico_usd_ton_dir = st.number_input(
        "Prêmio Físico USD/ton (Direita/Malha 30)",
        value=0.0,
        step=1.0,
        format="%.2f"
    )

st.divider()

# ETANOL EXPORTAÇÃO
st.subheader("🚢 Etanol Exportação")

col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    st.markdown("**Anidro Exportação**")
    preco_anidro_fob_usd_m3 = st.number_input(
        "Preço Anidro FOB (USD/m³)",
        value=600.0,
        step=10.0,
        format="%.2f",
        key="anidro_fob"
    )
    frete_porto_usina_brl_m3_anidro = st.number_input(
        "Frete Porto-Usina (R$/m³)",
        value=50.0,
        step=5.0,
        format="%.2f",
        key="frete_anidro"
    )
    terminal_brl_m3_anidro = st.number_input(
        "Terminal (R$/m³)",
        value=30.0,
        step=5.0,
        format="%.2f",
        key="terminal_anidro"
    )
    supervisao_doc_brl_m3_anidro = st.number_input(
        "Supervisão/Doc (R$/m³)",
        value=10.0,
        step=1.0,
        format="%.2f",
        key="supervisao_anidro"
    )
    custos_adicionais_demurrage_brl_m3_anidro = st.number_input(
        "Custos Adicionais/Demurrage (R$/m³)",
        value=0.0,
        step=5.0,
        format="%.2f",
        key="demurrage_anidro"
    )

with col_exp2:
    st.markdown("**Hidratado Exportação**")
    preco_hidratado_fob_usd_m3 = st.number_input(
        "Preço Hidratado FOB (USD/m³)",
        value=550.0,
        step=10.0,
        format="%.2f",
        key="hidratado_fob"
    )
    frete_porto_usina_brl_m3_hidratado = st.number_input(
        "Frete Porto-Usina (R$/m³)",
        value=50.0,
        step=5.0,
        format="%.2f",
        key="frete_hidratado"
    )
    terminal_brl_m3_hidratado = st.number_input(
        "Terminal (R$/m³)",
        value=30.0,
        step=5.0,
        format="%.2f",
        key="terminal_hidratado"
    )
    supervisao_doc_brl_m3_hidratado = st.number_input(
        "Supervisão/Doc (R$/m³)",
        value=10.0,
        step=1.0,
        format="%.2f",
        key="supervisao_hidratado"
    )
    custos_adicionais_demurrage_brl_m3_hidratado = st.number_input(
        "Custos Adicionais/Demurrage (R$/m³)",
        value=0.0,
        step=5.0,
        format="%.2f",
        key="demurrage_hidratado"
    )

st.divider()

# ETANOL MERCADO INTERNO
st.subheader("🏠 Etanol Mercado Interno")

col_int1, col_int2 = st.columns(2)

with col_int1:
    st.markdown("**Anidro Mercado Interno**")
    preco_anidro_interno_com_impostos_brl_m3 = st.number_input(
        "Preço Anidro com Impostos (R$/m³)",
        value=2500.0,
        step=50.0,
        format="%.2f",
        key="anidro_interno"
    )
    pis_cofins_anidro_brl_m3 = st.number_input(
        "PIS/COFINS Anidro (R$/m³)",
        value=200.0,
        step=10.0,
        format="%.2f",
        key="pis_cofins_anidro"
    )
    aliquota_icms_anidro = st.number_input(
        "Alíquota ICMS Anidro (%)",
        value=0.0,
        step=1.0,
        format="%.2f",
        key="icms_anidro"
    ) / 100
    contribuicao_agroindustria_anidro_brl_m3 = st.number_input(
        "Contribuição Agroindústria Anidro (R$/m³)",
        value=0.0,
        step=1.0,
        format="%.2f",
        key="contrib_anidro"
    )

with col_int2:
    st.markdown("**Hidratado Mercado Interno**")
    preco_hidratado_interno_com_impostos_brl_m3 = st.number_input(
        "Preço Hidratado com Impostos (R$/m³)",
        value=2300.0,
        step=50.0,
        format="%.2f",
        key="hidratado_interno"
    )
    pis_cofins_hidratado_brl_m3 = st.number_input(
        "PIS/COFINS Hidratado (R$/m³)",
        value=180.0,
        step=10.0,
        format="%.2f",
        key="pis_cofins_hidratado"
    )
    aliquota_icms_hidratado = st.number_input(
        "Alíquota ICMS Hidratado (%)",
        value=12.0,
        step=1.0,
        format="%.2f",
        key="icms_hidratado"
    ) / 100
    contribuicao_agroindustria_hidratado_brl_m3 = st.number_input(
        "Contribuição Agroindústria Hidratado (R$/m³)",
        value=0.0,
        step=1.0,
        format="%.2f",
        key="contrib_hidratado"
    )

st.divider()

# AÇÚCAR
st.subheader("🍬 Açúcar")

col_acucar1, col_acucar2 = st.columns(2)

with col_acucar1:
    preco_sugar_cristal_esalq_brl_saca = st.number_input(
        "SUGAR Cristal Esalq (R$/saca)",
        value=120.0,
        step=1.0,
        format="%.2f",
        key="esalq"
    )
    preco_sugar_cristal_export_malha30_brl_saca = st.number_input(
        "Cristal Exportação Malha 30 (R$/saca)",
        value=115.0,
        step=1.0,
        format="%.2f",
        key="cristal_export"
    )

with col_acucar2:
    fobizacao_container_brl_ton = st.number_input(
        "Fobização Container (R$/ton)",
        value=50.0,
        step=5.0,
        format="%.2f",
        key="fobizacao"
    )
    frete_export_sugar_brl_ton = st.number_input(
        "Frete Exportação Açúcar (R$/ton)",
        value=100.0,
        step=10.0,
        format="%.2f",
        key="frete_sugar"
    )

# ============================================================================
# CÁLCULOS
# ============================================================================

st.divider()
st.header("📈 Resultados das Paridades")

# Atualiza fatores globais temporariamente
FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP = fator_anidro_export
FATOR_M3_HIDRATADO_EXPORT_PARA_SACA_VHP = fator_hidratado_export
FATOR_M3_ANIDRO_INTERNO_PARA_SACA_VHP = fator_anidro_interno
FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP = fator_hidratado_interno

# Calcula paridades
paridade_anidro_exp = calc_paridade_anidro_exportacao(
    preco_anidro_fob_usd_m3,
    cambio_usd_brl,
    frete_porto_usina_brl_m3_anidro,
    terminal_brl_m3_anidro,
    supervisao_doc_brl_m3_anidro,
    custos_adicionais_demurrage_brl_m3_anidro
)

paridade_hidratado_exp = calc_paridade_hidratado_exportacao(
    preco_hidratado_fob_usd_m3,
    cambio_usd_brl,
    frete_porto_usina_brl_m3_hidratado,
    terminal_brl_m3_hidratado,
    supervisao_doc_brl_m3_hidratado,
    custos_adicionais_demurrage_brl_m3_hidratado
)

paridade_anidro_int = calc_paridade_anidro_interno(
    preco_anidro_interno_com_impostos_brl_m3,
    pis_cofins_anidro_brl_m3,
    aliquota_icms_anidro,
    contribuicao_agroindustria_anidro_brl_m3,
    preco_cbio_bruto_brl,
    aliquota_ir_cbio,
    aliquota_pis_cofins_cbio,
    share_produtor_cbio,
    fc_anidro
)
# Adiciona conversões para USD/ton e cents/lb
paridade_anidro_int['vhp_pvu_usd_ton'] = converter_brl_saca_para_usd_ton(
    paridade_anidro_int['vhp_pvu_brl_saca'], cambio_usd_brl
)
paridade_anidro_int['vhp_pvu_cents_lb'] = converter_usd_ton_para_cents_lb(
    paridade_anidro_int['vhp_pvu_usd_ton']
)

paridade_hidratado_int = calc_paridade_hidratado_interno(
    preco_hidratado_interno_com_impostos_brl_m3,
    pis_cofins_hidratado_brl_m3,
    aliquota_icms_hidratado,
    contribuicao_agroindustria_hidratado_brl_m3,
    preco_cbio_bruto_brl,
    aliquota_ir_cbio,
    aliquota_pis_cofins_cbio,
    share_produtor_cbio,
    fc_hidratado
)
# Adiciona conversões para USD/ton e cents/lb
paridade_hidratado_int['vhp_pvu_usd_ton'] = converter_brl_saca_para_usd_ton(
    paridade_hidratado_int['vhp_pvu_brl_saca'], cambio_usd_brl
)
paridade_hidratado_int['vhp_pvu_cents_lb'] = converter_usd_ton_para_cents_lb(
    paridade_hidratado_int['vhp_pvu_usd_ton']
)

paridade_acucar = calc_paridade_acucar(
    ny_sugar_fob_cents_lb,
    premio_fisico_usd_ton_esq,
    premio_fisico_usd_ton_dir,
    cambio_usd_brl,
    fobizacao_container_brl_ton,
    frete_export_sugar_brl_ton,
    preco_sugar_cristal_esalq_brl_saca,
    preco_sugar_cristal_export_malha30_brl_saca
)

# ============================================================================
# TABELA COMPARATIVA
# ============================================================================

# Prepara dados para tabela
dados_comparacao = [
    {
        'Rota': 'Anidro Exportação',
        'PVU (R$/m³)': paridade_anidro_exp['preco_liquido_pvu_brl_m3'],
        'VHP PVU (R$/saca)': paridade_anidro_exp['vhp_pvu_brl_saca'],
        'VHP PVU (cents/lb)': paridade_anidro_exp['vhp_pvu_cents_lb'],
        'VHP FOB (cents/lb)': paridade_anidro_exp['vhp_fob_cents_lb']
    },
    {
        'Rota': 'Hidratado Exportação',
        'PVU (R$/m³)': paridade_hidratado_exp['preco_liquido_pvu_brl_m3'],
        'VHP PVU (R$/saca)': paridade_hidratado_exp['vhp_pvu_brl_saca'],
        'VHP PVU (cents/lb)': paridade_hidratado_exp['vhp_pvu_cents_lb'],
        'VHP FOB (cents/lb)': paridade_hidratado_exp['vhp_fob_cents_lb']
    },
    {
        'Rota': 'Anidro Mercado Interno',
        'PVU (R$/m³)': paridade_anidro_int['preco_pvu_mais_cbio_brl_m3'],
        'VHP PVU (R$/saca)': paridade_anidro_int['vhp_pvu_brl_saca'],
        'VHP PVU (cents/lb)': paridade_anidro_int['vhp_pvu_cents_lb'],
        'VHP FOB (cents/lb)': None
    },
    {
        'Rota': 'Hidratado Mercado Interno',
        'PVU (R$/m³)': paridade_hidratado_int['preco_pvu_cbio_credito_brl_m3'],
        'VHP PVU (R$/saca)': paridade_hidratado_int['vhp_pvu_brl_saca'],
        'VHP PVU (cents/lb)': paridade_hidratado_int['vhp_pvu_cents_lb'],
        'VHP FOB (cents/lb)': None
    },
    {
        'Rota': 'Açúcar Exportação (Esquerda)',
        'PVU (R$/m³)': None,
        'VHP PVU (R$/saca)': paridade_acucar['sugar_pvu_brl_saca_esq'],
        'VHP PVU (cents/lb)': paridade_acucar['sugar_pvu_cents_lb_esq'],
        'VHP FOB (cents/lb)': paridade_acucar['sugar_fob_cents_lb_esq']
    },
    {
        'Rota': 'Açúcar Exportação (Direita)',
        'PVU (R$/m³)': None,
        'VHP PVU (R$/saca)': paridade_acucar['sugar_pvu_brl_saca_dir'],
        'VHP PVU (cents/lb)': paridade_acucar['sugar_pvu_cents_lb_dir'],
        'VHP FOB (cents/lb)': paridade_acucar['sugar_fob_cents_lb_dir']
    },
    {
        'Rota': 'SUGAR Cristal Esalq',
        'PVU (R$/m³)': None,
        'VHP PVU (R$/saca)': preco_sugar_cristal_esalq_brl_saca,
        'VHP PVU (cents/lb)': converter_usd_ton_para_cents_lb(
            converter_brl_saca_para_usd_ton(preco_sugar_cristal_esalq_brl_saca, cambio_usd_brl)
        ),
        'VHP FOB (cents/lb)': None
    },
    {
        'Rota': 'Cristal Exportação Malha 30',
        'PVU (R$/m³)': None,
        'VHP PVU (R$/saca)': preco_sugar_cristal_export_malha30_brl_saca,
        'VHP PVU (cents/lb)': converter_usd_ton_para_cents_lb(
            converter_brl_saca_para_usd_ton(preco_sugar_cristal_export_malha30_brl_saca, cambio_usd_brl)
        ),
        'VHP FOB (cents/lb)': None
    }
]

df_comparacao = pd.DataFrame(dados_comparacao)

# Formatação da tabela
def formatar_valor(valor):
    if valor is None:
        return "-"
    if abs(valor) < 0.01:
        return "0.00"
    return f"{valor:,.2f}"

# Exibe tabela
st.subheader("📊 Comparação de Paridades")

# Cria cópia para formatação
df_display = df_comparacao.copy()
for col in ['PVU (R$/m³)', 'VHP PVU (R$/saca)', 'VHP PVU (cents/lb)', 'VHP FOB (cents/lb)']:
    df_display[col] = df_display[col].apply(formatar_valor)

st.dataframe(df_display, use_container_width=True, hide_index=True)

# ============================================================================
# GRÁFICO COMPARATIVO
# ============================================================================

st.subheader("📈 Visualização Comparativa")

# Prepara dados para gráfico
rotas = df_comparacao['Rota'].tolist()
vhp_pvu_saca = df_comparacao['VHP PVU (R$/saca)'].tolist()
vhp_pvu_cents = df_comparacao['VHP PVU (cents/lb)'].tolist()

# Remove None values para gráfico
rotas_clean = []
vhp_saca_clean = []
vhp_cents_clean = []

for i, (rota, saca, cents) in enumerate(zip(rotas, vhp_pvu_saca, vhp_pvu_cents)):
    if saca is not None:
        rotas_clean.append(rota)
        vhp_saca_clean.append(saca)
        vhp_cents_clean.append(cents)

# Gráfico de barras comparativo
fig = make_subplots(
    rows=1, cols=2,
    subplot_titles=('VHP PVU (R$/saca)', 'VHP PVU (cents/lb)'),
    horizontal_spacing=0.15
)

# Gráfico R$/saca
cores = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
fig.add_trace(
    go.Bar(
        x=rotas_clean,
        y=vhp_saca_clean,
        name='VHP PVU (R$/saca)',
        marker_color=cores[:len(rotas_clean)],
        text=[f'{v:,.2f}' for v in vhp_saca_clean],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>VHP PVU: R$ %{y:,.2f}/saca<extra></extra>'
    ),
    row=1, col=1
)

# Gráfico cents/lb
fig.add_trace(
    go.Bar(
        x=rotas_clean,
        y=vhp_cents_clean,
        name='VHP PVU (cents/lb)',
        marker_color=cores[:len(rotas_clean)],
        text=[f'{v:,.2f}' for v in vhp_cents_clean],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>VHP PVU: %{y:,.2f} cents/lb<extra></extra>',
        showlegend=False
    ),
    row=1, col=2
)

fig.update_layout(
    height=500,
    template='plotly_dark',
    font=dict(family="Arial", size=12, color="#ffffff"),
    legend=dict(
        font=dict(color="#ffffff", size=12),
        bgcolor='rgba(0,0,0,0.85)',
        bordercolor='rgba(255,255,255,0.4)',
        borderwidth=2
    ),
    margin=dict(t=80, b=150, l=60, r=60)
)

fig.update_xaxes(tickangle=-45, tickfont=dict(color="#ffffff", size=10), row=1, col=1)
fig.update_xaxes(tickangle=-45, tickfont=dict(color="#ffffff", size=10), row=1, col=2)
fig.update_yaxes(title="R$/saca", title_font=dict(color="#ffffff"), tickfont=dict(color="#ffffff"), row=1, col=1)
fig.update_yaxes(title="cents/lb", title_font=dict(color="#ffffff"), tickfont=dict(color="#ffffff"), row=1, col=2)

st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# ANÁLISE DE ARBITRAGEM
# ============================================================================

st.subheader("🎯 Análise de Arbitragem")

# Encontra a melhor rota
vhp_saca_validos = [(r, v) for r, v in zip(rotas_clean, vhp_saca_clean) if v is not None]
if vhp_saca_validos:
    melhor_rota_saca = max(vhp_saca_validos, key=lambda x: x[1])
    
    st.success(f"✅ **Melhor rota (VHP PVU em R$/saca):** {melhor_rota_saca[0]} - **R$ {melhor_rota_saca[1]:,.2f}/saca**")
    
    # Mostra diferença percentual
    st.markdown("**Diferença percentual em relação à melhor rota:**")
    diferencas = []
    for rota, valor in vhp_saca_validos:
        if rota != melhor_rota_saca[0]:
            diff_pct = ((valor - melhor_rota_saca[1]) / melhor_rota_saca[1]) * 100
            diferencas.append({
                'Rota': rota,
                'VHP PVU (R$/saca)': valor,
                'Diferença (%)': diff_pct
            })
    
    if diferencas:
        df_diferencas = pd.DataFrame(diferencas)
        df_diferencas['VHP PVU (R$/saca)'] = df_diferencas['VHP PVU (R$/saca)'].apply(lambda x: f"{x:,.2f}")
        df_diferencas['Diferença (%)'] = df_diferencas['Diferença (%)'].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(df_diferencas, use_container_width=True, hide_index=True)

# ============================================================================
# DETALHAMENTO POR ROTA
# ============================================================================

st.divider()
st.subheader("🔍 Detalhamento por Rota")

tabs = st.tabs([
    "Anidro Exportação",
    "Hidratado Exportação",
    "Anidro Interno",
    "Hidratado Interno",
    "Açúcar"
])

with tabs[0]:
    st.markdown("### Anidro Exportação")
    st.metric("Preço Bruto PVU", f"R$ {paridade_anidro_exp['preco_bruto_pvu_brl_m3']:,.2f}/m³")
    st.metric("Preço Líquido PVU", f"R$ {paridade_anidro_exp['preco_liquido_pvu_brl_m3']:,.2f}/m³")
    st.metric("VHP PVU (R$/saca)", f"R$ {paridade_anidro_exp['vhp_pvu_brl_saca']:,.2f}/saca")
    st.metric("VHP PVU (cents/lb)", f"{paridade_anidro_exp['vhp_pvu_cents_lb']:,.2f} cents/lb")
    st.metric("VHP FOB (cents/lb)", f"{paridade_anidro_exp['vhp_fob_cents_lb']:,.2f} cents/lb")

with tabs[1]:
    st.markdown("### Hidratado Exportação")
    st.metric("Preço Bruto PVU", f"R$ {paridade_hidratado_exp['preco_bruto_pvu_brl_m3']:,.2f}/m³")
    st.metric("Preço Líquido PVU", f"R$ {paridade_hidratado_exp['preco_liquido_pvu_brl_m3']:,.2f}/m³")
    st.metric("VHP PVU (R$/saca)", f"R$ {paridade_hidratado_exp['vhp_pvu_brl_saca']:,.2f}/saca")
    st.metric("VHP PVU (cents/lb)", f"{paridade_hidratado_exp['vhp_pvu_cents_lb']:,.2f} cents/lb")
    st.metric("VHP FOB (cents/lb)", f"{paridade_hidratado_exp['vhp_fob_cents_lb']:,.2f} cents/lb")

with tabs[2]:
    st.markdown("### Anidro Mercado Interno")
    st.metric("Preço Líquido PVU", f"R$ {paridade_anidro_int['preco_liquido_pvu_brl_m3']:,.2f}/m³")
    st.metric("CBIO Líquido", f"R$ {paridade_anidro_int['valor_cbio_liquido_por_m3']:,.2f}/m³")
    st.metric("Preço PVU + CBIO", f"R$ {paridade_anidro_int['preco_pvu_mais_cbio_brl_m3']:,.2f}/m³")
    st.metric("Equivalente Hidratado", f"R$ {paridade_anidro_int['preco_hid_equivalente_brl_m3']:,.2f}/m³")
    st.metric("VHP PVU (R$/saca)", f"R$ {paridade_anidro_int['vhp_pvu_brl_saca']:,.2f}/saca")
    st.metric("VHP PVU (cents/lb)", f"{paridade_anidro_int['vhp_pvu_cents_lb']:,.2f} cents/lb")

with tabs[3]:
    st.markdown("### Hidratado Mercado Interno")
    st.metric("Preço Líquido PVU", f"R$ {paridade_hidratado_int['preco_liquido_pvu_brl_m3']:,.2f}/m³")
    st.metric("CBIO Líquido", f"R$ {paridade_hidratado_int['valor_cbio_liquido_por_m3']:,.2f}/m³")
    st.metric("Preço PVU + CBIO", f"R$ {paridade_hidratado_int['preco_pvu_mais_cbio_brl_m3']:,.2f}/m³")
    st.metric("Crédito Tributário", f"R$ {paridade_hidratado_int['credito_tributario_brl_m3']:,.2f}/m³")
    st.metric("Preço PVU + CBIO + Crédito", f"R$ {paridade_hidratado_int['preco_pvu_cbio_credito_brl_m3']:,.2f}/m³")
    st.metric("Equivalente Anidro", f"R$ {paridade_hidratado_int['preco_anidro_equivalente_brl_m3']:,.2f}/m³")
    st.metric("VHP PVU (R$/saca)", f"R$ {paridade_hidratado_int['vhp_pvu_brl_saca']:,.2f}/saca")
    st.metric("VHP PVU (cents/lb)", f"{paridade_hidratado_int['vhp_pvu_cents_lb']:,.2f} cents/lb")

with tabs[4]:
    st.markdown("### Açúcar")
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown("**Exportação (Esquerda)**")
        st.metric("VHP PVU (R$/saca)", f"R$ {paridade_acucar['sugar_pvu_brl_saca_esq']:,.2f}/saca")
        st.metric("VHP PVU (cents/lb)", f"{paridade_acucar['sugar_pvu_cents_lb_esq']:,.2f} cents/lb")
        st.metric("VHP FOB (cents/lb)", f"{paridade_acucar['sugar_fob_cents_lb_esq']:,.2f} cents/lb")
    with col_a2:
        st.markdown("**Exportação (Direita/Malha 30)**")
        st.metric("VHP PVU (R$/saca)", f"R$ {paridade_acucar['sugar_pvu_brl_saca_dir']:,.2f}/saca")
        st.metric("VHP PVU (cents/lb)", f"{paridade_acucar['sugar_pvu_cents_lb_dir']:,.2f} cents/lb")
        st.metric("VHP FOB (cents/lb)", f"{paridade_acucar['sugar_fob_cents_lb_dir']:,.2f} cents/lb")
    
    st.divider()
    st.markdown("**Mercado Interno**")
    col_a3, col_a4 = st.columns(2)
    with col_a3:
        st.metric("SUGAR Cristal Esalq", f"R$ {preco_sugar_cristal_esalq_brl_saca:,.2f}/saca")
    with col_a4:
        st.metric("Cristal Exportação Malha 30", f"R$ {preco_sugar_cristal_export_malha30_brl_saca:,.2f}/saca")

