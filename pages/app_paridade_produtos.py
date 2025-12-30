"""
Streamlit App para Cálculo de Paridade - Açúcar VHP
Interface focada no cálculo detalhado do açúcar VHP.
"""

import streamlit as st

st.set_page_config(page_title="Paridade Açúcar VHP", layout="wide")

# ============================================================================
# CONSTANTES
# ============================================================================

# Fator de conversão de c/lb para toneladas
FATOR_CONVERSAO_CENTS_LB_PARA_TON = 22.0462

# Sacas por tonelada
SACAS_POR_TON = 20

# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

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
# FUNÇÃO DE CÁLCULO DO AÇÚCAR VHP
# ============================================================================

def calc_acucar_vhp_detalhado(inputs, globais):
    """
    Calcula o açúcar VHP com desenvolvimento detalhado do cálculo.
    
    Args:
        inputs: dict com:
            - acucar_ny_cents_lb: Preço do açúcar NY em c/lb (centavos por libra)
            - premio_desconto: Prêmio/desconto em c/lb (pode ser decimal ou inteiro)
            - premio_pol: Prêmio de pol (número que será tratado como percentual)
            - custo_terminal_usd_ton: Custo de terminal em USD/ton
            - frete_brl_ton: Frete em BRL/ton
        globais: dict com parâmetros globais:
            - cambio_brl_usd: Câmbio USD/BRL
    
    Returns:
        dict: {
            'values': {
                'sugar_ny_mais_pol_cents_lb': ...,
                'equivalente_vhp_reais_saca_pvu': ...,
                'desenvolvimento': {...}  # Detalhamento do cálculo
            },
            'errors': [...]
        }
    """
    errors = []
    values = {}
    desenvolvimento = {}
    
    try:
        # Entradas
        acucar_ny_cents_lb = inputs.get('acucar_ny_cents_lb', 0)
        premio_desconto = inputs.get('premio_desconto', 0)
        premio_pol = inputs.get('premio_pol', 0)  # Será tratado como percentual
        custo_terminal_usd_ton = inputs.get('custo_terminal_usd_ton', 0)
        frete_brl_ton = inputs.get('frete_brl_ton', 0)
        
        cambio_brl_usd = globais.get('cambio_brl_usd', 1)
        
        # Validações
        if cambio_brl_usd <= 0:
            errors.append("Câmbio deve ser maior que zero")
            return {'values': values, 'errors': errors}
        
        # ====================================================================
        # PASSO 1: Calcular Sugar NY + Pol
        # Fórmula: (Açúcar NY + prêmio/desconto) * (1 + prêmio pol%)
        # ====================================================================
        
        # Converte prêmio de pol para percentual (se > 1, assume que está em %, senão assume decimal)
        premio_pol_percentual = premio_pol / 100 if premio_pol > 1 else premio_pol
        
        # Calcula Sugar NY + Pol
        sugar_ny_mais_pol_cents_lb = (acucar_ny_cents_lb + premio_desconto) * (1 + premio_pol_percentual)
        
        # Armazena desenvolvimento do Passo 1
        desenvolvimento['passo1'] = {
            'descricao': 'Cálculo Sugar NY + Pol',
            'formula': '(Açúcar NY + Prêmio/Desconto) × (1 + Prêmio Pol%)',
            'valores': {
                'acucar_ny_cents_lb': acucar_ny_cents_lb,
                'premio_desconto_cents_lb': premio_desconto,
                'premio_pol_percentual': premio_pol_percentual,
                'soma_ny_premio': acucar_ny_cents_lb + premio_desconto,
                'fator_pol': 1 + premio_pol_percentual,
                'resultado_cents_lb': sugar_ny_mais_pol_cents_lb
            }
        }
        
        # ====================================================================
        # PASSO 2: Calcular Equivalente VHP Reais/saca PVU
        # Fórmula: (((Sugar NY+pol * 22.0462) - custo de terminal - (frete Reais por ton/câmbio))/20) * Câmbio
        # ====================================================================
        
        # 1. Conversão de c/lb para USD/ton
        sugar_ny_mais_pol_usd_ton = sugar_ny_mais_pol_cents_lb * FATOR_CONVERSAO_CENTS_LB_PARA_TON
        
        # 2. Conversão do frete de BRL/ton para USD/ton
        frete_usd_ton = frete_brl_ton / cambio_brl_usd
        
        # 3. Cálculo do valor líquido em USD/ton
        valor_usd_ton = sugar_ny_mais_pol_usd_ton - custo_terminal_usd_ton - frete_usd_ton
        
        # 4. Divisão por 20 (sacas por tonelada) para obter USD/saca
        valor_usd_saca = valor_usd_ton / SACAS_POR_TON
        
        # 5. Conversão para BRL/saca multiplicando pelo câmbio
        equivalente_vhp_reais_saca_pvu = valor_usd_saca * cambio_brl_usd
        
        # Armazena desenvolvimento do Passo 2
        desenvolvimento['passo2'] = {
            'descricao': 'Cálculo Equivalente VHP Reais/saca PVU',
            'formula': '(((Sugar NY+pol × 22.0462) - Custo Terminal - (Frete BRL/ton ÷ Câmbio)) ÷ 20) × Câmbio',
            'valores': {
                'sugar_ny_mais_pol_cents_lb': sugar_ny_mais_pol_cents_lb,
                'fator_conversao': FATOR_CONVERSAO_CENTS_LB_PARA_TON,
                'sugar_ny_mais_pol_usd_ton': sugar_ny_mais_pol_usd_ton,
                'custo_terminal_usd_ton': custo_terminal_usd_ton,
                'frete_brl_ton': frete_brl_ton,
                'cambio_brl_usd': cambio_brl_usd,
                'frete_usd_ton': frete_usd_ton,
                'valor_usd_ton': valor_usd_ton,
                'sacas_por_ton': SACAS_POR_TON,
                'valor_usd_saca': valor_usd_saca,
                'resultado_brl_saca': equivalente_vhp_reais_saca_pvu
            }
        }
        
        # ====================================================================
        # PASSO 3: Calcular Equivalente VHP c/lb PVU
        # Fórmula: ((Equivalente VHP Reais/saca PVU * 20) / 22.0462) / câmbio
        # ====================================================================
        
        equivalente_vhp_cents_lb_pvu = ((equivalente_vhp_reais_saca_pvu * SACAS_POR_TON) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd
        
        desenvolvimento['passo3'] = {
            'descricao': 'Cálculo Equivalente VHP c/lb PVU',
            'formula': '((Equivalente VHP Reais/saca PVU × 20) ÷ 22.0462) ÷ Câmbio',
            'valores': {
                'equivalente_vhp_reais_saca_pvu': equivalente_vhp_reais_saca_pvu,
                'sacas_por_ton': SACAS_POR_TON,
                'fator_conversao': FATOR_CONVERSAO_CENTS_LB_PARA_TON,
                'cambio_brl_usd': cambio_brl_usd,
                'resultado_cents_lb_pvu': equivalente_vhp_cents_lb_pvu
            }
        }
        
        # ====================================================================
        # PASSO 4: Equivalente VHP c/lb FOB
        # Fórmula: igual ao Sugar NY + Pol
        # ====================================================================
        
        equivalente_vhp_cents_lb_fob = sugar_ny_mais_pol_cents_lb
        
        desenvolvimento['passo4'] = {
            'descricao': 'Equivalente VHP c/lb FOB',
            'formula': 'Igual ao Sugar NY + Pol',
            'valores': {
                'sugar_ny_mais_pol_cents_lb': sugar_ny_mais_pol_cents_lb,
                'resultado_cents_lb_fob': equivalente_vhp_cents_lb_fob
            }
        }
        
        # Armazena resultados
        values['sugar_ny_mais_pol_cents_lb'] = sugar_ny_mais_pol_cents_lb
        values['equivalente_vhp_reais_saca_pvu'] = equivalente_vhp_reais_saca_pvu
        values['equivalente_vhp_cents_lb_pvu'] = equivalente_vhp_cents_lb_pvu
        values['equivalente_vhp_cents_lb_fob'] = equivalente_vhp_cents_lb_fob
        values['desenvolvimento'] = desenvolvimento
        
    except Exception as e:
        errors.append(f"Erro ao calcular açúcar VHP: {str(e)}")
    
    return {
        'values': values,
        'errors': errors
    }

def calc_acucar_cristal_esalq(inputs, globais):
    """
    Calcula o açúcar cristal ESALQ com desenvolvimento detalhado do cálculo.
    
    Args:
        inputs: dict com:
            - preco_esalq_brl_saca: Preço ESALQ em R$/saca
            - imposto: Imposto (número que será tratado como percentual)
            - frete_santos_usina_brl_ton: Frete Santos-Usina em R$/Ton
            - custo_fobizacao_container_brl_ton: Custo de Fobização do container em R$/Ton
            - custo_vhp_para_cristal: Custo para transformar VHP em Cristal
        globais: dict com parâmetros globais:
            - cambio_brl_usd: Câmbio USD/BRL
            - custo_terminal_usd_ton: Custo de terminal em USD/ton (do açúcar VHP)
    
    Returns:
        dict: {
            'values': {
                'equivalente_cristal_reais_saca_pvu': ...,
                'equivalente_vhp_reais_saca_pvu': ...,
                'equivalente_vhp_cents_lb_pvu': ...,
                'equivalente_vhp_cents_lb_fob': ...,
                'equivalente_cristal_cents_lb_pvu': ...,
                'equivalente_cristal_cents_lb_fob': ...,
            },
            'errors': [...]
        }
    """
    errors = []
    values = {}
    
    try:
        # Entradas
        preco_esalq_brl_saca = inputs.get('preco_esalq_brl_saca', 0)
        imposto = inputs.get('imposto', 0)  # Será tratado como percentual
        frete_santos_usina_brl_ton = inputs.get('frete_santos_usina_brl_ton', 0)
        custo_fobizacao_container_brl_ton = inputs.get('custo_fobizacao_container_brl_ton', 0)
        custo_vhp_para_cristal = inputs.get('custo_vhp_para_cristal', 0)
        
        cambio_brl_usd = globais.get('cambio_brl_usd', 1)
        custo_terminal_usd_ton = globais.get('custo_terminal_usd_ton', 0)
        
        # Validações
        if cambio_brl_usd <= 0:
            errors.append("Câmbio deve ser maior que zero")
            return {'values': values, 'errors': errors}
        
        # Converte imposto para percentual (se > 1, assume que está em %, senão assume decimal)
        imposto_percentual = imposto / 100 if imposto > 1 else imposto
        
        # 1. Equivalente Cristal R$/Saca PVU
        equivalente_cristal_reais_saca_pvu = preco_esalq_brl_saca * (1 - imposto_percentual)
        
        # 2. Equivalente VHP R$/Saca PVU
        equivalente_vhp_reais_saca_pvu = equivalente_cristal_reais_saca_pvu - custo_vhp_para_cristal
        
        # 3. Equivalente VHP Cents/lb PVU
        equivalente_vhp_cents_lb_pvu = (((equivalente_vhp_reais_saca_pvu * SACAS_POR_TON) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd)
        
        # 4. Equivalente VHP Cents/lb FOB
        custo_terminal_brl_ton = custo_terminal_usd_ton * cambio_brl_usd
        equivalente_vhp_cents_lb_fob = (((((equivalente_vhp_reais_saca_pvu * SACAS_POR_TON) + frete_santos_usina_brl_ton + custo_terminal_brl_ton) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd))
        
        # 5. Equivalente Cristal c/lb PVU
        equivalente_cristal_cents_lb_pvu = (((equivalente_cristal_reais_saca_pvu * SACAS_POR_TON) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd) - (15 / FATOR_CONVERSAO_CENTS_LB_PARA_TON / cambio_brl_usd)
        
        # 6. Equivalente Cristal Cents/lb FOB
        # Usa 22.04622 conforme especificado na fórmula
        equivalente_cristal_cents_lb_fob = (((equivalente_cristal_reais_saca_pvu * SACAS_POR_TON) + frete_santos_usina_brl_ton + custo_fobizacao_container_brl_ton) / 22.04622) / cambio_brl_usd
        
        # Armazena resultados
        values['equivalente_cristal_reais_saca_pvu'] = equivalente_cristal_reais_saca_pvu
        values['equivalente_vhp_reais_saca_pvu'] = equivalente_vhp_reais_saca_pvu
        values['equivalente_vhp_cents_lb_pvu'] = equivalente_vhp_cents_lb_pvu
        values['equivalente_vhp_cents_lb_fob'] = equivalente_vhp_cents_lb_fob
        values['equivalente_cristal_cents_lb_pvu'] = equivalente_cristal_cents_lb_pvu
        values['equivalente_cristal_cents_lb_fob'] = equivalente_cristal_cents_lb_fob
        
    except Exception as e:
        errors.append(f"Erro ao calcular açúcar cristal ESALQ: {str(e)}")
    
    return {
        'values': values,
        'errors': errors
    }

def calc_paridade_comercializacao_mi_ny(inputs, globais):
    """
    Calcula a paridade de comercialização mercado interno e externo NY.
    
    Args:
        inputs: dict com:
            - acucar_ny_cents_lb: Valor do açúcar NY em c/lb (do campo do açúcar VHP)
            - premio_fisico_mi: Prêmio/desconto de físico
        globais: dict com parâmetros globais:
            - cambio_brl_usd: Câmbio USD/BRL
            - custo_terminal_usd_ton: Custo de terminal em USD/ton
            - frete_santos_usina_brl_ton: Frete Santos-Usina em R$/Ton
            - custo_fobizacao_container_brl_ton: Custo de fobização em R$/Ton
            - custo_vhp_para_cristal: Custo para transformar VHP em Cristal
    
    Returns:
        dict: {
            'values': {
                'equivalente_cristal_reais_saca_pvu': ...,
                'equivalente_vhp_reais_saca_pvu': ...,
                'equivalente_vhp_cents_lb_pvu': ...,
                'equivalente_vhp_cents_lb_fob': ...,
                'equivalente_cristal_cents_lb_pvu': ...,
                'equivalente_cristal_cents_lb_fob': ...,
            },
            'errors': [...]
        }
    """
    errors = []
    values = {}
    
    try:
        # Entradas
        acucar_ny_cents_lb = inputs.get('acucar_ny_cents_lb', 0)
        premio_fisico_mi = inputs.get('premio_fisico_mi', 0)
        
        cambio_brl_usd = globais.get('cambio_brl_usd', 1)
        custo_terminal_usd_ton = globais.get('custo_terminal_usd_ton', 0)
        frete_santos_usina_brl_ton = globais.get('frete_santos_usina_brl_ton', 0)
        custo_fobizacao_container_brl_ton = globais.get('custo_fobizacao_container_brl_ton', 0)
        custo_vhp_para_cristal = globais.get('custo_vhp_para_cristal', 0)
        
        # Validações
        if cambio_brl_usd <= 0:
            errors.append("Câmbio deve ser maior que zero")
            return {'values': values, 'errors': errors}
        
        # 1. Equivalente Cristal R$/Saca PVU
        # Fórmula: (((Valor do açúcar em c/lb * 22,04622) + Prêmio de físico) * Câmbio) / 20
        acucar_ny_usd_ton = acucar_ny_cents_lb * 22.04622
        acucar_com_premio_usd_ton = acucar_ny_usd_ton + premio_fisico_mi
        acucar_com_premio_brl_ton = acucar_com_premio_usd_ton * cambio_brl_usd
        equivalente_cristal_reais_saca_pvu = acucar_com_premio_brl_ton / SACAS_POR_TON
        
        # 2. Equivalente VHP R$/saca PVU
        equivalente_vhp_reais_saca_pvu = equivalente_cristal_reais_saca_pvu - custo_vhp_para_cristal
        
        # 3. Equivalente VHP Cents/lb PVU
        equivalente_vhp_cents_lb_pvu = (((equivalente_vhp_reais_saca_pvu * SACAS_POR_TON) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd)
        
        # 4. Equivalente VHP Cents/lb FOB
        custo_terminal_brl_ton = custo_terminal_usd_ton * cambio_brl_usd
        equivalente_vhp_cents_lb_fob = (((((equivalente_vhp_reais_saca_pvu * SACAS_POR_TON) + frete_santos_usina_brl_ton + custo_terminal_brl_ton) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd))
        
        # 5. Equivalente Cristal c/lb PVU
        equivalente_cristal_cents_lb_pvu = ((equivalente_cristal_reais_saca_pvu * SACAS_POR_TON) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd
        
        # 6. Equivalente Cristal Cents/lb FOB
        # Fórmula: ((Equivalente Cristal R$/Saca PVU * 20 + Custo de fobização + Frete Santos-Usina R$/ton) / 22,0462) / Câmbio
        equivalente_cristal_cents_lb_fob = ((equivalente_cristal_reais_saca_pvu * SACAS_POR_TON + custo_fobizacao_container_brl_ton + frete_santos_usina_brl_ton) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd
        
        # Armazena resultados
        values['equivalente_cristal_reais_saca_pvu'] = equivalente_cristal_reais_saca_pvu
        values['equivalente_vhp_reais_saca_pvu'] = equivalente_vhp_reais_saca_pvu
        values['equivalente_vhp_cents_lb_pvu'] = equivalente_vhp_cents_lb_pvu
        values['equivalente_vhp_cents_lb_fob'] = equivalente_vhp_cents_lb_fob
        values['equivalente_cristal_cents_lb_pvu'] = equivalente_cristal_cents_lb_pvu
        values['equivalente_cristal_cents_lb_fob'] = equivalente_cristal_cents_lb_fob
        
    except Exception as e:
        errors.append(f"Erro ao calcular custo de comercialização açúcar cristal MI: {str(e)}")
    
    return {
        'values': values,
        'errors': errors
    }

def calc_acucar_cristal_exportacao(inputs, globais):
    """
    Calcula o açúcar cristal para exportação.
    
    Args:
        inputs: dict com:
            - acucar_ny_cents_lb: Valor do açúcar NY em c/lb (do campo do açúcar VHP)
            - premio_fisico_exportacao: Prêmio/desconto de físico de exportação
        globais: dict com parâmetros globais:
            - cambio_brl_usd: Câmbio USD/BRL
            - custo_terminal_usd_ton: Custo de terminal em USD/ton
            - frete_brl_ton: Frete em R$/Ton
            - custo_fobizacao_container_brl_ton: Custo de fobização em R$/Ton
            - custo_vhp_para_cristal: Custo para transformar VHP em Cristal
    
    Returns:
        dict: {
            'values': {
                'equivalente_cristal_reais_saca_pvu': ...,
                'equivalente_vhp_reais_saca_pvu': ...,
                'equivalente_vhp_cents_lb_pvu': ...,
                'equivalente_vhp_cents_lb_fob': ...,
                'equivalente_cristal_cents_lb_pvu': ...,
                'equivalente_cristal_cents_lb_fob': ...,
            },
            'errors': [...]
        }
    """
    errors = []
    values = {}
    
    try:
        # Entradas
        acucar_ny_cents_lb = inputs.get('acucar_ny_cents_lb', 0)
        premio_fisico_exportacao = inputs.get('premio_fisico_exportacao', 0)
        
        cambio_brl_usd = globais.get('cambio_brl_usd', 1)
        custo_terminal_usd_ton = globais.get('custo_terminal_usd_ton', 0)
        frete_brl_ton = globais.get('frete_brl_ton', 0)
        custo_fobizacao_container_brl_ton = globais.get('custo_fobizacao_container_brl_ton', 0)
        custo_vhp_para_cristal = globais.get('custo_vhp_para_cristal', 0)
        
        # Validações
        if cambio_brl_usd <= 0:
            errors.append("Câmbio deve ser maior que zero")
            return {'values': values, 'errors': errors}
        
        # 1. Equivalente Cristal R$/Saca PVU
        # Fórmula: (((Valor em c/lb * 22,04622) + Prêmio/Desconto de Físico de exportação) * Câmbio - Custo de fobização - custo de frete R$/Ton) / 20
        acucar_ny_usd_ton = acucar_ny_cents_lb * 22.04622
        acucar_com_premio_usd_ton = acucar_ny_usd_ton + premio_fisico_exportacao
        acucar_com_premio_brl_ton = acucar_com_premio_usd_ton * cambio_brl_usd
        equivalente_cristal_reais_saca_pvu = (acucar_com_premio_brl_ton - custo_fobizacao_container_brl_ton - frete_brl_ton) / SACAS_POR_TON
        
        # 2. Equivalente VHP R$/saca PVU
        equivalente_vhp_reais_saca_pvu = equivalente_cristal_reais_saca_pvu - custo_vhp_para_cristal
        
        # 3. Equivalente VHP Cents/lb PVU
        equivalente_vhp_cents_lb_pvu = (((equivalente_vhp_reais_saca_pvu * SACAS_POR_TON) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd)
        
        # 4. Equivalente VHP Cents/lb FOB
        custo_terminal_brl_ton = custo_terminal_usd_ton * cambio_brl_usd
        equivalente_vhp_cents_lb_fob = (((((equivalente_vhp_reais_saca_pvu * SACAS_POR_TON) + frete_brl_ton + custo_terminal_brl_ton) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd))
        
        # 5. Equivalente Cristal c/lb PVU
        equivalente_cristal_cents_lb_pvu = ((equivalente_cristal_reais_saca_pvu * SACAS_POR_TON) / FATOR_CONVERSAO_CENTS_LB_PARA_TON) / cambio_brl_usd
        
        # 6. Equivalente Cristal Cents/lb FOB
        # Fórmula: (((Valor em c/lb * 22,04622) + Prêmio/Desconto de Físico de exportação) / 22,0462
        equivalente_cristal_cents_lb_fob = ((acucar_ny_cents_lb * 22.04622) + premio_fisico_exportacao) / 22.0462
        
        # Armazena resultados
        values['equivalente_cristal_reais_saca_pvu'] = equivalente_cristal_reais_saca_pvu
        values['equivalente_vhp_reais_saca_pvu'] = equivalente_vhp_reais_saca_pvu
        values['equivalente_vhp_cents_lb_pvu'] = equivalente_vhp_cents_lb_pvu
        values['equivalente_vhp_cents_lb_fob'] = equivalente_vhp_cents_lb_fob
        values['equivalente_cristal_cents_lb_pvu'] = equivalente_cristal_cents_lb_pvu
        values['equivalente_cristal_cents_lb_fob'] = equivalente_cristal_cents_lb_fob
        
    except Exception as e:
        errors.append(f"Erro ao calcular açúcar cristal exportação: {str(e)}")
    
    return {
        'values': values,
        'errors': errors
    }

# ============================================================================
# SIDEBAR - INPUTS
# ============================================================================

with st.sidebar:
    # Cria duas colunas na sidebar
    col_sidebar_1, col_sidebar_2 = st.columns(2)
    
    with col_sidebar_1:
        st.header("🍬 Açúcar")
    st.caption("Parâmetros para cálculo do açúcar VHP")
    
    st.divider()
    
    # Câmbio (usado em todos os cálculos)
    st.subheader("💱 Câmbio")
    cambio_brl_usd = st.number_input(
        "Câmbio USD/BRL",
        value=5.35,
        step=0.01,
        format="%.4f",
        help="Taxa de câmbio real equiparado ao dólar"
    )
    
    st.divider()
    
    # Seção específica para Açúcar VHP
    st.subheader("📝 Parâmetros do Açúcar VHP")
    st.caption("Campos específicos para cálculo do açúcar VHP")
    
    st.markdown("**Preço Base**")
    acucar_ny_cents_lb = st.number_input(
            "Açúcar NY (c/lb)",
            value=15.8,
            step=0.1,
            format="%.2f",
            help="Valor do açúcar na bolsa em dólar por libra peso (centavos por libra)",
            key="acucar_ny_sidebar"
        )
        
    st.markdown("**Prêmios e Descontos**")
    premio_desconto_vhp = st.number_input(
        "Prêmio/Desconto (c/lb)",
        value=-0.1,
        step=0.1,
        format="%.2f",
        help="Prêmio ou desconto em centavos por libra (pode ser decimal ou inteiro)",
        key="premio_desconto_vhp_sidebar"
    )
    
    premio_pol_vhp = st.number_input(
        "Prêmio de Pol",
        value=4.2,
        step=0.1,
        format="%.2f",
        help="Prêmio de pol (será considerado como percentual. Ex: 4.2 = 4.2%)",
        key="premio_pol_vhp_sidebar"
    )
    
    st.markdown("**Custos**")
    custo_terminal_vhp_usd_ton = st.number_input(
        "Custo de Terminal (USD/ton)",
        value=12.5,
        step=0.1,
        format="%.2f",
        help="Custo de terminal em dólar por tonelada",
        key="custo_terminal_vhp_sidebar"
    )
    
    frete_vhp_brl_ton = st.number_input(
        "Frete (BRL/ton)",
        value=202.0,
        step=1.0,
        format="%.2f",
        help="Frete em reais por tonelada",
        key="frete_vhp_sidebar"
    )
    
    st.divider()
    
    # Seção específica para Açúcar Cristal ESALQ
    st.subheader("📝 Parâmetros do Açúcar Cristal ESALQ")
    st.caption("Campos específicos para cálculo do açúcar cristal ESALQ")
    
    st.markdown("**Preço Base**")
    preco_esalq_brl_saca = st.number_input(
        "Preço ESALQ (R$/saca)",
        value=115.67,
        step=0.1,
        format="%.2f",
        help="Preço ESALQ em reais por saca",
        key="preco_esalq_sidebar"
    )
    
    st.markdown("**Impostos**")
    imposto_esalq = st.number_input(
        "Imposto",
        value=9.85,
        step=0.1,
        format="%.2f",
        help="Imposto (será considerado como percentual. Ex: 9.85 = 9.85%)",
        key="imposto_esalq_sidebar"
    )
    
    st.markdown("**Custos**")
    frete_santos_usina_brl_ton = st.number_input(
        "Frete Santos-Usina (R$/Ton)",
        value=202.0,
        step=1.0,
        format="%.2f",
        help="Frete Santos-Usina em reais por tonelada",
        key="frete_santos_usina_sidebar"
    )
    
    custo_fobizacao_container_brl_ton = st.number_input(
        "Custo de Fobização Container (R$/Ton)",
        value=198.0,
        step=1.0,
        format="%.2f",
        help="Custo de fobização do container em reais por tonelada",
        key="custo_fobizacao_sidebar"
    )
    
    custo_vhp_para_cristal = st.number_input(
        "Custo VHP para Cristal",
        value=9.25,
        step=0.1,
        format="%.2f",
        help="Custo para transformar VHP em Cristal",
        key="custo_vhp_cristal_sidebar"
    )
    
    st.divider()
    
    # Seção específica para Custo de Comercialização Açúcar Cristal MI
    st.subheader("📝 Custo de Comercialização Açúcar Cristal MI")
    st.caption("Cálculo de custo de comercialização açúcar cristal mercado interno")
    
    st.markdown("**Prêmios**")
    premio_fisico_mi = st.number_input(
        "Prêmio/Desconto de Físico",
        value=0.0,
        step=0.1,
        format="%.2f",
        help="Prêmio/desconto de físico - média de prêmio do mercado interno (pode variar)",
        key="premio_fisico_mi_sidebar"
    )
    
    st.divider()
    
    # Seção específica para Açúcar Cristal Exportação
    st.subheader("📝 Açúcar Cristal Exportação")
    st.caption("Cálculo de açúcar cristal para exportação")
    
    st.markdown("**Prêmios**")
    premio_fisico_exportacao = st.number_input(
        "Prêmio/Desconto de Físico Exportação",
        value=0.0,
        step=0.1,
        format="%.2f",
        help="Prêmio/desconto de físico para exportação",
        key="premio_fisico_exportacao_sidebar"
    )
    
    with col_sidebar_2:
        st.header("⛽ Etanol")
        st.caption("Parâmetros para cálculo de paridades de etanol")
        st.info("Seção será preenchida conforme desenvolvimento das paridades de etanol")

# ============================================================================
# CÁLCULOS
# ============================================================================

# Prepara inputs
inputs_acucar_vhp = {
    'acucar_ny_cents_lb': acucar_ny_cents_lb,
    'premio_desconto': premio_desconto_vhp,
    'premio_pol': premio_pol_vhp,
    'custo_terminal_usd_ton': custo_terminal_vhp_usd_ton,
    'frete_brl_ton': frete_vhp_brl_ton,
}

globais = {
    'cambio_brl_usd': cambio_brl_usd,
    'custo_terminal_usd_ton': custo_terminal_vhp_usd_ton,
    'frete_santos_usina_brl_ton': frete_santos_usina_brl_ton,
    'frete_brl_ton': frete_vhp_brl_ton,
    'custo_fobizacao_container_brl_ton': custo_fobizacao_container_brl_ton,
    'custo_vhp_para_cristal': custo_vhp_para_cristal,
}

# Executa cálculos
result_acucar_vhp = calc_acucar_vhp_detalhado(inputs_acucar_vhp, globais)

# Prepara inputs para açúcar cristal ESALQ
inputs_acucar_cristal_esalq = {
    'preco_esalq_brl_saca': preco_esalq_brl_saca,
    'imposto': imposto_esalq,
    'frete_santos_usina_brl_ton': frete_santos_usina_brl_ton,
    'custo_fobizacao_container_brl_ton': custo_fobizacao_container_brl_ton,
    'custo_vhp_para_cristal': custo_vhp_para_cristal,
}

# Executa cálculo do açúcar cristal ESALQ
result_acucar_cristal_esalq = calc_acucar_cristal_esalq(inputs_acucar_cristal_esalq, globais)

# Prepara inputs para custo de comercialização açúcar cristal MI
inputs_paridade_mi_ny = {
    'acucar_ny_cents_lb': acucar_ny_cents_lb,  # Usa o mesmo valor do açúcar VHP
    'premio_fisico_mi': premio_fisico_mi,
}

# Executa cálculo do custo de comercialização açúcar cristal MI
result_paridade_mi_ny = calc_paridade_comercializacao_mi_ny(inputs_paridade_mi_ny, globais)

# Prepara inputs para açúcar cristal exportação
inputs_acucar_cristal_exportacao = {
    'acucar_ny_cents_lb': acucar_ny_cents_lb,  # Usa o mesmo valor do açúcar VHP
    'premio_fisico_exportacao': premio_fisico_exportacao,
}

# Executa cálculo do açúcar cristal exportação
result_acucar_cristal_exportacao = calc_acucar_cristal_exportacao(inputs_acucar_cristal_exportacao, globais)

# ============================================================================
# EXIBIÇÃO DOS RESULTADOS
# ============================================================================

st.title("🍬 Paridade de Produtos")
st.caption("Análise comparativa de equivalentes")

# Exibe erros se houver
all_errors = (result_acucar_vhp.get('errors', []) + 
              result_acucar_cristal_esalq.get('errors', []) +
              result_paridade_mi_ny.get('errors', []) +
              result_acucar_cristal_exportacao.get('errors', []))
if all_errors:
    st.error("⚠️ Erros encontrados:")
    for error in all_errors:
        st.write(f"- {error}")

# Exibe resultados se houver
if result_acucar_vhp.get('values'):
    valores_vhp = result_acucar_vhp['values']
    
    # Seção Açúcar VHP
    st.header("🍬 Açúcar VHP")
    
    # Container estilizado para as equivalências
    st.markdown("""
    <style>
    .equivalencia-container {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        margin: 1.5rem 0;
    }
    .equivalencia-card {
        border-left: 4px solid;
        padding: 1.25rem 1.5rem;
        border-radius: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .equivalencia-card-red {
        border-left-color: #dc3545;
    }
    .equivalencia-card-green {
        border-left-color: #28a745;
    }
    .equivalencia-card-dark {
        border-left-color: #0d6efd;
    }
    .equivalencia-label {
        font-size: 1rem;
        font-weight: 500;
        flex: 1;
    }
    .equivalencia-label-red {
        color: #dc3545;
    }
    .equivalencia-label-green {
        color: #28a745;
    }
    .equivalencia-label-dark {
        color: #0d6efd;
    }
    .equivalencia-value {
        font-size: 1.75rem;
        font-weight: bold;
        margin-left: 1.5rem;
    }
    .equivalencia-value-red {
        color: #dc3545;
    }
    .equivalencia-value-green {
        color: #28a745;
    }
    .equivalencia-value-dark {
        color: #0d6efd;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Equivalências em formato de cartões
    st.markdown("""
    <div class="equivalencia-container">
        <div class="equivalencia-card equivalencia-card-red">
            <div class="equivalencia-label equivalencia-label-red">Equivalente VHP BRL/saca PVU</div>
            <div class="equivalencia-value equivalencia-value-red">R$ {}</div>
        </div>
        <div class="equivalencia-card equivalencia-card-green">
            <div class="equivalencia-label equivalencia-label-green">Equivalente VHP Cents/lb PVU</div>
            <div class="equivalencia-value equivalencia-value-green">{} c/lb</div>
        </div>
        <div class="equivalencia-card equivalencia-card-dark">
            <div class="equivalencia-label equivalencia-label-dark">Equivalente VHP Cents/lb FOB</div>
            <div class="equivalencia-value equivalencia-value-dark">{} c/lb</div>
        </div>
    </div>
    """.format(
        fmt_br(valores_vhp.get('equivalente_vhp_reais_saca_pvu', 0)),
        fmt_br(valores_vhp.get('equivalente_vhp_cents_lb_pvu', 0)),
        fmt_br(valores_vhp.get('equivalente_vhp_cents_lb_fob', 0))
    ), unsafe_allow_html=True)
    
    st.divider()
    
    # Seção Açúcar Cristal ESALQ
    if result_acucar_cristal_esalq.get('values'):
        valores_esalq = result_acucar_cristal_esalq['values']
        
        st.header("🍬 Açúcar Cristal ESALQ")
        
        # Equivalências em formato de cartões
        st.markdown("""
        <div class="equivalencia-container">
            <div class="equivalencia-card equivalencia-card-red">
                <div class="equivalencia-label equivalencia-label-red">Equivalente VHP BRL/saca PVU</div>
                <div class="equivalencia-value equivalencia-value-red">R$ {}</div>
            </div>
            <div class="equivalencia-card equivalencia-card-green">
                <div class="equivalencia-label equivalencia-label-green">Equivalente VHP Cents/lb PVU</div>
                <div class="equivalencia-value equivalencia-value-green">{} c/lb</div>
            </div>
            <div class="equivalencia-card equivalencia-card-dark">
                <div class="equivalencia-label equivalencia-label-dark">Equivalente VHP Cents/lb FOB</div>
                <div class="equivalencia-value equivalencia-value-dark">{} c/lb</div>
            </div>
            <div class="equivalencia-card equivalencia-card-red">
                <div class="equivalencia-label equivalencia-label-red">Equivalente Cristal R$/saca PVU</div>
                <div class="equivalencia-value equivalencia-value-red">R$ {}</div>
            </div>
            <div class="equivalencia-card equivalencia-card-green">
                <div class="equivalencia-label equivalencia-label-green">Equivalente Cristal c/lb PVU</div>
                <div class="equivalencia-value equivalencia-value-green">{} c/lb</div>
            </div>
            <div class="equivalencia-card equivalencia-card-dark">
                <div class="equivalencia-label equivalencia-label-dark">Equivalente Cristal Cents/lb FOB</div>
                <div class="equivalencia-value equivalencia-value-dark">{} c/lb</div>
            </div>
        </div>
        """.format(
            fmt_br(valores_esalq.get('equivalente_vhp_reais_saca_pvu', 0)),
            fmt_br(valores_esalq.get('equivalente_vhp_cents_lb_pvu', 0)),
            fmt_br(valores_esalq.get('equivalente_vhp_cents_lb_fob', 0)),
            fmt_br(valores_esalq.get('equivalente_cristal_reais_saca_pvu', 0)),
            fmt_br(valores_esalq.get('equivalente_cristal_cents_lb_pvu', 0)),
            fmt_br(valores_esalq.get('equivalente_cristal_cents_lb_fob', 0))
        ), unsafe_allow_html=True)
        
        st.divider()
    
    # Seção Custo de Comercialização Açúcar Cristal MI
    if result_paridade_mi_ny.get('values'):
        valores_mi_ny = result_paridade_mi_ny['values']
        
        st.header("🍬 Custo de Comercialização Açúcar Cristal MI")
        
        # Equivalências em formato de cartões
        st.markdown("""
        <div class="equivalencia-container">
            <div class="equivalencia-card equivalencia-card-red">
                <div class="equivalencia-label equivalencia-label-red">Equivalente VHP BRL/saca PVU</div>
                <div class="equivalencia-value equivalencia-value-red">R$ {}</div>
            </div>
            <div class="equivalencia-card equivalencia-card-green">
                <div class="equivalencia-label equivalencia-label-green">Equivalente VHP Cents/lb PVU</div>
                <div class="equivalencia-value equivalencia-value-green">{} c/lb</div>
            </div>
            <div class="equivalencia-card equivalencia-card-dark">
                <div class="equivalencia-label equivalencia-label-dark">Equivalente VHP Cents/lb FOB</div>
                <div class="equivalencia-value equivalencia-value-dark">{} c/lb</div>
            </div>
            <div class="equivalencia-card equivalencia-card-red">
                <div class="equivalencia-label equivalencia-label-red">Equivalente Cristal R$/saca PVU</div>
                <div class="equivalencia-value equivalencia-value-red">R$ {}</div>
            </div>
            <div class="equivalencia-card equivalencia-card-green">
                <div class="equivalencia-label equivalencia-label-green">Equivalente Cristal c/lb PVU</div>
                <div class="equivalencia-value equivalencia-value-green">{} c/lb</div>
            </div>
            <div class="equivalencia-card equivalencia-card-dark">
                <div class="equivalencia-label equivalencia-label-dark">Equivalente Cristal Cents/lb FOB</div>
                <div class="equivalencia-value equivalencia-value-dark">{} c/lb</div>
            </div>
        </div>
        """.format(
            fmt_br(valores_mi_ny.get('equivalente_vhp_reais_saca_pvu', 0)),
            fmt_br(valores_mi_ny.get('equivalente_vhp_cents_lb_pvu', 0)),
            fmt_br(valores_mi_ny.get('equivalente_vhp_cents_lb_fob', 0)),
            fmt_br(valores_mi_ny.get('equivalente_cristal_reais_saca_pvu', 0)),
            fmt_br(valores_mi_ny.get('equivalente_cristal_cents_lb_pvu', 0)),
            fmt_br(valores_mi_ny.get('equivalente_cristal_cents_lb_fob', 0))
        ), unsafe_allow_html=True)
        
        st.divider()
    
    # Seção Açúcar Cristal Exportação
    if result_acucar_cristal_exportacao.get('values'):
        valores_exportacao = result_acucar_cristal_exportacao['values']
        
        st.header("🍬 Açúcar Cristal Exportação")
        
        # Equivalências em formato de cartões
        st.markdown("""
        <div class="equivalencia-container">
            <div class="equivalencia-card equivalencia-card-red">
                <div class="equivalencia-label equivalencia-label-red">Equivalente VHP BRL/saca PVU</div>
                <div class="equivalencia-value equivalencia-value-red">R$ {}</div>
            </div>
            <div class="equivalencia-card equivalencia-card-green">
                <div class="equivalencia-label equivalencia-label-green">Equivalente VHP Cents/lb PVU</div>
                <div class="equivalencia-value equivalencia-value-green">{} c/lb</div>
            </div>
            <div class="equivalencia-card equivalencia-card-dark">
                <div class="equivalencia-label equivalencia-label-dark">Equivalente VHP Cents/lb FOB</div>
                <div class="equivalencia-value equivalencia-value-dark">{} c/lb</div>
            </div>
            <div class="equivalencia-card equivalencia-card-red">
                <div class="equivalencia-label equivalencia-label-red">Equivalente Cristal R$/saca PVU</div>
                <div class="equivalencia-value equivalencia-value-red">R$ {}</div>
            </div>
            <div class="equivalencia-card equivalencia-card-green">
                <div class="equivalencia-label equivalencia-label-green">Equivalente Cristal c/lb PVU</div>
                <div class="equivalencia-value equivalencia-value-green">{} c/lb</div>
            </div>
            <div class="equivalencia-card equivalencia-card-dark">
                <div class="equivalencia-label equivalencia-label-dark">Equivalente Cristal Cents/lb FOB</div>
                <div class="equivalencia-value equivalencia-value-dark">{} c/lb</div>
            </div>
        </div>
        """.format(
            fmt_br(valores_exportacao.get('equivalente_vhp_reais_saca_pvu', 0)),
            fmt_br(valores_exportacao.get('equivalente_vhp_cents_lb_pvu', 0)),
            fmt_br(valores_exportacao.get('equivalente_vhp_cents_lb_fob', 0)),
            fmt_br(valores_exportacao.get('equivalente_cristal_reais_saca_pvu', 0)),
            fmt_br(valores_exportacao.get('equivalente_cristal_cents_lb_pvu', 0)),
            fmt_br(valores_exportacao.get('equivalente_cristal_cents_lb_fob', 0))
        ), unsafe_allow_html=True)
        
        st.divider()
