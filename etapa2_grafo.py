import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

df = pd.read_csv("transacoesbtcsimples.csv")

G = nx.from_pandas_edgelist(
    df,
    source="origem",
    target="destino",
    edge_attr="valor",
    create_using=nx.DiGraph()
)

plt.figure(figsize=(10,7))

pos = nx.spring_layout(G, k=2, seed=42)

cores = []

for no in G.nodes():
    if no == "ransom_wallet":
        cores.append("red")
    else:
        cores.append("silver")

nx.draw_networkx_nodes(
    G,
    pos,
    node_color=cores,
    node_size=2000
)

nx.draw_networkx_edges(
    G,
    pos,
    arrows=True,
    arrowsize=20
)

nx.draw_networkx_labels(
    G,
    pos,
    font_size=11
)

labels = nx.get_edge_attributes(G, "valor")

nx.draw_networkx_edge_labels(
    G,
    pos,
    edge_labels=labels
)

plt.title("Rede de Transações Bitcoin")
plt.axis("off")
plt.tight_layout()

plt.show()

plt.show()

print("Grafo gerado com sucesso!")