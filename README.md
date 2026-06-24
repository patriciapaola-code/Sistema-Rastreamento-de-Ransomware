#  Sistema de Rastreamento de Ransomware e Análise Forense em Blockchain

Este projeto é uma plataforma de análise forense projetada para rastrear o fluxo de fundos ilícitos, como os provenientes de ataques de ransomware, na blockchain do Bitcoin. A ferramenta combina análise de grafos, um pipeline de heurísticas de simplificação e um assistente de investigação baseado em Inteligência Artificial (LLM) para transformar dados brutos de transações em insights e narrativas dedutivas.

##  Funcionalidades Principais

*   **Expansão de Grafo Automatizada:** A partir de uma carteira inicial suspeita, o sistema expande e constrói um grafo de transações, coletando dados diretamente da blockchain.
*   **Pipeline de Heurísticas:** Aplica uma série de filtros e transformações para reduzir o ruído e revelar a estrutura real do fluxo de fundos:
    *   **Agrupamento por Multi-Input:** Consolida carteiras que participam juntas em transações, aplicando a heurística de "common-input-ownership".
    *   **Remoção de Endereços de Troco:** Identifica e remove heuristicamente os endereços de troco para simplificar o rastreamento.
    *   **Análise Temporal:** Detecta "bursts" de atividade que podem indicar automação.
    *   **Simplificação de Cadeias:** Colapsa longas cadeias lineares de transações para focar nos pontos de distribuição e consolidação.
*   **Visualização Interativa:** Um dashboard construído com Streamlit permite navegar visualmente pelas etapas de transformação do grafo, destacando nós de alto risco, possíveis mixers e as trajetórias mais prováveis do dinheiro.
*   **Scoring de Risco Dinâmico:** Cada carteira no grafo recebe um score de risco com base em múltiplos fatores: proximidade com a fonte, centralidade no grafo (PageRank, Betweenness), padrões de transação e participação em atividades suspeitas (CoinJoin).
*   **Assistente Forense com IA:** Um agente de IA (utilizando Llama 3.3 via Groq e RAG) analisa um dossiê gerado automaticamente e responde a perguntas em linguagem natural, agindo como um "Sherlock Holmes cibernético" para explicar o que está acontecendo.

##  Como Funciona

O fluxo de trabalho da ferramenta é dividido em três fases principais:

1.  **Coleta e Modelagem:** O sistema consome dados da API da Blockstream para construir um `MultiDiGraph` usando a biblioteca NetworkX, onde os nós são carteiras e as arestas são transações.
2.  **Análise e Redução:** O grafo bruto passa pelo pipeline de heurísticas. A cada etapa, o grafo é simplificado e as métricas são recalculadas. Isso permite ao analista entender como cada técnica contribui para "limpar" a visualização e revelar o esqueleto da operação de lavagem.
3.  **Relatório e Investigação:** Ao final do pipeline, um dossiê completo em formato JSON é gerado. Este dossiê alimenta o índice vetorial (FAISS) que serve de base para o assistente de IA. O usuário pode então interagir com o grafo final e conversar com o assistente para aprofundar a investigação.

##  Tecnologias Utilizadas

*   **Backend & Lógica Principal:** Python
*   **Análise de Grafos:** NetworkX
*   **Manipulação de Dados:** Pandas, NumPy
*   **Dashboard Interativo:** Streamlit
*   **Visualização de Grafos:** `streamlit-agraph` (baseado em Vis.js)
*   **Inteligência Artificial:**
    *   **LLM:** Llama 3.3 via Groq API
    *   **Framework:** LangChain
    *   **RAG:** FAISS e HuggingFace Embeddings
*   **Fonte de Dados:** Blockstream API

##  Instalação e Execução

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/seu-usuario/seu-repositorio.git
    cd seu-repositorio
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # No Windows: venv\Scripts\activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure sua chave de API:**
    *   Crie um arquivo chamado `.env` na raiz do projeto.
    *   Adicione sua chave da Groq API ao arquivo:
        ```
        GROQ_API_KEY="sua_chave_aqui"
        ```

5.  **Execute a aplicação:**
    ```bash
    streamlit run main.py
    ```
    A aplicação será aberta automaticamente no seu navegador.

## Estrutura do Projeto

```
.
├── 📄 .env.example          # Exemplo de arquivo de variáveis de ambiente
├── 📄 README.md               # Este arquivo
├── 📄 requirements.txt       # Dependências do projeto
├── 🐍 main.py                 # Ponto de entrada da aplicação
├── 🐍 app_streamlit.py        # Lógica da interface e orquestração do pipeline
├── 🐍 coleta_blockchain.py    # Funções para interagir com a API da blockchain
├── 🐍 analise_heuristica.py   # Implementação de todas as heurísticas e cálculos de score
├── 🐍 gerador_dossie.py       # Responsável por criar o relatório final em JSON e o índice FAISS
├── 🐍 assistente_ia.py        # Configuração do agente LangChain (LLM, RAG, Prompt)
├── 🐍 visualizacao_grafo_interativo.py # Lógica para renderizar o grafo com streamlit-agraph
├── 📝 prompt.txt              # O prompt de sistema que define a persona do detetive de IA
└── 📁 faiss_index/            # Diretório onde o índice vetorial será salvo (criado na execução)
```
