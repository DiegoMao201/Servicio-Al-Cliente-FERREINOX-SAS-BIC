# CRM Ferreinox

Plataforma base para sincronizar archivos de Dropbox hacia PostgreSQL, validar la calidad de los datos y preparar la capa operativa para el agente de servicio al cliente y automatización comercial.

## Qué incluye

- Panel Streamlit unificado para operación, sincronización y diagnóstico.
- Carga de archivos CSV y Excel desde Dropbox con detección de delimitador y encoding.
- Lectura tolerante de filas irregulares sin descartar líneas del archivo fuente.
- Persistencia de esquemas de sincronización directamente en PostgreSQL.
- Tablas raw para aterrizar archivos vivos de Dropbox antes de transformarlos al modelo de negocio.
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
4. Confirmar que la tabla raw resultante aparece en el dashboard.
5. Revisar que ningún secreto quede dentro del commit.

## Diagnóstico de PostgreSQL y auditoría de estructura

El proyecto incluye un script para probar conectividad, autenticación, SSL y además inventariar tablas, columnas y volumen aproximado de datos.

Ejecuta esto desde el backend o desde el terminal del contenedor en Coolify:

```powershell
python backend/db_diagnostics.py
```

También puedes pedir muestras por tabla:

```powershell
python backend/db_diagnostics.py --sample-rows 3
```

Qué valida el script:

1. Si el host resuelve y el puerto responde por TCP.
2. Si SQLAlchemy puede autenticar y abrir sesión.
3. Versión de PostgreSQL, base activa, usuario activo, host y puerto del servidor.
4. Estado SSL de la conexión actual.
5. Tablas del esquema `public`, columnas, tipos de datos, nulabilidad y estimación de filas.

Qué revisar en Coolify si falla la conexión:

1. Si la app corre dentro del mismo stack, usa host interno `db` y puerto `5432`.
2. Si quieres conectar desde fuera del servidor, debes exponer PostgreSQL públicamente o usar un proxy seguro.
3. Verifica que PostgreSQL escuche en `0.0.0.0` y no sólo en `localhost`.
4. Verifica firewall, reglas del proveedor y `pg_hba.conf`.
5. Si el proveedor exige TLS, agrega `?sslmode=require` a `DATABASE_URL` o define `PGSSLMODE=require`.
6. En despliegues administrados por Coolify, el puerto publico puede ser distinto al puerto interno 5432. En este proyecto se confirmo acceso externo por el puerto 3000 y acceso interno por 5432.

## Arquitectura de datos actual

El flujo recomendado del proyecto ahora es:

1. Dropbox entrega archivos CSV y Excel vivos.
2. Streamlit sincroniza esos archivos a tablas `raw_*` en PostgreSQL.
3. La configuración de cada archivo queda registrada en `sync_schema_registry`.
4. Cada ejecución queda auditada en `sync_run_log`.
5. Sobre esas tablas raw se construyen vistas SQL y objetos expuestos por PostgREST.
6. El modelo operativo del agente usa tablas propias para contactos, conversaciones, mensajes y tareas.

## Servicio real de PostgREST

El `docker-compose.yml` incluye un servicio real de PostgREST en `http://localhost:3000`.

Rutas típicas después de levantar el stack:

```text
/vw_ventas_netas
/vw_estado_cartera
/vw_cuentas_por_pagar
/raw_ventas_detalle
/agent_conversation
/agent_message
```

Si arrancas la base local desde cero, PostgreSQL inicializa automáticamente:

1. `backend/schema_init.sql`
2. `backend/postgrest_views.sql`
3. `backend/postgrest_setup.sql`

## Estado de actualización

La app Streamlit ahora incluye un módulo llamado `Estado de Actualización`.

Ahí puedes ver:

1. Cuál fue el último resultado por cada CSV oficial.
2. Cuántas filas quedaron cargadas en cada tabla raw.
3. Cuándo fue la última sincronización registrada.

## Webhook base de WhatsApp

El backend ya expone un webhook base en estas rutas:

```text
GET  /webhooks/whatsapp
POST /webhooks/whatsapp
```

Qué hace ahora mismo:

1. Valida la suscripción del webhook con `WHATSAPP_VERIFY_TOKEN`.
2. Recibe mensajes entrantes de WhatsApp Cloud API.
3. Crea o reutiliza el contacto en `whatsapp_contacto`.
4. Crea o reutiliza la conversación en `agent_conversation`.
5. Guarda el mensaje entrante en `agent_message`.

Qué debes poner en tu servidor para comenzar completo:

1. `DATABASE_URL`
2. `PGRST_URL`
3. `WHATSAPP_VERIFY_TOKEN`
4. Si luego vas a responder mensajes automáticamente: `WHATSAPP_ACCESS_TOKEN` y `WHATSAPP_PHONE_NUMBER_ID`

## Flujo recomendado para empezar full conectado

1. Desplegar PostgreSQL, backend y PostgREST en tu servidor.
2. Ejecutar la sincronización oficial con `sync_official_postgrest.py`.
3. Confirmar en la pantalla `Estado de Actualización` que los 5 CSV oficiales quedaron bien.
4. Publicar el backend con HTTPS.
5. Configurar el webhook de Meta apuntando a `/webhooks/whatsapp`.
6. Verificar que los mensajes entren y se guarden en `agent_message`.
7. Después conectar la lógica de respuesta automática del agente.

## Paso a paso para desplegar el webhook desde tu servidor

Este es el camino simple y correcto:

1. Tener el backend publicado con HTTPS.
2. Tener PostgreSQL y PostgREST accesibles desde ese backend.
3. Poner las variables de entorno del backend.
4. Configurar el webhook en Meta.
5. Probar verificación y luego mensajes reales.

### 1. Variables mínimas en tu servidor

Debes definir al menos estas variables para el contenedor o servicio del backend:

```text
DATABASE_URL=postgresql://usuario:password@host:puerto/base
PGRST_URL=http://postgrest:3000
WHATSAPP_VERIFY_TOKEN=tu_token_privado_de_verificacion
```

Si más adelante vas a responder mensajes desde el backend, agrega también:

```text
WHATSAPP_ACCESS_TOKEN=EAA...
WHATSAPP_PHONE_NUMBER_ID=1234567890
```

### 2. URL que debes publicar

Tu backend debe quedar accesible por una URL pública HTTPS, por ejemplo:

```text
https://api.tudominio.com
```

El webhook de Meta apuntará a:

```text
https://api.tudominio.com/webhooks/whatsapp
```

### 3. Cómo verificar que tu servidor está listo

Antes de ir a Meta, prueba estas rutas desde navegador o Postman:

```text
GET https://api.tudominio.com/
GET https://api.tudominio.com/health
GET https://api.tudominio.com/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=tu_token_privado_de_verificacion&hub.challenge=12345
```

La última debe responder `12345`.

### 4. Qué hacer en Meta

En WhatsApp Cloud API o Meta for Developers:

1. Entra a tu app.
2. Abre el producto WhatsApp.
3. Ve a la sección de Webhooks.
4. Pega la URL pública del webhook.
5. Pega exactamente el mismo `WHATSAPP_VERIFY_TOKEN` que pusiste en tu servidor.
6. Guarda y verifica.

### 5. Qué hacer después de verificar

1. Suscribir el campo de mensajes.
2. Enviar un mensaje de prueba al número conectado.
3. Verificar que aparezca en `agent_message`.
4. Revisar la pantalla `Centro del Agente` en Streamlit.

## Operación diaria

Para refrescar la base operativa desde Streamlit ya quedó un solo botón en `Sincronización Dropbox`:

1. Carga los 5 CSV oficiales.
2. Refresca PostgREST.
3. Deja los logs listos para `Estado de Actualización`.

## Reinicio limpio de la base de datos

Si quieres borrar todo el esquema `public` y empezar desde cero, usa el script de reseteo controlado incluido en el proyecto.

Ejemplo usando la misma URI de Streamlit Cloud:

```powershell
python backend/reset_public_schema.py --db-uri "postgresql://usuario:password@host:5432/base" --yes-i-understand
```

Si necesitas SSL:

```powershell
python backend/reset_public_schema.py --db-uri "postgresql://usuario:password@host:5432/base?sslmode=require" --yes-i-understand
```

Qué hace este script:

1. Lista las tablas actuales del esquema `public`.
2. Elimina el esquema `public` completo con `CASCADE`.
3. Lo recrea limpio.
4. Restaura permisos base sobre el esquema.

Advertencia: esto elimina tablas, vistas, secuencias y relaciones del esquema `public`. No lo ejecutes sobre una base que no quieras reconstruir.

## Crear estructura desde archivo SQL

Cuando la conexión externa funcione o cuando ejecutes desde una red con acceso a PostgreSQL, puedes aplicar la estructura base del proyecto con un solo comando:

```powershell
python backend/bootstrap_database.py --db-uri "postgresql://usuario:password@host:5432/base" --sql-file backend/schema_init.sql
```

Con SSL si aplica:

```powershell
python backend/bootstrap_database.py --db-uri "postgresql://usuario:password@host:5432/base?sslmode=require" --sql-file backend/schema_init.sql
```

## Seguridad

- No subas `secrets.toml`, `.env`, logs ni archivos fuente de negocio.
- No dejes credenciales incrustadas en código Python.
- Usa un usuario PostgreSQL con permisos mínimos para el entorno cloud.
