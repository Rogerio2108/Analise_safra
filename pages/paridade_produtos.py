"""
================================================================================
PARIDADE PRODUTOS
================================================================================
Reprodução EXATA das fórmulas da aba "Paridade Produtos" do Excel.
Cada bloco corresponde a um conjunto de células da planilha original.
"""

# ============================================================================
# CONSTANTES
# ============================================================================

FATOR_VHP_ANIDRO_EXPORT = 32.669
FATOR_VHP_HIDRATADO_EXPORT = 31.304
FATOR_VHP_ANIDRO_INTERNO = 33.712
FATOR_VHP_HIDRATADO_INTERNO = 31.504
FATOR_CWT_POR_TON = 22.0462
FATOR_CWT_POR_TON_ALT = 22.04622
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
        x = x.strip().replace(",", ".").replace(" ", "")
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

def safe_div(numerador, denominador, errors, msg):
    """
    Divisão segura: retorna None se denominador for 0 ou None, e registra erro.
    
    Args:
        numerador: float
        denominador: float ou None
        errors: lista para adicionar mensagens de erro
        msg: mensagem de erro a adicionar se houver divisão por zero
        
    Returns:
        float ou None
    """
    if denominador == 0 or denominador is None:
        errors.append(msg)
        return None
    return numerador / denominador

# ============================================================================
# BLOCO 1 - ANIDRO EXPORTAÇÃO (colunas B/C, linhas 3-12)
# ============================================================================

def calc_anidro_exportacao(inputs, globais):
    """
    BLOCO 1 - ANIDRO EXPORTAÇÃO (colunas B/C, linhas 3-12)
    
    Args:
        inputs: dict com preco_anidro_fob_usd, cambio_brl_usd, frete_porto_usina_brl,
                terminal_brl, supervisao_documentos_brl, custos_adicionais_demurrage
        globais: dict com terminal_usd_por_ton, frete_brl_por_ton, cambio_brl_usd
    
    Returns:
        dict com "values", "errors", "meta"
    """
    errors = []
    values = {}
    meta = {"celulas": {}}
    
    # C3 preco_anidro_fob_usd
    preco_anidro_fob_usd = parse_ptbr_number(inputs.get('preco_anidro_fob_usd', 0))
    meta["celulas"]["preco_anidro_fob_usd"] = "C3"
    
    # C4 cambio_brl_usd
    cambio_brl_usd = parse_ptbr_number(inputs.get('cambio_brl_usd', globais.get('cambio_brl_usd', 0)))
    meta["celulas"]["cambio_brl_usd"] = "C4"
    
    # C5 frete_porto_usina_brl
    frete_porto_usina_brl = parse_ptbr_number(inputs.get('frete_porto_usina_brl', 0))
    meta["celulas"]["frete_porto_usina_brl"] = "C5"
    
    # C6 terminal_brl
    terminal_brl = parse_ptbr_number(inputs.get('terminal_brl', 0))
    meta["celulas"]["terminal_brl"] = "C6"
    
    # C7 supervisao_documentos_brl
    supervisao_documentos_brl = parse_ptbr_number(inputs.get('supervisao_documentos_brl', 0))
    meta["celulas"]["supervisao_documentos_brl"] = "C7"
    
    # C8 custos_adicionais_demurrage
    custos_adicionais_demurrage = parse_ptbr_number(inputs.get('custos_adicionais_demurrage', 0))
    if custos_adicionais_demurrage is None:
        custos_adicionais_demurrage = 0
    meta["celulas"]["custos_adicionais_demurrage"] = "C8"
    
    # Parâmetros globais
    terminal_usd_por_ton = parse_ptbr_number(globais.get('terminal_usd_por_ton', 0))
    frete_brl_por_ton = parse_ptbr_number(globais.get('frete_brl_por_ton', 0))
    
    # C9 preco_liquido_pvu
    # Excel: =((C3*C4)-C5-C6-C7-C8)
    preco_liquido_pvu = (preco_anidro_fob_usd * cambio_brl_usd) - frete_porto_usina_brl - terminal_brl - supervisao_documentos_brl - custos_adicionais_demurrage
    values['preco_liquido_pvu'] = preco_liquido_pvu
    meta["celulas"]["preco_liquido_pvu"] = "C9"
    
    # C10 vhp_brl_saca_pvu
    # Excel: =C9/32.669
    vhp_brl_saca_pvu = preco_liquido_pvu / FATOR_VHP_ANIDRO_EXPORT
    values['vhp_brl_saca_pvu'] = vhp_brl_saca_pvu
    meta["celulas"]["vhp_brl_saca_pvu"] = "C10"
    
    # C11 vhp_cents_lb_pvu
    # Excel: =((C10*20)/22.0462)/C4/1.042
    vhp_cents_lb_pvu = safe_div(
        ((vhp_brl_saca_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON) / FATOR_DESCONTO_VHP_FOB,
        cambio_brl_usd,
        errors,
        "C11 vhp_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_pvu'] = vhp_cents_lb_pvu
    meta["celulas"]["vhp_cents_lb_pvu"] = "C11"
    
    # C12 vhp_cents_lb_fob
    # Excel: =((((((C9)/32.669)*20)+C32+(C30*C4))/22.0462/C4)/1.042)
    temp_c12 = (((preco_liquido_pvu / FATOR_VHP_ANIDRO_EXPORT) * SACAS_POR_TON) + frete_brl_por_ton + (terminal_usd_por_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON
    vhp_cents_lb_fob = safe_div(
        temp_c12 / FATOR_DESCONTO_VHP_FOB,
        cambio_brl_usd,
        errors,
        "C12 vhp_cents_lb_fob: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_fob'] = vhp_cents_lb_fob
    meta["celulas"]["vhp_cents_lb_fob"] = "C12"
    
    return {
        "values": values,
        "errors": errors,
        "meta": meta
    }

# ============================================================================
# BLOCO 2 - HIDRATADO EXPORTAÇÃO (colunas E/F, linhas 3-11)
# ============================================================================

def calc_hidratado_exportacao(inputs, globais):
    """
    BLOCO 2 - HIDRATADO EXPORTAÇÃO (colunas E/F, linhas 3-11)
    
    Args:
        inputs: dict com preco_hidratado_fob_usd, cambio_brl_usd, frete_porto_usina_brl,
                terminal_brl, supervisao_documentos_brl
        globais: dict com terminal_usd_por_ton, frete_brl_por_ton, cambio_brl_usd
    
    Returns:
        dict com "values", "errors", "meta"
    """
    errors = []
    values = {}
    meta = {"celulas": {}}
    
    # F3 preco_hidratado_fob_usd
    preco_hidratado_fob_usd = parse_ptbr_number(inputs.get('preco_hidratado_fob_usd', 0))
    meta["celulas"]["preco_hidratado_fob_usd"] = "F3"
    
    # F4 cambio_brl_usd (derivado de C4)
    cambio_brl_usd = parse_ptbr_number(inputs.get('cambio_brl_usd', globais.get('cambio_brl_usd', 0)))
    meta["celulas"]["cambio_brl_usd"] = "F4"
    
    # F5 frete_porto_usina_brl (derivado de C5)
    frete_porto_usina_brl = parse_ptbr_number(inputs.get('frete_porto_usina_brl', 0))
    meta["celulas"]["frete_porto_usina_brl"] = "F5"
    
    # F6 terminal_brl (derivado de C6)
    terminal_brl = parse_ptbr_number(inputs.get('terminal_brl', 0))
    meta["celulas"]["terminal_brl"] = "F6"
    
    # F7 supervisao_documentos_brl (derivado de C7)
    supervisao_documentos_brl = parse_ptbr_number(inputs.get('supervisao_documentos_brl', 0))
    meta["celulas"]["supervisao_documentos_brl"] = "F7"
    
    # Parâmetros globais
    terminal_usd_por_ton = parse_ptbr_number(globais.get('terminal_usd_por_ton', 0))
    frete_brl_por_ton = parse_ptbr_number(globais.get('frete_brl_por_ton', 0))
    cambio_brl_usd_global = parse_ptbr_number(globais.get('cambio_brl_usd', 0))
    
    # F8 preco_liquido_pvu
    # Excel: =(F3*F4)-F5-F6-F7
    preco_liquido_pvu = (preco_hidratado_fob_usd * cambio_brl_usd) - frete_porto_usina_brl - terminal_brl - supervisao_documentos_brl
    values['preco_liquido_pvu'] = preco_liquido_pvu
    meta["celulas"]["preco_liquido_pvu"] = "F8"
    
    # F9 vhp_brl_saca_pvu
    # Excel: =F8/31.304
    vhp_brl_saca_pvu = preco_liquido_pvu / FATOR_VHP_HIDRATADO_EXPORT
    values['vhp_brl_saca_pvu'] = vhp_brl_saca_pvu
    meta["celulas"]["vhp_brl_saca_pvu"] = "F9"
    
    # F10 vhp_cents_lb_pvu
    # Excel: =((F9*20)/22.0462)/F4/1.042
    vhp_cents_lb_pvu = safe_div(
        ((vhp_brl_saca_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON) / FATOR_DESCONTO_VHP_FOB,
        cambio_brl_usd,
        errors,
        "F10 vhp_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_pvu'] = vhp_cents_lb_pvu
    meta["celulas"]["vhp_cents_lb_pvu"] = "F10"
    
    # F11 vhp_cents_lb_fob
    # Excel: =((((((F8)/32.669)*20)+C32+(C30*C4))/22.0462/C4)/1.042)
    temp_f11 = (((preco_liquido_pvu / 32.669) * SACAS_POR_TON) + frete_brl_por_ton + (terminal_usd_por_ton * cambio_brl_usd_global)) / FATOR_CWT_POR_TON
    vhp_cents_lb_fob = safe_div(
        temp_f11 / FATOR_DESCONTO_VHP_FOB,
        cambio_brl_usd_global,
        errors,
        "F11 vhp_cents_lb_fob: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_fob'] = vhp_cents_lb_fob
    meta["celulas"]["vhp_cents_lb_fob"] = "F11"
    
    return {
        "values": values,
        "errors": errors,
        "meta": meta
    }

# ============================================================================
# BLOCO 3 - ANIDRO MERCADO INTERNO (colunas H/I, linhas 3-22 e 14-19)
# ============================================================================

def calc_anidro_mi(inputs, deps, globais):
    """
    BLOCO 3 - ANIDRO MERCADO INTERNO (colunas H/I, linhas 3-22 e 14-19)
    
    Args:
        inputs: dict com preco_anidro_com_impostos, pis_cofins, contribuicao_agroindustria, valor_cbio_bruto
        deps: dict com equivalente_anidro (L11), preco_liquido_pvu_hidratado (L7)
        globais: dict com cambio_brl_usd, custo_c5, custo_c6, custo_c7, custo_c8
    
    Returns:
        dict com "values", "errors", "meta"
    """
    errors = []
    values = {}
    meta = {"celulas": {}}
    
    # I3 preco_anidro_com_impostos
    preco_anidro_com_impostos = parse_ptbr_number(inputs.get('preco_anidro_com_impostos', 0))
    meta["celulas"]["preco_anidro_com_impostos"] = "I3"
    
    # I4 pis_cofins
    pis_cofins = parse_ptbr_number(inputs.get('pis_cofins', 0))
    meta["celulas"]["pis_cofins"] = "I4"
    
    # I5 contribuicao_agroindustria
    contribuicao_agroindustria = parse_ptbr_number(inputs.get('contribuicao_agroindustria', 0))
    meta["celulas"]["contribuicao_agroindustria"] = "I5"
    
    # I7 valor_cbio_bruto
    valor_cbio_bruto = parse_ptbr_number(inputs.get('valor_cbio_bruto', 0))
    meta["celulas"]["valor_cbio_bruto"] = "I7"
    
    # Dependências
    equivalente_anidro = deps.get('equivalente_anidro')
    preco_liquido_pvu_hidratado = deps.get('preco_liquido_pvu_hidratado')
    
    # Parâmetros globais
    cambio_brl_usd = parse_ptbr_number(globais.get('cambio_brl_usd', 0))
    custo_c5 = parse_ptbr_number(globais.get('custo_c5', 0))
    custo_c6 = parse_ptbr_number(globais.get('custo_c6', 0))
    custo_c7 = parse_ptbr_number(globais.get('custo_c7', 0))
    custo_c8 = parse_ptbr_number(globais.get('custo_c8', 0))
    
    # I6 preco_liquido_pvu
    # Excel: =((I3*(1-I5))-I4)
    preco_liquido_pvu = ((preco_anidro_com_impostos * (1 - contribuicao_agroindustria)) - pis_cofins)
    values['preco_liquido_pvu'] = preco_liquido_pvu
    meta["celulas"]["preco_liquido_pvu"] = "I6"
    
    # I8 valor_cbio_liquido
    # Excel: =(I7*0.7575)*0.6
    valor_cbio_liquido = (valor_cbio_bruto * 0.7575) * SHARE_PRODUTOR_CBIO
    values['valor_cbio_liquido'] = valor_cbio_liquido
    meta["celulas"]["valor_cbio_liquido"] = "I8"
    
    # I9 preco_pvu_mais_cbio
    # Excel: =I6+((I8/712.4)*1000)
    preco_pvu_mais_cbio = preco_liquido_pvu + ((valor_cbio_liquido / FC_ANIDRO_CBIO) * 1000)
    values['preco_pvu_mais_cbio'] = preco_pvu_mais_cbio
    meta["celulas"]["preco_pvu_mais_cbio"] = "I9"
    
    # I10 equivalente_hidratado
    # Excel: =I6/(1+0.0769)
    equivalente_hidratado = preco_liquido_pvu / (1 + FATOR_CONV_ANIDRO_HIDRATADO)
    values['equivalente_hidratado'] = equivalente_hidratado
    meta["celulas"]["equivalente_hidratado"] = "I10"
    
    # I14 vhp_brl_saco_pvu
    # Excel: =(I9/33.712)
    vhp_brl_saco_pvu = (preco_pvu_mais_cbio / FATOR_VHP_ANIDRO_INTERNO)
    values['vhp_brl_saco_pvu'] = vhp_brl_saco_pvu
    meta["celulas"]["vhp_brl_saco_pvu"] = "I14"
    
    # I15 vhp_cents_lb_pvu
    # Excel: =(((I14*20)/22.0462)/C4)
    vhp_cents_lb_pvu = safe_div(
        ((vhp_brl_saco_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON),
        cambio_brl_usd,
        errors,
        "I15 vhp_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_pvu'] = vhp_cents_lb_pvu
    meta["celulas"]["vhp_cents_lb_pvu"] = "I15"
    
    # I16 vhp_cents_lb_fob
    # Excel: =(((I15*20)/22.0462)/C5)
    vhp_cents_lb_fob = safe_div(
        ((vhp_cents_lb_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON) if vhp_cents_lb_pvu is not None else None,
        custo_c5,
        errors,
        "I16 vhp_cents_lb_fob: Divisão por zero (custo_c5=0 ou vazio)"
    )
    values['vhp_cents_lb_fob'] = vhp_cents_lb_fob
    meta["celulas"]["vhp_cents_lb_fob"] = "I16"
    
    # I17 cristal_brl_saca_pvu
    # Excel: =(((I16*20)/22.0462)/C6)
    vhp_cents_lb_fob_temp = vhp_cents_lb_fob if vhp_cents_lb_fob is not None else 0
    cristal_brl_saca_pvu = safe_div(
        ((vhp_cents_lb_fob_temp * SACAS_POR_TON) / FATOR_CWT_POR_TON) if vhp_cents_lb_fob is not None else None,
        custo_c6,
        errors,
        "I17 cristal_brl_saca_pvu: Divisão por zero (custo_c6=0 ou vazio)"
    )
    values['cristal_brl_saca_pvu'] = cristal_brl_saca_pvu
    meta["celulas"]["cristal_brl_saca_pvu"] = "I17"
    
    # I18 cristal_cents_lb_pvu
    # Excel: =(((I17*20)/22.0462)/C7)
    cristal_brl_saca_pvu_temp = cristal_brl_saca_pvu if cristal_brl_saca_pvu is not None else 0
    cristal_cents_lb_pvu = safe_div(
        ((cristal_brl_saca_pvu_temp * SACAS_POR_TON) / FATOR_CWT_POR_TON) if cristal_brl_saca_pvu is not None else None,
        custo_c7,
        errors,
        "I18 cristal_cents_lb_pvu: Divisão por zero (custo_c7=0 ou vazio)"
    )
    values['cristal_cents_lb_pvu'] = cristal_cents_lb_pvu
    meta["celulas"]["cristal_cents_lb_pvu"] = "I18"
    
    # I19 cristal_cents_lb_fob
    # Excel: =(((I18*20)/22.0462)/C8)
    cristal_cents_lb_pvu_temp = cristal_cents_lb_pvu if cristal_cents_lb_pvu is not None else 0
    cristal_cents_lb_fob = safe_div(
        ((cristal_cents_lb_pvu_temp * SACAS_POR_TON) / FATOR_CWT_POR_TON) if cristal_cents_lb_pvu is not None else None,
        custo_c8,
        errors,
        "I19 cristal_cents_lb_fob: Divisão por zero (custo_c8=0 ou vazio)"
    )
    values['cristal_cents_lb_fob'] = cristal_cents_lb_fob
    meta["celulas"]["cristal_cents_lb_fob"] = "I19"
    
    # I21 premio_anidro_hidratado_liquido
    # Excel: =(I6/L11)-1
    premio_anidro_hidratado_liquido = safe_div(
        preco_liquido_pvu,
        equivalente_anidro,
        errors,
        "I21 premio_anidro_hidratado_liquido: Divisão por zero (equivalente_anidro=0 ou vazio)"
    )
    if premio_anidro_hidratado_liquido is not None:
        premio_anidro_hidratado_liquido = premio_anidro_hidratado_liquido - 1
    values['premio_anidro_hidratado_liquido'] = premio_anidro_hidratado_liquido
    meta["celulas"]["premio_anidro_hidratado_liquido"] = "I21"
    
    # I22 premio_anidro_hidratado_contrato
    # Excel: =(I6/L7)-1
    premio_anidro_hidratado_contrato = safe_div(
        preco_liquido_pvu,
        preco_liquido_pvu_hidratado,
        errors,
        "I22 premio_anidro_hidratado_contrato: Divisão por zero (preco_liquido_pvu_hidratado=0 ou vazio)"
    )
    if premio_anidro_hidratado_contrato is not None:
        premio_anidro_hidratado_contrato = premio_anidro_hidratado_contrato - 1
    values['premio_anidro_hidratado_contrato'] = premio_anidro_hidratado_contrato
    meta["celulas"]["premio_anidro_hidratado_contrato"] = "I22"
    
    return {
        "values": values,
        "errors": errors,
        "meta": meta
    }

# ============================================================================
# BLOCO 4 - HIDRATADO MERCADO INTERNO (colunas K/L, linhas 3-22 e 14-19)
# ============================================================================

def calc_hidratado_mi(inputs, deps, globais):
    """
    BLOCO 4 - HIDRATADO MERCADO INTERNO (colunas K/L, linhas 3-22 e 14-19)
    
    Args:
        inputs: dict com preco_hidratado_rp_com_impostos, pis_cofins, icms,
                contribuicao_agroindustria, valor_cbio_bruto, premio_fisico_pvu, fobizacao_container_brl_ton
        deps: dict vazio (não há dependências de outros blocos)
        globais: dict com cambio_brl_usd, terminal_usd_por_ton, frete_brl_por_ton
    
    Returns:
        dict com "values", "errors", "meta"
    """
    errors = []
    values = {}
    meta = {"celulas": {}}
    
    # L3 preco_hidratado_rp_com_impostos
    preco_hidratado_rp_com_impostos = parse_ptbr_number(inputs.get('preco_hidratado_rp_com_impostos', 0))
    meta["celulas"]["preco_hidratado_rp_com_impostos"] = "L3"
    
    # L4 pis_cofins
    pis_cofins = parse_ptbr_number(inputs.get('pis_cofins', 0))
    meta["celulas"]["pis_cofins"] = "L4"
    
    # L5 icms
    icms = parse_ptbr_number(inputs.get('icms', 0))
    meta["celulas"]["icms"] = "L5"
    
    # L6 contribuicao_agroindustria
    contribuicao_agroindustria = parse_ptbr_number(inputs.get('contribuicao_agroindustria', 0))
    meta["celulas"]["contribuicao_agroindustria"] = "L6"
    
    # L8 valor_cbio_bruto
    valor_cbio_bruto = parse_ptbr_number(inputs.get('valor_cbio_bruto', 0))
    meta["celulas"]["valor_cbio_bruto"] = "L8"
    
    # I28 premio_fisico_pvu
    premio_fisico_pvu = parse_ptbr_number(inputs.get('premio_fisico_pvu', 0))
    meta["celulas"]["premio_fisico_pvu"] = "I28"
    
    # L31 fobizacao_container_brl_ton
    fobizacao_container_brl_ton = parse_ptbr_number(inputs.get('fobizacao_container_brl_ton', 0))
    meta["celulas"]["fobizacao_container_brl_ton"] = "L31"
    
    # Parâmetros globais
    cambio_brl_usd = parse_ptbr_number(globais.get('cambio_brl_usd', 0))
    terminal_usd_por_ton = parse_ptbr_number(globais.get('terminal_usd_por_ton', 0))
    frete_brl_por_ton = parse_ptbr_number(globais.get('frete_brl_por_ton', 0))
    cambio_brl_usd_f4 = parse_ptbr_number(globais.get('cambio_brl_usd', 0))  # F4 = C4
    
    # L7 preco_liquido_pvu
    # Excel: =((L3*(1-L6))*(1-L5)-L4)
    preco_liquido_pvu = ((preco_hidratado_rp_com_impostos * (1 - contribuicao_agroindustria)) * (1 - icms) - pis_cofins)
    values['preco_liquido_pvu'] = preco_liquido_pvu
    meta["celulas"]["preco_liquido_pvu"] = "L7"
    
    # L9 valor_cbio_liquido
    # Excel: =(L8*0.7575)*0.6
    valor_cbio_liquido = (valor_cbio_bruto * 0.7575) * SHARE_PRODUTOR_CBIO
    values['valor_cbio_liquido'] = valor_cbio_liquido
    meta["celulas"]["valor_cbio_liquido"] = "L9"
    
    # L10 preco_pvu_mais_cbio
    # Excel: =L7+((L9/749.75)*1000)
    preco_pvu_mais_cbio = preco_liquido_pvu + ((valor_cbio_liquido / FC_HIDRATADO_CBIO) * 1000)
    values['preco_pvu_mais_cbio'] = preco_pvu_mais_cbio
    meta["celulas"]["preco_pvu_mais_cbio"] = "L10"
    
    # L11 equivalente_anidro
    # Excel: =L7*(1+0.0769)
    equivalente_anidro = preco_liquido_pvu * (1 + FATOR_CONV_ANIDRO_HIDRATADO)
    values['equivalente_anidro'] = equivalente_anidro
    meta["celulas"]["equivalente_anidro"] = "L11"
    
    # L12 preco_pvu_cbio_credito
    # Excel: =L10+240
    preco_pvu_cbio_credito = preco_pvu_mais_cbio + CREDITO_TRIBUTARIO_HIDRATADO
    values['preco_pvu_cbio_credito'] = preco_pvu_cbio_credito
    meta["celulas"]["preco_pvu_cbio_credito"] = "L12"
    
    # L14 vhp_brl_saco_pvu
    # Excel: =(L10/31.504)
    vhp_brl_saco_pvu = (preco_pvu_mais_cbio / FATOR_VHP_HIDRATADO_INTERNO)
    values['vhp_brl_saco_pvu'] = vhp_brl_saco_pvu
    meta["celulas"]["vhp_brl_saco_pvu"] = "L14"
    
    # L15 vhp_cents_lb_pvu
    # Excel: =(((L14*20)/22.0462)/F4)
    vhp_cents_lb_pvu = safe_div(
        ((vhp_brl_saco_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON),
        cambio_brl_usd_f4,
        errors,
        "L15 vhp_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_pvu'] = vhp_cents_lb_pvu
    meta["celulas"]["vhp_cents_lb_pvu"] = "L15"
    
    # L16 vhp_cents_lb_fob
    # Excel: =((((((L10)/31.504)*20)+C32+(C30*C4))/22.0462/C4)/1.042)
    temp_l16 = (((preco_pvu_mais_cbio / FATOR_VHP_HIDRATADO_INTERNO) * SACAS_POR_TON) + frete_brl_por_ton + (terminal_usd_por_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON
    vhp_cents_lb_fob = safe_div(
        temp_l16 / FATOR_DESCONTO_VHP_FOB,
        cambio_brl_usd,
        errors,
        "L16 vhp_cents_lb_fob: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_fob'] = vhp_cents_lb_fob
    meta["celulas"]["vhp_cents_lb_fob"] = "L16"
    
    # L18 cristal_cents_lb_pvu (calculado antes de L17)
    # Excel: =((((((L10)/31.504)*20)+(I28*C4))/22.0462/C4))
    temp_l18 = (((preco_pvu_mais_cbio / FATOR_VHP_HIDRATADO_INTERNO) * SACAS_POR_TON) + (premio_fisico_pvu * cambio_brl_usd)) / FATOR_CWT_POR_TON
    cristal_cents_lb_pvu = safe_div(
        temp_l18,
        cambio_brl_usd,
        errors,
        "L18 cristal_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['cristal_cents_lb_pvu'] = cristal_cents_lb_pvu
    meta["celulas"]["cristal_cents_lb_pvu"] = "L18"
    
    # L17 cristal_brl_saca_pvu
    # Excel: =(L18*22.0462/20)*C4
    if cristal_cents_lb_pvu is not None:
        cristal_brl_saca_pvu = (cristal_cents_lb_pvu * FATOR_CWT_POR_TON / SACAS_POR_TON) * cambio_brl_usd
    else:
        cristal_brl_saca_pvu = None
    values['cristal_brl_saca_pvu'] = cristal_brl_saca_pvu
    meta["celulas"]["cristal_brl_saca_pvu"] = "L17"
    
    # L19 cristal_cents_lb_fob
    # Excel: =(((((((L10)/31.504)*20)+C32+L31)+(I28*C4))/22.0462/C4))
    temp_l19 = ((((preco_pvu_mais_cbio / FATOR_VHP_HIDRATADO_INTERNO) * SACAS_POR_TON) + frete_brl_por_ton + fobizacao_container_brl_ton) + (premio_fisico_pvu * cambio_brl_usd)) / FATOR_CWT_POR_TON
    cristal_cents_lb_fob = safe_div(
        temp_l19,
        cambio_brl_usd,
        errors,
        "L19 cristal_cents_lb_fob: Divisão por zero (cambio_brl_usd=0)"
    )
    values['cristal_cents_lb_fob'] = cristal_cents_lb_fob
    meta["celulas"]["cristal_cents_lb_fob"] = "L19"
    
    return {
        "values": values,
        "errors": errors,
        "meta": meta
    }

# ============================================================================
# BLOCO 5 - PARIDADE AÇÚCAR (5 sub-blocos)
# ============================================================================

def calc_acucar(inputs, globais):
    """
    BLOCO 5 - PARIDADE AÇÚCAR (5 sub-blocos)
    
    Args:
        inputs: dict com todos os inputs dos 5 sub-blocos
        globais: dict com cambio_brl_usd, terminal_usd_por_ton, frete_brl_por_ton,
                 fobizacao_container_brl_ton, frete_brl_por_ton_l32, custo_cristal_vs_vhp
    
    Returns:
        dict com "values", "errors", "meta"
    """
    errors = []
    values = {}
    meta = {"celulas": {}}
    
    # Parâmetros comuns
    sugar_ny_fob_cents_lb = parse_ptbr_number(inputs.get('sugar_ny_fob_cents_lb', 0))
    meta["celulas"]["sugar_ny_fob_cents_lb"] = "C26"
    
    premio_desconto_cents_lb = parse_ptbr_number(inputs.get('premio_desconto_cents_lb', 0))
    meta["celulas"]["premio_desconto_cents_lb"] = "C27"
    
    premio_pol = parse_ptbr_number(inputs.get('premio_pol', 0))
    meta["celulas"]["premio_pol"] = "C28"
    
    terminal_usd_por_ton = parse_ptbr_number(globais.get('terminal_usd_por_ton', 0))
    cambio_brl_usd = parse_ptbr_number(globais.get('cambio_brl_usd', 0))
    frete_brl_por_ton = parse_ptbr_number(globais.get('frete_brl_por_ton', 0))
    fobizacao_container_brl_ton = parse_ptbr_number(globais.get('fobizacao_container_brl_ton', 0))
    frete_brl_por_ton_l32 = parse_ptbr_number(globais.get('frete_brl_por_ton_l32', globais.get('frete_brl_por_ton', 0)))
    custo_cristal_vs_vhp = parse_ptbr_number(globais.get('custo_cristal_vs_vhp', 0))
    
    premio_fisico_pvu = parse_ptbr_number(inputs.get('premio_fisico_pvu', 0))
    meta["celulas"]["premio_fisico_pvu"] = "I28"
    
    premio_fisico_fob = parse_ptbr_number(inputs.get('premio_fisico_fob', 0))
    meta["celulas"]["premio_fisico_fob"] = "L28"
    
    premio_fisico_malha30 = parse_ptbr_number(inputs.get('premio_fisico_malha30', 0))
    meta["celulas"]["premio_fisico_malha30"] = "O28"
    
    # ===== SUB-BLOCO 5.1 - SUGAR VHP (B/C) =====
    
    # C29 sugar_ny_pol
    # Excel: =(C26+C27)*(1+C28)
    sugar_ny_pol = (sugar_ny_fob_cents_lb + premio_desconto_cents_lb) * (1 + premio_pol)
    values['sugar_ny_pol'] = sugar_ny_pol
    meta["celulas"]["sugar_ny_pol"] = "C29"
    
    # C33 vhp_brl_saca_pvu
    # Excel: =(((C29*22.0462)-C30-(C32/C31))/20)*C31
    cambio_brl_usd_c31 = cambio_brl_usd  # C31 = C4
    temp_c33 = ((sugar_ny_pol * FATOR_CWT_POR_TON) - terminal_usd_por_ton - safe_div(frete_brl_por_ton, cambio_brl_usd_c31, errors, "C33: Divisão por zero (cambio_brl_usd=0)"))
    if temp_c33 is not None:
        vhp_brl_saca_pvu = (temp_c33 / SACAS_POR_TON) * cambio_brl_usd_c31
    else:
        vhp_brl_saca_pvu = None
        errors.append("C33 vhp_brl_saca_pvu: Erro no cálculo (depende de divisão anterior)")
    values['vhp_brl_saca_pvu'] = vhp_brl_saca_pvu
    meta["celulas"]["vhp_brl_saca_pvu"] = "C33"
    
    # C34 vhp_cents_lb_pvu
    # Excel: =((C33*20)/22.0462)/C31
    vhp_cents_lb_pvu = safe_div(
        ((vhp_brl_saca_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON) if vhp_brl_saca_pvu is not None else None,
        cambio_brl_usd_c31,
        errors,
        "C34 vhp_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_pvu'] = vhp_cents_lb_pvu
    meta["celulas"]["vhp_cents_lb_pvu"] = "C34"
    
    # C35 vhp_cents_lb_fob
    # Excel: =C29
    vhp_cents_lb_fob = sugar_ny_pol
    values['vhp_cents_lb_fob'] = vhp_cents_lb_fob
    meta["celulas"]["vhp_cents_lb_fob"] = "C35"
    
    # ===== SUB-BLOCO 5.2 - CRISTAL ESALQ (E/F) =====
    
    esalq_brl_saca = parse_ptbr_number(inputs.get('esalq_brl_saca', 0))
    meta["celulas"]["esalq_brl_saca"] = "F26"
    
    impostos_esalq = parse_ptbr_number(inputs.get('impostos_esalq', IMPOSTOS_ESALQ))
    meta["celulas"]["impostos_esalq"] = "F27"
    
    # F36 cristal_brl_saca_pvu
    # Excel: =(F26*(1-F27))
    cristal_brl_saca_pvu = (esalq_brl_saca * (1 - impostos_esalq))
    values['cristal_brl_saca_pvu_esalq'] = cristal_brl_saca_pvu
    meta["celulas"]["cristal_brl_saca_pvu_esalq"] = "F36"
    
    # F33 vhp_brl_saco_pvu
    # Excel: =F36-'Custo Cristal vs VHP'!D17
    vhp_brl_saco_pvu = cristal_brl_saca_pvu - custo_cristal_vs_vhp
    values['vhp_brl_saco_pvu_esalq'] = vhp_brl_saco_pvu
    meta["celulas"]["vhp_brl_saco_pvu_esalq"] = "F33"
    
    # F34 vhp_cents_lb_pvu
    # Excel: =(((F33*20)/22.0462)/C4)
    vhp_cents_lb_pvu_esalq = safe_div(
        ((vhp_brl_saco_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON),
        cambio_brl_usd,
        errors,
        "F34 vhp_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_pvu_esalq'] = vhp_cents_lb_pvu_esalq
    meta["celulas"]["vhp_cents_lb_pvu_esalq"] = "F34"
    
    # F35 vhp_cents_lb_fob
    # Excel: =((((((F33)*20)+L32+(C30*C4))/22.0462/C4)))
    temp_f35 = (((vhp_brl_saco_pvu * SACAS_POR_TON) + frete_brl_por_ton_l32 + (terminal_usd_por_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON)
    vhp_cents_lb_fob_esalq = safe_div(
        temp_f35,
        cambio_brl_usd,
        errors,
        "F35 vhp_cents_lb_fob: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_fob_esalq'] = vhp_cents_lb_fob_esalq
    meta["celulas"]["vhp_cents_lb_fob_esalq"] = "F35"
    
    # F37 cristal_cents_lb_pvu
    # Excel: =(((F36*20)/22.0462)/C4)-(15/22.0462/C4)
    temp_f37_1 = safe_div(
        ((cristal_brl_saca_pvu * SACAS_POR_TON) / FATOR_CWT_POR_TON),
        cambio_brl_usd,
        errors,
        "F37 cristal_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    temp_f37_2 = safe_div(
        15 / FATOR_CWT_POR_TON,
        cambio_brl_usd,
        errors,
        "F37 cristal_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    if temp_f37_1 is not None and temp_f37_2 is not None:
        cristal_cents_lb_pvu_esalq = temp_f37_1 - temp_f37_2
    else:
        cristal_cents_lb_pvu_esalq = None
    values['cristal_cents_lb_pvu_esalq'] = cristal_cents_lb_pvu_esalq
    meta["celulas"]["cristal_cents_lb_pvu_esalq"] = "F37"
    
    # F28 frete_santos_usina
    # Excel: =L32
    frete_santos_usina = frete_brl_por_ton_l32
    values['frete_santos_usina'] = frete_santos_usina
    meta["celulas"]["frete_santos_usina"] = "F28"
    
    # F29 fobizacao_container
    # Excel: =L31
    fobizacao_container = fobizacao_container_brl_ton
    values['fobizacao_container'] = fobizacao_container
    meta["celulas"]["fobizacao_container"] = "F29"
    
    # F38 cristal_cents_lb_fob
    # Excel: =(((F36*20)+F28+F29)/22.04622)/C4
    temp_f38 = ((cristal_brl_saca_pvu * SACAS_POR_TON) + frete_santos_usina + fobizacao_container) / FATOR_CWT_POR_TON_ALT
    cristal_cents_lb_fob_esalq = safe_div(
        temp_f38,
        cambio_brl_usd,
        errors,
        "F38 cristal_cents_lb_fob: Divisão por zero (cambio_brl_usd=0)"
    )
    values['cristal_cents_lb_fob_esalq'] = cristal_cents_lb_fob_esalq
    meta["celulas"]["cristal_cents_lb_fob_esalq"] = "F38"
    
    # ===== SUB-BLOCO 5.3 - CRISTAL MERCADO INTERNO (H/I) =====
    
    # I26 = C26
    sugar_ny_fob_cents_lb_i26 = sugar_ny_fob_cents_lb
    meta["celulas"]["sugar_ny_fob_cents_lb_i26"] = "I26"
    
    # I27
    # Excel: =I26*22.04622
    sugar_usd_ton = sugar_ny_fob_cents_lb_i26 * FATOR_CWT_POR_TON_ALT
    values['sugar_usd_ton'] = sugar_usd_ton
    meta["celulas"]["sugar_usd_ton"] = "I27"
    
    # I29 sugar_pvu_usd_ton
    # Excel: =I27+I28
    sugar_pvu_usd_ton = sugar_usd_ton + premio_fisico_pvu
    values['sugar_pvu_usd_ton'] = sugar_pvu_usd_ton
    meta["celulas"]["sugar_pvu_usd_ton"] = "I29"
    
    # I30 sugar_pvu_r_ton
    # Excel: =I29*C4
    sugar_pvu_r_ton = sugar_pvu_usd_ton * cambio_brl_usd
    values['sugar_pvu_r_ton'] = sugar_pvu_r_ton
    meta["celulas"]["sugar_pvu_r_ton"] = "I30"
    
    # I36 cristal_brl_saca_pvu
    # Excel: =(I30)/20
    cristal_brl_saca_pvu_mi = (sugar_pvu_r_ton) / SACAS_POR_TON
    values['cristal_brl_saca_pvu_mi'] = cristal_brl_saca_pvu_mi
    meta["celulas"]["cristal_brl_saca_pvu_mi"] = "I36"
    
    # I33 vhp_brl_saco_pvu
    # Excel: =I36-'Custo Cristal vs VHP'!D17
    vhp_brl_saco_pvu_mi = cristal_brl_saca_pvu_mi - custo_cristal_vs_vhp
    values['vhp_brl_saco_pvu_mi'] = vhp_brl_saco_pvu_mi
    meta["celulas"]["vhp_brl_saco_pvu_mi"] = "I33"
    
    # I34 vhp_cents_lb_pvu
    # Excel: =(((I33*20)/22.0462)/C4)
    vhp_cents_lb_pvu_mi = safe_div(
        ((vhp_brl_saco_pvu_mi * SACAS_POR_TON) / FATOR_CWT_POR_TON),
        cambio_brl_usd,
        errors,
        "I34 vhp_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_pvu_mi'] = vhp_cents_lb_pvu_mi
    meta["celulas"]["vhp_cents_lb_pvu_mi"] = "I34"
    
    # I35 vhp_cents_lb_fob
    # Excel: =((((((I33)*20)+L32+(C30*C4))/22.0462/C4)))
    temp_i35 = (((vhp_brl_saco_pvu_mi * SACAS_POR_TON) + frete_brl_por_ton_l32 + (terminal_usd_por_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON)
    vhp_cents_lb_fob_mi = safe_div(
        temp_i35,
        cambio_brl_usd,
        errors,
        "I35 vhp_cents_lb_fob: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_fob_mi'] = vhp_cents_lb_fob_mi
    meta["celulas"]["vhp_cents_lb_fob_mi"] = "I35"
    
    # I37 cristal_cents_lb_pvu
    # Excel: =((I36*20)/22.0462)/C4
    cristal_cents_lb_pvu_mi = safe_div(
        ((cristal_brl_saca_pvu_mi * SACAS_POR_TON) / FATOR_CWT_POR_TON),
        cambio_brl_usd,
        errors,
        "I37 cristal_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['cristal_cents_lb_pvu_mi'] = cristal_cents_lb_pvu_mi
    meta["celulas"]["cristal_cents_lb_pvu_mi"] = "I37"
    
    # I38 cristal_cents_lb_fob
    # Excel: =((I30+L31+L32)/22.0462)/C4
    temp_i38 = (sugar_pvu_r_ton + fobizacao_container_brl_ton + frete_brl_por_ton_l32) / FATOR_CWT_POR_TON
    cristal_cents_lb_fob_mi = safe_div(
        temp_i38,
        cambio_brl_usd,
        errors,
        "I38 cristal_cents_lb_fob: Divisão por zero (cambio_brl_usd=0)"
    )
    values['cristal_cents_lb_fob_mi'] = cristal_cents_lb_fob_mi
    meta["celulas"]["cristal_cents_lb_fob_mi"] = "I38"
    
    # I41 equivalente_esalq_com_impostos
    # Excel: =I36/0.9015
    equivalente_esalq_com_impostos_mi = cristal_brl_saca_pvu_mi / FATOR_ESALQ_SEM_IMPOSTOS
    values['equivalente_esalq_com_impostos_mi'] = equivalente_esalq_com_impostos_mi
    meta["celulas"]["equivalente_esalq_com_impostos_mi"] = "I41"
    
    # ===== SUB-BLOCO 5.4 - CRISTAL EXPORTAÇÃO (K/L) =====
    
    # L26 = C26
    sugar_ny_fob_cents_lb_l26 = sugar_ny_fob_cents_lb
    meta["celulas"]["sugar_ny_fob_cents_lb_l26"] = "L26"
    
    # L27
    # Excel: =L26*22.04622
    sugar_usd_ton_l27 = sugar_ny_fob_cents_lb_l26 * FATOR_CWT_POR_TON_ALT
    values['sugar_usd_ton_l27'] = sugar_usd_ton_l27
    meta["celulas"]["sugar_usd_ton_l27"] = "L27"
    
    # L29 sugar_fob_usd_ton
    # Excel: =L27+L28
    sugar_fob_usd_ton = sugar_usd_ton_l27 + premio_fisico_fob
    values['sugar_fob_usd_ton'] = sugar_fob_usd_ton
    meta["celulas"]["sugar_fob_usd_ton"] = "L29"
    
    # L30 sugar_fob_r_ton
    # Excel: =L29*C4
    sugar_fob_r_ton = sugar_fob_usd_ton * cambio_brl_usd
    values['sugar_fob_r_ton'] = sugar_fob_r_ton
    meta["celulas"]["sugar_fob_r_ton"] = "L30"
    
    # L36 cristal_brl_saca_pvu
    # Excel: =(L30-L31-L32)/20
    cristal_brl_saca_pvu_exp = (sugar_fob_r_ton - fobizacao_container_brl_ton - frete_brl_por_ton_l32) / SACAS_POR_TON
    values['cristal_brl_saca_pvu_exp'] = cristal_brl_saca_pvu_exp
    meta["celulas"]["cristal_brl_saca_pvu_exp"] = "L36"
    
    # L33 vhp_brl_saco_pvu
    # Excel: =L36-'Custo Cristal vs VHP'!D17
    vhp_brl_saco_pvu_exp = cristal_brl_saca_pvu_exp - custo_cristal_vs_vhp
    values['vhp_brl_saco_pvu_exp'] = vhp_brl_saco_pvu_exp
    meta["celulas"]["vhp_brl_saco_pvu_exp"] = "L33"
    
    # L34 vhp_cents_lb_pvu
    # Excel: =(((L33*20)/22.0462)/C4)
    vhp_cents_lb_pvu_exp = safe_div(
        ((vhp_brl_saco_pvu_exp * SACAS_POR_TON) / FATOR_CWT_POR_TON),
        cambio_brl_usd,
        errors,
        "L34 vhp_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_pvu_exp'] = vhp_cents_lb_pvu_exp
    meta["celulas"]["vhp_cents_lb_pvu_exp"] = "L34"
    
    # L35 vhp_cents_lb_fob
    # Excel: =((((((L33)*20)+L32+(C30*C4))/22.0462/C4)))
    temp_l35 = (((vhp_brl_saco_pvu_exp * SACAS_POR_TON) + frete_brl_por_ton_l32 + (terminal_usd_por_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON)
    vhp_cents_lb_fob_exp = safe_div(
        temp_l35,
        cambio_brl_usd,
        errors,
        "L35 vhp_cents_lb_fob: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_fob_exp'] = vhp_cents_lb_fob_exp
    meta["celulas"]["vhp_cents_lb_fob_exp"] = "L35"
    
    # L37 cristal_cents_lb_pvu
    # Excel: =((L36*20)/22.0462)/C4
    cristal_cents_lb_pvu_exp = safe_div(
        ((cristal_brl_saca_pvu_exp * SACAS_POR_TON) / FATOR_CWT_POR_TON),
        cambio_brl_usd,
        errors,
        "L37 cristal_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['cristal_cents_lb_pvu_exp'] = cristal_cents_lb_pvu_exp
    meta["celulas"]["cristal_cents_lb_pvu_exp"] = "L37"
    
    # L38 cristal_cents_lb_fob
    # Excel: =L29/22.04622
    cristal_cents_lb_fob_exp = sugar_fob_usd_ton / FATOR_CWT_POR_TON_ALT
    values['cristal_cents_lb_fob_exp'] = cristal_cents_lb_fob_exp
    meta["celulas"]["cristal_cents_lb_fob_exp"] = "L38"
    
    # L41 equivalente_esalq_com_impostos
    # Excel: =L36/0.9015
    equivalente_esalq_com_impostos_exp = cristal_brl_saca_pvu_exp / FATOR_ESALQ_SEM_IMPOSTOS
    values['equivalente_esalq_com_impostos_exp'] = equivalente_esalq_com_impostos_exp
    meta["celulas"]["equivalente_esalq_com_impostos_exp"] = "L41"
    
    # ===== SUB-BLOCO 5.5 - CRISTAL EXPORTAÇÃO MALHA 30 (N/O) =====
    
    # O26 = C26
    sugar_ny_fob_cents_lb_o26 = sugar_ny_fob_cents_lb
    meta["celulas"]["sugar_ny_fob_cents_lb_o26"] = "O26"
    
    # O27
    # Excel: =O26*22.04622
    sugar_usd_ton_o27 = sugar_ny_fob_cents_lb_o26 * FATOR_CWT_POR_TON_ALT
    values['sugar_usd_ton_o27'] = sugar_usd_ton_o27
    meta["celulas"]["sugar_usd_ton_o27"] = "O27"
    
    # O29 sugar_fob_usd_ton
    # Excel: =O27+O28
    sugar_fob_usd_ton_malha30 = sugar_usd_ton_o27 + premio_fisico_malha30
    values['sugar_fob_usd_ton_malha30'] = sugar_fob_usd_ton_malha30
    meta["celulas"]["sugar_fob_usd_ton_malha30"] = "O29"
    
    # O30 sugar_fob_r_ton
    # Excel: =O29*C4
    sugar_fob_r_ton_malha30 = sugar_fob_usd_ton_malha30 * cambio_brl_usd
    values['sugar_fob_r_ton_malha30'] = sugar_fob_r_ton_malha30
    meta["celulas"]["sugar_fob_r_ton_malha30"] = "O30"
    
    # O31 fobizacao_container_brl_ton
    fobizacao_container_brl_ton_o31 = parse_ptbr_number(inputs.get('fobizacao_container_brl_ton_o31', 198))
    values['fobizacao_container_brl_ton_o31'] = fobizacao_container_brl_ton_o31
    meta["celulas"]["fobizacao_container_brl_ton_o31"] = "O31"
    
    # O32 frete_brl_ton
    frete_brl_ton_o32 = parse_ptbr_number(inputs.get('frete_brl_ton_o32', 202))
    values['frete_brl_ton_o32'] = frete_brl_ton_o32
    meta["celulas"]["frete_brl_ton_o32"] = "O32"
    
    # O36 cristal_brl_saca_pvu
    # Excel: =(O30-O31-O32)/20
    cristal_brl_saca_pvu_malha30 = (sugar_fob_r_ton_malha30 - fobizacao_container_brl_ton_o31 - frete_brl_ton_o32) / SACAS_POR_TON
    values['cristal_brl_saca_pvu_malha30'] = cristal_brl_saca_pvu_malha30
    meta["celulas"]["cristal_brl_saca_pvu_malha30"] = "O36"
    
    # O33 vhp_brl_saco_pvu
    # Excel: =O36-'Custo Cristal vs VHP'!D17
    vhp_brl_saco_pvu_malha30 = cristal_brl_saca_pvu_malha30 - custo_cristal_vs_vhp
    values['vhp_brl_saco_pvu_malha30'] = vhp_brl_saco_pvu_malha30
    meta["celulas"]["vhp_brl_saco_pvu_malha30"] = "O33"
    
    # O34 vhp_cents_lb_pvu
    # Excel: =(((O33*20)/22.0462)/C4)
    vhp_cents_lb_pvu_malha30 = safe_div(
        ((vhp_brl_saco_pvu_malha30 * SACAS_POR_TON) / FATOR_CWT_POR_TON),
        cambio_brl_usd,
        errors,
        "O34 vhp_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_pvu_malha30'] = vhp_cents_lb_pvu_malha30
    meta["celulas"]["vhp_cents_lb_pvu_malha30"] = "O34"
    
    # O35 vhp_cents_lb_fob
    # Excel: =((((((O33)*20)+L32+(C30*C4))/22.0462/C4)))
    temp_o35 = (((vhp_brl_saco_pvu_malha30 * SACAS_POR_TON) + frete_brl_por_ton_l32 + (terminal_usd_por_ton * cambio_brl_usd)) / FATOR_CWT_POR_TON)
    vhp_cents_lb_fob_malha30 = safe_div(
        temp_o35,
        cambio_brl_usd,
        errors,
        "O35 vhp_cents_lb_fob: Divisão por zero (cambio_brl_usd=0)"
    )
    values['vhp_cents_lb_fob_malha30'] = vhp_cents_lb_fob_malha30
    meta["celulas"]["vhp_cents_lb_fob_malha30"] = "O35"
    
    # O37 cristal_cents_lb_pvu
    # Excel: =((O36*20)/22.0462)/C4
    cristal_cents_lb_pvu_malha30 = safe_div(
        ((cristal_brl_saca_pvu_malha30 * SACAS_POR_TON) / FATOR_CWT_POR_TON),
        cambio_brl_usd,
        errors,
        "O37 cristal_cents_lb_pvu: Divisão por zero (cambio_brl_usd=0)"
    )
    values['cristal_cents_lb_pvu_malha30'] = cristal_cents_lb_pvu_malha30
    meta["celulas"]["cristal_cents_lb_pvu_malha30"] = "O37"
    
    # O38 cristal_cents_lb_fob
    # Excel: =O29/22.04622
    cristal_cents_lb_fob_malha30 = sugar_fob_usd_ton_malha30 / FATOR_CWT_POR_TON_ALT
    values['cristal_cents_lb_fob_malha30'] = cristal_cents_lb_fob_malha30
    meta["celulas"]["cristal_cents_lb_fob_malha30"] = "O38"
    
    # O41 equivalente_esalq_com_impostos
    # Excel: =O36/0.9015
    equivalente_esalq_com_impostos_malha30 = cristal_brl_saca_pvu_malha30 / FATOR_ESALQ_SEM_IMPOSTOS
    values['equivalente_esalq_com_impostos_malha30'] = equivalente_esalq_com_impostos_malha30
    meta["celulas"]["equivalente_esalq_com_impostos_malha30"] = "O41"
    
    return {
        "values": values,
        "errors": errors,
        "meta": meta
    }

