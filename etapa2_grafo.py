import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


def filtrarNome(G):
    labels = {}

    for i, no in enumerate(G.nodes()):
        labels[no] = f"wallet_{i}"

    return labels


def filtrarNomeComScore(G, scores):
    labels = {}

    for i, no in enumerate(G.nodes()):
        score = scores.get(no, {}).get("score", 0)
        labels[no] = f"wallet_{i}\n{score}"

    return labels


def adicionarLegenda(itens):
    plt.legend(
        handles=itens,
        loc="upper right",
        frameon=True,
        title="Legenda"
    )


def corPorRisco(score):
    if score >= 70:
        return "red"
    if score >= 40:
        return "orange"
    if score > 0:
        return "lightgreen"
    return "lightgray"


def gerarGrafoFiltrado(
    G_filtrado,
    heuristica_nome,
    scores=None,
    carteira_principal=None,
    caminho_destacado=None
):
    plt.figure(figsize=(14, 10))

    pos = nx.spring_layout(
        G_filtrado,
        k=2,
        seed=42
    )

    cores = []
    tamanhos = []

    for no in G_filtrado.nodes():
        if scores:
            score = scores.get(no, {}).get("score", 0)
            cores.append(corPorRisco(score))
            tamanhos.append(500 + score * 12)
            continue

        vizinhos = set(G_filtrado.predecessors(no))
        vizinhos.update(G_filtrado.successors(no))
        grau_real = len(vizinhos)

        if grau_real >= 8:
            cores.append("red")
        elif grau_real >= 4:
            cores.append("orange")
        else:
            cores.append("lightgreen")

        tamanhos.append(500 + grau_real * 150)

    nx.draw_networkx_nodes(
        G_filtrado,
        pos,
        node_color=cores,
        node_size=tamanhos
    )

    nx.draw_networkx_edges(
        G_filtrado,
        pos,
        arrows=True,
        arrowsize=15
    )

    for no in G_filtrado.nodes():
        vizinhos = set(G_filtrado.predecessors(no))
        vizinhos.update(G_filtrado.successors(no))
        grau_real = len(vizinhos)
        risco_alto = scores and scores.get(no, {}).get("score", 0) >= 70

        if risco_alto or (not scores and grau_real >= 8):
            vizinhos = list(vizinhos)[:8]

            nx.draw_networkx_nodes(
                G_filtrado,
                pos,
                nodelist=vizinhos,
                node_color="yellow",
                node_size=1200
            )

            arestas = []

            for v in vizinhos:
                if G_filtrado.has_edge(no, v):
                    arestas.append((no, v))

                if G_filtrado.has_edge(v, no):
                    arestas.append((v, no))

            nx.draw_networkx_edges(
                G_filtrado,
                pos,
                edgelist=arestas,
                edge_color="red",
                width=4,
                arrows=True,
                arrowsize=20
            )

    if caminho_destacado and len(caminho_destacado) >= 2:
        arestas_caminho = list(zip(caminho_destacado, caminho_destacado[1:]))

        nx.draw_networkx_edges(
            G_filtrado,
            pos,
            edgelist=arestas_caminho,
            edge_color="blue",
            width=5,
            arrows=True,
            arrowsize=24
        )

        nx.draw_networkx_nodes(
            G_filtrado,
            pos,
            nodelist=caminho_destacado,
            node_color="deepskyblue",
            node_size=1500,
            edgecolors="black",
            linewidths=1.5
        )

    nx.draw_networkx_labels(
        G_filtrado,
        pos,
        labels=filtrarNomeComScore(G_filtrado, scores) if scores else filtrarNome(G_filtrado),
        font_size=8
    )

    if scores:
        adicionarLegenda([
            Patch(facecolor="red", label="Risco alto (score >= 70)"),
            Patch(facecolor="orange", label="Risco medio (40 a 69)"),
            Patch(facecolor="lightgreen", label="Risco baixo (1 a 39)"),
            Patch(facecolor="lightgray", label="Sem evidencia"),
            Patch(facecolor="yellow", label="Vizinho de carteira de alto risco"),
            Line2D([0], [0], color="red", lw=4, label="Ligacao envolvendo carteira de alto risco"),
            Line2D([0], [0], color="blue", lw=5, label="Trajetoria provavel")
        ])
    else:
        adicionarLegenda([
            Patch(facecolor="red", label="No com 8 ou mais conexoes"),
            Patch(facecolor="orange", label="No com 4 a 7 conexoes"),
            Patch(facecolor="lightgreen", label="No com ate 3 conexoes"),
            Patch(facecolor="yellow", label="Vizinho destacado de no critico"),
            Line2D([0], [0], color="red", lw=4, label="Aresta destacada")
        ])

    plt.title(f"Grafo Filtrado por Heuristica de {heuristica_nome}")
    plt.axis("off")
    plt.tight_layout()
    plt.show()


def gerarGrafo(G, carteira_principal, scores=None):
    plt.figure(figsize=(12, 8))

    pos = nx.spring_layout(
        G,
        k=1.5,
        seed=42
    )

    cores = []
    tamanhos = []

    for no in G.nodes():
        if scores:
            score = scores.get(no, {}).get("score", 0)
            cores.append(corPorRisco(score))
            tamanhos.append(600 + score * 10)
        elif no == carteira_principal:
            cores.append("red")
            tamanhos.append(1000)
        elif G.in_degree(no) >= 3:
            cores.append("orange")
            tamanhos.append(1000)
        else:
            cores.append("lightblue")
            tamanhos.append(1000)

    nx.draw_networkx_nodes(
        G,
        pos,
        node_color=cores,
        node_size=tamanhos
    )

    nx.draw_networkx_edges(
        G,
        pos,
        arrows=True,
        arrowsize=15
    )

    nx.draw_networkx_labels(
        G,
        pos,
        labels=filtrarNomeComScore(G, scores) if scores else filtrarNome(G),
        font_size=8
    )

    labels = nx.get_edge_attributes(
        G,
        "valor"
    )

    nx.draw_networkx_edge_labels(
        G,
        pos,
        edge_labels=labels,
        font_size=7
    )

    if scores:
        adicionarLegenda([
            Patch(facecolor="red", label="Risco alto (score >= 70)"),
            Patch(facecolor="orange", label="Risco medio (40 a 69)"),
            Patch(facecolor="lightgreen", label="Risco baixo (1 a 39)"),
            Patch(facecolor="lightgray", label="Sem evidencia"),
            Line2D([0], [0], color="black", lw=1, label="Transacao")
        ])
    else:
        adicionarLegenda([
            Patch(facecolor="red", label="Carteira principal"),
            Patch(facecolor="orange", label="No com 3 ou mais entradas"),
            Patch(facecolor="lightblue", label="Demais carteiras"),
            Line2D([0], [0], color="black", lw=1, label="Transacao")
        ])

    plt.title("Rede de Transacoes Bitcoin - Grafo Bruto")
    plt.axis("off")
    plt.tight_layout()
    plt.show()

    print("Grafo gerado com sucesso!")
