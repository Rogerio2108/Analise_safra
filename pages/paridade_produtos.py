"""
================================================================================
PARIDADE PRODUTOS - MÓDULO DE CÁLCULOS
================================================================================
Este módulo contém as funções de cálculo de paridade de produtos (etanol e açúcar)
usadas pela interface Streamlit app_paridade_produtos.py
================================================================================
"""

import re

# ============================================================================
# CONSTANTES
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
CREDITO_TRIBUTARIO_HIDRATADO_POR_LITRO = 0.24  # BRL/L

# Fatores de conversão etanol → VHP
FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP = 32.669
FATOR_M3_HIDRATADO_EXPORT_PARA_SACA_VHP = 31.304
FATOR_M3_ANIDRO_INTERNO_PARA_SACA_VHP = 33.712
FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP = 31.504

# Fator de desconto VHP FOB (1.042 = 4.2%)
FATOR_DESCONTO_VHP_FOB = 1.042

# Impostos Esalq
IMPOSTOS_ESALQ = 0.0985  # 9.85%
FATOR_ESALQ_SEM_IMPOSTOS = 0.9015  # 1 - 0.0985

# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

def parse_ptbr_number(texto):
    """
    Converte string em formato brasileiro (1.234,56) para float.
    
    Args:
        texto: String no formato brasileiro (ex: "1.234,56")
    
    Returns:
        float: Número convertido
    """
    if texto is None or texto == "":
        return None
    
    # Remove espaços
    texto = str(texto).strip()
    
    # Remove pontos (separadores de milhar)
    texto = texto.replace('.', '')
    
    # Substitui vírgula por ponto
    texto = texto.replace(',', '.')
    
    try:
        return float(texto)
    except ValueError:
        return None

def fmt_br(valor, casas=2):
    """
    Formata número no padrão brasileiro: 1.234.567,89
    
    Args:
        valor: Número a formatar
        casas: Número de casas decimais
    
    Returns:
        str: Número formatado no padrão brasileiro
    """
    if valor is None:
        return ""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ============================================================================
# FUNÇÕES DE CÁLCULO DE PARIDADES
# ============================================================================

def calc_anidro_exportacao(inputs, globais):
    """
    BLOCO 1 — ANIDRO EXPORTAÇÃO
    
    Args:
        inputs: dict com:
            - preco_anidro_fob_usd: Preço FOB USD/m³
            - cambio_brl_usd: Câmbio USD/BRL
            - frete_porto_usina_brl: Frete Porto-Usina BRL/m³
            - terminal_brl: Terminal BRL/m³
            - supervisao_documentos_brl: Supervisão/Doc BRL/m³
            - custos_adicionais_demurrage: Custos Adicionais/Demurrage BRL/m³
        globais: dict com parâmetros globais
    
    Returns:
        dict: {'values': {...}, 'meta': {'celulas': {...}}, 'errors': [...]}
    """
    errors = []
    values = {}
    celulas = {}
    
    try:
        preco_anidro_fob_usd = inputs.get('preco_anidro_fob_usd', 0)
        cambio_brl_usd = inputs.get('cambio_brl_usd', globais.get('cambio_brl_usd', 1))
        frete_porto_usina_brl = inputs.get('frete_porto_usina_brl', 0)
        terminal_brl = inputs.get('terminal_brl', 0)
        supervisao_documentos_brl = inputs.get('supervisao_documentos_brl', 0)
        custos_adicionais_demurrage = inputs.get('custos_adicionais_demurrage', 0)
        
        terminal_usd_ton = globais.get('terminal_usd_por_ton', 0)
        frete_brl_ton = globais.get('frete_brl_por_ton', 0)
        
        # Preço líquido PVU
        preco_liquido_pvu = (preco_anidro_fob_usd * cambio_brl_usd) - frete_porto_usina_brl - terminal_brl - supervisao_documentos_brl - custos_adicionais_demurrage
        values['preco_liquido_pvu'] = preco_liquido_pvu
        
        # Equivalente VHP BRL/saca PVU
        vhp_brl_saca_pvu = preco_liquido_pvu / FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP
        values['vhp_brl_saca_pvu'] = vhp_brl_saca_pvu
        
        # Equivalente Cents/lb PVU
        vhp_cents_lb_pvu = ((vhp_brl_saca_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd / FATOR_DESCONTO_VHP_FOB
        values['vhp_cents_lb_pvu'] = vhp_cents_lb_pvu
        
        # Equivalente Cents/lb FOB
        if terminal_usd_ton and frete_brl_ton:
            vhp_cents_lb_fob = (((((preco_liquido_pvu) / FATOR_M3_ANIDRO_EXPORT_PARA_SACA_VHP) * SACAS_POR_TON) + frete_brl_ton + (terminal_usd_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON / cambio_brl_usd) / FATOR_DESCONTO_VHP_FOB
            values['vhp_cents_lb_fob'] = vhp_cents_lb_fob
        else:
            values['vhp_cents_lb_fob'] = None
            
    except Exception as e:
        errors.append(f"Erro ao calcular anidro exportação: {str(e)}")
    
    return {
        'values': values,
        'meta': {'celulas': celulas},
        'errors': errors
    }

def calc_hidratado_exportacao(inputs, globais):
    """
    BLOCO 2 — HIDRATADO EXPORTAÇÃO
    
    Args:
        inputs: dict com:
            - preco_hidratado_fob_usd: Preço FOB USD/m³
            - cambio_brl_usd: Câmbio USD/BRL
            - frete_porto_usina_brl: Frete Porto-Usina BRL/m³
            - terminal_brl: Terminal BRL/m³
            - supervisao_documentos_brl: Supervisão/Doc BRL/m³
        globais: dict com parâmetros globais
    
    Returns:
        dict: {'values': {...}, 'meta': {'celulas': {...}}, 'errors': [...]}
    """
    errors = []
    values = {}
    celulas = {}
    
    try:
        preco_hidratado_fob_usd = inputs.get('preco_hidratado_fob_usd', 0)
        cambio_brl_usd = inputs.get('cambio_brl_usd', globais.get('cambio_brl_usd', 1))
        frete_porto_usina_brl = inputs.get('frete_porto_usina_brl', 0)
        terminal_brl = inputs.get('terminal_brl', 0)
        supervisao_documentos_brl = inputs.get('supervisao_documentos_brl', 0)
        
        terminal_usd_ton = globais.get('terminal_usd_por_ton', 0)
        frete_brl_ton = globais.get('frete_brl_por_ton', 0)
        
        # Preço líquido PVU
        preco_liquido_pvu = (preco_hidratado_fob_usd * cambio_brl_usd) - frete_porto_usina_brl - terminal_brl - supervisao_documentos_brl
        values['preco_liquido_pvu'] = preco_liquido_pvu
        
        # Equivalente VHP BRL/saca PVU
        vhp_brl_saca_pvu = preco_liquido_pvu / FATOR_M3_HIDRATADO_EXPORT_PARA_SACA_VHP
        values['vhp_brl_saca_pvu'] = vhp_brl_saca_pvu
        
        # Equivalente Cents/lb PVU
        vhp_cents_lb_pvu = ((vhp_brl_saca_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd / FATOR_DESCONTO_VHP_FOB
        values['vhp_cents_lb_pvu'] = vhp_cents_lb_pvu
        
        # Equivalente Cents/lb FOB
        if terminal_usd_ton and frete_brl_ton:
            vhp_cents_lb_fob = ((((((preco_liquido_pvu) / 32.669) * SACAS_POR_TON) + frete_brl_ton + (terminal_usd_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON / cambio_brl_usd) / FATOR_DESCONTO_VHP_FOB)
            values['vhp_cents_lb_fob'] = vhp_cents_lb_fob
        else:
            values['vhp_cents_lb_fob'] = None
            
    except Exception as e:
        errors.append(f"Erro ao calcular hidratado exportação: {str(e)}")
    
    return {
        'values': values,
        'meta': {'celulas': celulas},
        'errors': errors
    }

def calc_anidro_mi(inputs, deps, globais):
    """
    BLOCO 3 — ANIDRO MERCADO INTERNO
    
    Args:
        inputs: dict com:
            - preco_anidro_com_impostos: Preço com impostos BRL/m³
            - pis_cofins: PIS/COFINS BRL/m³
            - contribuicao_agroindustria: Contribuição Agroindústria (percentual)
            - valor_cbio_bruto: Valor CBIO bruto BRL/CBIO
        deps: dict com dependências:
            - equivalente_anidro: Equivalente anidro do hidratado
            - preco_liquido_pvu_hidratado: Preço líquido PVU do hidratado
        globais: dict com parâmetros globais
    
    Returns:
        dict: {'values': {...}, 'meta': {'celulas': {...}}, 'errors': [...]}
    """
    errors = []
    values = {}
    celulas = {}
    
    try:
        preco_anidro_com_impostos = inputs.get('preco_anidro_com_impostos', 0)
        pis_cofins = inputs.get('pis_cofins', 0)
        contribuicao_agroindustria = inputs.get('contribuicao_agroindustria', 0)
        valor_cbio_bruto = inputs.get('valor_cbio_bruto', 0)
        
        cambio_brl_usd = globais.get('cambio_brl_usd', 1)
        terminal_usd_ton = globais.get('terminal_usd_por_ton', 0)
        frete_brl_ton = globais.get('frete_brl_por_ton', 0)
        
        # Preço líquido PVU
        preco_liquido_pvu = (preco_anidro_com_impostos * (1 - contribuicao_agroindustria)) - pis_cofins
        values['preco_liquido_pvu'] = preco_liquido_pvu
        
        # Valor CBIO líquido por CBIO
        valor_cbio_liquido_por_cbio = (valor_cbio_bruto * 0.7575) * 0.6
        
        # Valor CBIO líquido por m³
        valor_cbio_liquido_por_m3 = (valor_cbio_liquido_por_cbio / FC_ANIDRO_LITROS_POR_CBIO) * 1000
        
        # Preço PVU + CBIO
        preco_pvu_mais_cbio = preco_liquido_pvu + valor_cbio_liquido_por_m3
        values['preco_pvu_mais_cbio'] = preco_pvu_mais_cbio
        
        # Equivalente Hidratado
        equivalente_anidro = preco_liquido_pvu / (1 + FATOR_CONV_ANIDRO_HIDRATADO)
        values['equivalente_anidro'] = equivalente_anidro
        
        # Equivalente VHP BRL/saco PVU
        vhp_brl_saco_pvu = preco_pvu_mais_cbio / FATOR_M3_ANIDRO_INTERNO_PARA_SACA_VHP
        values['vhp_brl_saco_pvu'] = vhp_brl_saco_pvu
        
        # Equivalente VHP Cents/lb PVU
        vhp_cents_lb_pvu = (((vhp_brl_saco_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd)
        values['vhp_cents_lb_pvu'] = vhp_cents_lb_pvu
        
        # Equivalente VHP Cents/lb FOB
        if terminal_usd_ton and frete_brl_ton:
            vhp_cents_lb_fob = (((vhp_cents_lb_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd)
            values['vhp_cents_lb_fob'] = vhp_cents_lb_fob
        else:
            values['vhp_cents_lb_fob'] = None
        
        # Prêmio Anidro/Hidratado Líquido
        preco_liquido_pvu_hidratado = deps.get('preco_liquido_pvu_hidratado')
        if preco_liquido_pvu_hidratado and preco_liquido_pvu_hidratado != 0:
            premio_anidro_hidratado_liquido = (preco_liquido_pvu / preco_liquido_pvu_hidratado) - 1
            values['premio_anidro_hidratado_liquido'] = premio_anidro_hidratado_liquido
        else:
            values['premio_anidro_hidratado_liquido'] = None
            
    except Exception as e:
        errors.append(f"Erro ao calcular anidro mercado interno: {str(e)}")
    
    return {
        'values': values,
        'meta': {'celulas': celulas},
        'errors': errors
    }

def calc_hidratado_mi(inputs, deps, globais):
    """
    BLOCO 4 — HIDRATADO MERCADO INTERNO
    
    Args:
        inputs: dict com:
            - preco_hidratado_rp_com_impostos: Preço RP com impostos BRL/m³
            - pis_cofins: PIS/COFINS BRL/m³
            - icms: Alíquota ICMS (percentual)
            - contribuicao_agroindustria: Contribuição Agroindústria (percentual)
            - valor_cbio_bruto: Valor CBIO bruto BRL/CBIO
            - premio_fisico_pvu: Prêmio físico PVU
            - fobizacao_container_brl_ton: Fobização container BRL/ton
        deps: dict com dependências (não usado neste bloco)
        globais: dict com parâmetros globais
    
    Returns:
        dict: {'values': {...}, 'meta': {'celulas': {...}}, 'errors': [...]}
    """
    errors = []
    values = {}
    celulas = {}
    
    try:
        preco_hidratado_rp_com_impostos = inputs.get('preco_hidratado_rp_com_impostos', 0)
        pis_cofins = inputs.get('pis_cofins', 0)
        icms = inputs.get('icms', 0)
        contribuicao_agroindustria = inputs.get('contribuicao_agroindustria', 0)
        valor_cbio_bruto = inputs.get('valor_cbio_bruto', 0)
        premio_fisico_pvu = inputs.get('premio_fisico_pvu', None)
        fobizacao_container_brl_ton = inputs.get('fobizacao_container_brl_ton', 0)
        
        cambio_brl_usd = globais.get('cambio_brl_usd', 1)
        terminal_usd_ton = globais.get('terminal_usd_por_ton', 0)
        frete_brl_ton = globais.get('frete_brl_por_ton', 0)
        custo_c5 = globais.get('custo_c5', 0)
        
        # Preço líquido PVU
        preco_liquido_pvu = ((preco_hidratado_rp_com_impostos * (1 - contribuicao_agroindustria)) * (1 - icms)) - pis_cofins
        values['preco_liquido_pvu'] = preco_liquido_pvu
        
        # Valor CBIO líquido por CBIO
        valor_cbio_liquido_por_cbio = (valor_cbio_bruto * 0.7575) * 0.6
        
        # Valor CBIO líquido por m³
        valor_cbio_liquido_por_m3 = (valor_cbio_liquido_por_cbio / FC_HIDRATADO_LITROS_POR_CBIO) * 1000
        
        # Preço PVU + CBIO
        preco_pvu_mais_cbio = preco_liquido_pvu + valor_cbio_liquido_por_m3
        values['preco_pvu_mais_cbio'] = preco_pvu_mais_cbio
        
        # Equivalente Anidro
        equivalente_anidro = preco_liquido_pvu * (1 + FATOR_CONV_ANIDRO_HIDRATADO)
        values['equivalente_anidro'] = equivalente_anidro
        
        # Crédito tributário
        credito_tributario_brl_m3 = 240  # 0.24 BRL/L * 1000 L/m³
        
        # Preço PVU + CBIO + Crédito
        preco_pvu_cbio_credito = preco_pvu_mais_cbio + credito_tributario_brl_m3
        
        # Equivalente VHP BRL/saco PVU
        vhp_brl_saco_pvu = preco_pvu_mais_cbio / FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP
        values['vhp_brl_saco_pvu'] = vhp_brl_saco_pvu
        
        # Equivalente VHP Cents/lb PVU
        vhp_cents_lb_pvu = (((vhp_brl_saco_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd)
        values['vhp_cents_lb_pvu'] = vhp_cents_lb_pvu
        
        # Equivalente VHP Cents/lb FOB
        if terminal_usd_ton and frete_brl_ton:
            vhp_cents_lb_fob = ((((((preco_pvu_mais_cbio) / FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP) * SACAS_POR_TON) + frete_brl_ton + (terminal_usd_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON / cambio_brl_usd) / FATOR_DESCONTO_VHP_FOB)
            values['vhp_cents_lb_fob'] = vhp_cents_lb_fob
        else:
            values['vhp_cents_lb_fob'] = None
        
        # Equivalente Cristal BRL/Saca PVU
        cristal_brl_saca_pvu = None
        if premio_fisico_pvu is not None:
            cristal_cents_lb_pvu = ((((((preco_pvu_mais_cbio) / FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP) * SACAS_POR_TON) + (premio_fisico_pvu * cambio_brl_usd)) / FATOR_CWT_POR_TON / cambio_brl_usd))
            cristal_brl_saca_pvu = (cristal_cents_lb_pvu * FATOR_CWT_POR_TON / SACAS_POR_TON) * cambio_brl_usd
            values['cristal_brl_saca_pvu'] = cristal_brl_saca_pvu
        
        # Equivalente Cristal Cents/lb FOB
        if frete_brl_ton and fobizacao_container_brl_ton and premio_fisico_pvu is not None:
            cristal_cents_lb_fob = (((((((preco_pvu_mais_cbio) / FATOR_M3_HIDRATADO_INTERNO_PARA_SACA_VHP) * SACAS_POR_TON) + frete_brl_ton + fobizacao_container_brl_ton) + (premio_fisico_pvu * cambio_brl_usd)) / FATOR_CWT_POR_TON / cambio_brl_usd)
            values['cristal_cents_lb_fob'] = cristal_cents_lb_fob
        else:
            values['cristal_cents_lb_fob'] = None
            
    except Exception as e:
        errors.append(f"Erro ao calcular hidratado mercado interno: {str(e)}")
    
    return {
        'values': values,
        'meta': {'celulas': celulas},
        'errors': errors
    }

def calc_acucar(inputs, globais):
    """
    BLOCO 5 — PARIDADE AÇÚCAR
    
    Args:
        inputs: dict com:
            - sugar_ny_fob_cents_lb: NY11 FOB cents/lb
            - premio_desconto_cents_lb: Prêmio/desconto cents/lb
            - premio_pol: Prêmio POL (percentual)
            - esalq_brl_saca: Preço Esalq BRL/saca
            - impostos_esalq: Impostos Esalq (percentual)
            - premio_fisico_pvu: Prêmio físico PVU
            - premio_fisico_fob: Prêmio físico FOB
            - premio_fisico_malha30: Prêmio físico Malha 30
            - fobizacao_container_brl_ton_o31: Fobização container BRL/ton
            - frete_brl_ton_o32: Frete BRL/ton
        globais: dict com parâmetros globais
    
    Returns:
        dict: {'values': {...}, 'meta': {'celulas': {...}}, 'errors': [...]}
    """
    errors = []
    values = {}
    celulas = {}
    
    try:
        sugar_ny_fob_cents_lb = inputs.get('sugar_ny_fob_cents_lb', 0)
        premio_desconto_cents_lb = inputs.get('premio_desconto_cents_lb', 0)
        premio_pol = inputs.get('premio_pol', 0)
        esalq_brl_saca = inputs.get('esalq_brl_saca', None)
        impostos_esalq = inputs.get('impostos_esalq', IMPOSTOS_ESALQ)
        premio_fisico_pvu = inputs.get('premio_fisico_pvu', None)
        premio_fisico_fob = inputs.get('premio_fisico_fob', None)
        premio_fisico_malha30 = inputs.get('premio_fisico_malha30', None)
        fobizacao_container_brl_ton_o31 = inputs.get('fobizacao_container_brl_ton_o31', 0)
        frete_brl_ton_o32 = inputs.get('frete_brl_ton_o32', 0)
        
        cambio_brl_usd = globais.get('cambio_brl_usd', 1)
        terminal_usd_ton = globais.get('terminal_usd_por_ton', 0)
        frete_brl_ton = globais.get('frete_brl_por_ton', 0)
        custo_cristal_vs_vhp = globais.get('custo_cristal_vs_vhp', 0)
        custo_c5 = globais.get('custo_c5', 0)
        custo_c6 = globais.get('custo_c6', 0)
        custo_c7 = globais.get('custo_c7', 0)
        custo_c8 = globais.get('custo_c8', 0)
        
        # SUB-BLOCO 5.1 — SUGAR VHP
        sugar_ny_pol_cents_lb = (sugar_ny_fob_cents_lb + premio_desconto_cents_lb) * (1 + premio_pol)
        sugar_vhp_pvu_brl_saca = (((sugar_ny_pol_cents_lb * FATOR_CWT_POR_TON) - terminal_usd_ton - (frete_brl_ton / cambio_brl_usd)) / SACAS_POR_TON) * cambio_brl_usd
        sugar_vhp_pvu_cents_lb = ((sugar_vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd
        sugar_vhp_fob_cents_lb = sugar_ny_pol_cents_lb
        
        values['vhp_brl_saca_pvu'] = sugar_vhp_pvu_brl_saca
        values['vhp_cents_lb_pvu'] = sugar_vhp_pvu_cents_lb
        values['vhp_cents_lb_fob'] = sugar_vhp_fob_cents_lb
        
        # SUB-BLOCO 5.2 — CRISTAL ESALQ
        if esalq_brl_saca is not None:
            sugar_esalq_cristal_pvu_brl_saca = esalq_brl_saca * (1 - impostos_esalq)
            sugar_esalq_vhp_pvu_brl_saca = sugar_esalq_cristal_pvu_brl_saca - custo_cristal_vs_vhp
            sugar_esalq_vhp_pvu_cents_lb = (((sugar_esalq_vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd)
            
            if frete_brl_ton:
                sugar_esalq_vhp_fob_cents_lb = ((((((sugar_esalq_vhp_pvu_brl_saca) * SACAS_POR_TON) + frete_brl_ton + (terminal_usd_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON / cambio_brl_usd))
                values['vhp_cents_lb_fob_esalq'] = sugar_esalq_vhp_fob_cents_lb
            else:
                values['vhp_cents_lb_fob_esalq'] = None
            
            sugar_esalq_cristal_pvu_cents_lb = (((sugar_esalq_cristal_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd) - (15 / FATOR_CWT_POR_TON / cambio_brl_usd)
            
            if frete_brl_ton and fobizacao_container_brl_ton_o31:
                sugar_esalq_cristal_fob_cents_lb = (((sugar_esalq_cristal_pvu_brl_saca * SACAS_POR_TON) + frete_brl_ton + fobizacao_container_brl_ton_o31) / 22.04622) / cambio_brl_usd
                values['cristal_cents_lb_fob_esalq'] = sugar_esalq_cristal_fob_cents_lb
            else:
                values['cristal_cents_lb_fob_esalq'] = None
            
            values['vhp_brl_saco_pvu_esalq'] = sugar_esalq_vhp_pvu_brl_saca
            values['vhp_cents_lb_pvu_esalq'] = sugar_esalq_vhp_pvu_cents_lb
            values['cristal_brl_saca_pvu_esalq'] = sugar_esalq_cristal_pvu_brl_saca
            values['cristal_cents_lb_pvu_esalq'] = sugar_esalq_cristal_pvu_cents_lb
        
        # SUB-BLOCO 5.3 — CRISTAL MERCADO INTERNO
        if premio_fisico_pvu is not None:
            sugar_ny_usd_ton = sugar_ny_fob_cents_lb * 22.04622
            sugar_pvu_usd_ton = sugar_ny_usd_ton + premio_fisico_pvu
            sugar_pvu_brl_ton = sugar_pvu_usd_ton * cambio_brl_usd
            sugar_interno_cristal_pvu_brl_saca = sugar_pvu_brl_ton / SACAS_POR_TON
            sugar_interno_vhp_pvu_brl_saca = sugar_interno_cristal_pvu_brl_saca - custo_cristal_vs_vhp
            sugar_interno_vhp_pvu_cents_lb = (((sugar_interno_vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd)
            
            if frete_brl_ton:
                sugar_interno_vhp_fob_cents_lb = ((((((sugar_interno_vhp_pvu_brl_saca) * SACAS_POR_TON) + frete_brl_ton + (terminal_usd_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON / cambio_brl_usd))
                values['vhp_cents_lb_fob_mi'] = sugar_interno_vhp_fob_cents_lb
            else:
                values['vhp_cents_lb_fob_mi'] = None
            
            sugar_interno_cristal_pvu_cents_lb = ((sugar_interno_cristal_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd
            
            if fobizacao_container_brl_ton_o31 and frete_brl_ton_o32:
                sugar_interno_cristal_fob_cents_lb = ((sugar_pvu_brl_ton + fobizacao_container_brl_ton_o31 + frete_brl_ton_o32) / FATOR_CWT_POR_TON) / cambio_brl_usd
                values['cristal_cents_lb_fob_mi'] = sugar_interno_cristal_fob_cents_lb
            else:
                values['cristal_cents_lb_fob_mi'] = None
            
            values['vhp_brl_saco_pvu_mi'] = sugar_interno_vhp_pvu_brl_saca
            values['vhp_cents_lb_pvu_mi'] = sugar_interno_vhp_pvu_cents_lb
            values['cristal_brl_saca_pvu_mi'] = sugar_interno_cristal_pvu_brl_saca
            values['cristal_cents_lb_pvu_mi'] = sugar_interno_cristal_pvu_cents_lb
        
        # SUB-BLOCO 5.4 — CRISTAL EXPORTAÇÃO
        if premio_fisico_fob is not None and fobizacao_container_brl_ton_o31 and frete_brl_ton_o32:
            sugar_ny_usd_ton_export = sugar_ny_fob_cents_lb * 22.04622
            sugar_fob_usd_ton_export = sugar_ny_usd_ton_export + premio_fisico_fob
            sugar_fob_brl_ton_export = sugar_fob_usd_ton_export * cambio_brl_usd
            sugar_export_cristal_pvu_brl_saca = (sugar_fob_brl_ton_export - fobizacao_container_brl_ton_o31 - frete_brl_ton_o32) / SACAS_POR_TON
            sugar_export_vhp_pvu_brl_saca = sugar_export_cristal_pvu_brl_saca - custo_cristal_vs_vhp
            sugar_export_vhp_pvu_cents_lb = (((sugar_export_vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd)
            sugar_export_vhp_fob_cents_lb = ((((((sugar_export_vhp_pvu_brl_saca) * SACAS_POR_TON) + frete_brl_ton_o32 + (terminal_usd_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON / cambio_brl_usd))
            sugar_export_cristal_pvu_cents_lb = ((sugar_export_cristal_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd
            sugar_export_cristal_fob_cents_lb = sugar_fob_usd_ton_export / 22.04622
            
            values['vhp_brl_saco_pvu_exp'] = sugar_export_vhp_pvu_brl_saca
            values['vhp_cents_lb_pvu_exp'] = sugar_export_vhp_pvu_cents_lb
            values['vhp_cents_lb_fob_exp'] = sugar_export_vhp_fob_cents_lb
            values['cristal_brl_saca_pvu_exp'] = sugar_export_cristal_pvu_brl_saca
            values['cristal_cents_lb_pvu_exp'] = sugar_export_cristal_pvu_cents_lb
            values['cristal_cents_lb_fob_exp'] = sugar_export_cristal_fob_cents_lb
        
        # SUB-BLOCO 5.5 — CRISTAL EXPORTAÇÃO MALHA 30
        if premio_fisico_malha30 is not None and fobizacao_container_brl_ton_o31 and frete_brl_ton_o32:
            sugar_ny_usd_ton_malha30 = sugar_ny_fob_cents_lb * 22.04622
            sugar_fob_usd_ton_malha30 = sugar_ny_usd_ton_malha30 + premio_fisico_malha30
            sugar_fob_brl_ton_malha30 = sugar_fob_usd_ton_malha30 * cambio_brl_usd
            sugar_malha30_cristal_pvu_brl_saca = (sugar_fob_brl_ton_malha30 - fobizacao_container_brl_ton_o31 - frete_brl_ton_o32) / SACAS_POR_TON
            sugar_malha30_vhp_pvu_brl_saca = sugar_malha30_cristal_pvu_brl_saca - custo_cristal_vs_vhp
            sugar_malha30_vhp_pvu_cents_lb = (((sugar_malha30_vhp_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd)
            sugar_malha30_vhp_fob_cents_lb = ((((((sugar_malha30_vhp_pvu_brl_saca) * SACAS_POR_TON) + frete_brl_ton_o32 + (terminal_usd_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON / cambio_brl_usd))
            sugar_malha30_cristal_pvu_cents_lb = ((sugar_malha30_cristal_pvu_brl_saca * SACAS_POR_TON) / FATOR_CWT_POR_TON) / cambio_brl_usd
            sugar_malha30_cristal_fob_cents_lb = sugar_fob_usd_ton_malha30 / 22.04622
            
            values['vhp_brl_saco_pvu_malha30'] = sugar_malha30_vhp_pvu_brl_saca
            values['vhp_cents_lb_pvu_malha30'] = sugar_malha30_vhp_pvu_cents_lb
            values['vhp_cents_lb_fob_malha30'] = sugar_malha30_vhp_fob_cents_lb
            values['cristal_brl_saca_pvu_malha30'] = sugar_malha30_cristal_pvu_brl_saca
            values['cristal_cents_lb_pvu_malha30'] = sugar_malha30_cristal_pvu_cents_lb
            values['cristal_cents_lb_fob_malha30'] = sugar_malha30_cristal_fob_cents_lb
            
    except Exception as e:
        errors.append(f"Erro ao calcular açúcar: {str(e)}")
    
    return {
        'values': values,
        'meta': {'celulas': celulas},
        'errors': errors
    }

