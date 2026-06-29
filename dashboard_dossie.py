import json
import os
from typing import Any, Dict

import pandas as pd
import plotly.express as px
import streamlit as st


DEFAULT_DOSSIE_PATH = "dossie_investigativo.json"


def carregar_dossie(caminho: str = DEFAULT_DOSSIE_PATH) -> Dict[str, Any]:
    if not os.path.exists(caminho):
        return {}

    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (json.JSONDecodeError, OSError):
        return {}


def _resumo_indicadores(dossie: Dict[str, Any]) -> Dict[str, Any]:
    carteiras = dossie.get("carteiras_alto_risco", [])
    if carteiras:
        primeira = carteiras[0]
        score_risco = primeira.get("score", "N/A")
        risco = primeira.get("risco", "N/A")
    else:
        score_risco = "N/A"
        risco = "N/A"

    resumo = dossie.get("resumo_grafo", {})
    return {
        "carteira_inicial": dossie.get("carteira_inicial", "N/A"),
        "score_risco": score_risco,
        "classificacao": risco,
        "nos": resumo.get("nos", 0),
        "arestas": resumo.get("arestas", 0),
        "clusters": resumo.get("clusters", 0),
        "carteiras_alto_risco": len(carteiras),
        "mixers": len(dossie.get("possiveis_mixers", [])),
        "trajetorias": len(dossie.get("trajetorias_provaveis", [])),
        "coinjoin": len(dossie.get("transacoes_coinjoin_suspeitas", [])),
    }


def _montar_dataframe(dossie: Dict[str, Any]) -> pd.DataFrame:
    categorias = [
        "Carteiras de Alto Risco",
        "Possíveis Mixers",
        "Trajetórias Prováveis",
        "Transações CoinJoin Suspeitas",
    ]
    valores = [
        len(dossie.get("carteiras_alto_risco", [])),
        len(dossie.get("possiveis_mixers", [])),
        len(dossie.get("trajetorias_provaveis", [])),
        len(dossie.get("transacoes_coinjoin_suspeitas", [])),
    ]
    return pd.DataFrame({"Categoria": categorias, "Quantidade": valores})


def _texto_analise(dossie: Dict[str, Any]) -> str:
    indicadores = _resumo_indicadores(dossie)
    linhas = [
        f"Carteira inicial: {indicadores['carteira_inicial']}",
        f"Score de risco principal: {indicadores['score_risco']}",
        f"Quantidade de carteiras de alto risco: {indicadores['carteiras_alto_risco']}",
        f"Possíveis mixers detectados: {indicadores['mixers']}",
        f"Trajetórias prováveis: {indicadores['trajetorias']}",
        "Análise rápida: sinais de concentração em hubs, divisão de valores e padrões temporais suspeitos merecem atenção prioritária.",
    ]
    return "\n".join(linhas)


def render_dashboard_dossie(dossie: Dict[str, Any] | None = None, caminho: str = DEFAULT_DOSSIE_PATH) -> None:
    if dossie is None:
        dossie = carregar_dossie(caminho)

    if not dossie:
        st.info("Ainda não existe um dossiê investigativo salvo para exibir.")
        return

    indicadores = _resumo_indicadores(dossie)

    st.title("📄 Dashboard Investigativo")
    st.caption("Resumo visual do dossiê gerado durante a análise da carteira")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Carteira inicial", indicadores["carteira_inicial"][:20] + "...", help=indicadores["carteira_inicial"])
    with col2:
        st.metric("Score de risco", indicadores["score_risco"])
    with col3:
        st.metric("Classificação", indicadores["classificacao"])

    st.subheader("Resumo Executivo")
    st.markdown(
        f"""
        - Nós no grafo: **{indicadores['nos']}**
        - Arestas: **{indicadores['arestas']}**
        - Clusters: **{indicadores['clusters']}**
        - Carteiras de alto risco: **{indicadores['carteiras_alto_risco']}**
        - Possíveis mixers: **{indicadores['mixers']}**
        - Trajetórias prováveis: **{indicadores['trajetorias']}**
        - Transações CoinJoin suspeitas: **{indicadores['coinjoin']}**
        """
    )

    st.subheader("Visualização das Evidências")
    df = _montar_dataframe(dossie)

    col_pizza, col_barra = st.columns(2)
    with col_pizza:
        fig_pizza = px.pie(df, values="Quantidade", names="Categoria", title="Distribuição por categoria")
        st.plotly_chart(fig_pizza, use_container_width=True)
        st.caption("A pizza mostra a participação relativa das categorias detectadas no dossiê.")

    with col_barra:
        fig_barra = px.bar(df, x="Categoria", y="Quantidade", text="Quantidade", title="Volume de evidências")
        st.plotly_chart(fig_barra, use_container_width=True)
        st.caption("A barra destaca quais categorias concentram mais sinais suspeitos.")

    st.subheader("Síntese da Investigação")
    st.info(_texto_analise(dossie))

    tab_risco, tab_mixers, tab_observacoes = st.tabs(["Carteiras de Alto Risco", "Possíveis Mixers", "Observações"])

    with tab_risco:
        carteiras = dossie.get("carteiras_alto_risco", [])
        if carteiras:
            st.dataframe(pd.DataFrame(carteiras))
        else:
            st.write("Nenhuma carteira de alto risco identificada.")

    with tab_mixers:
        mixers = dossie.get("possiveis_mixers", [])
        if mixers:
            st.dataframe(pd.DataFrame(mixers))
        else:
            st.write("Nenhum possível mixer identificado.")

    with tab_observacoes:
        observacoes = dossie.get("observacoes", [])
        if observacoes:
            for item in observacoes:
                st.write(f"- {item}")
        else:
            st.write("Nenhuma observação disponível.")
