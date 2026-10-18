# Painel de BI da assistência técnica de celulares.
# Para rodar: streamlit run app.py

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Painel da Assistência", layout="wide")
st.title("Painel da Assistência Técnica")
st.caption("Opção Telefonia Celular · Bauru (SP)")

# Visual dos gráficos: fundo branco e tons de azul, como em ferramentas de BI
CORES = ["#1F4E79", "#4A90C2", "#9CC3E4", "#F2A541", "#6C757D", "#2E8B57"]
px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = CORES

EM_ANDAMENTO = ["Em andamento", "Aguardando peça"]
DIAS_ESQUECIDO = 30  # aparelho pronto há mais de 30 dias sem o cliente buscar
MINIMO_OS = 30       # com poucas OS as conclusões dos insights não fazem sentido
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def mostrar_grafico(fig, onde=st):
    """Mostra o gráfico dentro de um cartão com borda."""
    with onde.container(border=True):
        st.plotly_chart(fig, width="stretch")


# ---------------- Carregar os dados ----------------

@st.cache_data
def carregar_dados():
    """Lê a base limpa convertendo as colunas de data."""
    df = pd.read_csv(
        "dados/ordens_servico_limpo.csv",
        sep=";",
        parse_dates=["data_entrada", "data_conclusao", "data_entrega"],
    )
    # Cliente que voltou: já tinha outra OS antes desta
    df = df.sort_values(["data_entrada", "os_id"])
    df["cliente_voltou"] = df.groupby("cliente_id").cumcount() > 0
    return df


df = carregar_dados()
HOJE = df["data_entrada"].max()  # "data de hoje" da base


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

# A lista de modelos mostra só os modelos das marcas escolhidas
opcoes_modelo = df[df["marca"].isin(marcas)] if marcas else df
modelos_escolhidos = st.sidebar.multiselect(
    "Modelo", sorted(opcoes_modelo["modelo"].unique()), placeholder="Todos (digite para buscar)"
)
tecnicos = st.sidebar.multiselect("Técnico", sorted(df["tecnico"].unique()), placeholder="Todos")

st.sidebar.caption("Dados simulados com base em informações da empresa.")

# Aplica marca, modelo e técnico (lista vazia = todos)
base = df.copy()
if marcas:
    base = base[base["marca"].isin(marcas)]
if modelos_escolhidos:
    base = base[base["modelo"].isin(modelos_escolhidos)]
if tecnicos:
    base = base[base["tecnico"].isin(tecnicos)]

inicio = pd.Timestamp(inicio)
fim = pd.Timestamp(fim)


# ---------------- Formatação brasileira ----------------

def formatar_numero(valor, casas=0):
    """1234.5 -> '1.234,5' (troca ponto e vírgula do formato americano)."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_reais(valor):
    return "R$ " + formatar_numero(valor, 2)


def formatar_percentual(valor):
    return formatar_numero(valor * 100, 1) + "%"


def nome_mes(texto_mes):
    """'2026-03' -> 'março/2026'."""
    ano, mes = texto_mes.split("-")
    return f"{MESES[int(mes) - 1]}/{ano}"


# ---------------- Indicadores ----------------

def dividir(a, b):
    """Divisão que devolve 0 quando o divisor é zero."""
    return a / b if b > 0 else 0


def calcular_indicadores(base, inicio, fim):
    """Calcula os indicadores de um período. Usada para o período atual e o anterior."""
    filtrado = base[(base["data_entrada"] >= inicio) & (base["data_entrada"] <= fim)]
    # Entregues contam pela data de entrega (quando o cliente paga)
    entregues = base[
        (base["status"] == "Entregue")
        & (base["data_entrega"] >= inicio)
        & (base["data_entrega"] <= fim)
    ]

    recusados = (filtrado["status"] == "Orçamento recusado").sum()
    andamento = filtrado["status"].isin(EM_ANDAMENTO).sum()
    concluidas = filtrado["status"].isin(["Pronto", "Entregue"]).sum()
    receita = entregues["valor"].sum()
    lucro = entregues["lucro"].sum()

    return {
        "filtrado": filtrado,
        "entregues": entregues,
        "recebidos": len(filtrado),
        "qtd_entregues": len(entregues),
        "tempo_medio": filtrado["dias_reparo"].mean(),
        # Aprovação: orçamentos aceitos ÷ aparelhos recebidos
        "taxa_aprovacao": 1 - dividir(recusados, len(filtrado)) if len(filtrado) > 0 else 0,
        # Conclusão: concluídas ÷ orçamentos aprovados, sem contar as em andamento
        "taxa_conclusao": dividir(concluidas, len(filtrado) - recusados - andamento),
        "taxa_retorno": dividir((entregues["retorno_garantia"] == "Sim").sum(), len(entregues)),
        "taxa_voltou": dividir(filtrado["cliente_voltou"].sum(), len(filtrado)),
        "receita": receita,
        "lucro": lucro,
        "margem": dividir(lucro, receita),
        "ticket_medio": dividir(receita, len(entregues)),
    }


atual = calcular_indicadores(base, inicio, fim)
filtrado = atual["filtrado"]
entregues = atual["entregues"]
em_andamento = base["status"].isin(EM_ANDAMENTO).sum()  # situação de hoje

# Período anterior: mesmo tamanho, logo antes do início escolhido
duracao = fim - inicio
fim_anterior = inicio - pd.Timedelta(days=1)
inicio_anterior = fim_anterior - duracao
tem_anterior = inicio_anterior >= df["data_entrada"].min()
anterior = calcular_indicadores(base, inicio_anterior, fim_anterior) if tem_anterior else None


def variacao(chave, tipo="percentual"):
    """Texto da setinha do cartão comparando com o período anterior.
    tipo: 'percentual' (+12,3%), 'pontos' (+1,2 p.p.) ou 'dias' (+0,4 dias)."""
    if anterior is None or anterior["recebidos"] == 0:
        return None
    a, b = atual[chave], anterior[chave]
    if pd.isna(a) or pd.isna(b):
        return None
    if tipo == "pontos":
        diferenca = (a - b) * 100
        return ("+" if diferenca >= 0 else "") + formatar_numero(diferenca, 1) + " p.p."
    if tipo == "dias":
        diferenca = a - b
        return ("+" if diferenca >= 0 else "") + formatar_numero(diferenca, 1) + " dias"
    if b == 0:
        return None
    mudanca = (a - b) / b * 100
    return ("+" if mudanca >= 0 else "") + formatar_numero(mudanca, 1) + "%"


# ---------------- Cartões ----------------

if tem_anterior:
    st.caption(
        f"Setas: comparação com o período anterior de mesmo tamanho "
        f"({inicio_anterior:%d/%m/%Y} a {fim_anterior:%d/%m/%Y})."
    )
else:
    st.caption("Sem comparação: não há dados antes do período escolhido. Escolha um período menor para ver as setas.")

linha1 = st.columns(4)
linha1[0].metric("Aparelhos recebidos", formatar_numero(atual["recebidos"]),
                 variacao("recebidos"), border=True)
linha1[1].metric("Aparelhos entregues", formatar_numero(atual["qtd_entregues"]),
                 variacao("qtd_entregues"), border=True)
linha1[2].metric("Em andamento (hoje)", formatar_numero(em_andamento), border=True)
linha1[3].metric("Tempo médio de reparo",
                 formatar_numero(atual["tempo_medio"], 1) + " dias" if pd.notna(atual["tempo_medio"]) else "-",
                 variacao("tempo_medio", "dias"), delta_color="inverse", border=True)

linha2 = st.columns(4)
linha2[0].metric("Orçamentos aprovados", formatar_percentual(atual["taxa_aprovacao"]),
                 variacao("taxa_aprovacao", "pontos"), border=True)
linha2[1].metric("Taxa de conclusão", formatar_percentual(atual["taxa_conclusao"]),
                 variacao("taxa_conclusao", "pontos"), border=True)
linha2[2].metric("Taxa de retorno", formatar_percentual(atual["taxa_retorno"]),
                 variacao("taxa_retorno", "pontos"), delta_color="inverse", border=True)
linha2[3].metric("OS de clientes que voltaram", formatar_percentual(atual["taxa_voltou"]),
                 variacao("taxa_voltou", "pontos"), border=True)

linha3 = st.columns(4)
linha3[0].metric("Receita total", formatar_reais(atual["receita"]), variacao("receita"), border=True)
linha3[1].metric("Lucro bruto", formatar_reais(atual["lucro"]), variacao("lucro"), border=True,
                 help="Receita menos o custo das peças (não inclui aluguel, salários etc.).")
linha3[2].metric("Margem", formatar_percentual(atual["margem"]), variacao("margem", "pontos"), border=True)
linha3[3].metric("Ticket médio", formatar_reais(atual["ticket_medio"]), variacao("ticket_medio"), border=True)


# ---------------- Previsão de demanda ----------------

def prever_demanda(base, meses_a_frente=3):
    """Previsão simples (sazonal): repete o mesmo mês do ano anterior,
    corrigido pelo ritmo recente da loja (últimos 3 meses ÷ média de todos os meses)."""
    por_mes = base.groupby("mes").size()

    # O mês atual ainda não terminou: fica fora do cálculo
    mes_atual = HOJE.strftime("%Y-%m")
    completos = por_mes[por_mes.index < mes_atual]
    if len(completos) < 4:
        return completos, pd.Series(dtype=float), 1.0

    ritmo = completos.tail(3).mean() / completos.mean()

    previsao = {}
    for i in range(1, meses_a_frente + 1):
        mes = (HOJE + pd.DateOffset(months=i)).strftime("%Y-%m")
        mes_ano_passado = (HOJE + pd.DateOffset(months=i - 12)).strftime("%Y-%m")
        if mes_ano_passado in completos.index:
            previsao[mes] = round(completos[mes_ano_passado] * ritmo)
    return completos, pd.Series(previsao, dtype=float), ritmo


historico, previsao, ritmo = prever_demanda(base)


# ---------------- Abas ----------------

aba_geral, aba_servicos, aba_qualidade, aba_financeiro, aba_clientes, aba_dados = st.tabs(
    ["Visão geral", "Serviços", "Qualidade", "Financeiro", "Clientes", "Dados"]
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
    mostrar_grafico(fig)

    col1, col2 = st.columns(2)

    # Previsão de demanda: histórico + próximos meses (tracejado)
    if len(previsao) > 0:
        linha_hist = historico.rename_axis("mes").reset_index(name="aparelhos")
        linha_hist["tipo"] = "Histórico"
        # A previsão começa no último mês real, para a linha ficar contínua
        linha_prev = pd.concat([historico.tail(1), previsao]).rename_axis("mes").reset_index(name="aparelhos")
        linha_prev["tipo"] = "Previsão"
        grafico = pd.concat([linha_hist, linha_prev])

        fig = px.line(grafico, x="mes", y="aparelhos", color="tipo", line_dash="tipo", markers=True,
                      title="Previsão de aparelhos recebidos (próximos 3 meses)")
        fig.update_layout(xaxis_title="Mês", yaxis_title="Aparelhos", legend_title="")
        with col1.container(border=True):
            st.plotly_chart(fig, width="stretch")
            st.caption(
                "Como é calculada: o mesmo mês do ano anterior × o ritmo recente da loja "
                f"({formatar_numero(ritmo, 2)}). O mês atual fica fora porque ainda não terminou. "
                "Usa todo o histórico (ignora o filtro de período)."
            )
    else:
        col1.info("Não há histórico suficiente para a previsão.")

    # Movimento por dia da semana
    ordem = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
    por_dia = filtrado["dia_semana"].value_counts().reindex(ordem, fill_value=0).reset_index()
    por_dia.columns = ["dia", "aparelhos"]
    fig = px.bar(por_dia, x="dia", y="aparelhos", text="aparelhos",
                 title="Aparelhos recebidos por dia da semana")
    fig.update_layout(xaxis_title="", yaxis_title="Aparelhos")
    mostrar_grafico(fig, col2)

    # ---------- Insights (calculados com os dados filtrados) ----------
    insights = []

    if atual["qtd_entregues"] >= MINIMO_OS:
        # 1. Serviço que mais traz receita e a margem dele
        por_tipo = entregues.groupby("tipo_reparo")[["valor", "lucro"]].sum()
        maior_tipo = por_tipo["valor"].idxmax()
        parte = por_tipo.loc[maior_tipo, "valor"] / atual["receita"]
        margem_tipo = por_tipo.loc[maior_tipo, "lucro"] / por_tipo.loc[maior_tipo, "valor"]
        insights.append(
            f"**{maior_tipo}** representa **{formatar_percentual(parte)}** da receita, com margem de "
            f"**{formatar_percentual(margem_tipo)}** (média geral: {formatar_percentual(atual['margem'])}) "
            f"→ manter estoque dos modelos mais comuns e negociar o preço da peça com fornecedores."
        )

        # 2. Defeito que mais volta na garantia, comparado com a média
        retorno_defeito = entregues.groupby("defeito")["retorno_garantia"].apply(lambda s: (s == "Sim").mean())
        if atual["taxa_retorno"] > 0:
            vezes = retorno_defeito.max() / atual["taxa_retorno"]
            insights.append(
                f"**{retorno_defeito.idxmax()}** volta na garantia em **{formatar_percentual(retorno_defeito.max())}** "
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
            # Só aponta um técnico se a diferença for grande (50% a mais que os outros)
            if taxa_outros > 0 and retorno_tecnico.max() / taxa_outros >= 1.5:
                insights.append(
                    f"O técnico **{pior_tecnico}** tem **{formatar_percentual(retorno_tecnico.max())}** de retorno, "
                    f"**{formatar_numero(retorno_tecnico.max() / taxa_outros, 1)}×** a taxa dos demais técnicos "
                    f"→ revisar juntos os reparos que voltaram."
                )
            else:
                taxas = ", ".join(f"{t}: {formatar_percentual(v)}" for t, v in retorno_tecnico.items())
                insights.append(
                    f"Os técnicos têm taxas de retorno parecidas ({taxas}) "
                    f"→ os retornos dependem mais do tipo de defeito do que de quem conserta."
                )

    if atual["recebidos"] >= MINIMO_OS:
        # 4. Serviço com mais orçamentos recusados
        recusa = filtrado.groupby("tipo_reparo")["status"].apply(lambda s: (s == "Orçamento recusado").mean())
        recusados = filtrado[filtrado["status"] == "Orçamento recusado"]
        if recusa.max() > 0:
            insights.append(
                f"**{recusa.idxmax()}** tem **{formatar_percentual(recusa.max())}** dos orçamentos recusados; "
                f"no total, {formatar_reais(recusados['valor'].sum())} em orçamentos não fecharam "
                f"→ revisar o preço ou oferecer parcelamento nesses serviços."
            )

        # 5. Principal origem dos clientes novos
        novos = filtrado[~filtrado["cliente_voltou"]]
        if len(novos) > 0:
            origem = novos["origem_cliente"].value_counts(normalize=True)
            insights.append(
                f"**{origem.index[0]}** trouxe **{formatar_percentual(origem.iloc[0])}** dos clientes novos "
                f"→ investir mais nesse canal (ex.: desconto para quem indica)."
            )

    # 6. Previsão: mês de maior movimento nos próximos meses
    if len(previsao) > 0:
        mes_pico = previsao.idxmax()
        insights.append(
            f"A previsão para **{nome_mes(mes_pico)}** é de **{formatar_numero(previsao.max())} aparelhos**, "
            f"contra {formatar_numero(historico.tail(3).mean())} por mês nos últimos 3 meses "
            f"→ planejar estoque e equipe com antecedência."
        )

    with st.container(border=True):
        st.subheader("Insights")
        if insights:
            for frase in insights:
                st.markdown("- " + frase)
        else:
            st.info(f"São necessárias pelo menos {MINIMO_OS} OS no filtro atual para gerar insights.")


# ---------------- Aba: Serviços ----------------

with aba_servicos:
    col1, col2 = st.columns(2)

    # Serviços em andamento hoje, por status
    andamento = base[base["status"].isin(EM_ANDAMENTO)]
    por_status = andamento["status"].value_counts().reset_index()
    por_status.columns = ["status", "quantidade"]
    fig = px.bar(por_status, x="status", y="quantidade", text="quantidade",
                 title="Serviços em andamento por status")
    fig.update_layout(xaxis_title="", yaxis_title="Aparelhos")
    mostrar_grafico(fig, col1)

    # Tempo médio de reparo por tipo de serviço
    tempo = filtrado.groupby("tipo_reparo")["dias_reparo"].mean().round(1).sort_values().reset_index()
    tempo["texto"] = tempo["dias_reparo"].apply(lambda d: formatar_numero(d, 1))
    fig = px.bar(tempo, x="dias_reparo", y="tipo_reparo", orientation="h", text="texto",
                 title="Tempo médio de reparo por tipo de serviço (dias)")
    fig.update_layout(xaxis_title="Dias", yaxis_title="")
    mostrar_grafico(fig, col2)

    # Modelos mais consertados, separados por defeito
    top_modelos = filtrado["modelo"].value_counts().head(10).index
    modelos = filtrado[filtrado["modelo"].isin(top_modelos)]
    modelos = modelos.groupby(["modelo", "defeito"]).size().reset_index(name="aparelhos")
    fig = px.bar(modelos, x="aparelhos", y="modelo", color="defeito", orientation="h",
                 title="10 modelos mais consertados (por defeito)")
    fig.update_layout(xaxis_title="Aparelhos", yaxis_title="", legend_title="Defeito",
                      yaxis={"categoryorder": "total ascending"})
    mostrar_grafico(fig)

    # Aparelhos esquecidos: prontos há muito tempo sem o cliente buscar (situação de hoje)
    with st.container(border=True):
        st.subheader(f"Aparelhos esquecidos (prontos há mais de {DIAS_ESQUECIDO} dias)")
        prontos = base[base["status"] == "Pronto"].copy()
        prontos["dias_parado"] = (HOJE - prontos["data_conclusao"]).dt.days
        esquecidos = prontos[prontos["dias_parado"] > DIAS_ESQUECIDO].sort_values("dias_parado", ascending=False)

        c1, c2 = st.columns(2)
        c1.metric("Aparelhos esquecidos", formatar_numero(len(esquecidos)))
        c2.metric("Valor a receber", formatar_reais(esquecidos["valor"].sum()))

        if len(esquecidos) > 0:
            tabela = esquecidos[["os_id", "cliente_id", "modelo", "tipo_reparo", "data_conclusao", "dias_parado", "valor"]]
            st.dataframe(
                tabela,
                hide_index=True,
                column_config={
                    "os_id": "OS",
                    "cliente_id": "Cliente",
                    "modelo": "Modelo",
                    "tipo_reparo": "Serviço",
                    "data_conclusao": st.column_config.DateColumn("Pronto desde", format="DD/MM/YYYY"),
                    "dias_parado": "Dias parado",
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
                },
            )
            st.caption("Sugestão: ligar para esses clientes e lembrar da retirada.")
        else:
            st.success("Nenhum aparelho esquecido.")


# ---------------- Aba: Qualidade ----------------

def grafico_retorno(coluna, titulo):
    """Barras com a taxa de retorno por grupo e uma linha tracejada na média geral."""
    taxa = entregues.groupby(coluna)["retorno_garantia"].apply(lambda s: (s == "Sim").mean() * 100)
    taxa = taxa.round(1).sort_values(ascending=False).reset_index(name="taxa")
    taxa["texto"] = taxa["taxa"].apply(lambda t: formatar_numero(t, 1) + "%")

    fig = px.bar(taxa, x=coluna, y="taxa", text="texto", title=titulo)
    fig.add_hline(y=atual["taxa_retorno"] * 100, line_dash="dash", line_color="red",
                  annotation_text="Média geral: " + formatar_percentual(atual["taxa_retorno"]))
    fig.update_layout(xaxis_title="", yaxis_title="% de retorno")
    return fig


with aba_qualidade:
    # Defeitos mais frequentes
    defeitos = filtrado["defeito"].value_counts().sort_values().reset_index()
    defeitos.columns = ["defeito", "quantidade"]
    fig = px.bar(defeitos, x="quantidade", y="defeito", orientation="h", text="quantidade",
                 title="Defeitos mais frequentes")
    fig.update_layout(xaxis_title="Aparelhos", yaxis_title="")
    mostrar_grafico(fig)

    col1, col2 = st.columns(2)
    mostrar_grafico(grafico_retorno("defeito", "Taxa de retorno por defeito"), col1)
    mostrar_grafico(grafico_retorno("tecnico", "Taxa de retorno por técnico"), col2)


# ---------------- Aba: Financeiro ----------------

with aba_financeiro:
    col1, col2 = st.columns(2)

    # Receita e lucro por tipo de reparo (OS entregues)
    por_tipo = entregues.groupby("tipo_reparo")[["valor", "lucro"]].sum().sort_values("valor").reset_index()
    por_tipo = por_tipo.rename(columns={"valor": "Receita", "lucro": "Lucro"})
    fig = px.bar(por_tipo, x=["Receita", "Lucro"], y="tipo_reparo", orientation="h", barmode="group",
                 title="Receita e lucro por tipo de reparo")
    fig.update_layout(xaxis_title="R$", yaxis_title="", legend_title="")
    mostrar_grafico(fig, col1)

    # Margem por tipo de reparo
    por_tipo["margem"] = (por_tipo["Lucro"] / por_tipo["Receita"] * 100).round(1)
    por_tipo["texto"] = por_tipo["margem"].apply(lambda m: formatar_numero(m, 1) + "%")
    fig = px.bar(por_tipo.sort_values("margem"), x="margem", y="tipo_reparo", orientation="h", text="texto",
                 title="Margem por tipo de reparo (lucro ÷ receita)")
    fig.update_layout(xaxis_title="% de margem", yaxis_title="")
    mostrar_grafico(fig, col2)

    # Receita e lucro por mês (pelo mês de entrega)
    por_mes = entregues.groupby(entregues["data_entrega"].dt.strftime("%Y-%m"))[["valor", "lucro"]].sum()
    por_mes = por_mes.rename(columns={"valor": "Receita", "lucro": "Lucro"}).rename_axis("mes").reset_index()
    fig = px.line(por_mes, x="mes", y=["Receita", "Lucro"], markers=True, title="Receita e lucro por mês")
    fig.update_layout(xaxis_title="Mês", yaxis_title="R$", legend_title="")
    mostrar_grafico(fig)

    # Orçamentos aprovados × recusados
    with st.container(border=True):
        st.subheader("Orçamentos")
        recusados = filtrado[filtrado["status"] == "Orçamento recusado"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Orçamentos recusados", formatar_numero(len(recusados)))
        c2.metric("Valor não fechado", formatar_reais(recusados["valor"].sum()))
        c3.metric("Taxa de aprovação", formatar_percentual(atual["taxa_aprovacao"]))

        recusa = filtrado.groupby("tipo_reparo")["status"].apply(lambda s: (s == "Orçamento recusado").mean() * 100)
        recusa = recusa.round(1).sort_values().reset_index(name="taxa")
        recusa["texto"] = recusa["taxa"].apply(lambda t: formatar_numero(t, 1) + "%")
        fig = px.bar(recusa, x="taxa", y="tipo_reparo", orientation="h", text="texto",
                     title="Orçamentos recusados por tipo de reparo (%)")
        fig.update_traces(marker_color=CORES[3])
        fig.update_layout(xaxis_title="% recusado", yaxis_title="")
        st.plotly_chart(fig, width="stretch")


# ---------------- Aba: Clientes ----------------

with aba_clientes:
    c1, c2, c3 = st.columns(3)
    c1.metric("Clientes atendidos", formatar_numero(filtrado["cliente_id"].nunique()), border=True)
    c2.metric("Clientes que voltaram", formatar_numero(filtrado[filtrado["cliente_voltou"]]["cliente_id"].nunique()),
              border=True, help="Clientes que já tinham trazido outro aparelho antes.")
    receita_voltou = entregues[entregues["cliente_voltou"]]["valor"].sum()
    c3.metric("Receita de clientes que voltaram", formatar_percentual(dividir(receita_voltou, atual["receita"])),
              border=True, help="Parte da receita vinda de clientes que já tinham vindo antes.")

    col1, col2 = st.columns(2)

    # Como os clientes novos conheceram a loja
    novos = filtrado[~filtrado["cliente_voltou"]]
    origem = novos["origem_cliente"].value_counts().reset_index()
    origem.columns = ["origem", "clientes"]
    fig = px.pie(origem, names="origem", values="clientes", hole=0.4, color_discrete_sequence=CORES,
                 title="Como os clientes novos conheceram a loja")
    mostrar_grafico(fig, col1)

    # Receita por origem do cliente
    receita_origem = entregues.groupby("origem_cliente")["valor"].sum().sort_values().reset_index()
    receita_origem["texto"] = receita_origem["valor"].apply(formatar_reais)
    fig = px.bar(receita_origem, x="valor", y="origem_cliente", orientation="h", text="texto",
                 title="Receita por origem do cliente")
    fig.update_layout(xaxis_title="Receita (R$)", yaxis_title="")
    mostrar_grafico(fig, col2)

    # Clientes novos × que voltaram por mês
    tipo_cliente = filtrado["cliente_voltou"].map({True: "Voltou", False: "Novo"})
    por_mes = filtrado.groupby(["mes", tipo_cliente]).size().reset_index(name="OS")
    por_mes.columns = ["mes", "cliente", "OS"]
    fig = px.bar(por_mes, x="mes", y="OS", color="cliente", title="OS de clientes novos × clientes que voltaram")
    fig.update_layout(xaxis_title="Mês", yaxis_title="Ordens de serviço", legend_title="")
    mostrar_grafico(fig)

    st.caption("Clientes identificados só por um código (ex.: CLI-0001). Nome, telefone e CPF ficam fora "
               "do painel para proteger os dados pessoais (LGPD).")


# ---------------- Aba: Dados ----------------

with aba_dados:
    st.write(f"{formatar_numero(len(filtrado))} ordens de serviço no filtro atual.")
    st.dataframe(filtrado, hide_index=True)

    # Botão para baixar as OS filtradas em CSV
    csv = filtrado.to_csv(sep=";", index=False).encode("utf-8-sig")
    st.download_button("Baixar CSV", data=csv, file_name="ordens_servico_filtradas.csv", mime="text/csv")
