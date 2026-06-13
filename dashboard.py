import streamlit as st
import pandas as pd

df = pd.read_csv("transacoesbtcsimples.csv")

st.title("Dashboard de Rastreamento Bitcoin")

st.subheader("Transações")

st.dataframe(df)

st.subheader("Detalhes")

st.write("Quantidade de transações:", len(df))

st.write("Valor total:", df["valor"].sum())