# Implementacion De Dos Agentes WhatsApp

## Decision

Se recomienda operar con dos despliegues del mismo backend:

1. Despliegue `customer`
2. Despliegue `internal`

Ambos comparten:

- La misma base de datos PostgreSQL.
- El mismo corpus RAG y tablas de documentos.
- Las mismas utilidades de autenticacion, almacenamiento de conversaciones y logging.
- Las mismas variables base de OpenAI, DB, PostgREST y correo.

Cada despliegue cambia:

- El numero de WhatsApp.
- El perfil del agente.
- El conjunto de herramientas habilitadas.
- Las reglas de intencion.
- El prompt y guardias de negocio.

## Por Que Es Lo Menos Riesgoso

Es menos riesgoso que una sola app multiagente por estas razones:

1. El numero publico y el numero interno no comparten accidentalmente herramientas ni estados.
2. Un error en el prompt o en el router de un agente no contamina al otro.
3. El despliegue interno puede salir primero sin esperar a que el flujo cliente quede perfecto.
4. El rollback es simple: si algo falla en `internal`, no compromete el WhatsApp de clientes.
5. La observabilidad es mas clara porque cada instancia tiene sus propios logs y trafico.

## Como Funciona

### Despliegue Customer

- Usa su propio `WHATSAPP_PHONE_NUMBER_ID`.
- Usa su propio webhook configurado en Meta.
- Arranca con `AGENT_PROFILE=customer`.
- Solo habilita consultas tecnicas, fichas, cartera, compras y reclamos validados por compra.
- Nunca consulta inventario ni arma pedidos ni cotizaciones.
- Termina en resumen para vendedor humano.

### Despliegue Internal

- Usa otro `WHATSAPP_PHONE_NUMBER_ID`.
- Usa otro webhook configurado en Meta.
- Arranca con `AGENT_PROFILE=internal`.
- Habilita inventario por tienda, disponibilidad, precios, BI comercial y consultas tecnicas RAG.
- No arma pedidos.
- No arma cotizaciones.
- No hace traslados.

## Variables De Entorno

Compartidas entre ambos:

- `DATABASE_URL`
- `PGRST_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `SENDGRID_API_KEY`
- `SENDGRID_FROM_EMAIL`
- `SENDGRID_FROM_NAME`

Separadas por despliegue:

- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `AGENT_PROFILE`
- `APP_VERSION_LABEL`

## Perfil Internal Objetivo

El primer agente a sacar es `internal`.

### Si Debe Hacer

1. Consultar inventario por producto.
2. Consultar disponibilidad por tienda.
3. Mostrar precios.
4. Responder preguntas tecnicas con RAG.
5. Enviar o referenciar fichas tecnicas.
6. Consultar BI comercial y ventas internas.

### No Debe Hacer

1. No pedidos.
2. No cotizaciones.
3. No PDFs comerciales.
4. No traslados.
5. No registro de clientes para cierre comercial.

## Toolset Recomendado

### Internal

Mantener:

- `consultar_inventario`
- `consultar_conocimiento_tecnico`
- `consultar_ventas_internas`
- helpers de documentos tecnicos

Eliminar del perfil:

- `consultar_inventario_lote`
- `confirmar_pedido_y_generar_pdf`
- `registrar_cliente_nuevo`
- `verificar_identidad` para flujos comerciales de cierre
- `solicitar_traslado_interno`
- `radicar_reclamo`

### Customer

Mantener:

- `consultar_conocimiento_tecnico`
- fichas tecnicas
- `verificar_identidad`
- `consultar_cartera`
- helper de compras del cliente
- `radicar_reclamo` con validacion de compra
- helper de resumen para vendedor

Eliminar del perfil:

- `consultar_inventario`
- `consultar_inventario_lote`
- `confirmar_pedido_y_generar_pdf`
- `solicitar_traslado_interno`
- `consultar_ventas_internas`

## Cambios Tecnicos Minimos Recomendados

### Fase 1

1. Introducir `AGENT_PROFILE` en backend.
2. Crear dos prompts separados:
   - `agent_prompt_customer.py`
   - `agent_prompt_internal.py`
3. Crear dos listas de herramientas separadas.
4. Crear un selector central que cargue prompt y herramientas segun perfil.

### Fase 2

1. Desactivar por perfil las rutas de negocio no permitidas.
2. Agregar tests de regresion por perfil.
3. Separar dashboards frontend si se van a seguir usando.

### Fase 3

1. Limpiar codigo muerto de pedidos, cotizaciones y traslados del runtime interno.
2. Mover lo experimental a carpetas de laboratorio.
3. Dejar el runtime principal solo con codigo vigente.

## Procedimiento Rapido Para Salir Con Internal Primero

1. Congelar nuevas features del agente general.
2. Crear perfil `internal` a partir del backend actual.
3. Cortar herramientas de pedido, cotizacion y traslado.
4. Validar 10 a 20 casos reales de inventario, precio, tienda, BI y ficha tecnica.
5. Desplegar en numero interno.
6. Despues abrir el perfil `customer` como segundo despliegue.

## Regla De Oro

El agente interno es un agente de consulta operativa y comercial asistida.
No es un agente transaccional.

Mientras se mantenga esa frontera, sera rapido, util y mucho mas estable.