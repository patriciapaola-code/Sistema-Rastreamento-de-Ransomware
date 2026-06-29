import requests 
import networkx as nx 
import json
import requests
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

def expandirGrafo(address, profundidade, max_vizinhos, max_nos, max_edges, valor_minimo=None, valor_maximo=None):
    G = nx.MultiDiGraph()
    fila = [address]
    visitados = set()
    nivel = 0

    valor_min_sat = valor_minimo * 100_000_000 if valor_minimo is not None else 0
    valor_max_sat = valor_maximo * 100_000_000 if valor_maximo is not None else float('inf')

    while fila and nivel < profundidade:
        proxima_fila = []

        for atual in fila:
            if atual in visitados:
                continue

            visitados.add(atual)
            # Aumentamos o limite de transações buscadas para garantir vizinhos após o filtro
            vizinhos = obterNeighbors(atual, max(10, max_vizinhos))

            for vizinho in vizinhos[:max_vizinhos]:
                destino = vizinho["address"]

                if not destino:
                    continue
                
                # Aplica o filtro de valor das transações
                if not (valor_min_sat <= vizinho["value"] <= valor_max_sat):
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

                # Verifica o limite de arestas a cada adição
                if G.number_of_edges() >= max_edges:
                    print(f"Limite global de arestas ({max_edges}) atingido.")
                    return G

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

        entidade_origem = uf[origem]
        
        entidade_destino = uf[destino]

        if entidade_origem != entidade_destino:

            valor = dados.get(
                "valor",
                0
            )

            G_filtrado.add_edge(
                entidade_origem,
                entidade_destino,
                **dados
            )

    return G_filtrado