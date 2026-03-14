"""
INTEGRAÇÃO COM GOOGLE GEMINI
Usa: google-generativeai (SDK oficial) ou compatibilidade OpenAI
Modelos recomendados: gemini-2.5-pro, gemini-2.5-flash
Instalação: pip install google-generativeai
"""

import os
from typing import Optional

# ─────────────────────────────────────────────
# OPÇÃO 1: SDK oficial do Google (recomendado)
# ─────────────────────────────────────────────

def gerar_conteudo_gemini(
    prompt: str,
    modelo: str = "gemini-2.5-flash",
    temperatura: float = 0.3,
    max_tokens: int = 8192,
    system_prompt: Optional[str] = None
) -> str:
    """
    Gera conteúdo usando Google Gemini via SDK oficial.
    
    Args:
        prompt: Instrução principal para o modelo
        modelo: "gemini-2.5-pro" (mais poderoso) ou "gemini-2.5-flash" (mais rápido/barato)
        temperatura: 0.0 a 1.0 (menor = mais preciso, maior = mais criativo)
        max_tokens: Limite de tokens na resposta
        system_prompt: Instrução de sistema (personalidade/contexto do agente)
    
    Returns:
        Texto gerado pelo modelo
    """
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não encontrada nas variáveis de ambiente.")

    genai.configure(api_key=api_key)

    # Configuração de geração
    generation_config = genai.GenerationConfig(
        temperature=temperatura,
        max_output_tokens=max_tokens,
    )

    # Configurar system prompt se fornecido
    model = genai.GenerativeModel(
        model_name=modelo,
        generation_config=generation_config,
        system_instruction=system_prompt or (
            "Você é um assistente especializado em criar conteúdo profissional "
            "em português brasileiro. Seja preciso, detalhado e bem estruturado."
        )
    )

    response = model.generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────
# OPÇÃO 2: Via compatibilidade OpenAI (alternativa)
# Útil se já tiver código usando openai client
# ─────────────────────────────────────────────

def gerar_conteudo_gemini_openai_compat(
    prompt: str,
    modelo: str = "gemini-2.5-flash",
    temperatura: float = 0.3,
    system_prompt: Optional[str] = None
) -> str:
    """
    Gera conteúdo usando Gemini via endpoint compatível com OpenAI.
    Útil para migrar código que já usa o cliente OpenAI.
    """
    from openai import OpenAI

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não encontrada nas variáveis de ambiente.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    mensagens = []
    if system_prompt:
        mensagens.append({"role": "system", "content": system_prompt})
    mensagens.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=modelo,
        messages=mensagens,
        temperature=temperatura,
    )

    return response.choices[0].message.content


# ─────────────────────────────────────────────
# FUNÇÕES ESPECÍFICAS PARA O SISTEMA
# ─────────────────────────────────────────────

def gerar_conteudo_para_pdf(topico: str, tipo_documento: str = "relatório") -> str:
    """
    Gera conteúdo em Markdown formatado para ser convertido em PDF.
    """
    prompt = f"""
Crie um {tipo_documento} profissional e completo sobre: "{topico}"

Requisitos:
- Escreva em português brasileiro
- Use formatação Markdown (## para títulos, **negrito**, tabelas, listas)
- Inclua pelo menos: introdução, desenvolvimento com subtópicos, tabela de dados relevantes e conclusão
- Seja detalhado, preciso e profissional
- Mínimo de 500 palavras

Retorne APENAS o conteúdo em Markdown, sem explicações adicionais.
"""
    return gerar_conteudo_gemini(prompt, temperatura=0.3)


def gerar_slides_para_pptx(topico: str, num_slides: int = 6) -> list:
    """
    Gera estrutura de slides em JSON para ser convertida em PPTX.
    """
    import json

    prompt = f"""
Crie uma apresentação profissional sobre: "{topico}"

Gere exatamente {num_slides} slides (excluindo o slide de capa que será criado automaticamente).

Retorne APENAS um JSON válido com esta estrutura exata:
[
  {{
    "titulo": "Título do Slide",
    "conteudo": "Texto do slide ou lista de itens",
    "tipo": "texto"
  }},
  {{
    "titulo": "Título do Slide com Lista",
    "conteudo": ["Item 1", "Item 2", "Item 3", "Item 4"],
    "tipo": "lista"
  }}
]

Use "tipo": "lista" quando o conteúdo for uma lista de tópicos.
Use "tipo": "texto" quando for um parágrafo explicativo.
Escreva em português brasileiro.
"""
    resposta = gerar_conteudo_gemini(prompt, temperatura=0.4)

    # Limpar e parsear JSON
    resposta_limpa = resposta.strip()
    if resposta_limpa.startswith("```"):
        resposta_limpa = resposta_limpa.split("```")[1]
        if resposta_limpa.startswith("json"):
            resposta_limpa = resposta_limpa[4:]

    try:
        slides = json.loads(resposta_limpa.strip())
        return slides
    except json.JSONDecodeError:
        # Fallback com slide genérico
        return [{"titulo": topico, "conteudo": resposta_limpa[:500], "tipo": "texto"}]


def gerar_dados_para_excel(topico: str) -> dict:
    """
    Gera dados tabulares para planilha Excel.
    Retorna dict com cabecalhos e dados.
    """
    import json

    prompt = f"""
Crie dados tabulares profissionais sobre: "{topico}"

Retorne APENAS um JSON válido com esta estrutura:
{{
  "titulo": "Título da Planilha",
  "cabecalhos": ["Coluna 1", "Coluna 2", "Coluna 3"],
  "dados": [
    ["valor1", "valor2", 100],
    ["valor3", "valor4", 200]
  ]
}}

- Inclua pelo menos 8 linhas de dados realistas
- Use números reais (int ou float) para colunas numéricas
- Escreva em português brasileiro
"""
    resposta = gerar_conteudo_gemini(prompt, temperatura=0.3)

    resposta_limpa = resposta.strip()
    if resposta_limpa.startswith("```"):
        resposta_limpa = resposta_limpa.split("```")[1]
        if resposta_limpa.startswith("json"):
            resposta_limpa = resposta_limpa[4:]

    try:
        return json.loads(resposta_limpa.strip())
    except json.JSONDecodeError:
        return {
            "titulo": topico,
            "cabecalhos": ["Item", "Descrição", "Valor"],
            "dados": [["Exemplo", "Dado gerado", 0]]
        }


# ─────────────────────────────────────────────
# EXEMPLO DE USO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Teste básico
    resultado = gerar_conteudo_gemini(
        prompt="Explique em 3 parágrafos o que são squads de agentes de IA em 2026.",
        modelo="gemini-2.5-flash",
        temperatura=0.3
    )
    print(resultado)
