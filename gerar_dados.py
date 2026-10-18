# Gera a base simulada de ordens de serviço (OS) da assistência técnica.
# Os números abaixo são parecidos com os informados pelo dono e podem ser ajustados.

import numpy as np
import pandas as pd

np.random.seed(42)

# ---------------- Configurações ----------------

DATA_INICIO = "2025-11-01"
DATA_HOJE = "2026-10-17"  # "data de hoje" da base

MEDIA_POR_DIA = 8         # aparelhos recebidos por dia
AUMENTO_DEZ_JAN = 1.3     # dezembro e janeiro com 30% a mais
CHANCE_CANCELADO = 0.05   # cliente desistiu depois de aprovar

# Peso de cada dia da semana (0 = segunda ... 5 = sábado; domingo fechado).
# Segunda tem os aparelhos que quebraram no fim de semana; sábado o cliente tem mais tempo.
PESO_DIA_SEMANA = {0: 1.15, 1: 0.90, 2: 0.90, 3: 1.00, 4: 1.00, 5: 1.05}

# Marca: (chance, modelos do mais comum para o menos comum)
MARCAS = {
    "Samsung": (0.40, ["Galaxy A14", "Galaxy A54", "Galaxy A34", "Galaxy A04", "Galaxy A24",
                       "Galaxy M34", "Galaxy S23", "Galaxy S21 FE"]),
    "Apple": (0.30, ["iPhone 11", "iPhone 13", "iPhone 12", "iPhone XR", "iPhone 14",
                     "iPhone 15", "iPhone SE"]),
    "Motorola": (0.20, ["Moto G54", "Moto G22", "Moto E13", "Moto G84", "Moto G32", "Edge 40"]),
    "Xiaomi": (0.10, ["Redmi Note 12", "Redmi 12C", "Redmi Note 13", "Poco X5", "Redmi 13C"]),
}
AUMENTO_APPLE = 1.5  # Apple custa ~50% a mais

# Defeito: tipo de reparo, chance, preço mín/máx, dias mín/máx, chance de retorno
DEFEITOS = {
    "Tela quebrada": ("Troca de tela", 0.35, 250, 700, 1, 3, 0.05),
    "Bateria viciada": ("Troca de bateria", 0.20, 120, 280, 1, 2, 0.04),
    "Conector de carga": ("Troca de conector", 0.15, 90, 190, 1, 2, 0.08),
    "Não liga": ("Reparo de placa", 0.10, 200, 600, 3, 8, 0.15),
    "Danos por água": ("Limpeza de oxidação", 0.10, 150, 380, 3, 7, 0.25),
    "Software travando": ("Reinstalação de software", 0.10, 60, 140, 0, 1, 0.10),
}

# Custo da peça como fração do preço cobrado (mín, máx).
# Referência: preços de peças paralelas em lojas online (tela é a peça mais cara;
# conector custa R$ 20 a 50; oxidação e software quase não usam peça).
CUSTO_PECA = {
    "Troca de tela": (0.40, 0.60),
    "Troca de bateria": (0.30, 0.45),
    "Troca de conector": (0.15, 0.30),
    "Reparo de placa": (0.10, 0.30),
    "Limpeza de oxidação": (0.05, 0.15),
    "Reinstalação de software": (0.00, 0.00),
}

# Chance de o cliente recusar o orçamento (reparos caros e incertos são mais recusados)
CHANCE_RECUSA = {
    "Troca de tela": 0.08,
    "Troca de bateria": 0.05,
    "Troca de conector": 0.05,
    "Reparo de placa": 0.30,
    "Limpeza de oxidação": 0.25,
    "Reinstalação de software": 0.05,
}

TECNICOS = ["Felipe", "Carlos Eduardo"]  # Felipe é o dono e também conserta

# Reparos que às vezes ficam esperando peça
REPAROS_COM_PECA = ["Troca de tela", "Reparo de placa"]
CHANCE_ESPERAR_PECA = 0.15
DIAS_PECA = (3, 7)
DIAS_ATE_RETIRADA = (0, 5)

# Alguns clientes demoram muito para buscar o aparelho ("aparelhos esquecidos")
CHANCE_ESQUECIDO = 0.04
DIAS_ESQUECIDO = (30, 150)

# Clientes (anônimos: só um código, sem nome, telefone ou CPF)
CHANCE_CLIENTE_VOLTAR = 0.25  # chance de a OS ser de um cliente que já veio antes
ORIGENS = {
    "Indicação": 0.35,
    "Instagram": 0.25,
    "Passou na frente": 0.20,
    "Google": 0.15,
    "Outros": 0.05,
}

# ---------------- 1. Datas de entrada ----------------

hoje = pd.Timestamp(DATA_HOJE)
dias = pd.date_range(DATA_INICIO, DATA_HOJE)
dias = dias[dias.dayofweek != 6]  # tira os domingos

datas_entrada = []
for dia in dias:
    media = MEDIA_POR_DIA * PESO_DIA_SEMANA[dia.dayofweek]
    if dia.month in (12, 1):
        media = media * AUMENTO_DEZ_JAN
    quantidade = np.random.poisson(media)  # número de aparelhos no dia
    datas_entrada += [dia] * quantidade

n = len(datas_entrada)

# ---------------- 2. Sorteio de marca, modelo, defeito e técnico ----------------

nomes_marcas = list(MARCAS.keys())
chances_marcas = [MARCAS[m][0] for m in nomes_marcas]
marcas = np.random.choice(nomes_marcas, size=n, p=chances_marcas)


def sortear_modelo(marca):
    """Sorteia um modelo: o primeiro da lista é o mais comum, o último o menos comum."""
    lista = MARCAS[marca][1]
    pesos = np.arange(len(lista), 0, -1)  # ex.: 8, 7, 6, ..., 1
    return np.random.choice(lista, p=pesos / pesos.sum())


modelos = [sortear_modelo(m) for m in marcas]

nomes_defeitos = list(DEFEITOS.keys())
chances_defeitos = [DEFEITOS[d][1] for d in nomes_defeitos]
defeitos = np.random.choice(nomes_defeitos, size=n, p=chances_defeitos)

tecnicos = np.random.choice(TECNICOS, size=n)

# ---------------- 3. Clientes ----------------

clientes = []        # cliente de cada OS
origem_cliente = {}  # como cada cliente conheceu a loja
for i in range(n):
    if clientes and np.random.rand() < CHANCE_CLIENTE_VOLTAR:
        cliente = np.random.choice(list(origem_cliente.keys()))  # cliente antigo voltando
    else:
        cliente = f"CLI-{len(origem_cliente) + 1:04d}"  # cliente novo
        origem_cliente[cliente] = np.random.choice(list(ORIGENS.keys()), p=list(ORIGENS.values()))
    clientes.append(cliente)

# ---------------- 4. Monta cada OS ----------------

linhas = []
for i in range(n):
    entrada = datas_entrada[i]
    marca = marcas[i]
    defeito = defeitos[i]
    tecnico = tecnicos[i]
    tipo, _, preco_min, preco_max, dias_min, dias_max, chance_retorno = DEFEITOS[defeito]

    # Preço (Apple mais caro) e custo da peça
    valor = np.random.uniform(preco_min, preco_max)
    if marca == "Apple":
        valor = valor * AUMENTO_APPLE
    valor = round(valor, 2)
    custo = round(valor * np.random.uniform(*CUSTO_PECA[tipo]), 2)

    # Dias de reparo (+ espera de peça em alguns casos)
    dias_reparo = np.random.randint(dias_min, dias_max + 1)
    esperou_peca = tipo in REPAROS_COM_PECA and np.random.rand() < CHANCE_ESPERAR_PECA
    if esperou_peca:
        dias_reparo += np.random.randint(DIAS_PECA[0], DIAS_PECA[1] + 1)

    # Dias até o cliente buscar (alguns esquecem o aparelho)
    if np.random.rand() < CHANCE_ESQUECIDO:
        dias_retirada = np.random.randint(DIAS_ESQUECIDO[0], DIAS_ESQUECIDO[1] + 1)
    else:
        dias_retirada = np.random.randint(DIAS_ATE_RETIRADA[0], DIAS_ATE_RETIRADA[1] + 1)

    conclusao = entrada + pd.Timedelta(days=dias_reparo)
    entrega = conclusao + pd.Timedelta(days=dias_retirada)

    # Status conforme o orçamento e as datas em relação a "hoje"
    if np.random.rand() < CHANCE_RECUSA[tipo]:
        status = "Orçamento recusado"  # valor = quanto foi orçado; nenhuma peça usada
        custo = 0.0
        conclusao = None
        entrega = None
    elif np.random.rand() < CHANCE_CANCELADO:
        status = "Cancelado"
        valor = 0.0
        custo = 0.0
        conclusao = None
        entrega = None
    elif conclusao > hoje:
        status = "Aguardando peça" if esperou_peca else "Em andamento"
        conclusao = None
        entrega = None
    elif entrega > hoje:
        status = "Pronto"
        entrega = None
    else:
        status = "Entregue"

    # Retorno na garantia só para OS entregues
    retorno = ""
    if status == "Entregue":
        retorno = "Sim" if np.random.rand() < chance_retorno else "Não"

    linhas.append({
        "os_id": f"OS-{i + 1:04d}",
        "data_entrada": entrada.strftime("%Y-%m-%d"),
        "data_conclusao": conclusao.strftime("%Y-%m-%d") if conclusao is not None else "",
        "data_entrega": entrega.strftime("%Y-%m-%d") if entrega is not None else "",
        "cliente_id": clientes[i],
        "origem_cliente": origem_cliente[clientes[i]],
        "marca": marca,
        "modelo": modelos[i],
        "defeito": defeito,
        "tipo_reparo": tipo,
        "tecnico": tecnico,
        "status": status,
        "valor": valor,
        "custo_peca": custo,
        "retorno_garantia": retorno,
    })

df = pd.DataFrame(linhas)

# ---------------- 5. Erros de propósito ----------------
# "Sujamos" a base para a etapa de limpeza ter o que corrigir.

CHANCE_DATA_BR = 0.10      # datas no formato DD/MM/AAAA
CHANCE_MARCA_ERRADA = 0.08
CHANCE_VALOR_TEXTO = 0.10  # valores como "R$ 350,00"
CHANCE_SEM_TECNICO = 0.03
QTD_DUPLICADAS = 30

# Jeitos errados de escrever cada marca
MARCAS_ERRADAS = {
    "Samsung": ["samsung", "SAMSUNG", "Sansung"],
    "Apple": ["apple", "iPhone"],
    "Motorola": ["moto"],
    "Xiaomi": ["XIAOMI"],
}

# 1. Algumas datas no formato DD/MM/AAAA
for coluna in ["data_entrada", "data_conclusao", "data_entrega"]:
    for i in df.index:
        data = df.loc[i, coluna]
        if data != "" and np.random.rand() < CHANCE_DATA_BR:
            ano, mes, dia = data.split("-")
            df.loc[i, coluna] = f"{dia}/{mes}/{ano}"

# 2. Algumas marcas escritas diferente
for i in df.index:
    if np.random.rand() < CHANCE_MARCA_ERRADA:
        marca = df.loc[i, "marca"]
        df.loc[i, "marca"] = np.random.choice(MARCAS_ERRADAS[marca])

# 3. Alguns valores como texto (R$ 350,00)
df["valor"] = df["valor"].astype(object)
for i in df.index:
    if np.random.rand() < CHANCE_VALOR_TEXTO:
        valor = df.loc[i, "valor"]
        df.loc[i, "valor"] = f"R$ {valor:.2f}".replace(".", ",")

# 4. Alguns técnicos vazios
for i in df.index:
    if np.random.rand() < CHANCE_SEM_TECNICO:
        df.loc[i, "tecnico"] = ""

# 5. Algumas linhas duplicadas (copiadas e colocadas logo após a original)
duplicadas = df.sample(QTD_DUPLICADAS, random_state=42)
df = pd.concat([df, duplicadas]).sort_values("os_id", kind="stable").reset_index(drop=True)

# ---------------- 6. Salva e confere ----------------

df.to_csv("dados/ordens_servico_bruto.csv", sep=";", index=False)

print("Total de linhas:", len(df))
print("Clientes diferentes:", df["cliente_id"].nunique())
print("\nOS por status:")
print(df["status"].value_counts())
print("\nOS por defeito:")
print(df["defeito"].value_counts())
print("\n10 linhas aleatórias:")
print(df.sample(10, random_state=1).to_string())
print("\nVariações de marca:")
print(df["marca"].value_counts())
