"""
GERADOR DE PDF DE ALTA QUALIDADE
Usa: Playwright (browser headless) + Tailwind CSS + Jinja2
Resultado: PDF com qualidade visual de design profissional
"""

import asyncio
import os
import uuid
import markdown2
from jinja2 import Template
from playwright.async_api import async_playwright

# ── Temas de cores ──
TEMAS = {
    "azul": {
        "primaria": "#1e3a8a",
        "secundaria": "#3b82f6",
        "acento": "#dbeafe",
        "texto": "#1e293b",
    },
    "verde": {
        "primaria": "#14532d",
        "secundaria": "#22c55e",
        "acento": "#dcfce7",
        "texto": "#1e293b",
    },
    "roxo": {
        "primaria": "#4c1d95",
        "secundaria": "#8b5cf6",
        "acento": "#ede9fe",
        "texto": "#1e293b",
    },
    "escuro": {
        "primaria": "#0f172a",
        "secundaria": "#475569",
        "acento": "#1e293b",
        "texto": "#f8fafc",
    },
}

# ── Template HTML com Tailwind CSS ──
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    * { font-family: 'Inter', sans-serif; }
    body { background: white; color: {{ tema.texto }}; }
    
    /* Cabeçalho do documento */
    .doc-header {
      background: linear-gradient(135deg, {{ tema.primaria }}, {{ tema.secundaria }});
      color: white;
      padding: 40px 50px;
      margin-bottom: 40px;
    }
    
    /* Títulos H1 */
    h1 { 
      color: {{ tema.primaria }}; 
      font-size: 1.875rem; 
      font-weight: 800; 
      margin: 2rem 0 1rem;
      border-bottom: 3px solid {{ tema.secundaria }};
      padding-bottom: 0.5rem;
    }
    
    /* Títulos H2 */
    h2 { 
      color: {{ tema.secundaria }}; 
      font-size: 1.375rem; 
      font-weight: 700; 
      margin: 1.5rem 0 0.75rem;
    }
    
    /* Títulos H3 */
    h3 { 
      color: {{ tema.texto }}; 
      font-size: 1.125rem; 
      font-weight: 600; 
      margin: 1.25rem 0 0.5rem;
    }
    
    /* Parágrafos */
    p { 
      line-height: 1.8; 
      margin: 0.75rem 0; 
      text-align: justify;
    }
    
    /* Tabelas */
    table { 
      width: 100%; 
      border-collapse: collapse; 
      margin: 1.5rem 0;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    th { 
      background: {{ tema.primaria }}; 
      color: white; 
      padding: 12px 16px; 
      text-align: left;
      font-weight: 600;
    }
    td { 
      padding: 10px 16px; 
      border-bottom: 1px solid #e2e8f0;
    }
    tr:nth-child(even) td { background: {{ tema.acento }}; }
    tr:hover td { background: #f1f5f9; }
    
    /* Listas */
    ul, ol { 
      padding-left: 1.5rem; 
      margin: 0.75rem 0;
    }
    li { 
      margin: 0.4rem 0; 
      line-height: 1.7;
    }
    ul li::marker { color: {{ tema.secundaria }}; }
    
    /* Código */
    code { 
      background: #f1f5f9; 
      padding: 2px 6px; 
      border-radius: 4px; 
      font-family: monospace;
      font-size: 0.875rem;
      color: {{ tema.primaria }};
    }
    pre { 
      background: #0f172a; 
      color: #e2e8f0; 
      padding: 20px; 
      border-radius: 8px; 
      overflow-x: auto;
      margin: 1rem 0;
    }
    pre code { background: none; color: inherit; padding: 0; }
    
    /* Blockquote */
    blockquote {
      border-left: 4px solid {{ tema.secundaria }};
      background: {{ tema.acento }};
      padding: 16px 20px;
      margin: 1rem 0;
      border-radius: 0 8px 8px 0;
      font-style: italic;
    }
    
    /* Conteúdo principal */
    .content { padding: 0 50px 50px; }
    
    /* Rodapé */
    .footer {
      margin-top: 40px;
      padding: 20px 50px;
      border-top: 2px solid {{ tema.acento }};
      color: #94a3b8;
      font-size: 0.8rem;
      display: flex;
      justify-content: space-between;
    }
    
    /* Quebra de página */
    .page-break { page-break-after: always; }
    
    @media print {
      .doc-header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      th { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    }
  </style>
</head>
<body>
  <!-- Cabeçalho -->
  <div class="doc-header">
    <h1 style="color:white; border:none; margin:0; font-size:2rem;">{{ titulo }}</h1>
    <p style="color:rgba(255,255,255,0.8); margin:8px 0 0; font-size:0.9rem;">
      Gerado automaticamente | {{ data }}
    </p>
  </div>
  
  <!-- Conteúdo -->
  <div class="content">
    {{ conteudo_html }}
  </div>
  
  <!-- Rodapé -->
  <div class="footer">
    <span>{{ titulo }}</span>
    <span>Gerado por Sistema IA</span>
  </div>
</body>
</html>
"""

async def gerar_pdf_html(titulo: str, conteudo_markdown: str, tema_nome: str = "azul") -> str:
    """
    Gera PDF de alta qualidade a partir de Markdown.
    Usa Playwright para renderizar HTML com Tailwind CSS.
    """
    tema = TEMAS.get(tema_nome, TEMAS["azul"])
    
    # Converter Markdown para HTML
    conteudo_html = markdown2.markdown(
        conteudo_markdown,
        extras=["tables", "fenced-code-blocks", "strike", "task_list"]
    )
    
    # Renderizar template HTML
    from datetime import datetime
    template = Template(HTML_TEMPLATE)
    html_final = template.render(
        titulo=titulo,
        conteudo_html=conteudo_html,
        tema=tema,
        data=datetime.now().strftime("%d/%m/%Y às %H:%M")
    )
    
    # Salvar HTML temporário
    os.makedirs("outputs", exist_ok=True)
    uid = str(uuid.uuid4())[:8]
    html_path = f"outputs/temp_{uid}.html"
    pdf_path = f"outputs/{titulo.replace(' ', '_')}_{uid}.pdf"
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_final)
    
    # Gerar PDF com Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"file://{os.path.abspath(html_path)}")
        await page.wait_for_load_state("networkidle")  # Aguarda Tailwind carregar
        
        await page.pdf(
            path=pdf_path,
            format="A4",
            margin={"top": "0", "right": "0", "bottom": "20mm", "left": "0"},
            print_background=True,
        )
        await browser.close()
    
    os.remove(html_path)  # Limpar temporário
    print(f"✅ PDF gerado: {pdf_path}")
    return pdf_path


# Uso direto (sem FastAPI)
if __name__ == "__main__":
    conteudo = """
## Introdução

Este é um **relatório de exemplo** gerado automaticamente com Python, Playwright e Tailwind CSS.

## Tabela de Dados

| Produto | Quantidade | Valor |
|---------|-----------|-------|
| Produto A | 100 | R$ 1.500,00 |
| Produto B | 50 | R$ 750,00 |
| Produto C | 200 | R$ 3.000,00 |

## Conclusão

O sistema funciona com alta qualidade visual, renderizando CSS moderno diretamente no PDF.
    """
    asyncio.run(gerar_pdf_html("Relatório de Teste", conteudo, "azul"))
