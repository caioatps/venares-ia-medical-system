FROM python:3.11-slim

# Bibliotecas nativas exigidas pelo WeasyPrint (renderizacao do PDF) e
# fontes com boa cobertura de acentos.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY src/ ./src/
COPY templates/ ./templates/
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir -e .

# `dados` guarda o SQLite; `trabalho` e a area temporaria de download.
RUN mkdir -p /app/dados /app/trabalho
VOLUME ["/app/dados"]

EXPOSE 8080
CMD ["venares-aulas", "servir", "--host", "0.0.0.0", "--porta", "8080"]
