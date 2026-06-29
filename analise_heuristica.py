from networkx.utils import UnionFind
import networkx as nx
import pandas as pd
import numpy as np
import json
from collections import Counter, defaultdict

# =========================
# HEURÍSTICAS DE TRANSFORMAÇÃO
# =========================

def detectarSuspeitaCoinJoin(tx_outputs):
    valores_saida = [v for _, v in tx_outputs if v and v > 0]

    if len(valores_saida) < 3:
        return False, None

    arredondados = [round(v, 8) for v in valores_saida]
    contagem = Counter(arredondados)
    valor_mais_comum, freq = contagem.most_common(1)[0]

    proporcao = freq / len(arredondados)

    if freq >= 3 and proporcao >= 0.5:
        return True, f"{freq} outputs com valor idêntico ({valor_mais_comum})"

    return False, None

def heuristicaMultiInput(G, limite_inputs_mixer=30):
    uf = UnionFind()
    tx_map = {}

    for u, v, k, d in G.edges(keys=True, data=True):
        txid = d.get("txid")
        if not txid:
            continue

        if txid not in tx_map:
            tx_map[txid] = {"inputs": set(), "outputs": []}

        tipo = d.get("tipo")
        valor = d.get("valor", 0)

        if tipo == "input":
            tx_map[txid]["inputs"].add(u)
        elif tipo == "output":
            tx_map[txid]["outputs"].append((v, valor))

    coinjoin_suspeitas = {}  # motivo para alimentar o score de risco depois

    for txid, tx in tx_map.items():
        inputs = list(tx["inputs"])
        outputs = tx["outputs"]

        if len(inputs) <= 1:
            continue

        suspeito, motivo = detectarSuspeitaCoinJoin(outputs)
        if suspeito:
            coinjoin_suspeitas[txid] = {
                "motivo": motivo,
                "carteiras": sorted(inputs)
            }

        # só exclui o union em casos extremos, típicos de serviços de mixing
        if len(inputs) > limite_inputs_mixer:
            continue

        base = inputs[0]
        for carteira in inputs[1:]:
            uf.union(base, carteira)

    return uf, coinjoin_suspeitas
def aplicarChangeAddress(G):
    G_novo = G.copy()
    for no in list(G.nodes()):
        if no not in G_novo:
            continue
        tx_outs = defaultdict(list)
        for u, v, k, d in G_novo.out_edges(no, keys=True, data=True):
            tx_outs[d.get("txid")].append((v, d.get("valor", 0)))

        for txid, dados_edges in tx_outs.items():
            if txid is None or len(dados_edges) != 2:
                continue
            (dest1, val1), (dest2, val2) = dados_edges
            total = val1 + val2
            if total == 0:
                continue
            if val1 < total * 0.3:
                possivel_troco = dest1
            elif val2 < total * 0.3:
                possivel_troco = dest2
            else:
                continue
            if possivel_troco in G_novo and G_novo.degree(possivel_troco) <= 1:
                G_novo = nx.contracted_nodes(G_novo, no, possivel_troco, self_loops=False)
    return G_novo

def aplicarValores(G):
    tx_map = defaultdict(list)

    for u, v, k, d in G.edges(keys=True, data=True):
        txid = d.get("txid")
        if txid is not None:
            tx_map[txid].append(d)

    for txid, edges in tx_map.items():
        valores = [d.get("valor", 0) for d in edges]

        if len(valores) < 2:
            continue

        mediana = np.median(valores)

        for d in edges:
            valor = d.get("valor", 0)
            d["valor_semelhante"] = (0.7 * mediana <= valor <= 1.3 * mediana)

    return G

def aplicarTempo(G, bin_size=7*24*3600):
    G_novo = G.copy()

    edges = [(u, v, k, d) for u, v, k, d in G.edges(keys=True, data=True)
             if d.get("timestamp") is not None]

    if not edges:
        return G_novo

    timestamps = [d["timestamp"] for _, _, _, d in edges]
    t_min = min(timestamps)

    bins = defaultdict(list)

    for u, v, k, d in edges:
        idx = (d["timestamp"] - t_min) // bin_size
        bins[idx].append(d)

    # acha bin de maior atividade
    melhor_bin = max(bins.items(), key=lambda x: len(x[1]))[0]

    for u, v, k, d in G_novo.edges(keys=True, data=True):
        ts = d.get("timestamp")
        if ts is None:
            continue

        idx = (ts - t_min) // bin_size

        if idx == melhor_bin:
            d["burst"] = True
        else:
            d["burst"] = False

    return G_novo

def aplicarChain(G):
    G_novo = G.copy()

    for no in G.nodes():
        entradas = set(G.predecessors(no))
        saidas = set(G.successors(no))

        if len(entradas) == 1 and len(saidas) == 1:
            G_novo.nodes[no]["chain_node"] = True
        else:
            G_novo.nodes[no]["chain_node"] = False

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

def calcularScoreRisco(G, carteira_inicial, coinjoin_suspeitas=None, sensibilidade="Médio", comportamentos=None):
    if G.number_of_nodes() == 0:
        return {}

    # Garante que coinjoin_suspeitas seja sempre um dicionário, mesmo se for None.
    coinjoin_suspeitas = coinjoin_suspeitas or {}
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

    # Limiares baseados no nível de sensibilidade
    if sensibilidade == "Alto":
        limiar_alto = 55
        limiar_medio = 25
    elif sensibilidade == "Baixo":
        limiar_alto = 85
        limiar_medio = 55
    else:
        limiar_alto = 70
        limiar_medio = 40

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

        # Comportamento: Fan-in / Fan-out
        if comportamentos is None or comportamentos.get("fan_in", True) or comportamentos.get("fan_out", True):
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

        # Comportamento: Valores Fracionados / Similaridades
        if comportamentos is None or comportamentos.get("fracionado", True):
            if any(dados.get("valor_semelhante") for _, _, _, dados in arestas):
                score += 10
                motivos.append("transaciona valores semelhantes")

        # Comportamento: Cadeias rápidas / Burst / Temporal
        if comportamentos is None or comportamentos.get("cadeia_rapida", True):
            if any(dados.get("burst") for _, _, _, dados in arestas):
                score += 15
                motivos.append("atividade em janela temporal suspeita")

            if G.nodes[no].get("chain_node", False):
                score += 5
                motivos.append("participa de cadeia simples")

        # Comportamento: Mixers / CoinJoin
        if comportamentos is None or comportamentos.get("mixer", True):
            txids_no = {d.get("txid") for _, _, _, d in arestas if d.get("txid")}
            txids_suspeitos = txids_no & coinjoin_suspeitas.keys()

            if txids_suspeitos:
                score += 8
                motivos.append(
                    f"participou de {len(txids_suspeitos)} transacao(oes) "
                    f"com denominacao suspeita de CoinJoin"
                )

        score = float(min(100, round(score, 2)))

        # Classificação dinâmica de risco baseada na sensibilidade
        if score >= limiar_alto:
            risco = "ALTO"
        elif score >= limiar_medio:
            risco = "MEDIO"
        elif score > 0:
            risco = "BAIXO"
        else:
            risco = "SEM EVIDENCIA"

        scores[no] = {
            "score": score,
            "risco": risco,
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

def encontrarTrajetoriasProvaveis(G, carteira_inicial, scores, limite=5):
    if carteira_inicial not in G:
        return []

    candidatos_destino = sorted(
        (n for n in G.nodes() if n != carteira_inicial),
        key=lambda n: scores.get(n, {}).get("score", 0),
        reverse=True
    )[:20]  # limita o universo de destinos a investigar

    trajetorias = []
    for destino in candidatos_destino:
        try:
            caminho = nx.shortest_path(G, carteira_inicial, destino)
        except nx.NetworkXNoPath:
            continue
        score_medio = np.mean([scores.get(no, {}).get("score", 0) for no in caminho])
        trajetorias.append({
            "destino": destino, "caminho": caminho,
            "score_final": round(score_medio, 2),
            "tamanho_caminho": len(caminho)
        })
        if len(trajetorias) >= limite:
            break
    return trajetorias

def imprimirTrajetorias(trajetorias):
    print("\n===== TRAJETORIAS PROVÁVEIS =====")

    if not trajetorias:
        print("Nenhuma trajetória provável encontrada a partir da carteira inicial.")
        return

    for posicao, dados in enumerate(trajetorias, start=1):
        caminho = " -> ".join(dados["caminho"])

        print(
            f"{posicao}. destino={dados['destino']} | "
            f"score_final={dados['score_final']} | "
            f"score_base_destino={dados['score_base_destino']} | "
            f"tamanho={dados['tamanho_caminho']} | "
            f"entradas={dados['entradas']} | saidas={dados['saidas']}"
        )

        print(f"   caminho: {caminho}")

        if dados["score_final"] >= 70:
            risco = "ALTO risco de fluxo suspeito"
        elif dados["score_final"] >= 40:
            risco = "risco moderado de comportamento anômalo"
        else:
            risco = "baixo risco observado"

        print(f"   avaliacao: {risco}")

def topItens(dados, limite=10):
    ordenados = sorted(
        dados.items(),
        key=lambda item: item[1],
        reverse=True
    )[:limite]

    return [
        {
            "carteira": chave,
            "valor": round(float(valor), 4)
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

def coeficienteVariacao(valores):
    valores = np.array(valores)
    if len(valores) == 0:
        return 0
    return np.std(valores) / (np.mean(valores) + 1e-9)


def detectarPossiveisMixers(G, limite=10):
    candidatos = defaultdict(lambda: {
        "score_mixer": 0,
        "motivos": set(),
        "txids": set()
    })

    tx_map = defaultdict(lambda: {
        "inputs": set(),
        "outputs": set(),
        "valores": []
    })

    for u, v, k, d in G.edges(keys=True, data=True):
        txid = d.get("txid")
        if not txid:
            continue

        tx_map[txid]["inputs"].add(u)
        tx_map[txid]["outputs"].add(v)
        tx_map[txid]["valores"].append(d.get("valor", 0))

    for txid, tx in tx_map.items():
        inputs = len(tx["inputs"])
        outputs = len(tx["outputs"])
        valores = tx["valores"]

        if len(valores) == 0:
            continue

        ent = coeficienteVariacao(valores)

        score = 0

        score += min(inputs * 4, 20)
        score += min(outputs * 4, 20)

        score += ent * 30

        if inputs >= 2 and outputs >= 2:
            score += 10

        if ent > 0.5:
            score += 10
            motivo_extra = "alta variacao de valores"

        else:
            motivo_extra = None

        if score >= 25:
            envolvidos = tx["inputs"].union(tx["outputs"])

            for carteira in envolvidos:
                candidatos[carteira]["score_mixer"] += score
                candidatos[carteira]["txids"].add(txid)
                candidatos[carteira]["motivos"].add(
                    f"transacao com {inputs} inputs e {outputs} outputs"
                )

                if motivo_extra:
                    candidatos[carteira]["motivos"].add(motivo_extra)

    for no in G.nodes():
        entradas = len(set(G.predecessors(no)))
        saidas = len(set(G.successors(no)))

        if entradas + saidas == 0:
            continue

        valores = [
            d.get("valor", 0)
            for _, _, _, d in list(G.in_edges(no, keys=True, data=True)) +
                             list(G.out_edges(no, keys=True, data=True))
        ]

        ent = coeficienteVariacao(valores)

        score = 0

        score += min((entradas + saidas) * 2, 25)

        if entradas >= 3 and saidas >= 3:
            score += 15
            candidatos[no]["motivos"].add("hub com fluxo bidirecional")

        score += ent * 20

        if score >= 20:
            candidatos[no]["score_mixer"] += score
            candidatos[no]["motivos"].add(f"fan-in {entradas} / fan-out {saidas}")

    resultado = []

    for carteira, dados in candidatos.items():
        resultado.append({
            "carteira": carteira,
            "score_mixer": float(min(round(dados["score_mixer"], 2), 100)),
            "motivos": sorted(dados["motivos"]),
            "txids": sorted(dados["txids"])
        })

    resultado.sort(key=lambda x: x["score_mixer"], reverse=True)

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

def analisarAutomacaoPorCarteira(G, carteira):
    """
    Analisa as transações de SAÍDA de uma carteira específica para detectar
    sinais de automação (bots, scripts).
    """
    # Coleta apenas timestamps de arestas de SAÍDA da carteira
    saidas = sorted(
        [d.get("timestamp") for _, _, d in G.out_edges(carteira, data=True) if d.get("timestamp")],
    )
    
    # Requer um número mínimo de amostras para uma análise confiável
    if len(saidas) < 3:
        return {"assinatura_automatizada": False, "intervalo_medio_segundos": None, "amostras": len(saidas)}

    # Calcula a diferença em segundos entre transações consecutivas
    diffs = np.diff(saidas)
    intervalo_medio = float(np.mean(diffs))
    variacao = float(np.std(diffs))

    # Heurística: um bot real opera com intervalos curtos E consistentes (baixa variação)
    assinatura_bot = bool(intervalo_medio < 120 and variacao < 30 and len(diffs) >= 3)

    return {
        "assinatura_automatizada": assinatura_bot,
        "intervalo_medio_segundos": round(intervalo_medio, 2),
        "variacao_intervalo_segundos": round(variacao, 2),
        "amostras": len(diffs)
    }
