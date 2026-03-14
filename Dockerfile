FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema necessárias para algumas bibliotecas Python
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas o requirements primeiro para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto para o container
COPY . .

# Garante que a pasta de outputs existe
RUN mkdir -p data/outputs

# Comando para iniciar a aplicação usando Uvicorn
# O Railway injeta a variável PORT automaticamente
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
