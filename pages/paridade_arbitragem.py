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

# Fatores de conversão etanol → VHP (EXATOS da planilha Excel)
FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP = 32.669  # m³ anidro export → saca VHP (C10 = C9/32.669)
FATOR_M3_HIDRATADO_EXPORT_PARA_SACA_VHP = 31.304  # m³ hidratado export → saca VHP (F9 = F8/31.304)
FATOR_M3_ANIDRO_INTERNO_PARA_SACA_VHP = 33.712  # m³ anidro interno → saca VHP (I14 = I9/33.712)
FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP = 31.504  # m³ hidratado interno → saca VHP (L14 = L10/31.504)

# Fator de desconto VHP FOB (1.042 = 4.2%)
FATOR_DESCONTO_VHP_FOB = 1.042

# Fator de conversão Cristal vs VHP (custo diferencial - será input)
# Por enquanto, valor padrão (será configurável na interface)
CUSTO_CRISTAL_VS_VHP_D17 = 0.0  # Será input do usuário

# Impostos Esalq
IMPOSTOS_ESALQ = 0.0985  # 9.85%
FATOR_ESALQ_SEM_IMPOSTOS = 0.9015  # 1 - 0.0985

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
    preco_anidro_fob_usd_m3,  # C3
    cambio_usd_brl,  # C4
    frete_porto_usina_brl_m3,  # C5
    terminal_brl_m3,  # C6
    supervisao_doc_brl_m3,  # C7
    custos_adicionais_demurrage_brl_m3=0,  # C8
    terminal_usd_ton=None,  # C30 (do bloco açúcar)
    frete_brl_ton=None  # C32 (do bloco açúcar)
):
    """
    BLOCO 1 — ANIDRO EXPORTAÇÃO (colunas B/C, linhas 3–12)
    
    Calcula paridade de etanol anidro para exportação seguindo EXATAMENTE as fórmulas da planilha Excel.
    
    Args:
        preco_anidro_fob_usd_m3: C3 - Preço FOB USD/m³
        cambio_usd_brl: C4 - Câmbio USD/BRL
        frete_porto_usina_brl_m3: C5 - Frete Porto-Usina R$/m³
        terminal_brl_m3: C6 - Terminal R$/m³
        supervisao_doc_brl_m3: C7 - Supervisão/Doc R$/m³
        custos_adicionais_demurrage_brl_m3: C8 - Custos Adicionais/Demurrage R$/m³
        terminal_usd_ton: C30 - Terminal USD/ton (do bloco açúcar, para cálculo FOB)
        frete_brl_ton: C32 - Frete R$/ton (do bloco açúcar, para cálculo FOB)
    
    Returns:
        dict: Dicionário com todos os valores calculados (C9-C12)
    """
    # C9: Preço líquido PVU
    # Excel: =((C3*C4)-C5-C6-C7-C8)
    preco_liquido_pvu_brl_m3 = (preco_anidro_fob_usd_m3 * cambio_usd_brl) - frete_porto_usina_brl_m3 - terminal_brl_m3 - supervisao_doc_brl_m3 - custos_adicionais_demurrage_brl_m3
    
    # C10: Equivalente VHP BRL/saca PVU
    # Excel: =C9/32.669
    vhp_pvu_brl_saca = preco_liquido_pvu_brl_m3 / FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP
    
    # C11: Equivalente Cents/lb PVU
    # Excel: =((C10*20)/22.0462)/C4/1.042
    vhp_pvu_cents_lb = ((vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl / FATOR_DESCONTO_VHP_FOB
    
    # C12: Equivalente Cents/lb FOB
    # Excel: =((((((C9)/32.669)*20)+$C$32+($C$30*$C$4))/22.0462/$C$4)/1.042)
    # Nota: Requer C30 (terminal_usd_ton) e C32 (frete_brl_ton) do bloco açúcar
    vhp_fob_cents_lb = None
    if terminal_usd_ton is not None and frete_brl_ton is not None:
        vhp_fob_cents_lb = (((((preco_liquido_pvu_brl_m3) / FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP) * SACAS_POR_TON) + frete_brl_ton + (terminal_usd_ton * cambio_usd_brl)) / FATOR_CWT_POR_TON / cambio_usd_brl) / FATOR_DESCONTO_VHP_FOB
    
    return {
        'rota': 'Anidro Exportação',
        'preco_liquido_pvu_brl_m3': preco_liquido_pvu_brl_m3,  # C9
        'vhp_pvu_brl_saca': vhp_pvu_brl_saca,  # C10
        'vhp_pvu_cents_lb': vhp_pvu_cents_lb,  # C11
        'vhp_fob_cents_lb': vhp_fob_cents_lb  # C12
    }

def calc_paridade_hidratado_exportacao(
    preco_hidratado_fob_usd_m3,  # F3
    cambio_usd_brl,  # F4 (=C4)
    frete_porto_usina_brl_m3,  # F5 (=C5)
    terminal_brl_m3,  # F6 (=C6)
    supervisao_doc_brl_m3,  # F7 (=C7)
    custos_adicionais_demurrage_brl_m3=0,  # F8 (não usado na planilha, mas mantido)
    terminal_usd_ton=None,  # C30 (do bloco açúcar)
    frete_brl_ton=None  # C32 (do bloco açúcar)
):
    """
    BLOCO 2 — HIDRATADO EXPORTAÇÃO (colunas E/F, linhas 3–11)
    
    Calcula paridade de etanol hidratado para exportação seguindo EXATAMENTE as fórmulas da planilha Excel.
    
    Args:
        preco_hidratado_fob_usd_m3: F3 - Preço FOB USD/m³
        cambio_usd_brl: F4 (=C4) - Câmbio USD/BRL
        frete_porto_usina_brl_m3: F5 (=C5) - Frete Porto-Usina R$/m³
        terminal_brl_m3: F6 (=C6) - Terminal R$/m³
        supervisao_doc_brl_m3: F7 (=C7) - Supervisão/Doc R$/m³
        custos_adicionais_demurrage_brl_m3: Não usado na planilha original
        terminal_usd_ton: C30 - Terminal USD/ton (do bloco açúcar, para cálculo FOB)
        frete_brl_ton: C32 - Frete R$/ton (do bloco açúcar, para cálculo FOB)
    
    Returns:
        dict: Dicionário com todos os valores calculados (F8-F11)
    """
    # F8: Preço líquido PVU
    # Excel: =(F3*F4)-F5-F6-F7
    preco_liquido_pvu_brl_m3 = (preco_hidratado_fob_usd_m3 * cambio_usd_brl) - frete_porto_usina_brl_m3 - terminal_brl_m3 - supervisao_doc_brl_m3
    
    # F9: Equivalente VHP BRL/saca PVU
    # Excel: =F8/31.304
    vhp_pvu_brl_saca = preco_liquido_pvu_brl_m3 / FATOR_M3_HIDRATADO_EXPORT_PARA_SACA_VHP
    
    # F10: Equivalente Cents/lb PVU
    # Excel: =((F9*20)/22.0462)/F4/1.042
    vhp_pvu_cents_lb = ((vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl / FATOR_DESCONTO_VHP_FOB
    
    # F11: Equivalente Cents/lb FOB
    # Excel: =((((((F8)/32.669)*20)+$C$32+($C$30*$C$4))/22.0462/$C$4)/1.042)
    # Nota: Requer C30 (terminal_usd_ton) e C32 (frete_brl_ton) do bloco açúcar
    # Nota: A planilha usa 32.669 aqui, não 31.304 (parece ser um erro na planilha, mas seguimos exatamente)
    vhp_fob_cents_lb = None
    if terminal_usd_ton is not None and frete_brl_ton is not None:
        vhp_fob_cents_lb = ((((((preco_liquido_pvu_brl_m3) / 32.669) * SACAS_POR_TON) + frete_brl_ton + (terminal_usd_ton * cambio_usd_brl)) / FATOR_CWT_POR_TON / cambio_usd_brl) / FATOR_DESCONTO_VHP_FOB)
    
    return {
        'rota': 'Hidratado Exportação',
        'preco_liquido_pvu_brl_m3': preco_liquido_pvu_brl_m3,  # F8
        'vhp_pvu_brl_saca': vhp_pvu_brl_saca,  # F9
        'vhp_pvu_cents_lb': vhp_pvu_cents_lb,  # F10
        'vhp_fob_cents_lb': vhp_fob_cents_lb  # F11
    }

def calc_paridade_anidro_interno(
    preco_anidro_com_impostos_brl_m3,  # I3
    pis_cofins_brl_m3,  # I4
    contribuicao_agroindustria,  # I5 (percentual, não R$/m³)
    valor_cbio_bruto_brl,  # I7
    cambio_usd_brl,  # C4 (para cálculos de equivalentes)
    terminal_usd_ton=None,  # C30 (para cálculos FOB)
    frete_brl_ton=None,  # C32 (para cálculos FOB)
    preco_hidratado_pvu_brl_m3=None,  # L11 (para I21)
    preco_hidratado_com_impostos_brl_m3=None  # L7 (para I22)
):
    """
    BLOCO 3 — ANIDRO MERCADO INTERNO (colunas H/I, linhas 3–22 e 14–19)
    
    Calcula paridade de etanol anidro para mercado interno seguindo EXATAMENTE as fórmulas da planilha Excel.
    
    Args:
        preco_anidro_com_impostos_brl_m3: I3 - Preço com impostos R$/m³
        pis_cofins_brl_m3: I4 - PIS/COFINS R$/m³
        contribuicao_agroindustria: I5 - Contribuição Agroindústria (percentual, não R$/m³)
        valor_cbio_bruto_brl: I7 - Valor CBIO bruto R$/CBIO
        cambio_usd_brl: C4 - Câmbio USD/BRL
        terminal_usd_ton: C30 - Terminal USD/ton (do bloco açúcar, para cálculos FOB)
        frete_brl_ton: C32 - Frete R$/ton (do bloco açúcar, para cálculos FOB)
        preco_hidratado_pvu_brl_m3: L11 - Preço hidratado PVU (para I21)
        preco_hidratado_com_impostos_brl_m3: L7 - Preço hidratado com impostos (para I22)
    
    Returns:
        dict: Dicionário com todos os valores calculados (I6-I22)
    """
    # I6: Preço líquido PVU
    # Excel: =((I3*(1-I5))-I4)
    preco_liquido_pvu_brl_m3 = (preco_anidro_com_impostos_brl_m3 * (1 - contribuicao_agroindustria)) - pis_cofins_brl_m3
    
    # I8: Valor CBIO sem IR (15%) / PIS/Cof (9,25%) / 60% Usina
    # Excel: =(I7*0.7575)*0.6
    # 0.7575 = 1 - 0.15 (IR) - 0.0925 (PIS/COFINS)
    valor_cbio_liquido_por_cbio = (valor_cbio_bruto_brl * 0.7575) * 0.6
    
    # I9: Preço líquido PVU + CBIO (FC 712,40)
    # Excel: =I6+((I8/712.4)*1000)
    valor_cbio_liquido_por_m3 = (valor_cbio_liquido_por_cbio / FC_ANIDRO_LITROS_POR_CBIO) * 1000
    preco_pvu_mais_cbio_brl_m3 = preco_liquido_pvu_brl_m3 + valor_cbio_liquido_por_m3
    
    # I10: Equivalente Hidratado - 7,69% Fator Conv.
    # Excel: =I6/(1+0.0769)
    preco_hid_equivalente_brl_m3 = preco_liquido_pvu_brl_m3 / (1 + FATOR_CONV_ANIDRO_HIDRATADO)
    
    # I14: Equivalente VHP BRL/saco PVU
    # Excel: =(I9/33.712)
    vhp_pvu_brl_saca = preco_pvu_mais_cbio_brl_m3 / FATOR_M3_ANIDRO_INTERNO_PARA_SACA_VHP
    
    # I15: Equivalente VHP Cents/lb PVU
    # Excel: =(((I14*20)/22.0462)/C4)
    vhp_pvu_cents_lb = (((vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl)
    
    # I16: Equivalente VHP Cents/lb FOB
    # Excel: =(((I15*20)/22.0462)/C5)
    # Nota: Parece haver um erro na planilha (C5 não existe, provavelmente deveria ser C4)
    # Mas seguimos exatamente como especificado
    vhp_fob_cents_lb = None
    if cambio_usd_brl is not None:
        # Assumindo que C5 é um erro e deveria ser C4
        vhp_fob_cents_lb = (((vhp_pvu_cents_lb * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl)
    
    # I17: Equivalente Cristal BRL/Saca PVU
    # Excel: =(((I16*20)/22.0462)/C6)
    # Nota: Parece haver um erro na planilha (C6 não existe no contexto)
    cristal_pvu_brl_saca = None
    if vhp_fob_cents_lb is not None:
        # Assumindo conversão similar
        cristal_pvu_brl_saca = (((vhp_fob_cents_lb * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl)
    
    # I18: Equivalente Cristal Cents/lb PVU
    # Excel: =(((I17*20)/22.0462)/C7)
    cristal_pvu_cents_lb = None
    if cristal_pvu_brl_saca is not None:
        cristal_pvu_cents_lb = (((cristal_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl)
    
    # I19: Equivalente Cristal Cents/lb FOB
    # Excel: =(((I18*20)/22.0462)/C8)
    cristal_fob_cents_lb = None
    if cristal_pvu_cents_lb is not None and cambio_usd_brl is not None:
        cristal_fob_cents_lb = (((cristal_pvu_cents_lb * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl)
    
    # I21: Prêmio Anidro/Hidratado Líquido
    # Excel: =(I6/L11)-1
    premio_anidro_hidratado_liquido = None
    if preco_hidratado_pvu_brl_m3 is not None and preco_hidratado_pvu_brl_m3 != 0:
        premio_anidro_hidratado_liquido = (preco_liquido_pvu_brl_m3 / preco_hidratado_pvu_brl_m3) - 1
    
    # I22: Prêmio Anidro/Hidratado Contrato
    # Excel: =(I6/L7)-1
    premio_anidro_hidratado_contrato = None
    if preco_hidratado_com_impostos_brl_m3 is not None and preco_hidratado_com_impostos_brl_m3 != 0:
        premio_anidro_hidratado_contrato = (preco_liquido_pvu_brl_m3 / preco_hidratado_com_impostos_brl_m3) - 1
    
    return {
        'rota': 'Anidro Mercado Interno',
        'preco_liquido_pvu_brl_m3': preco_liquido_pvu_brl_m3,  # I6
        'valor_cbio_liquido_por_cbio': valor_cbio_liquido_por_cbio,  # I8
        'preco_pvu_mais_cbio_brl_m3': preco_pvu_mais_cbio_brl_m3,  # I9
        'preco_hid_equivalente_brl_m3': preco_hid_equivalente_brl_m3,  # I10
        'vhp_pvu_brl_saca': vhp_pvu_brl_saca,  # I14
        'vhp_pvu_cents_lb': vhp_pvu_cents_lb,  # I15
        'vhp_fob_cents_lb': vhp_fob_cents_lb,  # I16
        'cristal_pvu_brl_saca': cristal_pvu_brl_saca,  # I17
        'cristal_pvu_cents_lb': cristal_pvu_cents_lb,  # I18
        'cristal_fob_cents_lb': cristal_fob_cents_lb,  # I19
        'premio_anidro_hidratado_liquido': premio_anidro_hidratado_liquido,  # I21
        'premio_anidro_hidratado_contrato': premio_anidro_hidratado_contrato  # I22
    }

def calc_paridade_hidratado_interno(
    preco_hidratado_rp_com_impostos_brl_m3,  # L3
    pis_cofins_brl_m3,  # L4
    aliquota_icms,  # L5 (percentual)
    contribuicao_agroindustria,  # L6 (percentual, não R$/m³)
    valor_cbio_bruto_brl,  # L8
    cambio_usd_brl,  # C4 (para cálculos de equivalentes)
    terminal_usd_ton=None,  # C30 (para cálculos FOB)
    frete_brl_ton=None,  # C32 (para cálculos FOB)
    premio_fisico_pvu=None,  # I28 (para L18, L19)
    fobizacao_container_brl_ton=None  # L31 (para L19)
):
    """
    BLOCO 4 — HIDRATADO MERCADO INTERNO (colunas K/L, linhas 3–22 e 14–19)
    
    Calcula paridade de etanol hidratado para mercado interno seguindo EXATAMENTE as fórmulas da planilha Excel.
    
    Args:
        preco_hidratado_rp_com_impostos_brl_m3: L3 - Preço RP com impostos R$/m³
        pis_cofins_brl_m3: L4 - PIS/COFINS R$/m³
        aliquota_icms: L5 - Alíquota ICMS (percentual)
        contribuicao_agroindustria: L6 - Contribuição Agroindústria (percentual, não R$/m³)
        valor_cbio_bruto_brl: L8 - Valor CBIO bruto R$/CBIO
        cambio_usd_brl: C4 - Câmbio USD/BRL
        terminal_usd_ton: C30 - Terminal USD/ton (do bloco açúcar, para cálculos FOB)
        frete_brl_ton: C32 - Frete R$/ton (do bloco açúcar, para cálculos FOB)
        premio_fisico_pvu: I28 - Prêmio físico PVU (para L18, L19)
        fobizacao_container_brl_ton: L31 - Fobização container R$/ton (para L19)
    
    Returns:
        dict: Dicionário com todos os valores calculados (L7-L19)
    """
    # L7: Preço líquido PVU
    # Excel: =((L3*(1-L6))*(1-L5)-L4)
    preco_liquido_pvu_brl_m3 = ((preco_hidratado_rp_com_impostos_brl_m3 * (1 - contribuicao_agroindustria)) * (1 - aliquota_icms)) - pis_cofins_brl_m3
    
    # L9: Valor CBIO sem IR (15%) / PIS/Cof (9,25%) / 60% Usina
    # Excel: =(L8*0.7575)*0.6
    valor_cbio_liquido_por_cbio = (valor_cbio_bruto_brl * 0.7575) * 0.6
    
    # L10: Preço líquido PVU + CBIO (FC 749,75)
    # Excel: =L7+((L9/749.75)*1000)
    valor_cbio_liquido_por_m3 = (valor_cbio_liquido_por_cbio / FC_HIDRATADO_LITROS_POR_CBIO) * 1000
    preco_pvu_mais_cbio_brl_m3 = preco_liquido_pvu_brl_m3 + valor_cbio_liquido_por_m3
    
    # L11: Equivalente Anidro - 7,69% Fator Conv.
    # Excel: =L7*(1+0.0769)
    preco_anidro_equivalente_brl_m3 = preco_liquido_pvu_brl_m3 * (1 + FATOR_CONV_ANIDRO_HIDRATADO)
    
    # L12: Preço Liquido PVU + CBIO + Credito Trib. (0,24)
    # Excel: =L10+240
    credito_tributario_brl_m3 = 240  # 0.24 R$/L * 1000 L/m³
    preco_pvu_cbio_credito_brl_m3 = preco_pvu_mais_cbio_brl_m3 + credito_tributario_brl_m3
    
    # L14: Equivalente VHP BRL/saco PVU
    # Excel: =(L10/31.504)
    vhp_pvu_brl_saca = preco_pvu_mais_cbio_brl_m3 / FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP
    
    # L15: Equivalente VHP Cents/lb PVU
    # Excel: =(((L14*20)/22.0462)/$F$4)
    # Nota: $F$4 = C4 (câmbio)
    vhp_pvu_cents_lb = (((vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl)
    
    # L16: Equivalente VHP Cents/lb FOB
    # Excel: =((((((L10)/31.504)*20)+$C$32+($C$30*$C$4))/22.0462/$C$4)/1.042)
    vhp_fob_cents_lb = None
    if terminal_usd_ton is not None and frete_brl_ton is not None:
        vhp_fob_cents_lb = ((((((preco_pvu_mais_cbio_brl_m3) / FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP) * SACAS_POR_TON) + frete_brl_ton + (terminal_usd_ton * cambio_usd_brl)) / FATOR_CWT_POR_TON / cambio_usd_brl) / FATOR_DESCONTO_VHP_FOB)
    
    # L17: Equivalente Cristal BRL/Saca PVU
    # Excel: =(L18*22.0462/20)*$C$4
    # Nota: L18 é calculado primeiro, então precisamos calcular L18 antes
    cristal_pvu_brl_saca = None
    
    # L18: Equivalente Cristal Cents/lb PVU
    # Excel: =((((((L10)/31.504)*20)+($I$28*$C$4))/22.0462/$C$4))
    cristal_pvu_cents_lb = None
    if premio_fisico_pvu is not None:
        cristal_pvu_cents_lb = ((((((preco_pvu_mais_cbio_brl_m3) / FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP) * SACAS_POR_TON) + (premio_fisico_pvu * cambio_usd_brl)) / FATOR_CWT_POR_TON / cambio_usd_brl))
        # Agora calculamos L17 usando L18
        cristal_pvu_brl_saca = (cristal_pvu_cents_lb * FATOR_CWT_POR_TON / SACAS_POR_TON) * cambio_usd_brl
    
    # L19: Equivalente Cristal Cents/lb FOB
    # Excel: =(((((((L10)/31.504)*20)+$C$32+L31)+($I$28*$C$4))/22.0462/$C$4))
    cristal_fob_cents_lb = None
    if frete_brl_ton is not None and fobizacao_container_brl_ton is not None and premio_fisico_pvu is not None:
        cristal_fob_cents_lb = (((((((preco_pvu_mais_cbio_brl_m3) / FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP) * SACAS_POR_TON) + frete_brl_ton + fobizacao_container_brl_ton) + (premio_fisico_pvu * cambio_usd_brl)) / FATOR_CWT_POR_TON / cambio_usd_brl)
    
    return {
        'rota': 'Hidratado Mercado Interno',
        'preco_liquido_pvu_brl_m3': preco_liquido_pvu_brl_m3,  # L7
        'valor_cbio_liquido_por_cbio': valor_cbio_liquido_por_cbio,  # L9
        'preco_pvu_mais_cbio_brl_m3': preco_pvu_mais_cbio_brl_m3,  # L10
        'preco_anidro_equivalente_brl_m3': preco_anidro_equivalente_brl_m3,  # L11
        'credito_tributario_brl_m3': credito_tributario_brl_m3,  # 240
        'preco_pvu_cbio_credito_brl_m3': preco_pvu_cbio_credito_brl_m3,  # L12
        'vhp_pvu_brl_saca': vhp_pvu_brl_saca,  # L14
        'vhp_pvu_cents_lb': vhp_pvu_cents_lb,  # L15
        'vhp_fob_cents_lb': vhp_fob_cents_lb,  # L16
        'cristal_pvu_brl_saca': cristal_pvu_brl_saca,  # L17
        'cristal_pvu_cents_lb': cristal_pvu_cents_lb,  # L18
        'cristal_fob_cents_lb': cristal_fob_cents_lb  # L19
    }

def calc_paridade_acucar(
    sugar_ny_fob_cents_lb,  # C26
    premio_desconto_cents_lb,  # C27
    premio_pol,  # C28 (percentual, não dividido por 100)
    cambio_usd_brl,  # C31 (=C4)
    terminal_usd_ton,  # C30
    frete_brl_ton,  # C32
    esalq_brl_saca=None,  # F26
    impostos_esalq=None,  # F27
    premio_fisico_pvu=None,  # I28
    premio_fisico_fob=None,  # L28
    premio_fisico_malha30=None,  # O28
    fobizacao_container_brl_ton=None,  # L31
    frete_export_brl_ton=None,  # L32
    custo_cristal_vs_vhp=0.0  # Custo Cristal vs VHP (referencia Excel D17)
):
    """
    BLOCO 5 — PARIDADE AÇÚCAR (5 sub-blocos)
    
    Calcula paridade de açúcar seguindo EXATAMENTE as fórmulas da planilha Excel.
    
    Args:
        sugar_ny_fob_cents_lb: C26 - NY11 FOB cents/lb
        premio_desconto_cents_lb: C27 - Prêmio/desconto cents/lb
        premio_pol: C28 - Prêmio POL (percentual, ex: 0.042 = 4.2%)
        cambio_usd_brl: C31 (=C4) - Câmbio USD/BRL
        terminal_usd_ton: C30 - Terminal USD/ton
        frete_brl_ton: C32 - Frete R$/ton
        esalq_brl_saca: F26 - Preço Esalq R$/saca
        impostos_esalq: F27 - Impostos Esalq (percentual)
        premio_fisico_pvu: I28 - Prêmio físico PVU (para Merc. Interno)
        premio_fisico_fob: L28 - Prêmio físico FOB (para Exportação)
        premio_fisico_malha30: O28 - Prêmio físico Malha 30
        fobizacao_container_brl_ton: L31 - Fobização container R$/ton
        frete_export_brl_ton: L32 - Frete exportação R$/ton
        custo_cristal_vs_vhp: Custo diferencial Cristal vs VHP
    
    Returns:
        dict: Dicionário com todos os valores calculados dos 5 sub-blocos
    """
    # ===== SUB-BLOCO 5.1 — SUGAR VHP (B/C, linhas 26–35) =====
    # C29: Sugar NY + POL
    # Excel: =(C26+C27)*(1+C28)
    sugar_ny_pol_cents_lb = (sugar_ny_fob_cents_lb + premio_desconto_cents_lb) * (1 + premio_pol)
    
    # C33: Equivalente VHP BRL/saca PVU
    # Excel: =(((C29*22.0462)-C30-(C32/C31))/20)*C31
    sugar_vhp_pvu_brl_saca = (((sugar_ny_pol_cents_lb * FATOR_CWT_POR_TON) - terminal_usd_ton - (frete_brl_ton / cambio_usd_brl)) / SACAS_POR_TON) * cambio_usd_brl
    
    # C34: Equivalente VHP Cents/lb PVU
    # Excel: =((C33*20)/22.0462)/C31
    sugar_vhp_pvu_cents_lb = ((sugar_vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl
    
    # C35: Equivalente VHP Cents/lb FOB
    # Excel: =C29
    sugar_vhp_fob_cents_lb = sugar_ny_pol_cents_lb
    
    # ===== SUB-BLOCO 5.2 — CRISTAL ESALQ (E/F, linhas 26–38) =====
    sugar_esalq_vhp_pvu_brl_saca = None
    sugar_esalq_vhp_pvu_cents_lb = None
    sugar_esalq_vhp_fob_cents_lb = None
    sugar_esalq_cristal_pvu_brl_saca = None
    sugar_esalq_cristal_pvu_cents_lb = None
    sugar_esalq_cristal_fob_cents_lb = None
    
    if esalq_brl_saca is not None and impostos_esalq is not None:
        # F36: Equivalente Cristal BRL/Saca PVU
        # Excel: =(F26*(1-F27))
        sugar_esalq_cristal_pvu_brl_saca = esalq_brl_saca * (1 - impostos_esalq)
        
        # F33: Equivalente VHP BRL/saco PVU
        # Excel: =F36-'Custo Cristal vs VHP'!$D$17
        sugar_esalq_vhp_pvu_brl_saca = sugar_esalq_cristal_pvu_brl_saca - custo_cristal_vs_vhp
        
        # F34: Equivalente VHP Cents/lb PVU
        # Excel: =(((F33*20)/22.0462)/$C$4)
        sugar_esalq_vhp_pvu_cents_lb = (((sugar_esalq_vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl)
        
        # F35: Equivalente VHP Cents/lb FOB
        # Excel: =((((((F33)*20)+$L$32+(C30*C4))/22.0462/$C$4)))
        if frete_export_brl_ton is not None:
            sugar_esalq_vhp_fob_cents_lb = ((((((sugar_esalq_vhp_pvu_brl_saca) * SACAS_POR_TON) + frete_export_brl_ton + (terminal_usd_ton * cambio_usd_brl)) / FATOR_CWT_POR_TON / cambio_usd_brl))
        
        # F37: Equivalente Cristal Cents/lb PVU
        # Excel: =(((F36*20)/22.0462)/C4)-(15/22.0462/C4)
        sugar_esalq_cristal_pvu_cents_lb = (((sugar_esalq_cristal_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl) - (15 / FATOR_CWT_POR_TON / cambio_usd_brl)
        
        # F38: Equivalente Cristal Cents/lb FOB
        # Excel: =(((F36*20)+F28+F29)/22.04622)/C4
        # F28 = L32, F29 = L31
        if frete_export_brl_ton is not None and fobizacao_container_brl_ton is not None:
            sugar_esalq_cristal_fob_cents_lb = (((sugar_esalq_cristal_pvu_brl_saca * SACAS_POR_TON) + frete_export_brl_ton + fobizacao_container_brl_ton) / 22.04622) / cambio_usd_brl
    
    # ===== SUB-BLOCO 5.3 — CRISTAL MERCADO INTERNO / PVU (H/I, linhas 26–41) =====
    sugar_interno_cristal_pvu_brl_saca = None
    sugar_interno_vhp_pvu_brl_saca = None
    sugar_interno_vhp_pvu_cents_lb = None
    sugar_interno_vhp_fob_cents_lb = None
    sugar_interno_cristal_pvu_cents_lb = None
    sugar_interno_cristal_fob_cents_lb = None
    sugar_interno_esalq_com_impostos = None
    
    if premio_fisico_pvu is not None:
        # I26: =C26
        # I27: =I26*22.04622
        sugar_ny_usd_ton = sugar_ny_fob_cents_lb * 22.04622
        
        # I29: Sugar PVU USD/ton
        # Excel: =I27+I28
        sugar_pvu_usd_ton = sugar_ny_usd_ton + premio_fisico_pvu
        
        # I30: Sugar PVU R$/ton
        # Excel: =I29*C4
        sugar_pvu_brl_ton = sugar_pvu_usd_ton * cambio_usd_brl
        
        # I36: Equivalente Cristal BRL/Saca PVU
        # Excel: =(I30)/20
        sugar_interno_cristal_pvu_brl_saca = sugar_pvu_brl_ton / SACAS_POR_TON
        
        # I33: Equivalente VHP BRL/saco PVU
        # Excel: =I36-'Custo Cristal vs VHP'!$D$17
        sugar_interno_vhp_pvu_brl_saca = sugar_interno_cristal_pvu_brl_saca - custo_cristal_vs_vhp
        
        # I34: Equivalente VHP Cents/lb PVU
        # Excel: =(((I33*20)/22.0462)/$C$4)
        sugar_interno_vhp_pvu_cents_lb = (((sugar_interno_vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl)
        
        # I35: Equivalente VHP Cents/lb FOB
        # Excel: =((((((I33)*20)+$L$32+($C$30*$C$4))/22.0462/$C$4)))
        if frete_export_brl_ton is not None:
            sugar_interno_vhp_fob_cents_lb = ((((((sugar_interno_vhp_pvu_brl_saca) * SACAS_POR_TON) + frete_export_brl_ton + (terminal_usd_ton * cambio_usd_brl)) / FATOR_CWT_POR_TON / cambio_usd_brl))
        
        # I37: Equivalente Cristal Cents/lb PVU
        # Excel: =((I36*20)/22.0462)/C4
        sugar_interno_cristal_pvu_cents_lb = ((sugar_interno_cristal_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl
        
        # I38: Equivalente Cristal Cents/lb FOB
        # Excel: =((I30+L31+L32)/22.0462)/C4
        if fobizacao_container_brl_ton is not None and frete_export_brl_ton is not None:
            sugar_interno_cristal_fob_cents_lb = ((sugar_pvu_brl_ton + fobizacao_container_brl_ton + frete_export_brl_ton) / FATOR_CWT_POR_TON) / cambio_usd_brl
        
        # I41: Equivalente Esalq com Impostos
        # Excel: =I36/0.9015
        sugar_interno_esalq_com_impostos = sugar_interno_cristal_pvu_brl_saca / FATOR_ESALQ_SEM_IMPOSTOS
    
    # ===== SUB-BLOCO 5.4 — CRISTAL EXPORTAÇÃO (K/L, linhas 26–41) =====
    sugar_export_cristal_pvu_brl_saca = None
    sugar_export_vhp_pvu_brl_saca = None
    sugar_export_vhp_pvu_cents_lb = None
    sugar_export_vhp_fob_cents_lb = None
    sugar_export_cristal_pvu_cents_lb = None
    sugar_export_cristal_fob_cents_lb = None
    sugar_export_esalq_com_impostos = None
    
    if premio_fisico_fob is not None and fobizacao_container_brl_ton is not None and frete_export_brl_ton is not None:
        # L26: =C26
        # L27: =L26*22.04622
        sugar_ny_usd_ton_export = sugar_ny_fob_cents_lb * 22.04622
        
        # L29: Sugar FOB USD/ton
        # Excel: =L27+L28
        sugar_fob_usd_ton_export = sugar_ny_usd_ton_export + premio_fisico_fob
        
        # L30: Sugar FOB R$/ton
        # Excel: =L29*C4
        sugar_fob_brl_ton_export = sugar_fob_usd_ton_export * cambio_usd_brl
        
        # L36: Equivalente Cristal BRL/Saca PVU
        # Excel: =(L30-L31-L32)/20
        sugar_export_cristal_pvu_brl_saca = (sugar_fob_brl_ton_export - fobizacao_container_brl_ton - frete_export_brl_ton) / SACAS_POR_TON
        
        # L33: Equivalente VHP BRL/saco PVU
        # Excel: =L36-'Custo Cristal vs VHP'!$D$17
        sugar_export_vhp_pvu_brl_saca = sugar_export_cristal_pvu_brl_saca - custo_cristal_vs_vhp
        
        # L34: Equivalente VHP Cents/lb PVU
        # Excel: =(((L33*20)/22,0462)/$C$4)
        sugar_export_vhp_pvu_cents_lb = (((sugar_export_vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl)
        
        # L35: Equivalente VHP Cents/lb FOB
        # Excel: =((((((L33)*20)+$L$32+(C30*C4))/22.0462/$C$4)))
        sugar_export_vhp_fob_cents_lb = ((((((sugar_export_vhp_pvu_brl_saca) * SACAS_POR_TON) + frete_export_brl_ton + (terminal_usd_ton * cambio_usd_brl)) / FATOR_CWT_POR_TON / cambio_usd_brl))
        
        # L37: Equivalente Cristal Cents/lb PVU
        # Excel: =((L36*20)/22.0462)/C4
        sugar_export_cristal_pvu_cents_lb = ((sugar_export_cristal_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl
        
        # L38: Equivalente Cristal Cents/lb FOB
        # Excel: =L29/22.04622
        sugar_export_cristal_fob_cents_lb = sugar_fob_usd_ton_export / 22.04622
        
        # L41: Equivalente Esalq com Impostos
        # Excel: =L36/0,9015
        sugar_export_esalq_com_impostos = sugar_export_cristal_pvu_brl_saca / FATOR_ESALQ_SEM_IMPOSTOS
    
    # ===== SUB-BLOCO 5.5 — CRISTAL EXPORTAÇÃO MALHA 30 (N/O, linhas 26–41) =====
    sugar_malha30_cristal_pvu_brl_saca = None
    sugar_malha30_vhp_pvu_brl_saca = None
    sugar_malha30_vhp_pvu_cents_lb = None
    sugar_malha30_vhp_fob_cents_lb = None
    sugar_malha30_cristal_pvu_cents_lb = None
    sugar_malha30_cristal_fob_cents_lb = None
    sugar_malha30_esalq_com_impostos = None
    
    if premio_fisico_malha30 is not None and fobizacao_container_brl_ton is not None and frete_export_brl_ton is not None:
        # O26: =C26
        # O27: =O26*22.04622
        sugar_ny_usd_ton_malha30 = sugar_ny_fob_cents_lb * 22.04622
        
        # O29: Sugar FOB USD/ton
        # Excel: =O27+O28
        sugar_fob_usd_ton_malha30 = sugar_ny_usd_ton_malha30 + premio_fisico_malha30
        
        # O30: Sugar FOB R$/ton
        # Excel: =O29*C4
        sugar_fob_brl_ton_malha30 = sugar_fob_usd_ton_malha30 * cambio_usd_brl
        
        # O36: Equivalente Cristal BRL/Saca PVU
        # Excel: =(O30-O31-O32)/20
        sugar_malha30_cristal_pvu_brl_saca = (sugar_fob_brl_ton_malha30 - fobizacao_container_brl_ton - frete_export_brl_ton) / SACAS_POR_TON
        
        # O33: Equivalente VHP BRL/saco PVU
        # Excel: =O36-'Custo Cristal vs VHP'!$D$17
        sugar_malha30_vhp_pvu_brl_saca = sugar_malha30_cristal_pvu_brl_saca - custo_cristal_vs_vhp
        
        # O34: Equivalente VHP Cents/lb PVU
        # Excel: =(((O33*20)/22.0462)/$C$4)
        sugar_malha30_vhp_pvu_cents_lb = (((sugar_malha30_vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl)
        
        # O35: Equivalente VHP Cents/lb FOB
        # Excel: =((((((O33)*20)+$L$32+(C30*C4))/22.0462/$C$4)))
        sugar_malha30_vhp_fob_cents_lb = ((((((sugar_malha30_vhp_pvu_brl_saca) * SACAS_POR_TON) + frete_export_brl_ton + (terminal_usd_ton * cambio_usd_brl)) / FATOR_CWT_POR_TON / cambio_usd_brl))
        
        # O37: Equivalente Cristal Cents/lb PVU
        # Excel: =((O36*20)/22.0462)/C4
        sugar_malha30_cristal_pvu_cents_lb = ((sugar_malha30_cristal_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_usd_brl
        
        # O38: Equivalente Cristal Cents/lb FOB
        # Excel: =O29/22.04622
        sugar_malha30_cristal_fob_cents_lb = sugar_fob_usd_ton_malha30 / 22.04622
        
        # O41: Equivalente Esalq com Impostos
        # Excel: =O36/0,9015
        sugar_malha30_esalq_com_impostos = sugar_malha30_cristal_pvu_brl_saca / FATOR_ESALQ_SEM_IMPOSTOS
    
    return {
        # SUB-BLOCO 5.1 — VHP
        'sugar_vhp_pvu_brl_saca': sugar_vhp_pvu_brl_saca,
        'sugar_vhp_pvu_cents_lb': sugar_vhp_pvu_cents_lb,
        'sugar_vhp_fob_cents_lb': sugar_vhp_fob_cents_lb,
        # SUB-BLOCO 5.2 — ESALQ
        'sugar_esalq_vhp_pvu_brl_saca': sugar_esalq_vhp_pvu_brl_saca,
        'sugar_esalq_vhp_pvu_cents_lb': sugar_esalq_vhp_pvu_cents_lb,
        'sugar_esalq_vhp_fob_cents_lb': sugar_esalq_vhp_fob_cents_lb,
        'sugar_esalq_cristal_pvu_brl_saca': sugar_esalq_cristal_pvu_brl_saca,
        'sugar_esalq_cristal_pvu_cents_lb': sugar_esalq_cristal_pvu_cents_lb,
        'sugar_esalq_cristal_fob_cents_lb': sugar_esalq_cristal_fob_cents_lb,
        # SUB-BLOCO 5.3 — MERCADO INTERNO
        'sugar_interno_cristal_pvu_brl_saca': sugar_interno_cristal_pvu_brl_saca,
        'sugar_interno_vhp_pvu_brl_saca': sugar_interno_vhp_pvu_brl_saca,
        'sugar_interno_vhp_pvu_cents_lb': sugar_interno_vhp_pvu_cents_lb,
        'sugar_interno_vhp_fob_cents_lb': sugar_interno_vhp_fob_cents_lb,
        'sugar_interno_cristal_pvu_cents_lb': sugar_interno_cristal_pvu_cents_lb,
        'sugar_interno_cristal_fob_cents_lb': sugar_interno_cristal_fob_cents_lb,
        'sugar_interno_esalq_com_impostos': sugar_interno_esalq_com_impostos,
        # SUB-BLOCO 5.4 — EXPORTAÇÃO
        'sugar_export_cristal_pvu_brl_saca': sugar_export_cristal_pvu_brl_saca,
        'sugar_export_vhp_pvu_brl_saca': sugar_export_vhp_pvu_brl_saca,
        'sugar_export_vhp_pvu_cents_lb': sugar_export_vhp_pvu_cents_lb,
        'sugar_export_vhp_fob_cents_lb': sugar_export_vhp_fob_cents_lb,
        'sugar_export_cristal_pvu_cents_lb': sugar_export_cristal_pvu_cents_lb,
        'sugar_export_cristal_fob_cents_lb': sugar_export_cristal_fob_cents_lb,
        'sugar_export_esalq_com_impostos': sugar_export_esalq_com_impostos,
        # SUB-BLOCO 5.5 — MALHA 30
        'sugar_malha30_cristal_pvu_brl_saca': sugar_malha30_cristal_pvu_brl_saca,
        'sugar_malha30_vhp_pvu_brl_saca': sugar_malha30_vhp_pvu_brl_saca,
        'sugar_malha30_vhp_pvu_cents_lb': sugar_malha30_vhp_pvu_cents_lb,
        'sugar_malha30_vhp_fob_cents_lb': sugar_malha30_vhp_fob_cents_lb,
        'sugar_malha30_cristal_pvu_cents_lb': sugar_malha30_cristal_pvu_cents_lb,
        'sugar_malha30_cristal_fob_cents_lb': sugar_malha30_cristal_fob_cents_lb,
        'sugar_malha30_esalq_com_impostos': sugar_malha30_esalq_com_impostos
    }

# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

# Nota: st.set_page_config não pode ser usado em páginas (arquivos em pages/)
# A configuração da página é feita no arquivo principal

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
    contribuicao_agroindustria_anidro = st.number_input(
        "Contribuição Agroindústria Anidro (%)",
        value=0.0,
        step=0.1,
        format="%.2f",
        key="contrib_anidro",
        help="Contribuição para agroindústria em percentual (geralmente 0%)"
    ) / 100

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
    contribuicao_agroindustria_hidratado = st.number_input(
        "Contribuição Agroindústria Hidratado (%)",
        value=0.0,
        step=0.1,
        format="%.2f",
        key="contrib_hidratado",
        help="Contribuição para agroindústria em percentual (geralmente 0%)"
    ) / 100

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
    custos_adicionais_demurrage_brl_m3_anidro,
    terminal_usd_ton=terminal_usd_ton,
    frete_brl_ton=frete_export_sugar_brl_ton
)

paridade_hidratado_exp = calc_paridade_hidratado_exportacao(
    preco_hidratado_fob_usd_m3,
    cambio_usd_brl,
    frete_porto_usina_brl_m3_hidratado,
    terminal_brl_m3_hidratado,
    supervisao_doc_brl_m3_hidratado,
    custos_adicionais_demurrage_brl_m3_hidratado,
    terminal_usd_ton=terminal_usd_ton,
    frete_brl_ton=frete_export_sugar_brl_ton
)

# Calcula paridade anidro interno
preco_hidratado_com_impostos_para_anidro = preco_hidratado_interno_com_impostos_brl_m3
paridade_anidro_int = calc_paridade_anidro_interno(
    preco_anidro_interno_com_impostos_brl_m3,
    pis_cofins_anidro_brl_m3,
    contribuicao_agroindustria_anidro,
    preco_cbio_bruto_brl,
    cambio_usd_brl,
    terminal_usd_ton=terminal_usd_ton,
    frete_brl_ton=frete_export_sugar_brl_ton,
    preco_hidratado_pvu_brl_m3=None,
    preco_hidratado_com_impostos_brl_m3=preco_hidratado_com_impostos_para_anidro
)

paridade_hidratado_int = calc_paridade_hidratado_interno(
    preco_hidratado_interno_com_impostos_brl_m3,  # L3
    pis_cofins_hidratado_brl_m3,  # L4
    aliquota_icms_hidratado,  # L5
    contribuicao_agroindustria_hidratado,  # L6 - Agora é percentual, não R$/m³
    preco_cbio_bruto_brl,  # L8
    cambio_usd_brl,  # C4
    terminal_usd_ton=terminal_usd_ton,  # C30
    frete_brl_ton=frete_export_sugar_brl_ton,  # C32
    premio_fisico_pvu=None,  # I28 - será input do usuário
    fobizacao_container_brl_ton=fobizacao_container_brl_ton  # L31
)

# Atualiza prêmios anidro/hidratado se hidratado já foi calculado
if paridade_hidratado_int.get('preco_liquido_pvu_brl_m3') is not None and paridade_hidratado_int.get('preco_liquido_pvu_brl_m3') != 0:
    paridade_anidro_int['premio_anidro_hidratado_liquido'] = (
        (paridade_anidro_int['preco_liquido_pvu_brl_m3'] / paridade_hidratado_int['preco_liquido_pvu_brl_m3']) - 1
    )
if preco_hidratado_interno_com_impostos_brl_m3 != 0:
    paridade_anidro_int['premio_anidro_hidratado_contrato'] = (
        (paridade_anidro_int['preco_liquido_pvu_brl_m3'] / preco_hidratado_interno_com_impostos_brl_m3) - 1
    )

paridade_acucar = calc_paridade_acucar(
    ny_sugar_fob_cents_lb,
    premio_desconto_cents_lb,
    premio_pol_percent / 100,  # Converter percentual para decimal
    cambio_usd_brl,
    terminal_usd_ton,
    frete_export_sugar_brl_ton,
    esalq_brl_saca=preco_sugar_cristal_esalq_brl_saca,
    impostos_esalq=IMPOSTOS_ESALQ,
    premio_fisico_pvu=None,  # I28 - será input do usuário
    premio_fisico_fob=premio_fisico_usd_ton_cristal,
    premio_fisico_malha30=premio_fisico_usd_ton_malha30,
    fobizacao_container_brl_ton=fobizacao_container_brl_ton,
    frete_export_brl_ton=frete_export_sugar_brl_ton,
    custo_cristal_vs_vhp=CUSTO_CRISTAL_VS_VHP_D17
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
if paridade_acucar.get('sugar_export_cristal_pvu_brl_saca') is not None:
    vhp_saca_export = paridade_acucar.get('sugar_export_vhp_pvu_brl_saca')
    if vhp_saca_export is None:
        vhp_saca_export = paridade_acucar.get('sugar_export_cristal_pvu_brl_saca')
    vhp_cents_export = paridade_acucar.get('sugar_export_vhp_pvu_cents_lb')
    if vhp_cents_export is None:
        vhp_cents_export = paridade_acucar.get('sugar_export_cristal_pvu_cents_lb')
    if vhp_saca_export is not None and vhp_cents_export is not None:
        dados_decisao.append({
            'Rota': '🍬 Açúcar Cristal Exportação',
            'VHP PVU (R$/saca)': vhp_saca_export,
            'VHP PVU (cents/lb)': vhp_cents_export,
            'PVU (R$/m³)': None,
            'Tipo': 'Açúcar'
        })

if paridade_acucar.get('sugar_malha30_cristal_pvu_brl_saca') is not None:
    vhp_saca_malha30 = paridade_acucar.get('sugar_malha30_vhp_pvu_brl_saca')
    if vhp_saca_malha30 is None:
        vhp_saca_malha30 = paridade_acucar.get('sugar_malha30_cristal_pvu_brl_saca')
    vhp_cents_malha30 = paridade_acucar.get('sugar_malha30_vhp_pvu_cents_lb')
    if vhp_cents_malha30 is None:
        vhp_cents_malha30 = paridade_acucar.get('sugar_malha30_cristal_pvu_cents_lb')
    if vhp_saca_malha30 is not None and vhp_cents_malha30 is not None:
        dados_decisao.append({
            'Rota': '🍬 Açúcar Cristal Exportação Malha 30',
            'VHP PVU (R$/saca)': vhp_saca_malha30,
            'VHP PVU (cents/lb)': vhp_cents_malha30,
            'PVU (R$/m³)': None,
            'Tipo': 'Açúcar'
        })

# SUGAR Cristal Esalq (preço direto do mercado interno)
if preco_sugar_cristal_esalq_brl_saca is not None and preco_sugar_cristal_esalq_brl_saca > 0:
    dados_decisao.append({
        'Rota': '🍬 SUGAR Cristal Esalq',
        'VHP PVU (R$/saca)': preco_sugar_cristal_esalq_brl_saca,
        'VHP PVU (cents/lb)': converter_usd_ton_para_cents_lb(
            converter_brl_saca_para_usd_ton(preco_sugar_cristal_esalq_brl_saca, cambio_usd_brl)
        ),
        'PVU (R$/m³)': None,
        'Tipo': 'Açúcar'
    })

# Cristal Exportação Malha 30 (preço direto do mercado)
if preco_sugar_cristal_export_malha30_brl_saca is not None and preco_sugar_cristal_export_malha30_brl_saca > 0:
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

# Extrai valores da melhor rota para evitar problemas com $ em f-strings
vhp_saca_melhor = melhor_rota['VHP PVU (R$/saca)']
vhp_cents_melhor = melhor_rota['VHP PVU (cents/lb)']
pvu_melhor = melhor_rota.get('PVU (R$/m³)')

# Resumo visual das top 3 rotas
st.markdown("### 🏆 Top 3 Rotas Mais Atrativas")

top3 = df_decisao.head(3)
cols_top3 = st.columns(3)

for i, (idx, row) in enumerate(top3.iterrows()):
    with cols_top3[i]:
        vhp_saca_row = row['VHP PVU (R$/saca)']
        vhp_cents_row = row['VHP PVU (cents/lb)']
        if i == 0:
            st.success(f"""
            **🥇 {row['Rota']}**
            
            **💰 R$ {vhp_saca_row:,.2f}/saca**
            
            **💵 {vhp_cents_row:,.2f} cents/lb**
            """)
        elif i == 1:
            diff_1 = vhp_saca_row - melhor_rota['VHP PVU (R$/saca)']
            st.info(f"""
            **🥈 {row['Rota']}**
            
            **💰 R$ {vhp_saca_row:,.2f}/saca**
            
            **💵 {vhp_cents_row:,.2f} cents/lb**
            
            Diferença: R$ {diff_1:+,.2f}/saca
            """)
        else:
            diff_2 = vhp_saca_row - melhor_rota['VHP PVU (R$/saca)']
            st.warning(f"""
            **🥉 {row['Rota']}**
            
            **💰 R$ {vhp_saca_row:,.2f}/saca**
            
            **💵 {vhp_cents_row:,.2f} cents/lb**
            
            Diferença: R$ {diff_2:+,.2f}/saca
            """)

st.divider()

# Cards destacando a melhor rota com destaque visual
st.markdown("### ✅ **MELHOR OPÇÃO PARA PRODUZIR**")

# Container destacado para a melhor rota
st.success(f"""
**🎯 {melhor_rota['Rota']}**

**💰 VHP PVU: R$ {vhp_saca_melhor:,.2f}/saca** | **💵 {vhp_cents_melhor:,.2f} cents/lb**

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
        f"R$ {vhp_saca_melhor:,.2f}",
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
    pvu_melhor = melhor_rota.get('PVU (R$/m³)')
    if pvu_melhor is not None:
        st.metric(
            "🏭 PVU (R$/m³)",
            f"R$ {pvu_melhor:,.2f}",
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
    lambda x: x - vhp_saca_melhor
)
df_display_decisao['Diferença Percentual'] = df_decisao['VHP PVU (R$/saca)'].apply(
    lambda x: ((x - vhp_saca_melhor) / vhp_saca_melhor) * 100
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
    preco_pvu_anidro_exp = paridade_anidro_exp['preco_liquido_pvu_brl_m3']
    vhp_saca_anidro_exp = paridade_anidro_exp['vhp_pvu_brl_saca']
    st.metric("Preço Líquido PVU", f"R$ {preco_pvu_anidro_exp:,.2f}/m³")
    st.metric("VHP PVU (R$/saca)", f"R$ {vhp_saca_anidro_exp:,.2f}/saca")
    st.metric("VHP PVU (cents/lb)", f"{paridade_anidro_exp['vhp_pvu_cents_lb']:,.2f} cents/lb")
    if paridade_anidro_exp.get('vhp_fob_cents_lb') is not None:
        st.metric("VHP FOB (cents/lb)", f"{paridade_anidro_exp['vhp_fob_cents_lb']:,.2f} cents/lb")

with tabs[1]:
    st.markdown("### Hidratado Exportação")
    preco_pvu_hidratado_exp = paridade_hidratado_exp['preco_liquido_pvu_brl_m3']
    vhp_saca_hidratado_exp = paridade_hidratado_exp['vhp_pvu_brl_saca']
    st.metric("Preço Líquido PVU", f"R$ {preco_pvu_hidratado_exp:,.2f}/m³")
    st.metric("VHP PVU (R$/saca)", f"R$ {vhp_saca_hidratado_exp:,.2f}/saca")
    st.metric("VHP PVU (cents/lb)", f"{paridade_hidratado_exp['vhp_pvu_cents_lb']:,.2f} cents/lb")
    if paridade_hidratado_exp.get('vhp_fob_cents_lb') is not None:
        st.metric("VHP FOB (cents/lb)", f"{paridade_hidratado_exp['vhp_fob_cents_lb']:,.2f} cents/lb")

with tabs[2]:
    st.markdown("### Anidro Mercado Interno")
    preco_pvu_anidro_int = paridade_anidro_int['preco_liquido_pvu_brl_m3']
    st.metric("Preço Líquido PVU", f"R$ {preco_pvu_anidro_int:,.2f}/m³")
    # Calcula valor_cbio_liquido_por_m3 a partir do valor_cbio_liquido_por_cbio
    valor_cbio_liquido_por_m3_anidro = (paridade_anidro_int.get('valor_cbio_liquido_por_cbio', 0) / FC_ANIDRO_LITROS_POR_CBIO) * 1000
    st.metric("CBIO Líquido", f"R$ {valor_cbio_liquido_por_m3_anidro:,.2f}/m³")
    preco_pvu_cbio_anidro = paridade_anidro_int['preco_pvu_mais_cbio_brl_m3']
    preco_hid_equiv_anidro = paridade_anidro_int['preco_hid_equivalente_brl_m3']
    vhp_saca_anidro_int = paridade_anidro_int['vhp_pvu_brl_saca']
    st.metric("Preço PVU + CBIO", f"R$ {preco_pvu_cbio_anidro:,.2f}/m³")
    st.metric("Equivalente Hidratado", f"R$ {preco_hid_equiv_anidro:,.2f}/m³")
    st.metric("VHP PVU (R$/saca)", f"R$ {vhp_saca_anidro_int:,.2f}/saca")
    st.metric("VHP PVU (cents/lb)", f"{paridade_anidro_int['vhp_pvu_cents_lb']:,.2f} cents/lb")
    if paridade_anidro_int.get('vhp_fob_cents_lb') is not None:
        st.metric("VHP FOB (cents/lb)", f"{paridade_anidro_int['vhp_fob_cents_lb']:,.2f} cents/lb")
    if paridade_anidro_int.get('premio_anidro_hidratado_liquido') is not None:
        st.metric("Prêmio Anidro/Hidratado Líquido", f"{paridade_anidro_int['premio_anidro_hidratado_liquido']*100:,.2f}%")
    if paridade_anidro_int.get('premio_anidro_hidratado_contrato') is not None:
        st.metric("Prêmio Anidro/Hidratado Contrato", f"{paridade_anidro_int['premio_anidro_hidratado_contrato']*100:,.2f}%")

with tabs[3]:
    st.markdown("### Hidratado Mercado Interno")
    preco_pvu_hidratado_int = paridade_hidratado_int['preco_liquido_pvu_brl_m3']
    st.metric("Preço Líquido PVU", f"R$ {preco_pvu_hidratado_int:,.2f}/m³")
    # Calcula valor_cbio_liquido_por_m3 a partir do valor_cbio_liquido_por_cbio
    valor_cbio_liquido_por_m3_hidratado = (paridade_hidratado_int.get('valor_cbio_liquido_por_cbio', 0) / FC_HIDRATADO_LITROS_POR_CBIO) * 1000
    st.metric("CBIO Líquido", f"R$ {valor_cbio_liquido_por_m3_hidratado:,.2f}/m³")
    preco_pvu_cbio_hidratado = paridade_hidratado_int['preco_pvu_mais_cbio_brl_m3']
    credito_trib_hidratado = paridade_hidratado_int['credito_tributario_brl_m3']
    preco_pvu_cbio_credito_hidratado = paridade_hidratado_int['preco_pvu_cbio_credito_brl_m3']
    preco_anidro_equiv_hidratado = paridade_hidratado_int['preco_anidro_equivalente_brl_m3']
    st.metric("Preço PVU + CBIO", f"R$ {preco_pvu_cbio_hidratado:,.2f}/m³")
    st.metric("Crédito Tributário", f"R$ {credito_trib_hidratado:,.2f}/m³")
    st.metric("Preço PVU + CBIO + Crédito", f"R$ {preco_pvu_cbio_credito_hidratado:,.2f}/m³")
    st.metric("Equivalente Anidro", f"R$ {preco_anidro_equiv_hidratado:,.2f}/m³")
    vhp_saca_hidratado = paridade_hidratado_int['vhp_pvu_brl_saca']
    st.metric("VHP PVU (R$/saca)", f"R$ {vhp_saca_hidratado:,.2f}/saca")
    st.metric("VHP PVU (cents/lb)", f"{paridade_hidratado_int['vhp_pvu_cents_lb']:,.2f} cents/lb")
    if paridade_hidratado_int.get('vhp_fob_cents_lb') is not None:
        st.metric("VHP FOB (cents/lb)", f"{paridade_hidratado_int['vhp_fob_cents_lb']:,.2f} cents/lb")
    if paridade_hidratado_int.get('cristal_pvu_brl_saca') is not None:
        cristal_saca_hidratado = paridade_hidratado_int['cristal_pvu_brl_saca']
        st.metric("Equivalente Cristal PVU (R$/saca)", f"R$ {cristal_saca_hidratado:,.2f}/saca")
    if paridade_hidratado_int.get('cristal_pvu_cents_lb') is not None:
        st.metric("Equivalente Cristal PVU (cents/lb)", f"{paridade_hidratado_int['cristal_pvu_cents_lb']:,.2f} cents/lb")
    if paridade_hidratado_int.get('cristal_fob_cents_lb') is not None:
        st.metric("Equivalente Cristal FOB (cents/lb)", f"{paridade_hidratado_int['cristal_fob_cents_lb']:,.2f} cents/lb")

with tabs[4]:
    st.markdown("### Açúcar")
    
    # VHP Exportação
    if paridade_acucar.get('sugar_vhp_pvu_brl_saca') is not None:
        st.markdown("**Açúcar VHP Exportação**")
        sugar_vhp_saca = paridade_acucar['sugar_vhp_pvu_brl_saca']
        st.metric("VHP PVU (R$/saca)", f"R$ {sugar_vhp_saca:,.2f}/saca")
        st.metric("VHP PVU (cents/lb)", f"{paridade_acucar['sugar_vhp_pvu_cents_lb']:,.2f} cents/lb")
        st.metric("VHP FOB (cents/lb)", f"{paridade_acucar['sugar_vhp_fob_cents_lb']:,.2f} cents/lb")
        st.divider()
    
    # Cristal Exportação
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown("**Cristal Exportação**")
        if paridade_acucar.get('sugar_export_vhp_pvu_brl_saca') is not None:
            sugar_export_vhp_saca = paridade_acucar['sugar_export_vhp_pvu_brl_saca']
            st.metric("VHP PVU (R$/saca)", f"R$ {sugar_export_vhp_saca:,.2f}/saca")
            st.metric("VHP PVU (cents/lb)", f"{paridade_acucar['sugar_export_vhp_pvu_cents_lb']:,.2f} cents/lb")
            st.metric("VHP FOB (cents/lb)", f"{paridade_acucar.get('sugar_export_vhp_fob_cents_lb', 0):,.2f} cents/lb")
        if paridade_acucar.get('sugar_export_cristal_pvu_brl_saca') is not None:
            sugar_export_cristal_saca = paridade_acucar['sugar_export_cristal_pvu_brl_saca']
            st.metric("Cristal PVU (R$/saca)", f"R$ {sugar_export_cristal_saca:,.2f}/saca")
            st.metric("Cristal PVU (cents/lb)", f"{paridade_acucar['sugar_export_cristal_pvu_cents_lb']:,.2f} cents/lb")
            st.metric("Cristal FOB (cents/lb)", f"{paridade_acucar.get('sugar_export_cristal_fob_cents_lb', 0):,.2f} cents/lb")
    with col_a2:
        st.markdown("**Cristal Exportação Malha 30**")
        if paridade_acucar.get('sugar_malha30_vhp_pvu_brl_saca') is not None:
            vhp_saca_malha30 = paridade_acucar['sugar_malha30_vhp_pvu_brl_saca']
            st.metric("VHP PVU (R$/saca)", f"R$ {vhp_saca_malha30:,.2f}/saca")
            st.metric("VHP PVU (cents/lb)", f"{paridade_acucar['sugar_malha30_vhp_pvu_cents_lb']:,.2f} cents/lb")
            st.metric("VHP FOB (cents/lb)", f"{paridade_acucar.get('sugar_malha30_vhp_fob_cents_lb', 0):,.2f} cents/lb")
        if paridade_acucar.get('sugar_malha30_cristal_pvu_brl_saca') is not None:
            cristal_saca_malha30 = paridade_acucar['sugar_malha30_cristal_pvu_brl_saca']
            cristal_cents_malha30 = paridade_acucar['sugar_malha30_cristal_pvu_cents_lb']
            st.metric("Cristal PVU (R$/saca)", f"R$ {cristal_saca_malha30:,.2f}/saca")
            st.metric("Cristal PVU (cents/lb)", f"{cristal_cents_malha30:,.2f} cents/lb")
            st.metric("Cristal FOB (cents/lb)", f"{paridade_acucar.get('sugar_malha30_cristal_fob_cents_lb', 0):,.2f} cents/lb")
    
    st.divider()
    st.markdown("**Mercado Interno**")
    col_a3, col_a4 = st.columns(2)
    with col_a3:
        esalq_saca = preco_sugar_cristal_esalq_brl_saca
        st.metric("SUGAR Cristal Esalq", f"R$ {esalq_saca:,.2f}/saca")
    with col_a4:
        malha30_saca = preco_sugar_cristal_export_malha30_brl_saca
        preco_malha30_str = f"R$ {malha30_saca:,.2f}/saca"
        st.metric("Cristal Exportação Malha 30", preco_malha30_str)

