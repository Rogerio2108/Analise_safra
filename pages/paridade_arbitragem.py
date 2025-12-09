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
    """
    Converte cents/lb para USD/ton.
    
    Fórmula: cents/lb * 22.0462 = USD/ton
    Exemplo: 15.80 cents/lb * 22.0462 = 348.33 USD/ton
    """
    return cents_lb * FATOR_CWT_POR_TON

def converter_usd_ton_para_cents_lb(usd_ton):
    """
    Converte USD/ton para cents/lb.
    
    Fórmula: USD/ton / 22.0462 = cents/lb
    Exemplo: 348.33 USD/ton / 22.0462 = 15.80 cents/lb
    """
    return usd_ton / FATOR_CWT_POR_TON

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
    premio_fisico_usd_ton_cristal,
    premio_fisico_usd_ton_malha30,
    cambio_usd_brl,
    fobizacao_container_brl_ton,
    frete_export_sugar_brl_ton,
    preco_sugar_cristal_esalq_brl_saca,
    preco_sugar_cristal_export_malha30_brl_saca,
    terminal_usd_ton=None,
    premio_pol_percent=None,
    premio_desconto_cents_lb=None
):
    """
    Calcula paridade de açúcar (NY11 + prêmios, Esalq, Cristal Export).
    
    Args:
        terminal_usd_ton: Custo de terminal em USD/ton (para VHP)
        premio_pol_percent: Prêmio POL em percentual (para VHP)
        premio_desconto_cents_lb: Prêmio/desconto em cents/lb (para VHP)
    
    Returns:
        dict: Dicionário com todos os valores calculados
    """
    # NY11 → USD/ton
    ny_usd_ton = converter_cents_lb_para_usd_ton(ny_sugar_fob_cents_lb)
    
    # ===== CÁLCULO VHP (se parâmetros fornecidos) =====
    sugar_vhp_pvu_brl_saca = None
    sugar_vhp_pvu_cents_lb = None
    sugar_vhp_fob_cents_lb = None
    
    if premio_pol_percent is not None and premio_desconto_cents_lb is not None and terminal_usd_ton is not None:
        # Fórmula da planilha Excel: =(((C29*22,0462)-C30-(C32/C31))/20)*C31
        # Onde:
        # C29 = Sugar NY + POL (em cents/lb) = (NY + prêmio/desconto) * (1 + POL%)
        # C30 = Terminal USD/ton
        # C32 = Frete R$/ton
        # C31 = Câmbio
        # 22,0462 = FATOR_CWT_POR_TON
        # 20 = SACAS_POR_TON
        
        # NY11 + prêmio/desconto em cents/lb
        ny_com_premio_cents_lb = ny_sugar_fob_cents_lb + premio_desconto_cents_lb
        
        # Aplicar prêmio POL
        ny_com_pol_cents_lb = ny_com_premio_cents_lb * (1 + premio_pol_percent / 100)
        
        # Fórmula da planilha: (((NY+POL * 22.0462) - Terminal - (Frete/Câmbio)) / 20) * Câmbio
        sugar_vhp_pvu_brl_saca = (((ny_com_pol_cents_lb * FATOR_CWT_POR_TON) - terminal_usd_ton - (frete_export_sugar_brl_ton / cambio_usd_brl)) / SACAS_POR_TON) * cambio_usd_brl
        
        # PVU USD/ton
        sugar_vhp_pvu_usd_ton = sugar_vhp_pvu_brl_saca * SACAS_POR_TON / cambio_usd_brl
        
        # PVU cents/lb
        sugar_vhp_pvu_cents_lb = converter_usd_ton_para_cents_lb(sugar_vhp_pvu_usd_ton)
        
        # FOB cents/lb = NY + POL (já calculado)
        sugar_vhp_fob_cents_lb = ny_com_pol_cents_lb
    
    # ===== CÁLCULO CRISTAL EXPORTAÇÃO (baseado na planilha Excel) =====
    # Fórmula da planilha: (L30-L31-L32)/20
    # Onde:
    # L30 = Sugar FOB R$/ton = (NY USD/ton + Prêmio Físico) * Câmbio
    # L31 = Fobização Container R$/ton
    # L32 = Frete R$/ton
    # 20 = SACAS_POR_TON
    
    # FOB USD/ton = NY11 + Prêmio Físico
    sugar_fob_usd_ton_cristal = ny_usd_ton + premio_fisico_usd_ton_cristal
    sugar_fob_usd_ton_malha30 = ny_usd_ton + premio_fisico_usd_ton_malha30
    
    # FOB R$/ton
    sugar_fob_brl_ton_cristal = sugar_fob_usd_ton_cristal * cambio_usd_brl
    sugar_fob_brl_ton_malha30 = sugar_fob_usd_ton_malha30 * cambio_usd_brl
    
    # PVU R$/ton = FOB R$/ton - Fobização - Frete (fórmula da planilha)
    sugar_pvu_brl_ton_cristal = sugar_fob_brl_ton_cristal - fobizacao_container_brl_ton - frete_export_sugar_brl_ton
    sugar_pvu_brl_ton_malha30 = sugar_fob_brl_ton_malha30 - fobizacao_container_brl_ton - frete_export_sugar_brl_ton
    
    # PVU R$/saca (fórmula da planilha: /20)
    sugar_pvu_brl_saca_cristal = sugar_pvu_brl_ton_cristal / SACAS_POR_TON
    sugar_pvu_brl_saca_malha30 = sugar_pvu_brl_ton_malha30 / SACAS_POR_TON
    
    # PVU USD/ton
    sugar_pvu_usd_ton_cristal = sugar_pvu_brl_ton_cristal / cambio_usd_brl
    sugar_pvu_usd_ton_malha30 = sugar_pvu_brl_ton_malha30 / cambio_usd_brl
    
    # PVU cents/lb
    sugar_pvu_cents_lb_cristal = converter_usd_ton_para_cents_lb(sugar_pvu_usd_ton_cristal)
    sugar_pvu_cents_lb_malha30 = converter_usd_ton_para_cents_lb(sugar_pvu_usd_ton_malha30)
    
    # FOB cents/lb
    sugar_fob_cents_lb_cristal = converter_usd_ton_para_cents_lb(sugar_fob_usd_ton_cristal)
    sugar_fob_cents_lb_malha30 = converter_usd_ton_para_cents_lb(sugar_fob_usd_ton_malha30)
    
    return {
        'rota_cristal': 'Açúcar Cristal Exportação',
        'rota_malha30': 'Açúcar Cristal Exportação Malha 30',
        'sugar_pvu_brl_saca_cristal': sugar_pvu_brl_saca_cristal,
        'sugar_pvu_brl_saca_malha30': sugar_pvu_brl_saca_malha30,
        'sugar_pvu_cents_lb_cristal': sugar_pvu_cents_lb_cristal,
        'sugar_pvu_cents_lb_malha30': sugar_pvu_cents_lb_malha30,
        'sugar_fob_cents_lb_cristal': sugar_fob_cents_lb_cristal,
        'sugar_fob_cents_lb_malha30': sugar_fob_cents_lb_malha30,
        'preco_sugar_cristal_esalq_brl_saca': preco_sugar_cristal_esalq_brl_saca,
        'preco_sugar_cristal_export_malha30_brl_saca': preco_sugar_cristal_export_malha30_brl_saca,
        'sugar_vhp_pvu_brl_saca': sugar_vhp_pvu_brl_saca,
        'sugar_vhp_pvu_cents_lb': sugar_vhp_pvu_cents_lb,
        'sugar_vhp_fob_cents_lb': sugar_vhp_fob_cents_lb
    }

# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

st.set_page_config(page_title="Análise de Paridades e Arbitragem", layout="wide")

st.title("📊 Análise de Paridades e Arbitragem")
st.markdown("""
**Objetivo:** Comparar todas as rotas de produção (etanol anidro, hidratado, açúcar) 
convertendo tudo para **equivalente VHP (R$/saca e cents/lb)** para identificar qual 
rota é mais atrativa financeiramente.

**Como usar:** Insira os preços de mercado abaixo e veja na seção **"🎯 Decisão: Qual Rota Produzir?"** 
qual opção paga mais.
""")

# ============================================================================
# SIDEBAR - PARÂMETROS CONFIGURÁVEIS
# ============================================================================

st.sidebar.header("⚙️ Parâmetros Técnicos")
st.sidebar.caption("💡 Ajuste estes valores apenas se souber os fatores específicos da sua usina")

with st.sidebar.expander("🔧 Fatores de Conversão Etanol → VHP", expanded=False):
    st.caption("""
    **O que é:** Quantos m³ de etanol equivalem a 1 saca de açúcar VHP.
    
    **Exemplo:** Se 32,669 m³ de anidro = 1 saca VHP, então o fator é 32,669.
    
    **Como usar:** Deixe os valores padrão ou ajuste conforme calibração da sua planilha.
    """)
    fator_anidro_export = st.number_input(
        "Fator m³ Anidro Export → Saca VHP",
        value=FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP,
        step=0.1,
        format="%.3f",
        help="m³ de anidro exportação necessários para produzir 1 saca VHP"
    )
    fator_hidratado_export = st.number_input(
        "Fator m³ Hidratado Export → Saca VHP",
        value=FATOR_M3_HIDRATADO_EXPORT_PARA_SACA_VHP,
        step=0.1,
        format="%.3f",
        help="m³ de hidratado exportação necessários para produzir 1 saca VHP"
    )
    fator_anidro_interno = st.number_input(
        "Fator m³ Anidro Interno → Saca VHP",
        value=FATOR_M3_ANIDRO_INTERNO_PARA_SACA_VHP,
        step=0.1,
        format="%.3f",
        help="m³ de anidro mercado interno necessários para produzir 1 saca VHP"
    )
    fator_hidratado_interno = st.number_input(
        "Fator m³ Hidratado Interno → Saca VHP",
        value=FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP,
        step=0.1,
        format="%.3f",
        help="m³ de hidratado mercado interno necessários para produzir 1 saca VHP"
    )

with st.sidebar.expander("📋 Parâmetros CBIO", expanded=False):
    st.caption("""
    **O que é:** Parâmetros para calcular o valor líquido do CBIO que fica na usina.
    
    **Alíquotas:** Impostos descontados do CBIO bruto.
    
    **Share Produtor:** Percentual do valor líquido que fica na usina (resto vai para distribuidora).
    
    **FC (Fator de Conversão):** Quantos litros de etanol geram 1 CBIO.
    """)
    aliquota_ir_cbio = st.number_input(
        "Alíquota IR CBIO (%)",
        value=ALIQUOTA_IR_CBIO * 100,
        step=0.1,
        format="%.2f",
        help="Imposto de Renda sobre CBIO"
    ) / 100
    aliquota_pis_cofins_cbio = st.number_input(
        "Alíquota PIS/COFINS CBIO (%)",
        value=ALIQUOTA_PIS_COFINS_CBIO * 100,
        step=0.1,
        format="%.2f",
        help="PIS e COFINS sobre CBIO"
    ) / 100
    share_produtor_cbio = st.number_input(
        "Share Produtor CBIO (%)",
        value=SHARE_PRODUTOR_CBIO * 100,
        step=1.0,
        format="%.0f",
        help="Percentual do valor líquido do CBIO que fica na usina"
    ) / 100
    fc_anidro = st.number_input(
        "FC Anidro (litros/CBIO)",
        value=FC_ANIDRO_LITROS_POR_CBIO,
        step=0.1,
        format="%.2f",
        help="FC = Fator de Conversão. Quantos litros de etanol anidro são necessários para gerar 1 CBIO. Padrão: 712.40 litros/CBIO"
    )
    fc_hidratado = st.number_input(
        "FC Hidratado (litros/CBIO)",
        value=FC_HIDRATADO_LITROS_POR_CBIO,
        step=0.1,
        format="%.2f",
        help="FC = Fator de Conversão. Quantos litros de etanol hidratado são necessários para gerar 1 CBIO. Padrão: 749.75 litros/CBIO"
    )
    
    st.info("""
    **💡 O que é FC (Fator de Conversão) CBIO?**
    
    O **FC CBIO** indica quantos **litros de etanol** são necessários para gerar **1 CBIO** (Crédito de Descarbonização).
    
    - **Anidro:** 712.40 litros geram 1 CBIO
    - **Hidratado:** 749.75 litros geram 1 CBIO
    
    Este fator é usado para calcular quanto valor de CBIO você recebe por m³ de etanol produzido.
    """)

# ============================================================================
# INPUTS DE MERCADO
# ============================================================================

st.header("💰 Preços de Mercado")
st.caption("💡 Insira os preços atuais do mercado para calcular as paridades")

col1, col2 = st.columns(2)

with col1:
    st.subheader("💱 Câmbio e CBIO")
    cambio_usd_brl = st.number_input(
        "Câmbio USD/BRL",
        value=4.90,
        step=0.01,
        format="%.4f",
        help="Taxa de câmbio atual USD para BRL. Usado para converter preços de exportação."
    )
    preco_cbio_bruto_brl = st.number_input(
        "Preço CBIO Bruto (R$/CBIO)",
        value=50.0,
        step=1.0,
        format="%.2f",
        help="Preço bruto do CBIO no mercado. O sistema calcula automaticamente o valor líquido que fica na usina (após impostos e share do produtor)."
    )

with col2:
    st.subheader("🌾 Açúcar")
    ny_sugar_fob_cents_lb = st.number_input(
        "NY11 FOB (cents/lb)",
        value=15.80,
        step=0.10,
        format="%.2f",
        help="Preço do açúcar NY11 em cents por libra (preço de referência internacional)"
    )
    premio_fisico_usd_ton_cristal = st.number_input(
        "Prêmio Físico USD/ton (Cristal Exportação)",
        value=90.0,
        step=1.0,
        format="%.2f",
        help="Prêmio ou desconto físico em USD por tonelada para açúcar cristal exportação. Valores positivos = prêmio, negativos = desconto."
    )
    premio_fisico_usd_ton_malha30 = st.number_input(
        "Prêmio Físico USD/ton (Cristal Exportação Malha 30)",
        value=104.0,
        step=1.0,
        format="%.2f",
        help="Prêmio ou desconto físico em USD por tonelada para açúcar cristal exportação Malha 30. Valores positivos = prêmio, negativos = desconto."
    )

st.divider()

# ETANOL EXPORTAÇÃO
st.subheader("🚢 Etanol Exportação")

col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    st.markdown("**Anidro Exportação**")
    st.caption("💡 Preço FOB em USD convertido para R$ e descontados custos logísticos")
    preco_anidro_fob_usd_m3 = st.number_input(
        "Preço Anidro FOB (USD/m³)",
        value=600.0,
        step=10.0,
        format="%.2f",
        key="anidro_fob",
        help="Preço do etanol anidro FOB (Free On Board) em USD por m³"
    )
    frete_porto_usina_brl_m3_anidro = st.number_input(
        "Frete Porto-Usina (R$/m³)",
        value=50.0,
        step=5.0,
        format="%.2f",
        key="frete_anidro",
        help="Custo de frete do porto até a usina"
    )
    terminal_brl_m3_anidro = st.number_input(
        "Terminal (R$/m³)",
        value=30.0,
        step=5.0,
        format="%.2f",
        key="terminal_anidro",
        help="Custo de terminal/armazenagem"
    )
    supervisao_doc_brl_m3_anidro = st.number_input(
        "Supervisão/Doc (R$/m³)",
        value=10.0,
        step=1.0,
        format="%.2f",
        key="supervisao_anidro",
        help="Custo de supervisão e documentação"
    )
    custos_adicionais_demurrage_brl_m3_anidro = st.number_input(
        "Custos Adicionais/Demurrage (R$/m³)",
        value=0.0,
        step=5.0,
        format="%.2f",
        key="demurrage_anidro",
        help="Custos adicionais como demurrage (multa por atraso no porto)"
    )

with col_exp2:
    st.markdown("**Hidratado Exportação**")
    st.caption("💡 Preço FOB em USD convertido para R$ e descontados custos logísticos")
    preco_hidratado_fob_usd_m3 = st.number_input(
        "Preço Hidratado FOB (USD/m³)",
        value=550.0,
        step=10.0,
        format="%.2f",
        key="hidratado_fob",
        help="Preço do etanol hidratado FOB (Free On Board) em USD por m³"
    )
    frete_porto_usina_brl_m3_hidratado = st.number_input(
        "Frete Porto-Usina (R$/m³)",
        value=50.0,
        step=5.0,
        format="%.2f",
        key="frete_hidratado",
        help="Custo de frete do porto até a usina"
    )
    terminal_brl_m3_hidratado = st.number_input(
        "Terminal (R$/m³)",
        value=30.0,
        step=5.0,
        format="%.2f",
        key="terminal_hidratado",
        help="Custo de terminal/armazenagem"
    )
    supervisao_doc_brl_m3_hidratado = st.number_input(
        "Supervisão/Doc (R$/m³)",
        value=10.0,
        step=1.0,
        format="%.2f",
        key="supervisao_hidratado",
        help="Custo de supervisão e documentação"
    )
    custos_adicionais_demurrage_brl_m3_hidratado = st.number_input(
        "Custos Adicionais/Demurrage (R$/m³)",
        value=0.0,
        step=5.0,
        format="%.2f",
        key="demurrage_hidratado",
        help="Custos adicionais como demurrage (multa por atraso no porto)"
    )

st.divider()

# ETANOL MERCADO INTERNO
st.subheader("🏠 Etanol Mercado Interno")

col_int1, col_int2 = st.columns(2)

with col_int1:
    st.markdown("**Anidro Mercado Interno**")
    st.caption("💡 Preço com impostos, descontados impostos e adicionado CBIO líquido")
    preco_anidro_interno_com_impostos_brl_m3 = st.number_input(
        "Preço Anidro com Impostos (R$/m³)",
        value=2500.0,
        step=50.0,
        format="%.2f",
        key="anidro_interno",
        help="Preço de venda do anidro no mercado interno incluindo todos os impostos"
    )
    pis_cofins_anidro_brl_m3 = st.number_input(
        "PIS/COFINS Anidro (R$/m³)",
        value=200.0,
        step=10.0,
        format="%.2f",
        key="pis_cofins_anidro",
        help="Valor de PIS e COFINS incluído no preço (será descontado para calcular PVU líquido)"
    )
    aliquota_icms_anidro = st.number_input(
        "Alíquota ICMS Anidro (%)",
        value=0.0,
        step=1.0,
        format="%.2f",
        key="icms_anidro",
        help="Alíquota de ICMS sobre o anidro (geralmente 0% para anidro)"
    ) / 100
    contribuicao_agroindustria_anidro_brl_m3 = st.number_input(
        "Contribuição Agroindústria Anidro (R$/m³)",
        value=0.0,
        step=1.0,
        format="%.2f",
        key="contrib_anidro",
        help="Contribuição para agroindústria (geralmente 0)"
    )

with col_int2:
    st.markdown("**Hidratado Mercado Interno**")
    st.caption("💡 Preço com impostos, descontados impostos, adicionado CBIO líquido e crédito tributário (0,24 R$/L)")
    preco_hidratado_interno_com_impostos_brl_m3 = st.number_input(
        "Preço Hidratado com Impostos (R$/m³)",
        value=2300.0,
        step=50.0,
        format="%.2f",
        key="hidratado_interno",
        help="Preço de venda do hidratado no mercado interno incluindo todos os impostos"
    )
    pis_cofins_hidratado_brl_m3 = st.number_input(
        "PIS/COFINS Hidratado (R$/m³)",
        value=180.0,
        step=10.0,
        format="%.2f",
        key="pis_cofins_hidratado",
        help="Valor de PIS e COFINS incluído no preço (será descontado para calcular PVU líquido)"
    )
    aliquota_icms_hidratado = st.number_input(
        "Alíquota ICMS Hidratado (%)",
        value=12.0,
        step=1.0,
        format="%.2f",
        key="icms_hidratado",
        help="Alíquota de ICMS sobre o hidratado (geralmente 12%)"
    ) / 100
    contribuicao_agroindustria_hidratado_brl_m3 = st.number_input(
        "Contribuição Agroindústria Hidratado (R$/m³)",
        value=0.0,
        step=1.0,
        format="%.2f",
        key="contrib_hidratado",
        help="Contribuição para agroindústria (geralmente 0)"
    )

st.divider()

# AÇÚCAR
st.subheader("🍬 Açúcar")

col_acucar1, col_acucar2 = st.columns(2)

with col_acucar1:
    st.caption("💡 Preços de açúcar no mercado interno")
    preco_sugar_cristal_esalq_brl_saca = st.number_input(
        "SUGAR Cristal Esalq (R$/saca)",
        value=120.0,
        step=1.0,
        format="%.2f",
        key="esalq",
        help="Preço do açúcar cristal no mercado interno (Esalq)"
    )
    preco_sugar_cristal_export_malha30_brl_saca = st.number_input(
        "Cristal Exportação Malha 30 (R$/saca)",
        value=115.0,
        step=1.0,
        format="%.2f",
        key="cristal_export",
        help="Preço do açúcar cristal para exportação (Malha 30)"
    )

with col_acucar2:
    st.caption("💡 Custos logísticos para exportação de açúcar")
    fobizacao_container_brl_ton = st.number_input(
        "Fobização Container (R$/ton)",
        value=198.0,
        step=5.0,
        format="%.2f",
        key="fobizacao",
        help="Custo de fobização (preparação para exportação em container)"
    )
    frete_export_sugar_brl_ton = st.number_input(
        "Frete Exportação Açúcar (R$/ton)",
        value=202.0,
        step=10.0,
        format="%.2f",
        key="frete_sugar",
        help="Custo de frete para exportação de açúcar"
    )

st.divider()

# Parâmetros adicionais para VHP
st.subheader("🌾 Parâmetros Adicionais para Açúcar VHP")
col_vhp1, col_vhp2, col_vhp3 = st.columns(3)

with col_vhp1:
    terminal_usd_ton = st.number_input(
        "Terminal USD/ton (VHP)",
        value=12.50,
        step=0.5,
        format="%.2f",
        key="terminal_vhp",
        help="Custo de terminal em USD por tonelada para açúcar VHP"
    )

with col_vhp2:
    premio_pol_percent = st.number_input(
        "Prêmio POL (%) (VHP)",
        value=4.20,
        step=0.1,
        format="%.2f",
        key="premio_pol",
        help="Prêmio POL em percentual para açúcar VHP"
    )

with col_vhp3:
    premio_desconto_cents_lb = st.number_input(
        "Prêmio/Desconto (cents/lb) (VHP)",
        value=-0.10,
        step=0.1,
        format="%.2f",
        key="premio_desconto",
        help="Prêmio ou desconto em cents por libra para açúcar VHP (negativo = desconto)"
    )

# ============================================================================
# CÁLCULOS
# ============================================================================

st.divider()
st.header("📈 Resultados das Paridades")

# Seção explicativa
with st.expander("ℹ️ Como interpretar os resultados", expanded=True):
    st.markdown("""
    **📌 Conceito Principal:**
    
    Todas as rotas (etanol anidro, hidratado, açúcar) foram convertidas para **equivalente VHP (R$/saca)** 
    para que você possa comparar diretamente qual rota paga mais.
    
    **🔢 O que significa cada valor:**
    
    - **💰 VHP PVU (R$/saca):** Quanto você recebe por saca de açúcar equivalente. **ESTE É O VALOR PRINCIPAL PARA DECISÃO** - quanto maior, melhor!
    - **💵 VHP PVU (cents/lb):** Mesmo valor em cents por libra (padrão internacional de mercado)
    - **🏭 PVU (R$/m³):** Preço líquido na usina por m³ de etanol (só para rotas de etanol)
    - **📉 Diferença Absoluta:** Quanto a menos (em R$/saca) que cada rota paga comparado à melhor
    - **📊 Diferença %:** Percentual a menos que cada rota paga comparado à melhor
    
    **✅ Decisão:** A rota com **MAIOR VHP PVU (R$/saca)** é a mais atrativa financeiramente.
    """)

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
    premio_fisico_usd_ton_cristal,
    premio_fisico_usd_ton_malha30,
    cambio_usd_brl,
    fobizacao_container_brl_ton,
    frete_export_sugar_brl_ton,
    preco_sugar_cristal_esalq_brl_saca,
    preco_sugar_cristal_export_malha30_brl_saca,
    terminal_usd_ton=terminal_usd_ton,
    premio_pol_percent=premio_pol_percent,
    premio_desconto_cents_lb=premio_desconto_cents_lb
)

# ============================================================================
# DECISÃO: QUAL ROTA PRODUZIR?
# ============================================================================

st.divider()
st.header("🎯 Decisão: Qual Rota Produzir?")
st.markdown("""
**📌 Objetivo:** Todas as rotas foram convertidas para **equivalente VHP (R$/saca)** para comparação direta.
Quanto maior o valor, mais atrativa é a rota.
""")

# Prepara dados para comparação focada no VHP PVU (R$/saca) - métrica principal
dados_decisao = []

# Etanol Exportação
dados_decisao.append({
    'Rota': '🚢 Anidro Exportação',
    'VHP PVU (R$/saca)': paridade_anidro_exp['vhp_pvu_brl_saca'],
    'VHP PVU (cents/lb)': paridade_anidro_exp['vhp_pvu_cents_lb'],
    'PVU (R$/m³)': paridade_anidro_exp['preco_liquido_pvu_brl_m3'],
    'Tipo': 'Etanol'
})

dados_decisao.append({
    'Rota': '🚢 Hidratado Exportação',
    'VHP PVU (R$/saca)': paridade_hidratado_exp['vhp_pvu_brl_saca'],
    'VHP PVU (cents/lb)': paridade_hidratado_exp['vhp_pvu_cents_lb'],
    'PVU (R$/m³)': paridade_hidratado_exp['preco_liquido_pvu_brl_m3'],
    'Tipo': 'Etanol'
})

# Etanol Mercado Interno
dados_decisao.append({
    'Rota': '🏠 Anidro Mercado Interno',
    'VHP PVU (R$/saca)': paridade_anidro_int['vhp_pvu_brl_saca'],
    'VHP PVU (cents/lb)': paridade_anidro_int['vhp_pvu_cents_lb'],
    'PVU (R$/m³)': paridade_anidro_int['preco_pvu_mais_cbio_brl_m3'],
    'Tipo': 'Etanol'
})

dados_decisao.append({
    'Rota': '🏠 Hidratado Mercado Interno',
    'VHP PVU (R$/saca)': paridade_hidratado_int['vhp_pvu_brl_saca'],
    'VHP PVU (cents/lb)': paridade_hidratado_int['vhp_pvu_cents_lb'],
    'PVU (R$/m³)': paridade_hidratado_int['preco_pvu_cbio_credito_brl_m3'],
    'Tipo': 'Etanol'
})

# Açúcar VHP (se calculado)
if paridade_acucar.get('sugar_vhp_pvu_brl_saca') is not None:
    dados_decisao.append({
        'Rota': '🍬 Açúcar VHP Exportação',
        'VHP PVU (R$/saca)': paridade_acucar['sugar_vhp_pvu_brl_saca'],
        'VHP PVU (cents/lb)': paridade_acucar['sugar_vhp_pvu_cents_lb'],
        'PVU (R$/m³)': None,
        'Tipo': 'Açúcar'
    })

# Açúcar Cristal Exportação
dados_decisao.append({
    'Rota': '🍬 Açúcar Cristal Exportação',
    'VHP PVU (R$/saca)': paridade_acucar['sugar_pvu_brl_saca_cristal'],
    'VHP PVU (cents/lb)': paridade_acucar['sugar_pvu_cents_lb_cristal'],
    'PVU (R$/m³)': None,
    'Tipo': 'Açúcar'
})

dados_decisao.append({
    'Rota': '🍬 Açúcar Cristal Exportação Malha 30',
    'VHP PVU (R$/saca)': paridade_acucar['sugar_pvu_brl_saca_malha30'],
    'VHP PVU (cents/lb)': paridade_acucar['sugar_pvu_cents_lb_malha30'],
    'PVU (R$/m³)': None,
    'Tipo': 'Açúcar'
})

dados_decisao.append({
    'Rota': '🍬 SUGAR Cristal Esalq',
    'VHP PVU (R$/saca)': preco_sugar_cristal_esalq_brl_saca,
    'VHP PVU (cents/lb)': converter_usd_ton_para_cents_lb(
        converter_brl_saca_para_usd_ton(preco_sugar_cristal_esalq_brl_saca, cambio_usd_brl)
    ),
    'PVU (R$/m³)': None,
    'Tipo': 'Açúcar'
})

dados_decisao.append({
    'Rota': '🍬 Cristal Exportação Malha 30',
    'VHP PVU (R$/saca)': preco_sugar_cristal_export_malha30_brl_saca,
    'VHP PVU (cents/lb)': converter_usd_ton_para_cents_lb(
        converter_brl_saca_para_usd_ton(preco_sugar_cristal_export_malha30_brl_saca, cambio_usd_brl)
    ),
    'PVU (R$/m³)': None,
    'Tipo': 'Açúcar'
})

df_decisao = pd.DataFrame(dados_decisao)
df_decisao = df_decisao.sort_values('VHP PVU (R$/saca)', ascending=False)

# Encontra a melhor rota
melhor_rota = df_decisao.iloc[0]

# Resumo visual das top 3 rotas
st.markdown("### 🏆 Top 3 Rotas Mais Atrativas")

top3 = df_decisao.head(3)
cols_top3 = st.columns(3)

for i, (idx, row) in enumerate(top3.iterrows()):
    with cols_top3[i]:
        if i == 0:
            st.success(f"""
            **🥇 {row['Rota']}**
            
            **💰 R$ {row['VHP PVU (R$/saca)']:,.2f}/saca**
            
            **💵 {row['VHP PVU (cents/lb)']:,.2f} cents/lb**
            """)
        elif i == 1:
            st.info(f"""
            **🥈 {row['Rota']}**
            
            **💰 R$ {row['VHP PVU (R$/saca)']:,.2f}/saca**
            
            **💵 {row['VHP PVU (cents/lb)']:,.2f} cents/lb**
            
            Diferença: R$ {row['VHP PVU (R$/saca)'] - melhor_rota['VHP PVU (R$/saca)']:+,.2f}/saca
            """)
        else:
            st.warning(f"""
            **🥉 {row['Rota']}**
            
            **💰 R$ {row['VHP PVU (R$/saca)']:,.2f}/saca**
            
            **💵 {row['VHP PVU (cents/lb)']:,.2f} cents/lb**
            
            Diferença: R$ {row['VHP PVU (R$/saca)'] - melhor_rota['VHP PVU (R$/saca)']:+,.2f}/saca
            """)

st.divider()

# Cards destacando a melhor rota com destaque visual
st.markdown("### ✅ **MELHOR OPÇÃO PARA PRODUZIR**")

# Container destacado para a melhor rota
st.success(f"""
**🎯 {melhor_rota['Rota']}**

**💰 VHP PVU: R$ {melhor_rota['VHP PVU (R$/saca)']:,.2f}/saca** | **💵 {melhor_rota['VHP PVU (cents/lb)']:,.2f} cents/lb**

Esta é a rota que paga **MAIS** em equivalente VHP. Todas as outras rotas pagam menos.
""", icon="✅")

# Cards com métricas
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        "📍 Rota",
        melhor_rota['Rota'],
        delta=None
    )
with col2:
    st.metric(
        "💰 VHP PVU (R$/saca)",
        f"R$ {melhor_rota['VHP PVU (R$/saca)']:,.2f}",
        delta="Melhor opção",
        delta_color="normal"
    )
with col3:
    st.metric(
        "💵 VHP PVU (cents/lb)",
        f"{melhor_rota['VHP PVU (cents/lb)']:,.2f}",
        delta=None
    )
with col4:
    if melhor_rota['PVU (R$/m³)'] is not None:
        st.metric(
            "🏭 PVU (R$/m³)",
            f"R$ {melhor_rota['PVU (R$/m³)']:,.2f}",
            delta=None
        )
    else:
        st.metric(
            "🏭 PVU",
            "N/A (Açúcar)",
            delta=None
        )

st.divider()

# Tabela comparativa ordenada
st.markdown("### 📊 Comparação Completa de Todas as Rotas")

# Formatação melhorada
df_display_decisao = df_decisao.copy()

# Adiciona coluna de diferença percentual e absoluta (mantém valores numéricos para highlight)
df_display_decisao['Diferença Absoluta (R$/saca)'] = df_decisao['VHP PVU (R$/saca)'].apply(
    lambda x: x - melhor_rota['VHP PVU (R$/saca)']
)
df_display_decisao['Diferença Percentual'] = df_decisao['VHP PVU (R$/saca)'].apply(
    lambda x: ((x - melhor_rota['VHP PVU (R$/saca)']) / melhor_rota['VHP PVU (R$/saca)']) * 100
)

# Renomeia coluna Rota primeiro
df_display_decisao = df_display_decisao.rename(columns={
    'Rota': '📍 Rota'
})

# Formata valores (depois de renomear)
df_display_decisao['💰 VHP PVU (R$/saca)'] = df_decisao['VHP PVU (R$/saca)'].apply(lambda x: f"R$ {x:,.2f}")
df_display_decisao['💵 VHP PVU (cents/lb)'] = df_decisao['VHP PVU (cents/lb)'].apply(lambda x: f"{x:,.2f}")
df_display_decisao['🏭 PVU (R$/m³)'] = df_decisao['PVU (R$/m³)'].apply(lambda x: f"R$ {x:,.2f}" if x is not None else "-")
df_display_decisao['📉 Diferença Absoluta'] = df_display_decisao['Diferença Absoluta (R$/saca)'].apply(lambda x: f"R$ {x:+,.2f}")
df_display_decisao['📊 Diferença %'] = df_display_decisao['Diferença Percentual'].apply(lambda x: f"{x:+.2f}%")

# Cria mapeamento de rotas para diferenças (para usar na função de highlight)
mapeamento_diferencas = {}
for idx, row in df_display_decisao.iterrows():
    rota = row['📍 Rota']
    mapeamento_diferencas[rota] = {
        'diff_abs': row['Diferença Absoluta (R$/saca)'],
        'diff_pct': row['Diferença Percentual']
    }

# Destaca a melhor rota e formata diferenças
def highlight_best_and_format(row):
    styles = []
    rota_atual = row['📍 Rota']
    is_best = rota_atual == melhor_rota['Rota']
    
    # Pega diferenças do mapeamento (mais seguro que acessar DataFrame)
    diffs = mapeamento_diferencas.get(rota_atual, {'diff_abs': 0, 'diff_pct': 0})
    diff_abs = diffs['diff_abs']
    diff_pct = diffs['diff_pct']
    
    for col in colunas_exibir:
        if is_best:
            styles.append('background-color: #2d5016; color: white; font-weight: bold')
        elif col == '📉 Diferença Absoluta':
            if diff_abs < 0:
                styles.append('background-color: #4a1c1c; color: #ffcccc')
            else:
                styles.append('')
        elif col == '📊 Diferença %':
            if diff_pct < 0:
                styles.append('background-color: #4a1c1c; color: #ffcccc')
            else:
                styles.append('')
        else:
            styles.append('')
    return styles

# Seleciona colunas para exibição
colunas_exibir = ['📍 Rota', '💰 VHP PVU (R$/saca)', '💵 VHP PVU (cents/lb)', '🏭 PVU (R$/m³)', '📉 Diferença Absoluta', '📊 Diferença %']

st.dataframe(
    df_display_decisao[colunas_exibir].style.apply(highlight_best_and_format, axis=1),
    use_container_width=True,
    hide_index=True
)

st.caption("""
**💡 Como interpretar:**
- **💰 VHP PVU (R$/saca):** Quanto você recebe por saca de açúcar equivalente (quanto maior, melhor) - **ESTE É O VALOR PRINCIPAL PARA DECISÃO**
- **💵 VHP PVU (cents/lb):** Mesmo valor em cents por libra (padrão internacional)
- **🏭 PVU (R$/m³):** Preço líquido na usina por m³ de etanol (só para etanol)
- **📉 Diferença vs Melhor:** Quanto cada rota paga a menos que a melhor opção (valores negativos indicam que paga menos)
""")

# ============================================================================
# GRÁFICO COMPARATIVO
# ============================================================================

st.divider()
st.subheader("📈 Visualização Gráfica")

# Prepara dados para gráfico (usando df_decisao que já está ordenado)
rotas_clean = df_decisao['Rota'].tolist()
vhp_saca_clean = df_decisao['VHP PVU (R$/saca)'].tolist()
vhp_cents_clean = df_decisao['VHP PVU (cents/lb)'].tolist()
tipos = df_decisao['Tipo'].tolist()

# Define cores por tipo
cores_por_tipo = {
    'Etanol': '#2ca02c',  # Verde
    'Açúcar': '#d62728'   # Vermelho
}
cores = [cores_por_tipo[tipo] for tipo in tipos]

# Gráfico de barras comparativo
fig = make_subplots(
    rows=1, cols=2,
    subplot_titles=('💰 VHP PVU (R$/saca) - Quanto você recebe por saca', '💵 VHP PVU (cents/lb) - Padrão internacional'),
    horizontal_spacing=0.15
)

# Gráfico R$/saca
fig.add_trace(
    go.Bar(
        x=rotas_clean,
        y=vhp_saca_clean,
        name='VHP PVU (R$/saca)',
        marker_color=cores,
        text=[f'R$ {v:,.2f}' for v in vhp_saca_clean],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>💰 VHP PVU: R$ %{y:,.2f}/saca<extra></extra>',
        marker_line=dict(color='white', width=2)
    ),
    row=1, col=1
)

# Gráfico cents/lb
fig.add_trace(
    go.Bar(
        x=rotas_clean,
        y=vhp_cents_clean,
        name='VHP PVU (cents/lb)',
        marker_color=cores,
        text=[f'{v:,.2f}' for v in vhp_cents_clean],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>💵 VHP PVU: %{y:,.2f} cents/lb<extra></extra>',
        showlegend=False,
        marker_line=dict(color='white', width=2)
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
    
    # VHP Exportação
    if paridade_acucar.get('sugar_vhp_pvu_brl_saca') is not None:
        st.markdown("**Açúcar VHP Exportação**")
        st.metric("VHP PVU (R$/saca)", f"R$ {paridade_acucar['sugar_vhp_pvu_brl_saca']:,.2f}/saca")
        st.metric("VHP PVU (cents/lb)", f"{paridade_acucar['sugar_vhp_pvu_cents_lb']:,.2f} cents/lb")
        st.metric("VHP FOB (cents/lb)", f"{paridade_acucar['sugar_vhp_fob_cents_lb']:,.2f} cents/lb")
        st.divider()
    
    # Cristal Exportação
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown("**Cristal Exportação**")
        st.metric("VHP PVU (R$/saca)", f"R$ {paridade_acucar['sugar_pvu_brl_saca_cristal']:,.2f}/saca")
        st.metric("VHP PVU (cents/lb)", f"{paridade_acucar['sugar_pvu_cents_lb_cristal']:,.2f} cents/lb")
        st.metric("VHP FOB (cents/lb)", f"{paridade_acucar['sugar_fob_cents_lb_cristal']:,.2f} cents/lb")
    with col_a2:
        st.markdown("**Cristal Exportação Malha 30**")
        st.metric("VHP PVU (R$/saca)", f"R$ {paridade_acucar['sugar_pvu_brl_saca_malha30']:,.2f}/saca")
        st.metric("VHP PVU (cents/lb)", f"{paridade_acucar['sugar_pvu_cents_lb_malha30']:,.2f} cents/lb")
        st.metric("VHP FOB (cents/lb)", f"{paridade_acucar['sugar_fob_cents_lb_malha30']:,.2f} cents/lb")
    
    st.divider()
    st.markdown("**Mercado Interno**")
    col_a3, col_a4 = st.columns(2)
    with col_a3:
        st.metric("SUGAR Cristal Esalq", f"R$ {preco_sugar_cristal_esalq_brl_saca:,.2f}/saca")
    with col_a4:
        st.metric("Cristal Exportação Malha 30", f"R$ {preco_sugar_cristal_export_malha30_brl_saca:,.2f}/saca")

