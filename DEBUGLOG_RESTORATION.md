# Relatório Técnico de Depuração e Restauração - Arth Executive
**Data:** 07 de março de 2026
**Responsável:** Antigravity AI
**Objetivo:** Documentar falhas críticas e correções para revisão do AIOS.

---

## 1. Falha Crítica: Bypass de Segurança (HITL)
### Problema
O sistema de aprovação humana (Human-In-The-Loop) estava sendo ignorado.
### Causa Raiz
O `supervisor_node` verificava apenas a última mensagem do histórico. Quando um agente intermediário (ex: `@arth-planner`) respondia antes do executor, o gatilho "imagem" saía do topo da pilha e o sistema entendia que a ação não era mais crítica, pulando a aprovação.
### Correção Aplicada
- Implementação de **Busca Resiliente**: O supervisor agora escaneia todo o histórico de mensagens da thread em busca de palavras-chave críticas.
- **Força Bruta de Roteamento**: Se um gatilho é detectado e não há aprovação, o estado `requires_approval` é injetado manualmente, anulando a decisão do LLM de seguir direto.

---

## 2. Perda de Mídias e Hallucinação de Markdown
### Problema
Imagens e documentos gerados não chegavam ao usuário ou apareciam como links quebrados.
### Causa Raiz
1. **Orquestrador Senil**: O `@arth-orchestrator` tentava resumir a resposta final, removendo as tags `<SEND_FILE:...>` geradas pelo executor.
2. **Hallucinação**: Agentes tentavam criar links `[Baixar]` ou `!Imagem` em markdown, que não funcionam no backend real.
### Correção Aplicada
- **Preservação de Tags**: O handler de mensagens agora coleta todas as tags de mídias de todas as mensagens dos especialistas e as anexa obrigatoriamente na resposta final.
- **Limpeza de Alucinação**: Adicionado filtro Regex agressivo que apaga qualquer tentativa de link markdown gerado pela IA antes de enviar ao usuário.

---

## 3. Loop Infinito (Recursion Limit 50)
### Problema
O sistema travava em loop infinito após o usuário dizer "Sim".
### Causa Raiz
O status `approval_status = "approved"` persistia no estado da conversa. O orquestrador lia que estava aprovado, enviava ao executor, que retornava ao orquestrador, que via o histórico com "imagem" e entrava em dúvida novamente, ou o orquestrador re-injetava a instrução de aprovação infinitamente.
### Correção Aplicada
- **Bypass Absoluto**: Se `is_approved` for verdadeiro, o sistema agora desativa todas as checagens de segurança para aquela rodada e força o roteamento para o executor.
- **Reset de State**: Flags de segurança `requires_approval` são forçadas para `False` em todos os retornos de nós para garantir que o estado limpo seja a norma.

---

## 4. Desalinhamento de Repositórios (O "Fantasma")
### Problema
Pushs realizados não alteravam o comportamento no Railway.
### Causa Raiz
O projeto possui um repositório Git (Raiz `GeanAIOS`) e um repositório filho (`arth-executive`). O Railway estava apontando para o repositório filho, mas as correções estavam sendo commitadas no pai.
### Correção Aplicada
Sincronização manual via terminal diretamente na pasta `arth-executive`, garantindo que o commit `01c2cb6` e posteriores chegassem ao servidor correto.

---

## 5. Melhorias de Adaptador (Telegram)
### Problema
Telegram enviava mídias como documentos genéricos, sem visualização prévia.
### Correção Aplicada
Implementado método `send_telegram_photo` usando a API oficial do Telegram para abrir imagens diretamente no chat.

---
---
**Status Final:** Sistema estabilizado, segurança resiliente e mídias restauradas. Pronto para revisão de AIOS.

## 6. Blindagem de Skills Homologadas (08 de Março de 2026)
### Funcionalidades Blindadas
- **Geração de Imagens**: Estabilizada com `gemini-3.1-flash-image-preview`. Estética executiva 8k. **NÃO ALTERAR**.
- **Documentos (DOCX/PDF)**: Padronização de nomes com hífens (`hex-nome.ext`) e conversão Markdown-to-RichText. **NOMEAÇÃO BLINDADA**.
- **Apresentações (PPTX)**: Design Premium Manus AI (Dark Navy/Electric Blue). Imagens embutidas automaticamente com orientação horizontal. **NÃO ALTERAR DESIGN**.
- **Mensagem de Apresentação (Manus AI Style)**: Fluxo de preservação de tags no handler e orquestrador garantido. O Executor deve sempre introduzir o arquivo com tom de consultoria premium.
- **Resiliência de Tags**: O `agent_node` no `graph.py` agora suporta variações de hífens/sublinhados e remove imagens redundantes se um PPTX estiver presente.

**Nota:** Qualquer tentativa de reverter para sublinhados (_) ou remover a lógica de verificação resiliente deve ser bloqueada.
