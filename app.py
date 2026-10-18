# Painel de BI da assistência técnica de celulares.
# Para rodar: streamlit run app.py

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Painel da Assistência", layout="wide")
st.title("📱 Painel da Assistência Técnica")


# ---------------- Carregar os dados ----------------

@st.cache_data
def carregar_dados():
    """Lê a base limpa convertendo as colunas de data."""
    return pd.read_csv(
        "dados/ordens_servico_limpo.csv",
        sep=";",
        parse_dates=["data_entrada", "data_conclusao", "data_entrega"],
    )


df = carregar_dados()


# ---------------- Filtros na barra lateral ----------------

st.sidebar.header("Filtros")

data_min = df["data_entrada"].min().date()
data_max = df["data_entrada"].max().date()
periodo = st.sidebar.date_input(
    "Período (data de entrada)",
    value=(data_min, data_max),
    min_value=data_min,
    max_value=data_max,
    format="DD/MM/YYYY",
)
# Enquanto o usuário escolhe só a primeira data, usa ela como início e fim
if len(periodo) == 2:
    inicio, fim = periodo
else:
    inicio = fim = periodo[0]

marcas = st.sidebar.multiselect("Marca", sorted(df["marca"].unique()), placeholder="Todas")
tecnicos = st.sidebar.multiselect("Técnico", sorted(df["tecnico"].unique()), placeholder="Todos")

st.sidebar.caption("Dados simulados com base em informações da empresa.")

# Aplica marca e técnico (lista vazia = todos)
base = df.copy()
if marcas:
    base = base[base["marca"].isin(marcas)]
if tecnicos:
    base = base[base["tecnico"].isin(tecnicos)]

# Aplica o período pela data de entrada
inicio = pd.Timestamp(inicio)
fim = pd.Timestamp(fim)
filtrado = base[(base["data_entrada"] >= inicio) & (base["data_entrada"] <= fim)]


# ---------------- Abas ----------------

aba_geral, aba_servicos, aba_qualidade, aba_financeiro, aba_dados = st.tabs(
    ["Visão geral", "Serviços", "Qualidade", "Financeiro", "Dados"]
)
