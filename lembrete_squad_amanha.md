# 🚨 LEMBRETE MÁXIMO PARA A PRÓXIMA SESSÃO (SQUAD SWARM V1) 🚨

**Objetivo:** Iniciar a Fase 6 - Transformação do Arth Executive de um Agente Singular (Orquestrador) para um "Agentic Swarm" de 6 personas integradas.
**Data Planejada:** Amanhã.

## ⚠️ AVISO EM LETRAS GARRAFAIS: ⚠️
**A ARQUITETURA DEVE SER CONSTRUÍDA E HOSPEDADA DIRETAMENTE NO ECOSSISTEMA DO 'AIOS' (GeanAIOS).** O AIOS será o motor de Roteamento, Segurança (Sandbox) e Banco de Dados (Memória/VectorDB) que vai sustentar a comunicação entre os agentes. NÃO pode ser apenas um script solto no LangGraph. Tem que integrar com a fundação do AIOS!

---

## O PROMPT ORIGINAL DO USUÁRIO (O BLUEPRINT):
```markdown
create-squad arth-executive-squad-v1

## IDENTIDADE DO SQUAD
- **Nome:** Arth Executive Squad v1
- **Propósito:** Orquestrar agentes especializados..
- **Orquestrador Principal:** @arth-orchestrator

## AGENTES DO SQUAD
1. @arth-orchestrator (Regente / Roteador)
2. @arth-researcher (Pesquisador / Web Search)
3. @arth-planner (Planejador / Visão de Tarefas)
4. @arth-executor (Executor / Tools pesadas)
5. @arth-qa (Revisor / Qualidade)
6. @arth-analyst (Analista / Insights futuros)

## FLUXO DE TRABALHO PADRÃO
USUÁRIO → @arth-orchestrator
@arth-orchestrator → @arth-researcher
@arth-researcher → Dados
@arth-orchestrator → @arth-planner
@arth-planner → Plano
@arth-orchestrator → @arth-executor
@arth-executor → Artefato
@arth-qa → Revisa (Loop)
@arth-analyst → Analisa
@arth-orchestrator → Entrega Final
```

---

## Passo a Passo Inicial de Código:
1. **Refatoração do `graph.py`:** Substituir o Grafo Linear por um **StateGraph Hierárquico Multi-Agente**.
2. **Separação de Tools:** Mover ferramentas complexas para o `@arth-executor` e ferramentas de web para o `@arth-researcher`.
3. **Plugar no AIOS:** Conectar Roteadores internos e Memory Checkpoints na base de dados do AIOS para não estourar os tokens copiando e colando texto de um agente pro outro.
4. **WhatsApp Webhooks:** Religar tudo ao `message_handler.py`.

*Fim de expediente registradíssimo.*
