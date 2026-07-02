import streamlit as st
import app_streamlit as ui


def executar_pipeline_completo(wallet, profundidade=4, max_vizinhos=100, max_nos=500, sensibilidade="Médio", comportamentos=None, valor_minimo=None, valor_maximo=None, ts_inicio=None, ts_fim=None):
    """Orquestra a execução do pipeline reutilizando a função de processamento
    definida em `app_streamlit.py` e retorna um dicionário com os dados.
    """
    # Chama a função com cache que já existe no app principal
    historico, dossie = ui.carregar_toda_a_blockchain(
        wallet,
        profundidade=profundidade,
        max_vizinhos=max_vizinhos,
        max_nos=max_nos,
        sensibilidade=sensibilidade,
        comportamentos=comportamentos,
        valor_minimo=valor_minimo,
        valor_maximo=valor_maximo,
        ts_inicio=ts_inicio,
        ts_fim=ts_fim
    )

    return {
        "historico": historico,
        "dossie": dossie,
        "wallet_ativo": wallet,
    }


def renderizar_dashboard(data: dict):
    """Renderização mínima do resultado. Define chaves em `st.session_state`
    para que a UI principal (`app_streamlit`) possa reutilizá-las, e mostra
    um resumo rápido na tela.
    """
    if not data:
        st.warning("Nenhum dado para exibir.")
        return

    st.session_state["historico"] = data.get("historico", [])
    st.session_state["dossie"] = data.get("dossie", {})
    st.session_state["wallet_ativo"] = data.get("wallet_ativo", "")

    st.success(f"Análise concluída para: {st.session_state.get('wallet_ativo','')}")

    # Exibe um resumo compacto enquanto o usuário navega para as abas
    if st.session_state.get("dossie"):
        st.subheader("Dossiê (resumo)")
        st.json({
            "carteiras_alto_risco": st.session_state["dossie"].get("carteiras_alto_risco", []),
            "possiveis_mixers": st.session_state["dossie"].get("possiveis_mixers", []),
        })

    if st.session_state.get("historico"):
        st.subheader("Etapas executadas")
        st.write([h["nome"] for h in st.session_state["historico"]])

    st.info("Vá para a aba 'Fluxo de Grafos' para visualizar o resultado completo.")
