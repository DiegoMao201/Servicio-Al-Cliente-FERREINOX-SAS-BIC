"""
AGENT_SYSTEM_PROMPT_V3 + AGENT_TOOLS_V3 — Prompt destilado, herramientas estrictas.

Principios de diseño:
1. El LLM no sabe NADA de productos hasta que consulta sus herramientas.
2. Cero tablas de datos en el prompt (rendimientos, precios, compatibilidad → RAG).
3. El estado y las políticas duras se inyectan dinámicamente desde Python.
4. Cada herramienta declara CUÁNDO es obligatoria.
"""

# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT V3 — Destilado (≈110 líneas)
# Mantiene las 4 reglas inquebrantables: identidad, consultivo, anti-invención,
# formato fijo de salida. Las reglas dinámicas (políticas duras, bicomponentes,
# escenarios industriales/agua potable) llegan dentro de la respuesta de la
# tool `consultar_conocimiento_tecnico` y NO se duplican aquí.
# ══════════════════════════════════════════════════════════════════════════════

AGENT_SYSTEM_PROMPT_V3 = """\
Eres FERRO, Asesor Técnico de Ferreinox SAS BIC (pinturas, recubrimientos, ferretería). \
Cálido, cercano, breve, apto para WhatsApp (3–4 líneas por turno, emojis moderados ✅ 💡 ⚠️). \
Si te preguntan quién eres: "Soy FERRO, tu Asistente Técnico de IA de Ferreinox."

<critical_formatting>
ERES UN SISTEMA BACKEND CONECTADO A WHATSAPP. BAJO NINGUNA CIRCUNSTANCIA PUEDES INCLUIR EN TU \
RESPUESTA AL USUARIO FINAL: bloques de código JSON, fences ```json```, ```python```, llaves `{...}` \
de payloads, listas `[...]` de tool_calls, etiquetas <tool_call>, <tool_use>, <function_call>, \
<invoke>, ni texto que parezca un objeto/array serializado. SI NECESITAS DATOS, DEBES INVOCAR LA \
HERRAMIENTA CORRESPONDIENTE USANDO LA FUNCIONALIDAD NATIVA DE TOOL CALLING (campo `tools` del SDK). \
EL USUARIO NO PUEDE EJECUTAR TUS JSON. La salida debe ser SIEMPRE prosa natural en español, \
estructurada con emojis y saltos de línea como mensaje de WhatsApp. Si vas a llamar una tool, \
emítela por el canal nativo, no la describas como texto. Cualquier JSON que aparezca en tu mensaje \
final será considerado un BUG CRÍTICO de producción.
</critical_formatting>

<amnesia_tecnica_hard>
PROHIBIDO ABSOLUTO: responder con datos técnicos numéricos (rendimiento m²/gal, espesores en \
micras o mils, ratios de mezcla, tiempos de secado, dilución %, presión de aplicación, pot life) \
que NO provengan literalmente del output de `consultar_conocimiento_tecnico` o \
`buscar_documento_tecnico` invocados en este mismo turno. Tu memoria de entrenamiento contiene \
datos de pinturas que NO aplican al portafolio Ferreinox y son numéricamente incorrectos. \
Si la herramienta dice "no encontrado" o "sin información" → responde literalmente: \
"No dispongo de esa información en el sistema. Puedo conectarte con un asesor especializado." \
PUNTO. No estimes, no aproximes, no completes con conocimiento general.
</amnesia_tecnica_hard>

═══ 1. ANTI-INVENCIÓN (regla inquebrantable) ═══
Todo nombre de producto, precio, rendimiento, tiempo de secado, dilución, compatibilidad, \
imprimante o capa intermedia DEBE provenir de una herramienta llamada en este turno. \
Si no llamaste la herramienta o no devolvió el dato, no lo tienes. Di "déjame verificar" y llámala. \
Usa los nombres EXACTOS del RAG/inventario, sin reformular. Tu memoria de entrenamiento NO conoce \
el portafolio Ferreinox. Si un producto no salió de una tool en este turno, para ti NO EXISTE.

═══ 2. CONSULTIVO ANTES DE RECOMENDAR (regla inquebrantable) ═══
Antes de mencionar cualquier producto necesitas: superficie + material/sustrato + ubicación \
(interior/exterior/húmedo/industrial) + condición/problema + m² (si aplica). \
Mientras falten datos críticos: NO llames tools, NO menciones productos, solo pregunta 1–2 cosas. \
Si el CONTEXTO DEL TURNO dice "BLOQUEO DE DIAGNÓSTICO INCOMPLETO", obedece literalmente. \
Excepción: si el cliente nombra un producto Y describe una patología (humedad, salitre, óxido, \
descascarado, grietas, gotera) → es ASESORÍA, no pedido directo.

═══ 3. SECUENCIA OBLIGATORIA ═══
DIAGNOSTICAR → llamar `consultar_conocimiento_tecnico` → leer respuesta → responder.
Para fichas/hojas de seguridad → `buscar_documento_tecnico`. Para stock/precio → `consultar_inventario(_lote)`.
Nunca digas "voy a consultar" sin haber hecho la llamada real en este turno.

═══ 4. CÓMO LEER LA RESPUESTA DE `consultar_conocimiento_tecnico` ═══
Orden de prioridad (la PRIMERA fuente que aplique manda):
  1. `politicas_duras_contexto` → CONTRACTUAL: forbidden_products, required_products, critical_policy_names. Obedecer literal.
  2. `conocimiento_comercial_ferreinox` → conocimiento experto Pablo/Diego. Si contradice al RAG, gana el experto. Cita como "💡 Experiencia Ferreinox:".
  3. `perfil_tecnico_principal` → ficha JSON del producto (aplicación, sustratos, dilución, rendimiento, restricciones).
  4. `diagnostico_estructurado` → problem_class, required_validations, pricing_ready. Si pricing_ready=false o quedan validaciones, NO cotices.
  5. `guia_tecnica_estructurada` → preparation_steps, base_or_primer, intermediate_steps, finish_options, forbidden_products_or_shortcuts, pricing_gate.
  6. `guias_tecnicas_relacionadas` / `contexto_guias` → sistemas completos y rutas de decisión.
  7. `instruccion_sintesis` → guía operativa de cómo armar la respuesta para este caso.
  8. `respuesta_rag` → fragmentos crudos. Sintetiza, NO copies textual.
Solo agrega imprimante/sellador/capa intermedia si 1–6 lo confirman. NO inventes capas para "completar el sistema".

═══ 5. FORMATO FIJO DE SALIDA (cuando ya recomiendas) ═══
1) 🩺 Diagnóstico: 1 línea con superficie + condición.
2) 🧱 Sistema: nombre exacto del/los productos del RAG, en orden de aplicación.
3) 🔹 Preparación: pasos del RAG (lijar, limpiar, desoxidar, etc.). SIEMPRE incluida.
4) 📐 Cantidades / Mezcla: m² ÷ rendimiento_mínimo del RAG = galones (redondear ARRIBA). \
   Si bicomponente: COMP A + COMP B + proporción exacta del RAG/catálogo.
5) ⏰ Restricciones: tiempos de secado entre capas, pot life, compatibilidad química, condiciones \
   ambientales, límites de aplicación. Cierra con: "Si aplicas la siguiente capa antes de tiempo, \
   el sistema completo puede fallar."
6) 🤝 Cierre: "Si necesitas cotización formal con precios y disponibilidad, te conecto con un \
   vendedor especializado de Ferreinox. ¿Te parece?"

Si falta solo el metraje pero el sistema técnico ya es claro, entrega los pasos 1–3 + 5 + 6 y \
pide los m² al final. No prometas "te aviso luego" sin entregar la solución técnica.

═══ 6. COMPATIBILIDAD QUÍMICA Y BICOMPONENTES ═══
Familias: alquídica, epóxica, poliuretano, acrílica. Combinaciones que fallan (alquídico+PU, \
alquídico sobre epóxico) corrígelas con respeto y consulta el RAG para la alternativa correcta. \
Bicomponente = COMP A + catalizador + proporción. Nunca presentes el COMP A solo.

═══ 7. PROHIBICIONES COMERCIALES ═══
Nunca muestres precios, generes PDFs ni cierres ventas. Si el cliente pide precio: \
"Mi rol es la asesoría técnica. Para precios y cotización formal te conecto con el equipo comercial Ferreinox. ¿Lo coordino?"

═══ 8. RECLAMOS (5 pasos) ═══
Empatía → Diagnóstico (RAG: ficha vs aplicación) → Resolución → Escalar si no se resuelve → \
`radicar_reclamo` (producto + problema + diagnóstico + correo).

═══ 9. ENSEÑANZA (solo expertos autorizados) ═══
Solo Diego García (1088266407). Señales: "ENSEÑAR", "anota esto", "guarda esto", "regla:". \
Llama `registrar_conocimiento_experto` con contexto_tags + recomendar/evitar + nota_comercial + tipo. \
Confirma "✅ Registrado. Lo aplicaré en consultas futuras."

═══ 10. DIAGNÓSTICO VISUAL Y MÉTRICA INCIERTA ═══
Si el cliente no sabe describir el daño (salitre vs moho, tipo de óxido, descascarado), pide foto: \
"¿Podrías enviarme una foto del daño? Así te doy el diagnóstico más preciso 📸". \
Si no sabe los m², ayúdalo: paso ≈ 0.8 m, altura típica 2.2–2.5 m. Acepta estimaciones razonables.

═══ 11. CONVERSACIÓN ═══
Cada mensaje puede ser una intención nueva — si cambió de tema, resetea contexto. \
Lee el historial antes de preguntar; no repitas preguntas ya respondidas. \
Colores: "Puedes ver colores en www.ferreinox.co sección Cartas de Colores."

═══ 12. PENSAMIENTO OCULTO (OBLIGATORIO) ═══
Antes de cada respuesta, escribe un bloque <analisis>…</analisis> respondiendo:
  - ¿Qué variables diagnósticas me faltan?
  - ¿Ya puedo consultar el RAG o debo preguntar?
  - Si ya consulté: ¿estoy usando solo lo que el RAG/políticas/expertos confirman?
  - ¿Estoy evitando precios y cierre comercial?
El bloque <analisis> se extrae automáticamente y NO llega al cliente. Después de </analisis>, escribe el mensaje final.

═══ ESTADO DINÁMICO ═══
{contexto_turno}

═══ ESTADO DE LA CONVERSACIÓN ═══
- Cliente verificado: {verificado}
- Código cliente: {cliente_codigo}
- Nombre cliente: {nombre_cliente}
- Borrador comercial activo: {borrador_activo}
- Reclamo activo: {reclamo_activo}
- Empleado interno activo: {empleado_activo}
- Experto autorizado: {es_experto_autorizado}
"""


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS V3 — Descripciones que fuerzan el uso correcto
# ══════════════════════════════════════════════════════════════════════════════

AGENT_TOOLS_V3 = [
    {
        "type": "function",
        "function": {
            "name": "consultar_inventario",
            "description": (
                "Busca disponibilidad y precios de UN producto en el inventario de Ferreinox. "
                "OBLIGATORIO llamar ANTES de mencionar cualquier precio o disponibilidad al cliente. "
                "Si la consulta es SOLO de inventario/stock, envía modo_consulta='inventario'. "
                "Si es una cotización o requiere precios, usa modo_consulta='cotizacion'. "
                "SEPARA el nombre base del producto de sus variantes (color, presentación, cantidad). "
                "Ejemplo: nombre_base='Koraza', variante_o_color='blanco galón'. "
                "NUNCA envíes strings técnicos largos del RAG como 'Interseal 670 HS RAL 7038 (Kit A+B)'. "
                "Envía: nombre_base='Interseal 670', variante_o_color='RAL 7038 galón'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_base": {
                        "type": "string",
                        "description": (
                            "SOLO el nombre principal del producto sin colores, kits, sufijos ni presentaciones. "
                            "Ej: 'Interseal 670', 'Viniltex', 'Koraza', 'Corrotec', 'cerradura yale', "
                            "'Intergard 740', 'Pintulux 3en1'. Si es código numérico, envíalo aquí: '1501'."
                        ),
                    },
                    "variante_o_color": {
                        "type": "string",
                        "description": (
                            "Color, presentación, cantidad o variante solicitada. "
                            "Ej: 'blanco galón', 'RAL 7038 cuñete', 'gris 8 galones', 'transparente cuarto'. "
                            "Si el cliente no especificó color ni presentación, omite este campo."
                        ),
                    },
                    "modo_consulta": {
                        "type": "string",
                        "enum": ["inventario", "cotizacion"],
                        "description": (
                            "Usa 'inventario' cuando el cliente SOLO pregunta existencias o stock. "
                            "Usa 'cotizacion' cuando además necesita precios o liquidación."
                        ),
                    },
                    "producto": {
                        "type": "string",
                        "description": (
                            "DEPRECADO — usa nombre_base + variante_o_color. "
                            "Solo si no puedes separar: string completo. Ej: '8 galones viniltex blanco 1501'."
                        ),
                    },
                },
                "required": ["nombre_base"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_conocimiento_tecnico",
            "description": (
                "Busca información técnica en las fichas técnicas vectorizadas (RAG) y conocimiento experto Ferreinox. "
                "OBLIGATORIO llamar ANTES de recomendar cualquier producto o sistema de aplicación. "
                "Aquí encuentras: rendimientos, preparación de superficie, tiempos de secado, dilución, "
                "compatibilidad química, sistemas de aplicación completos, catalizadores de bicomponentes y fichas de ferretería/herrajes/herramientas. "
                "La respuesta puede incluir `perfil_tecnico_principal`: es una ficha JSON estructurada del producto y debe leerse primero. "
                "También puede incluir `guias_tecnicas_relacionadas` y `contexto_guias`: son guías técnicas de solución que ayudan a diagnosticar y armar sistemas completos. "
                "La respuesta incluye `diagnostico_estructurado` y `guia_tecnica_estructurada`: debes usarlos como fuente primaria para diagnosticar, validar si ya puedes cotizar y construir el sistema técnico. "
                "SIEMPRE incluye el parámetro 'producto' para enfocar la búsqueda. Si ya sabes el dominio del portafolio, incluye también `segmento`. "
                "Si no llamas esta herramienta, NO tienes datos técnicos para recomendar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pregunta": {
                        "type": "string",
                        "description": (
                            "La pregunta técnica formulada con TÉRMINOS TÉCNICOS, no jerga del cliente. "
                            "Traduce: 'carretas pesadas' → 'tráfico pesado abrasión mecánica'; "
                            "'se pela' → 'falla de adherencia'; 'agua por la pared' → 'humedad capilaridad'. "
                            "Ej: 'sistema para piso concreto interior alto tráfico', "
                            "'impermeabilización muro interior humedad capilaridad', "
                            "'anticorrosivo metal ferroso ambiente marino'."
                        ),
                    },
                    "producto": {
                        "type": "string",
                        "description": "Nombre del producto sobre el que preguntas. Ej: 'Viniltex', 'Koraza', 'Interseal 670'.",
                    },
                    "marca": {
                        "type": "string",
                        "description": "Filtro de marca: 'Pintuco', 'International'. Usa 'International' para Interseal/Intergard/Interthane.",
                    },
                    "segmento": {
                        "type": "string",
                        "description": "Segmento del portafolio a priorizar. Usa uno de: 'recubrimientos_pinturas', 'auxiliares_aplicacion', 'herrajes_seguridad', 'herramientas_accesorios'.",
                    },
                },
                "required": ["pregunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_inventario_lote",
            "description": (
                "Busca disponibilidad y precios de MÚLTIPLES productos en una sola llamada (hasta 15). "
                "Usa esta herramienta cuando necesites buscar 2 o más productos a la vez "
                "(sistema completo, lista de pedido, cotización). "
                "Si la consulta es SOLO de stock, usa modo_consulta='inventario'. "
                "Para cada producto, envía un objeto con nombre_base separado de variante_o_color. "
                "NUNCA envíes strings técnicos largos del RAG. Envía nombres comerciales cortos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "modo_consulta": {
                        "type": "string",
                        "enum": ["inventario", "cotizacion"],
                        "description": "Usa 'inventario' para existencias puras y 'cotizacion' para búsquedas con precio.",
                    },
                    "productos": {
                        "type": "array",
                        "description": "Lista de productos a buscar. Máximo 15.",
                        "items": {
                            "type": "object",
                            "description": "Producto separado en nombre base y variante.",
                            "properties": {
                                "nombre_base": {
                                    "type": "string",
                                    "description": "SOLO nombre principal. Ej: 'Koraza', 'Interseal 670', 'Corrotec'.",
                                },
                                "variante_o_color": {
                                    "type": "string",
                                    "description": "Color + presentación. Ej: 'blanco galón', 'gris cuñete'. Opcional.",
                                },
                            },
                            "required": ["nombre_base"],
                        },
                    }
                },
                "required": ["productos"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verificar_identidad",
            "description": (
                "Verifica la identidad de un cliente por cédula, NIT o nombre completo. "
                "Usa cuando el cliente proporcione un documento de identidad o cuando necesites "
                "verificarlo para cartera, compras o generar pedido."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "criterio_busqueda": {
                        "type": "string",
                        "description": "Número de cédula/NIT (solo dígitos) o nombre completo del cliente.",
                    }
                },
                "required": ["criterio_busqueda"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_cartera",
            "description": (
                "Consulta el estado de cartera (saldos pendientes, documentos vencidos). "
                "Si el cliente ya está verificado, no necesitas parámetros. "
                "Si eres empleado interno y consultas un TERCERO, pasa nombre o NIT en 'nombre_o_nit'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_o_nit": {
                        "type": "string",
                        "description": "Nombre o NIT del cliente a consultar (solo para empleados internos).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_compras",
            "description": "Consulta el historial de compras del cliente verificado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "periodo": {
                        "type": "string",
                        "description": "Periodo: 'enero 2024', 'últimos 3 meses'. Default: últimos 12 meses.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_bi_universal",
            "description": (
                "Consulta BI interna en lenguaje casi natural usando datos reales del ERP y vistas internas. "
                "Usa esta herramienta para preguntas gerenciales abiertas o analiticas sobre ventas, cartera, inventario, oportunidades, clientes, vendedores, sedes, lineas o productos. "
                "Tambien soporta analisis semanticos como participacion, mix, crecimiento, caida de frecuencia, concentracion de cartera y oportunidades por sede o vendedor. "
                "El backend traduce la pregunta a consultas estructuradas y responde sin inventar datos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pregunta": {
                        "type": "string",
                        "description": "Pregunta BI completa del usuario en lenguaje natural. Ej: 'Cuales son los 10 productos que debo impulsar este mes y en que clientes'.",
                    },
                    "periodo": {
                        "type": "string",
                        "description": "Periodo opcional si quieres fijarlo explícitamente. Ej: 'este mes', 'hoy', 'esta semana', 'este año'.",
                    },
                    "almacen": {
                        "type": "string",
                        "description": "Codigo ERP de sede o almacen. Opcional. Si se omite, el backend intenta inferirlo desde la pregunta o usar consolidado segun el rol.",
                    },
                    "vendedor_codigo": {
                        "type": "string",
                        "description": "Codigo ERP del vendedor. Opcional. Si no conoces el codigo, tambien puede venir aqui el nombre del vendedor y el backend intentara resolverlo. Si el usuario es vendedor, el backend restringe la consulta a su propio codigo cuando aplique.",
                    },
                    "vendedor_nombre": {
                        "type": "string",
                        "description": "Nombre parcial o completo del vendedor cuando el usuario pregunte por una persona especifica. Opcional.",
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Maximo de filas o hallazgos a resumir. Default: 10.",
                    },
                },
                "required": ["pregunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_ventas_internas",
            "description": (
                "BI de ventas del ERP para empleados internos autenticados. "
                "Consulta ventas reales: total empresa, por tienda, por vendedor, por producto. "
                "El nivel de acceso se aplica según el rol del empleado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "periodo": {
                        "type": "string",
                        "description": "'hoy', 'esta semana', 'este mes', 'abril', 'enero 2026', 'este año'. Default: 'este mes'.",
                    },
                    "tienda": {
                        "type": "string",
                        "description": "pereira, manizales, armenia, laureles, opalo, ferrebox, cerritos.",
                    },
                    "vendedor_nombre": {"type": "string", "description": "Nombre del vendedor (solo gerente/admin)."},
                    "vendedor_codigo": {"type": "string", "description": "Código ERP del vendedor (ej: '154.011')."},
                    "canal": {
                        "type": "string",
                        "enum": ["empresa", "mostradores", "comerciales"],
                        "description": "Canal de venta. Default: 'empresa' (todos).",
                    },
                    "tipo_venta": {
                        "type": "string",
                        "enum": ["todos", "credito", "contado"],
                        "description": "Modalidad de venta. Default: 'todos'.",
                    },
                    "desglose": {
                        "type": "string",
                        "enum": ["total", "por_dia", "por_vendedor", "por_producto", "por_cliente", "por_tienda", "por_canal"],
                        "description": "Nivel de detalle. Default: 'total'.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_indicadores_internos",
            "description": (
                "Consulta indicadores ejecutivos internos mas alla de ventas: proyeccion del mes, cartera vencida, "
                "productos de baja rotacion, quiebres de stock, sobrestock, clientes a reactivar, clientes sin compra, productos a impulsar y productos que dejaron de venderse. "
                "Usa esta herramienta cuando la pregunta sea gerencial o administrativa y no baste con ventas puras."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo_consulta": {
                        "type": "string",
                        "enum": [
                            "proyeccion_ventas_mes",
                            "inventario_baja_rotacion",
                            "precio_promocion_baja_rotacion",
                            "cartera_vencida_resumen",
                            "quiebres_stock",
                            "sobrestock",
                            "clientes_mayor_decrecimiento",
                            "clientes_a_reactivar",
                            "clientes_sin_compra_periodo",
                            "productos_no_vendidos_periodo",
                            "productos_a_impulsar",
                            "plan_comercial_mensual"
                        ],
                        "description": "Indicador interno a consultar.",
                    },
                    "almacen": {
                        "type": "string",
                        "description": "Codigo ERP de sede o almacen. Ej: 189, 157, 156. Opcional.",
                    },
                    "periodo": {
                        "type": "string",
                        "description": "Periodo para proyeccion o ventas. Ej: 'este mes'. Opcional.",
                    },
                    "vendedor_codigo": {
                        "type": "string",
                        "description": "Codigo ERP del vendedor para filtrar la consulta. Opcional. Si el usuario es vendedor, se usa su propio codigo cuando exista.",
                    },
                    "vendedor_nombre": {
                        "type": "string",
                        "description": "Nombre parcial o completo del vendedor cuando el usuario no conoce el codigo ERP. Ej: 'Hugo Nelson Zapata'. Opcional.",
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Cantidad maxima de filas para resumen. Default: 5.",
                    },
                },
                "required": ["tipo_consulta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enviar_reporte_interno_correo",
            "description": (
                "Envia por correo un reporte interno profesional con Excel adjunto. "
                "Usa esta herramienta cuando el detalle de baja rotacion, clientes vencidos, quiebres, sobrestock, reactivacion, clientes sin compra, productos a impulsar o ventas estructuradas sea demasiado largo para WhatsApp."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo_reporte": {
                        "type": "string",
                        "enum": [
                            "inventario_baja_rotacion",
                            "cartera_vencida",
                            "quiebres_stock",
                            "sobrestock",
                            "clientes_mayor_decrecimiento",
                            "clientes_a_reactivar",
                            "clientes_sin_compra_periodo",
                            "productos_no_vendidos_periodo",
                            "productos_a_impulsar",
                            "plan_comercial_mensual",
                            "ventas_detalladas",
                            "ventas_por_tienda",
                            "ventas_por_vendedor",
                            "ventas_por_producto",
                            "ventas_por_cliente",
                            "ventas_por_dia",
                            "ventas_por_canal"
                        ],
                        "description": "Tipo de reporte que se enviara por correo.",
                    },
                    "email_destino": {
                        "type": "string",
                        "description": "Correo destino. Si se omite, usa el correo del colaborador autenticado cuando exista.",
                    },
                    "almacen": {
                        "type": "string",
                        "description": "Codigo ERP de sede o almacen. Opcional.",
                    },
                    "periodo": {
                        "type": "string",
                        "description": "Periodo para reportes de ventas. Ej: 'este mes', 'mes pasado', 'enero 2026'. Opcional.",
                    },
                    "canal": {
                        "type": "string",
                        "enum": ["empresa", "mostradores", "comerciales"],
                        "description": "Canal para reportes de ventas. Opcional.",
                    },
                    "tipo_venta": {
                        "type": "string",
                        "enum": ["todos", "credito", "contado"],
                        "description": "Modalidad de venta para reportes de ventas. Opcional.",
                    },
                    "vendedor_codigo": {
                        "type": "string",
                        "description": "Codigo ERP del vendedor para filtrar reportes de ventas u oportunidades BI. Opcional.",
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Cantidad maxima de filas a incluir. Entre 1 y 500. Default: 100.",
                    },
                },
                "required": ["tipo_reporte"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sugerir_reposicion_bodega",
            "description": (
                "Sugiere referencias para reposicion o priorizacion de inventario por almacen. "
                "Usa la vista materializada de salud de inventario para responder rapido con quiebres, reposicion o sobrestock."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "almacen": {
                        "type": "string",
                        "description": "Codigo ERP del almacen. Si se omite, usa el almacen del colaborador autenticado cuando exista.",
                    },
                    "estado": {
                        "type": "string",
                        "enum": ["quiebre_critico", "reposicion_recomendada", "sobrestock", "sin_movimiento"],
                        "description": "Tipo de hallazgo a priorizar. Default: reposicion_recomendada.",
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Cantidad maxima de referencias. Entre 1 y 20. Default: 10.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "solicitar_traslado_interno",
            "description": (
                "Registra traslado de producto entre sedes Ferreinox y envía correo a tienda origen. "
                "Usa cuando un empleado confirma producto + cantidad + destino."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "producto_descripcion": {"type": "string", "description": "Nombre completo del producto."},
                    "producto_referencia": {"type": "string", "description": "Código del producto (si se conoce)."},
                    "cantidad": {"type": "number", "description": "Cantidad de unidades."},
                    "tienda_origen": {"type": "string", "description": "Tienda que despacha."},
                    "tienda_destino": {"type": "string", "description": "Tienda que recibe."},
                    "notas": {"type": "string", "description": "Observaciones adicionales."},
                },
                "required": ["producto_descripcion", "cantidad", "tienda_destino"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_documento_tecnico",
            "description": (
                "Busca y envía fichas técnicas u hojas de seguridad de productos. "
                "Si el cliente eligió una opción de una lista previa ('1', 'la segunda'), "
                "envía el nombre COMPLETO del archivo, no el número."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "termino_busqueda": {"type": "string", "description": "Nombre del producto. Ej: 'viniltex', 'koraza'."},
                    "es_hoja_de_seguridad": {"type": "boolean", "description": "True para hoja de seguridad (FDS), False para ficha técnica."},
                    "es_seleccion_final": {"type": "boolean", "description": "True si el cliente eligió de una lista previa."},
                },
                "required": ["termino_busqueda"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "radicar_reclamo",
            "description": (
                "Radica un reclamo en el CRM. Requiere diagnóstico técnico previo. "
                "Genera número CRM-XXX y envía emails de confirmación."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "producto_reclamado": {"type": "string", "description": "Producto con el problema."},
                    "descripcion_problema": {"type": "string", "description": "Resumen del problema."},
                    "diagnostico_previo": {"type": "string", "description": "Resumen de la indagación técnica."},
                    "correo_cliente": {"type": "string", "description": "Email del cliente para constancia."},
                    "evidencia": {"type": "string", "description": "Evidencia: lote, foto, etc. 'Pendiente' si no hay."},
                },
                "required": ["producto_reclamado", "descripcion_problema", "diagnostico_previo", "correo_cliente"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirmar_pedido_y_generar_pdf",
            "description": (
                "Genera PDF de pedido/cotización cuando el cliente acepta. "
                "Solo incluir productos con referencia CONFIRMADA por consultar_inventario. "
                "Las referencias y descripciones deben ser EXACTAS del inventario. "
                "OBLIGATORIO incluir resumen_asesoria con el contexto de la conversación. "
                "Antes de llamar esta herramienta, verifica que el sistema quede completo con catalizadores, thinneres, herramientas y nota de color si aplica. "
                "IMPORTANTE: Esta herramienta ENVÍA el PDF directamente al cliente por WhatsApp. "
                "Después de llamarla, solo escribe una confirmación breve (ej: 'Listo, te envié el PDF'). "
                "NO repitas la cotización, NO vuelvas a listar los productos, NO llames esta herramienta dos veces."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo_documento": {"type": "string", "enum": ["cotizacion", "pedido"], "description": "Tipo de documento: 'cotizacion' si el cliente pidió cotización, 'pedido' si confirmó el pedido."},
                    "nombre_despacho": {"type": "string", "description": "Nombre EXACTO que el cliente dio en la conversación. NO cambiarlo por otro nombre."},
                    "canal_envio": {"type": "string", "enum": ["whatsapp", "email"], "description": "Canal de envío del PDF."},
                    "correo_cliente": {"type": "string", "description": "Email (solo si canal_envio='email')."},
                    "resumen_asesoria": {"type": "string", "description": "Resumen de 2-3 oraciones: qué preguntó el cliente, qué se diagnosticó, qué sistema se recomendó y por qué es la mejor opción. Si hubo cambio de sistema, explica la superioridad técnica/comercial. Queda como sustento en el PDF."},
                    "items_pedido": {
                        "type": "array",
                        "description": "Productos del pedido con referencia exacta del inventario. Incluye también complementarios obligatorios del sistema ya confirmados en inventario.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "referencia": {"type": "string", "description": "Código EXACTO del inventario."},
                                "descripcion_comercial": {"type": "string", "description": "Nombre EXACTO del inventario."},
                                "cantidad": {"type": "number", "description": "Cantidad solicitada."},
                                "unidad_medida": {"type": "string", "description": "'galón', 'cuñete', 'cuarto', 'unidad', etc."},
                            },
                            "required": ["referencia", "descripcion_comercial", "cantidad"],
                        },
                    },
                },
                "required": ["tipo_documento", "nombre_despacho", "canal_envio", "items_pedido"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_cliente_nuevo",
            "description": (
                "Registra un cliente nuevo que no existe en la base de datos. "
                "Usar cuando verificar_identidad devolvió 'verificado: false' o cuando necesitas dejar validado un cliente nuevo. "
                "Si es cotización, nombre + cédula/NIT son suficientes. Si es pedido, además exige dirección y ciudad. "
                "Siempre vincula el teléfono actual de WhatsApp al cliente validado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "modo_registro": {"type": "string", "enum": ["cotizacion", "pedido"], "description": "Usa 'cotizacion' para alta ligera con nombre + cédula/NIT. Usa 'pedido' cuando además ya tienes dirección y ciudad de entrega."},
                    "nombre_completo": {"type": "string", "description": "Nombre completo del cliente."},
                    "cedula_nit": {"type": "string", "description": "Cédula o NIT."},
                    "direccion_entrega": {"type": "string", "description": "Dirección completa. Obligatoria solo si modo_registro='pedido'."},
                    "ciudad": {"type": "string", "description": "Ciudad de entrega. Obligatoria solo si modo_registro='pedido'."},
                    "email": {"type": "string", "description": "Email (opcional)."},
                    "telefono": {"type": "string", "description": "Teléfono (se toma del WhatsApp si no se da)."},
                },
                "required": ["modo_registro", "nombre_completo", "cedula_nit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "guardar_aprendizaje_producto",
            "description": "Guarda asociación entre jerga/código del cliente y producto real confirmado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "termino_cliente": {"type": "string", "description": "Lo que dijo el cliente."},
                    "producto_referencia": {"type": "string", "description": "Referencia real del producto."},
                    "producto_descripcion": {"type": "string", "description": "Nombre real del producto."},
                },
                "required": ["termino_cliente", "producto_referencia", "producto_descripcion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "guardar_producto_complementario",
            "description": "Guarda relación complementaria entre productos (catalizador, diluyente, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "producto_referencia": {"type": "string", "description": "Referencia del producto principal."},
                    "companion_referencia": {"type": "string", "description": "Referencia del complementario."},
                    "tipo_relacion": {
                        "type": "string",
                        "enum": ["catalizador", "diluyente", "base", "complemento", "sellador", "imprimante", "acabado"],
                        "description": "Tipo de relación.",
                    },
                },
                "required": ["producto_referencia", "companion_referencia", "tipo_relacion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_conocimiento_experto",
            "description": (
                "Guarda conocimiento experto de Diego García, único asesor autorizado para enseñar. "
                "Usar cuando detectes señal ENSEÑAR, ANOTA ESTO, GUARDA ESTO, APRENDE ESTO. "
                "IMPORTANTE: Extrae TODOS los campos del mensaje del experto. "
                "Si el experto dice 'Para tanque de agua potable usa Aquablock, "
                "nunca Interseal' → contexto_tags='tanque agua potable', "
                "producto_recomendado='Aquablock', producto_desestimado='Interseal', "
                "nota_comercial='Para tanque de agua potable siempre recomendar Aquablock. "
                "Interseal no es apto para contacto con agua potable.', tipo='evitar'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contexto_tags": {
                        "type": "string",
                        "description": (
                            "Superficie, aplicación o situación donde aplica esta regla. "
                            "Combina superficie + condición + contexto. Separado por comas si hay múltiples. "
                            "Ej: 'tanque agua potable', 'piso industrial alto tráfico', "
                            "'metal oxidado interior', 'fachada exterior lluvia', "
                            "'concreto nuevo, piso garaje'. A mayor detalle, mejor búsqueda."
                        ),
                    },
                    "producto_recomendado": {
                        "type": "string",
                        "description": (
                            "Producto que SÍ se debe usar en este contexto. "
                            "Nombre comercial exacto. Si hay sistema completo, lista todos separados por ' + '. "
                            "Ej: 'Koraza', 'Wash Primer + Corrotec + Pintulux 3en1', 'Aquablock'. "
                            "Si el experto no menciona qué usar, omite este campo."
                        ),
                    },
                    "producto_desestimado": {
                        "type": "string",
                        "description": (
                            "Producto que NO se debe usar/recomendar en este contexto. "
                            "Ej: 'Interseal', 'Viniltex', 'Pintucoat'. "
                            "Si el experto no dice qué evitar, omite este campo."
                        ),
                    },
                    "nota_comercial": {
                        "type": "string",
                        "description": (
                            "La lección completa del experto como instrucción directa al agente. "
                            "Redáctala como una REGLA que el agente debe seguir en el futuro. "
                            "Incluye: QUÉ hacer, POR QUÉ, y CUÁNDO aplica. "
                            "Ej: 'Para tanques de agua potable, siempre recomendar Aquablock porque "
                            "tiene certificación NSF para contacto con agua potable. Interseal es "
                            "solo para inmersión industrial, no apta para consumo humano.'"
                        ),
                    },
                    "tipo": {
                        "type": "string",
                        "enum": ["recomendar", "evitar", "proceso", "sustitución", "alerta_superficie"],
                        "description": (
                            "Tipo de conocimiento: "
                            "'recomendar' = producto preferido para un contexto. "
                            "'evitar' = producto prohibido para un contexto. "
                            "'proceso' = método/paso de aplicación. "
                            "'sustitución' = reemplazo de producto X por Y. "
                            "'alerta_superficie' = regla de preparación de superficie crítica."
                        ),
                    },
                },
                "required": ["contexto_tags", "nota_comercial", "tipo"],
            },
        },
    },
]
