FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY dashboard/ ./dashboard/
COPY synthetic_data/ ./synthetic_data/
COPY sample_data/ ./sample_data/

ENV DB_URL="sqlite:///./trustipay.db" \
    TRUSTIPAY_API_BASE_URL="http://127.0.0.1:8000" \
    TRUSTIPAY_INGEST_KEY="trustipay_ingest_key"

EXPOSE 8000 8501

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 & streamlit run dashboard/dashboard.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true --browser.gatherUsageStats=false && wait"]
