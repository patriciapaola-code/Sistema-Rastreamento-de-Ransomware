import json
import streamlit as st
import coleta_blockchain as cb
import analise_heuristica as ht
import assistente_ia as ag
import gerador_dossie as ds
import visualizacao_grafo_interativo as dg
import visualizacao_grafo_matplotlib as vgm
import plotly.graph_objects as go
import networkx as nx
import pandas as pd
import os
import dashboard_dossie as dd

# ==============================================================================
# 1. CONFIGURAÇÃO DE PÁGINA DO STREAMLIT (OBRIGATORIAMENTE O PRIMEIRO COMANDO)
# ==============================================================================
st.set_page_config(
    layout="wide", 
    page_title="Sistema Antiransomware - Forense Blockchain", 
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded"
)

# CSS Customizado para melhorar ícones e layout
st.markdown("""
<style>
    /* Modo paisagem - maximizar espaço */
    .main { padding-top: 1rem; }
    .st-emotion-cache-z5fcl4 { padding: 0; }
    
    /* Melhorar aparência dos ícones */
    h1, h2, h3, h4, h5 {
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    
    /* Cards de status - layout melhorado */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        font-weight: bold;
    }
    
    /* Tabs - melhor estilo */
    .st-tabs [role="tablist"] button[role="tab"] {
        font-weight: 600;
        letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)
# ==============================================================================
# 2. FUNÇÃO COM CACHE PARA PROCESSAMENTO PESADO DA BLOCKCHAIN
# ==============================================================================
def is_grafo_valido(G): # Verifica se o grafo é válido (não nulo e com nós)
    return G is not None and G.number_of_nodes() > 0

    # ==============================================================================
# 2. FUNÇÃO COM CACHE (CORRIGIDA)
# ==============================================================================
@st.cache_resource(show_spinner=False)
def carregar_toda_a_blockchain(wallet, profundidade=4, max_vizinhos=100, max_nos=500,
                               sensibilidade="Médio", comportamentos=None):
    historico = []
    
   
    # =========================
    # 1. GRAFO BRUTO (Ponto de falha crítico) eliminar a divisão por zero em caso de grafo vazio
    # =========================
    G_bruto = cb.expandirGrafo(wallet, profundidade=profundidade, 
                                max_vizinhos=max_vizinhos, max_nos=max_nos, max_edges=600)


    # Verifica se o grafo existe e se ele tem pelo menos um nó
    if G_bruto is None or (hasattr(G_bruto, 'number_of_nodes') and G_bruto.number_of_nodes() == 0):
        # Isso impede que o código continue e tente calcular scores em um grafo vazio
        return [], {"error": "Nenhum histórico encontrado para esta carteira."}
    # ----------------------------------------------------

    # Agora sim, você pode usar o G_bruto com segurança
    score_bruto = ht.calcularScoreRisco(G_bruto, wallet)
    historico.append({
        "nome": "1. Grafo Bruto",
        "grafo": G_bruto,
        "scores": score_bruto,
        "trajetorias": []
    })

    if not is_grafo_valido(G_bruto):
        return [], {"error": "Nenhum dado transacional encontrado para esta carteira."}

    # Agora o cálculo é seguro
    score_bruto = ht.calcularScoreRisco(G_bruto, wallet)
    historico.append({
        "nome": "1. Grafo Bruto",
        "grafo": G_bruto,
        "scores": score_bruto,
        "trajetorias": []
    })

    # =========================
    # FLUXO SEGURO PARA AS PRÓXIMAS ETAPAS
    # =========================
    G_atual = G_bruto
    
    # Exemplo: Aplicando heurísticas com verificação
    heuristicas = [
        ("Multi-Input", ht.heuristicaMultiInput, cb.construirGrafoFiltrado),
        ("Valores", None, ht.aplicarValores),
        ("Tempo", None, ht.aplicarTempo)
    ]
    
    # =========================
    # 2. MULTI INPUT (Agrupa donos)
    # =========================
    uf, coinjoin_suspeitas = ht.heuristicaMultiInput(G_bruto)
    G_multi = cb.construirGrafoFiltrado(G_bruto, uf)
    
    score_multi = ht.calcularScoreRisco(G_multi, wallet, coinjoin_suspeitas=coinjoin_suspeitas)
    trajetorias_multi = ht.encontrarTrajetoriasProvaveis(nx.DiGraph(G_multi), wallet, score_multi)
    historico.append({
        "nome": "2. Multi-Input (Agrupamento de Carteiras)",
        "grafo": G_multi,
        "scores": score_multi,
        "trajetorias": trajetorias_multi
    })
    
    # =========================
    # 3. VALORES (Marca similaridades)
    # =========================
    G_valores = ht.aplicarValores(G_multi)
    
    score_valores = ht.calcularScoreRisco(G_valores, wallet, coinjoin_suspeitas=coinjoin_suspeitas)
    trajetorias_valores = ht.encontrarTrajetoriasProvaveis(nx.DiGraph(G_valores), wallet, score_valores)
    historico.append({
        "nome": "3. Análise de Valores",
        "grafo": G_valores,
        "scores": score_valores,
        "trajetorias": trajetorias_valores
    })
    
    # =========================
    # 4. TEMPO (Filtra janelas suspeitas)
    # =========================
    G_tempo = ht.aplicarTempo(G_valores)
    
    score_tempo = ht.calcularScoreRisco(G_tempo, wallet, coinjoin_suspeitas=coinjoin_suspeitas)
    trajetorias_tempo = ht.encontrarTrajetoriasProvaveis(nx.DiGraph(G_tempo), wallet, score_tempo)
    historico.append({
        "nome": "4. Filtro Temporal",
        "grafo": G_tempo,
        "scores": score_tempo,
        "trajetorias": trajetorias_tempo
    })
    
    # =========================
    # 5. CHANGE ADDRESS (Remove troco)
    # =========================
    G_change = ht.aplicarChangeAddress(G_tempo)
    
    score_change = ht.calcularScoreRisco(G_change, wallet, coinjoin_suspeitas=coinjoin_suspeitas)
    trajetorias_change = ht.encontrarTrajetoriasProvaveis(nx.DiGraph(G_change), wallet, score_change)
    historico.append({
        "nome": "5. Change Address (Remoção de Troco)",
        "grafo": G_change,
        "scores": score_change,
        "trajetorias": trajetorias_change
    })
    
    # =========================
    # 6. CHAIN (Simplifica caminhos lineares)
    # =========================
    G_chain = ht.aplicarChain(G_change)
    
    score_chain = ht.calcularScoreRisco(G_chain, wallet, coinjoin_suspeitas=coinjoin_suspeitas)
    trajetorias_chain = ht.encontrarTrajetoriasProvaveis(nx.DiGraph(G_chain), wallet, score_chain)
    historico.append({
        "nome": "6. Simplificação de Cadeias",
        "grafo": G_chain,
        "scores": score_chain,
        "trajetorias": trajetorias_chain
    })
    
    # =========================
    # 7. DOSSIÊ FINAL
    # =========================
    possiveis_mixers_final = ht.detectarPossiveisMixers(G_chain)
    dossie = ds.gerarDossieInvestigativo(
        G_chain, wallet, score_chain, 
        trajetorias_chain, possiveis_mixers_final, coinjoin_suspeitas=coinjoin_suspeitas
    )

    # =========================
    # 8. ETAPA FINAL (VISUALIZAÇÃO CONSOLIDADA)
    # =========================
    historico.append({
        "nome": "7. Grafo Final (Consolidado)",
        "grafo": G_chain,
        "scores": score_chain,
        "trajetorias": trajetorias_chain,
        "possiveis_mixers": dossie.get("possiveis_mixers", []),
        "carteiras_alto_risco": dossie.get("carteiras_alto_risco", [])
    })

    return historico, dossie

def mostrar_metricas_reducao(historico):
    """Mostra como as heurísticas reduzem o grafo"""
    inicial = historico[0]['grafo'].number_of_nodes()
    
    for etapa in historico:
        atual = etapa['grafo'].number_of_nodes()
        reducao = ((inicial - atual) / inicial) * 100
        st.metric(
            label=etapa['nome'],
            value=f"{atual} nós",
            delta=f"-{reducao:.1f}%"
        )

def calcular_densidade(G):
    n = G.number_of_nodes()
    if n <= 1:
        return 0.0
    
    # Converte MultiDiGraph para DiGraph simples
    if isinstance(G, nx.MultiDiGraph):
        G_simples = nx.DiGraph(G)
    elif isinstance(G, nx.MultiGraph):
        G_simples = nx.Graph(G)
    else:
        G_simples = G
    
    m = G_simples.number_of_edges()
    
    # Fórmula da densidade para grafos direcionados
    if isinstance(G_simples, nx.DiGraph):
        max_arestas = n * (n - 1)
    else:
        max_arestas = n * (n - 1) / 2
    
    return m / max_arestas if max_arestas > 0 else 0.0

@st.cache_resource
def carregar_agent():
    return ag.iniciarAgent()

@st.cache_data(show_spinner=False)
def cached_retrieve(_retriever, query):
    try:
        return _retriever.invoke(query)
    except Exception as e:
        # Se a IA falhar, não quebra o sistema; retorna uma mensagem amigável
        return "Erro ao consultar assistente: verifique a conexão com a API."

# ==============================================================================
# 3. INTERFACE DO USUÁRIO E CONTROLE DE EXIBIÇÃO (STREAMLIT UI)
# ==============================================================================

def mostrar_resumo_grafo_sidebar():
    """Adiciona métricas na sidebar"""
    with st.sidebar:
        st.header("📊 Resumo do Grafo")
        
        historico = st.session_state.historico
        index = st.session_state.grafo_index
        etapa = historico[index]
        
        # Cards com métricas principais
        st.metric("Etapa Atual", etapa['nome'])
        st.metric("Nós Restantes", etapa['grafo'].number_of_nodes())
        st.metric("Arestas Restantes", etapa['grafo'].number_of_edges())
        
        # Gráfico de redução
        if st.checkbox("Mostrar Redução"):
            nos_por_etapa = [h['grafo'].number_of_nodes() for h in historico]
            arestas_por_etapa = [h['grafo'].number_of_edges() for h in historico]
            
            st.line_chart({
                'Nós': nos_por_etapa,
                'Arestas': arestas_por_etapa
            })

def interface():

    st.title("🕵️ BlockSentinAI - Sistema Inteligente para Rastreamento e Investigação de Ransomware em Blockchain.")

    # =========================
    # PAINEL DE CONFIGURAÇÃO DO USUÁRIO (ENTRADA)
    # =========================

    # Inicializa valor padrão da carteira na sessão, se necessário
    if "wallet_input" not in st.session_state:
        st.session_state["wallet_input"] = "bc1qjuqyesxjgravlf0evtz5p8ks8k2w6ytcherrk3"
    if "executar_analise" not in st.session_state:
        st.session_state["executar_analise"] = False

    with st.expander("Análise de Carteira", expanded=True):
        st.markdown("### 📍 Endereço da Carteira e Parâmetros de Busca")
        
        col_wallet_1, col_wallet_2 = st.columns([3, 1])
        with col_wallet_1:
            # Usa o valor do session_state como value para garantir consistência
            wallet_input = st.text_input(
                "Endereço inicial da carteira:",
                value=st.session_state.get("wallet_input", "bc1qjuqyesxjgravlf0evtz5p8ks8k2w6ytcherrk3"),
                placeholder="Insira um endereço Bitcoin válido",
                help="Ex: bc1q... (SegWit) ou 1... ou 3... (Legacy)",
                key="wallet_input"
            )
        with col_wallet_2:
            if st.button("📋 Exemplo", help="Usar carteira de exemplo"):
                exemplo = "bc1qjuqyesxjgravlf0evtz5p8ks8k2w6ytcherrk3"
                # Atualiza o session_state e força rerun para refletir no input
                st.session_state.wallet_input = exemplo
                st.session_state.wallet_example = exemplo
                st.experimental_rerun()

        wallet = st.session_state.get("wallet_input", wallet_input)
        
        # Mostrar exemplo se selecionado
        if "wallet_example" in st.session_state:
            st.info(f"**Exemplo carregado:** {st.session_state.wallet_example}")
        
        # Parâmetros de busca
        st.markdown("### 🔍 Profundidade e Escala da Busca")
        col1, col2, col3 = st.columns(3)
        with col1:
            profundidade = st.slider(
                "Profundidade máxima de busca:",
                min_value=1, max_value=10, value=4,
                help="Quantos níveis de transações explorar a partir da carteira inicial"
            )
        with col2:
            max_vizinhos = st.slider(
                "Máximo de vizinhos por nó:",
                min_value=10, max_value=500, value=100, step=10,
                help="Limita o número de nós vizinhos explorados"
            )
        with col3:
            max_nos = st.slider(
                "Número máximo de nós:",
                min_value=50, max_value=500, value=500, step=50,
                help="Limite total de nós no grafo"
            )
        
        # Filtros de transações
        st.markdown("### 💰 Filtros de Transações")
        col_val1, col_val2 = st.columns(2)
        with col_val1:
            valor_minimo = st.number_input(
                "Valor mínimo das transações (BTC):",
                min_value=0.0, value=0.1, step=0.1,
                help="Filtrar transações abaixo deste valor"
            )
        with col_val2:
            valor_maximo = st.number_input(
                "Valor máximo das transações (BTC):",
                min_value=0.0, value=1000.0, step=1.0,
                help="Filtrar transações acima deste valor"
            )
        
        # Intervalo de datas
        st.markdown("### 📅 Intervalo Temporal")
        col_data1, col_data2 = st.columns(2)
        with col_data1:
            data_inicio = st.date_input(
                "Data de início:",
                help="Filtrar transações a partir desta data"
            )
        with col_data2:
            data_fim = st.date_input(
                "Data de término:",
                help="Filtrar transações até esta data"
            )
        
        # Nível de sensibilidade
        st.markdown("### ⚠️ Nível de Sensibilidade da Detecção de Risco")
        sensibilidade = st.radio(
            "Selecione o nível de sensibilidade:",
            options=["Baixo", "Médio", "Alto"],
            index=1,
            horizontal=True,
            help="Baixo: poucos alertas | Médio: equilibrado | Alto: máxima detecção"
        )
        
        # Comportamentos suspeitos
        st.markdown("### 🚨 Tipos de Comportamento Suspeito a Detectar")
        col_comp1, col_comp2 = st.columns(2)
        with col_comp1:
            detectar_fan_in = st.checkbox("Fan-in elevado", value=True, 
                                         help="Múltiplas entradas consolidadas em um nó")
            detectar_fan_out = st.checkbox("Fan-out elevado", value=True,
                                          help="Um nó distribuindo fundos para múltiplos destinos")
            detectar_mixer = st.checkbox("Possível mixer", value=True,
                                        help="Padrões indicativos de misturadores de moedas")
        with col_comp2:
            detectar_cadeia_rapida = st.checkbox("Transações em cadeia rápida", value=True,
                                                help="Sequências lineares de transações")
            detectar_fracionado = st.checkbox("Valores fracionados repetitivos", value=True,
                                             help="Padrão de quebra de valores em múltiplas parcelas")
        
        st.divider()
        
        # Botão de execução
        if st.button("🚀 Iniciar Análise Forense", type="primary", use_container_width=True):
            st.session_state.wallet_config = wallet
            st.session_state.profundidade_config = profundidade
            st.session_state.max_vizinhos_config = max_vizinhos
            st.session_state.max_nos_config = max_nos
            st.session_state.valor_minimo_config = valor_minimo
            st.session_state.valor_maximo_config = valor_maximo
            st.session_state.data_inicio_config = data_inicio
            st.session_state.data_fim_config = data_fim
            st.session_state.sensibilidade_config = sensibilidade
            st.session_state.comportamentos_config = {
                "fan_in": detectar_fan_in,
                "fan_out": detectar_fan_out,
                "mixer": detectar_mixer,
                "cadeia_rapida": detectar_cadeia_rapida,
                "fracionado": detectar_fracionado
            }
            st.session_state.executar_analise = True
            if "historico" in st.session_state:
                del st.session_state["historico"]
            st.session_state.grafo_index = 0
            st.toast("✅ Configuração salva! Processando blockchain...", icon="⚙️")
            st.rerun()
        
        # Mostrar exemplo de carteira
        st.divider()
        st.markdown("### 📚 Carteiras de Teste (Com Histórico Ativo)")
        
        # Abas com diferentes tipos de carteiras
        tab_segwit, tab_legacy, tab_ransomware = st.tabs(["SegWit (Recomendado)", "Legacy", "Histórico de Ransomware"])
        
        with tab_segwit:
            st.info("**Carteiras SegWit (bc1q...)** - Modernas e otimizadas")
            col_seg1, col_seg2 = st.columns(2)
            with col_seg1:
                st.caption("1. Carteira com Transações:")
                st.code("bc1qjuqyesxjgravlf0evtz5p8ks8k2w6ytcherrk3", language="text")
            with col_seg2:
                st.caption("2. Outra Carteira Ativa:")
                st.code("bc1qeca5hd7m9latsls46ty7u5udrvwclzq4nn64n4", language="text")
        
        with tab_legacy:
            st.info("**Carteiras Legacy (1... ou 3...)** - Formato antigo, ainda ativo")
            col_leg1, col_leg2 = st.columns(2)
            with col_leg1:
                st.caption("1. Legacy SegWit:")
                st.code("16FnhJgft5PxM3QNRjq9FiafkKHAAv8Ngy", language="text")
            with col_leg2:
                st.caption("2. Multisig (P2SH):")
                st.code("3J98t1WpEZ73CNmYviecrnyiWrnqRhWNLy", language="text")
        
        with tab_ransomware:
            st.warning("**⚠️ Carteiras de Histórico Público** - Para análise forense")
            st.markdown("""
            Estas carteiras têm histórico documentado de:
            - Múltiplas transações
            - Padrões complexos
            - Consolidações e distribuições
            - Atividade em longo prazo
            
            **Dica:** Se nenhuma carteira funcionar:
            1. Use carteiras do Blockchain.com (histórico verificado)
            2. Busque em bases de dados públicas: blockchain.info
            3. Procure por: "known ransomware addresses bitcoin"
            4. Teste com carteiras pequenas primeiro (2-3 transações)
            """)
            
            col_ran1, col_ran2, col_ran3 = st.columns(3)
            with col_ran1:
                st.caption("Carteira 1:")
                st.code("1A1z7agoat4EvZ8eD6gL2pmCe4Sj7jzRH4", language="text")
                st.caption("⚠️ Satoshi's wallet")
            with col_ran2:
                st.caption("Carteira 2:")
                st.code("1dice8EMCQAqQSN3LGzJ72b3FYYyHBiUSo", language="text")
                st.caption("📊 Dice gambling (histórico)")
            with col_ran3:
                st.caption("Carteira 3:")
                st.code("1HQ3Go3qs6LaRoVKKEZkj5GN6aRBjADSLU", language="text")
                st.caption("🔄 Mixer histórico")

    # =========================
    # INIT GLOBAL STATE
    # =========================
    if st.session_state.get("executar_analise", False) and "historico" not in st.session_state:
        # Usa parâmetros da configuração se disponível, senão usa defaults
        wallet_analise = st.session_state.get("wallet_config", wallet)
        profundidade_analise = st.session_state.get("profundidade_config", 4)
        max_vizinhos_analise = st.session_state.get("max_vizinhos_config", 100)
        max_nos_analise = st.session_state.get("max_nos_config", 500)
        sensibilidade_analise = st.session_state.get("sensibilidade_config", "Médio")
        comportamentos_analise = st.session_state.get("comportamentos_config", {})
        
        # Mostrar progresso detalhado
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        with progress_placeholder.container():
            progress_bar = st.progress(0, text="⏳ Iniciando análise...")
            
            try:
                # Etapa 1: Coleta
                status_placeholder.info("📡 **Etapa 1/4**: Coletando dados da blockchain...")
                progress_bar.progress(25, text="📡 Coletando dados (25%)")
                
                historico, dossie = carregar_toda_a_blockchain(
                    wallet_analise, 
                    profundidade=profundidade_analise,
                    max_vizinhos=max_vizinhos_analise,
                    max_nos=max_nos_analise,
                    sensibilidade=sensibilidade_analise,
                    comportamentos=comportamentos_analise
                )
                
                # Etapa 2: Análise
                status_placeholder.info("📊 **Etapa 2/4**: Analisando grafos...")
                progress_bar.progress(50, text="📊 Analisando (50%)")
                
                # Etapa 3: Dossiê
                status_placeholder.info("📝 **Etapa 3/4**: Gerando dossiê investigativo...")
                progress_bar.progress(75, text="📝 Gerando dossiê (75%)")
                
                st.session_state.historico = historico
                st.session_state.dossie = dossie
                st.session_state.wallet_ativo = wallet_analise
                
                # Etapa 4: Índice
                status_placeholder.info("🤖 **Etapa 4/4**: Criando índice de IA...")
                progress_bar.progress(90, text="🤖 Preparando IA (90%)")
                
                # SALVA O DOSSIÊ EM DISCO E ATUALIZA O ÍNDICE FAISS
                ds.salvarDossieInvestigativo(dossie, "dossie_investigativo.json")
                
                progress_bar.progress(100, text="✅ Análise concluída!")
                status_placeholder.success(f"✅ **Sucesso!** Carteira analisada: `{wallet_analise[:20]}...`")
                
                # Limpar placeholders após 2 segundos
                import time
                time.sleep(2)
                progress_placeholder.empty()
                status_placeholder.empty()
                
                st.toast("✅ Dashboard pronto para visualização!", icon="🎉")
                
                # Força o recarregamento da aplicação para garantir que o estado
                st.rerun()
                
            except Exception as e:
                progress_placeholder.empty()
                status_placeholder.error(f"❌ **Erro na análise:** {str(e)}")
                st.error(f"""
                ### Solução de Problemas:
                
                1. **API indisponível?** - Tente uma carteira diferente
                2. **Carteira sem histórico?** - Use uma das sugeridas na seção "Exemplos"
                3. **Timeout?** - Reduza a profundidade (tente 2-3 em vez de 4)
                4. **Memória insuficiente?** - Reduza "Máximo de nós" para 200-300
                
                **Erro técnico:** {e}
                """)

    if "grafo_index" not in st.session_state:
        st.session_state.grafo_index = 0

    if "agent" not in st.session_state:
        st.session_state.agent = None
        
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = [{
            "role": "assistant", 
            "content": "Sou o investigador forense. Pergunte sobre o grafo ou transações suspeitas."
        }]

    # Inicializa o estado das opções de visualização
    if "mostrar_nomes" not in st.session_state:
        st.session_state.mostrar_nomes = True
    if "mostrar_valores" not in st.session_state:
        st.session_state.mostrar_valores = True

    if "historico" not in st.session_state:
        st.info(
            "🔎 Insira o endereço da carteira e clique em **🚀 Iniciar Análise Forense**. "
            "A interface de grafos e o dossiê serão exibidos após o processamento."
        )
        return

    # =========================
    # TABS
    # =========================
    tab_grafos, tab_dossie, tab_chat = st.tabs([
        "📊 Fluxo de Grafos",
        "📄 Dossiê Investigativo",
        "🔎 Assistente IA Forense"
    ])

    # =========================
    # RESUMO DE CONFIGURAÇÃO ATIVA
    # =========================
    with st.container():
        col_info1, col_info2, col_info3, col_info4, col_info5 = st.columns(5)
        with col_info1:
            st.metric(
                "📍 Carteira",
                st.session_state.get("wallet_ativo", "")[:10] + "...",
                help=st.session_state.get("wallet_ativo", "Desconhecida")
            )
        with col_info2:
            st.metric(
                "🔍 Profundidade",
                st.session_state.get("profundidade_config", 4),
                help="Níveis de busca"
            )
        with col_info3:
            st.metric(
                "📊 Máx. Nós",
                st.session_state.get("max_nos_config", 500),
                help="Limite de nós"
            )
        with col_info4:
            sensib = st.session_state.get("sensibilidade_config", "Médio")
            cor_sensib = "🟢" if sensib == "Baixo" else "🟡" if sensib == "Médio" else "🔴"
            st.metric(
                "⚠️ Sensibilidade",
                f"{cor_sensib} {sensib}",
                help="Nível de detecção de risco"
            )
        with col_info5:
            comportamentos = st.session_state.get("comportamentos_config", {})
            total_comportamentos = sum(1 for v in comportamentos.values() if v)
            st.metric(
                "🚨 Comportamentos",
                f"{total_comportamentos}/5",
                help="Tipos de suspeita detectados"
            )
        st.divider()

    # =========================
    # ABA 1 - GRAFOS (ATUALIZADA)
    # =========================

    with tab_grafos:
        historico = st.session_state.get("historico", [])
        
        # 1. Verifica se a lista existe antes de qualquer coisa
        if not historico:
            st.warning("### 🔍 Investigação Inconclusiva")
            st.markdown("""
            Não foi possível obter dados transacionais suficientes para este endereço. 
            Isso ocorre devido a restrições técnicas na indexação de carteiras ou 
            falta de histórico ativo na rede.
            """)
            return  # Encerra esta aba graciosamente
        
        # 2. Calcula o índice seguro para evitar o erro 'out of range'
        # Pega o índice atual salvo, ou começa em 0
        index_atual = st.session_state.get("grafo_index", 0)
        
        # O 'min' garante que nunca buscaremos um índice maior que o último item da lista
        index_seguro = max(0, min(index_atual, len(historico) - 1))
        
        # 3. Atualiza o session_state com o índice validado
        st.session_state.grafo_index = index_seguro

        # 4. Agora é totalmente seguro acessar a lista
        index = index_seguro
        etapa = historico[index]
        
        # --- A partir daqui, você pode continuar renderizando o seu Grafo ---
        st.write(f"Visualizando: {etapa['nome']}")
        # (seu código de exibição do grafo aqui)

        # =========================
        # MÉTRICAS DE REDUÇÃO (ADICIONE AQUI)
        # =========================
        with st.expander("📊 Métricas de Redução do Grafo", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            grafo_inicial = historico[0]['grafo']
            nos_iniciais = grafo_inicial.number_of_nodes()
            arestas_iniciais = grafo_inicial.number_of_edges()
            
            grafo_atual = etapa['grafo']
            nos_atuais = grafo_atual.number_of_nodes()
            arestas_atuais = grafo_atual.number_of_edges()
            
            with col1:
                reducao_nos = ((nos_iniciais - nos_atuais) / nos_iniciais) * 100
                st.metric(
                    label="Nós",
                    value=f"{nos_atuais}",
                    delta=f"-{reducao_nos:.1f}% ({nos_iniciais - nos_atuais} removidos)"
                )
            
            with col2:
                reducao_arestas = ((arestas_iniciais - arestas_atuais) / arestas_iniciais) * 100
                st.metric(
                    label="Arestas",
                    value=f"{arestas_atuais}",
                    delta=f"-{reducao_arestas:.1f}% ({arestas_iniciais - arestas_atuais} removidas)"
                )
            
            with col3:
                # Densidade do grafo
                densidade_inicial = nx.density(grafo_inicial.to_undirected())
                densidade_atual = nx.density(grafo_atual.to_undirected())
                variacao_densidade = ((densidade_atual - densidade_inicial) / densidade_inicial) * 100 if densidade_inicial > 0 else 0
                
                st.metric(
                    label="Densidade",
                    value=f"{densidade_atual:.4f}",
                    delta=f"{variacao_densidade:+.1f}%"
                )

        # =========================
        # PROGRESSO DAS ETAPAS
        # =========================
        with st.expander("🔄 Pipeline de Transformação", expanded=False):
            # Barra de progresso horizontal
            etapa_nomes = [h['nome'] for h in historico]
            etapa_atual_idx = index_seguro 
            # Mostra etapas como badges
            cols = st.columns(len(etapa_nomes))
            for i, (col, nome) in enumerate(zip(cols, etapa_nomes)):
                with col:
                    if i < etapa_atual_idx:
                        st.success(f"✅ {nome.split('.')[1].strip()}")
                    elif i == etapa_atual_idx:
                        st.info(f"🔵 {nome.split('.')[1].strip()}")
                    else:
                        st.text(f"⬜ {nome.split('.')[1].strip()}")
            
            st.progress((index_seguro + 1) / len(historico))

        # =========================
        # GRAFO INTERATIVO
        # =========================
        dg.renderizar_grafo_interativo(
            G=etapa["grafo"],
            carteira_principal=st.session_state.get("wallet_ativo", "desconhecida"),
            scores=etapa["scores"],
            trajetorias_destacadas=etapa.get("trajetorias"),
            possiveis_mixers=etapa.get("possiveis_mixers"),
            carteiras_alto_risco=etapa.get("carteiras_alto_risco"),
            mostrar_nomes_carteiras=st.session_state.mostrar_nomes,
            mostrar_valores_transacoes=st.session_state.mostrar_valores
        )

        st.divider()

        # =========================
        # NAVEGAÇÃO
        # =========================
        col1, col2, col3 = st.columns([1, 3, 1])

        with col1:
            if st.button("⬅️", key="prev"):
                if st.session_state.grafo_index > 0:
                    # Reseta as opções de visualização ao navegar
                    st.session_state.mostrar_nomes = True
                    st.session_state.mostrar_valores = True
                    st.session_state.grafo_index -= 1
                    st.rerun()

        with col3:
            if st.button("➡️", key="next"):
                if st.session_state.grafo_index < len(historico) - 1:
                    # Reseta as opções de visualização ao navegar
                    st.session_state.mostrar_nomes = True
                    st.session_state.mostrar_valores = True
                    st.session_state.grafo_index += 1
                    st.rerun()

        st.subheader(etapa["nome"])

        # =========================
        # MÉTRICAS ESPECÍFICAS DA ETAPA
        # =========================
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Nós", etapa['grafo'].number_of_nodes())
        with col2:
            st.metric("Arestas", etapa['grafo'].number_of_edges())
        with col3:
            st.metric("Carteiras Alto Risco", 
                    len([s for s in etapa['scores'].values() if s['risco'] == 'ALTO']))
        with col4:
            trajetorias = etapa.get('trajetorias', [])
            if trajetorias:
                st.metric("Tamanho da Rota Principal", len(trajetorias[0].get('caminho', [])))
            else:
                st.metric("Tamanho da Rota Principal", "N/A")

        st.divider()

        # =========================
        # LEGENDA
        # =========================
        with st.columns([1])[0]:
            if etapa["nome"] == "7. Grafo Final (Consolidado)":
                st.caption(
                    f"**Nós:** "
                    f"<span style='color:#006400; font-weight:bold;'>■</span> Carteira Inicial | "
                    f"<span style='color:#8400FF; font-weight:bold;'>■</span> Possível Mixer | "
                    f"<span style='color:#800000; font-weight:bold;'>■</span> Alto Risco | "
                    f"Nó com **Borda Azul** = Parte de Trajetória",
                    unsafe_allow_html=True
                )
                st.caption(
                    f"**Arestas:** "
                    f"<span style='color:#0000FF; font-weight:bold;'>━━</span> Trajetória Principal | "
                    f"<span style='color:#4169E1; font-weight:bold;'>- - -</span> Trajetórias Secundárias | "
                    f"<span style='color:#b5b0a3; font-weight:bold;'>━━</span> Transação",
                    unsafe_allow_html=True
                )
            else:
                st.caption(
                    f"**Nós (Grau de Risco):** "
                    f"<span style='color:#006400; font-weight:bold;'>■</span> Carteira Inicial | "
                    f"<span style='color:#8B0000; font-weight:bold;'>■</span> Crítico | "
                    f"<span style='color:#FF0000; font-weight:bold;'>■</span> Alto | "
                    f"<span style='color:#FFA500; font-weight:bold;'>■</span> Médio | "
                    f"<span style='color:#83fc85; font-weight:bold;'>■</span> Baixo | "
                    f"<span style='color:#D3D3D3; font-weight:bold;'>■</span> Sem Evidência | "
                    f"Nó com **Borda Azul** = Parte de Trajetória",
                    unsafe_allow_html=True
                )
                st.caption(
                    f"**Arestas:**"
                    f"<span style='color:#0000FF; font-weight:bold;'>━━</span> Trajetória Provável | "
                    f"<span style='color:#4169E1; font-weight:bold;'>- - -</span> Trajetórias Secundárias | "
                    f"<span style='color:#b5b0a3; font-weight:bold;'>━━</span> Transação",
                    unsafe_allow_html=True
                    )
        
        st.divider()
        
        # =========================
        # OPÇÕES DE VISUALIZAÇÃO
        # =========================
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            st.session_state.mostrar_nomes = st.checkbox("Exibir nomes das carteiras", value=st.session_state.mostrar_nomes, key="mostrar_nomes_cb")
        with col_opt2:
            st.session_state.mostrar_valores = st.checkbox("Exibir valores das transações", value=st.session_state.mostrar_valores, key="mostrar_valores_cb")

        st.divider()

        # =========================
        # TABELA COMPARATIVA DAS ETAPAS
        # =========================
        with st.expander("📈 Evolução das Métricas por Etapa", expanded=False):
            dados_evolucao = []
            for i, h in enumerate(historico):
                g = h['grafo']
                scores = h['scores']
                
                alto_risco = len([s for s in scores.values() if s['risco'] == 'ALTO'])
                medio_risco = len([s for s in scores.values() if s['risco'] == 'MEDIO'])
                
                nome_etapa = h['nome']
                if '. ' in nome_etapa:
                    nome_etapa = nome_etapa.split('. ', 1)[1]
                
                dados_evolucao.append({
                    'Etapa': nome_etapa,
                    'Nós': g.number_of_nodes(),
                    'Arestas': g.number_of_edges(),
                    'Densidade': f"{calcular_densidade(g):.3f}",
                    'Alto Risco': alto_risco,
                    'Médio Risco': medio_risco,
                    'Tamanho Rota': len(h['trajetorias'][0]['caminho']) if h.get('trajetorias') else 0
                })
            
            df_evolucao = pd.DataFrame(dados_evolucao)
            
            st.dataframe(
                df_evolucao,
                use_container_width=True,
                hide_index=True
            )
            
            try:
                import plotly.graph_objects as go
                
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=df_evolucao['Etapa'],
                    y=df_evolucao['Nós'],
                    mode='lines+markers',
                    name='Nós',
                    line=dict(color='blue', width=3),
                    marker=dict(size=10)
                ))
                
                fig.add_trace(go.Scatter(
                    x=df_evolucao['Etapa'],
                    y=df_evolucao['Arestas'],
                    mode='lines+markers',
                    name='Arestas',
                    line=dict(color='red', width=3),
                    marker=dict(size=10),
                    yaxis='y2'
                ))
                
                fig.update_layout(
                    title={
                        'text': 'Redução do Grafo por Etapa',
                        'x': 0.5,
                        'xanchor': 'center'
                    },
                    xaxis={
                        'title': 'Etapa',
                        'tickangle': -45
                    },
                    yaxis={
                        'title': {
                            'text': 'Nós',
                            'font': {'color': 'blue'}
                        },
                        'tickfont': {'color': 'blue'}
                    },
                    yaxis2={
                        'title': {
                            'text': 'Arestas',
                            'font': {'color': 'red'}
                            },
                        'tickfont': {'color': 'red'},
                        'overlaying': 'y',
                        'side': 'right'
                    },
                    hovermode='x unified',
                    legend={
                        'orientation': 'h',
                        'yanchor': 'bottom',
                        'y': 1.02,
                        'xanchor': 'right',
                        'x': 1
                    },
                    margin=dict(t=50, b=100)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.warning(f"Gráfico Plotly não disponível: {e}")

    with tab_dossie:
        dd.render_dashboard_dossie()

        # Dossiê (original)
        with st.expander("Dossiê Investigativo"):
            st.json(st.session_state.dossie)

    # ================================
    # ABA 2 - CHAT
    # ================================
    with tab_chat:

        # Verifica se o índice FAISS já foi criado. Se não, desabilita o chat.
        if not os.path.exists("faiss_index"):
            st.info("O assistente de IA estará disponível assim que o processamento inicial da blockchain for concluído.")
            st.warning("Por favor, aguarde a geração do dossiê.")
        else:
            st.subheader("🔎 Chat Forense Blockchain")
            st.caption("Investigação assistida por Inteligência Artificial")

            if st.session_state.agent is None:
                with st.spinner("Inicializando o agente analítico..."):
                    st.session_state.agent = carregar_agent()

            llm, retriever, prompt = st.session_state.agent

            # Exibe o histórico de mensagens
            for msg in st.session_state.mensagens:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"], unsafe_allow_html=True)

            # Captura o input do usuário
            if pergunta := st.chat_input("Sua pergunta sobre as transações:"):
                # Adiciona a pergunta do usuário ao histórico e à tela
                st.session_state.mensagens.append({"role": "user", "content": pergunta})
                with st.chat_message("user"):
                    st.markdown(pergunta)

                # Gera e exibe a resposta da IA
                with st.chat_message("assistant"):
                    placeholder = st.empty()
                    placeholder.markdown("🧠 Analisando dados...")
                    try:
                        resposta = ag.responder(
                            llm,
                            retriever,
                            prompt,
                            pergunta
                        )
                        placeholder.markdown(resposta, unsafe_allow_html=True)
                        st.session_state.mensagens.append({"role": "assistant", "content": resposta})
                    
                    except Exception as e:
                        error_message = f"Ocorreu um erro: {e}"
                        if "429" in str(e) or "Quota exceeded" in str(e):
                            error_message = "🚨 Limite de requisições à API atingido. Por favor, aguarde um minuto antes de tentar novamente."
                        
                        placeholder.error(error_message)
                        st.session_state.mensagens.append({"role": "assistant", "content": error_message})
                
                # Força a re-execução para limpar o campo de input e evitar reenvio
                st.rerun()