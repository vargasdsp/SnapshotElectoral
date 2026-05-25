FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/

# Small data files committed to git
COPY data/processed/electos/ ./data/processed/electos/
COPY data/processed/pesos/ ./data/processed/pesos/
COPY data/processed/locales.parquet ./data/processed/locales.parquet
COPY data/processed/distritos.parquet ./data/processed/distritos.parquet
COPY data/processed/insights_alcaldes.parquet ./data/processed/insights_alcaldes.parquet
COPY data/processed/communes_index.csv ./data/processed/communes_index.csv

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
