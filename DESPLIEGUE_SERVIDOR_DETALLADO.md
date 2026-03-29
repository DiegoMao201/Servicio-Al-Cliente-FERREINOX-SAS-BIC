# Guía de despliegue CRM Ferreinox en tu propio servidor (Coolify + Cloudflare + Docker Compose)

Esta guía te lleva paso a paso, sin omitir detalles, para migrar tu app CRM Ferreinox desde Streamlit Cloud a tu propio servidor, desplegar el backend FastAPI (webhook WhatsApp), y dejar todo listo bajo tu dominio gestionado con Cloudflare. Incluye preparación, configuración, despliegue, dominio, HTTPS y verificación.

---

## 1. Preparativos en tu servidor

### 1.1. Requisitos previos
- Un servidor propio (VPS, bare metal, cloud, etc) con acceso root o sudo.
- Sistema operativo recomendado: Ubuntu 22.04 LTS o similar.
- Acceso SSH al servidor.
- Docker y Docker Compose instalados.
- Coolify instalado y funcionando (opcional, pero recomendado para gestión visual).

### 1.2. Instalar Docker y Docker Compose (si no están)
```bash
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
sudo add-apt-repository "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io
sudo usermod -aG docker $USER
# Cierra y vuelve a abrir la sesión SSH para que el grupo docker se aplique
sudo apt install -y docker-compose
```

### 1.3. Instalar Coolify (opcional, recomendado)
Sigue la guía oficial: https://coolify.io/docs/getting-started/self-hosted

---

## 2. Clonar el repositorio y preparar archivos

### 2.1. Clona tu repositorio en el servidor
```bash
git clone https://github.com/tu_usuario/CRM_Ferreinox.git
cd CRM_Ferreinox
```

### 2.2. Copia y edita los archivos de entorno
```bash
cp .env.example .env
nano .env
```
Completa TODOS los campos:
- `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DATABASE_URL`, etc.
- `PGRST_URL`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`
- `OPENAI_API_KEY` si usas IA

### 2.3. Configura los secretos de Streamlit
```bash
cp frontend/.streamlit/secrets.example.toml frontend/.streamlit/secrets.toml
nano frontend/.streamlit/secrets.toml
```
Completa las claves de Dropbox, conexión a PostgreSQL, etc.

---

## 3. Configuración de dominio y HTTPS con Cloudflare

### 3.1. Apunta tu dominio/subdominio a la IP de tu servidor
- Entra a Cloudflare > DNS > Añade un registro A:
  - Nombre: `@` o `app` o el subdominio que prefieras
  - IP: (la IP pública de tu servidor)
  - Proxy: activado (nube naranja)

### 3.2. (Opcional) Configura reglas de página para redirigir HTTP a HTTPS
- En Cloudflare > Reglas de página > Nueva regla:
  - Si la URL coincide con `http://datovatenexuspro.com/*` redirige a `https://datovatenexuspro.com/$1`

### 3.3. (Opcional) Instala y configura un proxy inverso (Nginx o Caddy)
- Si usas Coolify, puedes saltar este paso: Coolify gestiona el proxy y SSL automáticamente.
- Si lo haces manual:
  - Instala Nginx: `sudo apt install nginx`
  - Configura un server block para tu dominio apuntando al puerto del backend/frontend.
  - Usa Let's Encrypt para SSL: `sudo apt install certbot python3-certbot-nginx`
  - Ejecuta: `sudo certbot --nginx -d datovatenexuspro.com`

---

## 4. Despliegue con Docker Compose

### 4.1. Revisa y edita `docker-compose.yml`
- Asegúrate de que los servicios (db, backend, frontend, postgrest) usan las variables correctas.
- Ejemplo de sección de backend:
```yaml
  backend:
    build: ./backend
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - PGRST_URL=http://postgrest:3000
      - WHATSAPP_VERIFY_TOKEN=tu_token
      - ...
```

### 4.2. Lanza los servicios
```bash
docker compose up -d --build
```

### 4.3. Verifica el estado
```bash
docker compose ps
docker compose logs backend
```

---

## 5. Verificación de servicios

### 5.1. Accede a la app y backend
- App: `https://datovatenexuspro.com` (o subdominio)
- Backend: `https://datovatenexuspro.com/health`

### 5.2. Prueba la conexión a la base de datos y PostgREST
- Desde la app y backend, asegúrate de que puedes leer datos.

---

## 6. Configuración y verificación del webhook de WhatsApp

### 6.1. En Meta for Developers
- Ve a tu app > WhatsApp > Webhooks
- Agrega la URL pública:
  - `https://datovatenexuspro.com/webhooks/whatsapp`
- Usa el mismo `WHATSAPP_VERIFY_TOKEN` que pusiste en `.env`

### 6.2. Verifica el webhook
- Meta enviará un challenge, tu backend debe responder con el valor recibido (ya está implementado en el código).
- Si falla, revisa logs del backend: `docker compose logs backend`

### 6.3. Suscribe el campo de mensajes
- En la consola de Meta, activa la suscripción a mensajes.

### 6.4. Prueba el flujo
- Envía un mensaje de WhatsApp al número conectado.
- Verifica que el mensaje aparece en la tabla `agent_message` y en el dashboard de Streamlit.

---

## 7. Consejos y mejores prácticas

- Mantén tus secretos fuera del repo (usa `.env`, `secrets.toml`, y agrégalos a `.gitignore`).
- Haz backup de la base de datos antes de migrar datos sensibles.
- Usa monitoreo externo (UptimeRobot, StatusCake) para saber si tu app cae.
- Actualiza el sistema y los contenedores regularmente.
- Documenta cada cambio y guarda esta guía en el repo para futuras referencias.

---

**¡Listo! Con esto tu app CRM Ferreinox estará corriendo en tu propio servidor, con dominio propio, HTTPS, backend y webhook de WhatsApp listos para producción.**

Si tienes errores, revisa los logs de cada servicio y asegúrate de que las variables de entorno y secretos estén correctos.
