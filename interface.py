import json
import time
import streamlit as st
import etapa5_graphsense as etp5
import heuristica as ht
import agent as ag
import dossie as ds
import dashboard_graph as dg
import gerar_grafo as etp2 
import plotly.graph_objects as go
import networkx as nx
import pandas as pd

# ==============================================================================
# 1. CONFIGURAÇÃO DE PÁGINA DO STREAMLIT (OBRIGATORIAMENTE O PRIMEIRO COMANDO)
# ==============================================================================
st.set_page_config(
    layout="wide", 
    page_title="Sistema Antiransomware - Forense Blockchain", 
    page_icon="🕵️‍♂️"
)
# ==============================================================================
# 2. FUNÇÃO COM CACHE PARA PROCESSAMENTO PESADO DA BLOCKCHAIN
# ==============================================================================
@st.cache_resource(show_spinner=False)
def carregar_toda_a_blockchain(wallet):
    
    historico = []
    # =========================
    # 1. GRAFO BRUTO
    # =========================
    G_bruto = etp5.expandirGrafo(wallet, profundidade=4, 
                                  max_vizinhos=100, max_nos=500)
    score_bruto = ht.calcularScoreRisco(G_bruto, wallet)
    historico.append({
        "nome": "1. Grafo Bruto",
        "grafo": G_bruto,
        "scores": score_bruto,
        "caminho": None
    })
    
    # =========================
    # 2. MULTI INPUT (Agrupa donos)
    # =========================
    uf = ht.heuristicaMultiInput(G_bruto)
    G_multi = etp5.construirGrafoFiltrado(G_bruto, uf)
    
    score_multi = ht.calcularScoreRisco(G_multi, wallet)
    trajetorias_multi = ht.encontrarTrajetoriasProvaveis(G_multi, wallet, score_multi)
    historico.append({
        "nome": "2. Multi-Input (Agrupamento de Carteiras)",
        "grafo": G_multi,
        "scores": score_multi,
        "caminho": trajetorias_multi[0]["caminho"] if trajetorias_multi else None
    })
    
    # =========================
    # 3. VALORES (Marca similaridades)
    # =========================
    G_valores = ht.aplicarValores(G_multi)
    
    score_valores = ht.calcularScoreRisco(G_valores, wallet)
    trajetorias_valores = ht.encontrarTrajetoriasProvaveis(G_valores, wallet, score_valores)
    historico.append({
        "nome": "3. Análise de Valores",
        "grafo": G_valores,
        "scores": score_valores,
        "caminho": trajetorias_valores[0]["caminho"] if trajetorias_valores else None
    })
    
    # =========================
    # 4. TEMPO (Filtra janelas suspeitas)
    # =========================
    G_tempo = ht.aplicarTempo(G_valores)
    
    score_tempo = ht.calcularScoreRisco(G_tempo, wallet)
    trajetorias_tempo = ht.encontrarTrajetoriasProvaveis(G_tempo, wallet, score_tempo)
    historico.append({
        "nome": "4. Filtro Temporal",
        "grafo": G_tempo,
        "scores": score_tempo,
        "caminho": trajetorias_tempo[0]["caminho"] if trajetorias_tempo else None
    })
    
    # =========================
    # 5. CHANGE ADDRESS (Remove troco)
    # =========================
    G_change = ht.aplicarChangeAddress(G_tempo)
    
    score_change = ht.calcularScoreRisco(G_change, wallet)
    trajetorias_change = ht.encontrarTrajetoriasProvaveis(G_change, wallet, score_change)
    historico.append({
        "nome": "5. Change Address (Remoção de Troco)",
        "grafo": G_change,
        "scores": score_change,
        "caminho": trajetorias_change[0]["caminho"] if trajetorias_change else None
    })
    
    # =========================
    # 6. CHAIN (Simplifica caminhos lineares)
    # =========================
    G_chain = ht.aplicarChain(G_change)
    
    score_chain = ht.calcularScoreRisco(G_chain, wallet)
    trajetorias_chain = ht.encontrarTrajetoriasProvaveis(G_chain, wallet, score_chain)
    historico.append({
        "nome": "6. Simplificação de Cadeias",
        "grafo": G_chain,
        "scores": score_chain,
        "caminho": trajetorias_chain[0]["caminho"] if trajetorias_chain else None
    })
    
    # =========================
    # 7. DOSSIÊ FINAL
    # =========================
    possiveis_mixers = ht.detectarPossiveisMixers(G_chain)
    dossie = ds.gerarDossieInvestigativo(
        G_chain, wallet, score_chain, 
        trajetorias_chain, possiveis_mixers
    )
    
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
    return _retriever.invoke(query)

def iniciarChat(llm, prompt):

    st.markdown("""
        <style>
        .stChatMessage { font-size: 15px; }
        .block-container { padding-top: 2rem; }
        </style>
    """, unsafe_allow_html=True)

    # =========================
    # STATE INICIAL
    # =========================
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = [
            {
                "role": "assistant",
                "content": "Sou o investigador forense. Pergunte sobre o grafo ou transações suspeitas."
            }
        ]

    if "last_llm_call" not in st.session_state:
        st.session_state.last_llm_call = 0

    if "processing" not in st.session_state:
        st.session_state.processing = False

    # =========================
    # EXIBIÇÃO HISTÓRICO
    # =========================
    for msg in st.session_state.mensagens:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # =========================
    # INPUT
    # =========================
    pergunta = st.chat_input("Sua pergunta sobre as transações:")

    # =========================
    # CONTROLE PRINCIPAL
    # =========================
    if pergunta:

        pergunta_limpa = pergunta.strip()
        if not pergunta_limpa:
            st.stop()

        if st.session_state.processing:
            st.warning("Já estou processando uma pergunta. Aguarde...")
            st.stop()

        st.session_state.processing = True

        try:
            now = time.time()
            if now - st.session_state.last_llm_call < 3:
                st.warning("⏳ Aguarde alguns segundos antes de enviar outra pergunta.")
                st.stop()

            st.session_state.last_llm_call = now

            st.session_state.mensagens.append(
                {"role": "user", "content": pergunta_limpa}
            )

            with st.chat_message("user"):
                st.markdown(pergunta_limpa)

            with st.chat_message("assistant"):
                placeholder = st.empty()
                placeholder.markdown("🧠 Analisando dados...")

                contexto = json.dumps(st.session_state.dossie, ensure_ascii=False)

                mensagens = prompt.invoke({
                    "contexto": contexto,
                    "pergunta": pergunta_limpa
                })

                resposta = llm.invoke(mensagens).content

                placeholder.markdown(resposta)

                st.session_state.mensagens.append(
                    {"role": "assistant", "content": resposta}
                )

        except Exception as e:
            if "429" in str(e) or "Quota exceeded" in str(e):
                st.error("🚨 Limite de requisições atingido. Aguarde 30–60 segundos.")
            else:
                st.error(f"Erro: {e}")

        finally:
            st.session_state.processing = False

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

    st.title("🕵️ Dashboard Interativo - Rastreamento de Ransomware")

    wallet = "bc1q4my6vqq8cg689drf9jccqudjclv67sz4cudkyd"

    # =========================
    # INIT GLOBAL STATE
    # =========================
    if "historico" not in st.session_state:
        with st.spinner("Processando blockchain..."):
            historico, dossie = carregar_toda_a_blockchain(wallet)
            st.session_state.historico = historico
            st.session_state.dossie = dossie

    if "grafo_index" not in st.session_state:
        st.session_state.grafo_index = 0

    if "agent" not in st.session_state:
        st.session_state.agent = None

    # =========================
    # TABS
    # =========================
    tab_grafos, tab_chat = st.tabs([
        "📊 Fluxo de Grafos",
        "🔎 Assistente IA Forense"
    ])

    # =========================
    # ABA 1 - GRAFOS (ATUALIZADA)
    # =========================
    with tab_grafos:

        historico = st.session_state.historico
        index = st.session_state.grafo_index

        index = max(0, min(index, len(historico) - 1))
        st.session_state.grafo_index = index

        etapa = historico[index]

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
            etapa_atual_idx = index
            
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
            
            st.progress((index + 1) / len(historico))

        # =========================
        # NAVEGAÇÃO
        # =========================
        col1, col2, col3 = st.columns([1, 3, 1])

        with col1:
            if st.button("⬅️", key="prev"):
                if st.session_state.grafo_index > 0:
                    st.session_state.grafo_index -= 1
                    st.rerun()

        with col3:
            if st.button("➡️", key="next"):
                if st.session_state.grafo_index < len(historico) - 1:
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
            if etapa['caminho']:
                st.metric("Tamanho da Rota", len(etapa['caminho']))
            else:
                st.metric("Tamanho da Rota", "N/A")

        st.divider()

        # =========================
        # LEGENDA
        # =========================
        with st.columns([1])[0]:
            # Nós
            st.caption(
                f"**Nós (Grau de Risco):** "
                f"🟤 `{dg.corPorRiscoHex(80)}` Crítico | "
                f"🔴 `{dg.corPorRiscoHex(60)}` Alto | "
                f"🟠 `{dg.corPorRiscoHex(40)}` Médio | "
                f"🟢 `{dg.corPorRiscoHex(1)}` Baixo | "
                f"⬜ `{dg.corPorRiscoHex(0)}` Sem Evidência"
            )
            # Arestas
            st.caption(
                f"**Arestas (Fluxo Financeiro):** "
                f"🔵 Linha Azul Espessa = Trajetória Investigativa Destacada | "
                f"⚪ Linha Cinza = Fluxo Transacional Comum | "
            )
        
        st.divider()
        
        # =========================
        # GRAFO INTERATIVO
        # =========================
        dg.renderizar_grafo_interativo(
            G=etapa["grafo"],
            carteira_principal=wallet,
            scores=etapa["scores"],
            caminho_destacado=etapa["caminho"]
        )

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
                
                # Extrai nome limpo da etapa
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
                    'Tamanho Rota': len(h['caminho']) if h['caminho'] else 0
                })
            
            df_evolucao = pd.DataFrame(dados_evolucao)
            
            # Mostra tabela
            st.dataframe(
                df_evolucao,
                use_container_width=True,
                hide_index=True
            )
            
            # =========================
            # GRÁFICO
            # =========================
            try:
                import plotly.graph_objects as go
                
                fig = go.Figure()
                
                # Eixo Y principal - Nós
                fig.add_trace(go.Scatter(
                    x=df_evolucao['Etapa'],
                    y=df_evolucao['Nós'],
                    mode='lines+markers',
                    name='Nós',
                    line=dict(color='blue', width=3),
                    marker=dict(size=10)
                ))
                
                # Eixo Y secundário - Arestas
                fig.add_trace(go.Scatter(
                    x=df_evolucao['Etapa'],
                    y=df_evolucao['Arestas'],
                    mode='lines+markers',
                    name='Arestas',
                    line=dict(color='red', width=3),
                    marker=dict(size=10),
                    yaxis='y2'
                ))
                
                # Layout simplificado (sem parâmetros problemáticos)
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
                
                # Fallback: gráfico simples do Streamlit
                st.line_chart(
                    df_evolucao.set_index('Etapa')[['Nós', 'Arestas']]
                )

        # Dossiê (original)
        with st.expander("Dossiê Investigativo"):
            st.json(st.session_state.dossie)

    # ================================
    # ABA 2 - CHAT
    # ================================
    with tab_chat:

        st.subheader("🔎 Chat Forense Blockchain")
        st.caption("Investigação assistida por Inteligência Artificial")

        if st.session_state.agent is None:
            with st.spinner("Inicializando o agente analítico..."):
                st.session_state.agent = carregar_agent()

        llm, prompt = st.session_state.agent

        iniciarChat(llm, prompt)