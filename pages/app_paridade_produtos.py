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

st.title("📊 Paridade Produtos")
st.caption("Reprodução exata das fórmulas da aba 'Paridade Produtos' do Excel")

# ============================================================================
# SIDEBAR - INPUTS
# ============================================================================

with st.sidebar:
    st.header("⚙️ Parâmetros Globais")
    
    # C4 cambio_brl_usd
    cambio_brl_usd = st.number_input(
        "cambio_brl_usd — Câmbio USD/BRL",
        value=5.35,
        step=0.01,
        format="%.4f"
    )
    
    # C5-C8: Custos adicionais (usados em I16-I19)
    st.subheader("Custos Adicionais (para cálculos I16-I19)")
    custo_c5 = st.number_input(
        "custo_c5",
        value=0.0,
        step=0.1,
        format="%.2f"
    )
    custo_c6 = st.number_input(
        "custo_c6",
        value=0.0,
        step=0.1,
        format="%.2f"
    )
    custo_c7 = st.number_input(
        "custo_c7",
        value=0.0,
        step=0.1,
        format="%.2f"
    )
    custo_c8 = st.number_input(
        "custos_adicionais_demurrage — Custos Adicionais Demurrage",
        value=0.0,
        step=0.1,
        format="%.2f",
        help="Se vazio, I19 dará erro de divisão por zero"
    )
    
    # C30, C32: Parâmetros do bloco açúcar
    st.subheader("Parâmetros Açúcar (compartilhados)")
    terminal_usd_por_ton = st.number_input(
        "terminal_usd_por_ton — Terminal USD/ton",
        value=12.5,
        step=0.1,
        format="%.2f"
    )
    frete_brl_por_ton = st.number_input(
        "frete_brl_por_ton — Frete BRL/ton",
        value=202.0,
        step=1.0,
        format="%.2f"
    )
    fobizacao_container_brl_ton = st.number_input(
        "fobizacao_container_brl_ton — Fobização Container BRL/ton",
        value=198.0,
        step=1.0,
        format="%.2f"
    )
    frete_brl_por_ton_l32 = st.number_input(
        "frete_brl_por_ton_l32 — Frete BRL/ton (L32)",
        value=202.0,
        step=1.0,
        format="%.2f"
    )
    
    # Custo Cristal vs VHP
    custo_cristal_vs_vhp = st.number_input(
        "custo_cristal_vs_vhp — Custo Cristal vs VHP",
        value=0.0,
        step=0.1,
        format="%.2f"
    )
    
    st.divider()
    st.header("📥 Inputs por Bloco")
    
    # BLOCO 1 - ANIDRO EXPORTAÇÃO
    st.subheader("BLOCO 1 - Anidro Exportação")
    preco_anidro_fob_usd = st.number_input(
        "preco_anidro_fob_usd — Preço Anidro FOB USD",
        value=750.0,
        step=1.0,
        format="%.2f"
    )
    frete_porto_usina_brl_bloco1 = st.number_input(
        "frete_porto_usina_brl — Frete Porto-Usina BRL",
        value=200.0,
        step=1.0,
        format="%.2f"
    )
    terminal_brl_bloco1 = st.number_input(
        "terminal_brl — Terminal BRL",
        value=100.0,
        step=1.0,
        format="%.2f"
    )
    supervisao_documentos_brl_bloco1 = st.number_input(
        "supervisao_documentos_brl — Supervisão/Documentos BRL",
        value=4.0,
        step=0.1,
        format="%.2f"
    )
    custos_adicionais_demurrage_bloco1 = st.number_input(
        "custos_adicionais_demurrage — Custos Adicionais Demurrage",
        value=0.0,
        step=0.1,
        format="%.2f"
    )
    
    # BLOCO 2 - HIDRATADO EXPORTAÇÃO
    st.subheader("BLOCO 2 - Hidratado Exportação")
    preco_hidratado_fob_usd = st.number_input(
        "preco_hidratado_fob_usd — Preço Hidratado FOB USD",
        value=550.0,
        step=1.0,
        format="%.2f"
    )
    
    # BLOCO 3 - ANIDRO MERCADO INTERNO
    st.subheader("BLOCO 3 - Anidro Mercado Interno")
    preco_anidro_com_impostos = st.number_input(
        "preco_anidro_com_impostos — Preço Anidro com Impostos",
        value=3350.0,
        step=1.0,
        format="%.2f"
    )
    pis_cofins = st.number_input(
        "pis_cofins — PIS/COFINS",
        value=192.2,
        step=0.1,
        format="%.2f"
    )
    contribuicao_agroindustria = st.number_input(
        "contribuicao_agroindustria — Contribuição Agroindústria",
        value=0.0,
        step=0.01,
        format="%.4f"
    )
    valor_cbio_bruto = st.number_input(
        "valor_cbio_bruto — Valor CBIO Bruto",
        value=40.0,
        step=1.0,
        format="%.2f"
    )
    
    # BLOCO 4 - HIDRATADO MERCADO INTERNO
    st.subheader("BLOCO 4 - Hidratado Mercado Interno")
    preco_hidratado_rp_com_impostos = st.number_input(
        "preco_hidratado_rp_com_impostos — Preço Hidratado RP com Impostos",
        value=3400.0,
        step=1.0,
        format="%.2f"
    )
    pis_cofins_hidratado = st.number_input(
        "pis_cofins_hidratado — PIS/COFINS",
        value=192.2,
        step=0.1,
        format="%.2f"
    )
    icms = st.number_input(
        "icms — ICMS",
        value=0.12,
        step=0.01,
        format="%.4f"
    )
    contribuicao_agroindustria_hidratado = st.number_input(
        "contribuicao_agroindustria_hidratado — Contribuição Agroindústria",
        value=0.0,
        step=0.01,
        format="%.4f"
    )
    valor_cbio_bruto_hidratado = st.number_input(
        "valor_cbio_bruto_hidratado — Valor CBIO Bruto",
        value=40.0,
        step=1.0,
        format="%.2f"
    )
    premio_fisico_pvu = st.number_input(
        "premio_fisico_pvu — Prêmio Físico PVU",
        value=23.0,
        step=1.0,
        format="%.2f"
    )
    
    # BLOCO 5 - AÇÚCAR
    st.subheader("BLOCO 5 - Açúcar")
    sugar_ny_fob_cents_lb = st.number_input(
        "sugar_ny_fob_cents_lb — Sugar NY FOB (cents/lb)",
        value=15.8,
        step=0.1,
        format="%.2f"
    )
    premio_desconto_cents_lb = st.number_input(
        "premio_desconto_cents_lb — Prêmio/Desconto (cents/lb)",
        value=-0.1,
        step=0.1,
        format="%.2f"
    )
    premio_pol = st.number_input(
        "premio_pol — Prêmio POL",
        value=0.042,
        step=0.001,
        format="%.4f"
    )
    esalq_brl_saca = st.number_input(
        "esalq_brl_saca — Esalq BRL/saca",
        value=115.67,
        step=0.1,
        format="%.2f"
    )
    impostos_esalq = st.number_input(
        "impostos_esalq — Impostos Esalq",
        value=0.0985,
        step=0.001,
        format="%.4f"
    )
    premio_fisico_fob = st.number_input(
        "premio_fisico_fob — Prêmio Físico FOB",
        value=90.0,
        step=1.0,
        format="%.2f"
    )
    premio_fisico_malha30 = st.number_input(
        "premio_fisico_malha30 — Prêmio Físico Malha 30",
        value=104.0,
        step=1.0,
        format="%.2f"
    )
    fobizacao_container_brl_ton_o31 = st.number_input(
        "fobizacao_container_brl_ton_o31 — Fobização Container BRL/ton",
        value=198.0,
        step=1.0,
        format="%.2f"
    )
    frete_brl_ton_o32 = st.number_input(
        "frete_brl_ton_o32 — Frete BRL/ton",
        value=202.0,
        step=1.0,
        format="%.2f"
    )

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

# BLOCO 4 (precisa ser calculado antes do BLOCO 3 para ter equivalente_anidro e preco_liquido_pvu_hidratado)
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

# BLOCO 1
st.header("📦 BLOCO 1 - Anidro Exportação")
values1 = result_bloco1['values']
col1, col2, col3, col4 = st.columns(4)
col1.metric("preco_liquido_pvu — Preço Líquido PVU", fmt_br(values1.get('preco_liquido_pvu')))
col2.metric("vhp_brl_saca_pvu — VHP BRL/saca PVU", fmt_br(values1.get('vhp_brl_saca_pvu')))
col3.metric("vhp_cents_lb_pvu — VHP Cents/lb PVU", fmt_br(values1.get('vhp_cents_lb_pvu')))
col4.metric("vhp_cents_lb_fob — VHP Cents/lb FOB", fmt_br(values1.get('vhp_cents_lb_fob')))

# BLOCO 2
st.header("📦 BLOCO 2 - Hidratado Exportação")
values2 = result_bloco2['values']
col1, col2, col3, col4 = st.columns(4)
col1.metric("preco_liquido_pvu — Preço Líquido PVU", fmt_br(values2.get('preco_liquido_pvu')))
col2.metric("vhp_brl_saca_pvu — VHP BRL/saca PVU", fmt_br(values2.get('vhp_brl_saca_pvu')))
col3.metric("vhp_cents_lb_pvu — VHP Cents/lb PVU", fmt_br(values2.get('vhp_cents_lb_pvu')))
col4.metric("vhp_cents_lb_fob — VHP Cents/lb FOB", fmt_br(values2.get('vhp_cents_lb_fob')))

# BLOCO 3
st.header("📦 BLOCO 3 - Anidro Mercado Interno")
values3 = result_bloco3['values']
col1, col2, col3, col4 = st.columns(4)
col1.metric("preco_liquido_pvu — Preço Líquido PVU", fmt_br(values3.get('preco_liquido_pvu')))
col2.metric("preco_pvu_mais_cbio — PVU + CBIO", fmt_br(values3.get('preco_pvu_mais_cbio')))
col3.metric("vhp_brl_saco_pvu — VHP BRL/saco PVU", fmt_br(values3.get('vhp_brl_saco_pvu')))
col4.metric("vhp_cents_lb_pvu — VHP Cents/lb PVU", fmt_br(values3.get('vhp_cents_lb_pvu')))
col1, col2, col3, col4 = st.columns(4)
col1.metric("vhp_cents_lb_fob — VHP Cents/lb FOB", fmt_br(values3.get('vhp_cents_lb_fob')))
col2.metric("premio_anidro_hidratado_liquido — Prêmio Anidro/Hidratado Líquido", fmt_br(values3.get('premio_anidro_hidratado_liquido')))
col3.metric("premio_anidro_hidratado_contrato — Prêmio Anidro/Hidratado Contrato", fmt_br(values3.get('premio_anidro_hidratado_contrato')))

# BLOCO 4
st.header("📦 BLOCO 4 - Hidratado Mercado Interno")
values4 = result_bloco4['values']
col1, col2, col3, col4 = st.columns(4)
col1.metric("preco_liquido_pvu — Preço Líquido PVU", fmt_br(values4.get('preco_liquido_pvu')))
col2.metric("preco_pvu_mais_cbio — PVU + CBIO", fmt_br(values4.get('preco_pvu_mais_cbio')))
col3.metric("vhp_brl_saco_pvu — VHP BRL/saco PVU", fmt_br(values4.get('vhp_brl_saco_pvu')))
col4.metric("vhp_cents_lb_pvu — VHP Cents/lb PVU", fmt_br(values4.get('vhp_cents_lb_pvu')))
col1, col2, col3, col4 = st.columns(4)
col1.metric("vhp_cents_lb_fob — VHP Cents/lb FOB", fmt_br(values4.get('vhp_cents_lb_fob')))
col2.metric("cristal_brl_saca_pvu — Cristal BRL/saca PVU", fmt_br(values4.get('cristal_brl_saca_pvu')))
col3.metric("cristal_cents_lb_pvu — Cristal Cents/lb PVU", fmt_br(values4.get('cristal_cents_lb_pvu')))
col4.metric("cristal_cents_lb_fob — Cristal Cents/lb FOB", fmt_br(values4.get('cristal_cents_lb_fob')))

# BLOCO 5
st.header("📦 BLOCO 5 - Paridade Açúcar")
values5 = result_bloco5['values']

st.subheader("SUB-BLOCO 5.1 - Sugar VHP")
col1, col2, col3 = st.columns(3)
col1.metric("vhp_brl_saca_pvu — VHP BRL/saca PVU", fmt_br(values5.get('vhp_brl_saca_pvu')))
col2.metric("vhp_cents_lb_pvu — VHP Cents/lb PVU", fmt_br(values5.get('vhp_cents_lb_pvu')))
col3.metric("vhp_cents_lb_fob — VHP Cents/lb FOB", fmt_br(values5.get('vhp_cents_lb_fob')))

st.subheader("SUB-BLOCO 5.2 - Cristal Esalq")
col1, col2, col3, col4 = st.columns(4)
col1.metric("vhp_brl_saco_pvu_esalq — VHP BRL/saco PVU", fmt_br(values5.get('vhp_brl_saco_pvu_esalq')))
col2.metric("vhp_cents_lb_pvu_esalq — VHP Cents/lb PVU", fmt_br(values5.get('vhp_cents_lb_pvu_esalq')))
col3.metric("vhp_cents_lb_fob_esalq — VHP Cents/lb FOB", fmt_br(values5.get('vhp_cents_lb_fob_esalq')))
col4.metric("cristal_brl_saca_pvu_esalq — Cristal BRL/saca PVU", fmt_br(values5.get('cristal_brl_saca_pvu_esalq')))

st.subheader("SUB-BLOCO 5.3 - Cristal Mercado Interno")
col1, col2, col3, col4 = st.columns(4)
col1.metric("vhp_brl_saco_pvu_mi — VHP BRL/saco PVU", fmt_br(values5.get('vhp_brl_saco_pvu_mi')))
col2.metric("vhp_cents_lb_pvu_mi — VHP Cents/lb PVU", fmt_br(values5.get('vhp_cents_lb_pvu_mi')))
col3.metric("vhp_cents_lb_fob_mi — VHP Cents/lb FOB", fmt_br(values5.get('vhp_cents_lb_fob_mi')))
col4.metric("cristal_brl_saca_pvu_mi — Cristal BRL/saca PVU", fmt_br(values5.get('cristal_brl_saca_pvu_mi')))

st.subheader("SUB-BLOCO 5.4 - Cristal Exportação")
col1, col2, col3, col4 = st.columns(4)
col1.metric("vhp_brl_saco_pvu_exp — VHP BRL/saco PVU", fmt_br(values5.get('vhp_brl_saco_pvu_exp')))
col2.metric("vhp_cents_lb_pvu_exp — VHP Cents/lb PVU", fmt_br(values5.get('vhp_cents_lb_pvu_exp')))
col3.metric("vhp_cents_lb_fob_exp — VHP Cents/lb FOB", fmt_br(values5.get('vhp_cents_lb_fob_exp')))
col4.metric("cristal_brl_saca_pvu_exp — Cristal BRL/saca PVU", fmt_br(values5.get('cristal_brl_saca_pvu_exp')))

st.subheader("SUB-BLOCO 5.5 - Cristal Exportação Malha 30")
col1, col2, col3, col4 = st.columns(4)
col1.metric("vhp_brl_saco_pvu_malha30 — VHP BRL/saco PVU", fmt_br(values5.get('vhp_brl_saco_pvu_malha30')))
col2.metric("vhp_cents_lb_pvu_malha30 — VHP Cents/lb PVU", fmt_br(values5.get('vhp_cents_lb_pvu_malha30')))
col3.metric("vhp_cents_lb_fob_malha30 — VHP Cents/lb FOB", fmt_br(values5.get('vhp_cents_lb_fob_malha30')))
col4.metric("cristal_brl_saca_pvu_malha30 — Cristal BRL/saca PVU", fmt_br(values5.get('cristal_brl_saca_pvu_malha30')))

# ============================================================================
# TABELAS-RESUMO (BLOCO 6)
# ============================================================================

st.header("📊 TABELAS-RESUMO")

# PVU BRL/saca (linhas 3-8)
st.subheader("PVU BRL/saca")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("O3 = F33", fmt_br(values5.get('vhp_brl_saco_pvu_esalq')))
col2.metric("O4 = O33", fmt_br(values5.get('vhp_brl_saco_pvu_malha30')))
col3.metric("O5 = I14", fmt_br(values3.get('vhp_brl_saco_pvu')))
col4.metric("O6 = L33", fmt_br(values5.get('vhp_brl_saco_pvu_exp')))
col5.metric("O7 = C33", fmt_br(values5.get('vhp_brl_saca_pvu')))
col6.metric("O8 = L14", fmt_br(values4.get('vhp_brl_saco_pvu')))

# FOB Cents/lb (linhas 14-19)
st.subheader("FOB Cents/lb")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("O14 = F35", fmt_br(values5.get('vhp_cents_lb_fob_esalq')))
col2.metric("O15 = O35", fmt_br(values5.get('vhp_cents_lb_fob_malha30')))
col3.metric("O16 = L35", fmt_br(values5.get('vhp_cents_lb_fob_exp')))
col4.metric("O17 = I16", fmt_br(values3.get('vhp_cents_lb_fob')))
col5.metric("O18 = C35", fmt_br(values5.get('vhp_cents_lb_fob')))
col6.metric("O19 = L16", fmt_br(values4.get('vhp_cents_lb_fob')))

# ============================================================================
# MAPA CÉLULA -> VARIÁVEL
# ============================================================================

with st.expander("🗺️ Mapa Célula → Variável"):
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

