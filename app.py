import streamlit as st
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta
import locale

locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--headless')  # Modo headless
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

# Função para calcular o último dia útil (dia anterior, ajustando para sexta se necessário)
def calcular_data_util():
    hoje = datetime.now()
    dia_anterior = hoje - timedelta(days=1)

    if dia_anterior.weekday() == 5:  # Sábado
        dia_anterior -= timedelta(days=1)
    elif dia_anterior.weekday() == 6:  # Domingo
        dia_anterior -= timedelta(days=2)

    return dia_anterior

# Função para fazer a requisição e atualizar o DataFrame com dados reais
def atualizar_ntnb():
    # Obter a data formatada para a URL
    data_util = calcular_data_util()
    data_formatada = data_util.strftime("%d%b%Y").lower()

    # Montar a URL com a data ajustada
    ntnb_url = f'https://www.anbima.com.br/informacoes/merc-sec/resultados/msec_{data_formatada}_ntn-b.asp'

    # Configurando o WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    # Acessar a página e extrair os dados
    driver.get(ntnb_url)
    local = '/html/body/table/tbody/tr/td/div/table[2]'

    # Pegar o elemento da tabela
    elemento = driver.find_element('xpath', local)
    html = elemento.get_attribute('outerHTML')
    
    # Ler a tabela usando pandas
    tabela = pd.read_html(str(html), thousands='.', decimal=',')
    
    # Combinar os DataFrames (se houver mais de um) em um único
    df_combined = pd.concat(tabela)

    # Transformar os dados em um array e reorganizar
    tabela_array = df_combined.to_numpy()
    tabela_2d = tabela_array.reshape(-1, tabela_array.shape[-1])

    ntnb = pd.DataFrame(tabela_2d)

    # Limpar o DataFrame, mantendo apenas as colunas e linhas necessárias
    ntnb.drop(ntnb.columns[[0, 1, 3, 4, 6, 7, 8, 9, 10]], axis=1, inplace=True)
    ntnb.drop([0, 1, 2, 3, 4], inplace=True)

    # Renomear as colunas
    ntnb.rename(columns={2: 'Data Vencimento', 5: 'Tx. NTN-B Indicativa'}, inplace=True)

    # Ajustar a coluna 'Data Vencimento' para o formato correto e configurá-la como índice
    ntnb['Data Vencimento'] = pd.to_datetime(ntnb['Data Vencimento'])
    ntnb.set_index('Data Vencimento', inplace=True)

    return ntnb

# Função para calcular a tabela com base nas entradas
def calcular_tabela(ntnb_ref, spread, taxa_nominal):
    # Converter ntnb_ref para float, caso ainda seja uma string
    ntnb_ref = float(ntnb_ref)

    # Coluna Reserva (valores fixos conforme sua tabela)
    reserva = np.array([0.00, -0.0005, -0.0010, -0.0015, -0.0020, -0.0025, -0.0030, -0.0035, -0.0040, -0.0045, -0.0050,
                        -0.0055, -0.0060, -0.0065, -0.0070, -0.0075, -0.0080, -0.0085, -0.0090, -0.0095, -0.0100])
    
    # Cálculo da coluna Teto NTN-B (ajustado para somar corretamente)
    teto_ntnb = (1 + ntnb_ref/100) * (1 + spread/100) - 1
    teto_ntnb_col = [(teto_ntnb + r) * 100 for r in reserva]
    
    # Cálculo da coluna Teto Nominal
    teto_nominal_col = [taxa_nominal + r*100 for r in reserva]
    
    # Montar o DataFrame, converter reserva para percentual
    df_tabela = pd.DataFrame({
        'Reserva': [f'{r*100:.2f}%' for r in reserva],  # Mostrar reserva como percentuais pequenos (4 casas decimais)
        'Teto NTN-B': [f'{v:.2f}%' for v in teto_ntnb_col],
        'Teto Nominal': [f'{v:.2f}%' for v in teto_nominal_col]
    })
    
    return df_tabela

# Interface do Streamlit
st.sidebar.title("Calculadora NTN-B")

# Aplicando custom CSS
st.markdown(
    """
    <style>
    /* Estilo para o fundo da Sidebar */
    [data-testid="stSidebar"] {
        background-color: #000000;
    }
    /* Texto branco na Sidebar */
    [data-testid="stSidebar"] .css-1v3fvcr, [data-testid="stSidebar"] .css-1cpxqw2, [data-testid="stSidebar"] .css-1t8afax {
        color: #FFFFFF;
    }
    /* Centralizar título e alterá-lo para 'Taxa Teto Prevalecida' */
    h2 {
        text-align: center;
        color: #000;
    }
    /* Estilo para a tabela */
    thead tr th {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border: 1px solid black !important;
    }
    tbody tr td {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border: 1px solid black !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Botão para atualizar a requisição
if st.sidebar.button('Atualizar'):
    ntnb = atualizar_ntnb()
    st.success("Dados atualizados com sucesso!")
else:
    ntnb = atualizar_ntnb()  # Dados iniciais

# Seleção de Data
data_selecionada = st.sidebar.selectbox('Escolher Data', ntnb.index.strftime('%d/%m/%Y'))
ntnb_ref = ntnb.loc[pd.to_datetime(data_selecionada, format='%d/%m/%Y'), 'Tx. NTN-B Indicativa']

# Converter ntnb_ref para float (caso ainda seja string)
ntnb_ref = float(ntnb_ref)

# Mostrar a taxa NTN-B da data selecionada no Sidebar
st.sidebar.write(f"NTNB REF para {data_selecionada}: {ntnb_ref:.2f}%")

# Input para Spread e Taxa Nominal
spread = st.sidebar.number_input('Spread', min_value=0.0, max_value=10.0, value=1.25, step=0.01)
taxa_nominal = st.sidebar.number_input('Taxa Nominal', min_value=0.0, max_value=15.0, value=7.0, step=0.01)

# Gerar a tabela conforme os cálculos descritos
df_tabela = calcular_tabela(ntnb_ref, spread, taxa_nominal)

# Alterar o título da tabela para 'Taxa Teto Prevalecida'
st.write("## Taxa Teto Prevalecida")

# Exibir a tabela calculada sem o índice
st.dataframe(df_tabela, use_container_width=True)
