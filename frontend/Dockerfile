FROM python:3.11-slim
WORKDIR /app
COPY frontend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY frontend ./frontend
COPY streamlit_app.py ./streamlit_app.py
COPY frontend/start_streamlit.sh ./start_streamlit.sh
RUN chmod +x ./start_streamlit.sh