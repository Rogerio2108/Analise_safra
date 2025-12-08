"""
================================================================================
ACOMPANHAMENTO DE SAFRA - SIMULAÇÃO COM DADOS REAIS
================================================================================
Este módulo permite acompanhar a safra inserindo dados reais acumulados da Unica
e ajustando projeções baseadas no perfil histórico da safra.

Funcionalidades:
- Inserção de dados reais acumulados por quinzena
- Projeção automática baseada em perfis históricos
- Simulação de choques apenas em quinzenas futuras
- Cálculo automático de etanol (hidratado/anidro de cana e milho)
- Ajuste automático de projeções conforme dados reais são inseridos

================================================================================
"""

import pandas as pd
import streamlit as st
from pathlib import Path
import numpy as np
from datetime import date, datetime, timedelta
import json
import re

# Imports opcionais para busca de preços
try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    # Não mostra warning aqui para evitar erro durante o import
    # O warning será mostrado apenas quando o usuário tentar usar a funcionalidade
try:
    from Dados_base import (
        DATA_FILES,
        DESCONTO_VHP_FOB,
        TAXA_POL,
        ICMS_ETANOL,
        PIS_COFINS_ETANOL,
        FRETE_R_T,
        TERMINAL_USD_T,
        PERFIL_ATR,
        PERFIL_MIX,
        PERFIL_MOAGEM_PCT
    )
except ImportError:
    # Tenta importar do diretório pai (para Streamlit Cloud)
    import sys
    from pathlib import Path
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from Dados_base import (
        DATA_FILES,
        DESCONTO_VHP_FOB,
        TAXA_POL,
        ICMS_ETANOL,
        PIS_COFINS_ETANOL,
        FRETE_R_T,
        TERMINAL_USD_T,
        PERFIL_ATR,
        PERFIL_MIX,
        PERFIL_MOAGEM_PCT
    )


# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

def fmt_br(valor, casas=2):
    """Formata número no padrão brasileiro: 1.234.567,89"""
    if valor is None or pd.isna(valor):
        return ""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def safe_float(valor, default=0.0):
    """Converte valor para float de forma segura"""
    if valor is None:
        return default
    try:
        return float(valor)
    except (ValueError, TypeError):
        return default

# ============================================================================
# FUNÇÕES DE BUSCA DE PREÇOS REAIS
# ============================================================================

def buscar_dolar_bacen(data_corte=None):
    """
    Busca cotação do dólar (USD/BRL) do Banco Central do Brasil.

    Args:
        data_corte: Data para buscar (datetime.date). Se None, usa data atual.

    Returns:
        float: Cotação USD/BRL ou None em caso de erro
    """
    if not REQUESTS_AVAILABLE:
        st.error("❌ Bibliotecas necessárias não estão instaladas. Instale: pip install requests beautifulsoup4")
        return None

    try:
        if data_corte is None:
            data_corte = date.today()

        # API do Banco Central - Série de cotações diárias
        # Código da série: 1 (USD - Taxa de câmbio livre - Dólar americano (venda))
        # Formato da API: DD/MM/YYYY (formato brasileiro)
        data_str = data_corte.strftime('%d/%m/%Y')

        # URL da API do BCB - busca por período
        # A API do BCB espera formato DD/MM/YYYY
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json&dataInicial={data_str}&dataFinal={data_str}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        dados = response.json()

        if dados and len(dados) > 0:
            # Pega o último valor disponível
            # A API retorna o valor como string ou número
            valor = dados[-1]['valor']

            # Converte para float, tratando diferentes formatos
            if isinstance(valor, str):
                # Remove espaços, substitui vírgula por ponto
                valor_str = valor.strip().replace(',', '.').replace(' ', '')
                cotacao = float(valor_str)
            else:
                cotacao = float(valor)

            # Retorna com precisão de 4 casas decimais
            return round(cotacao, 4)

        # Se não encontrou na data específica, tenta buscar a última disponível
        url_ultima = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados/ultimos/1?formato=json"
        response = requests.get(url_ultima, headers=headers, timeout=10)
        response.raise_for_status()
        dados = response.json()

        if dados and len(dados) > 0:
            valor = dados[0]['valor']
            if isinstance(valor, str):
                valor_str = valor.strip().replace(',', '.').replace(' ', '')
                cotacao = float(valor_str)
            else:
                cotacao = float(valor)
            return round(cotacao, 4)

        return None
    except Exception as e:
        st.warning(f"Erro ao buscar dólar do BACEN: {e}")
        return None


def buscar_ny11_yahoo_finance():
    """
    Tenta buscar NY11 do Yahoo Finance (método alternativo).

    Returns:
        float: Cotação NY11 em USc/lb ou None
    """
    try:
        # Yahoo Finance - Sugar #11 (SB=F)
        # URL alternativa: usar API não oficial do Yahoo Finance
        url = "https://query1.finance.yahoo.com/v8/finance/chart/SB=F?interval=1d&range=1d"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        if 'chart' in data and 'result' in data['chart']:
            result = data['chart']['result']
            if result and len(result) > 0:
                meta = result[0].get('meta', {})
                preco = meta.get('regularMarketPrice') or meta.get('previousClose')
                if preco:
                    # Yahoo Finance retorna em cents/lb
                    # Retorna com 2 casas decimais (precisão padrão para preços)
                    return round(float(preco), 2)

        return None
    except Exception as e:
        return None


def buscar_ny11_tradingview():
    """
    Tenta buscar NY11 do TradingView (scraping).

    Returns:
        float: Cotação NY11 em USc/lb ou None
    """
    try:
        # TradingView - Sugar #11
        url = "https://www.tradingview.com/symbols/ICE-SB1!/"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Procura por elementos com preço
        elementos_preco = soup.find_all(['span', 'div'], class_=re.compile(r'last|price|value', re.I))

        for elemento in elementos_preco:
            texto = elemento.get_text(strip=True)
            match = re.search(r'(\d{1,2}\.\d{2})', texto)
            if match:
                valor = float(match.group(1))
                if 10.0 <= valor <= 30.0:
                    return valor

        return None
    except Exception as e:
        return None


def buscar_ny11_investing(data_corte=None):
    """
    Busca cotação do NY11 (Açúcar #11 Futuros) tentando múltiplas fontes.

    Tenta na seguinte ordem:
    1. Yahoo Finance (API não oficial)
    2. TradingView (scraping)
    3. Investing.com (scraping melhorado)

    Args:
        data_corte: Data para buscar (datetime.date). Se None, usa data atual.
        Nota: A maioria das fontes mostra apenas o preço atual, não histórico.

    Returns:
        float: Cotação NY11 em USc/lb ou None em caso de erro
    """
    if not REQUESTS_AVAILABLE:
        st.error("❌ Bibliotecas necessárias não estão instaladas. Instale: pip install requests beautifulsoup4")
        return None

    # Tenta Yahoo Finance primeiro (mais confiável)
    preco = buscar_ny11_yahoo_finance()
    if preco:
        return preco

    # Tenta TradingView
    preco = buscar_ny11_tradingview()
    if preco:
        return preco

    # Tenta Investing.com (método original melhorado)
    try:
        # Investing.com - Sugar #11 Futures
        url = "https://www.investing.com/commodities/us-sugar-no11"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Estratégia 1: Procurar por elementos com id específicos
        ids_possiveis = [
            'last_last', 'quotes_summary_current_data', 'instrument-header-last',
            'leftColumn', 'rightColumn', 'lastInst'
        ]
        for id_elem in ids_possiveis:
            elemento = soup.find(id=id_elem)
            if elemento:
                texto = elemento.get_text(strip=True)
                # Procura por padrão de preço
                matches = re.findall(r'(\d{1,2}\.\d{2,3})', texto)
                for match in matches:
                    try:
                        valor = float(match)
                        if 10.0 <= valor <= 30.0:
                            # Retorna com 2 casas decimais (precisão padrão para preços)
                            return round(valor, 2)
                    except ValueError:
                        continue

        # Estratégia 2: Procurar por classes comuns
        classes_possiveis = [
            'last', 'price', 'value', 'instrument-price-last',
            'pid-8827-last', 'text-2xl', 'text-3xl', 'font-bold'
        ]
        for classe in classes_possiveis:
            elementos = soup.find_all(class_=re.compile(classe, re.I))
            for elemento in elementos:
                texto = elemento.get_text(strip=True)
                matches = re.findall(r'(\d{1,2}\.\d{2,3})', texto)
                for match in matches:
                    try:
                        valor = float(match)
                        if 10.0 <= valor <= 30.0:
                            # Retorna com 2 casas decimais (precisão padrão para preços)
                            return round(valor, 2)
                    except ValueError:
                        continue

        # Estratégia 3: Procurar por atributos data-test ou data-symbol
        elementos_data = soup.find_all(attrs={'data-test': True})
        elementos_data.extend(soup.find_all(attrs={'data-symbol': True}))

        for elemento in elementos_data:
            texto = elemento.get_text(strip=True)
            matches = re.findall(r'(\d{1,2}\.\d{2,3})', texto)
            for match in matches:
                try:
                    valor = float(match)
                    if 10.0 <= valor <= 30.0:
                        # Retorna com 2 casas decimais (precisão padrão para preços)
                        return round(valor, 2)
                except ValueError:
                    continue

        # Estratégia 4: Procurar em todo o texto da página por padrões
        texto_pagina = soup.get_text()
        # Procura por padrões mais específicos
        padroes = [
            r'(?:Sugar|Açúcar|NY11|#11|Futures).*?(\d{1,2}\.\d{2,3})',
            r'(\d{1,2}\.\d{2,3}).*?(?:cents|lb|pound|USD)',
            r'Last[:\s]+(\d{1,2}\.\d{2,3})',
            r'Price[:\s]+(\d{1,2}\.\d{2,3})',
        ]
        for padrao in padroes:
            matches = re.findall(padrao, texto_pagina, re.IGNORECASE)
            for match in matches:
                try:
                    valor = float(match)
                    if 10.0 <= valor <= 30.0:
                        # Retorna com 2 casas decimais (precisão padrão para preços)
                        return round(valor, 2)
                except ValueError:
                    continue

        return None

    except Exception as e:
        st.warning(f"Erro ao buscar NY11: {e}")
        return None


# ============================================================================
# FUNÇÕES DE PERSISTÊNCIA
# ============================================================================

def salvar_dados_reais(dados_reais, arquivo="dados_reais_safra.json"):
    """Salva dados reais em arquivo JSON"""
    try:
        caminho_arquivo = Path(arquivo)
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            # Converte chaves int para str para JSON
            dados_serializados = {str(k): v for k, v in dados_reais.items()}
            json.dump(dados_serializados, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar dados: {e}")
        return False

def carregar_dados_reais(arquivo="dados_reais_safra.json"):
    """Carrega dados reais de arquivo JSON"""
    try:
        caminho_arquivo = Path(arquivo)
        if caminho_arquivo.exists():
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                dados_serializados = json.load(f)
                # Converte chaves str de volta para int
                dados_reais = {int(k): v for k, v in dados_serializados.items()}
                return dados_reais
        return {}
    except Exception as e:
        st.warning(f"Erro ao carregar dados: {e}")
        return {}


# ============================================================================
# CONFIGURAÇÃO STREAMLIT
# ============================================================================

st.set_page_config(page_title="Acompanhamento de Safra", layout="wide")


# ============================================================================
# CONSTANTES DE PRODUÇÃO
# ============================================================================

FATOR_ACUCAR = 0.95275
FATOR_ETANOL = 0.595
PERCENTUAL_ETANOL_MILHO = 0.30  # 30% do total de etanol é de milho

# Volatilidades e correlações padrão
DEFAULT_PRICE_VOLS = {
    "sugar": 0.282222,
    "usdbrl": 0.15098,
    "ethanol": 0.25126,
}

RHO_SUGAR_ETHANOL = 0.502463893713162
RHO_SUGAR_USDBRL = 0.786767236856384
RHO_ETHANOL_USDBRL = 0.452409814996351

DEFAULT_CORR_MATRIX = np.array([
    [1.0, RHO_SUGAR_ETHANOL, RHO_SUGAR_USDBRL],
    [RHO_SUGAR_ETHANOL, 1.0, RHO_ETHANOL_USDBRL],
    [RHO_SUGAR_USDBRL, RHO_ETHANOL_USDBRL, 1.0]
])


# ============================================================================
# FUNÇÕES DE CÁLCULO DE PRODUÇÃO
# ============================================================================

def calcular_producao(moagem, atr, mix_acucar):
    """Calcula produção de açúcar (t) e etanol (m³)"""
    mix = mix_acucar / 100
    acucar = ((moagem * mix * atr) * FATOR_ACUCAR) / 1000
    etanol = (moagem * atr * ((1 - mix) * FATOR_ETANOL) / 1000)
    return acucar, etanol


def calcular_producao_quinzenal(moagem, atr, mix):
    """Calcula produção quinzenal de açúcar (t) e etanol (m³)"""
    mix_decimal = mix / 100 if isinstance(mix, (int, float)) and mix > 1 else mix
    acucar = ((moagem * mix_decimal * atr) * FATOR_ACUCAR) / 1000
    etanol = (moagem * atr * ((1 - mix_decimal) * FATOR_ETANOL) / 1000)
    return acucar, etanol


def calcular_etanol_detalhado(etanol_total_cana, quinzena, n_quinzenas_total):
    """
    Calcula distribuição de etanol de cana (anidro e hidratado) baseado no perfil da safra.

    Regra:
    - Anidro começa em 20% e aumenta 2 pontos percentuais até chegar em 44%
    - Depois diminui 2 pontos percentuais
    - Hidratado = Total - Anidro
    """
    # Calcula percentual de anidro baseado na quinzena
    # Aproximadamente no meio da safra (quinzena 12 de 24) atinge 44%
    meio_safra = n_quinzenas_total / 2

    if quinzena <= meio_safra:
        # Fase crescente: 20% até 44%
        pct_anidro = 0.20 + (quinzena - 1) * 0.02
        pct_anidro = min(pct_anidro, 0.44)
    else:
        # Fase decrescente: diminui 2 pontos percentuais
        pct_anidro = 0.44 - (quinzena - meio_safra) * 0.02
        pct_anidro = max(pct_anidro, 0.20)

    etanol_anidro_cana = etanol_total_cana * pct_anidro
    etanol_hidratado_cana = etanol_total_cana - etanol_anidro_cana

    return etanol_anidro_cana, etanol_hidratado_cana


def calcular_etanol_milho(etanol_total, quinzena, n_quinzenas_total):
    """
    Calcula produção de etanol de milho (30% do total) e distribui entre anidro e hidratado.
    Usa as mesmas proporções do etanol de cana.
    """
    etanol_total_milho = etanol_total * PERCENTUAL_ETANOL_MILHO
    etanol_anidro_milho, etanol_hidratado_milho = calcular_etanol_detalhado(
        etanol_total_milho, quinzena, n_quinzenas_total
    )
    return etanol_anidro_milho, etanol_hidratado_milho


def simular_producao_etanol_com_volatilidade(etanol_base, tipo, seed=None):
    """
    Simula produção de etanol adicionando ruído baseado em volatilidade e desvio padrão.

    Args:
        etanol_base: Valor base da produção (m³)
        tipo: Tipo de etanol ('anidro_cana', 'hidratado_cana', 'anidro_milho', 'hidratado_milho')
        seed: Semente para reprodutibilidade (opcional)

    Returns:
        float: Valor simulado com ruído
    """
    try:
        from Dados_base import (
            VOLATILIDADE_ETANOL_ANIDRO_CANA,
            VOLATILIDADE_ETANOL_HIDRATADO_CANA,
            VOLATILIDADE_ETANOL_ANIDRO_MILHO,
            VOLATILIDADE_ETANOL_HIDRATADO_MILHO,
            DESVIO_PADRAO_ETANOL_ANIDRO_CANA,
            DESVIO_PADRAO_ETANOL_HIDRATADO_CANA,
            DESVIO_PADRAO_ETANOL_ANIDRO_MILHO,
            DESVIO_PADRAO_ETANOL_HIDRATADO_MILHO
        )
    except ImportError:
        # Se não conseguir importar, retorna valor base sem simulação
        return etanol_base

    if etanol_base <= 0:
        return 0.0

    rng = np.random.default_rng(seed)

    # Seleciona parâmetros baseado no tipo
    if tipo == 'anidro_cana':
        volatilidade = VOLATILIDADE_ETANOL_ANIDRO_CANA
        desvio_padrao = DESVIO_PADRAO_ETANOL_ANIDRO_CANA
    elif tipo == 'hidratado_cana':
        volatilidade = VOLATILIDADE_ETANOL_HIDRATADO_CANA
        desvio_padrao = DESVIO_PADRAO_ETANOL_HIDRATADO_CANA
    elif tipo == 'anidro_milho':
        volatilidade = VOLATILIDADE_ETANOL_ANIDRO_MILHO
        desvio_padrao = DESVIO_PADRAO_ETANOL_ANIDRO_MILHO
    elif tipo == 'hidratado_milho':
        volatilidade = VOLATILIDADE_ETANOL_HIDRATADO_MILHO
        desvio_padrao = DESVIO_PADRAO_ETANOL_HIDRATADO_MILHO
    else:
        # Tipo desconhecido, retorna valor base
        return etanol_base

    # Adiciona ruído usando distribuição normal
    # Usa desvio padrão absoluto ou volatilidade relativa, o que for mais apropriado
    # Para valores grandes, usa volatilidade relativa; para valores pequenos, usa desvio padrão
    if etanol_base > desvio_padrao * 2:
        # Usa volatilidade relativa (percentual)
        ruido = rng.normal(0, volatilidade)
        etanol_simulado = etanol_base * (1 + ruido)
    else:
        # Usa desvio padrão absoluto
        ruido = rng.normal(0, desvio_padrao)
        etanol_simulado = etanol_base + ruido

    # Garante que não seja negativo
    return max(0.0, etanol_simulado)


# ============================================================================
# FUNÇÕES DE CONVERSÃO DE PREÇOS
# ============================================================================

def converter_etanol_para_fob_cents_lb(preco_etanol_pvu_m3, cambio_usd_brl):
    """Converte preço do etanol PVU (R$/m³) para equivalente FOB em cents/lb"""
    if cambio_usd_brl <= 0 or preco_etanol_pvu_m3 <= 0:
        return 0.0

    preco_sem_icms = preco_etanol_pvu_m3 * (1 - ICMS_ETANOL)
    preco_liquido_pvu = preco_sem_icms - PIS_COFINS_ETANOL

    if preco_liquido_pvu <= 0:
        return 0.0

    FATOR_CONVERSAO_ETANOL_VHP = 31.504
    SACAS_POR_TONELADA = 20
    CENTS_LB_POR_TON = 22.0462
    FATOR_AJUSTE_QUALIDADE = 1.042

    equivalente_vhp_r_por_saco = (preco_liquido_pvu / FATOR_CONVERSAO_ETANOL_VHP) * SACAS_POR_TONELADA
    numerador = equivalente_vhp_r_por_saco + FRETE_R_T + (TERMINAL_USD_T * cambio_usd_brl)
    preco_fob_cents_lb = (numerador / CENTS_LB_POR_TON / cambio_usd_brl) / FATOR_AJUSTE_QUALIDADE

    return preco_fob_cents_lb


def converter_acucar_vhp_para_fob(preco_ny11_cents_lb):
    """Converte preço do açúcar VHP (NY11) para FOB em cents/lb"""
    if preco_ny11_cents_lb <= 0:
        return 0.0
    preco_fob = (preco_ny11_cents_lb - DESCONTO_VHP_FOB) * (1 + TAXA_POL)
    return max(0.0, preco_fob)


def calcular_paridade_etanol_acucar(preco_etanol_pvu_m3, preco_ny11_cents_lb, cambio_usd_brl):
    """Calcula paridade etanol/açúcar comparando equivalentes FOB em cents/lb"""
    if preco_ny11_cents_lb <= 0:
        return 1.0

    preco_etanol_fob_cents_lb = converter_etanol_para_fob_cents_lb(preco_etanol_pvu_m3, cambio_usd_brl)
    if preco_etanol_fob_cents_lb <= 0:
        return 1.0

    preco_acucar_fob_cents_lb = converter_acucar_vhp_para_fob(preco_ny11_cents_lb)
    if preco_acucar_fob_cents_lb <= 0:
        return 1.0

    paridade = preco_etanol_fob_cents_lb / preco_acucar_fob_cents_lb
    return paridade


def ny11_para_brl(cents_lb: float, usdbrl: float) -> float:
    """Converte NY11 (USc/lb) e USD/BRL em R$/t"""
    LB_POR_TON = 2204.62
    usd_per_ton = (cents_lb / 100.0) * LB_POR_TON
    return usd_per_ton * usdbrl


# ============================================================================
# FUNÇÕES DE SIMULAÇÃO E AJUSTE
# ============================================================================

def gerar_projecao_baseline_exata(moagem_total, atr_medio, mix_medio, n_quinzenas=24, data_inicio=None):
    """
    Gera projeção baseline EXATA baseada no perfil histórico.
    Esta é a projeção "ideal" que segue exatamente o perfil sem ajustes.
    """
    if data_inicio is None:
        data_inicio = date(date.today().year, 4, 1)

    datas = pd.date_range(start=data_inicio, periods=n_quinzenas, freq="15D")

    # Usa perfil de representatividade de moagem EXATO
    n_perfil_moagem = len(PERFIL_MOAGEM_PCT)
    pct_moagem = [PERFIL_MOAGEM_PCT[i % n_perfil_moagem] / 100.0 for i in range(n_quinzenas)]

    # Normaliza para garantir que soma = 1.0
    soma_pct = sum(pct_moagem)
    if soma_pct > 0:
        pct_moagem = [p / soma_pct for p in pct_moagem]

    # Moagem distribuída EXATAMENTE pelo perfil
    moagem_baseline = [moagem_total * pct_moagem[i] for i in range(n_quinzenas)]

    # Perfis de ATR e MIX
    n_perfil = len(PERFIL_ATR)
    perfil_atr = [PERFIL_ATR[i % n_perfil] for i in range(n_quinzenas)]
    perfil_mix = [PERFIL_MIX[i % n_perfil] for i in range(n_quinzenas)]

    # Calcula SOMARPRODUTO para ATR e Mix
    somarproduto_atr = sum(moagem_baseline[i] * perfil_atr[i] for i in range(n_quinzenas))
    somarproduto_mix = sum(moagem_baseline[i] * perfil_mix[i] for i in range(n_quinzenas))

    # Calcula fatores de correção para manter as médias
    fator_atr = (atr_medio * moagem_total) / somarproduto_atr if somarproduto_atr > 0 else 1.0
    fator_mix = (mix_medio * moagem_total) / somarproduto_mix if somarproduto_mix > 0 else 1.0

    # Gera DataFrame baseline
    linhas = []
    for i in range(n_quinzenas):
        quinzena = i + 1
        moagem_q = moagem_baseline[i]
        atr_q = perfil_atr[i] * fator_atr
        mix_q = perfil_mix[i] * fator_mix

        acucar_q, etanol_q = calcular_producao_quinzenal(moagem_q, atr_q, mix_q)

        etanol_anidro_cana, etanol_hidratado_cana = calcular_etanol_detalhado(
            etanol_q, quinzena, n_quinzenas
        )
        etanol_anidro_milho, etanol_hidratado_milho = calcular_etanol_milho(
            etanol_q, quinzena, n_quinzenas
        )

        etanol_total_quinzena = etanol_anidro_cana + etanol_hidratado_cana + etanol_anidro_milho + etanol_hidratado_milho

        linhas.append({
            "Quinzena": quinzena,
            "Mês": datas[i].month,
            "Data": datas[i].date(),
            "Moagem Baseline": moagem_q,
            "ATR Baseline": atr_q,
            "MIX Baseline": mix_q,
            "Açúcar Baseline (t)": acucar_q,
            "Etanol Baseline (m³)": etanol_q,
        })

    df_baseline = pd.DataFrame(linhas)
    return df_baseline


def gerar_projecao_quinzenal(moagem_total, atr_medio, mix_medio, n_quinzenas=24,
                              data_inicio=None, dados_reais=None, choques_safra=None, seed=42,
                              usar_volatilidade_etanol=False):
    """
    Gera projeção quinzenal ajustada com dados reais.

    Usa perfil de representatividade de moagem e perfis históricos de ATR e MIX.
    Mantém a FORMA do perfil, mas ajusta para os totais estimados.
    Mantém projeções baseline para comparação.
    """
    if data_inicio is None:
        data_inicio = date(date.today().year, 4, 1)

    rng = np.random.default_rng(seed)

    # Usa perfil de representatividade de moagem (percentual de cada quinzena)
    # Converte percentuais para decimais (ex: 2.67% -> 0.0267)
    n_perfil_moagem = len(PERFIL_MOAGEM_PCT)
    pct_moagem = [PERFIL_MOAGEM_PCT[i % n_perfil_moagem] / 100.0 for i in range(n_quinzenas)]

    # Normaliza para garantir que soma = 1.0
    soma_pct = sum(pct_moagem)
    if soma_pct > 0:
        pct_moagem = [p / soma_pct for p in pct_moagem]

    datas = pd.date_range(start=data_inicio, periods=n_quinzenas, freq="15D")

    # Calcula moagem distribuída baseada no perfil de representatividade
    # Esta é a distribuição INICIAL seguindo exatamente o perfil
    moagem_distribuida_inicial = [moagem_total * pct_moagem[i] for i in range(n_quinzenas)]
    moagem_distribuida = moagem_distribuida_inicial.copy()

    # Usa perfis históricos de ATR e MIX (mantém a FORMA do perfil)
    n_perfil = len(PERFIL_ATR)
    perfil_atr_ajustado = [PERFIL_ATR[i % n_perfil] for i in range(n_quinzenas)]
    perfil_mix_ajustado = [PERFIL_MIX[i % n_perfil] for i in range(n_quinzenas)]

    # Calcula SOMARPRODUTO para ATR e Mix usando a distribuição inicial
    somarproduto_atr_original = sum(moagem_distribuida_inicial[i] * perfil_atr_ajustado[i] for i in range(n_quinzenas))
    somarproduto_mix_original = sum(moagem_distribuida_inicial[i] * perfil_mix_ajustado[i] for i in range(n_quinzenas))

    # Calcula fatores de correção baseados no total estimado (garantem a média final)
    fator_atr_global = (atr_medio * moagem_total) / somarproduto_atr_original if somarproduto_atr_original > 0 else 1.0
    fator_mix_global = (mix_medio * moagem_total) / somarproduto_mix_original if somarproduto_mix_original > 0 else 1.0

    # Identifica última quinzena com dados reais
    ultima_quinzena_real = 0
    moagem_real_acum_total = 0
    if dados_reais:
        for q in sorted(dados_reais.keys(), reverse=True):
            if dados_reais[q].get('moagem_real') is not None:
                ultima_quinzena_real = q
                moagem_real_acum_total = dados_reais[q].get('moagem_real', 0)
                break

    # Ajusta distribuição futura da moagem para manter o total final estimado
    # IMPORTANTE: As quinzenas futuras começam APÓS a última quinzena com dados reais
    if ultima_quinzena_real > 0:
        primeira_quinzena_futura = ultima_quinzena_real + 1
    else:
        primeira_quinzena_futura = 1  # Se não há dados reais, todas são futuras

    if ultima_quinzena_real > 0 and primeira_quinzena_futura <= n_quinzenas:
        moagem_restante = moagem_total - moagem_real_acum_total

        # Calcula os pesos das quinzenas futuras (após a última com dados reais)
        # MANTÉM A FORMA DO PERFIL - usa os percentuais originais do perfil
        pesos_futuros = [pct_moagem[i] for i in range(primeira_quinzena_futura - 1, n_quinzenas)]
        soma_pesos_futuros = sum(pesos_futuros) if pesos_futuros else 1.0

        if soma_pesos_futuros > 0 and moagem_restante >= 0:
            # Redistribui proporcionalmente ao perfil ORIGINAL
            # Isso mantém a FORMA da curva do perfil, apenas ajusta a escala
            for i in range(primeira_quinzena_futura - 1, n_quinzenas):
                # Mantém a proporção exata do perfil
                moagem_distribuida[i] = moagem_restante * (pct_moagem[i] / soma_pesos_futuros)
        elif moagem_restante < 0:
            # Se a moagem real excedeu o total, zera as futuras
            for i in range(primeira_quinzena_futura - 1, n_quinzenas):
                moagem_distribuida[i] = 0

    # Ajusta ATR e MIX para manterem a média final estimada
    atr_real_acum_ponderado = 0
    mix_real_acum_ponderado = 0
    moagem_real_para_media = 0

    if dados_reais and ultima_quinzena_real > 0:
        for q in range(1, ultima_quinzena_real + 1):
            if q in dados_reais and dados_reais[q].get('moagem_real') is not None:
                # Calcula moagem quinzenal real (diferença do acumulado)
                if q == 1:
                    moagem_q_real = dados_reais[q].get('moagem_real', 0)
                else:
                    moagem_ant = dados_reais.get(q - 1, {}).get('moagem_real', 0) or 0
                    moagem_q_real = dados_reais[q].get('moagem_real', 0) - moagem_ant

                atr_q_real = dados_reais[q].get('atr_real')
                mix_q_real = dados_reais[q].get('mix_real')

                if atr_q_real is not None:
                    atr_real_acum_ponderado += atr_q_real * moagem_q_real
                if mix_q_real is not None:
                    mix_real_acum_ponderado += mix_q_real * moagem_q_real

                moagem_real_para_media += moagem_q_real

    fator_atr_futuro = fator_atr_global
    fator_mix_futuro = fator_mix_global

    # Ajusta fatores de ATR e MIX para as quinzenas futuras
    # Só ajusta se houver dados reais e quinzenas futuras
    if ultima_quinzena_real > 0 and primeira_quinzena_futura <= n_quinzenas:
        moagem_futura_total = sum(moagem_distribuida[i] for i in range(primeira_quinzena_futura - 1, n_quinzenas))

        if moagem_futura_total > 0:
            # Calcula o ATR e MIX total que ainda precisa ser alcançado
            # Se não há dados reais de ATR/MIX, usa os valores projetados das quinzenas com dados reais
            if atr_real_acum_ponderado == 0:
                # Não há dados reais de ATR, então calcula baseado nas projeções das quinzenas com dados reais
                atr_projetado_acum = 0
                for q in range(1, ultima_quinzena_real + 1):
                    if q in dados_reais and dados_reais[q].get('moagem_real') is not None:
                        if q == 1:
                            moagem_q_proj = dados_reais[q].get('moagem_real', 0)
                        else:
                            moagem_ant = dados_reais.get(q - 1, {}).get('moagem_real', 0) or 0
                            moagem_q_proj = dados_reais[q].get('moagem_real', 0) - moagem_ant
                        atr_projetado_acum += perfil_atr_ajustado[q - 1] * fator_atr_global * moagem_q_proj
                atr_total_restante = (atr_medio * moagem_total) - atr_projetado_acum
            else:
                atr_total_restante = (atr_medio * moagem_total) - atr_real_acum_ponderado

            # Calcula mix_total_restante usando a mesma lógica do ATR
            # Se não há dados reais de MIX, calcula baseado nas projeções das quinzenas com dados reais
            if mix_real_acum_ponderado == 0:
                # Não há dados reais de MIX, então calcula baseado nas projeções das quinzenas com dados reais
                mix_projetado_acum = 0
                for q in range(1, ultima_quinzena_real + 1):
                    if q in dados_reais and dados_reais[q].get('moagem_real') is not None:
                        if q == 1:
                            moagem_q_proj = dados_reais[q].get('moagem_real', 0)
                        else:
                            moagem_ant = dados_reais.get(q - 1, {}).get('moagem_real', 0) or 0
                            moagem_q_proj = dados_reais[q].get('moagem_real', 0) - moagem_ant
                        mix_projetado_acum += perfil_mix_ajustado[q - 1] * fator_mix_global * moagem_q_proj
                mix_total_restante = (mix_medio * moagem_total) - mix_projetado_acum
            else:
                # Há dados reais de MIX, usa o valor acumulado ponderado
                mix_total_restante = (mix_medio * moagem_total) - mix_real_acum_ponderado

            # Calcula o somarproduto das quinzenas futuras com os perfis originais
            # Usa a moagem_distribuida já ajustada para manter a proporção do perfil
            somarproduto_atr_futuro_base = sum(moagem_distribuida[i] * perfil_atr_ajustado[i]
                                                for i in range(primeira_quinzena_futura - 1, n_quinzenas))
            somarproduto_mix_futuro_base = sum(moagem_distribuida[i] * perfil_mix_ajustado[i]
                                                for i in range(primeira_quinzena_futura - 1, n_quinzenas))

            # Calcula fatores futuros - mesma lógica para ATR e MIX
            # IMPORTANTE: Usa a fórmula de ponderação: fator = (total_necessario - acumulado_real) / somarproduto_futuro
            # Mas garante que o fator não fique muito distante do fator global (mantém a forma do perfil)
            if somarproduto_atr_futuro_base > 0 and atr_total_restante >= 0:
                fator_atr_futuro_calc = atr_total_restante / somarproduto_atr_futuro_base
                # Limita a variação do fator para não sair muito do perfil (máximo 30% de variação)
                variacao_max = 0.30
                if abs(fator_atr_futuro_calc - fator_atr_global) / fator_atr_global > variacao_max:
                    # Se a variação for muito grande, ajusta para manter próximo ao perfil
                    if fator_atr_futuro_calc > fator_atr_global:
                        fator_atr_futuro = fator_atr_global * (1 + variacao_max)
                    else:
                        fator_atr_futuro = fator_atr_global * (1 - variacao_max)
                else:
                    fator_atr_futuro = fator_atr_futuro_calc
            else:
                fator_atr_futuro = fator_atr_global  # Fallback para o fator global

            if somarproduto_mix_futuro_base > 0 and mix_total_restante >= 0:
                fator_mix_futuro_calc = mix_total_restante / somarproduto_mix_futuro_base
                # Limita a variação do fator para não sair muito do perfil (máximo 30% de variação)
                variacao_max = 0.30
                if abs(fator_mix_futuro_calc - fator_mix_global) / fator_mix_global > variacao_max:
                    # Se a variação for muito grande, ajusta para manter próximo ao perfil
                    if fator_mix_futuro_calc > fator_mix_global:
                        fator_mix_futuro = fator_mix_global * (1 + variacao_max)
                    else:
                        fator_mix_futuro = fator_mix_global * (1 - variacao_max)
                else:
                    fator_mix_futuro = fator_mix_futuro_calc
            else:
                fator_mix_futuro = fator_mix_global  # Fallback para o fator global

            # Validação adicional: garante que os fatores sejam válidos e positivos
            if fator_mix_futuro <= 0 or not np.isfinite(fator_mix_futuro):
                fator_mix_futuro = fator_mix_global
            if fator_atr_futuro <= 0 or not np.isfinite(fator_atr_futuro):
                fator_atr_futuro = fator_atr_global

            # Garante que os fatores não sejam muito diferentes do global (proteção adicional)
            if fator_atr_futuro < fator_atr_global * 0.5 or fator_atr_futuro > fator_atr_global * 1.5:
                fator_atr_futuro = fator_atr_global
            if fator_mix_futuro < fator_mix_global * 0.5 or fator_mix_futuro > fator_mix_global * 1.5:
                fator_mix_futuro = fator_mix_global

    # Gera projeção baseline EXATA para comparação
    df_baseline = gerar_projecao_baseline_exata(moagem_total, atr_medio, mix_medio, n_quinzenas, data_inicio)

    # Calcula projeções originais (antes de ajustes com dados reais) para comparação
    projecoes_originais = {}
    for i in range(n_quinzenas):
        quinzena = i + 1
        projecoes_originais[quinzena] = {
            'moagem': moagem_distribuida_inicial[i],
            'atr': perfil_atr_ajustado[i] * fator_atr_global,
            'mix': perfil_mix_ajustado[i] * fator_mix_global
        }

    linhas = []
    for i in range(n_quinzenas):
        quinzena = i + 1

        # Verifica se há dados reais para esta quinzena
        tem_dados_reais = dados_reais and quinzena in dados_reais and dados_reais[quinzena].get('moagem_real') is not None

        # Projeção original (para comparação)
        proj_orig = projecoes_originais[quinzena]
        moagem_proj_orig = proj_orig['moagem']
        atr_proj_orig = proj_orig['atr']
        mix_proj_orig = proj_orig['mix']

        if tem_dados_reais:
            # Dados reais são ACUMULADOS, então calcula a diferença
            moagem_acum_atual = dados_reais[quinzena].get('moagem_real', 0)
            if quinzena == 1:
                moagem_q = moagem_acum_atual
            else:
                moagem_acum_anterior = dados_reais[quinzena - 1].get('moagem_real', 0) if (quinzena - 1) in dados_reais else 0
                moagem_q = moagem_acum_atual - moagem_acum_anterior

            # ATR e Mix são médios, usa o valor real se disponível, senão usa o perfil ajustado
            # IMPORTANTE: Se não há valor real, usa o perfil com o fator global (não o futuro)
            atr_q = dados_reais[quinzena].get('atr_real')
            if atr_q is None:
                atr_q = perfil_atr_ajustado[i] * fator_atr_global

            mix_q = dados_reais[quinzena].get('mix_real')
            if mix_q is None:
                # Se não há mix real, usa o perfil com o fator global
                mix_q = perfil_mix_ajustado[i] * fator_mix_global
        else:
            # Usa projeção ajustada para quinzenas futuras
            # Se está na primeira quinzena futura ou depois, usa os fatores ajustados
            if quinzena >= primeira_quinzena_futura:
                moagem_q = moagem_distribuida[i]
                atr_q = perfil_atr_ajustado[i] * fator_atr_futuro
                mix_q = perfil_mix_ajustado[i] * fator_mix_futuro

                # Validação: garante que MIX e ATR não sejam zero ou negativo
                # E garante que não saiam muito do perfil (máximo 50% de variação do baseline)
                atr_baseline = perfil_atr_ajustado[i] * fator_atr_global
                mix_baseline = perfil_mix_ajustado[i] * fator_mix_global

                if mix_q <= 0 or not np.isfinite(mix_q):
                    mix_q = mix_baseline
                elif abs(mix_q - mix_baseline) / mix_baseline > 0.5:  # Se variar mais de 50% do baseline
                    # Ajusta para ficar dentro do limite
                    if mix_q > mix_baseline:
                        mix_q = mix_baseline * 1.5
                    else:
                        mix_q = mix_baseline * 0.5

                if atr_q <= 0 or not np.isfinite(atr_q):
                    atr_q = atr_baseline
                elif abs(atr_q - atr_baseline) / atr_baseline > 0.5:  # Se variar mais de 50% do baseline
                    # Ajusta para ficar dentro do limite
                    if atr_q > atr_baseline:
                        atr_q = atr_baseline * 1.5
                    else:
                        atr_q = atr_baseline * 0.5
            else:
                # Quinzenas passadas sem dados reais (não deveria acontecer, mas por segurança)
                moagem_q = moagem_distribuida[i]
                atr_q = perfil_atr_ajustado[i] * fator_atr_global
                mix_q = perfil_mix_ajustado[i] * fator_mix_global

        # Aplica choques de safra apenas em quinzenas futuras (sem dados reais)
        if not tem_dados_reais and choques_safra and quinzena in choques_safra:
            choques_quinzena = choques_safra[quinzena]
            if isinstance(choques_quinzena, dict):
                choques_quinzena = [choques_quinzena]

            for choque in choques_quinzena:
                tipo = choque.get('tipo', '')
                magnitude = choque.get('magnitude', 0.0)

                if tipo == 'Moagem':
                    moagem_q = moagem_q * (1 + magnitude / 100)
                elif tipo == 'ATR':
                    atr_q = atr_q * (1 + magnitude / 100)
                elif tipo == 'MIX':
                    mix_q = mix_q * (1 + magnitude / 100)

        # Garante limites razoáveis
        mix_q = max(0, min(100, mix_q))
        atr_q = max(0, atr_q)

        # Calcula produção
        acucar_q, etanol_q = calcular_producao_quinzenal(moagem_q, atr_q, mix_q)

        # Calcula etanol detalhado
        etanol_anidro_cana_base, etanol_hidratado_cana_base = calcular_etanol_detalhado(
            etanol_q, quinzena, n_quinzenas
        )
        etanol_anidro_milho_base, etanol_hidratado_milho_base = calcular_etanol_milho(
            etanol_q, quinzena, n_quinzenas
        )

        # Aplica simulação com volatilidade se não houver dados reais e se usar_volatilidade_etanol estiver ativo
        # Usa seed baseado na quinzena para reprodutibilidade
        if not tem_dados_reais and usar_volatilidade_etanol:
            etanol_anidro_cana = simular_producao_etanol_com_volatilidade(
                etanol_anidro_cana_base, 'anidro_cana', seed=seed + quinzena
            )
            etanol_hidratado_cana = simular_producao_etanol_com_volatilidade(
                etanol_hidratado_cana_base, 'hidratado_cana', seed=seed + quinzena + 1000
            )
            etanol_anidro_milho = simular_producao_etanol_com_volatilidade(
                etanol_anidro_milho_base, 'anidro_milho', seed=seed + quinzena + 2000
            )
            etanol_hidratado_milho = simular_producao_etanol_com_volatilidade(
                etanol_hidratado_milho_base, 'hidratado_milho', seed=seed + quinzena + 3000
            )
        else:
            # Usa valores base (serão substituídos por dados reais se disponíveis)
            etanol_anidro_cana = etanol_anidro_cana_base
            etanol_hidratado_cana = etanol_hidratado_cana_base
            etanol_anidro_milho = etanol_anidro_milho_base
            etanol_hidratado_milho = etanol_hidratado_milho_base

        # Verifica se há dados reais de etanol (são ACUMULADOS, então calcula diferença)
        if tem_dados_reais:
            # Etanol acumulado atual
            etanol_anidro_cana_acum = dados_reais[quinzena].get('etanol_anidro_cana_real')
            etanol_hidratado_cana_acum = dados_reais[quinzena].get('etanol_hidratado_cana_real')
            etanol_anidro_milho_acum = dados_reais[quinzena].get('etanol_anidro_milho_real')
            etanol_hidratado_milho_acum = dados_reais[quinzena].get('etanol_hidratado_milho_real')

            # Calcula quinzenal como diferença do acumulado
            if etanol_anidro_cana_acum is not None:
                if quinzena == 1:
                    etanol_anidro_cana = etanol_anidro_cana_acum
                else:
                    etanol_anidro_cana_ant = dados_reais.get(quinzena - 1, {}).get('etanol_anidro_cana_real', 0) or 0
                    etanol_anidro_cana = etanol_anidro_cana_acum - etanol_anidro_cana_ant

            if etanol_hidratado_cana_acum is not None:
                if quinzena == 1:
                    etanol_hidratado_cana = etanol_hidratado_cana_acum
                else:
                    etanol_hidratado_cana_ant = dados_reais.get(quinzena - 1, {}).get('etanol_hidratado_cana_real', 0) or 0
                    etanol_hidratado_cana = etanol_hidratado_cana_acum - etanol_hidratado_cana_ant

            if etanol_anidro_milho_acum is not None:
                if quinzena == 1:
                    etanol_anidro_milho = etanol_anidro_milho_acum
                else:
                    etanol_anidro_milho_ant = dados_reais.get(quinzena - 1, {}).get('etanol_anidro_milho_real', 0) or 0
                    etanol_anidro_milho = etanol_anidro_milho_acum - etanol_anidro_milho_ant

            if etanol_hidratado_milho_acum is not None:
                if quinzena == 1:
                    etanol_hidratado_milho = etanol_hidratado_milho_acum
                else:
                    etanol_hidratado_milho_ant = dados_reais.get(quinzena - 1, {}).get('etanol_hidratado_milho_real', 0) or 0
                    etanol_hidratado_milho = etanol_hidratado_milho_acum - etanol_hidratado_milho_ant

        # Etanol total da quinzena (cana + milho)
        etanol_total_quinzena = etanol_anidro_cana + etanol_hidratado_cana + etanol_anidro_milho + etanol_hidratado_milho

        linhas.append({
            "Quinzena": quinzena,
            "Mês": datas[i].month,
            "Data": datas[i].date(),
            "Moagem": moagem_q,
            "ATR": atr_q,
            "MIX": mix_q,
            "Açúcar (t)": acucar_q,
            "Etanol Total (m³)": etanol_q,
            "Etanol Anidro Cana (m³)": etanol_anidro_cana,
            "Etanol Hidratado Cana (m³)": etanol_hidratado_cana,
            "Etanol Anidro Milho (m³)": etanol_anidro_milho,
            "Etanol Hidratado Milho (m³)": etanol_hidratado_milho,
            "Etanol Total Quinzena (m³)": etanol_total_quinzena,
            "Tem Dados Reais": tem_dados_reais,
            # Projeções originais para comparação
            "Moagem Proj. Original": moagem_proj_orig,
            "ATR Proj. Original": atr_proj_orig,
            "MIX Proj. Original": mix_proj_orig
        })

    df = pd.DataFrame(linhas)

    # Calcula acumulado progressivo
    df["Etanol Total Acumulado (m³)"] = df["Etanol Total Quinzena (m³)"].cumsum()
    
    # Adiciona outras colunas acumuladas
    df["Açúcar Acumulado (t)"] = df["Açúcar (t)"].cumsum()
    df["Etanol Acumulado (m³)"] = df["Etanol Total (m³)"].cumsum()
    df["Moagem Acumulada (ton)"] = df["Moagem"].cumsum()
    df["Etanol Anidro Cana Acumulado (m³)"] = df["Etanol Anidro Cana (m³)"].cumsum()
    df["Etanol Hidratado Cana Acumulado (m³)"] = df["Etanol Hidratado Cana (m³)"].cumsum()
    df["Etanol Anidro Milho Acumulado (m³)"] = df["Etanol Anidro Milho (m³)"].cumsum()
    df["Etanol Hidratado Milho Acumulado (m³)"] = df["Etanol Hidratado Milho (m³)"].cumsum()

    # Adiciona dados baseline para comparação
    df = df.merge(df_baseline[["Quinzena", "Moagem Baseline", "ATR Baseline", "MIX Baseline",
                                "Açúcar Baseline (t)", "Etanol Baseline (m³)"]],
                  on="Quinzena", how="left")

    return df


# ============================================================================
# FUNÇÕES DE SIMULAÇÃO DE PREÇOS
# ============================================================================

def simular_precos(ny11_inicial, usd_inicial, etanol_inicial, n_quinzenas,
                   df_producao, preco_ref=15.0, sensibilidade=0.10,
                   choques_precos=None, usar_paridade=False, dados_reais=None, seed=123):
    """
    Simula preços considerando:
    - Volatilidade e correlação entre commodities
    - Impacto da oferta (produção informada) nos preços
    - Choques externos (opcional)
    - Volatilidades específicas para etanol anidro e hidratado
    """
    rng = np.random.default_rng(seed)

    # Volatilidades
    vols = np.array([DEFAULT_PRICE_VOLS["sugar"], DEFAULT_PRICE_VOLS["ethanol"], DEFAULT_PRICE_VOLS["usdbrl"]])
    dt = 1.0 / 24.0
    cov_annual = np.outer(vols, vols) * DEFAULT_CORR_MATRIX
    cov_step = cov_annual * dt

    # Retornos correlacionados
    rets = rng.multivariate_normal(mean=[0.0, 0.0, 0.0], cov=cov_step, size=n_quinzenas)

    # Volatilidades específicas para etanol anidro e hidratado
    try:
        from Dados_base import (
            VOLATILIDADE_ETANOL_ANIDRO,
            VOLATILIDADE_ETANOL_HIDRATADO
        )
        vol_etanol_anidro = VOLATILIDADE_ETANOL_ANIDRO
        vol_etanol_hidratado = VOLATILIDADE_ETANOL_HIDRATADO
    except ImportError:
        # Usa volatilidade padrão se não conseguir importar
        vol_etanol_anidro = DEFAULT_PRICE_VOLS["ethanol"]
        vol_etanol_hidratado = DEFAULT_PRICE_VOLS["ethanol"]

    # Calcula produção total informada
    producao_total = 0
    for _, row in df_producao.iterrows():
        mix = row["MIX"] / 100
        producao_total += ((row["Moagem"] * mix * row["ATR"]) * FATOR_ACUCAR) / 1000

    producao_media = producao_total / n_quinzenas

    # Classifica preço inicial (alto/baixo)
    desvio_preco = (ny11_inicial - preco_ref) / preco_ref if preco_ref > 0 else 0

    # Calcula fator de oferta
    producao_normalizada = producao_media / 1_500_000
    fator_oferta_base = 1.0 - ((producao_normalizada - 1.0) * sensibilidade)

    # Ajusta baseado na interação preço inicial vs produção
    if desvio_preco < -0.05:  # Preço baixo
        if producao_normalizada > 1.0:
            fator_oferta = fator_oferta_base * 0.9
            direcao = "queda"
        else:
            fator_oferta = fator_oferta_base * 1.1
            direcao = "alta"
    elif desvio_preco > 0.05:  # Preço alto
        if producao_normalizada > 1.0:
            fator_oferta = fator_oferta_base * 1.05
            direcao = "alta"
        else:
            fator_oferta = fator_oferta_base * 1.15
            direcao = "alta"
    else:  # Preço neutro
        fator_oferta = fator_oferta_base
        direcao = "alta" if fator_oferta > 1.0 else "queda" if fator_oferta < 1.0 else "neutro"

    fator_oferta = np.clip(fator_oferta, 0.7, 1.3)

    # Simula trajetória
    ny11 = [ny11_inicial]
    etanol = [etanol_inicial]
    # Preços iniciais de etanol anidro e hidratado (assume que etanol_inicial é uma média)
    # Normalmente, anidro é um pouco mais caro que hidratado
    etanol_anidro = [etanol_inicial * 1.05]  # ~5% mais caro
    etanol_hidratado = [etanol_inicial * 0.95]  # ~5% mais barato
    usd = [usd_inicial]

    choques_aplicados = []

    # Gera retornos separados para etanol anidro e hidratado com suas volatilidades específicas
    rng_etanol = np.random.default_rng(seed + 10000)
    dt = 1.0 / 24.0
    rets_etanol_anidro = rng_etanol.normal(0, vol_etanol_anidro * np.sqrt(dt), n_quinzenas)
    rets_etanol_hidratado = rng_etanol.normal(0, vol_etanol_hidratado * np.sqrt(dt), n_quinzenas)

    for i in range(n_quinzenas):
        quinzena = i + 1
        r_sugar, r_eth, r_usd = rets[i]
        r_etanol_anidro = rets_etanol_anidro[i]
        r_etanol_hidratado = rets_etanol_hidratado[i]

        # Verifica se há dados reais de preços para esta quinzena
        tem_precos_reais = dados_reais and quinzena in dados_reais

        if tem_precos_reais:
            # Usa valores reais se disponíveis
            if dados_reais[quinzena].get('ny11_real'):
                ny11.append(dados_reais[quinzena]['ny11_real'])
            else:
                # Simula se não houver valor real
                r_sugar_ajustado = r_sugar * fator_oferta
                drift = (fator_oferta - 1.0) * 0.12
                ny11.append(ny11[-1] * (1 + r_sugar_ajustado + drift))

            if dados_reais[quinzena].get('usd_real'):
                usd.append(dados_reais[quinzena]['usd_real'])
            else:
                usd.append(usd[-1] * (1 + r_usd))

            # Para etanol, usa preços reais se disponíveis
            if dados_reais[quinzena].get('etanol_anidro_preco_real'):
                etanol_anidro.append(dados_reais[quinzena]['etanol_anidro_preco_real'])
            else:
                etanol_anidro.append(etanol_anidro[-1] * (1 + r_etanol_anidro))

            if dados_reais[quinzena].get('etanol_hidratado_preco_real'):
                etanol_hidratado.append(dados_reais[quinzena]['etanol_hidratado_preco_real'])
            else:
                etanol_hidratado.append(etanol_hidratado[-1] * (1 + r_etanol_hidratado))

            # Média ponderada para etanol geral (aproximação: 50% anidro, 50% hidratado)
            etanol.append((etanol_anidro[-1] + etanol_hidratado[-1]) / 2)
        else:
            # Verifica choques de preços apenas se não houver dados reais
            if choques_precos and quinzena in choques_precos:
                choque = choques_precos[quinzena]
                tipo = choque.get('tipo', '')
                magnitude = choque.get('magnitude', 0.0)

                if tipo == 'NY11':
                    ny11[-1] = ny11[-1] * (1 + magnitude / 100)
                    choques_aplicados.append(f"Q{quinzena}: NY11 {magnitude:+.1f}%")
                elif tipo == 'USD':
                    usd[-1] = usd[-1] * (1 + magnitude / 100)
                    choques_aplicados.append(f"Q{quinzena}: USD {magnitude:+.1f}%")

            # Aplica impacto da oferta no açúcar
            r_sugar_ajustado = r_sugar * fator_oferta
            drift = (fator_oferta - 1.0) * 0.12

            ny11.append(ny11[-1] * (1 + r_sugar_ajustado + drift))

            # Simula preços de etanol anidro e hidratado separadamente
            etanol_anidro.append(etanol_anidro[-1] * (1 + r_etanol_anidro))
            etanol_hidratado.append(etanol_hidratado[-1] * (1 + r_etanol_hidratado))

            # Média ponderada para etanol geral
            etanol.append((etanol_anidro[-1] + etanol_hidratado[-1]) / 2)
            usd.append(usd[-1] * (1 + r_usd))

    df_precos = pd.DataFrame({
        "Quinzena": np.arange(1, n_quinzenas + 1),
        "NY11_cents": ny11[1:],
        "Etanol_R$m3": etanol[1:],
        "Etanol_Anidro_R$m3": etanol_anidro[1:],
        "Etanol_Hidratado_R$m3": etanol_hidratado[1:],
        "USD_BRL": usd[1:],
    })

    # Adiciona colunas de preços reais de etanol se disponíveis (substitui valores simulados)
    if dados_reais:
        for quinzena in range(1, n_quinzenas + 1):
            if quinzena in dados_reais:
                idx = quinzena - 1
                if dados_reais[quinzena].get('etanol_anidro_preco_real'):
                    df_precos.loc[idx, "Etanol_Anidro_R$m3"] = dados_reais[quinzena]['etanol_anidro_preco_real']
                if dados_reais[quinzena].get('etanol_hidratado_preco_real'):
                    df_precos.loc[idx, "Etanol_Hidratado_R$m3"] = dados_reais[quinzena]['etanol_hidratado_preco_real']
                # Atualiza média se ambos estiverem disponíveis
                if dados_reais[quinzena].get('etanol_anidro_preco_real') and dados_reais[quinzena].get('etanol_hidratado_preco_real'):
                    df_precos.loc[idx, "Etanol_R$m3"] = (
                        dados_reais[quinzena]['etanol_anidro_preco_real'] +
                        dados_reais[quinzena]['etanol_hidratado_preco_real']
                    ) / 2

        # Adiciona colunas com nomes mais descritivos para compatibilidade
        df_precos["Etanol Anidro Preço (R$/m³)"] = df_precos["Etanol_Anidro_R$m3"]
        df_precos["Etanol Hidratado Preço (R$/m³)"] = df_precos["Etanol_Hidratado_R$m3"]

    return df_precos, direcao, fator_oferta, choques_aplicados


# ============================================================================
# INTERFACE
# ============================================================================

st.markdown("<h1 style='text-align: center; margin-bottom: 5px;'>Acompanhamento de Safra 📊</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="text-align: center; color: #666; font-size: 0.9em; margin-top: 0px; margin-bottom: 20px;">Desenvolvido por Rogério Guilherme Jr.</p>',
    unsafe_allow_html=True
)

# ============ SIDEBAR ============
st.sidebar.header("📊 Parâmetros da Safra")

# Inicializa parâmetros de simulação no session_state se não existirem
if 'simulacao_moagem' not in st.session_state:
    st.session_state.simulacao_moagem = 600_000_000
if 'simulacao_atr' not in st.session_state:
    st.session_state.simulacao_atr = 135.0
if 'simulacao_mix' not in st.session_state:
    st.session_state.simulacao_mix = 48.0
if 'simulacao_n_quinz' not in st.session_state:
    st.session_state.simulacao_n_quinz = 24
if 'simulacao_data_start' not in st.session_state:
    st.session_state.simulacao_data_start = date(date.today().year, 4, 1)

moagem = st.sidebar.number_input(
    "Moagem total estimada (ton)",
    value=st.session_state.simulacao_moagem,
    step=10_000_000,
    key="input_moagem"
)
atr = st.sidebar.number_input(
    "ATR médio estimado (kg/t)",
    value=st.session_state.simulacao_atr,
    step=1.0,
    format="%.1f",
    key="input_atr"
)
mix = st.sidebar.number_input(
    "Mix açúcar estimado (%)",
    value=st.session_state.simulacao_mix,
    step=1.0,
    format="%.1f",
    key="input_mix"
)

# Salva valores no session_state quando alterados
st.session_state.simulacao_moagem = moagem
st.session_state.simulacao_atr = atr
st.session_state.simulacao_mix = mix

st.sidebar.divider()

st.sidebar.subheader("⚙️ Simulação")
n_quinz = st.sidebar.number_input(
    "Nº de quinzenas",
    value=st.session_state.simulacao_n_quinz,
    min_value=4,
    max_value=24,
    step=1,
    key="input_n_quinz"
)
data_start = st.sidebar.date_input(
    "Início da safra",
    value=st.session_state.simulacao_data_start,
    key="input_data_start"
)

# Salva valores no session_state quando alterados
st.session_state.simulacao_n_quinz = n_quinz
st.session_state.simulacao_data_start = data_start

st.sidebar.divider()

st.sidebar.subheader("💰 Preços Iniciais")

# Expander para buscar preços reais
with st.sidebar.expander("🌐 Buscar Preços Reais", expanded=False):
    st.caption("💡 Busque preços reais do mercado para preencher automaticamente")

    data_busca = st.date_input(
        "Data de corte para buscar preços",
        value=date.today(),
        max_value=date.today(),
        key="data_busca_precos"
    )

    if st.button("💵 Buscar USD/BRL", use_container_width=True, key="btn_buscar_usd"):
        with st.spinner("Buscando dólar do BACEN..."):
            usd_buscado = buscar_dolar_bacen(data_busca)
            if usd_buscado:
                st.session_state['usd_buscado'] = usd_buscado
                st.session_state['usd_buscado_data'] = data_busca
                st.success(f"✅ USD/BRL encontrado: **{usd_buscado:.4f}**")
            else:
                st.error("❌ Não foi possível buscar o dólar")

    # Exibe valor encontrado se disponível
    if 'usd_buscado' in st.session_state:
        data_usd = st.session_state.get('usd_buscado_data', data_busca)
        st.info(f"💵 **USD/BRL encontrado:** {st.session_state['usd_buscado']:.4f} (Data: {data_usd.strftime('%d/%m/%Y')})")

# Usa valores buscados se disponíveis, senão usa valores padrão
usd_inicial_valor = st.session_state.get('usd_buscado', 4.90)

# Converte valores com segurança para float
usd_inicial_valor_safe = safe_float(usd_inicial_valor, 4.90)

ny11_inicial = st.sidebar.number_input("NY11 inicial (USc/lb)", value=14.90, step=0.10, format="%.2f", key="ny11_inicial_input")
usd_inicial = st.sidebar.number_input("USD/BRL inicial", value=usd_inicial_valor_safe, step=0.01, format="%.4f", key="usd_inicial_input")
etanol_inicial = st.sidebar.number_input("Etanol inicial (R$/m³)", value=2500.0, step=50.0, format="%.0f")

with st.sidebar.expander("🔧 Parâmetros Avançados", expanded=False):
    st.caption("⚙️ Ajustes finos da simulação (opcional)")
    preco_ref = st.number_input("Preço referência NY11 (USc/lb)", value=15.0, step=0.5, format="%.1f")
    sensibilidade = st.slider("Sensibilidade oferta → preço (%)", 0.0, 30.0, 10.0, 1.0)

# Inicializa dados reais no session_state (carrega de arquivo se existir)
if 'dados_reais' not in st.session_state:
    st.session_state.dados_reais = carregar_dados_reais()

# Inicializa choques de safra
if 'choques_safra' not in st.session_state:
    st.session_state.choques_safra = {}

# Inicializa choques de preços
if 'choques_precos' not in st.session_state:
    st.session_state.choques_precos = {}

# ============ INSERÇÃO DE DADOS REAIS ============
st.divider()
st.subheader("📥 Inserção de Dados Reais (Unica)")

st.caption("💡 Insira os dados acumulados conforme recebe da Unica. A projeção será ajustada automaticamente.")

# Seletor de quinzena para edição
quinzenas_com_dados = sorted([q for q in st.session_state.dados_reais.keys() if st.session_state.dados_reais[q].get('moagem_real')])
modo_edicao = False
quinzena_selecionada = "Nova quinzena"

if quinzenas_com_dados:
    col_sel1, col_sel2 = st.columns([3, 1])
    with col_sel1:
        quinzena_selecionada = st.selectbox(
            "📝 Selecionar quinzena para editar (ou deixe em 'Nova quinzena' para nova)",
            ["Nova quinzena"] + [f"Q{q}" for q in quinzenas_com_dados],
            key="select_quinzena_editar"
        )
    with col_sel2:
        if quinzena_selecionada and quinzena_selecionada != "Nova quinzena":
            quinzena_editar = int(quinzena_selecionada.replace("Q", ""))
            if st.button("🗑️ Remover", use_container_width=True, key="btn_remover_quinzena"):
                if quinzena_editar in st.session_state.dados_reais:
                    del st.session_state.dados_reais[quinzena_editar]
                    salvar_dados_reais(st.session_state.dados_reais)
                    st.success(f"✅ Quinzena {quinzena_editar} removida!")
                    st.rerun()

# Verifica se está em modo edição
if quinzena_selecionada and quinzena_selecionada != "Nova quinzena":
    modo_edicao = True
else:
    modo_edicao = False

# Preenche campos se estiver editando
if modo_edicao:
    quinzena_editar = int(quinzena_selecionada.replace("Q", ""))
    dados_editar = st.session_state.dados_reais.get(quinzena_editar, {})
    valor_default_quinzena = quinzena_editar
    valor_default_moagem = dados_editar.get('moagem_real', 0)
    valor_default_atr = dados_editar.get('atr_real', 0.0)
    valor_default_mix = dados_editar.get('mix_real', 0.0)
    valor_default_usd = dados_editar.get('usd_real', 0.0)
    valor_default_ny11 = dados_editar.get('ny11_real', 0.0)
    valor_default_etanol_anidro_preco = dados_editar.get('etanol_anidro_preco_real', 0.0)
    valor_default_etanol_hidratado_preco = dados_editar.get('etanol_hidratado_preco_real', 0.0)
    valor_default_etanol_anidro_cana = dados_editar.get('etanol_anidro_cana_real', 0.0)
    valor_default_etanol_hidratado_cana = dados_editar.get('etanol_hidratado_cana_real', 0.0)
    valor_default_etanol_anidro_milho = dados_editar.get('etanol_anidro_milho_real', 0.0)
    valor_default_etanol_hidratado_milho = dados_editar.get('etanol_hidratado_milho_real', 0.0)
    usar_etanol_manual_default = any([
        valor_default_etanol_anidro_cana > 0,
        valor_default_etanol_hidratado_cana > 0,
        valor_default_etanol_anidro_milho > 0,
        valor_default_etanol_hidratado_milho > 0
    ])
else:
    valor_default_quinzena = 1
    valor_default_moagem = 0
    valor_default_atr = 0.0
    valor_default_mix = 0.0
    valor_default_usd = 0.0
    valor_default_ny11 = 0.0
    valor_default_etanol_anidro_preco = 0.0
    valor_default_etanol_hidratado_preco = 0.0
    valor_default_etanol_anidro_cana = 0.0
    valor_default_etanol_hidratado_cana = 0.0
    valor_default_etanol_anidro_milho = 0.0
    valor_default_etanol_hidratado_milho = 0.0
    usar_etanol_manual_default = False

col1, col2, col3 = st.columns(3)
with col1:
    quinzena_inserir = st.number_input("Quinzena", min_value=1, max_value=int(n_quinz), value=valor_default_quinzena, step=1, disabled=modo_edicao)
with col2:
    moagem_real = st.number_input("Moagem acumulada (ton)", value=int(valor_default_moagem), step=1000, format="%d")
with col3:
    atr_real = st.number_input("ATR (kg/t)", value=valor_default_atr, step=0.1, format="%.1f")

col4, col5 = st.columns(2)
with col4:
    mix_real = st.number_input("Mix açúcar (%)", value=valor_default_mix, step=0.1, format="%.1f")
with col5:
    usar_etanol_manual = st.checkbox("Inserir etanol manualmente", value=usar_etanol_manual_default)

st.markdown("**💲 Preços no Fim da Quinzena:**")

# Busca de preços para dados reais
with st.expander("🌐 Buscar Preços Reais para esta Quinzena", expanded=False):
    st.caption("💡 Busque preços reais do mercado para preencher automaticamente")

    data_busca_real = st.date_input(
        "Data de corte para buscar preços",
        value=date.today(),
        max_value=date.today(),
        key="data_busca_precos_real"
    )

    if st.button("💵 Buscar USD/BRL", use_container_width=True, key="btn_buscar_usd_real"):
        with st.spinner("Buscando dólar do BACEN..."):
            usd_buscado_real = buscar_dolar_bacen(data_busca_real)
            if usd_buscado_real:
                st.session_state['usd_buscado_real'] = usd_buscado_real
                st.session_state['usd_buscado_real_data'] = data_busca_real
                st.success(f"✅ USD/BRL encontrado: **{usd_buscado_real:.4f}**")
                st.rerun()
            else:
                st.error("❌ Não foi possível buscar o dólar")

    # Exibe valor encontrado se disponível
    if 'usd_buscado_real' in st.session_state:
        data_usd_real = st.session_state.get('usd_buscado_real_data', data_busca_real)
        st.info(f"💵 **USD/BRL encontrado:** {st.session_state['usd_buscado_real']:.4f} (Data: {data_usd_real.strftime('%d/%m/%Y')})")

# Usa valores buscados se disponíveis, senão usa valores padrão
# Limpa após usar para não persistir
usd_real_valor = st.session_state.pop('usd_buscado_real', valor_default_usd)

# Converte valores com segurança para float
usd_real_valor_safe = safe_float(usd_real_valor, valor_default_usd)

col_preco1, col_preco2, col_preco3, col_preco4 = st.columns(4)
with col_preco1:
    usd_real = st.number_input("USD/BRL", value=usd_real_valor_safe, step=0.0001, format="%.4f", key="usd_real_input")
with col_preco2:
    ny11_real = st.number_input("NY11 (USc/lb)", value=safe_float(valor_default_ny11, 0.0), step=0.10, format="%.2f", key="ny11_real_input")
with col_preco3:
    etanol_anidro_preco_real = st.number_input("Etanol Anidro (R$/m³)", value=valor_default_etanol_anidro_preco, step=10.0, format="%.0f", key="etanol_anidro_preco")
with col_preco4:
    etanol_hidratado_preco_real = st.number_input("Etanol Hidratado (R$/m³)", value=valor_default_etanol_hidratado_preco, step=10.0, format="%.0f", key="etanol_hidratado_preco")

etanol_anidro_cana_real = None
etanol_hidratado_cana_real = None
etanol_anidro_milho_real = None
etanol_hidratado_milho_real = None

if usar_etanol_manual:
    st.markdown("**Dados de Etanol Acumulados (m³):**")
    col6, col7, col8, col9 = st.columns(4)
    with col6:
        etanol_anidro_cana_real = st.number_input("Anidro Cana Acumulado", value=valor_default_etanol_anidro_cana, step=100.0, format="%.0f")
    with col7:
        etanol_hidratado_cana_real = st.number_input("Hidratado Cana Acumulado", value=valor_default_etanol_hidratado_cana, step=100.0, format="%.0f")
    with col8:
        etanol_anidro_milho_real = st.number_input("Anidro Milho Acumulado", value=valor_default_etanol_anidro_milho, step=100.0, format="%.0f")
    with col9:
        etanol_hidratado_milho_real = st.number_input("Hidratado Milho Acumulado", value=valor_default_etanol_hidratado_milho, step=100.0, format="%.0f")

col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("➕ Adicionar/Atualizar Dados", use_container_width=True, type="primary"):
        if quinzena_inserir > 0:
            # Preserva dados existentes se a quinzena já existir
            dados_existentes = st.session_state.dados_reais.get(quinzena_inserir, {})
            
            # Atualiza apenas os campos fornecidos, preservando os existentes
            novos_dados = dados_existentes.copy()
            
            # Atualiza apenas se o valor for fornecido (> 0)
            if moagem_real > 0:
                novos_dados['moagem_real'] = moagem_real
            elif 'moagem_real' not in novos_dados:
                novos_dados['moagem_real'] = None
                
            if atr_real > 0:
                novos_dados['atr_real'] = atr_real
            elif 'atr_real' not in novos_dados:
                novos_dados['atr_real'] = None
                
            if mix_real > 0:
                novos_dados['mix_real'] = mix_real
            elif 'mix_real' not in novos_dados:
                novos_dados['mix_real'] = None
            
            if usar_etanol_manual:
                if etanol_anidro_cana_real and safe_float(etanol_anidro_cana_real, 0) > 0:
                    novos_dados['etanol_anidro_cana_real'] = etanol_anidro_cana_real
                elif 'etanol_anidro_cana_real' not in novos_dados:
                    novos_dados['etanol_anidro_cana_real'] = None
                    
                if etanol_hidratado_cana_real and safe_float(etanol_hidratado_cana_real, 0) > 0:
                    novos_dados['etanol_hidratado_cana_real'] = etanol_hidratado_cana_real
                elif 'etanol_hidratado_cana_real' not in novos_dados:
                    novos_dados['etanol_hidratado_cana_real'] = None
                    
                if etanol_anidro_milho_real and safe_float(etanol_anidro_milho_real, 0) > 0:
                    novos_dados['etanol_anidro_milho_real'] = etanol_anidro_milho_real
                elif 'etanol_anidro_milho_real' not in novos_dados:
                    novos_dados['etanol_anidro_milho_real'] = None
                    
                if etanol_hidratado_milho_real and safe_float(etanol_hidratado_milho_real, 0) > 0:
                    novos_dados['etanol_hidratado_milho_real'] = etanol_hidratado_milho_real
                elif 'etanol_hidratado_milho_real' not in novos_dados:
                    novos_dados['etanol_hidratado_milho_real'] = None
            
            if usd_real and safe_float(usd_real, 0) > 0:
                novos_dados['usd_real'] = usd_real
            elif 'usd_real' not in novos_dados:
                novos_dados['usd_real'] = None
                
            if ny11_real and safe_float(ny11_real, 0) > 0:
                novos_dados['ny11_real'] = ny11_real
            elif 'ny11_real' not in novos_dados:
                novos_dados['ny11_real'] = None
                
            if etanol_anidro_preco_real and safe_float(etanol_anidro_preco_real, 0) > 0:
                novos_dados['etanol_anidro_preco_real'] = etanol_anidro_preco_real
            elif 'etanol_anidro_preco_real' not in novos_dados:
                novos_dados['etanol_anidro_preco_real'] = None
                
            if etanol_hidratado_preco_real and safe_float(etanol_hidratado_preco_real, 0) > 0:
                novos_dados['etanol_hidratado_preco_real'] = etanol_hidratado_preco_real
            elif 'etanol_hidratado_preco_real' not in novos_dados:
                novos_dados['etanol_hidratado_preco_real'] = None
            
            # Atualiza os dados no session_state
            st.session_state.dados_reais[quinzena_inserir] = novos_dados
            
            # Salva automaticamente
            salvar_dados_reais(st.session_state.dados_reais)
            st.success(f"✅ Dados da Q{quinzena_inserir} adicionados/atualizados e salvos!")
            st.rerun()

with col_btn2:
    # Adiciona confirmação antes de limpar todos os dados
    if st.button("🗑️ Limpar Todos os Dados Reais", use_container_width=True):
        st.warning("⚠️ **ATENÇÃO:** Esta ação irá apagar TODOS os dados reais inseridos. Esta ação não pode ser desfeita!")
        if st.button("✅ Confirmar Limpeza", type="primary", key="confirmar_limpeza"):
            st.session_state.dados_reais = {}
            salvar_dados_reais(st.session_state.dados_reais)
            st.success("✅ Todos os dados reais foram removidos!")
            st.rerun()

# Lista dados reais inseridos
if st.session_state.dados_reais:
    st.markdown("**📋 Dados reais inseridos:**")
    for q in sorted(st.session_state.dados_reais.keys()):
        dados = st.session_state.dados_reais[q]
        info = f"Q{q}: "
        if dados.get('moagem_real'):
            info += f"Moagem: {fmt_br(dados['moagem_real'], 0)} ton"
        if dados.get('atr_real'):
            info += f" | ATR: {dados['atr_real']:.1f} kg/t"
        if dados.get('mix_real'):
            info += f" | Mix: {dados['mix_real']:.1f}%"
        if dados.get('ny11_real'):
            info += f" | NY11: {dados['ny11_real']:.2f} USc/lb"
        if dados.get('usd_real'):
            info += f" | USD: {dados['usd_real']:.2f}"
        st.caption(info)

# ============ CHOQUES DE SAFRA ============
st.sidebar.divider()
with st.sidebar.expander("🌾 Choques de Safra (Apenas Futuras)", expanded=False):
    st.caption("⚠️ Choques só podem ser aplicados em quinzenas sem dados reais")

    col_periodo1, col_periodo2 = st.columns(2)
    with col_periodo1:
        quinzena_inicio = st.number_input("Quinzena início", min_value=1, max_value=int(n_quinz),
                                         value=12, step=1, key="choque_inicio")
    with col_periodo2:
        quinzena_fim = st.number_input("Quinzena fim", min_value=1, max_value=int(n_quinz),
                                       value=12, step=1, key="choque_fim")

    periodo_valido = quinzena_fim >= quinzena_inicio

    # Verifica se há dados reais no período
    tem_dados_no_periodo = False
    if periodo_valido:
        for q in range(quinzena_inicio, quinzena_fim + 1):
            if q in st.session_state.dados_reais and st.session_state.dados_reais[q].get('moagem_real'):
                tem_dados_no_periodo = True
                break

    if tem_dados_no_periodo:
        st.warning("⚠️ Não é possível aplicar choques em quinzenas com dados reais!")

    tipo_choque = st.selectbox("Tipo de choque", ["Moagem", "ATR", "MIX"], key="tipo_choque")
    magnitude_choque = st.number_input("Magnitude (%)", min_value=-50.0, max_value=50.0,
                                      value=0.0, step=1.0, format="%.1f", key="magnitude_choque")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Aplicar", use_container_width=True,
                    disabled=not periodo_valido or tem_dados_no_periodo or magnitude_choque == 0,
                    key="btn_aplicar_choque"):
            novo_choque = {
                'tipo': tipo_choque,
                'magnitude': magnitude_choque
            }
            for q in range(quinzena_inicio, quinzena_fim + 1):
                # Só aplica se não houver dados reais
                if q not in st.session_state.dados_reais or not st.session_state.dados_reais[q].get('moagem_real'):
                    if q not in st.session_state.choques_safra:
                        st.session_state.choques_safra[q] = []
                    elif not isinstance(st.session_state.choques_safra[q], list):
                        st.session_state.choques_safra[q] = [st.session_state.choques_safra[q]]
                    st.session_state.choques_safra[q].append(novo_choque.copy())
            st.rerun()

    with col_btn2:
        if st.button("🗑️ Remover Todos", use_container_width=True, key="btn_remover_choques"):
            st.session_state.choques_safra = {}
            st.rerun()

# ============ CHOQUES DE PREÇOS ============
st.sidebar.divider()
with st.sidebar.expander("⚡ Choques de Preços", expanded=False):
    st.caption("Simule eventos que afetam PREÇOS (NY11, USD)")

    col_periodo1, col_periodo2 = st.columns(2)
    with col_periodo1:
        quinzena_inicio_preco = st.number_input("Quinzena início", min_value=1, max_value=int(n_quinz),
                                              value=12, step=1, key="choque_preco_inicio")
    with col_periodo2:
        quinzena_fim_preco = st.number_input("Quinzena fim", min_value=1, max_value=int(n_quinz),
                                            value=12, step=1, key="choque_preco_fim")

    periodo_valido_preco = quinzena_fim_preco >= quinzena_inicio_preco
    if not periodo_valido_preco:
        st.warning("⚠️ Quinzena fim deve ser >= quinzena início")

    tipo_choque_preco = st.selectbox("Tipo de choque", ["NY11", "USD"], key="tipo_choque_preco")
    magnitude_choque_preco = st.number_input("Magnitude (%)", min_value=-50.0, max_value=50.0,
                                             value=0.0, step=1.0, format="%.1f", key="magnitude_choque_preco")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Aplicar", use_container_width=True,
                    disabled=not periodo_valido_preco or magnitude_choque_preco == 0,
                    key="btn_aplicar_choque_preco"):
            for q in range(quinzena_inicio_preco, quinzena_fim_preco + 1):
                st.session_state.choques_precos[q] = {
                    'tipo': tipo_choque_preco,
                    'magnitude': magnitude_choque_preco
                }
            st.rerun()

    with col_btn2:
        if st.button("🗑️ Remover Todos", use_container_width=True, key="btn_remover_choques_precos"):
            st.session_state.choques_precos = {}
            st.rerun()

    # Lista choques ativos
    if st.session_state.choques_precos:
        st.write("**Choques ativos:**")
        for q in sorted(st.session_state.choques_precos.keys()):
            choque = st.session_state.choques_precos[q]
            mag = choque['magnitude']
            if mag > 0:
                st.success(f"Q{q}: {choque['tipo']} **+{mag:.1f}%**")
            elif mag < 0:
                st.error(f"Q{q}: {choque['tipo']} **{mag:.1f}%**")
            else:
                st.write(f"Q{q}: {choque['tipo']} {mag:.1f}%")

# ============ CÁLCULOS ============
# NOTA: Os preços iniciais (ny11_inicial, usd_inicial, etanol_inicial) são usados como
# ponto de partida para a simulação. Quando você altera os parâmetros de safra (moagem, ATR, mix),
# a produção muda e isso afeta a trajetória dos preços simulados, mas os preços iniciais
# permanecem como você definiu na sidebar.

df_projecao = gerar_projecao_quinzenal(
    moagem, atr, mix, int(n_quinz), data_start,
    st.session_state.dados_reais if st.session_state.dados_reais else None,
    st.session_state.choques_safra if st.session_state.choques_safra else None,
    seed=42,
    usar_volatilidade_etanol=True  # Ativa simulação com volatilidade
)

# Simula preços
# Os preços iniciais são usados aqui e a produção calculada afeta a trajetória dos preços
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

# Calcula totais
acucar_total = df_completo["Açúcar (t)"].sum()
etanol_total = df_completo["Etanol Total (m³)"].sum()
etanol_anidro_cana_total = df_completo["Etanol Anidro Cana (m³)"].sum()
etanol_hidratado_cana_total = df_completo["Etanol Hidratado Cana (m³)"].sum()
etanol_anidro_milho_total = df_completo["Etanol Anidro Milho (m³)"].sum()
etanol_hidratado_milho_total = df_completo["Etanol Hidratado Milho (m³)"].sum()
etanol_total_acum = df_completo["Etanol Total Acumulado (m³)"].iloc[-1] if len(df_completo) > 0 else 0

ny11_final = df_precos.iloc[-1]["NY11_cents"]
usd_final = df_precos.iloc[-1]["USD_BRL"]
preco_brl_t_final = ny11_para_brl(ny11_final, usd_final)
preco_saca_final = preco_brl_t_final / 20
variacao_ny11 = ny11_final - ny11_inicial
variacao_pct = (variacao_ny11 / ny11_inicial) * 100 if ny11_inicial > 0 else 0

# ============ EXIBIÇÃO ============
st.divider()
st.subheader("📈 Resultados da Projeção")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Açúcar estimado", fmt_br(acucar_total, 0) + " t")
col2.metric("Etanol total estimado", fmt_br(etanol_total, 0) + " m³")
col3.metric("Preço final NY11", f"{ny11_final:.2f} USc/lb",
           delta=f"{variacao_ny11:+.2f} ({variacao_pct:+.2f}%)",
           delta_color="inverse" if variacao_ny11 < 0 else "normal")
col4.metric("Preço final (R$/saca)", fmt_br(preco_saca_final, 2))

st.write("")
col5, col6, col7, col8 = st.columns(4)
col5.metric("Etanol Anidro Cana", fmt_br(etanol_anidro_cana_total, 0) + " m³")
col6.metric("Etanol Hidratado Cana", fmt_br(etanol_hidratado_cana_total, 0) + " m³")
col7.metric("Etanol Anidro Milho", fmt_br(etanol_anidro_milho_total, 0) + " m³")
col8.metric("Etanol Hidratado Milho", fmt_br(etanol_hidratado_milho_total, 0) + " m³")

st.write("")
col9, col10 = st.columns(2)
col9.metric("Etanol Total Acumulado", fmt_br(etanol_total_acum, 0) + " m³")
col10.metric("USD/BRL final", f"{usd_final:.2f}",
           delta=f"{usd_final - usd_inicial:+.2f}",
           delta_color="inverse" if (usd_final - usd_inicial) < 0 else "normal")

st.divider()
st.subheader("📅 Evolução Quinzenal")

# Formata DataFrame para exibição
df_mostrar = df_completo.copy()
colunas_formatacao = {
    "Moagem": (0, fmt_br),
    "Moagem Acumulada (ton)": (0, fmt_br),
    "ATR": (2, fmt_br),
    "MIX": (2, fmt_br),
    "Açúcar (t)": (0, fmt_br),
    "Açúcar Acumulado (t)": (0, fmt_br),
    "Etanol Total (m³)": (0, fmt_br),
    "Etanol Acumulado (m³)": (0, fmt_br),
    "Etanol Anidro Cana (m³)": (0, fmt_br),
    "Etanol Anidro Cana Acumulado (m³)": (0, fmt_br),
    "Etanol Hidratado Cana (m³)": (0, fmt_br),
    "Etanol Hidratado Cana Acumulado (m³)": (0, fmt_br),
    "Etanol Anidro Milho (m³)": (0, fmt_br),
    "Etanol Anidro Milho Acumulado (m³)": (0, fmt_br),
    "Etanol Hidratado Milho (m³)": (0, fmt_br),
    "Etanol Hidratado Milho Acumulado (m³)": (0, fmt_br),
    "Etanol Total Quinzena (m³)": (0, fmt_br),
    "Etanol Total Acumulado (m³)": (0, fmt_br),
    "NY11_cents": (2, lambda x: f"{x:.2f}"),
    "Etanol_R$m3": (0, fmt_br),
    "USD_BRL": (2, lambda x: f"{x:.2f}"),
    "Etanol Anidro Preço (R$/m³)": (0, lambda x: fmt_br(x, 0) if x is not None and not pd.isna(x) else ""),
    "Etanol Hidratado Preço (R$/m³)": (0, lambda x: fmt_br(x, 0) if x is not None and not pd.isna(x) else ""),
    "Moagem Proj. Original": (0, fmt_br),
    "ATR Proj. Original": (2, fmt_br),
    "MIX Proj. Original": (2, fmt_br),
    "Moagem Baseline": (0, fmt_br),
    "ATR Baseline": (2, fmt_br),
    "MIX Baseline": (2, fmt_br),
    "Açúcar Baseline (t)": (0, fmt_br),
    "Etanol Baseline (m³)": (0, fmt_br)
}

for coluna, (casas, func) in colunas_formatacao.items():
    if coluna in df_mostrar.columns:
        df_mostrar[coluna] = df_mostrar[coluna].apply(func)

# Remove coluna interna
df_mostrar_display = df_mostrar.drop(columns=["Tem Dados Reais"])

# Destaca linhas com dados reais
def highlight_real_data(row):
    if row.get("Tem Dados Reais", False):
        return ['background-color: #e8f5e9'] * len(row)
    return [''] * len(row)

# Seleciona colunas para exibição (organizadas)
colunas_exibir = [
    "Quinzena", "Data",
    "Moagem", "Moagem Acumulada (ton)", "ATR", "MIX",
    "Moagem Baseline", "ATR Baseline", "MIX Baseline",
    "Moagem Proj. Original", "ATR Proj. Original", "MIX Proj. Original",
    "Açúcar (t)", "Açúcar Acumulado (t)", "Açúcar Baseline (t)",
    "Etanol Total (m³)", "Etanol Acumulado (m³)", "Etanol Baseline (m³)",
    "Etanol Anidro Cana (m³)", "Etanol Anidro Cana Acumulado (m³)",
    "Etanol Hidratado Cana (m³)", "Etanol Hidratado Cana Acumulado (m³)",
    "Etanol Anidro Milho (m³)", "Etanol Anidro Milho Acumulado (m³)",
    "Etanol Hidratado Milho (m³)", "Etanol Hidratado Milho Acumulado (m³)",
    "Etanol Total Quinzena (m³)", "Etanol Total Acumulado (m³)",
    "NY11_cents", "Etanol_R$m3", "USD_BRL"
]

# Adiciona colunas de preços de etanol se existirem
if "Etanol Anidro Preço (R$/m³)" in df_mostrar_display.columns:
    colunas_exibir.extend(["Etanol Anidro Preço (R$/m³)", "Etanol Hidratado Preço (R$/m³)"])

# Filtra apenas colunas que existem no DataFrame
colunas_exibir = [col for col in colunas_exibir if col in df_mostrar_display.columns]

st.dataframe(
    df_mostrar_display[colunas_exibir],
    use_container_width=True,
    height=400,
    hide_index=True
)

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
    
    💡 *A projeção é ajustada automaticamente baseada nos dados reais inseridos. Choques só podem ser aplicados em quinzenas futuras (sem dados reais).*
    """
)

