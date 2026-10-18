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


# ---------------- Formatação brasileira ----------------

def formatar_numero(valor, casas=0):
    """1234.5 -> '1.234,5' (troca ponto e vírgula do formato americano)."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_reais(valor):
    return "R$ " + formatar_numero(valor, 2)


def formatar_percentual(valor):
    return formatar_numero(valor * 100, 1) + "%"


# ---------------- Indicadores (SDD seção 3) ----------------

# Recebidos: OS que entraram no período
recebidos = len(filtrado)

# Entregues: status Entregue e data de entrega dentro do período
entregues = base[
    (base["status"] == "Entregue")
    & (base["data_entrega"] >= inicio)
    & (base["data_entrega"] <= fim)
]
qtd_entregues = len(entregues)

# Em andamento: situação de hoje (não depende do período)
em_andamento = base["status"].isin(["Em andamento", "Aguardando peça"]).sum()

# Tempo médio de reparo: dias entre entrada e conclusão
tempo_medio = filtrado["dias_reparo"].mean()

# Taxa de conclusão: concluídas ÷ recebidas, sem contar as em andamento
concluidas = filtrado["status"].isin(["Pronto", "Entregue"]).sum()
sem_andamento = (~filtrado["status"].isin(["Em andamento", "Aguardando peça"])).sum()
taxa_conclusao = concluidas / sem_andamento if sem_andamento > 0 else 0

# Taxa de retorno: voltaram na garantia ÷ entregues
retornos = (entregues["retorno_garantia"] == "Sim").sum()
taxa_retorno = retornos / qtd_entregues if qtd_entregues > 0 else 0

# Receita e ticket médio (só OS entregues)
receita = entregues["valor"].sum()
ticket_medio = receita / qtd_entregues if qtd_entregues > 0 else 0


# ---------------- Cartões ----------------

linha1 = st.columns(4)
linha1[0].metric("Aparelhos recebidos", formatar_numero(recebidos))
linha1[1].metric("Aparelhos entregues", formatar_numero(qtd_entregues))
linha1[2].metric("Em andamento (hoje)", formatar_numero(em_andamento))
linha1[3].metric("Tempo médio de reparo",
                 formatar_numero(tempo_medio, 1) + " dias" if pd.notna(tempo_medio) else "-")

linha2 = st.columns(4)
linha2[0].metric("Taxa de conclusão", formatar_percentual(taxa_conclusao))
linha2[1].metric("Taxa de retorno", formatar_percentual(taxa_retorno))
linha2[2].metric("Receita total", formatar_reais(receita))
linha2[3].metric("Ticket médio", formatar_reais(ticket_medio))


# ---------------- Abas ----------------

aba_geral, aba_servicos, aba_qualidade, aba_financeiro, aba_dados = st.tabs(
    ["Visão geral", "Serviços", "Qualidade", "Financeiro", "Dados"]
)
