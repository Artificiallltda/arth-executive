FROM python:3.11-slim

# Instalar dependências do sistema para Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar Playwright e browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copiar código
COPY . .

# Criar pasta de outputs
RUN mkdir -p outputs

# Expor porta
EXPOSE 8000

# Iniciar servidor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
