FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema necessárias para o Chrome e Playwright
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    pkg-config \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libcairo2-dev \
    libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala as dependências Python (UTF-8 garantido agora)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# INSTALAÇÃO DO NAVEGADOR PARA PDF DE ALTA QUALIDADE
RUN playwright install chromium
RUN playwright install-deps chromium

# Copia todo o código do projeto
COPY . .

# Garante que as pastas de templates e outputs existem
RUN mkdir -p data/outputs data/templates/docx data/templates/pptx

CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
