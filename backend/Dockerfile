FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY data/ /app/data/
COPY artifacts/ /app/artifacts/
COPY .streamlit/ /app/.streamlit/
COPY ["LOGO FERREINOX SAS BIC 2024.png", "/app/"]
COPY ["datos_empleados.xlsx", "/app/"]