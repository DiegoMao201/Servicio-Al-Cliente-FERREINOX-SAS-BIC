# Despliegue Interno Operativo

## Objetivo

Levantar el primer backend separado para el WhatsApp interno Ferreinox usando el mismo codebase actual, pero con alcance limitado a:

- inventario
- disponibilidad por tienda
- precios
- BI comercial
- RAG técnico
- fichas técnicas y hojas de seguridad

## Qué Debe Quedar Apagado

- pedidos
- cotizaciones
- PDFs comerciales
- traslados
- despachos internos por WhatsApp
- reclamos internos operativos

## Perfil Activo

El despliegue interno debe arrancar con:

```text
AGENT_PROFILE=internal
```

## Variables De Entorno Recomendadas

### Compartidas

```text
DATABASE_URL=
PGRST_URL=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=
SENDGRID_FROM_NAME=
```

### Exclusivas Del Número Interno

```text
AGENT_PROFILE=internal
APP_VERSION_LABEL=internal-whatsapp-v1
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WA_DEBOUNCE_SECONDS_INTERNAL=0.8
INTERNAL_SESSION_CACHE_SECONDS=20
```

## Ajustes Recomendados De Latencia

Para el despliegue interno conviene favorecer velocidad de respuesta sobre buffering largo:

1. `WA_DEBOUNCE_SECONDS_INTERNAL=0.8`
2. `INTERNAL_SESSION_CACHE_SECONDS=20`
3. Mantener `OPENAI_MODEL=gpt-4o-mini` mientras se estabiliza operación.

Con esa configuración el canal interno:

- espera menos antes de responder mensajes seguidos,
- evita revalidar sesión en base de datos en cada turno inmediato,
- y reduce preguntas diagnósticas extra cuando el colaborador ya dio suficiente contexto.

## Verificaciones Después Del Deploy

1. Abrir `/health` y confirmar que `agent_profile` responde `internal`.
2. Abrir `/` y confirmar que `agent_profile` responde `internal`.
3. Validar webhook con Meta sobre el número interno.
4. Probar login interno.
5. Probar inventario por producto.
6. Probar precio por producto.
7. Probar disponibilidad por tienda.
8. Probar consulta BI.
9. Probar pregunta técnica RAG.
10. Probar envío de ficha técnica.

## Casos De Prueba Mínimos

### Inventario

- "inventario de sd1 blanco"
- "precio de viniltex blanco 1501"
- "en qué tienda hay corrotec gris"

### BI

- "ventas de este mes empresa"
- "ventas de pereira esta semana"
- "top productos del mes"

### RAG Técnico

- "interthane 990 requiere thinner"
- "qué sistema recomiendan para metal galvanizado"
- "ficha técnica de aquablock"

### Bloqueos Esperados

- "hazme un pedido"
- "genera cotización"
- "crea traslado"
- "qué despachos van hoy"

## Criterio De Salida A Producción Interna

El backend interno queda listo cuando:

1. Responde bien 10 a 15 casos reales.
2. No ofrece pedidos ni cotizaciones.
3. No entra a flujos de traslado.
4. Los precios y disponibilidades salen solo de herramientas.
5. Las preguntas técnicas salen solo de RAG.

## Siguiente Paso Después Del Deploy Interno

Una vez estable el interno, se replica el despliegue para `customer` con otro número y otro perfil.