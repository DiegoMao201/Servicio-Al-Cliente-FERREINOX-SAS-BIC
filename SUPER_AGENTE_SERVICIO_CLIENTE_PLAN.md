# Super Agente Ferreinox

## Prompt reforzado y regla de priorización técnica

El agente debe responder exclusivamente con información extraída de las fichas técnicas y la base técnica oficial. Si la consulta es sobre productos industriales, pisos o marcas International/MPY, debe priorizar la información de los documentos y fichas técnicas clave de ese portafolio. Si la consulta es sobre otros portafolios (decorativo, construcción, abrasivos, etc.), debe priorizar la información técnica y fichas correspondientes a ese portafolio, nunca mezclar ni forzar información de otro segmento.

Si el RAG no arroja chunks relevantes o la información técnica no es suficiente, el agente debe activar el Protocolo de Diagnóstico Comercial:

1. Nunca inventar datos técnicos (rendimientos, tiempos, proporciones, etc.).
2. Tomar el control de la conversación con preguntas de diagnóstico para precisar la necesidad del cliente (ej: "¿El piso es interior o exterior?", "¿De qué material es?", "¿Qué uso tendrá?").
3. Sugerir categorías de productos solo si tiene evidencia en la base técnica y explicar que necesita más detalles para una recomendación precisa.
4. Citar textualmente los fragmentos de la ficha técnica y referenciar el documento fuente (nombre del PDF, sección) cuando corresponda.
5. Si no hay información suficiente, guiar al cliente con preguntas inteligentes y nunca cortar la conversación.

El agente debe cruzar los campos de marca, familia, línea y tipo de la base de artículos para identificar correctamente el portafolio y responder con la información más relevante y confiable para cada caso.

Resumen: Prioriza la información técnica relevante según el portafolio consultado, usa la base técnica y fichas técnicas correctas, y aplica el protocolo de diagnóstico comercial cuando el RAG no arroje respuesta exacta.

## Objetivo

Construir un agente comercial y de servicio al cliente que opere sobre datos reales, verificables y trazables, sin inventar productos, estados de cartera, stock ni precios.

La prioridad inicial no es pagos ni proveedores. La prioridad es atencion al cliente, identificacion correcta, catalogo confiable, consulta de cartera/compras, pedidos, cotizaciones, sugerencias de compra, sugerencias de traslados y acceso interno por roles.

## Base ya existente en este CRM

El proyecto actual ya tiene piezas utiles para la fundacion:

1. Conversaciones, mensajes, tareas, cotizaciones y pedidos en tablas del agente.
2. Verificacion de identidad por telefono, cedula, NIT, nombre y codigo de cliente.
3. Aprendizaje controlado de alias de productos en `agent_product_learning`.
4. Flujo de pedidos y cotizaciones con borradores y envio interno por correo.
5. Capa oficial de datos via PostgreSQL y PostgREST.

## Principio rector

El agente no debe responder desde memoria libre del modelo.

Debe responder desde cuatro capas:

1. Identidad validada.
2. Catalogo canonico de productos.
3. Contexto oficial del cliente.
4. Reglas de negocio deterministas antes del LLM.

Si una respuesta no puede sostenerse con datos de esas capas, el agente debe pedir precision, escalar o generar una tarea, pero nunca inventar.

## Fase 1: Servicio al cliente primero

### Capacidades prioritarias

1. Identificar al cliente por cedula, NIT, codigo cliente o nombre completo.
2. Mostrar cartera, compras y contexto comercial solo despues de validar identidad.
3. Entender productos aunque el cliente los pida con nombres informales.
4. Confirmar existencia real del articulo antes de responder.
5. Responder stock por tienda y presentacion real.
6. Armar borradores de pedido o cotizacion sin inventar precio ni disponibilidad.
7. Sugerir alternativas, complementarios, compras o traslados usando reglas reales.
8. Escalar a vendedor o gerente con trazabilidad completa.

### Lo que NO debe hacer al inicio

1. No prometer precios si el precio no esta consolidado y validado.
2. No confirmar despachos o reservas si no existe proceso real.
3. No inventar equivalencias de referencias.
4. No responder datos sensibles sin validacion de identidad.

## Arquitectura funcional objetivo

### 1. Capa de identidad

Se debe consolidar una entidad de identidad de cliente usando:

1. `numero_documento`
2. `nit`
3. `codigo cliente`
4. `telefonos`
5. `nombre legal`
6. Alias conocidos del cliente

Resultado esperado:

1. Una sola resolucion canonica a `cliente_id` y `cod_cliente`.
2. Historial de verificaciones por canal.
3. Politica de acceso por tipo de consulta.

### 2. Capa de catalogo canonico

Esta es la pieza mas importante para evitar alucinacion de productos.

Debemos crear una base canonica unificada con:

1. Referencia ERP.
2. Codigo articulo.
3. Descripcion canonica.
4. Marca.
5. Presentacion canonica.
6. Unidad y tamano.
7. Alias comerciales.
8. Alias aprendidos del agente.
9. Estado de vigencia.
10. Stock por tienda.
11. Precio si aplica y si esta autorizado.
12. Productos relacionados o sustitutos.

Fuentes para esta capa:

1. Base oficial actual en PostgreSQL.
2. Cotizador externo.
3. Inventario y rotacion externos.
4. Aprendizaje controlado ya guardado por el agente.

### 3. Capa de contexto comercial del cliente

Debemos consolidar por cliente:

1. Cartera vigente.
2. Compras recientes.
3. Productos mas comprados.
4. Tienda habitual.
5. Vendedor asignado.
6. Ultimas cotizaciones.
7. Ultimos pedidos.
8. Reclamos o incidencias previas.

### 4. Capa de decisiones deterministas

Antes de usar el modelo, el backend debe resolver por reglas:

1. Verificacion de identidad.
2. Resolucion de producto.
3. Filtro de tiendas.
4. Consulta de stock.
5. Reglas de cartera.
6. Construccion de pedidos y cotizaciones.
7. Generacion de sugerencias de traslado.
8. Generacion de sugerencias de compra.

El LLM queda para:

1. Entender intencion.
2. Redactar respuesta natural.
3. Pedir aclaraciones cuando falte informacion.
4. Resumir y ordenar resultados.

## Integracion de repos externos

### 1. Cartera Ferreinox

Usar para:

1. Historico de cartera.
2. Logica de conciliacion.
3. Reglas de vencimiento y seguimiento.

Integracion recomendada:

1. ETL a PostgreSQL.
2. Vistas PostgREST de cartera e historico.
3. Reglas de seguimiento en backend.

### 2. Cotizador Ferreinox

Usar para:

1. Catalogo comercial.
2. Estructura de listas de precios.
3. Logica de PDF de cotizacion.
4. Agrupacion comercial de productos.

Integracion recomendada:

1. Sincronizar productos y listas a tablas canonicas.
2. No depender de Google Sheets como fuente final.
3. Reutilizar PDF y logica de armado como servicio interno.

### 3. Inventario y rotacion

Usar para:

1. Alias y maestro de articulos.
2. Analisis ABC.
3. Punto de reorden.
4. Sugerencias de compra.
5. Sugerencias de traslados.
6. Deteccion de quiebres y sobrestock.

Integracion recomendada:

1. ETL a PostgreSQL.
2. Tablas analiticas materializadas.
3. Endpoints para sugerencia de compra y traslado.

### 4. Ventas gerenciales

Usar para:

1. KPIs por vendedor.
2. Tienda habitual.
3. Marcas objetivo.
4. Contexto ejecutivo para gerente.

Integracion recomendada:

1. Vistas de reporting.
2. No como base transaccional primaria.

## Acceso interno por roles

El CRM hoy separa vistas de operador y administrador, pero no tiene autenticacion real.

Debemos agregar autenticacion real con usuarios internos y roles:

1. `cliente`
2. `vendedor`
3. `gerente`
4. `operador`
5. `administrador`

### Regla por rol

#### Cliente

1. Solo ve su propia informacion.
2. Debe validar identidad por telefono + cedula/NIT/codigo cliente.

#### Vendedor

1. Ve sus clientes asignados.
2. Ve cartera, compras, cotizaciones y pedidos de su cartera.
3. Puede aprobar o enviar solicitudes comerciales.

#### Gerente

1. Ve toda la informacion comercial y operativa autorizada.
2. Ve reportes consolidados y aprobaciones.

#### Operador

1. Gestiona conversaciones.
2. Ejecuta escalamiento y seguimiento.

#### Administrador

1. Configura integraciones, catalogo, reglas y monitoreo.

## Informacion que necesitamos consolidar ya

### Identidad

1. Tabla o fuente oficial de clientes.
2. Relacion entre telefono, documento, NIT y codigo cliente.
3. Regla de asignacion cliente-vendedor.

### Productos

1. Maestro unico de referencias.
2. Alias comerciales por producto.
3. Presentaciones reales y equivalencias validas.
4. Marcas y lineas.
5. Sustitutos permitidos.
6. Productos complementarios.

### Inventario

1. Stock por tienda.
2. Transferibilidad entre tiendas.
3. Reglas de sugerencia de traslado.
4. Punto de reorden.
5. Minimos y maximos.

### Comercial

1. Lista de precios autorizada por canal o cliente.
2. Reglas de descuento.
3. Plantillas de cotizacion.
4. Flujo de aprobacion.

### Servicio al cliente

1. Politicas de respuesta permitida.
2. Casos que deben escalar.
3. Frases prohibidas del agente.
4. Evidencias requeridas para reclamos.

## Nuevas tablas recomendadas

1. `agent_user`
2. `agent_user_role`
3. `agent_customer_identity`
4. `agent_customer_assignment`
5. `product_catalog_canonical`
6. `product_catalog_alias`
7. `product_substitute_rule`
8. `product_cross_sell_rule`
9. `inventory_stock_store`
10. `inventory_transfer_suggestion`
11. `inventory_purchase_suggestion`
12. `commercial_price_list`
13. `commercial_price_rule`
14. `agent_access_audit`

## Endpoints objetivo de la primera fase

1. `POST /agent/auth/login-internal`
2. `GET /agent/me`
3. `POST /agent/identity/verify`
4. `GET /agent/customer/{cod_cliente}/context`
5. `GET /agent/products/search?q=`
6. `GET /agent/products/{reference}`
7. `GET /agent/inventory/availability?reference=&store=`
8. `POST /agent/orders/draft`
9. `POST /agent/quotes/draft`
10. `GET /agent/suggestions/transfers?reference=&store=`
11. `GET /agent/suggestions/purchase?reference=&store=`
12. `POST /agent/orders/{id}/send-email`
13. `POST /agent/transfers/{id}/send-email`

## Reglas anti alucinacion

1. Ningun producto existe si no aparece en `product_catalog_canonical`.
2. Ningun alias se promueve a canonico sin validacion.
3. Ninguna respuesta de stock sale sin tienda o contexto de tienda.
4. Ninguna respuesta de cartera sale sin identidad validada.
5. Ninguna sugerencia de compra o traslado sale si no existe fuente analitica real.
6. Cuando existan varias coincidencias, el agente debe listar opciones y pedir confirmacion.
7. Cuando no exista coincidencia, el agente debe decirlo con claridad y crear tarea si aplica.

## Orden de construccion recomendado

### Sprint 1

1. Autenticacion interna real por roles.
2. Consolidacion de identidad cliente.
3. Catalogo canonico de productos y alias.
4. Endpoints de busqueda y disponibilidad.

### Sprint 2

1. Contexto comercial del cliente.
2. Cartera y compras con validacion fuerte.
3. Escalamiento a vendedor y gerente.
4. Borradores de pedido y cotizacion mas confiables.

### Sprint 3

1. Sugerencias de traslados.
2. Sugerencias de compra.
3. Generacion de orden y envio por correo.
4. Auditoria y trazabilidad completa.

## Primera entrega util

La primera entrega util del super agente debe responder bien estas preguntas:

1. Quien es el cliente.
2. Que productos quiso decir realmente.
3. Si ese articulo existe o no.
4. En que tienda esta.
5. Que ha comprado antes.
6. Como esta su cartera.
7. Si podemos armarle pedido o cotizacion.
8. A que vendedor o gerente se debe escalar.

Si eso queda bien, el resto se puede expandir sin perder control.