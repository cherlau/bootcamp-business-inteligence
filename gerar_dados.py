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
CHANCE_CANCELADO = 0.05

# Marca: (chance, modelos)
MARCAS = {
    "Samsung": (0.40, ["Galaxy A14", "Galaxy A54", "Galaxy S23", "Galaxy M34"]),
    "Apple": (0.30, ["iPhone 11", "iPhone 12", "iPhone 13", "iPhone 14"]),
    "Motorola": (0.20, ["Moto G22", "Moto G54", "Moto E13"]),
    "Xiaomi": (0.10, ["Redmi Note 12", "Redmi 12C", "Poco X5"]),
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

TECNICOS = ["Carlos", "Juliana", "Rafael", "Marcos"]
TECNICO_NOVO = "Marcos"  # tem o dobro de chance de retorno

# Reparos que às vezes ficam esperando peça
REPAROS_COM_PECA = ["Troca de tela", "Reparo de placa"]
CHANCE_ESPERAR_PECA = 0.15
DIAS_PECA = (3, 7)
DIAS_ATE_RETIRADA = (0, 5)

# ---------------- 1. Datas de entrada ----------------

hoje = pd.Timestamp(DATA_HOJE)
dias = pd.date_range(DATA_INICIO, DATA_HOJE)
dias = dias[dias.dayofweek != 6]  # tira os domingos

datas_entrada = []
for dia in dias:
    media = MEDIA_POR_DIA
    if dia.month in (12, 1):
        media = media * AUMENTO_DEZ_JAN
    quantidade = np.random.poisson(media)  # número de aparelhos no dia
    datas_entrada += [dia] * quantidade

n = len(datas_entrada)

# ---------------- 2. Sorteio de marca, defeito e técnico ----------------

nomes_marcas = list(MARCAS.keys())
chances_marcas = [MARCAS[m][0] for m in nomes_marcas]
marcas = np.random.choice(nomes_marcas, size=n, p=chances_marcas)
modelos = [np.random.choice(MARCAS[m][1]) for m in marcas]

nomes_defeitos = list(DEFEITOS.keys())
chances_defeitos = [DEFEITOS[d][1] for d in nomes_defeitos]
defeitos = np.random.choice(nomes_defeitos, size=n, p=chances_defeitos)

tecnicos = np.random.choice(TECNICOS, size=n)

# ---------------- 3. Monta cada OS ----------------

linhas = []
for i in range(n):
    entrada = datas_entrada[i]
    marca = marcas[i]
    defeito = defeitos[i]
    tecnico = tecnicos[i]
    tipo, _, preco_min, preco_max, dias_min, dias_max, chance_retorno = DEFEITOS[defeito]

    # Preço (Apple mais caro)
    valor = np.random.uniform(preco_min, preco_max)
    if marca == "Apple":
        valor = valor * AUMENTO_APPLE
    valor = round(valor, 2)

    # Dias de reparo (+ espera de peça em alguns casos)
    dias_reparo = np.random.randint(dias_min, dias_max + 1)
    esperou_peca = tipo in REPAROS_COM_PECA and np.random.rand() < CHANCE_ESPERAR_PECA
    if esperou_peca:
        dias_reparo += np.random.randint(DIAS_PECA[0], DIAS_PECA[1] + 1)

    conclusao = entrada + pd.Timedelta(days=dias_reparo)
    entrega = conclusao + pd.Timedelta(days=np.random.randint(DIAS_ATE_RETIRADA[0], DIAS_ATE_RETIRADA[1] + 1))

    # Status conforme as datas em relação a "hoje"
    if np.random.rand() < CHANCE_CANCELADO:
        status = "Cancelado"
        valor = 0.0
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
        if tecnico == TECNICO_NOVO:
            chance_retorno = chance_retorno * 2
        retorno = "Sim" if np.random.rand() < chance_retorno else "Não"

    linhas.append({
        "os_id": f"OS-{i + 1:04d}",
        "data_entrada": entrada.strftime("%Y-%m-%d"),
        "data_conclusao": conclusao.strftime("%Y-%m-%d") if conclusao is not None else "",
        "data_entrega": entrega.strftime("%Y-%m-%d") if entrega is not None else "",
        "marca": marca,
        "modelo": modelos[i],
        "defeito": defeito,
        "tipo_reparo": tipo,
        "tecnico": tecnico,
        "status": status,
        "valor": valor,
        "retorno_garantia": retorno,
    })

df = pd.DataFrame(linhas)

# ---------------- 4. Salva e confere ----------------

df.to_csv("dados/ordens_servico_bruto.csv", sep=";", index=False)

print("Total de OS:", len(df))
print("\nOS por status:")
print(df["status"].value_counts())
print("\nOS por defeito:")
print(df["defeito"].value_counts())
