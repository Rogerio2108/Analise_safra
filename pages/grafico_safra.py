"""
================================================================================
GRÁFICOS DE ACOMPANHAMENTO DE SAFRA - VISUALIZAÇÕES PROFISSIONAIS
================================================================================
Este módulo gera gráficos profissionais baseados nos dados de acompanhamento
de safra (acompanhamento_safra.py), permitindo visualizar:
- Comparação entre dados reais e projetados
- Evolução detalhada de etanol (anidro/hidratado, cana/milho)
- Análise de desvios entre real e projetado
- Evolução de preços reais vs simulados
- Análises estatísticas e correlações avançadas

================================================================================
"""

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import date

# Importa funções do acompanhamento_safra.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

# Tenta importar do acompanhamento_safra
try:
    from acompanhamento_safra import (
        gerar_projecao_quinzenal,
        simular_precos,
        calcular_producao_quinzenal,
        calcular_etanol_detalhado,
        calcular_etanol_milho,
        fmt_br
    )
except ImportError:
    st.error("⚠️ Erro ao importar funções de acompanhamento_safra.py. Certifique-se de que o arquivo existe.")
    st.stop()


# ============================================================================
# CONFIGURAÇÃO STREAMLIT
# ============================================================================

st.set_page_config(page_title="Gráficos de Acompanhamento", layout="wide")

st.markdown("<h1 style='text-align: center; margin-bottom: 5px;'>Gráficos de Acompanhamento de Safra 📊</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="text-align: center; color: #666; font-size: 0.9em; margin-top: 0px; margin-bottom: 20px;">Desenvolvido por Rogério Guilherme Jr.</p>',
    unsafe_allow_html=True
)

# ============================================================================
# ESQUEMA DE CORES CONSISTENTE
# ============================================================================

CORES = {
    'NY11': '#1f77b4',           # Azul
    'USD_BRL': '#ff7f0e',         # Laranja
    'Etanol': '#2ca02c',          # Verde
    'Açúcar': '#d62728',           # Vermelho
    'Moagem': '#1f77b4',           # Azul
    'ATR': '#ff7f0e',              # Laranja
    'MIX': '#2ca02c',              # Verde
    'Real': '#9467bd',             # Roxo
    'Projetado': '#8c564b',        # Marrom
    'Etanol_Anidro_Cana': '#d62728',    # Vermelho
    'Etanol_Hidratado_Cana': '#ff7f0e', # Laranja
    'Etanol_Anidro_Milho': '#2ca02c',   # Verde
    'Etanol_Hidratado_Milho': '#9467bd', # Roxo
    'Acumulado': '#8c564b',        # Marrom
    'Quinzenal': '#e377c2',        # Rosa
}


# ============================================================================
# FUNÇÕES DE GERAÇÃO DE GRÁFICOS
# ============================================================================

def criar_grafico_comparacao_real_projetado(df, coluna, titulo, unidade="", eixo_y=""):
    """
    Cria gráfico comparando dados reais vs projetados vs baseline (TUDO EM UM GRÁFICO).

    Args:
        df: DataFrame com dados
        coluna: Nome da coluna a comparar
        titulo: Título do gráfico
        unidade: Unidade de medida
        eixo_y: Label do eixo Y
    """
    fig = go.Figure()

    # Baseline (se disponível) - adiciona primeiro para ficar atrás
    coluna_baseline = coluna.replace('Moagem', 'Moagem Baseline').replace('ATR', 'ATR Baseline').replace('MIX', 'MIX Baseline').replace('Açúcar (t)', 'Açúcar Baseline (t)').replace('Etanol Total (m³)', 'Etanol Baseline (m³)')
    if coluna_baseline in df.columns:
        df_baseline_valid = df[df[coluna_baseline].notna() & (df[coluna_baseline] > 0)]
        if len(df_baseline_valid) > 0:
            fig.add_trace(go.Scatter(
                x=df_baseline_valid['Data'],
                y=df_baseline_valid[coluna_baseline],
                name='<b>Baseline (Perfil Ideal)</b>',
                line=dict(color='#17becf', width=3.5, dash='dot'),
                mode='lines+markers',
                marker=dict(size=7, symbol='x', line=dict(width=1.5, color='white')),
                hovertemplate=f'<b>Baseline</b><br>Data: %{{x}}<br>{titulo}: %{{y:,.0f}} {unidade}<extra></extra>'
            ))

    # Dados projetados (sempre presentes) - linha principal
    fig.add_trace(go.Scatter(
        x=df['Data'],
        y=df[coluna],
        name='<b>Projetado</b>',
        line=dict(color=CORES['Projetado'], width=3.5, dash='dash'),
        mode='lines+markers',
        marker=dict(size=7, symbol='circle', line=dict(width=1.5, color='white')),
        hovertemplate=f'<b>Projetado</b><br>Data: %{{x}}<br>{titulo}: %{{y:,.0f}} {unidade}<extra></extra>'
    ))

    # Identifica dados reais (se houver coluna correspondente)
    coluna_real = coluna.replace(' (t)', '_real').replace(' (m³)', '_real').replace('_', '_real_')

    # Verifica se há dados reais no session_state
    if 'dados_reais' in st.session_state and st.session_state.dados_reais:
        dados_reais_list = []
        datas_reais = []

        for quinzena in sorted(st.session_state.dados_reais.keys()):
            if quinzena <= len(df):
                dados_q = st.session_state.dados_reais[quinzena]
                data_q = df.iloc[quinzena - 1]['Data'] if quinzena <= len(df) else None

                # Mapeia coluna para campo real
                # IMPORTANTE: dados_reais contém valores ACUMULADOS, então calcula quinzenal como diferença
                valor_real = None
                if 'moagem' in coluna.lower():
                    # Moagem acumulada - calcula quinzenal
                    moagem_acum = dados_q.get('moagem_real')
                    if moagem_acum:
                        if quinzena == 1:
                            valor_real = moagem_acum
                        else:
                            moagem_ant = st.session_state.dados_reais.get(quinzena - 1, {}).get('moagem_real', 0) or 0
                            valor_real = moagem_acum - moagem_ant
                elif 'atr' in coluna.lower():
                    # ATR é médio, não acumulado
                    valor_real = dados_q.get('atr_real')
                elif 'mix' in coluna.lower():
                    # MIX é médio, não acumulado
                    valor_real = dados_q.get('mix_real')
                elif 'açúcar' in coluna.lower() or 'acucar' in coluna.lower():
                    # Calcula açúcar real quinzenal se tiver moagem, ATR e mix
                    if dados_q.get('moagem_real') and dados_q.get('atr_real') and dados_q.get('mix_real'):
                        from acompanhamento_safra import calcular_producao_quinzenal
                        moagem_acum = dados_q['moagem_real']
                        if quinzena == 1:
                            moagem_q = moagem_acum
                        else:
                            moagem_ant = st.session_state.dados_reais.get(quinzena - 1, {}).get('moagem_real', 0) or 0
                            moagem_q = moagem_acum - moagem_ant
                        acucar_q, _ = calcular_producao_quinzenal(moagem_q, dados_q['atr_real'], dados_q['mix_real'])
                        valor_real = acucar_q
                elif 'etanol' in coluna.lower():
                    # Para etanol, pode ser total ou detalhado
                    # Dados são ACUMULADOS, então calcula quinzenal como diferença
                    if 'total' in coluna.lower():
                        # Soma todos os tipos de etanol acumulados e calcula quinzenal
                        total_acum = 0
                        if dados_q.get('etanol_anidro_cana_real'):
                            total_acum += dados_q['etanol_anidro_cana_real']
                        if dados_q.get('etanol_hidratado_cana_real'):
                            total_acum += dados_q['etanol_hidratado_cana_real']
                        if dados_q.get('etanol_anidro_milho_real'):
                            total_acum += dados_q['etanol_anidro_milho_real']
                        if dados_q.get('etanol_hidratado_milho_real'):
                            total_acum += dados_q['etanol_hidratado_milho_real']

                        if total_acum > 0:
                            if quinzena == 1:
                                valor_real = total_acum
                            else:
                                # Calcula total acumulado anterior
                                dados_ant = st.session_state.dados_reais.get(quinzena - 1, {})
                                total_ant = 0
                                if dados_ant.get('etanol_anidro_cana_real'):
                                    total_ant += dados_ant['etanol_anidro_cana_real']
                                if dados_ant.get('etanol_hidratado_cana_real'):
                                    total_ant += dados_ant['etanol_hidratado_cana_real']
                                if dados_ant.get('etanol_anidro_milho_real'):
                                    total_ant += dados_ant['etanol_anidro_milho_real']
                                if dados_ant.get('etanol_hidratado_milho_real'):
                                    total_ant += dados_ant['etanol_hidratado_milho_real']
                                valor_real = total_acum - total_ant

                if valor_real and valor_real > 0 and data_q:
                    dados_reais_list.append(valor_real)
                    datas_reais.append(data_q)

        if dados_reais_list:
            fig.add_trace(go.Scatter(
                x=datas_reais,
                y=dados_reais_list,
                name='<b>Real</b>',
                line=dict(color=CORES['Real'], width=4.5),
                mode='lines+markers',
                marker=dict(size=10, symbol='diamond', line=dict(width=1.5, color='white')),
                hovertemplate=f'<b>Real</b><br>Data: %{{x}}<br>{titulo}: %{{y:,.0f}} {unidade}<extra></extra>'
            ))

    # Adiciona área sombreada entre real e projetado se ambos existirem
    if dados_reais_list and len(dados_reais_list) > 0:
        # Encontra datas comuns
        datas_comuns = [d for d in datas_reais if d in df['Data'].values]
        if datas_comuns:
            indices_reais = [datas_reais.index(d) for d in datas_comuns]
            indices_proj = [df[df['Data'] == d].index[0] for d in datas_comuns if len(df[df['Data'] == d]) > 0]
            
            if len(indices_reais) == len(indices_proj) and len(indices_reais) > 0:
                valores_reais_comuns = [dados_reais_list[i] for i in indices_reais]
                valores_proj_comuns = [df.iloc[i][coluna] for i in indices_proj]
                
                # Adiciona área de diferença
                fig.add_trace(go.Scatter(
                    x=datas_comuns,
                    y=valores_reais_comuns,
                    fill='tonexty',
                    fillcolor='rgba(148, 103, 189, 0.2)',
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo='skip'
                ))

    fig.update_layout(
        title=dict(
            text=f'<b>{titulo} - Real vs Projetado vs Baseline</b>',
            font=dict(size=18, family="Arial", color="#ffffff"),
            x=0.5,
            xanchor='center'
        ),
        height=550,
        hovermode='x unified',
        template='plotly_dark',
        font=dict(family="Arial", size=12, color="#ffffff"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=14, color="#ffffff", family="Arial"),
            bgcolor='rgba(0,0,0,0.85)',
            bordercolor='rgba(255,255,255,0.4)',
            borderwidth=2
        ),
        margin=dict(t=120, b=90, l=70, r=70),
        xaxis=dict(
            title="<b>Data</b>",
            title_font=dict(size=13, family="Arial", color="#ffffff"),
            gridcolor='rgba(255,255,255,0.15)',
            showgrid=True,
            tickfont=dict(color="#ffffff")
        ),
        yaxis=dict(
            title=f"<b>{eixo_y or titulo} {unidade}</b>",
            title_font=dict(size=13, family="Arial", color="#ffffff"),
            gridcolor='rgba(255,255,255,0.15)',
            showgrid=True,
            tickfont=dict(color="#ffffff")
        )
    )

    fig.update_xaxes(tickangle=-45, nticks=12, tickfont=dict(size=11, color="#ffffff"))

    return fig


def criar_grafico_comparacao_baseline(df, coluna_proj, coluna_baseline, titulo, unidade="", eixo_y=""):
    """
    Cria gráfico comparando dados projetados e reais com baseline.

    Args:
        df: DataFrame com dados
        coluna_proj: Nome da coluna projetada
        coluna_baseline: Nome da coluna baseline
        titulo: Título do gráfico
        unidade: Unidade de medida
        eixo_y: Label do eixo Y
    """
    # Verifica se a coluna baseline existe
    if coluna_baseline not in df.columns:
        return None

    fig = go.Figure()

    # Baseline (perfil ideal) - sempre mostra TODAS as quinzenas, mesmo que não haja dados reais
    # Filtra apenas valores válidos (não nulos e > 0)
    df_baseline_valid = df[df[coluna_baseline].notna() & (df[coluna_baseline] > 0)]

    if len(df_baseline_valid) > 0:
        fig.add_trace(go.Scatter(
            x=df_baseline_valid['Data'],
            y=df_baseline_valid[coluna_baseline],
            name='<b>Baseline (Perfil Ideal)</b>',
            line=dict(color='#17becf', width=3.5, dash='dot'),
            mode='lines+markers',
            marker=dict(size=7, symbol='x', line=dict(width=1, color='white')),
            hovertemplate=f'<b>Baseline</b><br>Data: %{{x}}<br>{titulo}: %{{y:,.2f}} {unidade}<extra></extra>'
        ))

    # Dados projetados - mostra TODAS as quinzenas
    df_proj_valid = df[df[coluna_proj].notna() & (df[coluna_proj] > 0)]

    if len(df_proj_valid) > 0:
        fig.add_trace(go.Scatter(
            x=df_proj_valid['Data'],
            y=df_proj_valid[coluna_proj],
            name='<b>Projetado</b>',
            line=dict(color=CORES['Projetado'], width=3.5, dash='dash'),
            mode='lines+markers',
            marker=dict(size=7, symbol='circle', line=dict(width=1, color='white')),
            hovertemplate=f'<b>Projetado</b><br>Data: %{{x}}<br>{titulo}: %{{y:,.2f}} {unidade}<extra></extra>'
        ))

    # Dados reais (se disponíveis)
    if 'dados_reais' in st.session_state and st.session_state.dados_reais:
        dados_reais_list = []
        datas_reais = []

        for quinzena in sorted(st.session_state.dados_reais.keys()):
            if quinzena <= len(df):
                dados_q = st.session_state.dados_reais[quinzena]
                data_q = df.iloc[quinzena - 1]['Data']

                valor_real = None
                if 'moagem' in coluna_proj.lower():
                    moagem_acum = dados_q.get('moagem_real')
                    if moagem_acum:
                        if quinzena == 1:
                            valor_real = moagem_acum
                        else:
                            moagem_ant = st.session_state.dados_reais.get(quinzena - 1, {}).get('moagem_real', 0) or 0
                            valor_real = moagem_acum - moagem_ant
                elif 'atr' in coluna_proj.lower():
                    valor_real = dados_q.get('atr_real')
                elif 'mix' in coluna_proj.lower():
                    valor_real = dados_q.get('mix_real')

                if valor_real and valor_real > 0 and data_q:
                    dados_reais_list.append(valor_real)
                    datas_reais.append(data_q)

        if dados_reais_list:
            fig.add_trace(go.Scatter(
                x=datas_reais,
                y=dados_reais_list,
                name='<b>Real</b>',
                line=dict(color=CORES['Real'], width=4.5),
                mode='lines+markers',
                marker=dict(size=10, symbol='diamond', line=dict(width=1.5, color='white')),
                hovertemplate=f'<b>Real</b><br>Data: %{{x}}<br>{titulo}: %{{y:,.2f}} {unidade}<extra></extra>'
            ))

    fig.update_layout(
        title=dict(
            text=f'<b>{titulo} - Baseline vs Projetado vs Real</b>',
            font=dict(size=18, family="Arial", color="#ffffff"),
            x=0.5,
            xanchor='center'
        ),
        height=550,
        hovermode='x unified',
        template='plotly_dark',
        font=dict(family="Arial", size=12, color="#ffffff"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=14, color="#ffffff", family="Arial"),
            bgcolor='rgba(0,0,0,0.85)',
            bordercolor='rgba(255,255,255,0.4)',
            borderwidth=2
        ),
        margin=dict(t=120, b=90, l=70, r=70),
        xaxis=dict(
            title="<b>Data</b>",
            title_font=dict(size=13, family="Arial", color="#ffffff"),
            gridcolor='rgba(255,255,255,0.15)',
            showgrid=True,
            tickfont=dict(color="#ffffff")
        ),
        yaxis=dict(
            title=f"<b>{eixo_y or titulo} {unidade}</b>",
            title_font=dict(size=13, family="Arial", color="#ffffff"),
            gridcolor='rgba(255,255,255,0.15)',
            showgrid=True,
            tickfont=dict(color="#ffffff")
        )
    )

    fig.update_xaxes(tickangle=-45, nticks=12, tickfont=dict(size=11, color="#ffffff"))

    return fig


def criar_grafico_desvios_baseline(df):
    """
    Cria gráfico de desvios entre dados REAIS e baseline (perfil ideal).
    """
    # Verifica se há colunas baseline
    colunas_baseline = [col for col in df.columns if 'Baseline' in col]
    if not colunas_baseline:
        return None

    # Verifica se há dados reais (mas permite gráfico mesmo com poucos dados)
    # Se não houver dados reais, ainda pode mostrar o gráfico com baseline e projetado
    tem_dados_reais = 'dados_reais' in st.session_state and st.session_state.dados_reais

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            '<b>Desvio Moagem Real vs Baseline (%)</b>',
            '<b>Desvio ATR Real vs Baseline (%)</b>',
            '<b>Desvio MIX Real vs Baseline (%)</b>',
            '<b>Resumo de Desvios Real vs Baseline</b>'
        ),
        specs=[[{"type": "scatter"}, {"type": "scatter"}],
               [{"type": "scatter"}, {"type": "bar"}]],
        vertical_spacing=0.18,
        horizontal_spacing=0.15
    )

    # Inicializa listas de desvios (apenas dados REAIS)
    desvios_moagem = []
    desvios_atr = []
    desvios_mix = []
    datas_moagem = []
    datas_atr = []
    datas_mix = []

    # Calcula desvios baseados em dados REAIS vs baseline (se houver dados reais)
    if tem_dados_reais:
        for quinzena in sorted(st.session_state.dados_reais.keys()):
            if quinzena <= len(df):
                dados_q = st.session_state.dados_reais[quinzena]
                data_q = df.iloc[quinzena - 1]['Data']
                row = df.iloc[quinzena - 1]

                # Desvio de Moagem (dados são acumulados, calcula quinzenal)
                if dados_q.get('moagem_real') and 'Moagem Baseline' in df.columns and row['Moagem Baseline'] > 0:
                    moagem_acum = dados_q['moagem_real']
                    if quinzena == 1:
                        moagem_q_real = moagem_acum
                    else:
                        moagem_ant = st.session_state.dados_reais.get(quinzena - 1, {}).get('moagem_real', 0) or 0
                        moagem_q_real = moagem_acum - moagem_ant

                    if moagem_q_real > 0:
                        desvio = ((moagem_q_real - row['Moagem Baseline']) / row['Moagem Baseline']) * 100
                        desvios_moagem.append(desvio)
                        datas_moagem.append(data_q)

                # Desvio de ATR (dados são médios, não acumulados)
                if dados_q.get('atr_real') and 'ATR Baseline' in df.columns and row['ATR Baseline'] > 0:
                    atr_real = dados_q['atr_real']
                    desvio = ((atr_real - row['ATR Baseline']) / row['ATR Baseline']) * 100
                    desvios_atr.append(desvio)
                    datas_atr.append(data_q)

                # Desvio de MIX (dados são médios, não acumulados)
                if dados_q.get('mix_real') and 'MIX Baseline' in df.columns and row['MIX Baseline'] > 0:
                    mix_real = dados_q['mix_real']
                    desvio = ((mix_real - row['MIX Baseline']) / row['MIX Baseline']) * 100
                    desvios_mix.append(desvio)
                    datas_mix.append(data_q)

    # Adiciona traços aos gráficos
    if desvios_moagem:
        fig.add_trace(
            go.Scatter(
                x=datas_moagem,
                y=desvios_moagem,
                mode='lines+markers',
                name='<b>Moagem</b>',
                line=dict(color=CORES['Moagem'], width=3.5),
                marker=dict(size=10, symbol='diamond', line=dict(width=1.5, color='white')),
                hovertemplate='<b>Desvio Moagem Real</b><br>Data: %{x}<br>Desvio: %{y:.2f}%<extra></extra>',
                showlegend=False,
                fill='tozeroy',
                fillcolor=f'rgba(31, 119, 180, 0.15)'
            ),
            row=1, col=1
        )

    if desvios_atr:
        fig.add_trace(
            go.Scatter(
                x=datas_atr,
                y=desvios_atr,
                mode='lines+markers',
                name='<b>ATR</b>',
                line=dict(color=CORES['ATR'], width=3.5),
                marker=dict(size=10, symbol='diamond', line=dict(width=1.5, color='white')),
                hovertemplate='<b>Desvio ATR Real</b><br>Data: %{x}<br>Desvio: %{y:.2f}%<extra></extra>',
                showlegend=False,
                fill='tozeroy',
                fillcolor=f'rgba(255, 127, 14, 0.15)'
            ),
            row=1, col=2
        )

    if desvios_mix:
        fig.add_trace(
            go.Scatter(
                x=datas_mix,
                y=desvios_mix,
                mode='lines+markers',
                name='<b>MIX</b>',
                line=dict(color=CORES['MIX'], width=3.5),
                marker=dict(size=10, symbol='diamond', line=dict(width=1.5, color='white')),
                hovertemplate='<b>Desvio MIX Real</b><br>Data: %{x}<br>Desvio: %{y:.2f}%<extra></extra>',
                showlegend=False,
                fill='tozeroy',
                fillcolor=f'rgba(44, 160, 44, 0.15)'
            ),
            row=2, col=1
        )

    # Resumo de desvios médios (apenas se houver dados)
    desvios_medios = []
    labels = []
    if desvios_moagem:
        desvios_medios.append(np.mean(desvios_moagem))
        labels.append('Moagem')
    if desvios_atr:
        desvios_medios.append(np.mean(desvios_atr))
        labels.append('ATR')
    if desvios_mix:
        desvios_medios.append(np.mean(desvios_mix))
        labels.append('MIX')

    if desvios_medios:
        cores_barras = [CORES.get(label, '#1f77b4') for label in labels]
        fig.add_trace(
            go.Bar(
                x=labels,
                y=desvios_medios,
                marker_color=cores_barras,
                marker_line=dict(color='white', width=2),
                opacity=0.9,
                text=[f'{d:+.2f}%' for d in desvios_medios],
                textposition='outside',
                textfont=dict(size=13, family="Arial", color='black'),
                hovertemplate='<b>%{x}</b><br>Desvio Médio: %{y:+.2f}%<extra></extra>',
                showlegend=False
            ),
            row=2, col=2
        )
    else:
        # Se não há dados, adiciona uma mensagem no gráfico de resumo
        fig.add_annotation(
            text="<b>Não há dados reais suficientes</b>",
            xref="x4", yref="y4",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color="#ffffff", family="Arial"),
            row=2, col=2
        )

    # Linha de referência zero
    for row in [1, 2]:
        for col in [1, 2]:
            if row == 2 and col == 2:
                continue
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=row, col=col)

    # Se não há nenhum dado real, ainda mostra o gráfico (vazio) para indicar que precisa de dados
    # Mas não retorna None para que o gráfico apareça

    fig.update_layout(
        height=800,
        template='plotly_dark',
        font=dict(family="Arial", size=12),
        margin=dict(t=120, b=100, l=70, r=70),
        title=dict(
            text='<b>Desvios da Baseline (Perfil Ideal)</b>',
            font=dict(size=18, family="Arial", color="#ffffff"),
            x=0.5,
            xanchor='center'
        )
    )

    fig.update_xaxes(tickangle=-45, nticks=10, row=1, col=1, tickfont=dict(size=11), gridcolor='rgba(0,0,0,0.1)')
    fig.update_xaxes(tickangle=-45, nticks=10, row=1, col=2, tickfont=dict(size=11), gridcolor='rgba(0,0,0,0.1)')
    fig.update_xaxes(tickangle=-45, nticks=10, row=2, col=1, tickfont=dict(size=11), gridcolor='rgba(0,0,0,0.1)')
    fig.update_xaxes(tickfont=dict(size=12), row=2, col=2)

    fig.update_yaxes(title="<b>Desvio (%)</b>", row=1, col=1, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_yaxes(title="<b>Desvio (%)</b>", row=1, col=2, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_yaxes(title="<b>Desvio (%)</b>", row=2, col=1, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_yaxes(title="<b>Desvio Médio (%)</b>", row=2, col=2, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')

    return fig


def criar_grafico_etanol_detalhado(df):
    """
    Cria gráfico detalhado de produção de etanol (anidro/hidratado, cana/milho).
    """
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            '<b>Etanol de Cana</b>',
            '<b>Etanol de Milho</b>',
            '<b>Etanol Anidro vs Hidratado</b>',
            '<b>Etanol Total Acumulado</b>'
        ),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]],
        vertical_spacing=0.18,
        horizontal_spacing=0.12
    )

    # ========== ETANOL DE CANA ==========
    fig.add_trace(
        go.Bar(
            x=df['Data'],
            y=df['Etanol Anidro Cana (m³)'],
            name='<b>Anidro Cana</b>',
            marker_color=CORES['Etanol_Anidro_Cana'],
            opacity=0.85,
            hovertemplate='<b>Anidro Cana</b><br>Data: %{x}<br>Produção: %{y:,.0f} m³<extra></extra>'
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Bar(
            x=df['Data'],
            y=df['Etanol Hidratado Cana (m³)'],
            name='<b>Hidratado Cana</b>',
            marker_color=CORES['Etanol_Hidratado_Cana'],
            opacity=0.85,
            hovertemplate='<b>Hidratado Cana</b><br>Data: %{x}<br>Produção: %{y:,.0f} m³<extra></extra>'
        ),
        row=1, col=1
    )

    # ========== ETANOL DE MILHO ==========
    fig.add_trace(
        go.Bar(
            x=df['Data'],
            y=df['Etanol Anidro Milho (m³)'],
            name='<b>Anidro Milho</b>',
            marker_color=CORES['Etanol_Anidro_Milho'],
            opacity=0.85,
            hovertemplate='<b>Anidro Milho</b><br>Data: %{x}<br>Produção: %{y:,.0f} m³<extra></extra>',
            showlegend=False
        ),
        row=1, col=2
    )

    fig.add_trace(
        go.Bar(
            x=df['Data'],
            y=df['Etanol Hidratado Milho (m³)'],
            name='<b>Hidratado Milho</b>',
            marker_color=CORES['Etanol_Hidratado_Milho'],
            opacity=0.85,
            hovertemplate='<b>Hidratado Milho</b><br>Data: %{x}<br>Produção: %{y:,.0f} m³<extra></extra>',
            showlegend=False
        ),
        row=1, col=2
    )

    # ========== ANIDRO VS HIDRATADO ==========
    etanol_anidro_total = df['Etanol Anidro Cana (m³)'] + df['Etanol Anidro Milho (m³)']
    etanol_hidratado_total = df['Etanol Hidratado Cana (m³)'] + df['Etanol Hidratado Milho (m³)']

    fig.add_trace(
        go.Bar(
            x=df['Data'],
            y=etanol_anidro_total,
            name='<b>Anidro Total</b>',
            marker_color='#d62728',
            opacity=0.85,
            hovertemplate='<b>Anidro Total</b><br>Data: %{x}<br>Produção: %{y:,.0f} m³<extra></extra>',
            showlegend=False
        ),
        row=2, col=1
    )

    fig.add_trace(
        go.Bar(
            x=df['Data'],
            y=etanol_hidratado_total,
            name='<b>Hidratado Total</b>',
            marker_color='#ff7f0e',
            opacity=0.85,
            hovertemplate='<b>Hidratado Total</b><br>Data: %{x}<br>Produção: %{y:,.0f} m³<extra></extra>',
            showlegend=False
        ),
        row=2, col=1
    )

    # ========== ETANOL TOTAL ACUMULADO ==========
    fig.add_trace(
        go.Scatter(
            x=df['Data'],
            y=df['Etanol Total Acumulado (m³)'],
            name='<b>Total Acumulado</b>',
            line=dict(color=CORES['Acumulado'], width=3.5),
            mode='lines+markers',
            marker=dict(size=6, symbol='circle'),
            fill='tozeroy',
            fillcolor="rgba(140, 86, 75, 0.2)",
            hovertemplate='<b>Total Acumulado</b><br>Data: %{x}<br>Total: %{y:,.0f} m³<extra></extra>',
            showlegend=False
        ),
        row=2, col=2
    )

    fig.update_layout(
        height=850,
        hovermode='x unified',
        template='plotly_dark',
        font=dict(family="Arial", size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=14, color="#ffffff", family="Arial"),
            bgcolor='rgba(0,0,0,0.85)',
            bordercolor='rgba(255,255,255,0.4)',
            borderwidth=1
        ),
        margin=dict(t=120, b=100, l=70, r=70)
    )

    # Configuração de eixos
    fig.update_xaxes(title="<b>Data</b>", row=2, col=1, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title="<b>Data</b>", row=2, col=2, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title="<b>Data</b>", row=1, col=1, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title="<b>Data</b>", row=1, col=2, title_font=dict(size=12), tickangle=-45, nticks=8)

    fig.update_yaxes(title="<b>Produção (m³)</b>", row=1, col=1, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Produção (m³)</b>", row=1, col=2, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Produção (m³)</b>", row=2, col=1, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Total Acumulado (m³)</b>", row=2, col=2, title_font=dict(size=11))

    return fig


def criar_grafico_desvios(df):
    """
    Cria gráfico de desvios entre dados reais e projetados.
    """
    if 'dados_reais' not in st.session_state or not st.session_state.dados_reais:
        st.warning("⚠️ Não há dados reais para comparar. Insira dados reais na página de Acompanhamento de Safra.")
        return None

    # Calcula desvios
    desvios_moagem = []
    desvios_atr = []
    desvios_mix = []
    desvios_acucar = []
    desvios_etanol = []
    datas = []

    for quinzena in sorted(st.session_state.dados_reais.keys()):
        if quinzena <= len(df):
            dados_q = st.session_state.dados_reais[quinzena]
            data_q = df.iloc[quinzena - 1]['Data']

            # Moagem (dados são acumulados, então calcula quinzenal)
            if dados_q.get('moagem_real'):
                moagem_acum = dados_q['moagem_real']
                if quinzena == 1:
                    moagem_q_real = moagem_acum
                else:
                    moagem_ant = st.session_state.dados_reais.get(quinzena - 1, {}).get('moagem_real', 0) or 0
                    moagem_q_real = moagem_acum - moagem_ant
                moagem_q_proj = df.iloc[quinzena - 1]['Moagem']
                if moagem_q_proj > 0:
                    desvio = ((moagem_q_real - moagem_q_proj) / moagem_q_proj) * 100
                    desvios_moagem.append(desvio)
                    datas.append(data_q)

            # ATR
            if dados_q.get('atr_real'):
                atr_real = dados_q['atr_real']
                atr_proj = df.iloc[quinzena - 1]['ATR']
                if atr_proj > 0:
                    desvio = ((atr_real - atr_proj) / atr_proj) * 100
                    desvios_atr.append(desvio)

            # MIX
            if dados_q.get('mix_real'):
                mix_real = dados_q['mix_real']
                mix_proj = df.iloc[quinzena - 1]['MIX']
                if mix_proj > 0:
                    desvio = ((mix_real - mix_proj) / mix_proj) * 100
                    desvios_mix.append(desvio)

            # Açúcar (calcula quinzenal a partir de moagem acumulada)
            if dados_q.get('moagem_real') and dados_q.get('atr_real') and dados_q.get('mix_real'):
                moagem_acum = dados_q['moagem_real']
                if quinzena == 1:
                    moagem_q_real = moagem_acum
                else:
                    moagem_ant = st.session_state.dados_reais.get(quinzena - 1, {}).get('moagem_real', 0) or 0
                    moagem_q_real = moagem_acum - moagem_ant
                acucar_q_real, _ = calcular_producao_quinzenal(moagem_q_real, dados_q['atr_real'], dados_q['mix_real'])
                acucar_q_proj = df.iloc[quinzena - 1]['Açúcar (t)']
                if acucar_q_proj > 0:
                    desvio = ((acucar_q_real - acucar_q_proj) / acucar_q_proj) * 100
                    desvios_acucar.append(desvio)

            # Etanol (dados são acumulados, então calcula quinzenal como diferença)
            total_etanol_acum = 0
            if dados_q.get('etanol_anidro_cana_real'):
                total_etanol_acum += dados_q['etanol_anidro_cana_real']
            if dados_q.get('etanol_hidratado_cana_real'):
                total_etanol_acum += dados_q['etanol_hidratado_cana_real']
            if dados_q.get('etanol_anidro_milho_real'):
                total_etanol_acum += dados_q['etanol_anidro_milho_real']
            if dados_q.get('etanol_hidratado_milho_real'):
                total_etanol_acum += dados_q['etanol_hidratado_milho_real']

            if total_etanol_acum > 0:
                # Calcula quinzenal como diferença
                if quinzena == 1:
                    total_etanol_real = total_etanol_acum
                else:
                    dados_ant = st.session_state.dados_reais.get(quinzena - 1, {})
                    total_ant = 0
                    if dados_ant.get('etanol_anidro_cana_real'):
                        total_ant += dados_ant['etanol_anidro_cana_real']
                    if dados_ant.get('etanol_hidratado_cana_real'):
                        total_ant += dados_ant['etanol_hidratado_cana_real']
                    if dados_ant.get('etanol_anidro_milho_real'):
                        total_ant += dados_ant['etanol_anidro_milho_real']
                    if dados_ant.get('etanol_hidratado_milho_real'):
                        total_ant += dados_ant['etanol_hidratado_milho_real']
                    total_etanol_real = total_etanol_acum - total_ant

                etanol_q_proj = df.iloc[quinzena - 1]['Etanol Total (m³)']
                if etanol_q_proj > 0:
                    desvio = ((total_etanol_real - etanol_q_proj) / etanol_q_proj) * 100
                    desvios_etanol.append(desvio)

    if not datas:
        st.warning("⚠️ Não há dados suficientes para calcular desvios.")
        return None

    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=(
            '<b>Desvio Moagem (%)</b>',
            '<b>Desvio ATR (%)</b>',
            '<b>Desvio MIX (%)</b>',
            '<b>Desvio Açúcar (%)</b>',
            '<b>Desvio Etanol (%)</b>',
            '<b>Resumo de Desvios</b>'
        ),
        specs=[[{"type": "scatter"}, {"type": "scatter"}, {"type": "scatter"}],
               [{"type": "scatter"}, {"type": "scatter"}, {"type": "bar"}]],
        vertical_spacing=0.15,
        horizontal_spacing=0.12
    )

    # Desvios individuais com melhorias visuais
    if desvios_moagem:
        fig.add_trace(
            go.Scatter(
                x=datas[:len(desvios_moagem)],
                y=desvios_moagem,
                mode='lines+markers',
                name='<b>Moagem</b>',
                line=dict(color=CORES['Moagem'], width=3.5),
                marker=dict(size=10, symbol='diamond', line=dict(width=1.5, color='white')),
                fill='tozeroy',
                fillcolor='rgba(31, 119, 180, 0.15)',
                hovertemplate='<b>Desvio Moagem</b><br>Data: %{x}<br>Desvio: %{y:+.2f}%<extra></extra>',
                showlegend=False
            ),
            row=1, col=1
        )

    if desvios_atr:
        fig.add_trace(
            go.Scatter(
                x=datas[:len(desvios_atr)],
                y=desvios_atr,
                mode='lines+markers',
                name='<b>ATR</b>',
                line=dict(color=CORES['ATR'], width=3.5),
                marker=dict(size=10, symbol='diamond', line=dict(width=1.5, color='white')),
                fill='tozeroy',
                fillcolor='rgba(255, 127, 14, 0.15)',
                hovertemplate='<b>Desvio ATR</b><br>Data: %{x}<br>Desvio: %{y:+.2f}%<extra></extra>',
                showlegend=False
            ),
            row=1, col=2
        )

    if desvios_mix:
        fig.add_trace(
            go.Scatter(
                x=datas[:len(desvios_mix)],
                y=desvios_mix,
                mode='lines+markers',
                name='<b>MIX</b>',
                line=dict(color=CORES['MIX'], width=3.5),
                marker=dict(size=10, symbol='diamond', line=dict(width=1.5, color='white')),
                fill='tozeroy',
                fillcolor='rgba(44, 160, 44, 0.15)',
                hovertemplate='<b>Desvio MIX</b><br>Data: %{x}<br>Desvio: %{y:+.2f}%<extra></extra>',
                showlegend=False
            ),
            row=1, col=3
        )

    if desvios_acucar:
        fig.add_trace(
            go.Scatter(
                x=datas[:len(desvios_acucar)],
                y=desvios_acucar,
                mode='lines+markers',
                name='<b>Açúcar</b>',
                line=dict(color=CORES['Açúcar'], width=3.5),
                marker=dict(size=10, symbol='diamond', line=dict(width=1.5, color='white')),
                fill='tozeroy',
                fillcolor='rgba(214, 39, 40, 0.15)',
                hovertemplate='<b>Desvio Açúcar</b><br>Data: %{x}<br>Desvio: %{y:+.2f}%<extra></extra>',
                showlegend=False
            ),
            row=2, col=1
        )

    if desvios_etanol:
        fig.add_trace(
            go.Scatter(
                x=datas[:len(desvios_etanol)],
                y=desvios_etanol,
                mode='lines+markers',
                name='<b>Etanol</b>',
                line=dict(color=CORES['Etanol'], width=3.5),
                marker=dict(size=10, symbol='diamond', line=dict(width=1.5, color='white')),
                fill='tozeroy',
                fillcolor='rgba(148, 103, 189, 0.15)',
                hovertemplate='<b>Desvio Etanol</b><br>Data: %{x}<br>Desvio: %{y:+.2f}%<extra></extra>',
                showlegend=False
            ),
            row=2, col=2
        )

    # Resumo de desvios médios
    desvios_medios = []
    labels = []
    if desvios_moagem:
        desvios_medios.append(np.mean(desvios_moagem))
        labels.append('Moagem')
    if desvios_atr:
        desvios_medios.append(np.mean(desvios_atr))
        labels.append('ATR')
    if desvios_mix:
        desvios_medios.append(np.mean(desvios_mix))
        labels.append('MIX')
    if desvios_acucar:
        desvios_medios.append(np.mean(desvios_acucar))
        labels.append('Açúcar')
    if desvios_etanol:
        desvios_medios.append(np.mean(desvios_etanol))
        labels.append('Etanol')

    if desvios_medios:
        cores_barras = [CORES.get(label, '#1f77b4') for label in labels]
        fig.add_trace(
            go.Bar(
                x=labels,
                y=desvios_medios,
                marker_color=cores_barras,
                marker_line=dict(color='white', width=2),
                opacity=0.9,
                text=[f'{d:+.2f}%' for d in desvios_medios],
                textposition='outside',
                textfont=dict(size=13, family="Arial", color='black'),
                hovertemplate='<b>%{x}</b><br>Desvio Médio: %{y:+.2f}%<extra></extra>',
                showlegend=False
            ),
            row=2, col=3
        )

    # Linha de referência zero
    for row in [1, 2]:
        for col in [1, 2, 3]:
            if row == 1 or col < 3:
                fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=row, col=col)

    fig.update_layout(
        height=900,
        template='plotly_dark',
        font=dict(family="Arial", size=12),
        margin=dict(t=120, b=100, l=70, r=70),
        title=dict(
            text='<b>Análise de Desvios - Real vs Projetado</b>',
            font=dict(size=18, family="Arial", color="#ffffff"),
            x=0.5,
            xanchor='center'
        )
    )
    
    # Melhora eixos
    for row in [1, 2]:
        for col in [1, 2, 3]:
            if row == 1 or col < 3:
                fig.update_xaxes(tickangle=-45, nticks=8, tickfont=dict(size=11), gridcolor='rgba(0,0,0,0.1)', row=row, col=col)
                fig.update_yaxes(title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)', row=row, col=col)
            else:
                fig.update_xaxes(tickfont=dict(size=12), row=row, col=col)
                fig.update_yaxes(title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)', row=row, col=col)

    fig.update_xaxes(tickangle=-45, nticks=8, row=1, col=1)
    fig.update_xaxes(tickangle=-45, nticks=8, row=1, col=2)
    fig.update_xaxes(tickangle=-45, nticks=8, row=1, col=3)
    fig.update_xaxes(tickangle=-45, nticks=8, row=2, col=1)
    fig.update_xaxes(tickangle=-45, nticks=8, row=2, col=2)

    fig.update_yaxes(title="<b>Desvio (%)</b>", row=1, col=1, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Desvio (%)</b>", row=1, col=2, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Desvio (%)</b>", row=1, col=3, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Desvio (%)</b>", row=2, col=1, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Desvio (%)</b>", row=2, col=2, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Desvio Médio (%)</b>", row=2, col=3, title_font=dict(size=11))

    return fig


def criar_grafico_precos_real_vs_simulado(df):
    """
    Cria gráfico comparando preços reais vs simulados.
    """
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            '<b>NY11 - Real vs Simulado</b>',
            '<b>USD/BRL - Real vs Simulado</b>',
            '<b>Etanol Anidro - Real vs Simulado</b>',
            '<b>Etanol Hidratado - Real vs Simulado</b>'
        ),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]],
        vertical_spacing=0.18,
        horizontal_spacing=0.12
    )

    # NY11
    fig.add_trace(
        go.Scatter(
            x=df['Data'],
            y=df['NY11_cents'],
            name='<b>NY11 Simulado</b>',
            line=dict(color=CORES['NY11'], width=3, dash='dash'),
            mode='lines+markers',
            marker=dict(size=6, symbol='circle'),
            hovertemplate='<b>NY11 Simulado</b><br>Data: %{x}<br>Preço: %{y:.2f} USc/lb<extra></extra>',
            showlegend=False
        ),
        row=1, col=1
    )

    # USD/BRL
    fig.add_trace(
        go.Scatter(
            x=df['Data'],
            y=df['USD_BRL'],
            name='<b>USD/BRL Simulado</b>',
            line=dict(color=CORES['USD_BRL'], width=3, dash='dash'),
            mode='lines+markers',
            marker=dict(size=6, symbol='square'),
            hovertemplate='<b>USD/BRL Simulado</b><br>Data: %{x}<br>Câmbio: %{y:.2f}<extra></extra>',
            showlegend=False
        ),
        row=1, col=2
    )

    # Etanol Anidro
    if 'Etanol Anidro Preço (R$/m³)' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Data'],
                y=df['Etanol Anidro Preço (R$/m³)'],
                name='<b>Etanol Anidro Simulado</b>',
                line=dict(color='#d62728', width=3, dash='dash'),
                mode='lines+markers',
                marker=dict(size=6, symbol='diamond'),
                hovertemplate='<b>Etanol Anidro Simulado</b><br>Data: %{x}<br>Preço: R$ %{y:,.0f}/m³<extra></extra>',
                showlegend=False
            ),
            row=2, col=1
        )

    # Etanol Hidratado
    if 'Etanol Hidratado Preço (R$/m³)' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Data'],
                y=df['Etanol Hidratado Preço (R$/m³)'],
                name='<b>Etanol Hidratado Simulado</b>',
                line=dict(color='#ff7f0e', width=3, dash='dash'),
                mode='lines+markers',
                marker=dict(size=6, symbol='diamond'),
                hovertemplate='<b>Etanol Hidratado Simulado</b><br>Data: %{x}<br>Preço: R$ %{y:,.0f}/m³<extra></extra>',
                showlegend=False
            ),
            row=2, col=2
        )

    # Adiciona dados reais se disponíveis
    if 'dados_reais' in st.session_state and st.session_state.dados_reais:
        datas_reais_ny11 = []
        valores_reais_ny11 = []
        datas_reais_usd = []
        valores_reais_usd = []
        datas_reais_etanol_anidro = []
        valores_reais_etanol_anidro = []
        datas_reais_etanol_hidratado = []
        valores_reais_etanol_hidratado = []

        for quinzena in sorted(st.session_state.dados_reais.keys()):
            if quinzena <= len(df):
                dados_q = st.session_state.dados_reais[quinzena]
                data_q = df.iloc[quinzena - 1]['Data']

                if dados_q.get('ny11_real'):
                    datas_reais_ny11.append(data_q)
                    valores_reais_ny11.append(dados_q['ny11_real'])

                if dados_q.get('usd_real'):
                    datas_reais_usd.append(data_q)
                    valores_reais_usd.append(dados_q['usd_real'])

                if dados_q.get('etanol_anidro_preco_real'):
                    datas_reais_etanol_anidro.append(data_q)
                    valores_reais_etanol_anidro.append(dados_q['etanol_anidro_preco_real'])

                if dados_q.get('etanol_hidratado_preco_real'):
                    datas_reais_etanol_hidratado.append(data_q)
                    valores_reais_etanol_hidratado.append(dados_q['etanol_hidratado_preco_real'])

        if valores_reais_ny11:
            fig.add_trace(
                go.Scatter(
                    x=datas_reais_ny11,
                    y=valores_reais_ny11,
                    name='<b>NY11 Real</b>',
                    line=dict(color=CORES['Real'], width=4),
                    mode='lines+markers',
                    marker=dict(size=8, symbol='diamond'),
                    hovertemplate='<b>NY11 Real</b><br>Data: %{x}<br>Preço: %{y:.2f} USc/lb<extra></extra>',
                    showlegend=False
                ),
                row=1, col=1
            )

        if valores_reais_usd:
            fig.add_trace(
                go.Scatter(
                    x=datas_reais_usd,
                    y=valores_reais_usd,
                    name='<b>USD/BRL Real</b>',
                    line=dict(color=CORES['Real'], width=4),
                    mode='lines+markers',
                    marker=dict(size=8, symbol='diamond'),
                    hovertemplate='<b>USD/BRL Real</b><br>Data: %{x}<br>Câmbio: %{y:.2f}<extra></extra>',
                    showlegend=False
                ),
                row=1, col=2
            )

        if valores_reais_etanol_anidro:
            fig.add_trace(
                go.Scatter(
                    x=datas_reais_etanol_anidro,
                    y=valores_reais_etanol_anidro,
                    name='<b>Etanol Anidro Real</b>',
                    line=dict(color=CORES['Real'], width=4),
                    mode='lines+markers',
                    marker=dict(size=8, symbol='diamond'),
                    hovertemplate='<b>Etanol Anidro Real</b><br>Data: %{x}<br>Preço: R$ %{y:,.0f}/m³<extra></extra>',
                    showlegend=False
                ),
                row=2, col=1
            )

        if valores_reais_etanol_hidratado:
            fig.add_trace(
                go.Scatter(
                    x=datas_reais_etanol_hidratado,
                    y=valores_reais_etanol_hidratado,
                    name='<b>Etanol Hidratado Real</b>',
                    line=dict(color=CORES['Real'], width=4),
                    mode='lines+markers',
                    marker=dict(size=8, symbol='diamond'),
                    hovertemplate='<b>Etanol Hidratado Real</b><br>Data: %{x}<br>Preço: R$ %{y:,.0f}/m³<extra></extra>',
                    showlegend=False
                ),
                row=2, col=2
            )

    fig.update_layout(
        height=850,
        hovermode='x unified',
        template='plotly_dark',
        font=dict(family="Arial", size=12),
        margin=dict(t=120, b=100, l=70, r=70),
        title=dict(
            text='<b>Preços - Real vs Simulado</b>',
            font=dict(size=18, family="Arial", color="#ffffff"),
            x=0.5,
            xanchor='center'
        )
    )

    fig.update_xaxes(title="<b>Data</b>", row=1, col=1, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title="<b>Data</b>", row=1, col=2, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title="<b>Data</b>", row=2, col=1, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title="<b>Data</b>", row=2, col=2, title_font=dict(size=12), tickangle=-45, nticks=8)

    fig.update_yaxes(title="<b>NY11 (USc/lb)</b>", row=1, col=1, title_font=dict(size=11))
    fig.update_yaxes(title="<b>USD/BRL</b>", row=1, col=2, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Preço (R$/m³)</b>", row=2, col=1, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Preço (R$/m³)</b>", row=2, col=2, title_font=dict(size=11))

    return fig


def criar_grafico_analise_estatistica(df):
    """
    Cria gráfico com análises estatísticas avançadas e profundas.
    """
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=(
            '<b>Distribuição de Moagem</b>',
            '<b>Distribuição de ATR</b>',
            '<b>Distribuição de MIX</b>',
            '<b>Box Plot - Parâmetros de Safra</b>',
            '<b>Correlação Produção vs Preços</b>',
            '<b>Análise de Tendências</b>'
        ),
        specs=[[{"type": "histogram"}, {"type": "histogram"}],
               [{"type": "histogram"}, {"type": "box"}],
               [{"type": "scatter"}, {"type": "scatter"}]],
        vertical_spacing=0.15,
        horizontal_spacing=0.12,
        row_heights=[0.3, 0.3, 0.4]
    )

    # Histograma Moagem com linha de média
    media_moagem = df['Moagem'].mean()
    std_moagem = df['Moagem'].std()
    fig.add_trace(
        go.Histogram(
            x=df['Moagem'],
            name='<b>Moagem</b>',
            marker_color=CORES['Moagem'],
            opacity=0.75,
            nbinsx=20,
            hovertemplate='<b>Moagem</b><br>Valor: %{x:,.0f} ton<br>Frequência: %{y}<extra></extra>',
            showlegend=False
        ),
        row=1, col=1
    )
    fig.add_vline(x=media_moagem, line_dash="dash", line_color="red", 
                  annotation_text=f"Média: {media_moagem:,.0f}", row=1, col=1)

    # Histograma ATR com linha de média
    media_atr = df['ATR'].mean()
    std_atr = df['ATR'].std()
    fig.add_trace(
        go.Histogram(
            x=df['ATR'],
            name='<b>ATR</b>',
            marker_color=CORES['ATR'],
            opacity=0.75,
            nbinsx=20,
            hovertemplate='<b>ATR</b><br>Valor: %{x:.2f} kg/t<br>Frequência: %{y}<extra></extra>',
            showlegend=False
        ),
        row=1, col=2
    )
    fig.add_vline(x=media_atr, line_dash="dash", line_color="red",
                  annotation_text=f"Média: {media_atr:.2f}", row=1, col=2)

    # Histograma MIX com linha de média
    media_mix = df['MIX'].mean()
    std_mix = df['MIX'].std()
    fig.add_trace(
        go.Histogram(
            x=df['MIX'],
            name='<b>MIX</b>',
            marker_color=CORES['MIX'],
            opacity=0.75,
            nbinsx=20,
            hovertemplate='<b>MIX</b><br>Valor: %{x:.2f}%<br>Frequência: %{y}<extra></extra>',
            showlegend=False
        ),
        row=2, col=1
    )
    fig.add_vline(x=media_mix, line_dash="dash", line_color="red",
                  annotation_text=f"Média: {media_mix:.2f}%", row=2, col=1)

    # Box Plot comparativo
    fig.add_trace(
        go.Box(
            y=df['Moagem'],
            name='Moagem',
            marker_color=CORES['Moagem'],
            boxmean='sd',
            hovertemplate='<b>Moagem</b><br>%{y:,.0f} ton<extra></extra>',
            showlegend=False
        ),
        row=2, col=2
    )
    fig.add_trace(
        go.Box(
            y=df['ATR'],
            name='ATR',
            marker_color=CORES['ATR'],
            boxmean='sd',
            hovertemplate='<b>ATR</b><br>%{y:.2f} kg/t<extra></extra>',
            showlegend=False
        ),
        row=2, col=2
    )
    fig.add_trace(
        go.Box(
            y=df['MIX'],
            name='MIX',
            marker_color=CORES['MIX'],
            boxmean='sd',
            hovertemplate='<b>MIX</b><br>%{y:.2f}%<extra></extra>',
            showlegend=False
        ),
        row=2, col=2
    )

    # Correlação Produção vs Preços com linha de tendência
    if 'Açúcar (t)' in df.columns and 'NY11_cents' in df.columns:
        # Calcula correlação
        correlacao = df['Açúcar (t)'].corr(df['NY11_cents'])
        
        fig.add_trace(
            go.Scatter(
                x=df['Açúcar (t)'],
                y=df['NY11_cents'],
                mode='markers',
                name='<b>NY11 vs Açúcar</b>',
                marker=dict(color=CORES['NY11'], size=10, opacity=0.7, 
                           line=dict(width=1, color='white')),
                hovertemplate='<b>NY11 vs Açúcar</b><br>Açúcar: %{x:,.0f} t<br>NY11: %{y:.2f} USc/lb<extra></extra>',
                showlegend=False
            ),
            row=3, col=1
        )
        
        # Adiciona linha de tendência
        z = np.polyfit(df['Açúcar (t)'], df['NY11_cents'], 1)
        p = np.poly1d(z)
        fig.add_trace(
            go.Scatter(
                x=df['Açúcar (t)'],
                y=p(df['Açúcar (t)']),
                mode='lines',
                name=f'Tendência (r={correlacao:.3f})',
                line=dict(color='red', width=3, dash='dash'),
                hovertemplate=f'<b>Tendência</b><br>Correlação: {correlacao:.3f}<extra></extra>',
                showlegend=False
            ),
            row=3, col=1
        )

    # Análise de tendências temporais
    if 'Data' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Data'],
                y=df['Moagem'].rolling(window=3, center=True).mean() if len(df) > 3 else df['Moagem'],
                name='<b>Tendência Moagem</b>',
                line=dict(color=CORES['Moagem'], width=3),
                mode='lines',
                hovertemplate='<b>Tendência Moagem</b><br>Data: %{x}<br>Média Móvel: %{y:,.0f} ton<extra></extra>',
                showlegend=False
            ),
            row=3, col=2
        )
        fig.add_trace(
            go.Scatter(
                x=df['Data'],
                y=df['ATR'].rolling(window=3, center=True).mean() if len(df) > 3 else df['ATR'],
                name='<b>Tendência ATR</b>',
                line=dict(color=CORES['ATR'], width=3),
                mode='lines',
                hovertemplate='<b>Tendência ATR</b><br>Data: %{x}<br>Média Móvel: %{y:.2f} kg/t<extra></extra>',
                showlegend=False
            ),
            row=3, col=2
        )

    fig.update_layout(
        height=1000,
        template='plotly_dark',
        font=dict(family="Arial", size=12),
        margin=dict(t=120, b=100, l=70, r=70),
        title=dict(
            text='<b>Análise Estatística Avançada</b>',
            font=dict(size=20, family="Arial", color="#1f1f1f"),
            x=0.5,
            xanchor='center'
        )
    )

    fig.update_xaxes(title="<b>Moagem (ton)</b>", row=1, col=1, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_xaxes(title="<b>ATR (kg/t)</b>", row=1, col=2, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_xaxes(title="<b>MIX (%)</b>", row=2, col=1, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_xaxes(title="<b>Parâmetro</b>", row=2, col=2, title_font=dict(size=12))
    fig.update_xaxes(title="<b>Açúcar (t)</b>", row=3, col=1, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_xaxes(title="<b>Data</b>", row=3, col=2, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)', tickangle=-45)

    fig.update_yaxes(title="<b>Frequência</b>", row=1, col=1, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_yaxes(title="<b>Frequência</b>", row=1, col=2, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_yaxes(title="<b>Frequência</b>", row=2, col=1, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_yaxes(title="<b>Valor</b>", row=2, col=2, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_yaxes(title="<b>NY11 (USc/lb)</b>", row=3, col=1, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')
    fig.update_yaxes(title="<b>Valor</b>", row=3, col=2, title_font=dict(size=12), gridcolor='rgba(0,0,0,0.1)')

    return fig


# ============================================================================
# INTERFACE
# ============================================================================

# Sidebar com parâmetros (mesmos do acompanhamento_safra.py)
# Usa session_state para persistir valores
st.sidebar.header("📊 Parâmetros da Safra")

# Inicializa valores no session_state se não existirem
if 'grafico_moagem' not in st.session_state:
    st.session_state.grafico_moagem = 600_000_000
if 'grafico_atr' not in st.session_state:
    st.session_state.grafico_atr = 135.0
if 'grafico_mix' not in st.session_state:
    st.session_state.grafico_mix = 48.0
if 'grafico_n_quinz' not in st.session_state:
    st.session_state.grafico_n_quinz = 24
if 'grafico_data_start' not in st.session_state:
    st.session_state.grafico_data_start = date(date.today().year, 4, 1)
if 'grafico_ny11_inicial' not in st.session_state:
    st.session_state.grafico_ny11_inicial = 14.90
if 'grafico_usd_inicial' not in st.session_state:
    st.session_state.grafico_usd_inicial = 4.90
if 'grafico_etanol_inicial' not in st.session_state:
    st.session_state.grafico_etanol_inicial = 2500.0
if 'grafico_preco_ref' not in st.session_state:
    st.session_state.grafico_preco_ref = 15.0
if 'grafico_sensibilidade' not in st.session_state:
    st.session_state.grafico_sensibilidade = 10.0

# Tenta carregar valores de acompanhamento_safra.py se disponíveis
if 'simulacao_moagem' in st.session_state:
    st.session_state.grafico_moagem = st.session_state.simulacao_moagem
if 'simulacao_atr' in st.session_state:
    st.session_state.grafico_atr = st.session_state.simulacao_atr
if 'simulacao_mix' in st.session_state:
    st.session_state.grafico_mix = st.session_state.simulacao_mix
if 'simulacao_n_quinz' in st.session_state:
    st.session_state.grafico_n_quinz = st.session_state.simulacao_n_quinz
if 'simulacao_data_start' in st.session_state:
    st.session_state.grafico_data_start = st.session_state.simulacao_data_start

moagem = st.sidebar.number_input(
    "Moagem total estimada (ton)",
    value=st.session_state.grafico_moagem,
    step=10_000_000,
    key="input_grafico_moagem"
)
atr = st.sidebar.number_input(
    "ATR médio estimado (kg/t)",
    value=st.session_state.grafico_atr,
    step=1.0,
    format="%.1f",
    key="input_grafico_atr"
)
mix = st.sidebar.number_input(
    "Mix açúcar estimado (%)",
    value=st.session_state.grafico_mix,
    step=1.0,
    format="%.1f",
    key="input_grafico_mix"
)

# Salva valores no session_state
st.session_state.grafico_moagem = moagem
st.session_state.grafico_atr = atr
st.session_state.grafico_mix = mix

st.sidebar.divider()

st.sidebar.subheader("⚙️ Simulação")
n_quinz = st.sidebar.number_input(
    "Nº de quinzenas",
    value=st.session_state.grafico_n_quinz,
    min_value=4,
    max_value=24,
    step=1,
    key="input_grafico_n_quinz"
)
data_start = st.sidebar.date_input(
    "Início da safra",
    value=st.session_state.grafico_data_start,
    key="input_grafico_data_start"
)

# Salva valores no session_state
st.session_state.grafico_n_quinz = n_quinz
st.session_state.grafico_data_start = data_start

st.sidebar.divider()

st.sidebar.subheader("💰 Preços Iniciais")
ny11_inicial = st.sidebar.number_input(
    "NY11 inicial (USc/lb)",
    value=st.session_state.grafico_ny11_inicial,
    step=0.10,
    format="%.2f",
    key="input_grafico_ny11"
)
usd_inicial = st.sidebar.number_input(
    "USD/BRL inicial",
    value=st.session_state.grafico_usd_inicial,
    step=0.01,
    format="%.2f",
    key="input_grafico_usd"
)
etanol_inicial = st.sidebar.number_input(
    "Etanol inicial (R$/m³)",
    value=st.session_state.grafico_etanol_inicial,
    step=50.0,
    format="%.0f",
    key="input_grafico_etanol"
)

# Salva valores no session_state
st.session_state.grafico_ny11_inicial = ny11_inicial
st.session_state.grafico_usd_inicial = usd_inicial
st.session_state.grafico_etanol_inicial = etanol_inicial

with st.sidebar.expander("🔧 Parâmetros Avançados", expanded=False):
    st.caption("⚙️ Ajustes finos da simulação (opcional)")
    preco_ref = st.number_input(
        "Preço referência NY11 (USc/lb)",
        value=st.session_state.grafico_preco_ref,
        step=0.5,
        format="%.1f",
        key="input_grafico_preco_ref"
    )
    sensibilidade = st.slider(
        "Sensibilidade oferta → preço (%)",
        0.0, 30.0,
        st.session_state.grafico_sensibilidade,
        1.0,
        key="input_grafico_sensibilidade"
    )

    # Salva valores no session_state
    st.session_state.grafico_preco_ref = preco_ref
    st.session_state.grafico_sensibilidade = sensibilidade

# Inicializa dados reais no session_state (compartilhado com acompanhamento_safra)
if 'dados_reais' not in st.session_state:
    st.session_state.dados_reais = {}

# Inicializa choques
if 'choques_safra' not in st.session_state:
    st.session_state.choques_safra = {}

if 'choques_precos' not in st.session_state:
    st.session_state.choques_precos = {}

# ============ GERAÇÃO DE DADOS ============

# Gera projeção quinzenal
# Usa volatilidade de etanol por padrão (pode ser desabilitado se necessário)
df_projecao = gerar_projecao_quinzenal(
    moagem, atr, mix, int(n_quinz), data_start,
    st.session_state.dados_reais if st.session_state.dados_reais else None,
    st.session_state.choques_safra if st.session_state.choques_safra else None,
    seed=42,
    usar_volatilidade_etanol=True  # Ativa simulação com volatilidade
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

# ============ EXIBIÇÃO DE GRÁFICOS ============

st.divider()

# Seletor de gráficos
tipo_grafico = st.selectbox(
    "📊 Selecione o tipo de gráfico:",
    [
        "Moagem - Real vs Projetado vs Baseline",
        "ATR - Real vs Projetado vs Baseline",
        "MIX - Real vs Projetado vs Baseline",
        "Açúcar - Real vs Projetado vs Baseline",
        "Etanol - Real vs Projetado vs Baseline",
        "Desvios da Baseline",
        "Etanol Detalhado",
        "Análise de Desvios",
        "Preços Real vs Simulado",
        "Análise Estatística",
        "Evolução de Parâmetros de Safra",
        "Produção Acumulada"
    ],
    key="tipo_grafico_safra"
)

st.divider()

# Gera gráficos baseado na seleção
if tipo_grafico == "Moagem - Real vs Projetado vs Baseline":
    st.subheader("📊 Moagem - Real vs Projetado vs Baseline")
    fig = criar_grafico_comparacao_real_projetado(df_completo, 'Moagem', 'Moagem', 'ton', 'Moagem (ton)')
    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 Este gráfico compara a moagem real, projetada e baseline (perfil ideal) em um único gráfico.")

elif tipo_grafico == "ATR - Real vs Projetado vs Baseline":
    st.subheader("📊 ATR - Real vs Projetado vs Baseline")
    fig = criar_grafico_comparacao_real_projetado(df_completo, 'ATR', 'ATR', 'kg/t', 'ATR (kg/t)')
    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 Este gráfico compara o ATR real, projetado e baseline (perfil ideal) em um único gráfico.")

elif tipo_grafico == "MIX - Real vs Projetado vs Baseline":
    st.subheader("📊 MIX - Real vs Projetado vs Baseline")
    fig = criar_grafico_comparacao_real_projetado(df_completo, 'MIX', 'MIX', '%', 'MIX (%)')
    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 Este gráfico compara o MIX real, projetado e baseline (perfil ideal) em um único gráfico.")

elif tipo_grafico == "Açúcar - Real vs Projetado vs Baseline":
    st.subheader("📊 Açúcar - Real vs Projetado vs Baseline")
    fig = criar_grafico_comparacao_real_projetado(df_completo, 'Açúcar (t)', 'Açúcar', 't', 'Açúcar (t)')
    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 Este gráfico compara a produção de açúcar real, projetada e baseline (perfil ideal) em um único gráfico.")

elif tipo_grafico == "Etanol - Real vs Projetado vs Baseline":
    st.subheader("📊 Etanol - Real vs Projetado vs Baseline")
    fig = criar_grafico_comparacao_real_projetado(df_completo, 'Etanol Total (m³)', 'Etanol Total', 'm³', 'Etanol Total (m³)')
    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 Este gráfico compara a produção de etanol real, projetada e baseline (perfil ideal) em um único gráfico.")

elif tipo_grafico == "Desvios da Baseline":
    st.subheader("📈 Desvios da Baseline (Perfil Ideal)")
    fig = criar_grafico_desvios_baseline(df_completo)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
        st.caption("💡 Este gráfico mostra os desvios percentuais entre dados reais e a baseline (perfil ideal). Valores positivos indicam que o real está acima da baseline.")
    else:
        st.warning("⚠️ Não há dados baseline disponíveis ou não há dados reais suficientes.")

elif tipo_grafico == "Etanol Detalhado":
    st.subheader("🍯 Etanol Detalhado - Anidro/Hidratado, Cana/Milho")
    fig = criar_grafico_etanol_detalhado(df_completo)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 Este gráfico mostra a produção detalhada de etanol por tipo (anidro/hidratado) e origem (cana/milho).")

elif tipo_grafico == "Análise de Desvios":
    st.subheader("📈 Análise de Desvios - Real vs Projetado")
    fig = criar_grafico_desvios(df_completo)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
        st.caption("💡 Este gráfico mostra os desvios percentuais entre dados reais e projetados. Valores positivos indicam que o real está acima do projetado.")
    else:
        st.warning("⚠️ Não há dados reais suficientes para calcular desvios. Insira dados reais na página de Acompanhamento de Safra.")

elif tipo_grafico == "Preços Real vs Simulado":
    st.subheader("💰 Preços - Real vs Simulado")
    fig = criar_grafico_precos_real_vs_simulado(df_completo)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 Este gráfico compara os preços reais (quando disponíveis) com os preços simulados.")

elif tipo_grafico == "Análise Estatística":
    st.subheader("📊 Análise Estatística Avançada")
    fig = criar_grafico_analise_estatistica(df_completo)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 Este gráfico mostra análises estatísticas: distribuições e correlações entre variáveis.")

elif tipo_grafico == "Evolução de Parâmetros de Safra":
    st.subheader("🌾 Evolução dos Parâmetros de Safra")
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=(
            '<b>Evolução da Moagem Quinzenal</b>',
            '<b>Evolução do ATR</b>',
            '<b>Evolução do MIX</b>'
        ),
        vertical_spacing=0.15,
        row_heights=[0.4, 0.3, 0.3]
    )

    fig.add_trace(
        go.Scatter(
            x=df_completo['Data'],
            y=df_completo['Moagem'],
            name='<b>Moagem</b>',
            line=dict(color=CORES['Moagem'], width=3),
            mode='lines+markers',
            marker=dict(size=6, symbol='circle'),
            fill='tozeroy',
            fillcolor="rgba(31, 119, 180, 0.2)",
            hovertemplate='<b>Moagem</b><br>Data: %{x}<br>Moagem: %{y:,.0f} ton<extra></extra>'
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df_completo['Data'],
            y=df_completo['ATR'],
            name='<b>ATR</b>',
            line=dict(color=CORES['ATR'], width=3),
            mode='lines+markers',
            marker=dict(size=6, symbol='square'),
            hovertemplate='<b>ATR</b><br>Data: %{x}<br>ATR: %{y:.2f} kg/t<extra></extra>'
        ),
        row=2, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df_completo['Data'],
            y=df_completo['MIX'],
            name='<b>MIX</b>',
            line=dict(color=CORES['MIX'], width=3),
            mode='lines+markers',
            marker=dict(size=6, symbol='diamond'),
            fill='tozeroy',
            fillcolor="rgba(44, 160, 44, 0.2)",
            hovertemplate='<b>MIX</b><br>Data: %{x}<br>MIX: %{y:.2f}%<extra></extra>'
        ),
        row=3, col=1
    )

    fig.update_layout(
        height=850,
        hovermode='x unified',
        template='plotly_dark',
        font=dict(family="Arial", size=11),
        showlegend=False,
        margin=dict(t=80, b=100, l=60, r=60)
    )

    fig.update_xaxes(title="<b>Data</b>", row=1, col=1, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title="<b>Data</b>", row=2, col=1, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title="<b>Data</b>", row=3, col=1, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_yaxes(title="<b>Moagem (ton)</b>", row=1, col=1, title_font=dict(size=12))
    fig.update_yaxes(title="<b>ATR (kg/t)</b>", row=2, col=1, title_font=dict(size=12))
    fig.update_yaxes(title="<b>MIX (%)</b>", row=3, col=1, title_font=dict(size=12))

    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 Este gráfico mostra a evolução dos principais parâmetros de safra: Moagem, ATR e MIX.")

elif tipo_grafico == "Produção Acumulada":
    st.subheader("📦 Produção Acumulada")
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            '<b>Produção Acumulada de Açúcar</b>',
            '<b>Produção Acumulada de Etanol</b>'
        ),
        specs=[[{"secondary_y": True}, {"secondary_y": True}]],
        horizontal_spacing=0.12
    )

    df_acum = df_completo.copy()
    df_acum['Açúcar Acumulado (t)'] = df_acum['Açúcar (t)'].cumsum()
    df_acum['Etanol Acumulado (m³)'] = df_acum['Etanol Total (m³)'].cumsum()

    fig.add_trace(
        go.Scatter(
            x=df_acum['Data'],
            y=df_acum['Açúcar Acumulado (t)'],
            name='<b>Açúcar Acumulado</b>',
            line=dict(color=CORES['Açúcar'], width=3.5),
            mode='lines',
            fill='tozeroy',
            fillcolor="rgba(214, 39, 40, 0.2)",
            hovertemplate='<b>Açúcar Acumulado</b><br>Data: %{x}<br>Total: %{y:,.0f} t<extra></extra>'
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Bar(
            x=df_acum['Data'],
            y=df_acum['Açúcar (t)'],
            name='<b>Açúcar Quinzenal</b>',
            marker_color=CORES['Quinzenal'],
            opacity=0.6,
            hovertemplate='<b>Açúcar Quinzenal</b><br>Data: %{x}<br>Produção: %{y:,.0f} t<extra></extra>',
            showlegend=False
        ),
        row=1, col=1, secondary_y=True
    )

    fig.add_trace(
        go.Scatter(
            x=df_acum['Data'],
            y=df_acum['Etanol Acumulado (m³)'],
            name='<b>Etanol Acumulado</b>',
            line=dict(color=CORES['Etanol'], width=3.5),
            mode='lines',
            fill='tozeroy',
            fillcolor="rgba(44, 160, 44, 0.2)",
            hovertemplate='<b>Etanol Acumulado</b><br>Data: %{x}<br>Total: %{y:,.0f} m³<extra></extra>'
        ),
        row=1, col=2
    )

    fig.add_trace(
        go.Bar(
            x=df_acum['Data'],
            y=df_acum['Etanol Total (m³)'],
            name='<b>Etanol Quinzenal</b>',
            marker_color=CORES['Quinzenal'],
            opacity=0.6,
            hovertemplate='<b>Etanol Quinzenal</b><br>Data: %{x}<br>Produção: %{y:,.0f} m³<extra></extra>',
            showlegend=False
        ),
        row=1, col=2, secondary_y=True
    )

    fig.update_layout(
        height=550,
        hovermode='x unified',
        template='plotly_dark',
        font=dict(family="Arial", size=11),
        showlegend=False,
        margin=dict(t=80, b=100, l=60, r=60)
    )

    fig.update_xaxes(title="<b>Data</b>", row=1, col=1, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title="<b>Data</b>", row=1, col=2, title_font=dict(size=12), tickangle=-45, nticks=8)
    fig.update_yaxes(title="<b>Acumulado (t)</b>", row=1, col=1, secondary_y=False, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Quinzenal (t)</b>", row=1, col=1, secondary_y=True, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Acumulado (m³)</b>", row=1, col=2, secondary_y=False, title_font=dict(size=11))
    fig.update_yaxes(title="<b>Quinzenal (m³)</b>", row=1, col=2, secondary_y=True, title_font=dict(size=11))

    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 Este gráfico mostra a produção acumulada e quinzenal de açúcar e etanol.")

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
    
    💡 *Os dados são compartilhados com a página de Acompanhamento de Safra através do session_state.*
    """
)

