# CRM Ferreinox

Plataforma base para sincronizar archivos de Dropbox hacia PostgreSQL, validar la calidad de los datos y preparar la capa operativa para el agente de servicio al cliente y automatización comercial.

## Qué incluye

- Panel Streamlit unificado para operación, sincronización y diagnóstico.
- Carga de archivos CSV desde Dropbox con detección de delimitador y encoding.
- Persistencia local de esquemas para reprocesos automáticos.
- Dashboard de exploración de tablas en PostgreSQL.
- Backend base con FastAPI para futuras integraciones con WhatsApp, IA y webhooks.

## Estructura principal

```text
CRM_Ferreinox/
├── backend/
├── frontend/
├── .streamlit/
├── streamlit_app.py
├── requirements.txt
├── runtime.txt
├── .env.example
└── README.md
```

## Ejecución local

1. Crea y activa el entorno virtual.

```powershell
python -m venv .venv
.venv\Scripts\activate
```

2. Instala dependencias de la app Streamlit.

```powershell
pip install -r requirements.txt
```

3. Crea tu archivo local de secretos a partir del ejemplo.

```powershell
Copy-Item .streamlit\secrets.example.toml .streamlit\secrets.toml
```

4. Completa tus credenciales reales en `.streamlit/secrets.toml`.

5. Ejecuta la aplicación principal.

```powershell
streamlit run streamlit_app.py
```

## Despliegue en Streamlit Cloud

1. Crea un repositorio nuevo en GitHub, sin subir secretos ni datos sensibles.
2. Sube este proyecto usando la rama principal.
3. En Streamlit Cloud, selecciona el repositorio y usa como archivo principal `streamlit_app.py`.
4. En la sección `Secrets`, pega el contenido equivalente a tu archivo local de secretos.
5. Despliega y valida primero el módulo `Diagnóstico de Conexiones`.
6. Luego ejecuta el módulo `Sincronización Dropbox` y finalmente verifica datos en `Dashboard Operativo`.

## Configuración sensible

El repositorio ya está preparado para no versionar secretos reales. Usa alguno de estos mecanismos:

- Streamlit Secrets para la app desplegada.
- `DATABASE_URL` o `POSTGRES_DB_URI` como variable de entorno para procesos auxiliares.
- `.env` local solo para desarrollo o Docker, nunca para GitHub.

## Creación del repositorio y push inicial

Para publicar este proyecto sobre el repositorio existente, ejecuta:

```powershell
git init
git add .
git commit -m "Initial production-ready CRM Ferreinox setup"
git branch -M main
git remote add origin https://github.com/DiegoMao201/Servicio-Al-Cliente-FERREINOX-SAS-BIC.git
git push -u origin main
```

## Validación recomendada antes del deploy

1. Abrir `Diagnóstico de Conexiones` y probar PostgreSQL.
2. Probar al menos una fuente de Dropbox.
3. Sincronizar un archivo controlado.
4. Confirmar que la tabla resultante aparece en el dashboard.
5. Revisar que ningún secreto quede dentro del commit.

## Seguridad

- No subas `secrets.toml`, `.env`, logs ni archivos fuente de negocio.
- No dejes credenciales incrustadas en código Python.
- Usa un usuario PostgreSQL con permisos mínimos para el entorno cloud.
