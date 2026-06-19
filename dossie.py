import json
import pandas as pd
import heuristica as ht

def gerarDossieInvestigativo(G, carteira_inicial, scores, trajetorias=None, possiveis_mixers=None):
    
    trajetorias = trajetorias or []
    possiveis_mixers = possiveis_mixers or ht.detectarPossiveisMixers(G)

    analise_comp = {
        "pico_transacoes_por_minuto": 0,
        "intervalo_medio_segundos": 0.0,
        "assinatura_automatizada_detectada": False,
        "transacoes_valores_padronizados": 0
    }

    if G.number_of_edges() > 0:
        # Extrai os dados das arestas (edges) do NetworkX para um DataFrame
        dados_arestas = []
        for u, v, data in G.edges(data=True):
            dados_arestas.append({
                "timestamp": data.get("timestamp"),
                "valor": data.get("valor")
            })
        
        df_transacoes = pd.DataFrame(dados_arestas)
        
        # Executa as análises comportamentais passadas anteriormente
        por_minuto = ht.analisarBurst(df_transacoes)
        diferenca_tempo = ht.analisarTempo(df_transacoes)
        valores_semelhantes = ht.analisarValores(df_transacoes)
        
        # Consolida as métricas se os retornos forem válidos
        pico_burst = int(por_minuto.max()) if (por_minuto is not None and not por_minuto.empty) else 0
        intervalo_medio = float(diferenca_tempo.mean()) if (diferenca_tempo is not None and not diferenca_tempo.empty) else 0.0
        
        # Heurística de automação (Desvio padrão baixo indica intervalos idênticos/scripts)
        variacao_tempo = diferenca_tempo.std() if (diferenca_tempo is not None and not diferenca_tempo.empty) else 999
        assinatura_bot = bool(variacao_tempo < 2.0 and len(diferenca_tempo) > 5)
        
        qtd_valores_padronizados = len(valores_semelhantes) if (valores_semelhantes is not None and not valores_semelhantes.empty) else 0
        
        analise_comp = {
            "pico_transacoes_por_minuto": pico_burst,
            "intervalo_medio_segundos": round(intervalo_medio, 2),
            "assinatura_automatizada_detectada": assinatura_bot,
            "transacoes_valores_padronizados": qtd_valores_padronizados
        }

    fanin = ht.analisarFanIn(G)
    fanout = ht.analisarFanOut(G)
    pagerank = ht.analisarPageRank(G) if G.number_of_nodes() > 0 else {}
    betweenness = ht.analisarBetweenness(G) if G.number_of_nodes() > 0 else {}
    closeness = ht.analisarCloseness(G) if G.number_of_nodes() > 0 else {}
    degree = ht.analisarDegree(G) if G.number_of_nodes() > 1 else {}
    clusters = ht.analisarClusters(G)
    chains = ht.analisarChain(G)
    key_addresses = ht.detectarKeyAddresses(G) if G.number_of_nodes() > 0 else {}

    carteiras_alto_risco = [
        {
            "carteira": carteira,
            "score": dados["score"],
            "risco": dados["risco"],
            "motivos": dados["motivos"]
        }
        for carteira, dados in sorted(
            scores.items(),
            key=lambda item: item[1]["score"],
            reverse=True
        )
        if dados["score"] >= 70
    ]

    return {
        "carteira_inicial": carteira_inicial,
        "resumo_grafo": {
            "nos": G.number_of_nodes(),
            "arestas": G.number_of_edges(),
            "clusters": len(clusters)
        },
        "carteiras_alto_risco": carteiras_alto_risco[:10],
        "possiveis_mixers": possiveis_mixers,
        "trajetorias_provaveis": trajetorias,
        
        "analise_comportamental": analise_comp, 

        "analises": {
            "fanin": ht.topItens(fanin),
            "fanout": ht.topItens(fanout),
            "pagerank": ht.topItens(pagerank),
            "betweenness": ht.topItens(betweenness),
            "closeness": ht.topItens(closeness),
            "degree": ht.topItens(degree),
            "key_addresses": ht.topItens(key_addresses),
            "chains": chains[:20],
            "clusters_maiores": sorted(
                [len(cluster) for cluster in clusters],
                reverse=True
            )[:10]
        },
        "observacoes": [
            "Scores e mixers sao indicios heuristicos, nao prova conclusiva.",
            "Uma LLM investigadora deve usar este dossie para explicar hipoteses e incertezas.",
            "Nos com possivel mixer podem representar servicos legitimos, exchanges ou consolidadores.",
            "A analise comportamental mapeia o uso potencial de scripts e automacoes pelo atacante."
        ]
    }

def imprimirDossieInvestigativo(dossie):
    print("\n===== DOSSIE INVESTIGATIVO =====")
    print("Carteira inicial:", dossie["carteira_inicial"])
    print("Nos:", dossie["resumo_grafo"]["nos"])
    print("Arestas:", dossie["resumo_grafo"]["arestas"])
    print("Clusters:", dossie["resumo_grafo"]["clusters"])
    print("Carteiras de alto risco:", len(dossie["carteiras_alto_risco"]))
    print("Possiveis mixers:", len(dossie["possiveis_mixers"]))
    print("Trajetorias provaveis:", len(dossie["trajetorias_provaveis"]))

    if dossie["possiveis_mixers"]:
        print("\nTop possiveis mixers:")
        for mixer in dossie["possiveis_mixers"][:5]:
            motivos = "; ".join(mixer["motivos"][:3])
            print(
                f"- {mixer['carteira']} | score_mixer={mixer['score_mixer']} | "
                f"motivos: {motivos}"
            )

def salvarDossieInvestigativo(dossie, caminho="dossie_investigativo.json"):
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dossie, arquivo, ensure_ascii=False, indent=2)