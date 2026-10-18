# Limpa a base bruta de ordens de serviço e salva a versão limpa.
# Cada função corrige um problema e devolve: (base corrigida, quantas linhas foram corrigidas).

import pandas as pd

ARQUIVO_BRUTO = "dados/ordens_servico_bruto.csv"
ARQUIVO_LIMPO = "dados/ordens_servico_limpo.csv"

COLUNAS_DATA = ["data_entrada", "data_conclusao", "data_entrega"]
MARCAS_VALIDAS = ["Samsung", "Apple", "Motorola", "Xiaomi"]

# Escritas erradas conhecidas → marca certa (comparando em minúsculas)
CORRECOES_MARCA = {
    "samsung": "Samsung",
    "sansung": "Samsung",
    "apple": "Apple",
    "iphone": "Apple",
    "motorola": "Motorola",
    "moto": "Motorola",
    "xiaomi": "Xiaomi",
}


def remover_duplicadas(df):
    """Remove linhas repetidas."""
    antes = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    return df, antes - len(df)


def corrigir_datas(df):
    """Converte as colunas de data aceitando AAAA-MM-DD e DD/MM/AAAA."""
    df = df.copy()
    # Linhas que têm pelo menos uma data no formato brasileiro
    tem_formato_br = df[COLUNAS_DATA].apply(lambda col: col.str.contains("/", na=False)).any(axis=1)

    for coluna in COLUNAS_DATA:
        formato_iso = pd.to_datetime(df[coluna], format="%Y-%m-%d", errors="coerce")
        formato_br = pd.to_datetime(df[coluna], format="%d/%m/%Y", errors="coerce")
        df[coluna] = formato_iso.fillna(formato_br)  # usa o que funcionar
    return df, int(tem_formato_br.sum())


def padronizar_marcas(df):
    """Tira espaços, ajusta maiúsculas e corrige erros de digitação nas marcas."""
    df = df.copy()
    original = df["marca"]
    df["marca"] = original.str.strip().str.lower().map(CORRECOES_MARCA)
    return df, int((df["marca"] != original).sum())


def converter_valores(df):
    """Transforma valores como 'R$ 350,00' em número (350.0)."""
    df = df.copy()
    em_texto = df["valor"].str.contains("R\\$", na=False)
    df["valor"] = (
        df["valor"]
        .str.replace("R$", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
        .astype(float)
    )
    return df, int(em_texto.sum())


def preencher_tecnico(df):
    """Técnico vazio vira 'Não informado'."""
    df = df.copy()
    vazios = df["tecnico"].isna()
    df["tecnico"] = df["tecnico"].fillna("Não informado")
    return df, int(vazios.sum())


def criar_colunas(df):
    """Cria dias_reparo (conclusão - entrada) e mes (mês da entrada, ex.: 2026-03)."""
    df = df.copy()
    df["dias_reparo"] = (df["data_conclusao"] - df["data_entrada"]).dt.days
    df["mes"] = df["data_entrada"].dt.strftime("%Y-%m")
    return df, len(df)
