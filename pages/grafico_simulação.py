"""
================================================================================
GRÁFICOS DE SIMULAÇÃO - VISUALIZAÇÕES PROFISSIONAIS
================================================================================
Este módulo gera gráficos profissionais baseados nas simulações do arquivo
analise_safra.py, permitindo visualizar de forma clara e intuitiva:
- Evolução de preços (NY11, Etanol, USD/BRL)
- Evolução de produção (Açúcar, Etanol)
- Parâmetros de safra (Moagem, ATR, MIX)
- Comparações de cenários
- Análises de correlação

================================================================================
"""

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import date
from Dados_base import PERFIL_ATR, PERFIL_MIX

# Importa funções do analise_safra.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

# Tenta importar do analise_safra, mas se não conseguir, define funções básicas
try:
    from analise_safra import (
        gerar_simulacao_quinzenal,
        simular_precos,
        calcular_producao_quinzenal,
        calcular_producao_total_quinzenal,
        ny11_para_brl,
        fmt_br
    )
except ImportError:
    st.error("⚠️ Erro ao importar funções de analise_safra.py. Certifique-se de que o arquivo existe.")
    st.stop()


# ============================================================================
# CONFIGURAÇÃO STREAMLIT
# ============================================================================

st.set_page_config(page_title="Gráficos de Simulação", layout="wide")

st.markdown("<h1 style='text-align: center; margin-bottom: 5px;'>Gráficos de Simulação 📊</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="text-align: center; color: #666; font-size: 0.9em; margin-top: 0px; margin-bottom: 20px;">Desenvolvido por Rogério Guilherme Jr.</p>',
    unsafe_allow_html=True
)

# ============================================================================
# ESQUEMA DE CORES CONSISTENTE
# ============================================================================

CORES = {
    'NY11': '#1f77b4',           # Azul
    'USD_BRL': '#ff7f0e',        # Laranja
    'Etanol': '#2ca02c',         # Verde
    'Açúcar': '#d62728',         # Vermelho
    'Moagem': '#1f77b4',         # Azul
    'ATR': '#ff7f0e',            # Laranja
    'MIX': '#2ca02c',            # Verde
    'Etanol_Prod': '#9467bd',    # Roxo
    'Açúcar_Prod': '#d62728',    # Vermelho
    'Acumulado': '#8c564b',      # Marrom
    'Quinzenal': '#e377c2',      # Rosa
}

# ============================================================================
# FUNÇÕES DE GERAÇÃO DE GRÁFICOS
# ============================================================================

def criar_grafico_precos(df, ny11_inicial, usd_inicial, etanol_inicial):
    """
    Cria gráfico de evolução de preços com eixos duplos.

    Args:
        df: DataFrame com dados de preços
        ny11_inicial: Preço inicial do NY11
        usd_inicial: Taxa de câmbio inicial
        etanol_inicial: Preço inicial do etanol
    """
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            '<b>Evolução de Preços - NY11 e USD/BRL</b>',
            '<b>Evolução de Preços - Etanol</b>'
        ),
        vertical_spacing=0.25,  # Aumentado para evitar sobreposição de legendas
        row_heights=[0.5, 0.5],
        specs=[[{"secondary_y": True}], [{}]]
    )

    # ========== GRÁFICO 1: NY11 e USD/BRL ==========
    fig.add_trace(
        go.Scatter(
            x=df['Data'],
            y=df['NY11_cents'],
            name='<b>NY11</b>',
            line=dict(color=CORES['NY11'], width=3),
            mode='lines+markers',
            marker=dict(size=6, symbol='circle'),
            hovertemplate='<b>NY11</b><br>Data: %{x}<br>Preço: %{y:.2f} USc/lb<extra></extra>',
            showlegend=True,
            legendgroup='precos1'
        ),
        row=1, col=1, secondary_y=False
    )

    fig.add_trace(
        go.Scatter(
            x=df['Data'],
            y=df['USD_BRL'],
            name='<b>USD/BRL</b>',
            line=dict(color=CORES['USD_BRL'], width=3),
            mode='lines+markers',
            marker=dict(size=6, symbol='square'),
            hovertemplate='<b>USD/BRL</b><br>Data: %{x}<br>Câmbio: %{y:.2f}<extra></extra>',
            showlegend=True,
            legendgroup='precos1'
        ),
        row=1, col=1, secondary_y=True
    )

    # Linhas de referência
    fig.add_hline(
        y=ny11_inicial,
        line_dash="dash",
        line_color=CORES['NY11'],
        opacity=0.4,
        line_width=2,
        annotation_text=f"<b>Inicial: {ny11_inicial:.2f}</b>",
        annotation_position="right",
        row=1, col=1
    )

    fig.add_hline(
        y=usd_inicial,
        line_dash="dash",
        line_color=CORES['USD_BRL'],
        opacity=0.4,
        line_width=2,
        annotation_text=f"<b>Inicial: {usd_inicial:.2f}</b>",
        annotation_position="left",
        row=1, col=1
    )

    # ========== GRÁFICO 2: Etanol ==========
    fig.add_trace(
        go.Scatter(
            x=df['Data'],
            y=df['Etanol_R$m3'],
            name='<b>Etanol</b>',
            line=dict(color=CORES['Etanol'], width=3),
            mode='lines+markers',
            marker=dict(size=6, symbol='diamond'),
            fill='tozeroy',
            fillcolor="rgba(44, 160, 44, 0.15)",
            hovertemplate='<b>Etanol</b><br>Data: %{x}<br>Preço: R$ %{y:,.0f}/m³<extra></extra>',
            showlegend=True,
            legendgroup='etanol'
        ),
        row=2, col=1
    )

    fig.add_hline(
        y=etanol_inicial,
        line_dash="dash",
        line_color=CORES['Etanol'],
        opacity=0.4,
        line_width=2,
        annotation_text=f"<b>Inicial: R$ {etanol_inicial:,.0f}</b>",
        annotation_position="right",
        row=2, col=1
    )

    # ========== CONFIGURAÇÃO DE LAYOUT ==========
    fig.update_layout(
        height=800,
        hovermode='x unified',
        template='plotly_white',
        font=dict(family="Arial", size=11),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            font=dict(size=11),
            bgcolor='rgba(255,255,255,0.0)',
            bordercolor='rgba(0,0,0,0)',
            borderwidth=0,
            itemwidth=30
        ),
        margin=dict(t=120, b=100, l=60, r=60)
    )

    # Configuração de eixos X e Y
    fig.update_xaxes(title_text="<b>Data</b>", row=1, col=1, titlefont=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title_text="<b>Data</b>", row=2, col=1, titlefont=dict(size=12), tickangle=-45, nticks=8)

    # Configuração dos eixos Y (usando update_yaxes para subplots com secondary_y)
    fig.update_yaxes(title_text="<b>NY11 (USc/lb)</b>", row=1, col=1, secondary_y=False, titlefont=dict(size=12))
    fig.update_yaxes(title_text="<b>USD/BRL</b>", row=1, col=1, secondary_y=True, titlefont=dict(size=12))
    fig.update_yaxes(title_text="<b>Etanol (R$/m³)</b>", row=2, col=1, titlefont=dict(size=12))

    return fig


def criar_grafico_producao(df):
    """
    Cria gráfico de evolução de produção quinzenal (Açúcar e Etanol).

    Args:
        df: DataFrame com dados de produção
    """
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            '<b>Produção Quinzenal de Açúcar</b>',
            '<b>Produção Quinzenal de Etanol</b>'
        ),
        vertical_spacing=0.18,
        row_heights=[0.5, 0.5]
    )

    # ========== GRÁFICO 1: Açúcar ==========
    media_acucar = df['Açúcar (t)'].mean()

    fig.add_trace(
        go.Bar(
            x=df['Data'],
            y=df['Açúcar (t)'],
            name='<b>Açúcar</b>',
            marker_color=CORES['Açúcar'],
            opacity=0.85,
            hovertemplate='<b>Açúcar</b><br>Data: %{x}<br>Produção: %{y:,.0f} t<extra></extra>'
        ),
        row=1, col=1
    )

    fig.add_hline(
        y=media_acucar,
        line_dash="dash",
        line_color=CORES['Açúcar'],
        opacity=0.6,
        line_width=2.5,
        annotation_text=f"<b>Média: {fmt_br(media_acucar, 0)} t</b>",
        annotation_position="right",
        row=1, col=1
    )

    # ========== GRÁFICO 2: Etanol ==========
    media_etanol = df['Etanol (m³)'].mean()

    fig.add_trace(
        go.Bar(
            x=df['Data'],
            y=df['Etanol (m³)'],
            name='<b>Etanol</b>',
            marker_color=CORES['Etanol_Prod'],
            opacity=0.85,
            hovertemplate='<b>Etanol</b><br>Data: %{x}<br>Produção: %{y:,.0f} m³<extra></extra>'
        ),
        row=2, col=1
    )

    fig.add_hline(
        y=media_etanol,
        line_dash="dash",
        line_color=CORES['Etanol_Prod'],
        opacity=0.6,
        line_width=2.5,
        annotation_text=f"<b>Média: {fmt_br(media_etanol, 0)} m³</b>",
        annotation_position="right",
        row=2, col=1
    )

    # ========== CONFIGURAÇÃO DE LAYOUT ==========
    fig.update_layout(
        height=750,
        hovermode='x unified',
        template='plotly_white',
        font=dict(family="Arial", size=11),
        showlegend=False,
        margin=dict(t=80, b=100, l=60, r=60)
    )

    fig.update_xaxes(title_text="<b>Data</b>", row=1, col=1, titlefont=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title_text="<b>Data</b>", row=2, col=1, titlefont=dict(size=12), tickangle=-45, nticks=8)
    fig.update_yaxes(title_text="<b>Açúcar (t)</b>", row=1, col=1, titlefont=dict(size=12))
    fig.update_yaxes(title_text="<b>Etanol (m³)</b>", row=2, col=1, titlefont=dict(size=12))

    return fig


def criar_grafico_parametros_safra(df):
    """
    Cria gráfico de evolução dos parâmetros de safra (Moagem, ATR, MIX).

    Args:
        df: DataFrame com dados de safra
    """
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

    # ========== MOAGEM ==========
    fig.add_trace(
        go.Scatter(
            x=df['Data'],
            y=df['Moagem'],
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

    # ========== ATR ==========
    fig.add_trace(
        go.Scatter(
            x=df['Data'],
            y=df['ATR'],
            name='<b>ATR</b>',
            line=dict(color=CORES['ATR'], width=3),
            mode='lines+markers',
            marker=dict(size=6, symbol='square'),
            hovertemplate='<b>ATR</b><br>Data: %{x}<br>ATR: %{y:.2f} kg/t<extra></extra>'
        ),
        row=2, col=1
    )

    # ========== MIX ==========
    fig.add_trace(
        go.Scatter(
            x=df['Data'],
            y=df['MIX'],
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

    # ========== CONFIGURAÇÃO DE LAYOUT ==========
    fig.update_layout(
        height=850,
        hovermode='x unified',
        template='plotly_white',
        font=dict(family="Arial", size=11),
        showlegend=False,
        margin=dict(t=80, b=100, l=60, r=60)
    )

    fig.update_xaxes(title_text="<b>Data</b>", row=1, col=1, titlefont=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title_text="<b>Data</b>", row=2, col=1, titlefont=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title_text="<b>Data</b>", row=3, col=1, titlefont=dict(size=12), tickangle=-45, nticks=8)
    fig.update_yaxes(title_text="<b>Moagem (ton)</b>", row=1, col=1, titlefont=dict(size=12))
    fig.update_yaxes(title_text="<b>ATR (kg/t)</b>", row=2, col=1, titlefont=dict(size=12))
    fig.update_yaxes(title_text="<b>MIX (%)</b>", row=3, col=1, titlefont=dict(size=12))

    return fig


def criar_grafico_correlacao_precos_producao(df):
    """Cria gráfico de correlação entre preços e produção"""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            '<b>NY11 vs Produção de Açúcar</b>',
            '<b>Etanol vs Produção de Etanol</b>',
            '<b>USD/BRL vs Produção de Açúcar</b>',
            '<b>Correlação NY11 vs Etanol</b>'
        ),
        specs=[[{"secondary_y": True}, {"secondary_y": True}],
               [{"secondary_y": True}, {"type": "scatter"}]],
        vertical_spacing=0.15,
        horizontal_spacing=0.12
    )

    # NY11 vs Açúcar
    fig.add_trace(
        go.Scatter(
            x=df['Açúcar (t)'],
            y=df['NY11_cents'],
            mode='markers',
            name='<b>NY11</b>',
            marker=dict(color=CORES['NY11'], size=10, opacity=0.7, line=dict(width=1, color='white')),
            hovertemplate='<b>NY11 vs Açúcar</b><br>Açúcar: %{x:,.0f} t<br>NY11: %{y:.2f} USc/lb<extra></extra>'
        ),
        row=1, col=1, secondary_y=False
    )
    fig.update_yaxes(title_text="<b>NY11 (USc/lb)</b>", row=1, col=1, secondary_y=False, titlefont=dict(size=11))
    fig.update_xaxes(title_text="<b>Açúcar (t)</b>", row=1, col=1, titlefont=dict(size=11))

    # Etanol vs Produção Etanol
    fig.add_trace(
        go.Scatter(
            x=df['Etanol (m³)'],
            y=df['Etanol_R$m3'],
            mode='markers',
            name='<b>Etanol</b>',
            marker=dict(color=CORES['Etanol'], size=10, opacity=0.7, line=dict(width=1, color='white')),
            hovertemplate='<b>Etanol Preço vs Produção</b><br>Produção: %{x:,.0f} m³<br>Preço: R$ %{y:,.0f}/m³<extra></extra>'
        ),
        row=1, col=2, secondary_y=False
    )
    fig.update_yaxes(title_text="<b>Etanol (R$/m³)</b>", row=1, col=2, secondary_y=False, titlefont=dict(size=11))
    fig.update_xaxes(title_text="<b>Etanol Produzido (m³)</b>", row=1, col=2, titlefont=dict(size=11))

    # USD vs Açúcar
    fig.add_trace(
        go.Scatter(
            x=df['Açúcar (t)'],
            y=df['USD_BRL'],
            mode='markers',
            name='<b>USD/BRL</b>',
            marker=dict(color=CORES['USD_BRL'], size=10, opacity=0.7, line=dict(width=1, color='white')),
            hovertemplate='<b>USD/BRL vs Açúcar</b><br>Açúcar: %{x:,.0f} t<br>USD/BRL: %{y:.2f}<extra></extra>'
        ),
        row=2, col=1, secondary_y=False
    )
    fig.update_yaxes(title_text="<b>USD/BRL</b>", row=2, col=1, secondary_y=False, titlefont=dict(size=11))
    fig.update_xaxes(title_text="<b>Açúcar (t)</b>", row=2, col=1, titlefont=dict(size=11))

    # Correlação entre preços
    fig.add_trace(
        go.Scatter(
            x=df['NY11_cents'],
            y=df['Etanol_R$m3'],
            mode='markers',
            name='<b>NY11 vs Etanol</b>',
            marker=dict(color=CORES['Etanol_Prod'], size=10, opacity=0.7, line=dict(width=1, color='white')),
            hovertemplate='<b>NY11 vs Etanol</b><br>NY11: %{x:.2f} USc/lb<br>Etanol: R$ %{y:,.0f}/m³<extra></extra>'
        ),
        row=2, col=2
    )
    fig.update_xaxes(title_text="<b>NY11 (USc/lb)</b>", row=2, col=2, titlefont=dict(size=11))
    fig.update_yaxes(title_text="<b>Etanol (R$/m³)</b>", row=2, col=2, titlefont=dict(size=11))

    fig.update_layout(
        height=750,
        template='plotly_white',
        font=dict(family="Arial", size=11),
        showlegend=False,
        margin=dict(t=80, b=80, l=60, r=60)
    )

    # Rotaciona labels do eixo X para evitar sobreposição
    fig.update_xaxes(tickangle=-45, row=1, col=1)
    fig.update_xaxes(tickangle=-45, row=1, col=2)
    fig.update_xaxes(tickangle=-45, row=2, col=1)
    fig.update_xaxes(tickangle=-45, row=2, col=2)

    return fig


def criar_grafico_acumulado(df):
    """Cria gráfico de produção acumulada"""
    df_acum = df.copy()
    df_acum['Açúcar Acumulado (t)'] = df_acum['Açúcar (t)'].cumsum()
    df_acum['Etanol Acumulado (m³)'] = df_acum['Etanol (m³)'].cumsum()

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            '<b>Produção Acumulada de Açúcar</b>',
            '<b>Produção Acumulada de Etanol</b>'
        ),
        specs=[[{"secondary_y": True}, {"secondary_y": True}]],
        horizontal_spacing=0.12
    )

    # Açúcar acumulado
    fig.add_trace(
        go.Scatter(
            x=df_acum['Data'],
            y=df_acum['Açúcar Acumulado (t)'],
            name='<b>Açúcar Acumulado</b>',
            line=dict(color=CORES['Açúcar'], width=3.5),
            mode='lines',
            fill='tozeroy',
            fillcolor=f"rgba(214, 39, 40, 0.2)",
            hovertemplate='<b>Açúcar Acumulado</b><br>Data: %{x}<br>Total: %{y:,.0f} t<extra></extra>'
        ),
        row=1, col=1
    )

    # Açúcar quinzenal (barras)
    fig.add_trace(
        go.Bar(
            x=df_acum['Data'],
            y=df_acum['Açúcar (t)'],
            name='<b>Açúcar Quinzenal</b>',
            marker_color=CORES['Quinzenal'],
            opacity=0.6,
            hovertemplate='<b>Açúcar Quinzenal</b><br>Data: %{x}<br>Produção: %{y:,.0f} t<extra></extra>'
        ),
        row=1, col=1, secondary_y=True
    )

    # Etanol acumulado
    fig.add_trace(
        go.Scatter(
            x=df_acum['Data'],
            y=df_acum['Etanol Acumulado (m³)'],
            name='<b>Etanol Acumulado</b>',
            line=dict(color=CORES['Etanol_Prod'], width=3.5),
            mode='lines',
            fill='tozeroy',
            fillcolor=f"rgba(148, 103, 189, 0.2)",
            hovertemplate='<b>Etanol Acumulado</b><br>Data: %{x}<br>Total: %{y:,.0f} m³<extra></extra>'
        ),
        row=1, col=2
    )

    # Etanol quinzenal (barras)
    fig.add_trace(
        go.Bar(
            x=df_acum['Data'],
            y=df_acum['Etanol (m³)'],
            name='<b>Etanol Quinzenal</b>',
            marker_color=CORES['Quinzenal'],
            opacity=0.6,
            hovertemplate='<b>Etanol Quinzenal</b><br>Data: %{x}<br>Produção: %{y:,.0f} m³<extra></extra>'
        ),
        row=1, col=2, secondary_y=True
    )

    fig.update_layout(
        height=550,
        hovermode='x unified',
        template='plotly_white',
        font=dict(family="Arial", size=11),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=12),
            bgcolor='rgba(255,255,255,0.0)',
            bordercolor='rgba(0,0,0,0)',
            borderwidth=0
        ),
        margin=dict(t=100, b=100, l=60, r=60)
    )

    fig.update_xaxes(title_text="<b>Data</b>", row=1, col=1, titlefont=dict(size=12), tickangle=-45, nticks=8)
    fig.update_xaxes(title_text="<b>Data</b>", row=1, col=2, titlefont=dict(size=12), tickangle=-45, nticks=8)
    fig.update_yaxes(title_text="<b>Acumulado (t)</b>", row=1, col=1, secondary_y=False, titlefont=dict(size=11))
    fig.update_yaxes(title_text="<b>Quinzenal (t)</b>", row=1, col=1, secondary_y=True, titlefont=dict(size=11))
    fig.update_yaxes(title_text="<b>Acumulado (m³)</b>", row=1, col=2, secondary_y=False, titlefont=dict(size=11))
    fig.update_yaxes(title_text="<b>Quinzenal (m³)</b>", row=1, col=2, secondary_y=True, titlefont=dict(size=11))

    return fig


def criar_grafico_heatmap_correlacao(df):
    """Cria heatmap de correlação entre variáveis"""
    # Seleciona variáveis numéricas
    vars_corr = ['Moagem', 'ATR', 'MIX', 'Açúcar (t)', 'Etanol (m³)',
                 'NY11_cents', 'Etanol_R$m3', 'USD_BRL']

    df_corr = df[vars_corr].corr()

    # Labels mais amigáveis
    labels = {
        'Moagem': '<b>Moagem</b>',
        'ATR': '<b>ATR</b>',
        'MIX': '<b>MIX</b>',
        'Açúcar (t)': '<b>Açúcar</b>',
        'Etanol (m³)': '<b>Etanol Prod</b>',
        'NY11_cents': '<b>NY11</b>',
        'Etanol_R$m3': '<b>Etanol Preço</b>',
        'USD_BRL': '<b>USD/BRL</b>'
    }

    x_labels = [labels.get(col, col) for col in df_corr.columns]
    y_labels = [labels.get(col, col) for col in df_corr.columns]

    # Cria matriz de texto com cores baseadas no valor
    # Para valores próximos de 0 (cores claras no heatmap), usa texto preto
    # Para valores próximos de -1 ou 1 (cores escuras), usa texto branco
    text_matrix = []
    text_colors = []
    for row in df_corr.values:
        text_row = []
        color_row = []
        for val in row:
            text_row.append(f'{val:.2f}')
            # Determina cor do texto baseado no valor absoluto
            # Valores próximos de 0 (cores claras) = texto preto
            # Valores próximos de -1 ou 1 (cores escuras) = texto branco
            if abs(val) < 0.3:  # Cor clara no heatmap (próximo de 0)
                color_row.append('black')
            else:  # Cor escura no heatmap (próximo de -1 ou 1)
                color_row.append('white')
        text_matrix.append(text_row)
        text_colors.append(color_row)

    # Cria heatmap com texto
    fig = go.Figure(data=go.Heatmap(
        z=df_corr.values,
        x=x_labels,
        y=y_labels,
        colorscale='RdBu',
        zmid=0,
        zmin=-1,
        zmax=1,
        text=text_matrix,
        texttemplate='%{text}',
        textfont=dict(size=12, family="Arial"),
        showscale=True,
        colorbar=dict(title="<b>Correlação</b>", titlefont=dict(size=12)),
        hovertemplate='<b>%{y} vs %{x}</b><br>Correlação: %{z:.2f}<extra></extra>'
    ))

    # Atualiza as cores do texto dinamicamente usando annotations
    # Plotly não permite cores diferentes por célula no textfont, então usamos annotations
    annotations = []
    for i, row in enumerate(df_corr.values):
        for j, val in enumerate(row):
            # Determina cor do texto baseado no valor absoluto
            if abs(val) < 0.3:  # Cor clara no heatmap (próximo de 0)
                text_color = 'black'
            else:  # Cor escura no heatmap (próximo de -1 ou 1)
                text_color = 'white'

            annotations.append(
                dict(
                    x=j, y=i,
                    text=f'<b>{val:.2f}</b>',
                    showarrow=False,
                    font=dict(color=text_color, size=13, family="Arial", weight="bold"),
                    xref='x', yref='y',
                    xanchor='center',
                    yanchor='middle'
                )
            )

    fig.update_layout(
        title=dict(text='<b>Matriz de Correlação entre Variáveis</b>', font=dict(size=16)),
        height=650,
        template='plotly_white',
        font=dict(family="Arial", size=11),
        margin=dict(t=80, b=60, l=100, r=60),
        annotations=annotations
    )

    # Remove o texto do heatmap para evitar duplicação (usamos apenas annotations)
    fig.update_traces(texttemplate='', textfont=None)

    return fig


def criar_grafico_distribuicao_producao(df):
    """Cria gráfico de distribuição da produção"""
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            '<b>Distribuição de Açúcar</b>',
            '<b>Distribuição de Etanol</b>'
        ),
        specs=[[{"type": "histogram"}, {"type": "histogram"}]],
        horizontal_spacing=0.12
    )

    # Histograma Açúcar
    fig.add_trace(
        go.Histogram(
            x=df['Açúcar (t)'],
            name='<b>Açúcar</b>',
            marker_color=CORES['Açúcar'],
            opacity=0.8,
            nbinsx=20,
            hovertemplate='<b>Açúcar</b><br>Intervalo: %{x}<br>Frequência: %{y}<extra></extra>'
        ),
        row=1, col=1
    )

    # Linha de média para açúcar
    media_acucar = df['Açúcar (t)'].mean()
    fig.add_vline(
        x=media_acucar,
        line_dash="dash",
        line_color=CORES['Açúcar'],
        opacity=0.7,
        line_width=2,
        annotation_text=f"<b>Média: {fmt_br(media_acucar, 0)}</b>",
        row=1, col=1
    )

    # Histograma Etanol
    fig.add_trace(
        go.Histogram(
            x=df['Etanol (m³)'],
            name='<b>Etanol</b>',
            marker_color=CORES['Etanol_Prod'],
            opacity=0.8,
            nbinsx=20,
            hovertemplate='<b>Etanol</b><br>Intervalo: %{x}<br>Frequência: %{y}<extra></extra>'
        ),
        row=1, col=2
    )

    # Linha de média para etanol
    media_etanol = df['Etanol (m³)'].mean()
    fig.add_vline(
        x=media_etanol,
        line_dash="dash",
        line_color=CORES['Etanol_Prod'],
        opacity=0.7,
        line_width=2,
        annotation_text=f"<b>Média: {fmt_br(media_etanol, 0)}</b>",
        row=1, col=2
    )

    fig.update_layout(
        height=450,
        template='plotly_white',
        font=dict(family="Arial", size=11),
        showlegend=False,
        margin=dict(t=80, b=80, l=60, r=60)
    )

    fig.update_xaxes(title_text="<b>Açúcar (t)</b>", row=1, col=1, titlefont=dict(size=12))
    fig.update_xaxes(title_text="<b>Etanol (m³)</b>", row=1, col=2, titlefont=dict(size=12))
    fig.update_yaxes(title_text="<b>Frequência</b>", row=1, col=1, titlefont=dict(size=12))
    fig.update_yaxes(title_text="<b>Frequência</b>", row=1, col=2, titlefont=dict(size=12))

    return fig


def criar_grafico_correlacao_dolar(df):
    """Cria gráfico de correlação do dólar com outras variáveis"""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            '<b>USD/BRL vs NY11</b>',
            '<b>USD/BRL vs Etanol Preço</b>',
            '<b>USD/BRL vs Açúcar</b>',
            '<b>USD/BRL vs Etanol Produção</b>'
        ),
        specs=[[{"type": "scatter"}, {"type": "scatter"}],
               [{"type": "scatter"}, {"type": "scatter"}]],
        vertical_spacing=0.15,
        horizontal_spacing=0.12
    )

    # USD vs NY11
    fig.add_trace(
        go.Scatter(
            x=df['USD_BRL'],
            y=df['NY11_cents'],
            mode='markers',
            name='<b>NY11</b>',
            marker=dict(color=CORES['NY11'], size=10, opacity=0.7, line=dict(width=1, color='white')),
            hovertemplate='<b>USD/BRL vs NY11</b><br>USD/BRL: %{x:.2f}<br>NY11: %{y:.2f} USc/lb<extra></extra>'
        ),
        row=1, col=1
    )
    fig.update_xaxes(title_text="<b>USD/BRL</b>", row=1, col=1, titlefont=dict(size=11))
    fig.update_yaxes(title_text="<b>NY11 (USc/lb)</b>", row=1, col=1, titlefont=dict(size=11))

    # USD vs Etanol Preço
    fig.add_trace(
        go.Scatter(
            x=df['USD_BRL'],
            y=df['Etanol_R$m3'],
            mode='markers',
            name='<b>Etanol</b>',
            marker=dict(color=CORES['Etanol'], size=10, opacity=0.7, line=dict(width=1, color='white')),
            hovertemplate='<b>USD/BRL vs Etanol</b><br>USD/BRL: %{x:.2f}<br>Etanol: R$ %{y:,.0f}/m³<extra></extra>'
        ),
        row=1, col=2
    )
    fig.update_xaxes(title_text="<b>USD/BRL</b>", row=1, col=2, titlefont=dict(size=11))
    fig.update_yaxes(title_text="<b>Etanol (R$/m³)</b>", row=1, col=2, titlefont=dict(size=11))

    # USD vs Açúcar
    fig.add_trace(
        go.Scatter(
            x=df['USD_BRL'],
            y=df['Açúcar (t)'],
            mode='markers',
            name='<b>Açúcar</b>',
            marker=dict(color=CORES['Açúcar'], size=10, opacity=0.7, line=dict(width=1, color='white')),
            hovertemplate='<b>USD/BRL vs Açúcar</b><br>USD/BRL: %{x:.2f}<br>Açúcar: %{y:,.0f} t<extra></extra>'
        ),
        row=2, col=1
    )
    fig.update_xaxes(title_text="<b>USD/BRL</b>", row=2, col=1, titlefont=dict(size=11))
    fig.update_yaxes(title_text="<b>Açúcar (t)</b>", row=2, col=1, titlefont=dict(size=11))

    # USD vs Etanol Produção
    fig.add_trace(
        go.Scatter(
            x=df['USD_BRL'],
            y=df['Etanol (m³)'],
            mode='markers',
            name='<b>Etanol Prod</b>',
            marker=dict(color=CORES['Etanol_Prod'], size=10, opacity=0.7, line=dict(width=1, color='white')),
            hovertemplate='<b>USD/BRL vs Etanol Produção</b><br>USD/BRL: %{x:.2f}<br>Etanol: %{y:,.0f} m³<extra></extra>'
        ),
        row=2, col=2
    )
    fig.update_xaxes(title_text="<b>USD/BRL</b>", row=2, col=2, titlefont=dict(size=11))
    fig.update_yaxes(title_text="<b>Etanol (m³)</b>", row=2, col=2, titlefont=dict(size=11))

    fig.update_layout(
        height=750,
        template='plotly_white',
        font=dict(family="Arial", size=11),
        showlegend=False,
        margin=dict(t=80, b=80, l=60, r=60)
    )

    return fig


# ============================================================================
# INTERFACE
# ============================================================================

# Sidebar com parâmetros (mesmos do analise_safra.py)
st.sidebar.header("📊 Parâmetros da Simulação")

moagem = st.sidebar.number_input("Moagem total (ton)", value=600_000_000, step=10_000_000)
atr = st.sidebar.number_input("ATR médio (kg/t)", value=135.0, step=1.0, format="%.1f")
mix = st.sidebar.number_input("Mix açúcar (%)", value=48.0, step=1.0, format="%.1f")

st.sidebar.divider()

st.sidebar.subheader("💰 Preços Iniciais")
ny11_inicial = st.sidebar.number_input("NY11 inicial (USc/lb)", value=14.90, step=0.10, format="%.2f")
usd_inicial = st.sidebar.number_input("USD/BRL inicial", value=4.90, step=0.01, format="%.2f")
etanol_inicial = st.sidebar.number_input("Etanol inicial (R$/m³)", value=2500.0, step=50.0, format="%.0f")

st.sidebar.divider()

st.sidebar.subheader("⚙️ Simulação")
n_quinz = st.sidebar.number_input("Nº de quinzenas", value=24, min_value=4, max_value=24, step=1)
data_start = st.sidebar.date_input("Início da safra", value=date(date.today().year, 4, 1))

with st.sidebar.expander("🔧 Parâmetros Avançados", expanded=False):
    preco_ref = st.number_input("Preço referência NY11 (USc/lb)", value=15.0, step=0.5, format="%.1f")
    sensibilidade = st.slider("Sensibilidade oferta → preço (%)", 0.0, 30.0, 10.0, 1.0)
    usar_paridade = st.checkbox("Usar paridade etanol/açúcar", value=False)

# Inicializa session state
if 'choques_safra' not in st.session_state:
    st.session_state.choques_safra = {}
if 'choques' not in st.session_state:
    st.session_state.choques = {}

# ============ CÁLCULOS ============
choques_safra = st.session_state.get('choques_safra', {})
df_base = gerar_simulacao_quinzenal(moagem, atr, mix, int(n_quinz), data_start,
                                    choques_safra if choques_safra else None)

choques_precos = st.session_state.get('choques', {})
df_precos, direcao, fator_oferta, choques_aplicados, mix_ajustado = simular_precos(
    ny11_inicial, usd_inicial, etanol_inicial, int(n_quinz),
    df_base, preco_ref, sensibilidade / 100,
    choques_precos if choques_precos else None, usar_paridade
)

df_completo = df_base.merge(df_precos, on="Quinzena")

# Calcula produção quinzenal
producao_acucar_quinzenal = []
producao_etanol_quinzenal = []

for i, row in df_completo.iterrows():
    if usar_paridade and mix_ajustado and i < len(mix_ajustado):
        mix_quinzena = mix_ajustado[i]
    else:
        mix_quinzena = row["MIX"]

    acucar_q, etanol_q = calcular_producao_quinzenal(row["Moagem"], row["ATR"], mix_quinzena)
    producao_acucar_quinzenal.append(acucar_q)
    producao_etanol_quinzenal.append(etanol_q)

df_completo["Açúcar (t)"] = producao_acucar_quinzenal
df_completo["Etanol (m³)"] = producao_etanol_quinzenal

# ============ EXIBIÇÃO DE GRÁFICOS ============

st.divider()

# Seletor de gráficos
tipo_grafico = st.selectbox(
    "📊 Selecione o tipo de gráfico:",
    [
        "Evolução de Preços",
        "Evolução de Produção",
        "Parâmetros de Safra",
        "Correlação Preços vs Produção",
        "Correlação USD/BRL",
        "Produção Acumulada",
        "Matriz de Correlação",
        "Distribuição de Produção"
    ],
    key="tipo_grafico"
)

st.divider()

if tipo_grafico == "Evolução de Preços":
    st.subheader("📈 Evolução de Preços ao Longo da Safra")
    fig = criar_grafico_precos(df_completo, ny11_inicial, usd_inicial, etanol_inicial)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("💡 Este gráfico mostra a evolução dos preços simulados (NY11, USD/BRL e Etanol) ao longo das quinzenas da safra.")

elif tipo_grafico == "Evolução de Produção":
    st.subheader("🌾 Evolução de Produção Quinzenal")
    fig = criar_grafico_producao(df_completo)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("💡 Este gráfico mostra a produção quinzenal de açúcar e etanol, com linhas de média para referência.")

elif tipo_grafico == "Parâmetros de Safra":
    st.subheader("📊 Evolução dos Parâmetros de Safra")
    fig = criar_grafico_parametros_safra(df_completo)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("💡 Este gráfico mostra a evolução dos principais parâmetros de safra: Moagem, ATR e MIX.")

elif tipo_grafico == "Correlação Preços vs Produção":
    st.subheader("🔗 Correlação entre Preços e Produção")
    fig = criar_grafico_correlacao_precos_producao(df_completo)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("💡 Este gráfico mostra a relação entre preços e produção, ajudando a identificar padrões e correlações.")

elif tipo_grafico == "Correlação USD/BRL":
    st.subheader("💲 Correlação do Dólar (USD/BRL) com Outras Variáveis")
    fig = criar_grafico_correlacao_dolar(df_completo)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("💡 Este gráfico mostra como o dólar se relaciona com NY11, Etanol, Açúcar e Produção de Etanol.")

elif tipo_grafico == "Produção Acumulada":
    st.subheader("📦 Produção Acumulada")
    fig = criar_grafico_acumulado(df_completo)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("💡 Este gráfico mostra a produção acumulada ao longo da safra, com sobreposição da produção quinzenal.")

elif tipo_grafico == "Matriz de Correlação":
    st.subheader("🔍 Matriz de Correlação entre Variáveis")
    fig = criar_grafico_heatmap_correlacao(df_completo)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("💡 Este heatmap mostra as correlações entre todas as variáveis da simulação. Valores próximos de 1 indicam forte correlação positiva, próximos de -1 indicam correlação negativa.")

elif tipo_grafico == "Distribuição de Produção":
    st.subheader("📊 Distribuição de Produção")
    fig = criar_grafico_distribuicao_producao(df_completo)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("💡 Este gráfico mostra a distribuição (histograma) da produção quinzenal de açúcar e etanol.")

# Resumo estatístico
st.divider()
st.subheader("📋 Resumo Estatístico")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Açúcar Total", fmt_br(df_completo["Açúcar (t)"].sum(), 0) + " t")
col2.metric("Etanol Total", fmt_br(df_completo["Etanol (m³)"].sum(), 0) + " m³")
col3.metric("NY11 Final", f"{df_completo['NY11_cents'].iloc[-1]:.2f} USc/lb")
col4.metric("USD/BRL Final", f"{df_completo['USD_BRL'].iloc[-1]:.2f}")

