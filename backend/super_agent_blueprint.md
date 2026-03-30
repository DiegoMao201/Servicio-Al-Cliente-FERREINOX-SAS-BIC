# Super Agente WhatsApp Ferreinox

## Objetivo

Construir un agente publico de WhatsApp con respuestas fluidas, rapidas y trazables, sin alucinaciones sobre cartera, stock, compras, cotizaciones, pedidos ni documentacion tecnica.

## Principios de arquitectura

1. SQL es la fuente de verdad.
2. El backend decide el intent y la consulta; el modelo no decide a que tabla o vista ir.
3. RAG solo se usa para documentos de apoyo y conocimiento no transaccional.
4. Toda accion comercial debe quedar en tablas estructuradas, no solo en texto libre de la conversacion.
5. La memoria conversacional sirve para continuidad, no para inventar datos de negocio.

## Capa recomendada

### 1. Datos operativos

- PostgreSQL como fuente canonica.
- PostgREST como capa de lectura estable sobre vistas curadas.
- Vistas separadas por dominio:
  - `vw_cliente_contexto_agente` para contexto resumido del cliente.
  - `vw_estado_cartera` para cartera y vencidos.
  - `vw_ventas_netas` para compras e historial.
  - `productos` para catalogo comercial agregado.
  - `vw_inventario_agente` solo para detalle por tienda y disponibilidad puntual.

### 2. Orquestacion

- FastAPI como capa de control.
- Router de intent deterministico antes de invocar IA.
- Validacion de identidad obligatoria para cartera, compras, pedidos y cotizaciones personalizadas.
- IA solo para redaccion, tono, seguimiento conversacional y ayudas no criticas.

### 3. Documentos

- Dropbox + cache para fichas tecnicas y hojas de seguridad.
- Flujo de confirmacion numerada antes de enviar archivo.
- Sin OCR ni embedding para datos transaccionales.

## Flujos criticos

### Flujo de productos

1. Detectar `consulta_productos`.
2. Extraer terminos, presentacion, marca, tienda, direccion, tamano y referencias.
3. Buscar primero en `productos`.
4. Si hay tienda especifica, resolver sobre `vw_inventario_agente` filtrado por almacen.
5. Si hay empate, pedir aclaracion corta.
6. Si hay una coincidencia fuerte, responder directo.

### Flujo de cartera

1. Detectar `consulta_cartera`.
2. Pedir validacion si no hay identidad verificada.
3. Si llega cedula/NIT en una conversacion pendiente de verificacion, tratarlo como identidad y no como referencia de producto.
4. Consultar `vw_estado_cartera`.
5. Responder con datos puntuales y resumidos.

### Flujo de cotizacion

1. Crear o reutilizar un `agent_quote` en estado `borrador`.
2. Cada producto confirmado entra como `agent_quote_line`.
3. Guardar presentacion, cantidad, tienda, stock confirmado y precio unitario.
4. Mostrar resumen de cotizacion antes de enviarla.
5. Al confirmar, pasar a `confirmada` o `enviada`.

### Flujo de pedido

1. Crear o reutilizar un `agent_order` en estado `borrador`.
2. Cada producto confirmado entra como `agent_order_line`.
3. Validar stock y tienda antes de permitir confirmacion final.
4. Requerir confirmacion explicita del cliente.
5. Solo despues marcar `confirmado` y luego `enviado_erp`.

## Tablas nuevas para evitar alucinacion transaccional

- `agent_quote`
- `agent_quote_line`
- `agent_order`
- `agent_order_line`

Estas tablas permiten que el agente trabaje sobre estados estructurados y no sobre memoria libre del modelo.

## Reglas para evitar errores y lentitud

1. No consultar tablas raw desde el flujo del agente publico.
2. No usar RAG para cartera, compras, stock o pedidos.
3. No permitir que el modelo redacte importes o disponibilidad si el backend no los consulto antes.
4. Mantener maximo 1 a 2 consultas SQL por mensaje normal.
5. Cachear catalogos y documentos donde aplique, nunca cartera ni pedidos activos.
6. Separar vistas publicas de catalogo y vistas privadas por cliente.

## Hoja de ruta recomendada

1. Migrar completamente el matching comercial a `productos`.
2. Crear helpers de backend para abrir, editar y confirmar cotizaciones.
3. Crear helpers de backend para abrir, editar y confirmar pedidos.
4. Agregar RPC o endpoints internos para confirmacion final y envio a ERP.
5. Añadir pruebas de regresion para saludo, cartera, productos, documentacion y verificacion.

## Decision recomendada

La mejor arquitectura para Ferreinox es `PostgreSQL + PostgREST + FastAPI deterministico + RAG solo documental`.

No se recomienda RAG por cliente como base del agente publico porque aumenta alucinacion, latencia y riesgo de mezclar informacion sensible.