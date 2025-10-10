# Usa uma imagem oficial do Python como base
FROM python:3.10-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo de requisitos para o diretório de trabalho
COPY requirements.txt .

# Instala as bibliotecas Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos do projeto (o código) para o contêiner
COPY . .

# Define o comando que será executado quando o contêiner iniciar
CMD ["uvicorn", "rag:app", "--host", "0.0.0.0", "--port", "8000"]
