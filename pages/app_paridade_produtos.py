"""
Streamlit App para Paridade Produtos
Interface para editar inputs e visualizar outputs dos cálculos de paridade.
"""

import streamlit as st
import pandas as pd

# Importação relativa - paridade_produtos está no mesmo diretório
try:
    from .paridade_produtos import (
        parse_ptbr_number,
        fmt_br,
        calc_anidro_exportacao,
        calc_hidratado_exportacao,
        calc_anidro_mi,
        calc_hidratado_mi,
        calc_acucar
    )
except ImportError:
    # Fallback para importação absoluta
    import sys
    from pathlib import Path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    from paridade_produtos import (
        parse_ptbr_number,
        fmt_br,
        calc_anidro_exportacao,
        calc_hidratado_exportacao,
        calc_anidro_mi,
        calc_hidratado_mi,
        calc_acucar
    )

st.set_page_config(page_title="Paridade Produtos", layout="wide")

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def formatar_nome_bonito(nome_variavel):
    """
    Converte nome de variável com underscore para formato legível.
    Ex: 'preco_liquido_pvu' -> 'Preço Líquido PVU'
    """
    # Mapeamento de abreviações conhecidas
    abreviacoes = {
        'pvu': 'PVU',
        'vhp': 'VHP',
        'brl': 'BRL',
        'usd': 'USD',
        'cbio': 'CBIO',
        'icms': 'ICMS',
        'fob': 'FOB',
        'rp': 'RP',
        'mi': 'Mercado Interno',
        'exp': 'Exportação',
        'esalq': 'Esalq',
        'malha30': 'Malha 30',
        'cents_lb': 'cents/lb',
        'brl_saca': 'BRL/saca',
        'brl_saco': 'BRL/saco',
        'brl_ton': 'BRL/ton',
        'usd_ton': 'USD/ton',
        'brl_por_ton': 'BRL/ton',
        'usd_por_ton': 'USD/ton',
    }
    
    palavras = nome_variavel.split('_')
    resultado = []
    
    for palavra in palavras:
        palavra_lower = palavra.lower()
        if palavra_lower in abreviacoes:
            resultado.append(abreviacoes[palavra_lower])
        else:
            # Capitaliza primeira letra
            resultado.append(palavra.capitalize())
    
    # Junta as palavras
    texto = ' '.join(resultado)
    
    # Ajustes finais
    texto = texto.replace('Preco', 'Preço')
    texto = texto.replace('Custo', 'Custo')
    texto = texto.replace('Premio', 'Prêmio')
    texto = texto.replace('Desconto', 'Desconto')
    texto = texto.replace('Contribuicao', 'Contribuição')
    texto = texto.replace('Impostos', 'Impostos')
    texto = texto.replace('Fobizacao', 'Fobização')
    texto = texto.replace('Supervisao', 'Supervisão')
    texto = texto.replace('Demurrage', 'Demurrage')
    texto = texto.replace('Hidratado', 'Hidratado')
    texto = texto.replace('Anidro', 'Anidro')
    texto = texto.replace('Cristal', 'Cristal')
    texto = texto.replace('Equivalente', 'Equivalente')
    texto = texto.replace('Liquido', 'Líquido')
    texto = texto.replace('Mais', 'Mais')
    texto = texto.replace('Fisico', 'Físico')
    texto = texto.replace('Contrato', 'Contrato')
    
    return texto

# ============================================================================
# SIDEBAR - INPUTS
# ============================================================================

with st.sidebar:
    st.header("⚙️ Parâmetros Globais")
    
    cambio_brl_usd = st.number_input(
        "Câmbio USD/BRL",
        value=5.35,
        step=0.01,
        format="%.4f"
    )
    
    st.subheader("Custos Adicionais (para cálculos de equivalentes)")
    custo_c5 = st.number_input(
        "Custo Adicional 1 (para cálculo VHP FOB)",
        value=0.0,
        step=0.1,
        format="%.2f",
        help="Usado no cálculo de equivalente VHP Cents/lb FOB"
    )
    custo_c6 = st.number_input(
        "Custo Adicional 2 (para cálculo Cristal PVU)",
        value=0.0,
        step=0.1,
        format="%.2f",
        help="Usado no cálculo de equivalente Cristal BRL/saca PVU"
    )
    custo_c7 = st.number_input(
        "Custo Adicional 3 (para cálculo Cristal PVU Cents/lb)",
        value=0.0,
        step=0.1,
        format="%.2f",
        help="Usado no cálculo de equivalente Cristal Cents/lb PVU"
    )
    custo_c8 = st.number_input(
        "Custo Adicional 4 - Demurrage (para cálculo Cristal FOB)",
        value=0.0,
        step=0.1,
        format="%.2f",
        help="Usado no cálculo de equivalente Cristal Cents/lb FOB. Se vazio, dará erro de divisão por zero"
    )
    
    st.subheader("Parâmetros Açúcar")
    terminal_usd_por_ton = st.number_input("Terminal USD/ton", value=12.5, step=0.1, format="%.2f")
    frete_brl_por_ton = st.number_input("Frete BRL/ton", value=202.0, step=1.0, format="%.2f")
    fobizacao_container_brl_ton = st.number_input("Fobização Container BRL/ton", value=198.0, step=1.0, format="%.2f")
    frete_brl_por_ton_l32 = st.number_input("Frete BRL/ton (L32)", value=202.0, step=1.0, format="%.2f")
    custo_cristal_vs_vhp = st.number_input("Custo Cristal vs VHP", value=0.0, step=0.1, format="%.2f")
    
    st.divider()
    st.header("📥 Inputs por Bloco")
    
    st.subheader("Anidro Exportação")
    preco_anidro_fob_usd = st.number_input("Preço Anidro FOB USD", value=750.0, step=1.0, format="%.2f")
    frete_porto_usina_brl_bloco1 = st.number_input("Frete Porto-Usina BRL", value=200.0, step=1.0, format="%.2f")
    terminal_brl_bloco1 = st.number_input("Terminal BRL", value=100.0, step=1.0, format="%.2f")
    supervisao_documentos_brl_bloco1 = st.number_input("Supervisão/Documentos BRL", value=4.0, step=0.1, format="%.2f")
    custos_adicionais_demurrage_bloco1 = st.number_input("Custos Adicionais Demurrage", value=0.0, step=0.1, format="%.2f")
    
    st.subheader("Hidratado Exportação")
    preco_hidratado_fob_usd = st.number_input("Preço Hidratado FOB USD", value=550.0, step=1.0, format="%.2f")
    
    st.subheader("Anidro Mercado Interno")
    preco_anidro_com_impostos = st.number_input("Preço Anidro com Impostos", value=3350.0, step=1.0, format="%.2f")
    pis_cofins = st.number_input("PIS/COFINS", value=192.2, step=0.1, format="%.2f")
    contribuicao_agroindustria = st.number_input("Contribuição Agroindústria", value=0.0, step=0.01, format="%.4f")
    valor_cbio_bruto = st.number_input("Valor CBIO Bruto", value=40.0, step=1.0, format="%.2f")
    
    st.subheader("Hidratado Mercado Interno")
    preco_hidratado_rp_com_impostos = st.number_input("Preço Hidratado RP com Impostos", value=3400.0, step=1.0, format="%.2f")
    pis_cofins_hidratado = st.number_input("PIS/COFINS (Hidratado)", value=192.2, step=0.1, format="%.2f")
    icms = st.number_input("ICMS", value=0.12, step=0.01, format="%.4f")
    contribuicao_agroindustria_hidratado = st.number_input("Contribuição Agroindústria (Hidratado)", value=0.0, step=0.01, format="%.4f")
    valor_cbio_bruto_hidratado = st.number_input("Valor CBIO Bruto (Hidratado)", value=40.0, step=1.0, format="%.2f")
    premio_fisico_pvu = st.number_input("Prêmio Físico PVU", value=23.0, step=1.0, format="%.2f")
    
    st.subheader("Açúcar")
    sugar_ny_fob_cents_lb = st.number_input("Sugar NY FOB (cents/lb)", value=15.8, step=0.1, format="%.2f")
    premio_desconto_cents_lb = st.number_input("Prêmio/Desconto (cents/lb)", value=-0.1, step=0.1, format="%.2f")
    premio_pol = st.number_input("Prêmio POL", value=0.042, step=0.001, format="%.4f")
    esalq_brl_saca = st.number_input("Esalq BRL/saca", value=115.67, step=0.1, format="%.2f")
    impostos_esalq = st.number_input("Impostos Esalq", value=0.0985, step=0.001, format="%.4f")
    premio_fisico_fob = st.number_input("Prêmio Físico FOB", value=90.0, step=1.0, format="%.2f")
    premio_fisico_malha30 = st.number_input("Prêmio Físico Malha 30", value=104.0, step=1.0, format="%.2f")
    fobizacao_container_brl_ton_o31 = st.number_input("Fobização Container BRL/ton (O31)", value=198.0, step=1.0, format="%.2f")
    frete_brl_ton_o32 = st.number_input("Frete BRL/ton (O32)", value=202.0, step=1.0, format="%.2f")

# ============================================================================
# PARÂMETROS GLOBAIS
# ============================================================================

globais = {
    'cambio_brl_usd': cambio_brl_usd,
    'custo_c5': custo_c5,
    'custo_c6': custo_c6,
    'custo_c7': custo_c7,
    'custo_c8': custo_c8,
    'terminal_usd_por_ton': terminal_usd_por_ton,
    'frete_brl_por_ton': frete_brl_por_ton,
    'fobizacao_container_brl_ton': fobizacao_container_brl_ton,
    'frete_brl_por_ton_l32': frete_brl_por_ton_l32,
    'custo_cristal_vs_vhp': custo_cristal_vs_vhp,
}

# ============================================================================
# CÁLCULOS
# ============================================================================

# BLOCO 1
inputs_bloco1 = {
    'preco_anidro_fob_usd': preco_anidro_fob_usd,
    'cambio_brl_usd': cambio_brl_usd,
    'frete_porto_usina_brl': frete_porto_usina_brl_bloco1,
    'terminal_brl': terminal_brl_bloco1,
    'supervisao_documentos_brl': supervisao_documentos_brl_bloco1,
    'custos_adicionais_demurrage': custos_adicionais_demurrage_bloco1,
}
result_bloco1 = calc_anidro_exportacao(inputs_bloco1, globais)

# BLOCO 2
inputs_bloco2 = {
    'preco_hidratado_fob_usd': preco_hidratado_fob_usd,
    'cambio_brl_usd': cambio_brl_usd,
    'frete_porto_usina_brl': frete_porto_usina_brl_bloco1,
    'terminal_brl': terminal_brl_bloco1,
    'supervisao_documentos_brl': supervisao_documentos_brl_bloco1,
}
result_bloco2 = calc_hidratado_exportacao(inputs_bloco2, globais)

# BLOCO 4 (precisa ser calculado antes do BLOCO 3)
inputs_bloco4 = {
    'preco_hidratado_rp_com_impostos': preco_hidratado_rp_com_impostos,
    'pis_cofins': pis_cofins_hidratado,
    'icms': icms,
    'contribuicao_agroindustria': contribuicao_agroindustria_hidratado,
    'valor_cbio_bruto': valor_cbio_bruto_hidratado,
    'premio_fisico_pvu': premio_fisico_pvu,
    'fobizacao_container_brl_ton': fobizacao_container_brl_ton,
}
result_bloco4 = calc_hidratado_mi(inputs_bloco4, {}, globais)

# BLOCO 3 (depende de equivalente_anidro e preco_liquido_pvu_hidratado do BLOCO 4)
deps_bloco3 = {
    'equivalente_anidro': result_bloco4['values'].get('equivalente_anidro'),
    'preco_liquido_pvu_hidratado': result_bloco4['values'].get('preco_liquido_pvu'),
}
inputs_bloco3 = {
    'preco_anidro_com_impostos': preco_anidro_com_impostos,
    'pis_cofins': pis_cofins,
    'contribuicao_agroindustria': contribuicao_agroindustria,
    'valor_cbio_bruto': valor_cbio_bruto,
}
result_bloco3 = calc_anidro_mi(inputs_bloco3, deps_bloco3, globais)

# BLOCO 5
inputs_bloco5 = {
    'sugar_ny_fob_cents_lb': sugar_ny_fob_cents_lb,
    'premio_desconto_cents_lb': premio_desconto_cents_lb,
    'premio_pol': premio_pol,
    'esalq_brl_saca': esalq_brl_saca,
    'impostos_esalq': impostos_esalq,
    'premio_fisico_pvu': premio_fisico_pvu,
    'premio_fisico_fob': premio_fisico_fob,
    'premio_fisico_malha30': premio_fisico_malha30,
    'fobizacao_container_brl_ton_o31': fobizacao_container_brl_ton_o31,
    'frete_brl_ton_o32': frete_brl_ton_o32,
}
result_bloco5 = calc_acucar(inputs_bloco5, globais)

# ============================================================================
# EXIBIÇÃO DOS RESULTADOS
# ============================================================================

st.title("📊 Análise de Paridade de Produtos")
st.caption("Compare todas as rotas de produção para identificar a mais atrativa")

# Erros
all_errors = (
    result_bloco1.get('errors', []) +
    result_bloco2.get('errors', []) +
    result_bloco3.get('errors', []) +
    result_bloco4.get('errors', []) +
    result_bloco5.get('errors', [])
)
if all_errors:
    st.error("⚠️ Erros encontrados:")
    for error in all_errors:
        st.write(f"- {error}")

# ============================================================================
# SEÇÃO DE DECISÃO - COMPARAÇÃO CLARA
# ============================================================================

st.header("🎯 Decisão: Qual Rota Produzir?")

# Coleta todos os valores VHP PVU em BRL/saca para comparação
rotas_comparacao = []

# Anidro Exportação
vhp_saca_anidro_exp = result_bloco1['values'].get('vhp_brl_saca_pvu')
if vhp_saca_anidro_exp is not None:
    rotas_comparacao.append({
        'rota': 'Anidro Exportação',
        'vhp_pvu_brl_saca': vhp_saca_anidro_exp,
        'vhp_pvu_cents_lb': result_bloco1['values'].get('vhp_cents_lb_pvu'),
        'vhp_fob_cents_lb': result_bloco1['values'].get('vhp_cents_lb_fob'),
    })

# Hidratado Exportação
vhp_saca_hidratado_exp = result_bloco2['values'].get('vhp_brl_saca_pvu')
if vhp_saca_hidratado_exp is not None:
    rotas_comparacao.append({
        'rota': 'Hidratado Exportação',
        'vhp_pvu_brl_saca': vhp_saca_hidratado_exp,
        'vhp_pvu_cents_lb': result_bloco2['values'].get('vhp_cents_lb_pvu'),
        'vhp_fob_cents_lb': result_bloco2['values'].get('vhp_cents_lb_fob'),
    })

# Anidro Mercado Interno
vhp_saca_anidro_mi = result_bloco3['values'].get('vhp_brl_saco_pvu')
if vhp_saca_anidro_mi is not None:
    rotas_comparacao.append({
        'rota': 'Anidro Mercado Interno',
        'vhp_pvu_brl_saca': vhp_saca_anidro_mi,
        'vhp_pvu_cents_lb': result_bloco3['values'].get('vhp_cents_lb_pvu'),
        'vhp_fob_cents_lb': result_bloco3['values'].get('vhp_cents_lb_fob'),
    })

# Hidratado Mercado Interno
vhp_saca_hidratado_mi = result_bloco4['values'].get('vhp_brl_saco_pvu')
if vhp_saca_hidratado_mi is not None:
    rotas_comparacao.append({
        'rota': 'Hidratado Mercado Interno',
        'vhp_pvu_brl_saca': vhp_saca_hidratado_mi,
        'vhp_pvu_cents_lb': result_bloco4['values'].get('vhp_cents_lb_pvu'),
        'vhp_fob_cents_lb': result_bloco4['values'].get('vhp_cents_lb_fob'),
    })

# Açúcar - VHP Exportação
vhp_saca_acucar_vhp = result_bloco5['values'].get('vhp_brl_saca_pvu')
if vhp_saca_acucar_vhp is not None:
    rotas_comparacao.append({
        'rota': 'Açúcar VHP Exportação',
        'vhp_pvu_brl_saca': vhp_saca_acucar_vhp,
        'vhp_pvu_cents_lb': result_bloco5['values'].get('vhp_cents_lb_pvu'),
        'vhp_fob_cents_lb': result_bloco5['values'].get('vhp_cents_lb_fob'),
    })

# Açúcar - Cristal Esalq
vhp_saca_esalq = result_bloco5['values'].get('vhp_brl_saco_pvu_esalq')
if vhp_saca_esalq is not None:
    rotas_comparacao.append({
        'rota': 'Açúcar Cristal Esalq',
        'vhp_pvu_brl_saca': vhp_saca_esalq,
        'vhp_pvu_cents_lb': result_bloco5['values'].get('vhp_cents_lb_pvu_esalq'),
        'vhp_fob_cents_lb': result_bloco5['values'].get('vhp_cents_lb_fob_esalq'),
    })

# Açúcar - Cristal Mercado Interno
vhp_saca_mi = result_bloco5['values'].get('vhp_brl_saco_pvu_mi')
if vhp_saca_mi is not None:
    rotas_comparacao.append({
        'rota': 'Açúcar Cristal Mercado Interno',
        'vhp_pvu_brl_saca': vhp_saca_mi,
        'vhp_pvu_cents_lb': result_bloco5['values'].get('vhp_cents_lb_pvu_mi'),
        'vhp_fob_cents_lb': result_bloco5['values'].get('vhp_cents_lb_fob_mi'),
    })

# Açúcar - Cristal Exportação
vhp_saca_exp = result_bloco5['values'].get('vhp_brl_saco_pvu_exp')
if vhp_saca_exp is not None:
    rotas_comparacao.append({
        'rota': 'Açúcar Cristal Exportação',
        'vhp_pvu_brl_saca': vhp_saca_exp,
        'vhp_pvu_cents_lb': result_bloco5['values'].get('vhp_cents_lb_pvu_exp'),
        'vhp_fob_cents_lb': result_bloco5['values'].get('vhp_cents_lb_fob_exp'),
    })

# Açúcar - Cristal Exportação Malha 30
vhp_saca_malha30 = result_bloco5['values'].get('vhp_brl_saco_pvu_malha30')
if vhp_saca_malha30 is not None:
    rotas_comparacao.append({
        'rota': 'Açúcar Cristal Exportação Malha 30',
        'vhp_pvu_brl_saca': vhp_saca_malha30,
        'vhp_pvu_cents_lb': result_bloco5['values'].get('vhp_cents_lb_pvu_malha30'),
        'vhp_fob_cents_lb': result_bloco5['values'].get('vhp_cents_lb_fob_malha30'),
    })

# Ordena por VHP PVU BRL/saca (maior primeiro)
rotas_comparacao.sort(key=lambda x: x['vhp_pvu_brl_saca'] if x['vhp_pvu_brl_saca'] is not None else float('-inf'), reverse=True)

# Exibe top 3
if rotas_comparacao:
    st.subheader("🏆 Top 3 Rotas Mais Atrativas (VHP PVU BRL/saca)")
    col1, col2, col3 = st.columns(3)
    
    for idx, rota in enumerate(rotas_comparacao[:3]):
        col = [col1, col2, col3][idx]
        with col:
            st.metric(
                label=rota['rota'],
                value=fmt_br(rota['vhp_pvu_brl_saca']),
                delta=None
            )
            st.caption(f"PVU: {fmt_br(rota['vhp_pvu_cents_lb'])} cents/lb")
            st.caption(f"FOB: {fmt_br(rota['vhp_fob_cents_lb'])} cents/lb")

# Tabela comparativa completa
st.subheader("📋 Comparação Completa de Todas as Rotas")
df_comparacao = pd.DataFrame(rotas_comparacao)
if not df_comparacao.empty:
    df_comparacao['VHP PVU (BRL/saca)'] = df_comparacao['vhp_pvu_brl_saca'].apply(lambda x: fmt_br(x))
    df_comparacao['VHP PVU (cents/lb)'] = df_comparacao['vhp_pvu_cents_lb'].apply(lambda x: fmt_br(x))
    df_comparacao['VHP FOB (cents/lb)'] = df_comparacao['vhp_fob_cents_lb'].apply(lambda x: fmt_br(x))
    df_display = df_comparacao[['rota', 'VHP PVU (BRL/saca)', 'VHP PVU (cents/lb)', 'VHP FOB (cents/lb)']].copy()
    df_display.columns = ['Rota', 'VHP PVU (BRL/saca)', 'VHP PVU (cents/lb)', 'VHP FOB (cents/lb)']
    st.dataframe(df_display, use_container_width=True, hide_index=True)

st.divider()

# ============================================================================
# DETALHES POR BLOCO (em abas para não amontoar)
# ============================================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🚢 Etanol Exportação",
    "🏠 Etanol Mercado Interno",
    "🍬 Açúcar",
    "📊 Tabelas Resumo",
    "🗺️ Mapa Células"
])

with tab1:
    st.subheader("Anidro Exportação")
    values1 = result_bloco1['values']
    col1, col2 = st.columns(2)
    col1.metric("Preço Líquido PVU", fmt_br(values1.get('preco_liquido_pvu')))
    col2.metric("VHP BRL/saca PVU", fmt_br(values1.get('vhp_brl_saca_pvu')))
    col1, col2 = st.columns(2)
    col1.metric("VHP Cents/lb PVU", fmt_br(values1.get('vhp_cents_lb_pvu')))
    col2.metric("VHP Cents/lb FOB", fmt_br(values1.get('vhp_cents_lb_fob')))
    
    st.subheader("Hidratado Exportação")
    values2 = result_bloco2['values']
    col1, col2 = st.columns(2)
    col1.metric("Preço Líquido PVU", fmt_br(values2.get('preco_liquido_pvu')))
    col2.metric("VHP BRL/saca PVU", fmt_br(values2.get('vhp_brl_saca_pvu')))
    col1, col2 = st.columns(2)
    col1.metric("VHP Cents/lb PVU", fmt_br(values2.get('vhp_cents_lb_pvu')))
    col2.metric("VHP Cents/lb FOB", fmt_br(values2.get('vhp_cents_lb_fob')))

with tab2:
    st.subheader("Anidro Mercado Interno")
    values3 = result_bloco3['values']
    col1, col2 = st.columns(2)
    col1.metric("Preço Líquido PVU", fmt_br(values3.get('preco_liquido_pvu')))
    col2.metric("PVU + CBIO", fmt_br(values3.get('preco_pvu_mais_cbio')))
    col1, col2 = st.columns(2)
    col1.metric("VHP BRL/saco PVU", fmt_br(values3.get('vhp_brl_saco_pvu')))
    col2.metric("VHP Cents/lb PVU", fmt_br(values3.get('vhp_cents_lb_pvu')))
    col1, col2 = st.columns(2)
    col1.metric("VHP Cents/lb FOB", fmt_br(values3.get('vhp_cents_lb_fob')))
    col2.metric("Prêmio Anidro/Hidratado Líquido", fmt_br(values3.get('premio_anidro_hidratado_liquido')))
    
    st.subheader("Hidratado Mercado Interno")
    values4 = result_bloco4['values']
    col1, col2 = st.columns(2)
    col1.metric("Preço Líquido PVU", fmt_br(values4.get('preco_liquido_pvu')))
    col2.metric("PVU + CBIO", fmt_br(values4.get('preco_pvu_mais_cbio')))
    col1, col2 = st.columns(2)
    col1.metric("VHP BRL/saco PVU", fmt_br(values4.get('vhp_brl_saco_pvu')))
    col2.metric("VHP Cents/lb PVU", fmt_br(values4.get('vhp_cents_lb_pvu')))
    col1, col2 = st.columns(2)
    col1.metric("VHP Cents/lb FOB", fmt_br(values4.get('vhp_cents_lb_fob')))
    col2.metric("Cristal BRL/saca PVU", fmt_br(values4.get('cristal_brl_saca_pvu')))

with tab3:
    values5 = result_bloco5['values']
    
    st.subheader("Sugar VHP")
    col1, col2, col3 = st.columns(3)
    col1.metric("VHP BRL/saca PVU", fmt_br(values5.get('vhp_brl_saca_pvu')))
    col2.metric("VHP Cents/lb PVU", fmt_br(values5.get('vhp_cents_lb_pvu')))
    col3.metric("VHP Cents/lb FOB", fmt_br(values5.get('vhp_cents_lb_fob')))
    
    st.subheader("Cristal Esalq")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("VHP BRL/saco PVU", fmt_br(values5.get('vhp_brl_saco_pvu_esalq')))
    col2.metric("VHP Cents/lb PVU", fmt_br(values5.get('vhp_cents_lb_pvu_esalq')))
    col3.metric("VHP Cents/lb FOB", fmt_br(values5.get('vhp_cents_lb_fob_esalq')))
    col4.metric("Cristal BRL/saca PVU", fmt_br(values5.get('cristal_brl_saca_pvu_esalq')))
    
    st.subheader("Cristal Mercado Interno")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("VHP BRL/saco PVU", fmt_br(values5.get('vhp_brl_saco_pvu_mi')))
    col2.metric("VHP Cents/lb PVU", fmt_br(values5.get('vhp_cents_lb_pvu_mi')))
    col3.metric("VHP Cents/lb FOB", fmt_br(values5.get('vhp_cents_lb_fob_mi')))
    col4.metric("Cristal BRL/saca PVU", fmt_br(values5.get('cristal_brl_saca_pvu_mi')))
    
    st.subheader("Cristal Exportação")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("VHP BRL/saco PVU", fmt_br(values5.get('vhp_brl_saco_pvu_exp')))
    col2.metric("VHP Cents/lb PVU", fmt_br(values5.get('vhp_cents_lb_pvu_exp')))
    col3.metric("VHP Cents/lb FOB", fmt_br(values5.get('vhp_cents_lb_fob_exp')))
    col4.metric("Cristal BRL/saca PVU", fmt_br(values5.get('cristal_brl_saca_pvu_exp')))
    
    st.subheader("Cristal Exportação Malha 30")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("VHP BRL/saco PVU", fmt_br(values5.get('vhp_brl_saco_pvu_malha30')))
    col2.metric("VHP Cents/lb PVU", fmt_br(values5.get('vhp_cents_lb_pvu_malha30')))
    col3.metric("VHP Cents/lb FOB", fmt_br(values5.get('vhp_cents_lb_fob_malha30')))
    col4.metric("Cristal BRL/saca PVU", fmt_br(values5.get('cristal_brl_saca_pvu_malha30')))

with tab4:
    st.subheader("PVU BRL/saca")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Cristal Esalq", fmt_br(values5.get('vhp_brl_saco_pvu_esalq')))
    col2.metric("Cristal Malha 30", fmt_br(values5.get('vhp_brl_saco_pvu_malha30')))
    col3.metric("Anidro MI", fmt_br(values3.get('vhp_brl_saco_pvu')))
    col4.metric("Cristal Export", fmt_br(values5.get('vhp_brl_saco_pvu_exp')))
    col5.metric("VHP Export", fmt_br(values5.get('vhp_brl_saca_pvu')))
    col6.metric("Hidratado MI", fmt_br(values4.get('vhp_brl_saco_pvu')))
    
    st.subheader("FOB Cents/lb")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Cristal Esalq", fmt_br(values5.get('vhp_cents_lb_fob_esalq')))
    col2.metric("Cristal Malha 30", fmt_br(values5.get('vhp_cents_lb_fob_malha30')))
    col3.metric("Cristal Export", fmt_br(values5.get('vhp_cents_lb_fob_exp')))
    col4.metric("Anidro MI", fmt_br(values3.get('vhp_cents_lb_fob')))
    col5.metric("VHP Export", fmt_br(values5.get('vhp_cents_lb_fob')))
    col6.metric("Hidratado MI", fmt_br(values4.get('vhp_cents_lb_fob')))

with tab5:
    st.subheader("Mapeamento completo de células para variáveis")
    
    all_meta = {
        "BLOCO 1": result_bloco1['meta']['celulas'],
        "BLOCO 2": result_bloco2['meta']['celulas'],
        "BLOCO 3": result_bloco3['meta']['celulas'],
        "BLOCO 4": result_bloco4['meta']['celulas'],
        "BLOCO 5": result_bloco5['meta']['celulas'],
    }
    
    for bloco, celulas in all_meta.items():
        st.write(f"**{bloco}**")
        df = pd.DataFrame([
            {"Célula": celula, "Variável": variavel}
            for variavel, celula in celulas.items()
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
