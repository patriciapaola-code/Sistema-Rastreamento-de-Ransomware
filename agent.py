from dotenv import load_dotenv
import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

def criarAgent():
    # Carregar variáveis de ambiente
    load_dotenv()
    google_api_key = os.getenv("GOOGLE_API_KEY")
      
    if not google_api_key:
        raise ValueError("Erro: GOOGLE_API_KEY não foi encontrada no arquivo .env")

    # Criar modelo do Google Gemini
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash"
    )

    # Ler arquivo JSON
    try:
        with open("dossie_investigativo.json", "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)

    except FileNotFoundError:
        raise FileNotFoundError("Erro: O arquivo 'dossie_investigativo.json' não foi encontrado.")
    except json.JSONDecodeError:
        raise ValueError("Erro: O arquivo JSON está mal formatado.")

    # Converter cada seção do JSON em um documento
    try:
        documents = []

        for chave, valor in dados.items():
            texto = (
                f"{chave}:\n"
                f"{json.dumps(valor, indent=2, ensure_ascii=False)}"
            )

            documents.append(
                Document(page_content=texto)
            )

    except Exception as e:
        raise RuntimeError(f"Erro ao criar documentos: {e}")

    # Criar embeddings do Hugging Face
    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        # Criar vectorstore FAISS
        vectorstore = FAISS.from_documents(documents, embeddings)

        # Recuperar os 3 documentos mais relevantes
        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 3}
        )

    except Exception as e:
        raise RuntimeError(f"Erro ao criar vectorstore: {e}")

    # Prompt para instruir a IA
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Você é um investigador cibernético brilhante e obstinado, com a mente analítica de Sherlock Holmes e o foco implacável do Batman. "
            "Sua missão é analisar dados de transações blockchain e rastreamento de ransomware para construir cenários e hipóteses criminais baseadas estritamente nos fatos fornecidos.\n\n"
            "Siga estas diretrizes fundamentais de conduta:\n"
            "1. Metodologia de Detetive: Diante de carteiras suspeitas, mixers ou indícios de lavagem de dinheiro, monte o cenário mais provável. Formule hipóteses claras sobre o comportamento do criminoso (ex: 'O fluxo indica que o suspeito tentou pulverizar os fundos para ocultar a origem...').\n"
            "2. Didática Acessível: Traduza conceitos técnicos complexos da blockchain para analogias do mundo real (ex: compare um 'mixer' a uma lavanderia que mistura cédulas marcadas, ou um 'smart contract' a um cofre digital com regras automáticas). O usuário comum deve entender seu raciocínio perfeitamente sem precisar de conhecimento prévio.\n"
            "3. Linha Tênue da Verdade: Diferencie o que é FATO (provado pelos dados) do que é HIPÓTESE/INDÍCIO (as probabilidades). Deixe claro que scores e indicadores são heurísticas, não provas definitivas em um tribunal.\n"
            "4. Integridade da Investigação: Nunca invente dados que não estão no contexto. Se faltarem pistas cruciais para fechar um cenário, diga: 'Falta uma peça neste quebra-cabeça...' e aponte o que seria necessário para concluir.\n"
            "5. Tom e Estilo: Seja observador, direto, astuto e use uma linguagem que evoque o clima de uma investigação sombria e cerebral. Se a entrada for incompreensível, responda que a pista está corrompida ou ilegível.\n"
            "6. O Quadro de Suspeitos (Grafo e Heurísticas): As informações que você recebe vêm de um grafo de transações Bitcoin que já passou por filtros e heurísticas de rastreamento de Ransomware. "
            "Trate esses dados como 'padrões de comportamento do alvo'. Se uma carteira foi filtrada como suspeita, explique o porquê de forma simples (ex: 'Esta carteira se comportou como um posto de coleta, recebendo frações de várias outras antes de mover o montante maior'). "
            "Sempre lembre o usuário de que essas heurísticas mapeiam probabilidades e conexões, e que você está refinando esses cenários para encontrar a rota de fuga do dinheiro."
        ),

        (
            "human",
            "Contexto:\n{contexto}\n\nPergunta: {pergunta}"
        )
    ])

    print("=== Investigador Blockchain ===")
    print("Digite 'sair' para encerrar.\n")

    while True:
        pergunta = input("Pergunta: ")

        if pergunta.lower() == "sair":
            break

        # Recupera os documentos mais relevantes
        docs = retriever.invoke(pergunta)

        # Junta o conteúdo dos documentos
        contexto = "\n\n".join(doc.page_content for doc in docs)

        # Monta a mensagem para o modelo
        mensagens = prompt.invoke({
            "contexto": contexto,
            "pergunta": pergunta
        })

        # Obtém a resposta do Gemini
        resposta = llm.invoke(mensagens)

        print("\nResposta:")
        print(resposta.content)
        print("-" * 50)
