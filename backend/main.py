from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Estado": "Sistema CRM Ferreinox Activo", "Version": "2026.1"}

# Aquí irá tu Webhook para WhatsApp más adelante