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

# Marca: (chance, modelos do mais comum para o menos comum).
# Modelos vendidos no Brasil entre 2017 e 2024: dos básicos mais populares aos premium.
MARCAS = {
    "Samsung": (0.37, [
        "Galaxy A14", "Galaxy A15", "Galaxy A54", "Galaxy A34", "Galaxy A12", "Galaxy A13",
        "Galaxy A22", "Galaxy A32", "Galaxy A03s", "Galaxy A04s", "Galaxy A05s", "Galaxy A24",
        "Galaxy A25", "Galaxy A35", "Galaxy A55", "Galaxy A23", "Galaxy A53", "Galaxy A52",
        "Galaxy A51", "Galaxy A31", "Galaxy A21s", "Galaxy A11", "Galaxy A10s", "Galaxy A02s",
        "Galaxy A01", "Galaxy A04", "Galaxy A04e", "Galaxy A05", "Galaxy A03", "Galaxy A20s",
        "Galaxy A30s", "Galaxy A71", "Galaxy A72", "Galaxy M12", "Galaxy M13", "Galaxy M14",
        "Galaxy M15", "Galaxy M23", "Galaxy M33", "Galaxy M34", "Galaxy M35", "Galaxy M54",
        "Galaxy S20 FE", "Galaxy S21 FE", "Galaxy S23 FE", "Galaxy S21", "Galaxy S22",
        "Galaxy S23", "Galaxy S24", "Galaxy S22 Ultra", "Galaxy S23 Ultra", "Galaxy S24 Ultra",
        "Galaxy Note 10", "Galaxy Note 20", "Galaxy Z Flip4", "Galaxy Z Flip5", "Galaxy Z Fold5",
    ]),
    "Apple": (0.27, [
        "iPhone 11", "iPhone 13", "iPhone 12", "iPhone XR", "iPhone 14", "iPhone 8",
        "iPhone 7", "iPhone 8 Plus", "iPhone 7 Plus", "iPhone SE (2020)", "iPhone X",
        "iPhone XS", "iPhone XS Max", "iPhone 11 Pro", "iPhone 11 Pro Max", "iPhone 12 Pro",
        "iPhone 12 Pro Max", "iPhone 12 mini", "iPhone 13 Pro", "iPhone 13 Pro Max",
        "iPhone 13 mini", "iPhone SE (2022)", "iPhone 14 Plus", "iPhone 14 Pro",
        "iPhone 14 Pro Max", "iPhone 15", "iPhone 15 Plus", "iPhone 15 Pro", "iPhone 15 Pro Max",
        "iPhone 16", "iPhone 16 Pro",
    ]),
    "Motorola": (0.19, [
        "Moto G54", "Moto G22", "Moto E13", "Moto G84", "Moto G32", "Moto G52", "Moto G23",
        "Moto G24", "Moto G34", "Moto G04", "Moto G14", "Moto G13", "Moto G53", "Moto G73",
        "Moto G42", "Moto G62", "Moto G82", "Moto G60", "Moto G60s", "Moto G50", "Moto G30",
        "Moto G20", "Moto G10", "Moto G9 Play", "Moto G8 Power", "Moto G8 Plus", "Moto E7",
        "Moto E20", "Moto E22", "Moto E32", "Moto E40", "Edge 30", "Edge 40 Neo", "Edge 40",
        "Edge 50", "Razr 40",
    ]),
    "Xiaomi": (0.11, [
        "Redmi Note 12", "Redmi 12C", "Redmi Note 13", "Poco X5", "Redmi 13C", "Redmi Note 11",
        "Redmi Note 10", "Redmi Note 9", "Redmi 9A", "Redmi 9C", "Redmi 10C", "Redmi 12",
        "Redmi 13", "Redmi Note 12 Pro", "Redmi Note 13 Pro", "Redmi Note 8", "Poco X6",
        "Poco X6 Pro", "Poco X3 Pro", "Poco M5", "Poco M6 Pro", "Poco F5", "Xiaomi 12",
        "Xiaomi 13", "Xiaomi 13T", "Xiaomi 14",
    ]),
    "Realme": (0.03, [
        "Realme C55", "Realme C35", "Realme C53", "Realme 11", "Realme C67", "Realme 10",
        "Realme 9i", "Realme C33", "Realme 11 Pro", "Realme GT Master",
    ]),
    "LG": (0.02, [
        "LG K41s", "LG K62", "LG K52", "LG K51s", "LG K22", "LG K50s", "LG K12 Max", "LG Velvet",
    ]),
    "Asus": (0.01, [
        "Zenfone Max Pro M1", "Zenfone 5", "Zenfone Max Shot", "Zenfone 8", "Zenfone 9",
    ]),
}
AUMENTO_APPLE = 1.5  # Apple custa ~50% a mais

# Modelos premium (telas e placas mais caras): conserto ~40% mais caro
PALAVRAS_PREMIUM = ["Pro", "Ultra", "Galaxy S", "Galaxy Note", "Galaxy Z",
                    "Edge", "Razr", "Xiaomi 1", "Poco F", "GT", "Velvet", "Zenfone 8", "Zenfone 9"]
AUMENTO_PREMIUM = 1.4

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

# Alguns clientes demoram muito para buscar o aparelho
CHANCE_RETIRADA_DEMORADA = 0.04
DIAS_RETIRADA_DEMORADA = (30, 150)

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
    """Sorteia um modelo: o primeiro da lista é o mais comum, o último o menos comum.
    Peso = 1 / posição^0,8 → poucos modelos muito comuns e muitos modelos raros (como na vida real)."""
    lista = MARCAS[marca][1]
    pesos = 1 / np.arange(1, len(lista) + 1) ** 0.8
    return np.random.choice(lista, p=pesos / pesos.sum())


def eh_premium(modelo):
    return any(palavra in modelo for palavra in PALAVRAS_PREMIUM)


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

    # Preço (Apple e modelos premium mais caros) e custo da peça
    valor = np.random.uniform(preco_min, preco_max)
    if marca == "Apple":
        valor = valor * AUMENTO_APPLE
    if eh_premium(modelos[i]):
        valor = valor * AUMENTO_PREMIUM
    valor = round(valor, 2)
    custo = round(valor * np.random.uniform(*CUSTO_PECA[tipo]), 2)

    # Dias de reparo (+ espera de peça em alguns casos)
    dias_reparo = np.random.randint(dias_min, dias_max + 1)
    esperou_peca = tipo in REPAROS_COM_PECA and np.random.rand() < CHANCE_ESPERAR_PECA
    if esperou_peca:
        dias_reparo += np.random.randint(DIAS_PECA[0], DIAS_PECA[1] + 1)

    # Dias até o cliente buscar (alguns demoram muito)
    if np.random.rand() < CHANCE_RETIRADA_DEMORADA:
        dias_retirada = np.random.randint(DIAS_RETIRADA_DEMORADA[0], DIAS_RETIRADA_DEMORADA[1] + 1)
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
    "Realme": ["realme", "REALME"],
    "LG": ["lg", "Lg"],
    "Asus": ["asus", "ASUS"],
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
print("Modelos diferentes:", df["modelo"].nunique())
print("\nOS por status:")
print(df["status"].value_counts())
print("\nOS por defeito:")
print(df["defeito"].value_counts())
print("\n10 linhas aleatórias:")
print(df.sample(10, random_state=1).to_string())
print("\nVariações de marca:")
print(df["marca"].value_counts())
