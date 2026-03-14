# Sistema de Templates com Imagens Contextuais por IA

## Como funciona o fluxo completo

```
Cliente pede documento sobre "Relatório Financeiro Q1 2026"
         ↓
Gemini recebe o tema + categoria e cria um prompt de imagem otimizado
         ↓
DALL-E 3 gera a imagem com base no prompt
         ↓
Imagem é salva localmente em outputs/imagens/
         ↓
Imagem é inserida automaticamente no PPTX ou DOCX
         ↓
Arquivo final entregue com design + imagem contextual
```

---

## Arquivos do sistema

| Arquivo | Função |
|---------|--------|
| `gerar_imagem_contextual.py` | Módulo principal: Gemini cria prompt → DALL-E gera imagem |
| `criar_templates_pptx_com_imagens.py` | Gera PPTX com imagens contextuais |
| `criar_templates_docx_com_imagens.py` | Gera DOCX com imagens contextuais |
| `criar_templates_pptx.py` | Gera templates PPTX base (sem imagens) |
| `criar_templates_docx.py` | Gera templates DOCX base (sem imagens) |
| `usar_templates.py` | Exemplos de como carregar templates existentes |

---

## Variáveis de ambiente necessárias

```env
GEMINI_API_KEY=sua_chave_gemini   # Para gerar os prompts de imagem
OPENAI_API_KEY=sua_chave_openai   # Para gerar as imagens com DALL-E 3
```

> **Dica:** Se não quiser usar DALL-E 3, você pode substituir a função `gerar_imagem_dalle` por Stable Diffusion (via Replicate) ou qualquer outra API de geração de imagens.

---

## Categorias disponíveis

| Categoria | Paleta de Cores | Estilo Visual |
|-----------|----------------|---------------|
| `financeiro` | Azul marinho + Dourado | Profissional, sóbrio |
| `marketing` | Roxo + Rosa neon | Vibrante, criativo |
| `apresentacao` | Branco + Azul moderno | Limpo, minimalista |
| `escola` | Verde + Laranja | Amigável, colorido |
| `ideias` | Âmbar + Roxo | Criativo, inspirador |
| `corporativo` | Azul + Vermelho | Formal, institucional |
| `saude` | Verde médico + Azul | Limpo, confiável |
| `tech` | Preto + Ciano neon | Futurista, tecnológico |

---

## Como usar no seu projeto

### Gerar PPTX com imagens contextuais

```python
from criar_templates_pptx_com_imagens import gerar_pptx_com_imagens

slides = [
    {
        "titulo": "Visão Geral do Mercado",
        "conteudo": "O mercado cresceu 35% em 2025...",
        "tipo": "texto",
        "imagem": True   # ← Gemini + DALL-E geram imagem para este slide
    },
    {
        "titulo": "Principais Resultados",
        "conteudo": ["Receita +42%", "Clientes +28%", "NPS: 87"],
        "tipo": "lista",
        "imagem": False
    },
]

gerar_pptx_com_imagens(
    titulo="Resultados Q1 2026",
    subtitulo="Análise Completa",
    slides_conteudo=slides,
    categoria="financeiro",   # Define paleta e estilo visual
    gerar_imagens=True
)
```

### Gerar DOCX com imagens contextuais

```python
from criar_templates_docx_com_imagens import gerar_docx_com_imagens

secoes = [
    {
        "titulo": "Introdução",
        "conteudo": "Este relatório apresenta...",
        "tipo": "texto",
        "imagem": True   # ← Gera imagem contextual para esta seção
    },
    {
        "titulo": "Dados",
        "tipo": "tabela",
        "imagem": False,
        "dados": [
            ["Item", "Valor"],
            ["Produto A", "R$ 1.200"],
        ]
    },
]

gerar_docx_com_imagens(
    titulo="Relatório Financeiro",
    secoes=secoes,
    categoria="financeiro",
    autor="Gean",
    gerar_imagens=True,
    imagem_capa=True   # ← Banner de imagem no topo do documento
)
```

---

## Dica de economia de créditos

Para economizar créditos do DALL-E, use:
- `qualidade="standard"` para imagens de seções (menos importantes)
- `qualidade="hd"` apenas para a imagem de capa
- `gerar_imagens=False` para gerar sem imagens quando não for necessário
- Defina `"imagem": False` nos slides/seções que não precisam de imagem

---

## Instalação

```bash
pip install python-pptx python-docx google-generativeai openai requests
```
