import pandas as pd

df = pd.read_csv("transacoesbtcsimples.csv")

recebimentos = df["destino"].value_counts()

print("Análise de Risco\n")

for carteira, quantidade in recebimentos.items():

    if quantidade >= 3:
        risco = "ALTO"

    elif quantidade >= 2:
        risco = "MEDIO"

    else:
        risco = "BAIXO"

    print(f"{carteira} -> {risco}")