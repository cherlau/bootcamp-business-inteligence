# Painel de BI da assistência técnica de celulares.
# Para rodar: streamlit run app.py

import pandas as pd
import plotly.express as px
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


# ---------------- Aba: Visão geral ----------------

with aba_geral:
    # Recebidos contam pelo mês de entrada; entregues pelo mês de entrega
    recebidos_mes = filtrado.groupby("mes").size().rename("Recebidos")
    entregues_mes = entregues.groupby(entregues["data_entrega"].dt.strftime("%Y-%m")).size().rename("Entregues")
    volume = pd.concat([recebidos_mes, entregues_mes], axis=1).fillna(0).reset_index(names="mes")

    fig = px.line(volume, x="mes", y=["Recebidos", "Entregues"], markers=True,
                  title="Aparelhos recebidos × entregues por mês")
    fig.update_layout(xaxis_title="Mês", yaxis_title="Aparelhos", legend_title="")
    st.plotly_chart(fig, width="stretch")

    # ---------- Insights (calculados com os dados filtrados) ----------
    st.subheader("💡 Insights")
    insights = []
    MINIMO_OS = 30  # com poucas OS as conclusões não fazem sentido

    if qtd_entregues >= MINIMO_OS:
        # 1. Serviço que mais traz receita
        receita_por_tipo = entregues.groupby("tipo_reparo")["valor"].sum()
        maior_tipo = receita_por_tipo.idxmax()
        parte = receita_por_tipo.max() / receita
        insights.append(
            f"**{maior_tipo}** representa **{formatar_percentual(parte)}** da receita "
            f"→ manter estoque de peças para os modelos mais comuns."
        )

        # 2. Defeito que mais volta na garantia, comparado com a média
        retorno_defeito = entregues.groupby("defeito")["retorno_garantia"].apply(lambda s: (s == "Sim").mean())
        pior_defeito = retorno_defeito.idxmax()
        if taxa_retorno > 0:
            vezes = retorno_defeito.max() / taxa_retorno
            insights.append(
                f"**{pior_defeito}** volta na garantia em **{formatar_percentual(retorno_defeito.max())}** "
                f"dos casos, **{formatar_numero(vezes, 1)}×** a média "
                f"→ revisar o procedimento ou reduzir o prazo de garantia desse serviço."
            )

        # 3. Técnico com mais retornos, comparado com os outros técnicos
        com_tecnico = entregues[entregues["tecnico"] != "Não informado"]
        retorno_tecnico = com_tecnico.groupby("tecnico")["retorno_garantia"].apply(lambda s: (s == "Sim").mean())
        if len(retorno_tecnico) > 1:
            pior_tecnico = retorno_tecnico.idxmax()
            outros = com_tecnico[com_tecnico["tecnico"] != pior_tecnico]
            taxa_outros = (outros["retorno_garantia"] == "Sim").mean()
            if taxa_outros > 0:
                insights.append(
                    f"O técnico **{pior_tecnico}** tem **{formatar_percentual(retorno_tecnico.max())}** de retorno, "
                    f"**{formatar_numero(retorno_tecnico.max() / taxa_outros, 1)}×** a taxa dos demais técnicos "
                    f"→ acompanhamento e treinamento."
                )

    if recebidos >= MINIMO_OS:
        # 4. Mês com mais entradas
        MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                 "agosto", "setembro", "outubro", "novembro", "dezembro"]
        por_mes = filtrado.groupby("mes").size()
        mes_pico = por_mes.idxmax()
        ano, mes = mes_pico.split("-")
        insights.append(
            f"**{MESES[int(mes) - 1].capitalize()}/{ano}** foi o mês com mais entradas "
            f"(**{formatar_numero(por_mes.max())}** aparelhos, média de {formatar_numero(por_mes.mean())} por mês) "
            f"→ reforçar a equipe nessa época."
        )

        # 5. Serviço mais demorado
        tempo_tipo = filtrado.groupby("tipo_reparo")["dias_reparo"].mean()
        if tempo_tipo.notna().any():
            insights.append(
                f"**{tempo_tipo.idxmax()}** é o serviço mais demorado (**{formatar_numero(tempo_tipo.max(), 1)} dias** "
                f"em média, contra {formatar_numero(tempo_medio, 1)} no geral) "
                f"→ avisar o cliente do prazo e manter peças em estoque."
            )

    if insights:
        for frase in insights:
            st.markdown("- " + frase)
    else:
        st.info(f"São necessárias pelo menos {MINIMO_OS} OS no filtro atual para gerar insights.")


# ---------------- Aba: Serviços ----------------

with aba_servicos:
    col1, col2 = st.columns(2)

    # Serviços em andamento hoje, por status
    andamento = base[base["status"].isin(["Em andamento", "Aguardando peça"])]
    por_status = andamento["status"].value_counts().reset_index()
    por_status.columns = ["status", "quantidade"]
    fig = px.bar(por_status, x="status", y="quantidade", text="quantidade",
                 title="Serviços em andamento por status")
    fig.update_layout(xaxis_title="", yaxis_title="Aparelhos")
    col1.plotly_chart(fig, width="stretch")

    # Tempo médio de reparo por tipo de serviço
    tempo = filtrado.groupby("tipo_reparo")["dias_reparo"].mean().round(1).sort_values().reset_index()
    tempo["texto"] = tempo["dias_reparo"].apply(lambda d: formatar_numero(d, 1))
    fig = px.bar(tempo, x="dias_reparo", y="tipo_reparo", orientation="h", text="texto",
                 title="Tempo médio de reparo por tipo de serviço (dias)")
    fig.update_layout(xaxis_title="Dias", yaxis_title="")
    col2.plotly_chart(fig, width="stretch")


# ---------------- Aba: Qualidade ----------------

def grafico_retorno(coluna, titulo):
    """Barras com a taxa de retorno por grupo e uma linha tracejada na média geral."""
    taxa = entregues.groupby(coluna)["retorno_garantia"].apply(lambda s: (s == "Sim").mean() * 100)
    taxa = taxa.round(1).sort_values(ascending=False).reset_index(name="taxa")
    taxa["texto"] = taxa["taxa"].apply(lambda t: formatar_numero(t, 1) + "%")

    fig = px.bar(taxa, x=coluna, y="taxa", text="texto", title=titulo)
    fig.add_hline(y=taxa_retorno * 100, line_dash="dash", line_color="red",
                  annotation_text="Média geral: " + formatar_percentual(taxa_retorno))
    fig.update_layout(xaxis_title="", yaxis_title="% de retorno")
    return fig


with aba_qualidade:
    # Defeitos mais frequentes
    defeitos = filtrado["defeito"].value_counts().sort_values().reset_index()
    defeitos.columns = ["defeito", "quantidade"]
    fig = px.bar(defeitos, x="quantidade", y="defeito", orientation="h", text="quantidade",
                 title="Defeitos mais frequentes")
    fig.update_layout(xaxis_title="Aparelhos", yaxis_title="")
    st.plotly_chart(fig, width="stretch")

    col1, col2 = st.columns(2)
    col1.plotly_chart(grafico_retorno("defeito", "Taxa de retorno por defeito"), width="stretch")
    col2.plotly_chart(grafico_retorno("tecnico", "Taxa de retorno por técnico"), width="stretch")


# ---------------- Aba: Financeiro ----------------

with aba_financeiro:
    col1, col2 = st.columns(2)

    # Receita por tipo de reparo (OS entregues)
    receita_tipo = entregues.groupby("tipo_reparo")["valor"].sum().sort_values().reset_index()
    receita_tipo["texto"] = receita_tipo["valor"].apply(formatar_reais)
    fig = px.bar(receita_tipo, x="valor", y="tipo_reparo", orientation="h", text="texto",
                 title="Receita por tipo de reparo")
    fig.update_layout(xaxis_title="Receita (R$)", yaxis_title="")
    col1.plotly_chart(fig, width="stretch")

    # Receita por mês (pelo mês de entrega)
    receita_mes = entregues.groupby(entregues["data_entrega"].dt.strftime("%Y-%m"))["valor"].sum()
    receita_mes = receita_mes.rename_axis("mes").reset_index()
    fig = px.line(receita_mes, x="mes", y="valor", markers=True, title="Receita por mês")
    fig.update_layout(xaxis_title="Mês", yaxis_title="Receita (R$)")
    col2.plotly_chart(fig, width="stretch")


# ---------------- Aba: Dados ----------------

with aba_dados:
    st.write(f"{formatar_numero(len(filtrado))} ordens de serviço no filtro atual.")
    st.dataframe(filtrado, hide_index=True)

    # Botão para baixar as OS filtradas em CSV
    csv = filtrado.to_csv(sep=";", index=False).encode("utf-8-sig")
    st.download_button("Baixar CSV", data=csv, file_name="ordens_servico_filtradas.csv", mime="text/csv")
