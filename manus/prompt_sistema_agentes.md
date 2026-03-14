# Prompt para Criação de um Sistema de Agentes de IA Multimodal e Orquestrado

## 1. Visão Geral do Projeto

O objetivo deste projeto é desenvolver um sistema de agentes de IA robusto e escalável, capaz de replicar e aprimorar as capacidades de plataformas avançadas como Manus. O sistema deverá ser capaz de realizar pesquisas aprofundadas, gerar documentos profissionais em diversos formatos (PDF, Excel, PPTX), criar imagens com IA, e orquestrar múltiplos Modelos de Linguagem Grandes (LLMs) e ferramentas externas para entregar resultados de alta qualidade. A arquitetura deve ser modular, permitindo fácil expansão e manutenção.

## 2. Arquitetura do Sistema

A arquitetura proposta é baseada em um modelo de orquestração de agentes, onde um agente principal coordena o trabalho de agentes especializados. Utilizaremos um grafo de execução para definir fluxos de trabalho complexos e permitir a interação humana quando necessário.

### 2.1. Componentes Principais

*   **Orquestrador Central:** Responsável por receber as requisições do usuário, decompor tarefas, atribuir agentes, gerenciar o estado do fluxo de trabalho e consolidar os resultados.
*   **Agentes Especializados:** Agentes autônomos focados em tarefas específicas, como pesquisa, análise de dados, geração de texto, geração de imagens, e formatação de documentos.
*   **Gerenciamento de Estado e Memória:** Um mecanismo para persistir o estado do fluxo de trabalho e permitir que os agentes mantenham contexto ao longo das interações.
*   **Interface do Usuário (UI):** Uma interface intuitiva para o usuário interagir com o sistema, submeter requisições e visualizar os resultados.
*   **Módulos de Ferramentas:** Integrações com APIs e bibliotecas externas para funcionalidades específicas.

### 2.2. Fluxo de Trabalho (Exemplo)

1.  **Requisição do Usuário:** O usuário solicita a criação de um relatório de mercado sobre um tópico específico, incluindo gráficos e imagens.
2.  **Decomposição da Tarefa:** O Orquestrador Central divide a requisição em sub-tarefas: pesquisa de dados, análise de dados, geração de texto do relatório, criação de gráficos, geração de imagens e formatação do relatório em PDF e PPTX.
3.  **Atribuição de Agentes:**
    *   Agente de Pesquisa: Coleta informações relevantes usando ferramentas de busca na web.
    *   Agente de Análise de Dados: Processa os dados coletados e gera insights, incluindo dados para gráficos.
    *   Agente de Geração de Texto: Escreve o conteúdo textual do relatório.
    *   Agente de Geração de Imagens: Cria imagens relevantes para o relatório.
    *   Agente de Formatação: Compila o texto, gráficos e imagens em documentos PDF e PPTX.
4.  **Execução e Orquestração:** O Orquestrador Central gerencia a execução sequencial e paralela dos agentes, passando os resultados de um agente para o próximo.
5.  **Revisão e Entrega:** O relatório final é apresentado ao usuário através da UI.

## 3. Tecnologias Recomendadas (Melhores Práticas 2026)

### 3.1. Frameworks de Agentes e Orquestração

*   **LangGraph:** Essencial para a orquestração central. Sua capacidade de modelar fluxos de trabalho como grafos direcionados com estado tipado, checkpointing e suporte a interação humana no loop é crucial para sistemas complexos e resilientes. Permite a atribuição de diferentes LLMs a diferentes nós do grafo [1].
*   **CrewAI:** Ideal para a criação de agentes especializados. Sua abordagem baseada em papéis (role-based) e alta experiência do desenvolvedor (DX) facilita a prototipagem e a implementação de agentes com tarefas bem definidas [1]. Pode ser integrado como nós dentro de um grafo LangGraph.
*   **AutoGen (Microsoft):** Uma alternativa ou complemento para cenários que exigem conversas multi-agente mais complexas e flexíveis [1].

### 3.2. Modelos de Linguagem Grandes (LLMs)

O sistema deve ser agnóstico em relação ao modelo, permitindo a integração de múltiplos LLMs para aproveitar seus pontos fortes específicos. A orquestração multi-LLM é uma prática fundamental em 2026 [2].

*   **GPT-5 / GPT-4.5 (OpenAI):** Para raciocínio avançado, compreensão de linguagem natural e integração com ferramentas [2].
*   **Claude 4.5 Opus (Anthropic):** Destaca-se em codificação, seguimento de instruções complexas e janelas de contexto longas [2].
*   **Gemini 3.1 Pro (Google):** Oferece janelas de contexto massivas e capacidades multimodais nativas, ideal para processamento de dados diversos [2].

### 3.3. Ferramentas de Busca na Web e Extração de Dados

*   **Tavily API:** Otimizada para agentes de IA, fornece resultados de busca limpos e relevantes para LLMs, minimizando ruído [3].
*   **Exa API:** Para busca semântica avançada, utilizando embeddings para encontrar informações mais contextuais [3].
*   **Firecrawl API:** Para extração profunda de conteúdo de websites, convertendo páginas web em Markdown estruturado, o que é ideal para alimentar LLMs [3].

### 3.4. Geração de Imagens com IA

O sistema deve integrar APIs de geração de imagens para criar visuais relevantes para os documentos.

*   **DALL-E 3 (OpenAI):** Excelente para precisão de texto em imagens e designs comerciais [4].
*   **Midjourney API (via Discord bot ou API não oficial):** Para imagens com alta qualidade artística e visuais de marketing [4]. (Nota: A integração via API oficial pode ser um desafio em 2026, exigindo soluções alternativas).
*   **Stable Diffusion 3 / Flux:** Para cenários que exigem maior controle e personalização na geração de imagens [4].

### 3.5. Geração e Formatação de Documentos

*   **python-pptx:** Biblioteca Python para criar e modificar arquivos PowerPoint (.pptx), permitindo a geração programática de slides [5].
*   **openpyxl:** Biblioteca Python para ler e escrever arquivos Excel (.xlsx), essencial para planilhas formatadas [5].
*   **markdown-to-pdf (ou similar):** Ferramentas ou bibliotecas Python para converter conteúdo Markdown em documentos PDF profissionais, mantendo a formatação e estrutura [5]. `manus-md-to-pdf` é um exemplo de ferramenta robusta.
*   **MarkItDown (Microsoft):** Para conversão de diversos formatos de documentos (PDF, DOCX, XLSX, PPTX) para Markdown estruturado, facilitando o processamento por LLMs [5].

### 3.6. Interface do Usuário (UI)

*   **Streamlit / Gradio:** Para prototipagem rápida e interfaces interativas simples para demonstração e interação inicial.
*   **Next.js / React:** Para uma interface de usuário mais robusta e escalável, com suporte a streaming de tokens e uma experiência de usuário rica.

## 4. Integração e Orquestração de LLMs

O sistema deve implementar uma estratégia de orquestração multi-LLM, onde diferentes modelos são utilizados para diferentes tipos de tarefas ou para validação cruzada. Isso pode ser gerenciado pelo LangGraph, atribuindo LLMs específicos a nós ou agentes.

*   **Seleção Dinâmica de LLM:** O Orquestrador deve ser capaz de selecionar o LLM mais adequado para uma sub-tarefa com base em critérios como custo, desempenho, capacidade de contexto e especialização (ex: Claude para codificação, Gemini para multimodalidade).
*   **Cadeias de LLMs:** Possibilidade de encadear múltiplos LLMs para refinar respostas ou realizar tarefas complexas em etapas.
*   **Gerenciamento de Tokens e Custos:** Implementar mecanismos para monitorar e otimizar o uso de tokens e os custos associados aos diferentes LLMs.

## 5. Considerações de Desenvolvimento

*   **Modularidade:** O código deve ser altamente modular, com cada agente e ferramenta encapsulados, facilitando a substituição ou adição de novos componentes.
*   **Observabilidade:** Integrar ferramentas de observabilidade (ex: LangSmith para LangGraph) para monitorar o desempenho dos agentes, depurar fluxos de trabalho e identificar gargalos.
*   **Persistência:** Utilizar um banco de dados (ex: PostgreSQL, SQLite) para persistir o estado do grafo, a memória dos agentes e os resultados das tarefas.
*   **Segurança:** Implementar práticas de segurança robustas, especialmente ao lidar com APIs externas e dados sensíveis.
*   **Escalabilidade:** Projetar o sistema para ser escalável, capaz de lidar com um aumento no número de requisições e agentes.

## 6. Requisitos de Implementação

O criador de código com IA deve:

*   Gerar o código-fonte completo para a arquitetura descrita, incluindo a configuração dos frameworks (LangGraph, CrewAI).
*   Fornecer exemplos de implementação para cada tipo de agente (pesquisa, análise, geração de texto, imagem, formatação).
*   Incluir a integração com as APIs de busca (Tavily, Exa, Firecrawl).
*   Demonstrar a integração com as APIs de geração de imagens (DALL-E 3, Stable Diffusion).
*   Implementar a geração de documentos usando `python-pptx`, `openpyxl` e uma biblioteca de Markdown para PDF.
*   Desenvolver uma interface de usuário básica (Streamlit ou Next.js) para demonstrar as funcionalidades.
*   Fornecer instruções claras para configuração do ambiente e execução do sistema.

## 7. Referências

[1] Best Multi-Agent Frameworks in 2026 - Gurusup. (n.d.). Retrieved from https://gurusup.com/blog/best-multi-agent-frameworks-2026
[2] The Best LLM in 2026: Gemini 3 vs. Claude 4.5 vs. GPT 5.1... - Teneo AI. (n.d.). Retrieved from https://www.teneo.ai/blog/the-best-llm-in-2026-gemini-3-vs-claude-4-5-vs-gpt-5-1
[3] Best Web Search APIs for AI Applications in 2026 - Firecrawl. (n.d.). Retrieved from https://www.firecrawl.dev/blog/best-web-search-apis
[4] Midjourney vs DALL-E vs Stable Diffusion for creative agencies in 2026 - Luniq. (n.d.). Retrieved from https://www.luniq.io/en/resources/blog/midjourney-vs-dall-e-vs-stable-diffusion-for-creative-agencies-in-2026
[5] Document Processor automates extraction, summarization, and conversion of common office formats (PDF, DOCX, XLSX, PPTX). - LobeHub. (n.d.). Retrieved from https://lobehub.com/skills/jiunbae-agent-skills-document-processor
