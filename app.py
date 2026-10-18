# Painel de BI da assistência técnica de celulares.
# Para rodar: streamlit run app.py
#
# Layout em "F" (padrão de dashboards): filtros e números principais no topo,
# gráfico principal + insights logo abaixo, e os detalhes em seções na sequência.

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Opção Celular · Painel da Assistência", page_icon="assets/logo.jpg", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------- Configurações ----------------

# Cores (paleta segura para daltônicos): cinza é o padrão, cor só para destacar
AZUL = "#0077BB"      # dado principal
CINZA = "#BBBBBB"     # contexto / demais itens
LARANJA = "#EE7733"   # atenção
VERMELHO = "#CC3311"  # problema
VERDE = "#009988"     # bom

px.defaults.template = "plotly_white"

# Meta de tempo de reparo (ajustar com o Felipe)
META_TEMPO = 3.0  # dias, no máximo

EM_ANDAMENTO = ["Em andamento", "Aguardando peça"]
MINIMO_OS = 30       # com poucas OS as conclusões dos insights não fazem sentido
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

# Tamanho dos números (cartões principais grandes, secundários menores) e sem a barra do topo
st.markdown("""
<style>
.st-key-principais [data-testid="stMetricValue"] { font-size: 2.1rem; }
.st-key-secundarios [data-testid="stMetricValue"] { font-size: 1.35rem; }
[data-testid="stHeader"] { display: none; }  /* esconde a barra do topo do Streamlit */
[data-testid="stMainBlockContainer"] { padding-top: 2rem; }  /* tira o espaço vazio que ela deixava */
</style>
""", unsafe_allow_html=True)


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
DATA_MIN = df["data_entrada"].min()


# ---------------- Formatação brasileira ----------------

def formatar_numero(valor, casas=0):
    """1234.5 -> '1.234,5' (troca ponto e vírgula do formato americano)."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_reais(valor):
    return "R$ " + formatar_numero(valor, 2)


def formatar_reais_curto(valor):
    """751943 -> 'R$ 751,9 mil' (mais fácil de ler em cartões e gráficos)."""
    if abs(valor) >= 1_000_000:
        return "R$ " + formatar_numero(valor / 1_000_000, 1) + " mi"
    if abs(valor) >= 1_000:
        return "R$ " + formatar_numero(valor / 1_000, 1) + " mil"
    return formatar_reais(valor)


def formatar_percentual(valor):
    return formatar_numero(valor * 100, 1) + "%"


def nome_mes(texto_mes):
    """'2026-03' -> 'março/2026'."""
    ano, mes = texto_mes.split("-")
    return f"{MESES[int(mes) - 1]}/{ano}"


def dividir(a, b):
    """Divisão que devolve 0 quando o divisor é zero."""
    return a / b if b > 0 else 0


# ---------------- Cabeçalho e filtros (no topo) ----------------

# Logo da empresa ao lado do título
col_logo, col_titulo = st.columns([1, 12], vertical_alignment="center")
col_logo.image("assets/logo.jpg", width=90)
with col_titulo:
    st.title("Opção Celular · Painel da Assistência")
    st.caption("Opção Telefonia Celular · Bauru (SP)")

PERIODOS = {"Últimos 30 dias": 30, "Últimos 3 meses": 91, "Últimos 6 meses": 182,
            "Últimos 12 meses": 365, "Personalizado": None}

with st.container(border=True):
    f1, f2, f3, f4 = st.columns([1.2, 1, 1, 1.6])  # Período · Técnico · Marca · Modelo
    escolha = f1.selectbox("Período", list(PERIODOS), index=0)  # padrão: últimos 30 dias
    if PERIODOS[escolha]:
        fim = HOJE
        inicio = max(HOJE - pd.Timedelta(days=PERIODOS[escolha] - 1), DATA_MIN)
    else:
        datas = f1.date_input("Datas", value=(DATA_MIN.date(), HOJE.date()), min_value=DATA_MIN.date(),
                              max_value=HOJE.date(), format="DD/MM/YYYY", label_visibility="collapsed")
        inicio, fim = (datas[0], datas[1]) if len(datas) == 2 else (datas[0], datas[0])
        inicio, fim = pd.Timestamp(inicio), pd.Timestamp(fim)

    tecnicos = f2.multiselect("Técnico", sorted(df["tecnico"].unique()), placeholder="Todos", select_all=False)
    marcas = f3.multiselect("Marca", sorted(df["marca"].unique()), placeholder="Todas", select_all=False)
    # A lista de modelos mostra só os modelos das marcas escolhidas
    opcoes_modelo = df[df["marca"].isin(marcas)] if marcas else df
    modelos_escolhidos = f4.multiselect("Modelo", sorted(opcoes_modelo["modelo"].unique()),
                                        placeholder="Todos (digite para buscar)", select_all=False)

# Aplica marca, modelo e técnico (lista vazia = todos; por isso a opção "Select all" fica desligada)
base = df.copy()
if marcas:
    base = base[base["marca"].isin(marcas)]
if modelos_escolhidos:
    base = base[base["modelo"].isin(modelos_escolhidos)]
if tecnicos:
    base = base[base["tecnico"].isin(tecnicos)]


# ---------------- Indicadores ----------------

def calcular_indicadores(base, inicio, fim):
    """Calcula os indicadores do período escolhido."""
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

if len(filtrado) == 0:
    st.warning("Nenhuma ordem de serviço com esses filtros. Tente outro período, marca ou modelo.")
    st.stop()

def cartao(onde, titulo, valor, ajuda=None):
    """Cartão de indicador com borda: título e número."""
    with onde.container(border=True):
        st.metric(titulo, valor, help=ajuda)


# ---------------- Números principais (nível 1) ----------------

st.caption(f"Período: **{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}**")

tempo = atual["tempo_medio"]
with st.container(key="principais"):
    k = st.columns(5)
    cartao(k[0], "Receita", formatar_reais_curto(atual["receita"]))
    cartao(k[1], "Lucro bruto", formatar_reais_curto(atual["lucro"]),
           ajuda="Receita menos o custo das peças (não inclui aluguel, salários etc.).")
    cartao(k[2], "Aparelhos recebidos", formatar_numero(atual["recebidos"]))
    cartao(k[3], "Tempo médio de reparo", formatar_numero(tempo, 1) + " dias" if pd.notna(tempo) else "-")
    cartao(k[4], "Taxa de retorno", formatar_percentual(atual["taxa_retorno"]),
           ajuda="Aparelhos que voltaram com defeito na garantia ÷ aparelhos entregues.")

# ---------------- Números de apoio (nível 2) ----------------

em_andamento = base["status"].isin(EM_ANDAMENTO).sum()  # situação de hoje
aguardando_peca = (base["status"] == "Aguardando peça").sum()
with st.container(key="secundarios", border=True):
    s = st.columns(5)
    s[0].metric("Em andamento (hoje)", formatar_numero(em_andamento),
                help=f"{formatar_numero(aguardando_peca)} aguardando peça")
    s[1].metric("Taxa de conclusão", formatar_percentual(atual["taxa_conclusao"]),
                help="Reparos concluídos ÷ orçamentos aprovados (sem contar os em andamento).")
    s[2].metric("Orçamentos aprovados", formatar_percentual(atual["taxa_aprovacao"]))
    s[3].metric("Clientes que voltaram", formatar_percentual(atual["taxa_voltou"]),
                help="OS de clientes que já tinham vindo antes.")
    s[4].metric("Clientes atendidos", formatar_numero(filtrado["cliente_id"].nunique()))


# ---------------- Gráficos: funções de apoio ----------------

def titulo(fig, texto, subtitulo):
    """Título como conclusão (o que o gráfico mostra) + subtítulo com a medida."""
    fig.update_layout(title={"text": f"<b>{texto}</b>", "subtitle": {"text": subtitulo}},
                      margin={"t": 80, "l": 10, "r": 10, "b": 10})
    return fig


def barras(dados, categoria, valor, texto_titulo, subtitulo, destaque=(), cor=AZUL,
           texto=None, horizontal=True, eixo_valor="", linha=None, linha_texto=""):
    """Barras em cinza com os itens de 'destaque' coloridos (a cor chama atenção só para o que importa)."""
    dados = dados.copy()
    dados["grupo"] = dados[categoria].isin(list(destaque)).map({True: "destaque", False: "outros"})
    if horizontal:
        fig = px.bar(dados, x=valor, y=categoria, orientation="h", color="grupo", text=texto,
                     color_discrete_map={"destaque": cor, "outros": CINZA})
        fig.update_yaxes(title="", categoryorder="total ascending")
        fig.update_xaxes(title=eixo_valor)
    else:
        fig = px.bar(dados, x=categoria, y=valor, color="grupo", text=texto,
                     color_discrete_map={"destaque": cor, "outros": CINZA})
        fig.update_xaxes(title="", categoryorder="array", categoryarray=list(dados[categoria]))
        fig.update_yaxes(title=eixo_valor)
    fig.update_layout(showlegend=False)
    # Rótulos sempre na horizontal e para fora da barra (não ficam cortados nem girados)
    fig.update_traces(textangle=0, textposition="outside", cliponaxis=False)
    if linha is not None:
        if horizontal:
            fig.add_vline(x=linha, line_dash="dash", line_color="#555555",
                          annotation_text=linha_texto, annotation_position="bottom right")
        else:
            fig.add_hline(y=linha, line_dash="dash", line_color="#555555",
                          annotation_text=linha_texto, annotation_position="bottom right")
    return titulo(fig, texto_titulo, subtitulo)


def mostrar(fig, onde=st):
    """Mostra o gráfico dentro de um cartão com borda."""
    with onde.container(border=True):
        st.plotly_chart(fig, width="stretch")


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


# ---------------- Insights (calculados com os dados filtrados) ----------------

insights = []
if atual["qtd_entregues"] >= MINIMO_OS:
    # Serviço que mais traz receita e a margem dele
    por_tipo = entregues.groupby("tipo_reparo")[["valor", "lucro"]].sum()
    maior_tipo = por_tipo["valor"].idxmax()
    parte = por_tipo.loc[maior_tipo, "valor"] / atual["receita"]
    margem_tipo = por_tipo.loc[maior_tipo, "lucro"] / por_tipo.loc[maior_tipo, "valor"]
    insights.append(
        f"**{maior_tipo}** traz **{formatar_percentual(parte)}** da receita, mas com margem de "
        f"{formatar_percentual(margem_tipo)} → negociar o preço da peça e estocar os modelos mais comuns."
    )

    # Defeito que mais volta na garantia
    retorno_defeito = entregues.groupby("defeito")["retorno_garantia"].apply(lambda s: (s == "Sim").mean())
    if atual["taxa_retorno"] > 0:
        insights.append(
            f"**{retorno_defeito.idxmax()}** volta na garantia em **{formatar_percentual(retorno_defeito.max())}** "
            f"dos casos ({formatar_numero(retorno_defeito.max() / atual['taxa_retorno'], 1)}× a média) "
            f"→ revisar o procedimento ou o prazo de garantia."
        )

if atual["recebidos"] >= MINIMO_OS:
    # Serviço com mais orçamentos recusados
    recusa = filtrado.groupby("tipo_reparo")["status"].apply(lambda s: (s == "Orçamento recusado").mean())
    valor_recusado = filtrado[filtrado["status"] == "Orçamento recusado"]["valor"].sum()
    if recusa.max() > 0:
        insights.append(
            f"**{recusa.idxmax()}** tem **{formatar_percentual(recusa.max())}** dos orçamentos recusados "
            f"({formatar_reais_curto(valor_recusado)} não fecharam no total) → revisar preço ou oferecer parcelamento."
        )

    # Principal origem dos clientes novos
    novos = filtrado[~filtrado["cliente_voltou"]]
    if len(novos) > 0:
        origem = novos["origem_cliente"].value_counts(normalize=True)
        insights.append(
            f"**{origem.index[0]}** trouxe **{formatar_percentual(origem.iloc[0])}** dos clientes novos "
            f"→ investir nesse canal (ex.: desconto para quem indica)."
        )

# Previsão: mês de maior movimento nos próximos meses (só com volume suficiente)
if len(previsao) > 0 and historico.tail(3).sum() >= MINIMO_OS:
    insights.append(
        f"Previsão de **{formatar_numero(previsao.max())} aparelhos em {nome_mes(previsao.idxmax())}** "
        f"(média recente: {formatar_numero(historico.tail(3).mean())}/mês) → planejar estoque e equipe."
    )


# ---------------- Gráfico principal + insights ----------------

col_grafico, col_insights = st.columns([3, 2])

with col_grafico.container(border=True):
    # Recebidos (azul) e entregues (cinza) por mês, com a previsão tracejada
    entregues_base = base[base["status"] == "Entregue"]
    entregues_mes = entregues_base.groupby(entregues_base["data_entrega"].dt.strftime("%Y-%m")).size()
    entregues_mes = entregues_mes[entregues_mes.index.isin(historico.index)]

    linhas = [
        pd.DataFrame({"mes": historico.index, "aparelhos": historico.values, "serie": "Recebidos"}),
        pd.DataFrame({"mes": entregues_mes.index, "aparelhos": entregues_mes.values, "serie": "Entregues"}),
    ]
    if len(previsao) > 0:
        inicio_prev = historico.tail(1)  # a previsão começa no último mês real, para a linha ficar contínua
        prev = pd.concat([inicio_prev, previsao])
        linhas.append(pd.DataFrame({"mes": prev.index, "aparelhos": prev.values, "serie": "Previsão"}))
    movimento = pd.concat(linhas)

    fig = px.line(movimento, x="mes", y="aparelhos", color="serie", line_dash="serie", markers=True,
                  color_discrete_map={"Recebidos": AZUL, "Entregues": CINZA, "Previsão": AZUL},
                  line_dash_map={"Recebidos": "solid", "Entregues": "solid", "Previsão": "dot"})
    fig.update_layout(xaxis_title="", yaxis_title="Aparelhos", legend_title="",
                      legend={"orientation": "h", "y": -0.15})
    # Destaca o período escolhido nos filtros
    fig.add_vrect(x0=inicio, x1=fim, fillcolor=AZUL, opacity=0.07, line_width=0)
    if len(previsao) > 0:
        titulo(fig, f"Pico previsto em {nome_mes(previsao.idxmax())}: {formatar_numero(previsao.max())} aparelhos",
               "Aparelhos por mês (últimos 12 meses) e previsão para os próximos 3 meses")
    else:
        titulo(fig, "Movimento mensal", "Aparelhos recebidos e entregues por mês")
    st.plotly_chart(fig, width="stretch")

with col_insights.container(border=True):
    st.subheader("Insights")
    if insights:
        for frase in insights:
            st.markdown("- " + frase)
    else:
        st.info(f"São necessárias pelo menos {MINIMO_OS} OS no filtro para gerar insights.")


# ---------------- Seção: Serviços e qualidade ----------------

st.subheader("Serviços e qualidade")
c1, c2 = st.columns(2)

# Defeitos mais frequentes
defeitos = filtrado["defeito"].value_counts().reset_index()
defeitos.columns = ["defeito", "aparelhos"]
defeitos["texto"] = (defeitos["aparelhos"] / len(filtrado)).apply(formatar_percentual)
top_defeito = defeitos.iloc[0]
mostrar(barras(defeitos, "defeito", "aparelhos",
               f"{top_defeito['defeito']} é {top_defeito['texto']} dos defeitos",
               "Aparelhos recebidos por defeito", destaque=[top_defeito["defeito"]],
               texto="texto", eixo_valor="Aparelhos"), c1)

# Taxa de retorno por defeito, com a média
if len(entregues) > 0:
    retorno = entregues.groupby("defeito")["retorno_garantia"].apply(lambda s: (s == "Sim").mean() * 100)
    retorno = retorno.round(1).reset_index(name="taxa")
    retorno["texto"] = retorno["taxa"].apply(lambda t: formatar_numero(t, 1) + "%")
    media = atual["taxa_retorno"] * 100
    acima = retorno[retorno["taxa"] > media]["defeito"]
    pior = retorno.loc[retorno["taxa"].idxmax()]
    mostrar(barras(retorno, "defeito", "taxa",
                   f"{pior['defeito']} volta {formatar_numero(pior['taxa'] / media, 1) if media else '-'}× mais que a média",
                   "Taxa de retorno na garantia por defeito (%) · vermelho = acima da média",
                   destaque=acima, cor=VERMELHO, texto="texto", eixo_valor="% de retorno",
                   linha=media, linha_texto=f"média {formatar_numero(media, 1)}%"), c2)

c1, c2 = st.columns(2)

# Tempo médio de reparo por tipo, com a meta
tempo_tipo = filtrado.groupby("tipo_reparo")["dias_reparo"].mean().round(1).dropna().reset_index()
if len(tempo_tipo) > 0:
    tempo_tipo["texto"] = tempo_tipo["dias_reparo"].apply(lambda d: formatar_numero(d, 1))
    lento = tempo_tipo.loc[tempo_tipo["dias_reparo"].idxmax()]
    acima_meta = tempo_tipo[tempo_tipo["dias_reparo"] > META_TEMPO]["tipo_reparo"]
    mostrar(barras(tempo_tipo, "tipo_reparo", "dias_reparo",
                   f"{lento['tipo_reparo']} é o mais demorado ({lento['texto']} dias)",
                   f"Tempo médio de reparo (dias) · laranja = acima da meta de {formatar_numero(META_TEMPO, 0)} dias",
                   destaque=acima_meta, cor=LARANJA, texto="texto", eixo_valor="Dias",
                   linha=META_TEMPO, linha_texto="meta"), c1)

# Modelos mais consertados
modelos = filtrado["modelo"].value_counts().head(10).reset_index()
modelos.columns = ["modelo", "aparelhos"]
top3 = list(modelos["modelo"].head(3))
mostrar(barras(modelos, "modelo", "aparelhos",
               f"{', '.join(top3[:-1])} e {top3[-1]} lideram" if len(top3) > 1 else f"{top3[0]} lidera",
               "10 modelos que mais chegam para conserto · prioridade no estoque de peças",
               destaque=top3, texto="aparelhos", eixo_valor="Aparelhos"), c2)

# ---------------- Seção: Financeiro ----------------

st.subheader("Financeiro")
c1, c2 = st.columns(2)

if len(entregues) > 0:
    por_tipo = entregues.groupby("tipo_reparo")[["valor", "lucro"]].sum().reset_index()
    por_tipo["parte"] = por_tipo["valor"] / por_tipo["valor"].sum()
    por_tipo["texto"] = por_tipo["valor"].apply(formatar_reais_curto)
    top_tipo = por_tipo.loc[por_tipo["valor"].idxmax()]
    mostrar(barras(por_tipo, "tipo_reparo", "valor",
                   f"{top_tipo['tipo_reparo']} traz {formatar_percentual(top_tipo['parte'])} da receita",
                   "Receita por tipo de reparo (aparelhos entregues no período)",
                   destaque=[top_tipo["tipo_reparo"]], texto="texto", eixo_valor="R$"), c1)

    # Margem por tipo, com a média
    por_tipo["margem"] = (por_tipo["lucro"] / por_tipo["valor"] * 100).round(1)
    por_tipo["texto_margem"] = por_tipo["margem"].apply(lambda m: formatar_numero(m, 1) + "%")
    menor_margem = por_tipo.loc[por_tipo["margem"].idxmin()]
    mostrar(barras(por_tipo, "tipo_reparo", "margem",
                   f"{menor_margem['tipo_reparo']} tem a menor margem ({menor_margem['texto_margem']})",
                   "Margem por tipo de reparo (lucro ÷ receita) · laranja = abaixo da média",
                   destaque=por_tipo[por_tipo["margem"] < atual["margem"] * 100]["tipo_reparo"], cor=LARANJA,
                   texto="texto_margem", eixo_valor="% de margem",
                   linha=atual["margem"] * 100, linha_texto="média"), c2)

c1, c2 = st.columns(2)

# Receita e lucro por mês (últimos 12 meses, para ver a tendência)
entregues_base = base[base["status"] == "Entregue"].copy()
entregues_base["mes_entrega"] = entregues_base["data_entrega"].dt.strftime("%Y-%m")
fin_mes = entregues_base[entregues_base["mes_entrega"].isin(historico.index)]
fin_mes = fin_mes.groupby("mes_entrega")[["valor", "lucro"]].sum().reset_index()
fin_mes = fin_mes.rename(columns={"valor": "Receita", "lucro": "Lucro"})
if len(fin_mes) > 0:
    melhor_mes = fin_mes.loc[fin_mes["Receita"].idxmax()]
    fig = px.line(fin_mes, x="mes_entrega", y=["Receita", "Lucro"], markers=True,
                  color_discrete_map={"Receita": AZUL, "Lucro": CINZA})
    fig.update_layout(xaxis_title="", yaxis_title="R$", legend_title="", legend={"orientation": "h", "y": -0.15})
    mostrar(titulo(fig, f"Melhor mês: {nome_mes(melhor_mes['mes_entrega'])} ({formatar_reais_curto(melhor_mes['Receita'])})",
                   "Receita e lucro por mês (últimos 12 meses completos)"), c1)

# Orçamentos recusados por tipo
recusa = filtrado.groupby("tipo_reparo")["status"].apply(lambda s: (s == "Orçamento recusado").mean() * 100)
recusa = recusa.round(1).reset_index(name="taxa")
recusa["texto"] = recusa["taxa"].apply(lambda t: formatar_numero(t, 1) + "%")
media_recusa = (1 - atual["taxa_aprovacao"]) * 100
mais_recusado = recusa.loc[recusa["taxa"].idxmax()]
mostrar(barras(recusa, "tipo_reparo", "taxa",
               f"{mais_recusado['tipo_reparo']}: {mais_recusado['texto']} dos orçamentos recusados",
               "Orçamentos recusados por tipo de reparo (%) · laranja = acima da média",
               destaque=recusa[recusa["taxa"] > media_recusa]["tipo_reparo"], cor=LARANJA,
               texto="texto", eixo_valor="% recusado", linha=media_recusa, linha_texto="média"), c2)


# ---------------- Seção: Clientes ----------------

st.subheader("Clientes")
c1, c2 = st.columns(2)

# Como os clientes novos conheceram a loja (barras ranqueadas no lugar de pizza)
novos = filtrado[~filtrado["cliente_voltou"]]
if len(novos) > 0:
    origem = novos["origem_cliente"].value_counts().reset_index()
    origem.columns = ["origem", "clientes"]
    origem["texto"] = (origem["clientes"] / len(novos)).apply(formatar_percentual)
    top_origem = origem.iloc[0]
    mostrar(barras(origem, "origem", "clientes",
                   f"{top_origem['origem']} traz {top_origem['texto']} dos clientes novos",
                   "Como os clientes novos conheceram a loja", destaque=[top_origem["origem"]],
                   texto="texto", eixo_valor="Clientes novos"), c1)

# Clientes novos × que voltaram por mês (últimos 12 meses)
hist_clientes = base[base["mes"].isin(historico.index)].copy()
hist_clientes["cliente"] = hist_clientes["cliente_voltou"].map({True: "Voltou", False: "Novo"})
por_mes = hist_clientes.groupby(["mes", "cliente"]).size().reset_index(name="OS")
if len(por_mes) > 0:
    fig = px.bar(por_mes, x="mes", y="OS", color="cliente",
                 color_discrete_map={"Novo": CINZA, "Voltou": AZUL}, category_orders={"cliente": ["Voltou", "Novo"]})
    fig.update_layout(xaxis_title="", yaxis_title="Ordens de serviço", legend_title="",
                      legend={"orientation": "h", "y": -0.15})
    mostrar(titulo(fig, f"{formatar_percentual(atual['taxa_voltou'])} das OS são de clientes que voltaram",
                   "OS de clientes novos e de clientes que voltaram, por mês (últimos 12 meses)"), c2)
