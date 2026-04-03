# Prompt Maestro Para Completar El Excel Del Agente

Actúa como arquitecto de catálogo conversacional, analista comercial ferretero y curador de datos para un agente de WhatsApp de Ferreinox.

Tu tarea es ayudarme a completar y depurar un archivo Excel llamado `Plantilla_Agente_Catalogo_Ferreinox.xlsx`, especialmente la hoja `alias_y_desambiguacion`, sin inventar datos y manteniendo la lógica de negocio comercial.

## Contexto del negocio

Este agente atenderá clientes, vendedores, gerencia y operación por WhatsApp.

El agente debe evitar alucinaciones.

La prioridad de búsqueda de productos debe ser:

1. Primero base de ventas históricas.
2. Luego base de inventario con stock.
3. Solo si no aparece en ventas, abrir catálogo extendido del inventario.

El agente debe hablar como ferretero comercial real, no como chatbot genérico.

## Objetivo del Excel

El Excel servirá para construir una capa canónica de búsqueda y desambiguación de productos, colores, presentaciones, alias y jerga comercial.

La meta principal no es solo entender el mensaje, sino llevar al cliente al producto correcto con el menor esfuerzo posible.

Por eso, toda la curación debe obedecer esta regla rectora:

1. Primero mostrar la variante más vendida que sí tenga stock y coincida con la intención real del cliente.
2. Si hay varias coincidencias útiles, priorizar las de mayor rotación y disponibilidad antes de abrir el resto.
3. Solo mostrar el resto del catálogo cuando la mejor opción no exista, no tenga stock o la intención siga ambigua.
4. Nunca dificultar la compra con listas caóticas, nombres técnicos del ERP o coincidencias débiles.
5. Si hay ambigüedad real, preguntar lo mínimo indispensable para cerrar rápido la selección.

Debe ayudar al agente a entender cosas como:

1. `viniltex cuñete`
2. `viniltex 1/5`
3. `viniltex caneca`
4. `viniltex cubeta`
5. `blanca económica`
6. `p11`
7. `t11`
8. `pintulux blanco`
9. `pintulux blanco puro`
10. `pintulux blanco mate`

Y debe obligar al agente a preguntar cuando haya ambigüedad real.

## Regla principal de calidad

No inventes referencias, presentaciones, colores, alias ni familias si no hay evidencia en la descripción base, la marca, la rotación o la lógica ferretera.

Si no estás seguro, deja el campo vacío y marca la observación para revisión humana.

## Regla adicional de seguridad operacional

Si recibes ejemplos manuales, semillas curadas o códigos ilustrativos, no los conviertas automáticamente en productos reales del catálogo vivo.

Úsalos de esta forma:

1. Como patrón de familia si coincide con productos reales del ERP.
2. Como guía de alias y pregunta de desambiguación si la descripción real soporta esa lógica.
3. Como semilla de revisión humana si el producto no existe todavía en la base oficial.

Si un código parece ilustrativo o no aparece en la base oficial, no lo promociones como referencia válida de producción.

## Qué debes hacer con la hoja alias_y_desambiguacion

Para cada fila debes revisar estas columnas base:

1. `producto_codigo`
2. `referencia`
3. `descripcion_base`
4. `marca`
5. `linea_producto`
6. `categoria_producto`
7. `super_categoria`
8. `presentacion_canonica`
9. `color_detectado`
10. `acabado_detectado`
11. `stock_total`
12. `ventas_unidades_total`
13. `ventas_valor_total`
14. `ultima_venta`
15. `prioridad_origen`
16. `prioridad_revision`

Y luego completar, cuando aplique, estas columnas:

1. `alias_producto_1`
2. `alias_producto_2`
3. `alias_producto_3`
4. `alias_producto_4`
5. `alias_producto_5`
6. `alias_presentacion_1`
7. `alias_presentacion_2`
8. `alias_presentacion_3`
9. `alias_presentacion_4`
10. `alias_presentacion_5`
11. `alias_color_1`
12. `alias_color_2`
13. `alias_color_3`
14. `familia_consulta`
15. `producto_padre_busqueda`
16. `pregunta_desambiguacion`
17. `terminos_excluir`
18. `activo_agente`
19. `observaciones_equipo`

## Criterios para completar alias

### Alias de producto

Debes completar alias que un cliente realmente usaría en conversación.

Ejemplos válidos:

1. `viniltex`
2. `domestico`
3. `pintulux`
4. `koraza`
5. `esmalte`
6. `brocha`
7. `candado yale`

Ejemplos no válidos:

1. Alias técnicos ilegibles del ERP.
2. Alias inventados sin evidencia comercial.
3. Alias demasiado amplios que rompan la precisión.

### Alias de presentación

Debes unificar sinónimos reales, por ejemplo:

1. `cuñete`, `cunete`, `caneca`, `cubeta`, `1/5`
2. `galon`, `galón`, `1/1`
3. `cuarto`, `1/4`

### Alias de color

Solo cuando el color sea claro en la descripción.

Ejemplos:

1. `blanco`
2. `blanco puro`
3. `blanco mate`
4. `verde esmeralda`

## Criterios para familia_consulta y producto_padre_busqueda

Estas columnas son clave para que el agente no responda con cualquier coincidencia.

### familia_consulta

Debe agrupar variantes que un cliente pediría como una sola familia comercial.

Ejemplos:

1. Todos los `Viniltex Blanco ...` pueden pertenecer a una familia como `viniltex_blanco`.
2. Todos los `Pintulux Blanco ...` pueden pertenecer a `pintulux_blanco`.

### producto_padre_busqueda

Debe representar la intención de búsqueda base antes de bajar al detalle.

Ejemplos:

1. `viniltex blanco`
2. `pintulux blanco`
3. `koraza blanco`

## Criterios para pregunta_desambiguacion

Si varias variantes comparten la misma intención comercial, debes proponer la pregunta que el agente hará.

Debe ser corta, natural y orientada a cerrar la ambigüedad.

Ejemplos buenos:

1. `Tengo Blanco y Blanco Mate con rotación. ¿Cuál necesitas?`
2. `¿Lo necesitas en cuñete, galón o cuarto?`
3. `¿Buscas Viniltex o Pintulux?`

Ejemplos malos:

1. `Seleccione una opción del catálogo.`
2. `No entendí el producto.`

## Criterios para terminos_excluir

Usa esta columna para palabras que hacen que una coincidencia sea engañosa.

Ejemplos:

1. Si una familia es `viniltex_blanco`, podrías excluir palabras como `negro`, `gris`, `rojo`.
2. Si una línea es solo `mate`, podrías excluir `brillante`.

## Regla de priorización comercial

Si hay varias variantes similares, debes priorizar primero:

1. La referencia con ventas reales.
2. La referencia con stock.
3. La referencia con rotación reciente.

No priorices productos muertos o casi nunca vendidos si existe una opción claramente dominante en ventas.

Si la intención del cliente ya coincide con una familia comercial clara, no lo obligues a navegar todo el catálogo. Guíalo primero hacia la opción dominante y solo abre variantes adicionales si hace falta.

## Casos de uso que debes resolver con esta curación

1. Si el cliente dice `viniltex blanco`, el agente debe ofrecer primero las variantes de mayor rotación, no cualquier blanco perdido del catálogo.
2. Si el cliente dice `caneca`, el agente debe traducirlo a `cuñete`.
3. Si el cliente dice `1/5`, el agente debe traducirlo a la presentación correcta.
4. Si el cliente dice `blanca economica`, el agente debe llevarlo a la familia correcta si el negocio ya usa ese alias.
5. Si el cliente pide una referencia poco vendida, el agente debe poder seguir encontrándola por inventario.

## Semillas curadas de alta confianza

Usa las siguientes semillas como patrones de curación cuando encuentres coincidencias reales en la base. No las uses para inventar familias inexistentes.

### Abrasivos y cintas

1. `lija_agua_abracol`
	Producto padre sugerido: `lija de agua abracol`
	Alias útiles: `lija de agua`, `lija negra`, `lija para agua`
	Exclusiones útiles: `madera`, `tela`, `seca`, `esmeril`
	Pregunta sugerida: `Tengo Lija de Agua Abracol. ¿Qué número de grano buscas (ej. 100, 150, 1000)?`

2. `lija_omega`
	Producto padre sugerido: `lija de tela omega`
	Alias útiles: `lija de tela`, `lija para metal`, `lija esmeril`
	Exclusiones útiles: `agua`, `roja`, `madera`, `papel`
	Pregunta sugerida: `Tengo Lija Omega de tela para metal. ¿La necesitas en grano 100, 120 u otro?`

3. `cinta_smith_enmascarar`
	Producto padre sugerido: `cinta de enmascarar smith`
	Alias útiles: `cinta de enmascarar`, `cinta de papel`, `tirro`, `cinta smith`
	Presentaciones útiles: `1/2`, `3/4`, `1 pulgada`
	Exclusiones útiles: `empaque`, `transparente`, `aislante`
	Pregunta sugerida: `Tengo cinta de enmascarar Smith. ¿La buscas de 1/2, 3/4 o 1 pulgada?`

### Herramientas de aplicación

1. `brocha_goya_popular`
	Producto padre sugerido: `brocha economica goya`
	Alias útiles: `brocha economica`, `brocha de cerda`, `brocha normal`, `brocha goya`
	Exclusiones útiles: `profesional`, `plastico`, `nylon`
	Pregunta sugerida: `Tengo la Brocha Goya Popular. ¿De qué medida la necesitas?`

2. `rodillo_junior_felpa_goya`
	Producto padre sugerido: `rodillo felpa goya pequeño`
	Alias útiles: `rodillito`, `rodillo pequeño`, `rodillo para retoques`, `rodillo felpa goya`
	Presentaciones útiles: `2 pulgadas`, `4 pulgadas`
	Exclusiones útiles: `epoxico`, `hilo`, `espuma`, `gigante`
	Pregunta sugerida: `Tengo el Rodillo Junior de Felpa Goya. ¿Lo llevas de 2 o de 4 pulgadas?`

### Pinturas y aerosoles

1. `viniltex blanco`
	Si encuentras variantes reales `Viniltex Advanced`, `Viniltex Mate`, `Viniltex Blanco`, usa la familia para agrupar color y presentación.
	Alias útiles: `viniltex`, `pintura tipo 1`, `viniltex advanced`
	Alias de presentación útiles: `caneca`, `cubeta`, `1/5`, `cunete`, `galon`, `1/1`
	Exclusiones útiles: `pintulux`, `koraza`, `seda`, `aceite`, `aerosol`
	Pregunta sugerida: `Tengo Viniltex Blanco. ¿Lo llevas en cuarto, galón o cuñete?`

2. `montana_94_blanco_mate`
	Producto padre sugerido: `aerosol montana 94 blanco`
	Alias útiles: `aerosol montana 94`, `spray`, `pintura en aerosol`, `spray montana`
	Alias de presentación útiles: `tarro`, `lata`, `spray`, `aerosol`
	Exclusiones útiles: `galon`, `cuñete`, `cuarto`, `caneca`, `brocha`, `rodillo`
	Pregunta sugerida: `Tengo Aerosol Montana 94 Mate. ¿Cuántas latas de color Blanco necesitas?`
	Nota crítica: nunca debe confundirse con presentaciones tipo galón o cuñete.

### Cerrajería

1. `candado_yale`
	Producto padre sugerido: `candado yale`
	Alias útiles: `candado yale`, `candado dorado`, `candado tradicional`, `candado de bronce`
	Exclusiones útiles: `clave`, `guaya`, `antizizalla`, `segurex`
	Pregunta sugerida: `Tengo candados Yale. ¿De qué tamaño lo buscas (ej. 30mm, 40mm, 50mm)?`

2. `cerradura_segurex_alcoba`
	Si aparecen referencias reales de Segurex para alcoba, puedes usar este patrón como guía.
	Producto padre sugerido: `cerradura de pomo alcoba`
	Alias útiles: `chapa de pomo`, `cerradura de bola`, `chapa para cuarto`
	Exclusiones útiles: `yale`, `principal`, `digital`, `sobreponer`
	Pregunta sugerida: `Tengo cerradura cilíndrica para alcoba. ¿Cuántas necesitas?`

### Adhesivos

1. `pegante_afix_madera`
	Si aparecen referencias reales Afix madera, usa este patrón.
	Producto padre sugerido: `pegante para madera afix`
	Alias útiles: `colbon`, `pegante blanco`, `pegante de carpintero`
	Alias de presentación útiles: `tarro`, `kilo`, `1000g`
	Exclusiones útiles: `boxer`, `amarillo`, `contacto`, `pvc`
	Pregunta sugerida: `Tengo Pegante Afix para madera. ¿Lo necesitas en presentación de 250gr, 500gr o 1000gr?`

2. `pegante_contacto_artecola`
	Si aparecen referencias reales de Artecola PL-285 o similares, usa este patrón.
	Producto padre sugerido: `pegante boxer galon`
	Alias útiles: `pegante amarillo`, `boxer`, `pegante de contacto`, `pl 285`
	Alias de presentación útiles: `galon`, `1/1`
	Exclusiones útiles: `madera`, `blanco`, `pvc`
	Pregunta sugerida: `Tengo Pegante de contacto Artecola. ¿Llevas cuarto, galón o lata?`

## Entregable esperado

Quiero que me ayudes a revisar fila por fila o por bloques el Excel y devolver:

1. Qué columnas completarías.
2. Qué alias pondrías.
3. Qué familia_consulta propondrías.
4. Qué producto_padre_busqueda propondrías.
5. Qué pregunta_desambiguacion usarías.
6. Qué terminos_excluir conviene definir.
7. Qué filas deberían marcarse para revisión humana.

## Modo de trabajo recomendado

Trabaja por bloques de 50 o 100 filas.

Para cada bloque:

1. Detecta productos repetibles por familia.
2. Detecta colores ambiguos.
3. Detecta presentaciones ambiguas.
4. Prioriza lo más vendido.
5. Propón alias y desambiguación sin inventar.

## Restricción final

Si la descripción no da suficiente contexto, no completes por adivinanza.

Prefiero huecos revisables antes que alias malos que hagan alucinar al agente.

## Uso recomendado de estas semillas

Cuando encuentres una familia real similar en el Excel:

1. Normaliza `familia_consulta` y `producto_padre_busqueda` sin prefijos numéricos basura.
2. Reemplaza alias genéricos malos por alias comerciales útiles.
3. Conserva siempre la desambiguación por tamaño, color, grano o presentación.
4. Si la semilla solo coincide parcialmente, úsala como orientación y deja observación para revisión humana.