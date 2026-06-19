import requests
import networkx as nx
import time

BASE_URL = "https://blockstream.info/api"

def obterNeighbors(address, limite_transacoes):

    try:
        url = f"{BASE_URL}/address/{address}/txs"

        time.sleep(0.3)

        resposta = requests.get(
            url,
            timeout=10
        )

        if resposta.status_code != 200:
            return []

        vizinhos = []

        transacoes = resposta.json()

        transacoes = transacoes[:limite_transacoes]

        for tx in transacoes:

            txid = tx["txid"]

            timestamp = tx["status"].get(
                "block_time",
                None
            )

            # Inputs
            for vin in tx.get("vin", []):

                prev_out = vin.get("prevout")

                if prev_out and prev_out.get("scriptpubkey_address"):

                    vizinhos.append({
                        "address": prev_out["scriptpubkey_address"],
                        "value": prev_out.get(
                            "value",
                            0
                        ),
                        "timestamp": timestamp,
                        "txid": txid,
                        "tipo": "input"

                    })

            for vout in tx.get("vout", []):
                if vout.get("scriptpubkey_address"):
                    vizinhos.append({
                        "address": vout["scriptpubkey_address"],
                        "value": vout.get(
                            "value",
                            0
                        ),
                        "timestamp": timestamp,
                        "txid": txid,
                        "tipo": "output"

                    })

        return vizinhos

    except Exception as e:

        print("Erro em", address)
        print(e)

        return []

def expandirGrafo(address, profundidade, max_vizinhos, max_nos):
    G = nx.MultiDiGraph()
    fila = [address]
    visitados = set()
    nivel = 0

    while fila and nivel < profundidade:
        proxima_fila = []

        for atual in fila:
            if atual in visitados:
                continue

            visitados.add(atual)
            vizinhos = obterNeighbors(atual, max_vizinhos)

            for vizinho in vizinhos[:max_vizinhos]:
                destino = vizinho["address"]

                if not destino:
                    continue
                
                if vizinho["tipo"] == "input":
                    origem_real = destino
                    destino_real = atual
                else:
                    origem_real = atual
                    destino_real = destino

                G.add_edge(
                    origem_real,
                    destino_real,
                    valor=vizinho["value"],
                    timestamp=vizinho["timestamp"],
                    txid=vizinho["txid"],
                    tipo=vizinho["tipo"]
                )

                if destino not in visitados and destino not in proxima_fila:
                    proxima_fila.append(destino)

            if G.number_of_nodes() >= max_nos:
                print(f"Limite global de nós ({max_nos}) atingido.")
                return G

        fila = proxima_fila
        nivel += 1

    return G

def construirGrafoFiltrado(G, uf):
    G_filtrado = nx.MultiDiGraph()

    for origem, destino, dados in G.edges(data=True):
        # CORREÇÃO: Se o nó não está no UnionFind, ele representa ele mesmo
        entidade_origem = uf[origem] if origem in uf else origem
        entidade_destino = uf[destino] if destino in uf else destino

        if entidade_origem != entidade_destino:
            G_filtrado.add_edge(
                entidade_origem,
                entidade_destino,
                **dados
            )
            
    # Garante que nós isolados que perderam arestas não quebrem o desenho
    return G_filtrado
