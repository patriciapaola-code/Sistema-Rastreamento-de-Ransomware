from networkx.utils import UnionFind
import networkx as nx
import pandas as pd
import numpy as np
import json

# =========================
# HEURÍSTICAS DE TRANSFORMAÇÃO
# =========================

def heuristicaMultiInput(G):
    uf = UnionFind()
    tx_inputs = {}

    # Agrupa todas as origens (inputs) pelo ID da transação (txid/key)
    for origem, destino, chave, dados in G.edges(keys=True, data=True):
        if dados.get("tipo") != "input":
            continue

        txid = dados.get("txid")
        if not txid:
            continue

        if txid not in tx_inputs:
            tx_inputs[txid] = set()

        tx_inputs[txid].add(origem)

    # Se houver mais de uma origem para a mesma transação, unifica sob a mesma entidade
    for txid, origens in tx_inputs.items():
        origens_lista = list(origens)
        if len(origens_lista) > 1:
            principal = origens_lista[0]
            for carteira in origens_lista[1:]:
                uf.union(principal, carteira)
    return uf

def aplicarChangeAddress(G):
    G_novo = G.copy()
    
    for no in list(G.nodes()):
        if no not in G_novo: 
            continue
            
        sucessores = sorted(set(G_novo.successors(no)))
        
        # Só avalia se houver exatamente 2 carteiras de destino únicas
        if len(sucessores) == 2:
            destino1, destino2 = sucessores[0], sucessores[1]
            
            # Funde o nó se um dos destinos for uma carteira "folha" (novo endereço de troco)
            if G_novo.out_degree(destino1) == 0:
                G_novo = nx.contracted_nodes(G_novo, no, destino1, self_loops=False)
            elif G_novo.out_degree(destino2) == 0:
                G_novo = nx.contracted_nodes(G_novo, no, destino2, self_loops=False)
                
    return G_novo

def aplicarValores(G):
    valores = [dados.get("valor", 0) for _, _, _, dados in G.edges(keys=True, data=True)]
    
    if not valores:
        return G
        
    mediana = np.median(valores)

    for origem, destino, txid, dados in G.edges(keys=True, data=True):
        valor = dados.get("valor", 0)
        
        if 0.5 * mediana <= valor <= 1.5 * mediana:
            dados["valor_semelhante"] = True
        else:
            dados["valor_semelhante"] = False
            
    return G

def aplicarTempo(G, janela=2592000):
    G_novo = nx.MultiDiGraph()
    timestamps = [
        dados["timestamp"] 
        for _, _, _, dados in G.edges(keys=True, data=True) 
        if dados.get("timestamp") is not None
    ]

    if not timestamps:
        return G

    referencia = np.median(timestamps)

    for origem, destino, txid, dados in G.edges(keys=True, data=True):
        timestamp = dados.get("timestamp")
        
        if timestamp is None:
            continue
        
        if abs(timestamp - referencia) <= janela:
            G_novo.add_edge(origem, destino, key=txid, **dados)
            
    return G_novo

def aplicarChain(G):
    G_novo = G.copy()
    
    for no in list(G.nodes()):
        if no not in G_novo: 
            continue
        
        entradas_unicas = list(set(G_novo.predecessors(no)))
        saidas_unicas = list(set(G_novo.successors(no)))

        if len(entradas_unicas) == 1 and len(saidas_unicas) == 1:
            pred = entradas_unicas[0]
            succ = saidas_unicas[0]

            if pred != succ:
                valor_total = sum(d.get("valor", 0) for _, _, d in G_novo.edges(no, data=True))
                G_novo.add_edge(pred, succ, key=f"fused_{no}", valor=valor_total)
                G_novo.remove_node(no)
                
    return G_novo

# =========================
# HEURÍSTICAS DE ANÁLISE
# =========================

def analisarFanIn(G):
    fanin = {}
    for no in G.nodes():
        grau_entrada_unico = len(set(G.predecessors(no)))
        if grau_entrada_unico >= 3:
            fanin[no] = grau_entrada_unico
    return fanin

def analisarFanOut(G):
    fanout = {}
    for no in G.nodes():
        grau_saida_unico = len(set(G.successors(no)))
        if grau_saida_unico >= 3:
            fanout[no] = grau_saida_unico
    return fanout

def analisarPageRank(G):
    G_simples = nx.DiGraph(G)
    return nx.pagerank(G_simples, alpha=0.85)

def analisarBetweenness(G):
    G_simples = nx.DiGraph(G)
    return nx.betweenness_centrality(G_simples)

def analisarCloseness(G):
    G_simples = nx.DiGraph(G)
    return nx.closeness_centrality(G_simples)

def analisarDegree(G):
    G_simples = nx.DiGraph(G)
    return nx.degree_centrality(G_simples)

def analisarClusters(G):
    G_simples = nx.DiGraph(G)
    return list(nx.weakly_connected_components(G_simples))

def analisarChain(G):
    chains = []
    for no in G.nodes():
        entradas_unicas = set(G.predecessors(no))
        saidas_unicas = set(G.successors(no))
        
        if len(entradas_unicas) == 1 and len(saidas_unicas) == 1:
            chains.append(no)
    return chains

def detectarKeyAddresses(G):
    G_simples = nx.DiGraph(G)
    pagerank = nx.pagerank(G_simples)
    
    key_addresses = {no: score for no, score in pagerank.items() if score > 0.01}
    return key_addresses

def normalizar(valor, maior):
    if maior <= 0:
        return 0
    return valor / maior

def resolverCarteiraInicial(carteira_inicial, uf=None):
    if uf is None:
        return carteira_inicial

    return uf[carteira_inicial] if carteira_inicial in uf else carteira_inicial

def classificarRisco(score):
    if score >= 70:
        return "ALTO"
    if score >= 40:
        return "MEDIO"
    if score > 0:
        return "BAIXO"
    return "SEM EVIDENCIA"

def calcularScoreRisco(G, carteira_inicial):
    if G.number_of_nodes() == 0:
        return {}

    G_simples = nx.DiGraph(G)
    G_nao_direcionado = G_simples.to_undirected()

    if carteira_inicial in G_nao_direcionado:
        distancias = nx.single_source_shortest_path_length(
            G_nao_direcionado,
            carteira_inicial
        )
    else:
        distancias = {}

    try:
        pagerank = nx.pagerank(G_simples, alpha=0.85)
    except Exception:
        pagerank = {no: 0 for no in G.nodes()}

    try:
        betweenness = nx.betweenness_centrality(G_simples)
    except Exception:
        betweenness = {no: 0 for no in G.nodes()}

    graus = {
        no: len(set(G.predecessors(no))) + len(set(G.successors(no)))
        for no in G.nodes()
    }
    maior_grau = max(graus.values(), default=0)
    maior_pagerank = max(pagerank.values(), default=0)
    maior_betweenness = max(betweenness.values(), default=0)

    chain_nodes = set(analisarChain(G))
    scores = {}

    for no in G.nodes():
        motivos = []
        score = 0

        if no == carteira_inicial:
            score += 100
            motivos.append("carteira maliciosa inicial")
        else:
            distancia = distancias.get(no)
            if distancia is not None:
                score_distancia = max(0, 35 - (distancia * 8))
                score += score_distancia
                motivos.append(f"distancia {distancia} da carteira inicial")

        grau_score = normalizar(graus.get(no, 0), maior_grau) * 20
        if grau_score >= 8:
            motivos.append("muitas conexoes")
        score += grau_score

        pr_score = normalizar(pagerank.get(no, 0), maior_pagerank) * 15
        if pr_score >= 6:
            motivos.append("PageRank relevante")
        score += pr_score

        between_score = normalizar(betweenness.get(no, 0), maior_betweenness) * 15
        if between_score >= 6:
            motivos.append("atua como intermediaria")
        score += between_score

        arestas = list(G.in_edges(no, keys=True, data=True)) + list(G.out_edges(no, keys=True, data=True))
        if any(dados.get("valor_semelhante") for _, _, _, dados in arestas):
            score += 10
            motivos.append("transaciona valores semelhantes")

        if no in chain_nodes:
            score += 5
            motivos.append("participa de cadeia simples")

        score = float(min(100, round(score, 2)))
        scores[no] = {
            "score": score,
            "risco": classificarRisco(score),
            "motivos": motivos if motivos else ["sem evidencia forte"]
        }

    return scores

def imprimirRelatorioRisco(scores, limite=10):
    ordenados = sorted(
        scores.items(),
        key=lambda item: item[1]["score"],
        reverse=True
    )

    print("\n===== RELATORIO DE RISCO =====")

    for posicao, (carteira, dados) in enumerate(ordenados[:limite], start=1):
        motivos = "; ".join(dados["motivos"][:4])
        print(
            f"{posicao}. {carteira} | score={dados['score']} | "
            f"risco={dados['risco']} | motivos: {motivos}"
        )

def encontrarTrajetoriasProvaveis(G, carteira_inicial, scores, limite=3):
    if G.number_of_nodes() == 0 or carteira_inicial not in G:
        return []

    G_simples = nx.DiGraph(G)
    trajetorias = []

    for no in G_simples.nodes():
        if no == carteira_inicial:
            continue

        if not nx.has_path(G_simples, carteira_inicial, no):
            continue

        caminho = nx.shortest_path(G_simples, carteira_inicial, no)
        if len(caminho) < 2:
            continue

        entradas = len(set(G.predecessors(no)))
        saidas = len(set(G.successors(no)))
        score_no = scores.get(no, {}).get("score", 0)

        score_destino = score_no

        if saidas == 0:
            score_destino += 25
        elif saidas <= 1:
            score_destino += 10

        if entradas >= 3:
            score_destino += 15

        score_destino += min(len(caminho) * 3, 15)

        trajetorias.append({
            "destino": no,
            "caminho": caminho,
            "score_destino": float(round(min(score_destino, 100), 2)),
            "score_risco": float(score_no),
            "entradas": entradas,
            "saidas": saidas
        })

    trajetorias.sort(
        key=lambda item: item["score_destino"],
        reverse=True
    )

    return trajetorias[:limite]

def imprimirTrajetorias(trajetorias):
    print("\n===== TRAJETORIAS PROVAVEIS =====")

    if not trajetorias:
        print("Nenhuma trajetoria provavel encontrada a partir da carteira inicial.")
        return

    for posicao, dados in enumerate(trajetorias, start=1):
        caminho = " -> ".join(dados["caminho"])
        print(
            f"{posicao}. destino={dados['destino']} | "
            f"score_destino={dados['score_destino']} | "
            f"score_risco={dados['score_risco']} | "
            f"entradas={dados['entradas']} | saidas={dados['saidas']}"
        )
        print(f"   caminho: {caminho}")

def topItens(dados, limite=10):
    ordenados = sorted(
        dados.items(),
        key=lambda item: item[1],
        reverse=True
    )[:limite]

    return [
        {
            "carteira": chave,
            "valor": float(valor)
        }
        for chave, valor in ordenados
    ]

def calcularSimilaridadeValores(valores):
    valores = [valor for valor in valores if valor is not None and valor > 0]

    if len(valores) < 2:
        return 0

    media = float(np.mean(valores))
    if media == 0:
        return 0

    desvio = float(np.std(valores))
    coeficiente_variacao = desvio / media

    return round(max(0, 1 - coeficiente_variacao), 4)

def detectarPossiveisMixers(G, limite=10):
    candidatos = {}
    tx_por_no = {}

    for origem, destino, chave, dados in G.edges(keys=True, data=True):
        txid = dados.get("txid")
        if not txid:
            continue

        if txid not in tx_por_no:
            tx_por_no[txid] = {
                "inputs": set(),
                "outputs": set(),
                "valores": []
            }

        if dados.get("tipo") == "input":
            tx_por_no[txid]["inputs"].add(origem)
            tx_por_no[txid]["outputs"].add(destino)
        elif dados.get("tipo") == "output":
            tx_por_no[txid]["inputs"].add(origem)
            tx_por_no[txid]["outputs"].add(destino)

        tx_por_no[txid]["valores"].append(dados.get("valor", 0))

    for txid, dados_tx in tx_por_no.items():
        qtd_inputs = len(dados_tx["inputs"])
        qtd_outputs = len(dados_tx["outputs"])
        similaridade = calcularSimilaridadeValores(dados_tx["valores"])

        if qtd_inputs >= 3 and qtd_outputs >= 3:
            score = 35 + min(qtd_inputs * 5, 25) + min(qtd_outputs * 5, 25)
            score += similaridade * 15

            envolvidos = dados_tx["inputs"].union(dados_tx["outputs"])
            for carteira in envolvidos:
                if carteira not in candidatos:
                    candidatos[carteira] = {
                        "carteira": carteira,
                        "score_mixer": 0,
                        "motivos": set(),
                        "txids": set()
                    }

                candidatos[carteira]["score_mixer"] += score
                candidatos[carteira]["txids"].add(txid)
                candidatos[carteira]["motivos"].add(
                    f"transacao com {qtd_inputs} inputs e {qtd_outputs} outputs"
                )

                if similaridade >= 0.75:
                    candidatos[carteira]["motivos"].add("outputs com valores parecidos")

    for no in G.nodes():
        entradas = len(set(G.predecessors(no)))
        saidas = len(set(G.successors(no)))
        arestas = list(G.in_edges(no, keys=True, data=True)) + list(G.out_edges(no, keys=True, data=True))
        valores = [dados.get("valor", 0) for _, _, _, dados in arestas]
        similaridade = calcularSimilaridadeValores(valores)

        if entradas >= 4 and saidas >= 4:
            if no not in candidatos:
                candidatos[no] = {
                    "carteira": no,
                    "score_mixer": 0,
                    "motivos": set(),
                    "txids": set()
                }

            candidatos[no]["score_mixer"] += 30 + min(entradas + saidas, 30)
            candidatos[no]["motivos"].add(f"fan-in {entradas} e fan-out {saidas}")

            if similaridade >= 0.65:
                candidatos[no]["score_mixer"] += 15
                candidatos[no]["motivos"].add("valores de entrada/saida semelhantes")

    resultado = []

    for dados in candidatos.values():
        resultado.append({
            "carteira": dados["carteira"],
            "score_mixer": float(round(min(dados["score_mixer"], 100), 2)),
            "motivos": sorted(dados["motivos"]),
            "txids": sorted(dados["txids"])
        })

    resultado.sort(
        key=lambda item: item["score_mixer"],
        reverse=True
    )

    return resultado[:limite]

# =========================
# ANÁLISE SOBRE DATAFRAME
# =========================

def analisarBurst(df):
    if df.empty or "timestamp" not in df.columns:
        return pd.Series(dtype=int)
        
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    por_minuto = df.groupby(pd.Grouper(key="timestamp", freq="1min")).size()
    return por_minuto

def analisarTempo(df):
    if df.empty or "timestamp" not in df.columns:
        return pd.Series(dtype=float)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    diferenca = df["timestamp"].diff().dt.total_seconds()
    
    return diferenca

def analisarValores(df):
    if df.empty or "valor" not in df.columns:
        return pd.DataFrame()

    media = df["valor"].mean()
    tolerancia = media * 0.1
    semelhantes = df[abs(df["valor"] - media) < tolerancia]
    
    return semelhantes
