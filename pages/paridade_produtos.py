"""
================================================================================
PARIDADE PRODUTOS
================================================================================
Reprodução EXATA das fórmulas da aba "Paridade Produtos" do Excel.
Cada bloco corresponde a um conjunto de células da planilha original.
"""

import streamlit as st
import pandas as pd

# ============================================================================
# CONSTANTES
# ============================================================================

# Fatores de conversão
FATOR_VHP_ANIDRO_EXPORT = 32.669
FATOR_VHP_HIDRATADO_EXPORT = 31.304
FATOR_VHP_ANIDRO_INTERNO = 33.712
FATOR_VHP_HIDRATADO_INTERNO = 31.504
FATOR_CWT_POR_TON = 22.0462
FATOR_CWT_POR_TON_ALT = 22.04622  # Usado em algumas fórmulas
SACAS_POR_TON = 20
FATOR_CONV_ANIDRO_HIDRATADO = 0.0769
FATOR_DESCONTO_VHP_FOB = 1.042
FC_ANIDRO_CBIO = 712.4
FC_HIDRATADO_CBIO = 749.75
FATOR_ESALQ_SEM_IMPOSTOS = 0.9015
IMPOSTOS_ESALQ = 0.0985
CREDITO_TRIBUTARIO_HIDRATADO = 240
ALIQUOTA_IR_CBIO = 0.15
ALIQUOTA_PIS_COFINS_CBIO = 0.0925
SHARE_PRODUTOR_CBIO = 0.6

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def parse_ptbr_number(x):
    """
    Converte número no formato PT-BR (string com vírgula) para float.
    
    Args:
        x: String com vírgula ("5,35") ou número/None
        
    Returns:
        float ou None
    """
    if x is None or x == "":
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        # Remove espaços e substitui vírgula por ponto
        x = x.strip().replace(",", ".")
        if x == "":
            return None
        try:
            return float(x)
        except ValueError:
            return None
    return None

def fmt_br(valor, casas=2):
    """
    Formata número para exibição no padrão BR (vírgula como separador decimal).
    Se valor for None, retorna "Erro (divisão por zero)".
    """
    if valor is None:
        return "Erro (divisão por zero)"
    return f"{valor:,.{casas}f}".replace(".", "X").replace(",", ".").replace("X", ",")

# ============================================================================
# BLOCO 1 - ANIDRO EXPORTAÇÃO (colunas B/C, linhas 3-12)
# ============================================================================

def calc_anidro_exportacao(inputs, params_globais):
    """
    BLOCO 1 - ANIDRO EXPORTAÇÃO (colunas B/C, linhas 3-12)
    
    Args:
        inputs: dict com C3, C4, C5, C6, C7, C8
        params_globais: dict com C30, C32, C4 (cambio)
    
    Returns:
        dict com todos os outputs calculados + errors
    """
    errors = []
    result = {}
    
    # Inputs
    C3 = parse_ptbr_number(inputs.get('C3', 0))  # preco_anidro_fob_usd
    C4 = parse_ptbr_number(inputs.get('C4', params_globais.get('C4', 0)))  # cambio
    C5 = parse_ptbr_number(inputs.get('C5', 0))  # frete_porto_usina_brl
    C6 = parse_ptbr_number(inputs.get('C6', 0))  # terminal_brl
    C7 = parse_ptbr_number(inputs.get('C7', 0))  # supervisao_documentos_brl
    C8 = parse_ptbr_number(inputs.get('C8', 0))  # custos_adicionais_demurrage (pode ser None)
    if C8 is None:
        C8 = 0
    
    # Parâmetros globais
    C30 = parse_ptbr_number(params_globais.get('C30', 0))  # terminal_usd_ton
    C32 = parse_ptbr_number(params_globais.get('C32', 0))  # frete_brl_ton
    
    # C9: Preço liquido PVU
    # Excel: =((C3*C4)-C5-C6-C7-C8)
    C9 = (C3 * C4) - C5 - C6 - C7 - C8
    result['C9_preco_liquido_pvu'] = C9
    
    # C10: Equivalente VHP BRL/saca PVU
    # Excel: =C9/32.669
    C10 = C9 / FATOR_VHP_ANIDRO_EXPORT
    result['C10_vhp_brl_saca_pvu'] = C10
    
    # C11: Equivalente Cents/lb PVU
    # Excel: =((C10*20)/22.0462)/C4/1.042
    if C4 == 0:
        C11 = None
        errors.append("C11: Divisão por zero (C4=0)")
    else:
        C11 = ((C10 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C4 / FATOR_DESCONTO_VHP_FOB
    result['C11_vhp_cents_lb_pvu'] = C11
    
    # C12: Equivalente Cents/lb FOB
    # Excel: =((((((C9)/32.669)*20)+$C$32+($C$30*$C$4))/22.0462/$C$4)/1.042)
    if C4 == 0:
        C12 = None
        errors.append("C12: Divisão por zero (C4=0)")
    else:
        C12 = ((((((C9) / FATOR_VHP_ANIDRO_EXPORT) * SACAS_POR_TON) + C32 + (C30 * C4)) / FATOR_CWT_POR_TON / C4) / FATOR_DESCONTO_VHP_FOB)
    result['C12_vhp_cents_lb_fob'] = C12
    
    result['errors'] = errors
    return result

# ============================================================================
# BLOCO 2 - HIDRATADO EXPORTAÇÃO (colunas E/F, linhas 3-11)
# ============================================================================

def calc_hidratado_exportacao(inputs, params_globais):
    """
    BLOCO 2 - HIDRATADO EXPORTAÇÃO (colunas E/F, linhas 3-11)
    
    Args:
        inputs: dict com F3, F4, F5, F6, F7 (F4=F5=F6=F7 derivados de C4, C5, C6, C7)
        params_globais: dict com C30, C32, C4
    
    Returns:
        dict com todos os outputs calculados + errors
    """
    errors = []
    result = {}
    
    # Inputs
    F3 = parse_ptbr_number(inputs.get('F3', 0))  # preco_hidratado_fob_usd
    # F4, F5, F6, F7 são derivados de C4, C5, C6, C7
    F4 = parse_ptbr_number(inputs.get('F4', params_globais.get('C4', 0)))  # cambio (derivado de C4)
    F5 = parse_ptbr_number(inputs.get('F5', params_globais.get('C5', 0)))  # frete (derivado de C5)
    F6 = parse_ptbr_number(inputs.get('F6', params_globais.get('C6', 0)))  # terminal (derivado de C6)
    F7 = parse_ptbr_number(inputs.get('F7', params_globais.get('C7', 0)))  # supervisao (derivado de C7)
    
    # Parâmetros globais
    C30 = parse_ptbr_number(params_globais.get('C30', 0))
    C32 = parse_ptbr_number(params_globais.get('C32', 0))
    C4 = parse_ptbr_number(params_globais.get('C4', 0))
    
    # F8: Preço liquido PVU
    # Excel: =(F3*F4)-F5-F6-F7
    F8 = (F3 * F4) - F5 - F6 - F7
    result['F8_preco_liquido_pvu'] = F8
    
    # F9: Equivalente VHP BRL/saca PVU
    # Excel: =F8/31.304
    F9 = F8 / FATOR_VHP_HIDRATADO_EXPORT
    result['F9_vhp_brl_saca_pvu'] = F9
    
    # F10: Equivalente Cents/lb PVU
    # Excel: =((F9*20)/22.0462)/F4/1.042
    if F4 == 0:
        F10 = None
        errors.append("F10: Divisão por zero (F4=0)")
    else:
        F10 = ((F9 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / F4 / FATOR_DESCONTO_VHP_FOB
    result['F10_vhp_cents_lb_pvu'] = F10
    
    # F11: Equivalente Cents/lb FOB
    # Excel: =((((((F8)/32.669)*20)+$C$32+($C$30*$C$4))/22.0462/$C$4)/1.042)
    if C4 == 0:
        F11 = None
        errors.append("F11: Divisão por zero (C4=0)")
    else:
        F11 = ((((((F8) / 32.669) * SACAS_POR_TON) + C32 + (C30 * C4)) / FATOR_CWT_POR_TON / C4) / FATOR_DESCONTO_VHP_FOB)
    result['F11_vhp_cents_lb_fob'] = F11
    
    result['errors'] = errors
    return result

# ============================================================================
# BLOCO 3 - ANIDRO MERCADO INTERNO (colunas H/I, linhas 3-22 e 14-19)
# ============================================================================

def calc_anidro_mercado_interno(inputs, deps, params_globais):
    """
    BLOCO 3 - ANIDRO MERCADO INTERNO (colunas H/I, linhas 3-22 e 14-19)
    
    Args:
        inputs: dict com I3, I4, I5, I7
        deps: dict com L11, L7 (para I21, I22)
        params_globais: dict com C4, C5, C6, C7, C8
    
    Returns:
        dict com todos os outputs calculados + errors
    """
    errors = []
    result = {}
    
    # Inputs
    I3 = parse_ptbr_number(inputs.get('I3', 0))  # preco_anidro_com_impostos
    I4 = parse_ptbr_number(inputs.get('I4', 0))  # pis_cofins
    I5 = parse_ptbr_number(inputs.get('I5', 0))  # contribuicao_agroindustria
    I7 = parse_ptbr_number(inputs.get('I7', 0))  # valor_cbio_bruto
    
    # Dependências
    L11 = parse_ptbr_number(deps.get('L11'))
    L7 = parse_ptbr_number(deps.get('L7'))
    
    # Parâmetros globais
    C4 = parse_ptbr_number(params_globais.get('C4', 0))
    C5 = parse_ptbr_number(params_globais.get('C5', 0))
    C6 = parse_ptbr_number(params_globais.get('C6', 0))
    C7 = parse_ptbr_number(params_globais.get('C7', 0))
    C8 = parse_ptbr_number(params_globais.get('C8', 0))
    
    # I6: Preço liquido PVU
    # Excel: =((I3*(1-I5))-I4)
    I6 = ((I3 * (1 - I5)) - I4)
    result['I6_preco_liquido_pvu'] = I6
    
    # I8: Valor CBIO sem IR (15%) / PIS/Cof (9,25%) / 60% Usina
    # Excel: =(I7*0.7575)*0.6
    I8 = (I7 * 0.7575) * SHARE_PRODUTOR_CBIO
    result['I8_valor_cbio_liquido'] = I8
    
    # I9: Preço liquido PVU + CBIO (FC 712,40)
    # Excel: =I6+((I8/712.4)*1000)
    I9 = I6 + ((I8 / FC_ANIDRO_CBIO) * 1000)
    result['I9_preco_pvu_mais_cbio'] = I9
    
    # I10: Equivalente Hidratado - 7,69% Fator Conv.
    # Excel: =I6/(1+0.0769)
    I10 = I6 / (1 + FATOR_CONV_ANIDRO_HIDRATADO)
    result['I10_equivalente_hidratado'] = I10
    
    # I14: Equivalente VHP BRL/saco PVU
    # Excel: =(I9/33.712)
    I14 = (I9 / FATOR_VHP_ANIDRO_INTERNO)
    result['I14_vhp_brl_saco_pvu'] = I14
    
    # I15: Equivalente VHP Cents/lb PVU
    # Excel: =(((I14*20)/22.0462)/C4)
    if C4 == 0:
        I15 = None
        errors.append("I15: Divisão por zero (C4=0)")
    else:
        I15 = (((I14 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C4)
    result['I15_vhp_cents_lb_pvu'] = I15
    
    # I16: Equivalente VHP Cents/lb FOB
    # Excel: =(((I15*20)/22.0462)/C5)
    if C5 == 0:
        I16 = None
        errors.append("I16: Divisão por zero (C5=0)")
    else:
        I16 = (((I15 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C5) if I15 is not None else None
    result['I16_vhp_cents_lb_fob'] = I16
    
    # I17: Equivalente Cristal BRL/Saca PVU
    # Excel: =(((I16*20)/22.0462)/C6)
    if C6 == 0:
        I17 = None
        errors.append("I17: Divisão por zero (C6=0)")
    else:
        I17 = (((I16 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C6) if I16 is not None else None
    result['I17_cristal_brl_saca_pvu'] = I17
    
    # I18: Equivalente Cristal Cents/lb PVU
    # Excel: =(((I17*20)/22.0462)/C7)
    if C7 == 0:
        I18 = None
        errors.append("I18: Divisão por zero (C7=0)")
    else:
        I18 = (((I17 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C7) if I17 is not None else None
    result['I18_cristal_cents_lb_pvu'] = I18
    
    # I19: Equivalente Cristal Cents/lb FOB
    # Excel: =(((I18*20)/22.0462)/C8)
    if C8 == 0 or C8 is None:
        I19 = None
        errors.append("I19: Divisão por zero (C8=0 ou vazio)")
    else:
        I19 = (((I18 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C8) if I18 is not None else None
    result['I19_cristal_cents_lb_fob'] = I19
    
    # I21: Prêmio Anidro/Hidratado Líquido
    # Excel: =(I6/L11)-1
    if L11 == 0 or L11 is None:
        I21 = None
        errors.append("I21: Divisão por zero (L11=0 ou vazio)")
    else:
        I21 = (I6 / L11) - 1
    result['I21_premio_anidro_hidratado_liquido'] = I21
    
    # I22: Prêmio Anidro/Hidratado Contrato
    # Excel: =(I6/L7)-1
    if L7 == 0 or L7 is None:
        I22 = None
        errors.append("I22: Divisão por zero (L7=0 ou vazio)")
    else:
        I22 = (I6 / L7) - 1
    result['I22_premio_anidro_hidratado_contrato'] = I22
    
    result['errors'] = errors
    return result

# ============================================================================
# BLOCO 4 - HIDRATADO MERCADO INTERNO (colunas K/L, linhas 3-22 e 14-19)
# ============================================================================

def calc_hidratado_mercado_interno(inputs, deps, params_globais):
    """
    BLOCO 4 - HIDRATADO MERCADO INTERNO (colunas K/L, linhas 3-22 e 14-19)
    
    Args:
        inputs: dict com L3, L4, L5, L6, L8, I28, L31
        deps: dict vazio (não há dependências de outros blocos)
        params_globais: dict com C4, C30, C32, F4
    
    Returns:
        dict com todos os outputs calculados + errors
    """
    errors = []
    result = {}
    
    # Inputs
    L3 = parse_ptbr_number(inputs.get('L3', 0))  # preco_hidratado_rp_com_impostos
    L4 = parse_ptbr_number(inputs.get('L4', 0))  # pis_cofins
    L5 = parse_ptbr_number(inputs.get('L5', 0))  # icms
    L6 = parse_ptbr_number(inputs.get('L6', 0))  # contribuicao_agroindustria
    L8 = parse_ptbr_number(inputs.get('L8', 0))  # valor_cbio_bruto
    I28 = parse_ptbr_number(inputs.get('I28', 0))  # premio_fisico_pvu
    L31 = parse_ptbr_number(inputs.get('L31', 0))  # fobizacao_container_brl_ton
    
    # Parâmetros globais
    C4 = parse_ptbr_number(params_globais.get('C4', 0))
    C30 = parse_ptbr_number(params_globais.get('C30', 0))
    C32 = parse_ptbr_number(params_globais.get('C32', 0))
    F4 = parse_ptbr_number(params_globais.get('F4', params_globais.get('C4', 0)))  # F4 = C4
    
    # L7: Preço liquido PVU
    # Excel: =((L3*(1-L6))*(1-L5)-L4)
    L7 = ((L3 * (1 - L6)) * (1 - L5) - L4)
    result['L7_preco_liquido_pvu'] = L7
    
    # L9: Valor CBIO sem IR (15%) / PIS/Cof (9,25%) / 60% Usina
    # Excel: =(L8*0.7575)*0.6
    L9 = (L8 * 0.7575) * SHARE_PRODUTOR_CBIO
    result['L9_valor_cbio_liquido'] = L9
    
    # L10: Preço liquido PVU + CBIO (FC 749,75)
    # Excel: =L7+((L9/749.75)*1000)
    L10 = L7 + ((L9 / FC_HIDRATADO_CBIO) * 1000)
    result['L10_preco_pvu_mais_cbio'] = L10
    
    # L11: Equivalente Anidro - 7,69% Fator Conv.
    # Excel: =L7*(1+0.0769)
    L11 = L7 * (1 + FATOR_CONV_ANIDRO_HIDRATADO)
    result['L11_equivalente_anidro'] = L11
    
    # L12: Preço Liquido PVU + CBIO + Credito Trib. (0,24)
    # Excel: =L10+240
    L12 = L10 + CREDITO_TRIBUTARIO_HIDRATADO
    result['L12_preco_pvu_cbio_credito'] = L12
    
    # L14: Equivalente VHP BRL/saco PVU
    # Excel: =(L10/31.504)
    L14 = (L10 / FATOR_VHP_HIDRATADO_INTERNO)
    result['L14_vhp_brl_saco_pvu'] = L14
    
    # L15: Equivalente VHP Cents/lb PVU
    # Excel: =(((L14*20)/22.0462)/$F$4)
    if F4 == 0:
        L15 = None
        errors.append("L15: Divisão por zero (F4=0)")
    else:
        L15 = (((L14 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / F4)
    result['L15_vhp_cents_lb_pvu'] = L15
    
    # L16: Equivalente VHP Cents/lb FOB
    # Excel: =((((((L10)/31.504)*20)+$C$32+($C$30*$C$4))/22.0462/$C$4)/1.042)
    if C4 == 0:
        L16 = None
        errors.append("L16: Divisão por zero (C4=0)")
    else:
        L16 = ((((((L10) / FATOR_VHP_HIDRATADO_INTERNO) * SACAS_POR_TON) + C32 + (C30 * C4)) / FATOR_CWT_POR_TON / C4) / FATOR_DESCONTO_VHP_FOB)
    result['L16_vhp_cents_lb_fob'] = L16
    
    # L17: Equivalente Cristal BRL/Saca PVU
    # Excel: =(L18*22.0462/20)*$C$4
    # Nota: L18 precisa ser calculado primeiro
    # L18: Equivalente Cristal Cents/lb PVU
    # Excel: =((((((L10)/31.504)*20)+($I$28*$C$4))/22.0462/$C$4))
    if C4 == 0:
        L18 = None
        errors.append("L18: Divisão por zero (C4=0)")
    else:
        L18 = ((((((L10) / FATOR_VHP_HIDRATADO_INTERNO) * SACAS_POR_TON) + (I28 * C4)) / FATOR_CWT_POR_TON / C4))
    
    result['L18_cristal_cents_lb_pvu'] = L18
    
    # Agora calcula L17 usando L18
    if L18 is not None:
        L17 = (L18 * FATOR_CWT_POR_TON / SACAS_POR_TON) * C4
    else:
        L17 = None
    result['L17_cristal_brl_saca_pvu'] = L17
    
    # L19: Equivalente Cristal Cents/lb FOB
    # Excel: =(((((((L10)/31.504)*20)+$C$32+L31)+($I$28*$C$4))/22.0462/$C$4))
    if C4 == 0:
        L19 = None
        errors.append("L19: Divisão por zero (C4=0)")
    else:
        L19 = (((((((L10) / FATOR_VHP_HIDRATADO_INTERNO) * SACAS_POR_TON) + C32 + L31) + (I28 * C4)) / FATOR_CWT_POR_TON / C4))
    result['L19_cristal_cents_lb_fob'] = L19
    
    result['errors'] = errors
    return result

# ============================================================================
# BLOCO 5 - PARIDADE AÇÚCAR (5 sub-blocos)
# ============================================================================

def calc_acucar(inputs, custo_cristal_vs_vhp_D17, params_globais):
    """
    BLOCO 5 - PARIDADE AÇÚCAR (5 sub-blocos)
    
    Args:
        inputs: dict com todos os inputs dos 5 sub-blocos
        custo_cristal_vs_vhp_D17: float (custo diferencial)
        params_globais: dict com C4, C30, C32, L31, L32
    
    Returns:
        dict com todos os outputs calculados + errors
    """
    errors = []
    result = {}
    
    # Parâmetros comuns
    C26 = parse_ptbr_number(inputs.get('C26', 0))  # sugar_ny_fob_cents_lb
    C27 = parse_ptbr_number(inputs.get('C27', 0))  # premio_desconto_cents_lb
    C28 = parse_ptbr_number(inputs.get('C28', 0))  # premio_pol
    C30 = parse_ptbr_number(params_globais.get('C30', 0))  # terminal_usd_ton
    C31 = parse_ptbr_number(params_globais.get('C4', 0))  # cambio (C31 = C4)
    C32 = parse_ptbr_number(params_globais.get('C32', 0))  # frete_brl_ton
    L31 = parse_ptbr_number(params_globais.get('L31', 0))  # fobizacao_container_brl_ton
    L32 = parse_ptbr_number(params_globais.get('L32', params_globais.get('C32', 0)))  # frete_brl_ton (L32 = C32)
    I28 = parse_ptbr_number(inputs.get('I28', 0))  # premio_fisico_pvu
    L28 = parse_ptbr_number(inputs.get('L28', 0))  # premio_fisico_fob
    O28 = parse_ptbr_number(inputs.get('O28', 0))  # premio_fisico_malha30
    C4 = parse_ptbr_number(params_globais.get('C4', 0))
    
    # ===== SUB-BLOCO 5.1 - SUGAR VHP (B/C) =====
    
    # C29: Sugar NY + POL
    # Excel: =(C26+C27)*(1+C28)
    C29 = (C26 + C27) * (1 + C28)
    result['C29_sugar_ny_pol'] = C29
    
    # C33: Equivalente VHP BRL/saca PVU
    # Excel: =(((C29*22.0462)-C30-(C32/C31))/20)*C31
    if C31 == 0:
        C33 = None
        errors.append("C33: Divisão por zero (C31=0)")
    else:
        C33 = (((C29 * FATOR_CWT_POR_TON) - C30 - (C32 / C31)) / SACAS_POR_TON) * C31
    result['C33_vhp_brl_saca_pvu'] = C33
    
    # C34: Equivalente VHP Cents/lb PVU
    # Excel: =((C33*20)/22.0462)/C31
    if C31 == 0:
        C34 = None
        errors.append("C34: Divisão por zero (C31=0)")
    else:
        C34 = ((C33 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C31 if C33 is not None else None
    result['C34_vhp_cents_lb_pvu'] = C34
    
    # C35: Equivalente VHP Cents/lb FOB
    # Excel: =C29
    C35 = C29
    result['C35_vhp_cents_lb_fob'] = C35
    
    # ===== SUB-BLOCO 5.2 - CRISTAL ESALQ (E/F) =====
    
    F26 = parse_ptbr_number(inputs.get('F26', 0))  # esalq_brl_saca
    F27 = parse_ptbr_number(inputs.get('F27', IMPOSTOS_ESALQ))  # impostos
    
    # F36: Equivalente Cristal BRL/Saca PVU
    # Excel: =(F26*(1-F27))
    F36 = (F26 * (1 - F27))
    result['F36_cristal_brl_saca_pvu'] = F36
    
    # F33: Equivalente VHP BRL/saco PVU
    # Excel: =F36-'Custo Cristal vs VHP'!$D$17
    F33 = F36 - custo_cristal_vs_vhp_D17
    result['F33_vhp_brl_saco_pvu'] = F33
    
    # F34: Equivalente VHP Cents/lb PVU
    # Excel: =(((F33*20)/22.0462)/$C$4)
    if C4 == 0:
        F34 = None
        errors.append("F34: Divisão por zero (C4=0)")
    else:
        F34 = (((F33 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C4)
    result['F34_vhp_cents_lb_pvu'] = F34
    
    # F35: Equivalente VHP Cents/lb FOB
    # Excel: =((((((F33)*20)+$L$32+(C30*C4))/22.0462/$C$4)))
    if C4 == 0:
        F35 = None
        errors.append("F35: Divisão por zero (C4=0)")
    else:
        F35 = ((((((F33) * SACAS_POR_TON) + L32 + (C30 * C4)) / FATOR_CWT_POR_TON / C4)))
    result['F35_vhp_cents_lb_fob'] = F35
    
    # F37: Equivalente Cristal Cents/lb PVU
    # Excel: =(((F36*20)/22.0462)/C4)-(15/22.0462/C4)
    if C4 == 0:
        F37 = None
        errors.append("F37: Divisão por zero (C4=0)")
    else:
        F37 = (((F36 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C4) - (15 / FATOR_CWT_POR_TON / C4)
    result['F37_cristal_cents_lb_pvu'] = F37
    
    # F28: Frete Santos-Usina R$/ton
    # Excel: =L32
    F28 = L32
    result['F28_frete_santos_usina'] = F28
    
    # F29: Fobização Container R$/ton
    # Excel: =L31
    F29 = L31
    result['F29_fobizacao_container'] = F29
    
    # F38: Equivalente Cristal Cents/lb FOB
    # Excel: =(((F36*20)+F28+F29)/22.04622)/C4
    if C4 == 0:
        F38 = None
        errors.append("F38: Divisão por zero (C4=0)")
    else:
        F38 = (((F36 * SACAS_POR_TON) + F28 + F29) / FATOR_CWT_POR_TON_ALT) / C4
    result['F38_cristal_cents_lb_fob'] = F38
    
    # ===== SUB-BLOCO 5.3 - CRISTAL MERCADO INTERNO (H/I) =====
    
    # I26: =C26
    I26 = C26
    result['I26'] = I26
    
    # I27: =I26*22.04622
    I27 = I26 * FATOR_CWT_POR_TON_ALT
    result['I27'] = I27
    
    # I29: Sugar PVU USD/ton
    # Excel: =I27+I28
    I29 = I27 + I28
    result['I29_sugar_pvu_usd_ton'] = I29
    
    # I30: Sugar PVU R$/ton
    # Excel: =I29*C4
    I30 = I29 * C4
    result['I30_sugar_pvu_r_ton'] = I30
    
    # I36: Equivalente Cristal BRL/Saca PVU
    # Excel: =(I30)/20
    I36 = (I30) / SACAS_POR_TON
    result['I36_cristal_brl_saca_pvu'] = I36
    
    # I33: Equivalente VHP BRL/saco PVU
    # Excel: =I36-'Custo Cristal vs VHP'!$D$17
    I33 = I36 - custo_cristal_vs_vhp_D17
    result['I33_vhp_brl_saco_pvu'] = I33
    
    # I34: Equivalente VHP Cents/lb PVU
    # Excel: =(((I33*20)/22.0462)/$C$4)
    if C4 == 0:
        I34 = None
        errors.append("I34: Divisão por zero (C4=0)")
    else:
        I34 = (((I33 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C4)
    result['I34_vhp_cents_lb_pvu'] = I34
    
    # I35: Equivalente VHP Cents/lb FOB
    # Excel: =((((((I33)*20)+$L$32+($C$30*$C$4))/22.0462/$C$4)))
    if C4 == 0:
        I35 = None
        errors.append("I35: Divisão por zero (C4=0)")
    else:
        I35 = ((((((I33) * SACAS_POR_TON) + L32 + (C30 * C4)) / FATOR_CWT_POR_TON / C4)))
    result['I35_vhp_cents_lb_fob'] = I35
    
    # I37: Equivalente Cristal Cents/lb PVU
    # Excel: =((I36*20)/22.0462)/C4
    if C4 == 0:
        I37 = None
        errors.append("I37: Divisão por zero (C4=0)")
    else:
        I37 = ((I36 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C4
    result['I37_cristal_cents_lb_pvu'] = I37
    
    # I38: Equivalente Cristal Cents/lb FOB
    # Excel: =((I30+L31+L32)/22.0462)/C4
    if C4 == 0:
        I38 = None
        errors.append("I38: Divisão por zero (C4=0)")
    else:
        I38 = ((I30 + L31 + L32) / FATOR_CWT_POR_TON) / C4
    result['I38_cristal_cents_lb_fob'] = I38
    
    # I41: Equivalente Esalq com Impostos
    # Excel: =I36/0.9015
    I41 = I36 / FATOR_ESALQ_SEM_IMPOSTOS
    result['I41_equivalente_esalq_com_impostos'] = I41
    
    # ===== SUB-BLOCO 5.4 - CRISTAL EXPORTAÇÃO (K/L) =====
    
    # L26: =C26
    L26 = C26
    result['L26'] = L26
    
    # L27: =L26*22.04622
    L27 = L26 * FATOR_CWT_POR_TON_ALT
    result['L27'] = L27
    
    # L29: Sugar FOB USD/ton
    # Excel: =L27+L28
    L29 = L27 + L28
    result['L29_sugar_fob_usd_ton'] = L29
    
    # L30: Sugar FOB R$/ton
    # Excel: =L29*C4
    L30 = L29 * C4
    result['L30_sugar_fob_r_ton'] = L30
    
    # L36: Equivalente Cristal BRL/Saca PVU
    # Excel: =(L30-L31-L32)/20
    L36 = (L30 - L31 - L32) / SACAS_POR_TON
    result['L36_cristal_brl_saca_pvu'] = L36
    
    # L33: Equivalente VHP BRL/saco PVU
    # Excel: =L36-'Custo Cristal vs VHP'!$D$17
    L33 = L36 - custo_cristal_vs_vhp_D17
    result['L33_vhp_brl_saco_pvu'] = L33
    
    # L34: Equivalente VHP Cents/lb PVU
    # Excel: =(((L33*20)/22,0462)/$C$4)  (atenção: vírgula no Excel)
    if C4 == 0:
        L34 = None
        errors.append("L34: Divisão por zero (C4=0)")
    else:
        L34 = (((L33 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C4)
    result['L34_vhp_cents_lb_pvu'] = L34
    
    # L35: Equivalente VHP Cents/lb FOB
    # Excel: =((((((L33)*20)+$L$32+(C30*C4))/22.0462/$C$4)))
    if C4 == 0:
        L35 = None
        errors.append("L35: Divisão por zero (C4=0)")
    else:
        L35 = ((((((L33) * SACAS_POR_TON) + L32 + (C30 * C4)) / FATOR_CWT_POR_TON / C4)))
    result['L35_vhp_cents_lb_fob'] = L35
    
    # L37: Equivalente Cristal Cents/lb PVU
    # Excel: =((L36*20)/22.0462)/C4
    if C4 == 0:
        L37 = None
        errors.append("L37: Divisão por zero (C4=0)")
    else:
        L37 = ((L36 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C4
    result['L37_cristal_cents_lb_pvu'] = L37
    
    # L38: Equivalente Cristal Cents/lb FOB
    # Excel: =L29/22.04622
    L38 = L29 / FATOR_CWT_POR_TON_ALT
    result['L38_cristal_cents_lb_fob'] = L38
    
    # L41: Equivalente Esalq com Impostos
    # Excel: =L36/0.9015
    L41 = L36 / FATOR_ESALQ_SEM_IMPOSTOS
    result['L41_equivalente_esalq_com_impostos'] = L41
    
    # ===== SUB-BLOCO 5.5 - CRISTAL EXPORTAÇÃO MALHA 30 (N/O) =====
    
    # O26: =C26
    O26 = C26
    result['O26'] = O26
    
    # O27: =O26*22.04622
    O27 = O26 * FATOR_CWT_POR_TON_ALT
    result['O27'] = O27
    
    # O29: Sugar FOB USD/ton
    # Excel: =O27+O28
    O29 = O27 + O28
    result['O29_sugar_fob_usd_ton'] = O29
    
    # O30: Sugar FOB R$/ton
    # Excel: =O29*C4
    O30 = O29 * C4
    result['O30_sugar_fob_r_ton'] = O30
    
    # O31: fobização container R$/ton
    O31 = parse_ptbr_number(inputs.get('O31', 198))
    result['O31_fobizacao_container'] = O31
    
    # O32: frete R$/ton
    O32 = parse_ptbr_number(inputs.get('O32', 202))
    result['O32_frete'] = O32
    
    # O36: Equivalente Cristal BRL/Saca PVU
    # Excel: =(O30-O31-O32)/20
    O36 = (O30 - O31 - O32) / SACAS_POR_TON
    result['O36_cristal_brl_saca_pvu'] = O36
    
    # O33: Equivalente VHP BRL/saco PVU
    # Excel: =O36-'Custo Cristal vs VHP'!$D$17
    O33 = O36 - custo_cristal_vs_vhp_D17
    result['O33_vhp_brl_saco_pvu'] = O33
    
    # O34: Equivalente VHP Cents/lb PVU
    # Excel: =(((O33*20)/22.0462)/$C$4)
    if C4 == 0:
        O34 = None
        errors.append("O34: Divisão por zero (C4=0)")
    else:
        O34 = (((O33 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C4)
    result['O34_vhp_cents_lb_pvu'] = O34
    
    # O35: Equivalente VHP Cents/lb FOB
    # Excel: =((((((O33)*20)+$L$32+(C30*C4))/22.0462/$C$4)))
    if C4 == 0:
        O35 = None
        errors.append("O35: Divisão por zero (C4=0)")
    else:
        O35 = ((((((O33) * SACAS_POR_TON) + L32 + (C30 * C4)) / FATOR_CWT_POR_TON / C4)))
    result['O35_vhp_cents_lb_fob'] = O35
    
    # O37: Equivalente Cristal Cents/lb PVU
    # Excel: =((O36*20)/22.0462)/C4
    if C4 == 0:
        O37 = None
        errors.append("O37: Divisão por zero (C4=0)")
    else:
        O37 = ((O36 * SACAS_POR_TON) / FATOR_CWT_POR_TON) / C4
    result['O37_cristal_cents_lb_pvu'] = O37
    
    # O38: Equivalente Cristal Cents/lb FOB
    # Excel: =O29/22.04622
    O38 = O29 / FATOR_CWT_POR_TON_ALT
    result['O38_cristal_cents_lb_fob'] = O38
    
    # O41: Equivalente Esalq com Impostos
    # Excel: =O36/0,9015  (atenção: vírgula no Excel)
    O41 = O36 / FATOR_ESALQ_SEM_IMPOSTOS
    result['O41_equivalente_esalq_com_impostos'] = O41
    
    result['errors'] = errors
    return result

# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

st.set_page_config(page_title="Paridade Produtos", layout="wide")

st.title("📊 Paridade Produtos")
st.caption("Reprodução exata das fórmulas da aba 'Paridade Produtos' do Excel")

# ============================================================================
# SIDEBAR - INPUTS
# ============================================================================

with st.sidebar:
    st.header("⚙️ Parâmetros Globais")
    
    # C4: Câmbio
    C4 = st.number_input("C4 - Câmbio USD/BRL", value=5.35, step=0.01, format="%.4f")
    
    # C5-C8: Custos adicionais (usados em I16-I19)
    st.subheader("Custos Adicionais (para cálculos I16-I19)")
    C5 = st.number_input("C5", value=0.0, step=0.1, format="%.2f")
    C6 = st.number_input("C6", value=0.0, step=0.1, format="%.2f")
    C7 = st.number_input("C7", value=0.0, step=0.1, format="%.2f")
    C8 = st.number_input("C8 - Custos Adicionais Demurrage", value=0.0, step=0.1, format="%.2f", help="Se vazio, I19 dará erro de divisão por zero")
    
    # C30, C32: Parâmetros do bloco açúcar
    st.subheader("Parâmetros Açúcar (compartilhados)")
    C30 = st.number_input("C30 - Terminal USD/ton", value=12.5, step=0.1, format="%.2f")
    C32 = st.number_input("C32 - Frete BRL/ton", value=202.0, step=1.0, format="%.2f")
    L31 = st.number_input("L31 - Fobização Container BRL/ton", value=198.0, step=1.0, format="%.2f")
    L32 = st.number_input("L32 - Frete BRL/ton", value=202.0, step=1.0, format="%.2f")
    
    # Custo Cristal vs VHP
    custo_cristal_vs_vhp_D17 = st.number_input("Custo Cristal vs VHP (D17)", value=0.0, step=0.1, format="%.2f")
    
    st.divider()
    st.header("📥 Inputs por Bloco")
    
    # BLOCO 1 - ANIDRO EXPORTAÇÃO
    st.subheader("BLOCO 1 - Anidro Exportação")
    C3 = st.number_input("C3 - Preço Anidro FOB USD", value=750.0, step=1.0, format="%.2f")
    C5_bloco1 = st.number_input("C5 - Frete Porto-Usina BRL", value=200.0, step=1.0, format="%.2f")
    C6_bloco1 = st.number_input("C6 - Terminal BRL", value=100.0, step=1.0, format="%.2f")
    C7_bloco1 = st.number_input("C7 - Supervisão/Documentos BRL", value=4.0, step=0.1, format="%.2f")
    C8_bloco1 = st.number_input("C8 - Custos Adicionais Demurrage", value=0.0, step=0.1, format="%.2f")
    
    # BLOCO 2 - HIDRATADO EXPORTAÇÃO
    st.subheader("BLOCO 2 - Hidratado Exportação")
    F3 = st.number_input("F3 - Preço Hidratado FOB USD", value=550.0, step=1.0, format="%.2f")
    
    # BLOCO 3 - ANIDRO MERCADO INTERNO
    st.subheader("BLOCO 3 - Anidro Mercado Interno")
    I3 = st.number_input("I3 - Preço Anidro com Impostos", value=3350.0, step=1.0, format="%.2f")
    I4 = st.number_input("I4 - PIS/COFINS", value=192.2, step=0.1, format="%.2f")
    I5 = st.number_input("I5 - Contribuição Agroindústria", value=0.0, step=0.01, format="%.4f")
    I7 = st.number_input("I7 - Valor CBIO Bruto", value=40.0, step=1.0, format="%.2f")
    
    # BLOCO 4 - HIDRATADO MERCADO INTERNO
    st.subheader("BLOCO 4 - Hidratado Mercado Interno")
    L3 = st.number_input("L3 - Preço Hidratado RP com Impostos", value=3400.0, step=1.0, format="%.2f")
    L4 = st.number_input("L4 - PIS/COFINS", value=192.2, step=0.1, format="%.2f")
    L5 = st.number_input("L5 - ICMS", value=0.12, step=0.01, format="%.4f")
    L6 = st.number_input("L6 - Contribuição Agroindústria", value=0.0, step=0.01, format="%.4f")
    L8 = st.number_input("L8 - Valor CBIO Bruto", value=40.0, step=1.0, format="%.2f")
    I28 = st.number_input("I28 - Prêmio Físico PVU", value=23.0, step=1.0, format="%.2f")
    
    # BLOCO 5 - AÇÚCAR
    st.subheader("BLOCO 5 - Açúcar")
    C26 = st.number_input("C26 - Sugar NY FOB (cents/lb)", value=15.8, step=0.1, format="%.2f")
    C27 = st.number_input("C27 - Prêmio/Desconto (cents/lb)", value=-0.1, step=0.1, format="%.2f")
    C28 = st.number_input("C28 - Prêmio POL", value=0.042, step=0.001, format="%.4f")
    F26 = st.number_input("F26 - Esalq BRL/saca", value=115.67, step=0.1, format="%.2f")
    F27 = st.number_input("F27 - Impostos Esalq", value=0.0985, step=0.001, format="%.4f")
    L28 = st.number_input("L28 - Prêmio Físico FOB", value=90.0, step=1.0, format="%.2f")
    O28 = st.number_input("O28 - Prêmio Físico Malha 30", value=104.0, step=1.0, format="%.2f")
    O31 = st.number_input("O31 - Fobização Container BRL/ton", value=198.0, step=1.0, format="%.2f")
    O32 = st.number_input("O32 - Frete BRL/ton", value=202.0, step=1.0, format="%.2f")

# ============================================================================
# PARÂMETROS GLOBAIS
# ============================================================================

params_globais = {
    'C4': C4,
    'C5': C5,
    'C6': C6,
    'C7': C7,
    'C8': C8,
    'C30': C30,
    'C32': C32,
    'L31': L31,
    'L32': L32,
    'F4': C4,  # F4 = C4
}

# ============================================================================
# CÁLCULOS
# ============================================================================

# BLOCO 1
inputs_bloco1 = {
    'C3': C3,
    'C4': C4,
    'C5': C5_bloco1,
    'C6': C6_bloco1,
    'C7': C7_bloco1,
    'C8': C8_bloco1,
}
result_bloco1 = calc_anidro_exportacao(inputs_bloco1, params_globais)

# BLOCO 2
inputs_bloco2 = {
    'F3': F3,
    'F4': C4,  # Derivado de C4
    'F5': C5_bloco1,  # Derivado de C5
    'F6': C6_bloco1,  # Derivado de C6
    'F7': C7_bloco1,  # Derivado de C7
}
result_bloco2 = calc_hidratado_exportacao(inputs_bloco2, params_globais)

# BLOCO 4 (precisa ser calculado antes do BLOCO 3 para ter L11 e L7)
inputs_bloco4 = {
    'L3': L3,
    'L4': L4,
    'L5': L5,
    'L6': L6,
    'L8': L8,
    'I28': I28,
    'L31': L31,
}
result_bloco4 = calc_hidratado_mercado_interno(inputs_bloco4, {}, params_globais)

# BLOCO 3 (depende de L11 e L7 do BLOCO 4)
deps_bloco3 = {
    'L11': result_bloco4.get('L11_equivalente_anidro'),
    'L7': result_bloco4.get('L7_preco_liquido_pvu'),
}
inputs_bloco3 = {
    'I3': I3,
    'I4': I4,
    'I5': I5,
    'I7': I7,
}
result_bloco3 = calc_anidro_mercado_interno(inputs_bloco3, deps_bloco3, params_globais)

# BLOCO 5
inputs_bloco5 = {
    'C26': C26,
    'C27': C27,
    'C28': C28,
    'F26': F26,
    'F27': F27,
    'I28': I28,
    'L28': L28,
    'O28': O28,
    'O31': O31,
    'O32': O32,
}
result_bloco5 = calc_acucar(inputs_bloco5, custo_cristal_vs_vhp_D17, params_globais)

# ============================================================================
# EXIBIÇÃO DOS RESULTADOS
# ============================================================================

# Erros
all_errors = result_bloco1.get('errors', []) + result_bloco2.get('errors', []) + result_bloco3.get('errors', []) + result_bloco4.get('errors', []) + result_bloco5.get('errors', [])
if all_errors:
    st.error("⚠️ Erros encontrados:")
    for error in all_errors:
        st.write(f"- {error}")

# BLOCO 1
st.header("📦 BLOCO 1 - Anidro Exportação")
col1, col2, col3, col4 = st.columns(4)
col1.metric("C9 - Preço Líquido PVU", fmt_br(result_bloco1.get('C9_preco_liquido_pvu')))
col2.metric("C10 - VHP BRL/saca PVU", fmt_br(result_bloco1.get('C10_vhp_brl_saca_pvu')))
col3.metric("C11 - VHP Cents/lb PVU", fmt_br(result_bloco1.get('C11_vhp_cents_lb_pvu')))
col4.metric("C12 - VHP Cents/lb FOB", fmt_br(result_bloco1.get('C12_vhp_cents_lb_fob')))

# BLOCO 2
st.header("📦 BLOCO 2 - Hidratado Exportação")
col1, col2, col3, col4 = st.columns(4)
col1.metric("F8 - Preço Líquido PVU", fmt_br(result_bloco2.get('F8_preco_liquido_pvu')))
col2.metric("F9 - VHP BRL/saca PVU", fmt_br(result_bloco2.get('F9_vhp_brl_saca_pvu')))
col3.metric("F10 - VHP Cents/lb PVU", fmt_br(result_bloco2.get('F10_vhp_cents_lb_pvu')))
col4.metric("F11 - VHP Cents/lb FOB", fmt_br(result_bloco2.get('F11_vhp_cents_lb_fob')))

# BLOCO 3
st.header("📦 BLOCO 3 - Anidro Mercado Interno")
col1, col2, col3, col4 = st.columns(4)
col1.metric("I6 - Preço Líquido PVU", fmt_br(result_bloco3.get('I6_preco_liquido_pvu')))
col2.metric("I9 - PVU + CBIO", fmt_br(result_bloco3.get('I9_preco_pvu_mais_cbio')))
col3.metric("I14 - VHP BRL/saco PVU", fmt_br(result_bloco3.get('I14_vhp_brl_saco_pvu')))
col4.metric("I15 - VHP Cents/lb PVU", fmt_br(result_bloco3.get('I15_vhp_cents_lb_pvu')))
col1, col2, col3, col4 = st.columns(4)
col1.metric("I16 - VHP Cents/lb FOB", fmt_br(result_bloco3.get('I16_vhp_cents_lb_fob')))
col2.metric("I21 - Prêmio Anidro/Hidratado Líq.", fmt_br(result_bloco3.get('I21_premio_anidro_hidratado_liquido')))
col3.metric("I22 - Prêmio Anidro/Hidratado Cont.", fmt_br(result_bloco3.get('I22_premio_anidro_hidratado_contrato')))

# BLOCO 4
st.header("📦 BLOCO 4 - Hidratado Mercado Interno")
col1, col2, col3, col4 = st.columns(4)
col1.metric("L7 - Preço Líquido PVU", fmt_br(result_bloco4.get('L7_preco_liquido_pvu')))
col2.metric("L10 - PVU + CBIO", fmt_br(result_bloco4.get('L10_preco_pvu_mais_cbio')))
col3.metric("L14 - VHP BRL/saco PVU", fmt_br(result_bloco4.get('L14_vhp_brl_saco_pvu')))
col4.metric("L15 - VHP Cents/lb PVU", fmt_br(result_bloco4.get('L15_vhp_cents_lb_pvu')))
col1, col2, col3, col4 = st.columns(4)
col1.metric("L16 - VHP Cents/lb FOB", fmt_br(result_bloco4.get('L16_vhp_cents_lb_fob')))
col2.metric("L17 - Cristal BRL/saca PVU", fmt_br(result_bloco4.get('L17_cristal_brl_saca_pvu')))
col3.metric("L18 - Cristal Cents/lb PVU", fmt_br(result_bloco4.get('L18_cristal_cents_lb_pvu')))
col4.metric("L19 - Cristal Cents/lb FOB", fmt_br(result_bloco4.get('L19_cristal_cents_lb_fob')))

# BLOCO 5
st.header("📦 BLOCO 5 - Paridade Açúcar")

st.subheader("SUB-BLOCO 5.1 - Sugar VHP")
col1, col2, col3, col4 = st.columns(4)
col1.metric("C33 - VHP BRL/saca PVU", fmt_br(result_bloco5.get('C33_vhp_brl_saca_pvu')))
col2.metric("C34 - VHP Cents/lb PVU", fmt_br(result_bloco5.get('C34_vhp_cents_lb_pvu')))
col3.metric("C35 - VHP Cents/lb FOB", fmt_br(result_bloco5.get('C35_vhp_cents_lb_fob')))

st.subheader("SUB-BLOCO 5.2 - Cristal Esalq")
col1, col2, col3, col4 = st.columns(4)
col1.metric("F33 - VHP BRL/saco PVU", fmt_br(result_bloco5.get('F33_vhp_brl_saco_pvu')))
col2.metric("F34 - VHP Cents/lb PVU", fmt_br(result_bloco5.get('F34_vhp_cents_lb_pvu')))
col3.metric("F35 - VHP Cents/lb FOB", fmt_br(result_bloco5.get('F35_vhp_cents_lb_fob')))
col4.metric("F36 - Cristal BRL/saca PVU", fmt_br(result_bloco5.get('F36_cristal_brl_saca_pvu')))

st.subheader("SUB-BLOCO 5.3 - Cristal Mercado Interno")
col1, col2, col3, col4 = st.columns(4)
col1.metric("I33 - VHP BRL/saco PVU", fmt_br(result_bloco5.get('I33_vhp_brl_saco_pvu')))
col2.metric("I34 - VHP Cents/lb PVU", fmt_br(result_bloco5.get('I34_vhp_cents_lb_pvu')))
col3.metric("I35 - VHP Cents/lb FOB", fmt_br(result_bloco5.get('I35_vhp_cents_lb_fob')))
col4.metric("I36 - Cristal BRL/saca PVU", fmt_br(result_bloco5.get('I36_cristal_brl_saca_pvu')))

st.subheader("SUB-BLOCO 5.4 - Cristal Exportação")
col1, col2, col3, col4 = st.columns(4)
col1.metric("L33 - VHP BRL/saco PVU", fmt_br(result_bloco5.get('L33_vhp_brl_saco_pvu')))
col2.metric("L34 - VHP Cents/lb PVU", fmt_br(result_bloco5.get('L34_vhp_cents_lb_pvu')))
col3.metric("L35 - VHP Cents/lb FOB", fmt_br(result_bloco5.get('L35_vhp_cents_lb_fob')))
col4.metric("L36 - Cristal BRL/saca PVU", fmt_br(result_bloco5.get('L36_cristal_brl_saca_pvu')))

st.subheader("SUB-BLOCO 5.5 - Cristal Exportação Malha 30")
col1, col2, col3, col4 = st.columns(4)
col1.metric("O33 - VHP BRL/saco PVU", fmt_br(result_bloco5.get('O33_vhp_brl_saco_pvu')))
col2.metric("O34 - VHP Cents/lb PVU", fmt_br(result_bloco5.get('O34_vhp_cents_lb_pvu')))
col3.metric("O35 - VHP Cents/lb FOB", fmt_br(result_bloco5.get('O35_vhp_cents_lb_fob')))
col4.metric("O36 - Cristal BRL/saca PVU", fmt_br(result_bloco5.get('O36_cristal_brl_saca_pvu')))

# ============================================================================
# TABELAS-RESUMO (BLOCO 6)
# ============================================================================

st.header("📊 TABELAS-RESUMO")

# PVU BRL/saca (linhas 3-8)
st.subheader("PVU BRL/saca")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("O3 = F33", fmt_br(result_bloco5.get('F33_vhp_brl_saco_pvu')))
col2.metric("O4 = O33", fmt_br(result_bloco5.get('O33_vhp_brl_saco_pvu')))
col3.metric("O5 = I14", fmt_br(result_bloco3.get('I14_vhp_brl_saco_pvu')))
col4.metric("O6 = L33", fmt_br(result_bloco5.get('L33_vhp_brl_saco_pvu')))
col5.metric("O7 = C33", fmt_br(result_bloco5.get('C33_vhp_brl_saca_pvu')))
col6.metric("O8 = L14", fmt_br(result_bloco4.get('L14_vhp_brl_saco_pvu')))

# FOB Cents/lb (linhas 14-19)
st.subheader("FOB Cents/lb")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("O14 = F35", fmt_br(result_bloco5.get('F35_vhp_cents_lb_fob')))
col2.metric("O15 = O35", fmt_br(result_bloco5.get('O35_vhp_cents_lb_fob')))
col3.metric("O16 = L35", fmt_br(result_bloco5.get('L35_vhp_cents_lb_fob')))
col4.metric("O17 = I16", fmt_br(result_bloco3.get('I16_vhp_cents_lb_fob')))
col5.metric("O18 = C35", fmt_br(result_bloco5.get('C35_vhp_cents_lb_fob')))
col6.metric("O19 = L16", fmt_br(result_bloco4.get('L16_vhp_cents_lb_fob')))

