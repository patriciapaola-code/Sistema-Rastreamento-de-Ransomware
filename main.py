import etapa2_grafo as etp2
import etapa5_graphsense as etp5
import heuristica as ht
import agent as ag
import dossie as ds

def main():

    wallet = "bc1q4my6vqq8cg689drf9jccqudjclv67sz4cudkyd"

    print("Expandindo grafo...")
    G_bruto = etp5.expandirGrafo(
        wallet,
        profundidade=3,
        max_vizinhos=100,
        max_nos=500
    )

    print("\n===== GRAFO BRUTO =====")
    print("Nós:", G_bruto.number_of_nodes())
    print("Arestas:", G_bruto.number_of_edges())

    print("Grafo bruto")
    etp2.gerarGrafo(G_bruto, wallet)


    print("\nAplicando Multi-Input...")
    uf = ht.heuristicaMultiInput(G_bruto)

    G_multi = etp5.construirGrafoFiltrado(
        G_bruto,
        uf
    )

    # A heurística de Multi-Input assume que endereços que aparecem como inputs na mesma transação pertencem ao mesmo usuário
    # Funde em um único nó representando esse usuário.
    print("\n===== APÓS MULTI-INPUT =====")
    print("Nós:", G_multi.number_of_nodes())
    print("Arestas:", G_multi.number_of_edges())

    print("Grafo após Multi-Input")
    etp2.gerarGrafoFiltrado(G_multi, "Multi-Input")

    # Endereços de troco numa transação geralmente têm um comportamento distinto: eles recebem o valor de volta para o remetente, mas não são usados como input em outras transações.
    # A heurística de Change Address tenta identificar esses endereços e fundi-los com o endereço de origem
    G_change = ht.aplicarChangeAddress(G_multi)

    print("\n===== APÓS CHANGE ADDRESS =====")
    print("Nós:", G_change.number_of_nodes())
    print("Arestas:", G_change.number_of_edges())

    print("Grafo após Change Address")
    etp2.gerarGrafoFiltrado(G_change, "Change Address")

    # Filtra transações feitas num tempo próximo umas das outras
    print("\nAplicando Heurística Temporal...")
    G_tempo = ht.aplicarTempo(G_change)

    print("\n===== APÓS TEMPO =====")
    print("Nós:", G_tempo.number_of_nodes())
    print("Arestas:", G_tempo.number_of_edges())

    print("Grafo após Tempo")
    etp2.gerarGrafoFiltrado(G_tempo, "Tempo")

    # Filtra transações com valores semelhantes/iguais (que podem indicar transações automatizadas ou em lote)
    # A heurística de Similaridade de Valores marca as transações cujo valor é semelhante à mediana dos valores do grafo
    print("\nAplicando Similaridade de Valores...")
    G_valores = ht.aplicarValores(G_tempo)

    print("\n===== APÓS VALORES =====")
    print("Nós:", G_valores.number_of_nodes())
    print("Arestas:", G_valores.number_of_edges())

    print("Grafo após Valores")
    etp2.gerarGrafoFiltrado(G_valores, "Valores")
    
    # A heurística de Chain tenta identificar e fundir sequências de transações que ocorrem em rápida sucessão
    # onde o destinatário de uma transação é o remetente da próxima, formando uma "cadeia" de transações.
    print("\nAplicando Chain...")
    G_chain = ht.aplicarChain(G_valores)
    
    print("\n===== APÓS CHAIN =====")
    print("Nós:", G_chain.number_of_nodes())
    print("Arestas:", G_chain.number_of_edges())
    
    print("Grafo após Chain")
    etp2.gerarGrafoFiltrado(G_chain, "Chain")

    print("\nCalculando score de risco no grafo final...")
    scores = ht.calcularScoreRisco(G_chain, wallet)

    trajetoria = ht.encontrarTrajetoriasProvaveis(G_chain, wallet, scores)
    possive_mixers = ht.detectarPossiveisMixers(G_chain)

    # =========================
    # DOSSIÊ
    # =========================

    dossie = ds.gerarDossieInvestigativo(
        G_chain,
        wallet,
        scores,
        trajetoria,
        possive_mixers
    )

    ds.salvarDossieInvestigativo(dossie)
    ds.imprimirDossieInvestigativo(dossie)

    # =========================
    # AGENTE INVESTIGATIVO
    # =========================

    ag.criarAgent()

if __name__ == "__main__":
    main()
