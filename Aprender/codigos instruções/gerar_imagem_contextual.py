"""
GERADOR DE IMAGENS CONTEXTUAIS
Fluxo: Gemini cria o prompt → DALL-E 3 gera a imagem → imagem salva localmente
Uso: chamado automaticamente pelos geradores de PPTX e DOCX
"""

import os
import uuid
import requests
import google.generativeai as genai
from openai import OpenAI

# ── Configuração ──
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

os.makedirs("outputs/imagens", exist_ok=True)

# ── Estilos visuais por categoria de template ──
ESTILOS_POR_CATEGORIA = {
    "financeiro":   "professional financial photography, dark navy blue tones, gold accents, charts and graphs, modern office, clean minimalist",
    "marketing":    "vibrant creative marketing, bold colors, dynamic composition, modern advertising aesthetic, energetic and eye-catching",
    "apresentacao": "clean modern business presentation, white and blue tones, professional corporate, minimalist design, elegant",
    "escola":       "bright educational environment, friendly and colorful, books and learning, warm inviting atmosphere, cheerful",
    "ideias":       "creative brainstorming concept, lightbulb and innovation, warm amber tones, artistic and inspiring, creative workspace",
    "corporativo":  "corporate business environment, formal professional, navy blue and red, executive meeting room, authoritative",
    "saude":        "clean medical environment, healthcare professional, green and white tones, calm and trustworthy, modern clinic",
    "tech":         "futuristic technology concept, dark background, neon cyan and purple, circuit boards and AI, cutting-edge digital",
    "geral":        "professional high quality illustration, modern clean design, suitable for business documents",
}

# ── Tamanhos disponíveis no DALL-E 3 ──
TAMANHOS = {
    "quadrado":   "1024x1024",
    "horizontal": "1792x1024",
    "vertical":   "1024x1792",
}


def gerar_prompt_imagem_com_gemini(
    tema: str,
    categoria: str = "geral",
    tipo_imagem: str = "capa de apresentação profissional"
) -> str:
    """
    Usa o Gemini para criar um prompt otimizado para geração de imagem.
    
    Args:
        tema: Tema do documento/apresentação (ex: "Resultados Financeiros Q1 2026")
        categoria: Categoria do template (financeiro, marketing, escola, etc.)
        tipo_imagem: Contexto de uso da imagem
    
    Returns:
        Prompt otimizado em inglês para DALL-E 3
    """
    if not GEMINI_API_KEY:
        # Fallback sem API key — prompt genérico baseado no tema
        estilo = ESTILOS_POR_CATEGORIA.get(categoria, ESTILOS_POR_CATEGORIA["geral"])
        return f"Professional high quality image about '{tema}', {estilo}, 4K resolution, no text, no watermark"

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config=genai.GenerationConfig(temperature=0.6, max_output_tokens=300)
    )

    estilo = ESTILOS_POR_CATEGORIA.get(categoria, ESTILOS_POR_CATEGORIA["geral"])

    prompt_gemini = f"""
Crie um prompt em inglês para gerar uma imagem profissional com DALL-E 3.

Contexto:
- Tema do documento: "{tema}"
- Categoria: {categoria}
- Uso da imagem: {tipo_imagem}
- Estilo visual base: {estilo}

Regras para o prompt:
- Escreva APENAS o prompt em inglês, sem explicações
- Máximo de 150 palavras
- Inclua: descrição visual, estilo, iluminação, composição e qualidade
- NÃO inclua texto, letras ou palavras na imagem
- NÃO inclua marcas d'água
- Termine com: "photorealistic, 4K, high resolution, professional quality, no text, no watermark"
"""

    response = model.generate_content(prompt_gemini)
    prompt_final = response.text.strip()
    print(f"🤖 Prompt gerado pelo Gemini: {prompt_final[:100]}...")
    return prompt_final


def gerar_imagem_dalle(
    prompt: str,
    tamanho: str = "horizontal",
    qualidade: str = "hd"
) -> str:
    """
    Gera imagem com DALL-E 3 e salva localmente.
    
    Args:
        prompt: Prompt descritivo da imagem
        tamanho: "quadrado", "horizontal" ou "vertical"
        qualidade: "standard" ou "hd"
    
    Returns:
        Caminho local da imagem salva
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY não encontrada. Configure no arquivo .env")

    client = OpenAI(api_key=OPENAI_API_KEY)
    size = TAMANHOS.get(tamanho, TAMANHOS["horizontal"])

    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,
        quality=qualidade,
        n=1,
    )

    url_imagem = response.data[0].url
    uid = str(uuid.uuid4())[:8]
    caminho = f"outputs/imagens/img_{uid}.png"

    img_data = requests.get(url_imagem, timeout=30).content
    with open(caminho, "wb") as f:
        f.write(img_data)

    print(f"✅ Imagem gerada e salva: {caminho}")
    return caminho


def gerar_imagem_contextual(
    tema: str,
    categoria: str = "geral",
    tipo_imagem: str = "capa de apresentação profissional",
    tamanho: str = "horizontal",
    qualidade: str = "hd"
) -> str:
    """
    Função principal: Gemini cria o prompt → DALL-E gera a imagem.
    
    Args:
        tema: Tema do documento (ex: "Vendas Q1 2026", "Plano de Marketing Digital")
        categoria: Categoria do template (financeiro, marketing, escola, etc.)
        tipo_imagem: Contexto de uso ("capa", "ilustração de seção", "banner")
        tamanho: "quadrado", "horizontal" ou "vertical"
        qualidade: "standard" ou "hd"
    
    Returns:
        Caminho local da imagem gerada
    """
    print(f"\n🎨 Gerando imagem contextual para: '{tema}' (categoria: {categoria})")

    # Passo 1: Gemini cria o prompt
    prompt_imagem = gerar_prompt_imagem_com_gemini(tema, categoria, tipo_imagem)

    # Passo 2: DALL-E gera a imagem
    caminho = gerar_imagem_dalle(prompt_imagem, tamanho, qualidade)

    return caminho


# ── Teste direto ──
if __name__ == "__main__":
    # Exemplo de uso
    caminho = gerar_imagem_contextual(
        tema="Resultados Financeiros Q1 2026",
        categoria="financeiro",
        tipo_imagem="capa de apresentação profissional",
        tamanho="horizontal"
    )
    print(f"Imagem salva em: {caminho}")
