FROM python:3.11-slim
WORKDIR /app
COPY frontend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY frontend ./frontend
COPY streamlit_app.py ./streamlit_app.py