# Guía completa para desplegar CRM Ferreinox en Coolify

Esta guía está escrita para este proyecto exacto. El objetivo es dejar funcionando en tu servidor, administrado con Coolify, todo el stack necesario para operar CRM Ferreinox con:

- Streamlit como panel operativo
- FastAPI como backend y webhook de WhatsApp
- PostgreSQL como base de datos
- PostgREST como capa de lectura de datos
- Dropbox como fuente oficial de actualización de CSV ERP
- Cloudflare como proveedor DNS del dominio
- Subdominios sobre datovatenexuspro.com

Esta guía asume que ya tienes:

- Coolify instalado y funcionando en tu servidor
- El repositorio conectado a GitHub
- El dominio datovatenexuspro.com gestionado en Cloudflare
- El proyecto ya desplegando parcialmente en Coolify

---

## 1. Arquitectura que vas a dejar funcionando

La arquitectura final esperada para este proyecto es esta:

1. `crm.datovatenexuspro.com`
   Servicio: `frontend`
   Función: panel Streamlit
   Puerto interno: `8501`

2. `apicrm.datovatenexuspro.com`
   Servicio: `backend`
   Función: API FastAPI + webhook de WhatsApp
   Puerto interno: `8000`

3. `postgrest.datovatenexuspro.com`
   Servicio: `postgrest`
   Función: lectura externa controlada de vistas SQL
   Puerto interno: `3000`
   Nota: este servicio solo debes publicarlo si realmente necesitas consumir PostgREST desde fuera del stack.

4. `db`
   Servicio interno de PostgreSQL
   Función: persistencia de datos
   Puerto interno: `5432`
   Nota: no debe exponerse públicamente.

---

## 2. Estado actual importante del proyecto

Este proyecto ya fue ajustado para que funcione mejor en servidor:

1. El backend y el frontend ya usan Python 3.11.
2. El frontend ya arranca desde `streamlit_app.py`.
3. El frontend ya no se cae si no existe `secrets.toml`.
4. El frontend ya puede leer credenciales de Dropbox desde variables de entorno.
5. El frontend puede usar `DATABASE_URL` si no hay secretos de Streamlit.
6. El backend ya incluye el webhook de WhatsApp.
7. El esquema de tablas del agente ya existe en `backend/agent_schema.sql`.

---

## 3. Variables de entorno que debes cargar en Coolify

Debes poner estas variables en Coolify para el stack o para los servicios correspondientes.

### 3.1. Variables mínimas obligatorias

```dotenv
DB_USER=postgres
DB_PASSWORD=TU_PASSWORD_REAL
DB_NAME=ferreinox_db
OPENAI_API_KEY=
WHATSAPP_VERIFY_TOKEN=ferreinox_token_123
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
```

### 3.2. Variables de Dropbox obligatorias para que funcione la sincronización oficial

Estas variables deben existir porque el módulo de sincronización Dropbox las necesita.

```dotenv
DROPBOX_ROTACION_APP_KEY=TU_APP_KEY_ROTACION
DROPBOX_ROTACION_APP_SECRET=TU_APP_SECRET_ROTACION
DROPBOX_ROTACION_REFRESH_TOKEN=TU_REFRESH_TOKEN_ROTACION
DROPBOX_ROTACION_FOLDER=/data

DROPBOX_CARTERA_APP_KEY=TU_APP_KEY_CARTERA
DROPBOX_CARTERA_APP_SECRET=TU_APP_SECRET_CARTERA
DROPBOX_CARTERA_REFRESH_TOKEN=TU_REFRESH_TOKEN_CARTERA
DROPBOX_CARTERA_FOLDER=/data

DROPBOX_VENTAS_APP_KEY=TU_APP_KEY_VENTAS
DROPBOX_VENTAS_APP_SECRET=TU_APP_SECRET_VENTAS
DROPBOX_VENTAS_REFRESH_TOKEN=TU_REFRESH_TOKEN_VENTAS
DROPBOX_VENTAS_FOLDER=/data
```

### 3.3. Variables derivadas que puedes definir si Coolify no resuelve interpolaciones automáticamente como esperas

Si ves problemas con interpolación, define también estas de forma explícita:

```dotenv
DATABASE_URL=postgresql://USUARIO:CLAVE@HOST_REAL:PUERTO_REAL/BASE_REAL
POSTGRES_DB_URI=postgresql://USUARIO:CLAVE@HOST_REAL:PUERTO_REAL/BASE_REAL
PGRST_URL=http://postgrest:3000
PGSSLMODE=prefer
```

### 3.4. Variables recomendadas por servicio

#### Servicio `frontend`

```dotenv
DATABASE_URL=postgresql://USUARIO:CLAVE@HOST_REAL:PUERTO_REAL/BASE_REAL
BACKEND_URL=https://apicrm.datovatenexuspro.com
PGRST_URL=http://postgrest:3000
STREAMLIT_SECRETS_TOML=
DROPBOX_ROTACION_APP_KEY=...
DROPBOX_ROTACION_APP_SECRET=...
DROPBOX_ROTACION_REFRESH_TOKEN=...
DROPBOX_ROTACION_FOLDER=/data
DROPBOX_CARTERA_APP_KEY=...
DROPBOX_CARTERA_APP_SECRET=...
DROPBOX_CARTERA_REFRESH_TOKEN=...
DROPBOX_CARTERA_FOLDER=/data
DROPBOX_VENTAS_APP_KEY=...
DROPBOX_VENTAS_APP_SECRET=...
DROPBOX_VENTAS_REFRESH_TOKEN=...
DROPBOX_VENTAS_FOLDER=/data
```

Si vas a usar una sola variable con el contenido completo de `secrets.toml`, puedes usar `STREAMLIT_SECRETS_TOML` y dejar las `DROPBOX_*` vacías.

#### Servicio `backend`

```dotenv
DATABASE_URL=postgresql://USUARIO:CLAVE@HOST_REAL:PUERTO_REAL/BASE_REAL
PGRST_URL=http://postgrest:3000
OPENAI_API_KEY=
WHATSAPP_VERIFY_TOKEN=ferreinox_token_123
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
```

#### Servicio `postgrest`

```dotenv
PGRST_DB_URI=postgres://USUARIO:CLAVE@HOST_REAL:PUERTO_REAL/BASE_REAL
PGRST_DB_SCHEMA=public
PGRST_DB_ANON_ROLE=web_anon
PGRST_SERVER_HOST=0.0.0.0
PGRST_SERVER_PORT=3000
```

#### Servicio `db`

```dotenv
POSTGRES_USER=postgres
POSTGRES_PASSWORD=TU_PASSWORD_REAL
POSTGRES_DB=ferreinox_db
```

---

## 4. Registros DNS que debes crear en Cloudflare

En Cloudflare crea estos registros `A` apuntando a la IP pública de tu servidor:

1. `crm.datovatenexuspro.com`
2. `apicrm.datovatenexuspro.com`
3. `postgrest.datovatenexuspro.com` solo si lo publicarás

Configuración recomendada:

1. Tipo: `A`
2. Nombre: `crm`, `apicrm`, `postgrest`
3. IPv4 address: la IP de tu servidor
4. Proxy status: activado, nube naranja

---

## 5. Qué debe quedar en Coolify

Tu archivo `docker-compose.yml` ya fue corregido para esto. No deberías editarlo manualmente en el servidor si ya estás desplegando desde GitHub.

Lo correcto es:

1. Hacer cambios localmente
2. `git add`
3. `git commit`
4. `git push origin main`
5. Dejar que Coolify haga redeploy

---

## 6. Cómo configurar el proyecto en Coolify paso a paso

### 6.1. Abre el proyecto o stack

1. Entra a Coolify.
2. Abre el proyecto donde tienes CRM Ferreinox.
3. Entra al stack basado en tu repositorio GitHub.
4. Verifica que la rama desplegada sea `main`.

### 6.2. Verifica que Coolify detecta estos servicios

1. `db`
2. `backend`
3. `postgrest`
4. `frontend`

Si no aparecen, revisa que Coolify esté leyendo correctamente tu `docker-compose.yml` desde la raíz del repositorio.

### 6.3. Configura los dominios por servicio

#### Para `frontend`

1. Entra al servicio `frontend`.
2. Busca la sección `Domains`.
3. Agrega:
   `crm.datovatenexuspro.com`
4. Puerto interno esperado:
   `8501`
5. Guarda.

#### Para `backend`

1. Entra al servicio `backend`.
2. Busca la sección `Domains`.
3. Agrega:
   `apicrm.datovatenexuspro.com`
4. Puerto interno esperado:
   `8000`
5. Guarda.

#### Para `postgrest`

1. Entra al servicio `postgrest`.
2. Si de verdad quieres acceso externo, agrega:
   `postgrest.datovatenexuspro.com`
3. Puerto interno esperado:
   `3000`
4. Guarda.

#### Para `db`

No agregues dominio. No debe exponerse.

---

## 7. Cómo cargar variables de entorno en Coolify

### Opción recomendada

Carga las variables a nivel del stack si todas son compartidas.

### Opción más controlada

Carga solo las variables que necesita cada servicio, separadas por servicio.

Recomendación práctica:

1. Variables de base compartidas: stack
2. Variables exclusivas de frontend: frontend
3. Variables exclusivas de backend: backend
4. Variables exclusivas de PostgREST: postgrest

## 7.1. Opción alternativa: usar secrets.toml en Coolify Storage

No necesitas obligatoriamente `secrets.toml`, porque este proyecto ya fue adaptado para funcionar también con variables de entorno. Esa es la opción más simple y más robusta en servidor.

Pero si quieres mantener el formato clásico de Streamlit Secrets sin subir el archivo al repositorio, entonces hazlo así:

1. No agregues `./secrets.toml` al repositorio.
2. No uses un bind mount local tipo `- ./secrets.toml:/app/.streamlit/secrets.toml` en GitHub/Coolify, porque ese archivo no existe en el repo y el despliegue se vuelve frágil.
3. Usa Storage de Coolify para crear un archivo externo fuera del repositorio.
4. Monta ese archivo en el contenedor `frontend` exactamente en esta ruta:

```text
/app/.streamlit/secrets.toml
```

5. Usa como base la plantilla incluida en el repositorio:

```text
frontend/.streamlit/secrets.template.toml
```

### Contenido recomendado del archivo secrets.toml en Coolify Storage

```toml
[postgres]
db_uri = "postgresql://postgres:TU_PASSWORD_REAL@db:5432/ferreinox_db"

[dropbox_rotacion]
app_key = "TU_APP_KEY_ROTACION"
app_secret = "TU_APP_SECRET_ROTACION"
refresh_token = "TU_REFRESH_TOKEN_ROTACION"
folder = "/data"

[dropbox_cartera]
app_key = "TU_APP_KEY_CARTERA"
app_secret = "TU_APP_SECRET_CARTERA"
refresh_token = "TU_REFRESH_TOKEN_CARTERA"
folder = "/data"

[dropbox_ventas]
app_key = "TU_APP_KEY_VENTAS"
app_secret = "TU_APP_SECRET_VENTAS"
refresh_token = "TU_REFRESH_TOKEN_VENTAS"
folder = "/data"
```

### Paso a paso dentro de Coolify

1. Abre el servicio `frontend`.
2. Ve a la sección `Storage` o `Persistent Storage`.
3. Crea un nuevo archivo o file mount externo.
4. Pega el contenido del `secrets.toml` con tus valores reales.
5. Define el mount path como:

```text
/app/.streamlit/secrets.toml
```

6. Guarda.
7. Haz `Redeploy` del servicio `frontend`.

### Recomendación técnica para este proyecto

Para este repo en producción, la mejor práctica es:

1. Usar variables de entorno en Coolify para `DATABASE_URL`, `PGRST_URL` y `DROPBOX_*`.
2. Usar `secrets.toml` solo si prefieres administrar Dropbox y PostgreSQL con formato Streamlit.
3. No mezclar un archivo secreto del repo con secretos reales del servidor.

---

## 8. Primer despliegue correcto

Cuando ya tengas:

1. DNS creados en Cloudflare
2. Variables cargadas en Coolify
3. Repo actualizado en GitHub

Haz esto:

1. Entra al stack en Coolify.
2. Pulsa `Redeploy`.
3. Espera a que reconstruya los 4 servicios.
4. Revisa logs uno por uno.

Orden recomendado de revisión:

1. `db`
2. `postgrest`
3. `backend`
4. `frontend`

---

## 9. Qué debes ver en los logs si todo va bien

### `db`

Debe iniciar sin errores de autenticación ni corrupción de volumen.

### `postgrest`

Debe iniciar y quedar escuchando en puerto `3000`.

### `backend`

Debe iniciar `uvicorn` sin crash.
No debe aparecer:

- `TypeError: unsupported operand type(s) for |`
- `ModuleNotFoundError: No module named 'backend'`
- falta de `DATABASE_URL`

### `frontend`

Debe iniciar Streamlit sin errores.
No debe aparecer:

- `No module named frontend`
- `StreamlitSecretNotFoundError`

---

## 10. Pruebas obligatorias después del despliegue

### 10.1. Probar frontend

Abre:

```text
https://crm.datovatenexuspro.com
```

Debes ver la app Streamlit.

### 10.2. Probar backend

Abre:

```text
https://apicrm.datovatenexuspro.com/
https://apicrm.datovatenexuspro.com/health
```

Debes recibir JSON válido.

### 10.3. Probar webhook de verificación

Abre esta URL cambiando el token si usas otro:

```text
https://apicrm.datovatenexuspro.com/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=ferreinox_token_123&hub.challenge=12345
```

La respuesta correcta debe ser:

```text
12345
```

### 10.4. Probar PostgREST

Si lo expones externamente, prueba por ejemplo:

```text
https://postgrest.datovatenexuspro.com/vw_cliente_contexto_agente?select=cliente_codigo&limit=3
```

---

## 11. Cómo verificar que Dropbox quedó funcionando

Dropbox en este proyecto no depende solo del backend. La sincronización principal se dispara desde la app Streamlit.

Debes comprobar esto:

1. Entra a `crm.datovatenexuspro.com`
2. Abre `Sincronización Dropbox`
3. Verifica que carguen las fuentes:
   - Rotación Inventarios
   - Cartera Ferreinox
   - Ventas Ferreinox
4. Ejecuta la actualización oficial
5. Ve a `Estado de Actualización`
6. Confirma que se actualicen los conteos

Si no aparecen fuentes Dropbox, el problema casi siempre será una de estas causas:

1. Faltan variables `DROPBOX_*`
2. El `refresh_token` está vencido o incorrecto
3. El `folder` no coincide con `/data`
4. El frontend no recibió las variables de entorno correctas

---

## 12. Qué base de datos estás usando y cómo decidirlo

Tienes dos opciones de arquitectura:

### Opción A. Base interna del stack

Usar el servicio `db` del `docker-compose`.

Ventajas:

1. Todo queda autocontenido en Coolify
2. Menos dependencias externas

Desventajas:

1. Si ya tienes una base remota viva, duplicas infraestructura
2. Debes migrar datos si quieres conservar lo actual

### Opción B. Base remota existente

Apuntar `DATABASE_URL` y `PGRST_DB_URI` a tu PostgreSQL remoto actual.

Ventajas:

1. Reutilizas la base que ya está poblada
2. No vuelves a cargar todo desde cero

Desventajas:

1. Debes ajustar el compose o sobreescribir variables en Coolify
2. Debes validar conectividad de red desde el servidor a esa base

Si tu base remota actual es la fuente real que ya validaste antes, esta suele ser la mejor opción para no fragmentar el proyecto.

---

## 13. Recomendación práctica para tu caso

Por el estado actual del proyecto, la recomendación más limpia es esta:

1. Mantener el stack con `frontend`, `backend` y `postgrest`
2. Decidir si `db` será local del stack o si seguirás con la base remota
3. Si usarás la base remota, sobreescribe `DATABASE_URL` y `PGRST_DB_URI` en Coolify con la conexión remota
4. Mantén Dropbox alimentando la base operativa oficial
5. Usa Streamlit como panel de actualización y monitoreo
6. Usa FastAPI como webhook de Meta y punto de entrada del agente

---

## 14. Qué hacer si quieres usar tu base remota actual

Si quieres que el servidor no use `db` local y en cambio use la base remota ya existente, entonces en Coolify define estas variables reales:

```dotenv
DATABASE_URL=postgresql://USUARIO:CLAVE@HOST_REMOTO:PUERTO_REMOTO/NOMBRE_BD
POSTGRES_DB_URI=postgresql://USUARIO:CLAVE@HOST_REMOTO:PUERTO_REMOTO/NOMBRE_BD
PGRST_DB_URI=postgres://USUARIO:CLAVE@HOST_REMOTO:PUERTO_REMOTO/NOMBRE_BD
```

Y valida:

1. que el servidor de Coolify tenga salida de red al host remoto
2. que el firewall permita la conexión
3. que el puerto esté abierto

---

## 15. Cómo conectar Meta cuando el backend ya esté arriba

Cuando `backend` ya funcione con HTTPS:

1. Entra a Meta for Developers
2. Abre tu app de WhatsApp Cloud API
3. Ve a `Webhooks`
4. Configura como callback URL:

```text
https://apicrm.datovatenexuspro.com/webhooks/whatsapp
```

5. Usa como verify token:

```text
ferreinox_token_123
```

6. Guarda
7. Suscribe el campo `messages`

Después prueba enviando un mensaje real al número conectado.

---

## 16. Qué no debes hacer

1. No subas `.env` al repositorio
2. No expongas PostgreSQL a internet
3. No uses `localhost` dentro de contenedores para comunicar servicios entre sí
4. No publiques PostgREST si no lo necesitas externamente
5. No dependas solo de `secrets.toml` en Coolify

---

## 17. Checklist final de despliegue

Debes poder marcar todo esto como completo:

1. `crm.datovatenexuspro.com` abre Streamlit
2. `apicrm.datovatenexuspro.com/health` responde bien
3. `postgrest.datovatenexuspro.com` responde si decides exponerlo
4. Streamlit muestra datos
5. `Sincronización Dropbox` detecta las 3 fuentes Dropbox
6. La actualización oficial corre sin errores
7. `Estado de Actualización` muestra ejecuciones recientes
8. `Centro del Agente` abre sin fallar
9. El webhook verifica correctamente con Meta
10. Los mensajes entrantes se guardan en la base

---

## 18. Si algo falla, orden correcto de diagnóstico

1. Revisa logs de `db`
2. Revisa logs de `postgrest`
3. Revisa logs de `backend`
4. Revisa logs de `frontend`
5. Verifica variables de entorno
6. Verifica DNS en Cloudflare
7. Verifica dominios en Coolify
8. Verifica puertos internos configurados por servicio

---

## 19. Qué archivo del repo controla cada cosa

1. `docker-compose.yml`
   Orquestación del stack

2. `frontend/Dockerfile`
   Imagen del frontend Streamlit

3. `backend/Dockerfile`
   Imagen del backend FastAPI

4. `frontend/config.py`
   Lectura de `DATABASE_URL`, `secrets.toml` y credenciales Dropbox

5. `backend/main.py`
   API principal y webhook de WhatsApp

6. `backend/postgrest_views.sql`
   Vistas operativas del proyecto

7. `backend/agent_schema.sql`
   Tablas operativas del agente

---

## 20. Recomendación final

No intentes cerrar todo al mismo tiempo. El orden correcto para este proyecto es:

1. Hacer que `frontend` abra bien
2. Hacer que `backend` responda `/health`
3. Confirmar que `postgrest` responde
4. Confirmar que Streamlit ve Dropbox y la base
5. Ejecutar sincronización oficial
6. Ver datos en el dashboard
7. Configurar el webhook en Meta
8. Probar mensaje real
9. Luego sí continuar con respuestas automáticas, IA, Google Workspace, agenda y correos
