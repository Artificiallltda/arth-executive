# Guia Técnico Passo a Passo: Construindo um Sistema de Agentes de IA Multimodal e Orquestrado

## 1. Introdução

Este guia detalha a construção de um sistema de agentes de IA avançado, capaz de realizar pesquisas, gerar documentos profissionais (PDF, Excel, PPTX) e imagens com IA, orquestrando múltiplos Modelos de Linguagem Grandes (LLMs) e ferramentas externas. O objetivo é fornecer um roteiro claro para instalar, configurar, executar e expandir um sistema similar às capacidades de plataformas como Manus.

## 2. Pré-requisitos

Para seguir este guia, você precisará dos seguintes conhecimentos e ferramentas:

*   **Conhecimento em Python:** Familiaridade com programação Python, incluindo gerenciamento de pacotes (pip) e ambientes virtuais.
*   **Conhecimento Básico de IA/ML:** Entendimento fundamental de LLMs e conceitos de agentes de IA.
*   **Git:** Para clonar repositórios e gerenciar código-fonte.
*   **Docker (Opcional, mas Recomendado):** Para isolamento de ambiente e implantação facilitada.
*   **Chaves de API:** Acesso a APIs de LLMs (OpenAI, Anthropic, Google), busca na web (Tavily, Exa, Firecrawl) e geração de imagens (DALL-E, Stable Diffusion).

## 3. Configuração do Ambiente de Desenvolvimento

Recomenda-se configurar um ambiente virtual Python para gerenciar as dependências do projeto.

```bash
# Crie um diretório para o projeto
mkdir ai_agent_system
cd ai_agent_system

# Crie e ative um ambiente virtual
python3 -m venv venv
source venv/bin/activate

# (Opcional) Instale o Git se ainda não tiver
sudo apt update
sudo apt install git -y
```

## 4. Instalação das Dependências

Instale as bibliotecas Python necessárias para os frameworks de agentes, integração de LLMs, ferramentas de busca e geração de documentos e imagens.

```bash
pip install langchain_core langchain_community langgraph crewai 'crewai[tools]' openai anthropic google-generativeai python-pptx openpyxl markdown-it-py beautifulsoup4 requests python-dotenv
```

**Observações:**

*   `langchain_core` e `langchain_community` são componentes do ecossistema LangChain, que o LangGraph utiliza.
*   `crewai[tools]` instala o CrewAI com suas ferramentas padrão.
*   `openai`, `anthropic`, `google-generativeai` são os SDKs para os respectivos LLMs.
*   `python-pptx` e `openpyxl` são para manipulação de arquivos PowerPoint e Excel.
*   `markdown-it-py` e `beautifulsoup4` podem ser úteis para processamento de Markdown e HTML (para Firecrawl).
*   `requests` para chamadas HTTP a APIs.
*   `python-dotenv` para gerenciar variáveis de ambiente.

## 5. Estrutura do Projeto

Uma estrutura de projeto modular é crucial para a manutenibilidade e escalabilidade. Sugere-se a seguinte organização:

```
ai_agent_system/
├── venv/
├── .env
├── main.py
├── agents/
│   ├── __init__.py
│   ├── research_agent.py
│   ├── data_analysis_agent.py
│   ├── text_generation_agent.py
│   ├── image_generation_agent.py
│   └── document_formatting_agent.py
├── tools/
│   ├── __init__.py
│   ├── web_search_tool.py
│   ├── image_gen_tool.py
│   └── document_gen_tool.py
├── workflows/
│   ├── __init__.py
│   └── report_workflow.py
├── utils/
│   ├── __init__.py
│   └── llm_config.py
└── README.md
```

## 6. Configuração das APIs e Credenciais

Crie um arquivo `.env` na raiz do projeto para armazenar suas chaves de API e outras credenciais sensíveis. **Nunca exponha essas chaves diretamente no código-fonte.**

Exemplo de `.env`:

```dotenv
OPENAI_API_KEY="sua_chave_openai"
ANTHROPIC_API_KEY="sua_chave_anthropic"
GOOGLE_API_KEY="sua_chave_google"
TAVILY_API_KEY="sua_chave_tavily"
EXA_API_KEY="sua_chave_exa"
FIRECRAWL_API_KEY="sua_chave_firecrawl"
# Outras chaves de API, como Stable Diffusion, se aplicável
```

Carregue essas variáveis no seu código Python usando `python-dotenv`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
# ... e assim por diante para as outras chaves
```

## 7. Implementação dos Componentes Principais

### 7.1. Configuração dos LLMs (`utils/llm_config.py`)

Crie um módulo para configurar e instanciar os diferentes LLMs, permitindo a seleção dinâmica.

```python
# Exemplo simplificado
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
import os

def get_llm(model_name: str):
    if "gpt" in model_name:
        return ChatOpenAI(model=model_name, api_key=os.getenv("OPENAI_API_KEY"))
    elif "claude" in model_name:
        return ChatAnthropic(model=model_name, api_key=os.getenv("ANTHROPIC_API_KEY"))
    elif "gemini" in model_name:
        return ChatGoogleGenerativeAI(model=model_name, api_key=os.getenv("GOOGLE_API_KEY"))
    else:
        raise ValueError(f"Modelo LLM '{model_name}' não suportado.")
```

### 7.2. Ferramentas (`tools/`)

Implemente as ferramentas que seus agentes utilizarão. Por exemplo, uma ferramenta de busca na web usando Tavily:

```python
# tools/web_search_tool.py
import os
import requests

class TavilySearchTool:
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com/search"

    def search(self, query: str, max_results: int = 5) -> str:
        headers = {"Content-Type": "application/json"}
        data = {"api_key": self.api_key, "query": query, "num_results": max_results}
        response = requests.post(self.base_url, headers=headers, json=data)
        response.raise_for_status()
        results = response.json().get("results", [])
        return "\n".join([f"Título: {r['title']}\nURL: {r['url']}\nConteúdo: {r['content']}\n" for r in results])

# Exemplo de ferramenta de geração de imagens (DALL-E 3)
# tools/image_gen_tool.py
from openai import OpenAI

class Dalle3ImageGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_image(self, prompt: str, size: str = "1024x1024") -> str:
        response = self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality="standard",
            n=1,
        )
        return response.data[0].url
```

### 7.3. Agentes (`agents/`)

Defina os agentes especializados usando CrewAI. Cada agente terá um papel, objetivo e ferramentas específicas.

```python
# agents/research_agent.py
from crewai import Agent
from tools.web_search_tool import TavilySearchTool
from utils.llm_config import get_llm

class ResearchAgent:
    def __init__(self):
        self.llm = get_llm("gpt-4.5") # Exemplo: usar GPT-4.5 para pesquisa
        self.search_tool = TavilySearchTool()

    def create_researcher(self):
        return Agent(
            role='Pesquisador Sênior',
            goal='Conduzir pesquisas aprofundadas e coletar informações relevantes sobre o tópico fornecido.',
            backstory='Especialista em busca de informações, capaz de sintetizar dados de múltiplas fontes.',
            tools=[self.search_tool.search],
            llm=self.llm,
            verbose=True
        )

# agents/document_formatting_agent.py
from crewai import Agent
from utils.llm_config import get_llm
# Importar ferramentas de geração de documentos aqui (ex: para PPTX, Excel, PDF)

class DocumentFormattingAgent:
    def __init__(self):
        self.llm = get_llm("claude-4.5-opus") # Exemplo: usar Claude para formatação

    def create_formatter(self):
        return Agent(
            role='Formatador de Documentos',
            goal='Compilar e formatar informações em documentos profissionais (PDF, PPTX, XLSX).',
            backstory='Mestre na criação de layouts limpos e apresentações impactantes.',
            # tools=[ferramenta_pptx, ferramenta_excel, ferramenta_pdf],
            llm=self.llm,
            verbose=True
        )
```

### 7.4. Fluxos de Trabalho (Workflows) com LangGraph (`workflows/`)

Utilize LangGraph para orquestrar os agentes e definir o fluxo de trabalho. Este é o coração do sistema.

```python
# workflows/report_workflow.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List
import operator

# Definir o estado do grafo
class GraphState(TypedDict):
    topic: str
    research_data: str
    analysis_results: str
    report_text: str
    image_url: str
    final_document_paths: List[str]

# Definir os nós (agentes ou funções)
def call_research_agent(state):
    print("---Chamando Agente de Pesquisa---")
    # Instanciar e executar o agente de pesquisa do CrewAI
    # ... (lógica para chamar o agente de pesquisa)
    return {"research_data": "Dados de pesquisa sobre " + state["topic"]}

def call_analysis_agent(state):
    print("---Chamando Agente de Análise---")
    # Instanciar e executar o agente de análise do CrewAI
    # ...
    return {"analysis_results": "Resultados da análise dos dados"}

# ... (outros nós para geração de texto, imagem, formatação)

# Construir o grafo
workflow = StateGraph(GraphState)

workflow.add_node("research", call_research_agent)
workflow.add_node("analysis", call_analysis_agent)
# ... adicione outros nós

workflow.set_entry_point("research")

workflow.add_edge("research", "analysis")
# ... adicione outras arestas

workflow.add_edge("analysis", END) # Exemplo simples, o fluxo real seria mais complexo

app = workflow.compile()
```

## 8. Execução do Sistema (`main.py`)

O arquivo `main.py` será o ponto de entrada para interagir com o sistema.

```python
# main.py
from workflows.report_workflow import app

if __name__ == "__main__":
    initial_state = {
        "topic": "Impacto da IA na educação em 2026",
        "research_data": "",
        "analysis_results": "",
        "report_text": "",
        "image_url": "",
        "final_document_paths": []
    }
    
    # Executar o grafo
    for s in app.stream(initial_state):
        print(s)
        print("----")

    # O estado final conteria os caminhos para os documentos gerados
    # print(app.get_state().values["final_document_paths"])
```

Para executar:

```bash
python main.py
```

## 9. Expansão e Personalização

*   **Novos Agentes:** Crie novos arquivos em `agents/` e `tools/` para adicionar funcionalidades específicas (ex: agente de tradução, agente de resumo de vídeo).
*   **Novos Fluxos de Trabalho:** Defina novos grafos em `workflows/` para diferentes tipos de tarefas (ex: criação de landing page, análise de sentimentos).
*   **Integração de LLMs:** Adicione suporte a novos LLMs em `utils/llm_config.py` e utilize-os em seus agentes.
*   **Interface do Usuário:** Desenvolva uma UI mais completa usando Streamlit, Gradio, ou um framework web como Next.js/React para uma experiência de usuário rica, incluindo streaming de tokens e visualização de progresso.
*   **Persistência:** Integre um banco de dados (ex: PostgreSQL com SQLAlchemy ou Drizzle) para armazenar o histórico de conversas, resultados de tarefas e configurações de agentes.

## 10. Resolução de Problemas Comuns

*   **Chaves de API Ausentes:** Verifique se o arquivo `.env` está configurado corretamente e se as variáveis de ambiente estão sendo carregadas.
*   **Erros de Instalação:** Certifique-se de que o ambiente virtual está ativado e que todas as dependências foram instaladas com `pip install`.
*   **Erros de Conexão com API:** Verifique sua conexão com a internet e se as chaves de API são válidas e têm permissões adequadas.
*   **Comportamento Inesperado do Agente:** Utilize o modo `verbose=True` nos agentes do CrewAI e as ferramentas de observabilidade do LangGraph (como LangSmith) para depurar o fluxo de trabalho e o raciocínio dos agentes.

Este guia fornece a base para construir um sistema de agentes de IA altamente capaz e personalizável. A modularidade e a escolha de frameworks líderes de mercado em 2026 garantem flexibilidade e poder para futuras expansões.
