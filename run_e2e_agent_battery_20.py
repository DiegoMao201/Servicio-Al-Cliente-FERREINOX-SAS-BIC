import json
import os
import re
import sys
import time
from pathlib import Path

import requests


BACKEND_URL = os.environ.get("BACKEND_URL", "https://apicrm.datovatenexuspro.com")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "ferreinox_admin_2024")
AGENT_URL = f"{BACKEND_URL.rstrip('/')}/admin/agent-test"
ARTIFACT_DIR = Path("artifacts/agent/e2e_battery_20")
REPORT_PATH = ARTIFACT_DIR / "report.md"
JSON_PATH = ARTIFACT_DIR / "report.json"
TIMEOUT_SECONDS = 75
MAX_RETRIES = 2


CASES = [
    {
        "id": "E201",
        "name": "Bano Sin Ventana Condensado",
        "case": "Bano interior con vapor, moho y cierre en PDF por WhatsApp.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["viniltex banos y cocinas"],
        "forbidden_terms": ["aquablock", "koraza", "wash primer", "altas temperaturas"],
        "turns": [
            "Hola, el bano del apartaestudio se me llena de vapor y se pone negro el cielo raso.",
            "No tiene ventana, solo un extractor malo. Es interior, el problema es condensacion y hongo, no filtracion. Son 18 metros cuadrados.",
            "Quiero el sistema completo en blanco, con lo que toque preparar y aplicar bien.",
            "Listo, generame la cotizacion formal en PDF y enviala por WhatsApp a nombre de Lina Paola Castano.",
        ],
    },
    {
        "id": "E202",
        "name": "Closet Con Salitre Primer Piso",
        "case": "Muro interior con capilaridad y cierre comercial completo.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["aquablock", "viniltex"],
        "forbidden_terms": ["koraza", "pintuco fill", "wash primer"],
        "turns": [
            "Buenas, detras del closet del primer piso la pared se esta soplando y sale polvillo blanco desde abajo.",
            "Es interior, el dano arranca pegado al piso y ya saco salitre. No es lluvia por fachada. Son 24 metros cuadrados.",
            "Si, quiero el sistema completo para resolverlo bien, no maquillarlo.",
            "Perfecto, armame la cotizacion formal en PDF y mandamela por WhatsApp a nombre de Daniela Hoyos.",
        ],
    },
    {
        "id": "E203",
        "name": "Culata Lluvia Lateral",
        "case": "Fachada exterior con microfisuras y agua de lluvia lateral.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["pintuco fill", "koraza"],
        "forbidden_terms": ["aquablock", "viniltex"],
        "turns": [
            "Hola, la culata del edificio se me pela cada invierno y se marca toda cuando le pega la lluvia de lado.",
            "Es exterior, en revoque firme, con microfisuras finas y 62 metros cuadrados. No viene humedad desde abajo.",
            "Quiero la ruta completa, no solo la pintura final.",
            "Dale, genera la cotizacion formal en PDF y enviala por WhatsApp a nombre de Edificio Monteverde 2.",
        ],
    },
    {
        "id": "E204",
        "name": "Fibrocemento Tizado Campestre",
        "case": "Cubierta de fibrocemento vieja, tizada y con cierre comercial.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["sellomax", "koraza"],
        "forbidden_terms": ["aquablock", "viniltex", "wash primer"],
        "turns": [
            "Buenas, tengo una cubierta de fibrocemento de una finca que ya esta toda tizosa y triste.",
            "Es exterior total, ya tenia pintura vieja y el acabado esta polvoso. Son 96 metros cuadrados.",
            "Necesito el sistema completo para recuperarla y que quede blanca otra vez.",
            "Hazme el PDF de cotizacion y mandalo por WhatsApp a nombre de Parcelacion Altos de Lisboa.",
        ],
    },
    {
        "id": "E205",
        "name": "Ladrillo Vista Restaurante",
        "case": "Ladrillo a la vista ahumado por cocina y lluvia, sin querer pintarlo.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["construcleaner", "siliconite"],
        "forbidden_terms": ["koraza", "viniltex", "aquablock"],
        "turns": [
            "Hola, la fachada en ladrillo a la vista del restaurante se puso negra por humo y agua.",
            "No la quiero pintar. Quiero limpiarla, conservar el ladrillo natural y dejarla protegida. Son 110 metros cuadrados.",
            "Listo, cotizame el sistema completo con lo necesario para aplicarlo bien.",
            "Genera el PDF y envialo por WhatsApp a nombre de Brasa Urbana SAS.",
        ],
    },
    {
        "id": "E206",
        "name": "Reja Calle Oxido Viejo",
        "case": "Reja exterior con oxido avanzado y acabado negro.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["pintoxido", "corrotec"],
        "forbidden_terms": ["wash primer", "koraza", "viniltex"],
        "turns": [
            "Buenas, necesito recuperar una reja que da a la calle y ya tiene oxido por varios lados.",
            "Es hierro viejo en exterior total, el oxido ya esta activo y la quiero terminar en negro. Son 28 metros cuadrados.",
            "Si, quiero el sistema completo y bien planteado.",
            "Arma el PDF de cotizacion y mandalo por WhatsApp a nombre de Edificio Mirador del Lago.",
        ],
    },
    {
        "id": "E207",
        "name": "Tuberia Galvanizada Nueva",
        "case": "Tuberia galvanizada nueva a la vista, sin oxido, para validar el flujo correcto.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["wash primer", "corrotec"],
        "forbidden_terms": ["altas temperaturas", "pintoxido", "viniltex"],
        "turns": [
            "Hola, voy a pintar una tuberia galvanizada nueva que va expuesta en la fachada.",
            "Es exterior, material nuevo sin oxido y luego la quiero terminar blanca. Son 16 metros cuadrados.",
            "Necesito el sistema correcto completo para que no se pele.",
            "Genera la cotizacion formal en PDF y mandala por WhatsApp a nombre de Conjunto Arrayanes Park.",
        ],
    },
    {
        "id": "E208",
        "name": "Ducto Horno Panaderia",
        "case": "Ducto metalico caliente con necesidad de pintura de altas temperaturas.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["altas temperaturas"],
        "forbidden_terms": ["wash primer", "viniltex", "aquablock"],
        "turns": [
            "Buenas, necesito pintar un ducto metalico que trabaja caliente en una panaderia.",
            "Le llega bastante temperatura cerca a la salida del horno, esta en exterior parcial y tiene oxido leve. Son 12 metros cuadrados.",
            "Quiero hacerlo bien desde el inicio y con sistema completo.",
            "Listo, genera el PDF y envialo por WhatsApp a nombre de Panaderia La Hornada.",
        ],
    },
    {
        "id": "E209",
        "name": "Deck Madera Campestre",
        "case": "Deck de madera exterior con desgaste por lluvia y sol.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["barnex", "wood stain"],
        "forbidden_terms": ["koraza", "viniltex", "aquablock"],
        "turns": [
            "Hola, necesito renovar un deck de madera exterior de una casa campestre.",
            "Le pega sol y lluvia, tiene acabado viejo gastado y quiero que siga viendose la veta. Son 42 metros cuadrados.",
            "Quiero el sistema durable, no una salida barata.",
            "Genera la cotizacion en PDF y mandala por WhatsApp a nombre de Finca La Serranita.",
        ],
    },
    {
        "id": "E210",
        "name": "Puerta Interior Blanca",
        "case": "Puerta de madera interior para dejar blanca satinada sin mandarla a exterior.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["pintulux", "esmalte domestico"],
        "forbidden_terms": ["barnex", "koraza", "wash primer"],
        "turns": [
            "Buenas, quiero repintar una puerta de madera interior que hoy esta envejecida.",
            "Es interior seco, la quiero blanca satinada y son unos 9 metros cuadrados contando marcos.",
            "Si, quiero el sistema completo para prepararla y acabarla bien.",
            "Hazme la cotizacion formal en PDF y mandamela por WhatsApp a nombre de Paula Andrea Jaramillo.",
        ],
    },
    {
        "id": "E211",
        "name": "Cancha Escolar Azul",
        "case": "Cancha multiple escolar con demarcacion y cierre en PDF.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["pintura canchas"],
        "forbidden_terms": ["pintucoat", "intergard", "koraza", "aquablock"],
        "turns": [
            "Hola, necesito repintar una cancha multiple de colegio porque ya se borraron las lineas.",
            "Es placa de concreto exterior, uso peatonal y deportivo, nada de montacargas. Son 620 metros cuadrados y la quieren azul.",
            "Listo, armame la cotizacion completa con demarcaciones.",
            "Genera el PDF y envialo por WhatsApp a nombre de Colegio Senderos del Saber.",
        ],
    },
    {
        "id": "E212",
        "name": "Drywall Apartamento Nuevo",
        "case": "Apartamento nuevo en drywall con resanes y deseo de acabado lavable.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["viniltex"],
        "forbidden_terms": ["koraza", "aquablock", "wash primer"],
        "turns": [
            "Buenas, me entregaron un apartamento nuevo y el drywall quedo con varios resanes y diferencias.",
            "Es interior seco, paredes nuevas, 64 metros cuadrados, y quiero un acabado lavable mate.",
            "Cotizame el sistema completo, incluyendo preparacion si hace falta.",
            "Genera el PDF y envialo por WhatsApp a nombre de Sara Bedoya.",
        ],
    },
    {
        "id": "E213",
        "name": "Fachada Cambio De Color",
        "case": "Fachada exterior donde el cliente cambia color en el cierre y debe revalidarse inventario.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "min_inventory_calls": 2,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["koraza"],
        "forbidden_terms": ["aquablock", "viniltex"],
        "turns": [
            "Hola, la fachada lateral del edificio se esta pelando por sol y lluvia y ya quiero arreglarla.",
            "Es exterior, en revoque firme, 78 metros cuadrados y sin humedad que venga desde abajo.",
            "Primero cotizala en blanco para ver por donde va el sistema.",
            "Mejor cambiala a un tono arena o almendra si lo manejan y actualiza la cotizacion.",
            "Ahora si, genera el PDF final y envialo por WhatsApp a nombre de Edificio Altos del Parque.",
        ],
    },
    {
        "id": "E214",
        "name": "Porton Viejo Con Herramientas",
        "case": "Porton oxidado con solicitud explicita de incluir preparacion y herramientas.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "min_quote_items": 2,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["pintoxido", "corrotec"],
        "forbidden_terms": ["wash primer", "interseal", "viniltex"],
        "turns": [
            "Buenas, un porton viejo de hierro tiene capas levantadas y oxido por debajo.",
            "Es exterior, son 30 metros cuadrados, lo vamos a dejar negro mate y quiero hacer bien la preparacion.",
            "Incluye removedor, lijas y brochas si aplica. Quiero la cotizacion completa.",
            "Perfecto, generame el PDF y mandalo por WhatsApp a nombre de Talleres JF Metal.",
        ],
    },
    {
        "id": "E215",
        "name": "Piscina Concreto Gap",
        "case": "Caso de gap del portafolio donde no deberia cerrar cotizacion ni PDF.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": False,
        "should_quote": False,
        "should_pdf": False,
        "expected_terms": [],
        "forbidden_terms": ["koraza", "viniltex", "pintuco fill", "aquablock"],
        "turns": [
            "Hola, necesito un sistema para pintar una piscina de concreto con cloro y agua permanente.",
            "Es por dentro, contacto permanente con agua y el vaso tiene 52 metros cuadrados.",
            "Si ustedes no manejan algo realmente apto prefiero que me lo digas claro y no me cotices por salir del paso.",
        ],
    },
    {
        "id": "E216",
        "name": "Tanque Potable Sumergido",
        "case": "Caso especializado de contacto con agua potable, sin forzar cotizacion.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": False,
        "should_quote": False,
        "should_pdf": False,
        "expected_terms": [],
        "forbidden_terms": [],
        "turns": [
            "Buenas, necesito pintar por dentro un tanque metalico de agua potable.",
            "Va sumergido, en contacto directo con agua para consumo humano y son 30 metros cuadrados.",
            "Si eso no se puede manejar de forma segura, no me armes cotizacion falsa.",
        ],
    },
    {
        "id": "E217",
        "name": "Diagnostico Incompleto Bloqueado",
        "case": "El agente no debe saltar a productos si el cliente no entrega datos criticos.",
        "require_initial_diagnostic": True,
        "must_call_technical": False,
        "must_call_inventory": False,
        "should_quote": False,
        "should_pdf": False,
        "expected_terms": [],
        "forbidden_terms": ["koraza", "viniltex", "aquablock", "corrotec", "wash primer"],
        "turns": [
            "Hola, necesito pintar una cosa que se me dano horrible.",
            "Todavia no se si es interior o exterior, ni el material. Solo dime de una vez que comprar.",
        ],
    },
    {
        "id": "E218",
        "name": "Solo Asesoria Sin Cotizar",
        "case": "El agente debe diagnosticar y recomendar, pero respetar que el cliente no quiere cotizacion.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": False,
        "should_quote": False,
        "should_pdf": False,
        "expected_terms": ["koraza"],
        "forbidden_terms": ["aquablock"],
        "turns": [
            "Buenas, la fachada lateral del edificio se esta pelando por sol y lluvia.",
            "Es exterior, 55 metros cuadrados, no hay salitre desde abajo, solo desgaste y microfisura superficial.",
            "Solo dame la ruta correcta y los productos. No necesito cotizacion ni PDF por ahora.",
        ],
    },
    {
        "id": "E219",
        "name": "Terraza PDF Por Correo",
        "case": "Impermeabilizacion de terraza con entrega final por correo.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "email",
        "expected_terms": ["pintuco fill"],
        "forbidden_terms": ["aquablock", "viniltex"],
        "turns": [
            "Hola, tengo una terraza transitable que cuando llueve moja el cuarto de abajo.",
            "Es una placa de concreto ya pintada hace anos, con fisuras finas y 44 metros cuadrados.",
            "Quiero la ruta correcta y la cotizacion completa para impermeabilizarla.",
            "Genera el PDF y envialo al correo compras.terraza@obraejemplo.com a nombre de Jorge Ivan Ramirez.",
        ],
    },
    {
        "id": "E220",
        "name": "Estructura Interior Bajo Techo",
        "case": "Metal interior nuevo bajo techo con presupuesto medio, evitando sobreindustrializar.",
        "require_initial_diagnostic": True,
        "must_call_technical": True,
        "must_call_inventory": True,
        "should_quote": True,
        "should_pdf": True,
        "expected_pdf_channel": "whatsapp",
        "expected_terms": ["corrotec", "pintulux"],
        "forbidden_terms": ["interseal", "intergard", "interthane"],
        "turns": [
            "Buenas, voy a pintar una estructura metalica interior de un local nuevo.",
            "Es acero nuevo bajo techo, cero humedad, 24 metros cuadrados, acabado negro y presupuesto medio.",
            "Quiero el sistema correcto sin meter epoxicos innecesarios.",
            "Listo, genera la cotizacion formal en PDF y mandala por WhatsApp a nombre de Bodega Nexo Interior.",
        ],
    },
]


def normalize_text(value: str) -> str:
    value = (value or "").lower()
    value = value.replace("ñ", "n")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def ensure_dirs() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def parse_jsonish(value):
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not value:
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def response_has_question(response_text: str) -> bool:
    lowered = (response_text or "").lower()
    return "?" in response_text or lowered.startswith("cual") or lowered.startswith("que ") or lowered.startswith("donde")


def extract_quote_items(conversation_context: dict) -> list[dict]:
    draft = conversation_context.get("commercial_draft") or {}
    items = []
    for item in draft.get("items") or []:
        if item.get("status") != "matched":
            continue
        matched_product = item.get("matched_product") or {}
        items.append(
            {
                "descripcion": item.get("descripcion_comercial") or matched_product.get("descripcion") or matched_product.get("nombre_articulo") or item.get("original_text") or "Producto",
                "referencia": item.get("referencia") or matched_product.get("referencia") or matched_product.get("codigo_articulo") or "",
                "cantidad": item.get("cantidad") or (item.get("product_request") or {}).get("requested_quantity") or 1,
                "unidad": item.get("unidad_medida") or (item.get("product_request") or {}).get("requested_unit") or "unidad",
                "source": item.get("source") or "manual",
            }
        )
    return items


def flatten_tool_text(tool_calls: list[dict]) -> str:
    parts = []
    for tool_call in tool_calls or []:
        parts.append(json.dumps(tool_call.get("args") or {}, ensure_ascii=False))
        parsed = parse_jsonish(tool_call.get("result"))
        if isinstance(parsed, (dict, list)):
            parts.append(json.dumps(parsed, ensure_ascii=False))
        elif parsed:
            parts.append(str(parsed))
    return "\n".join(parts)


def detect_terms(terms: list[str], text: str) -> list[str]:
    normalized_text = normalize_text(text)
    hits = []
    for term in terms:
        if normalize_text(term) and normalize_text(term) in normalized_text:
            hits.append(term)
    return hits


def extract_pdf_signals(turn_details: list[dict], conversation_context: dict) -> dict:
    pdf_signal = {
        "called": False,
        "success": False,
        "channel": None,
        "archivo": None,
        "mensaje": None,
        "order_id": None,
        "draft_pdf_id": ((conversation_context.get("commercial_draft") or {}).get("pdf_id") if isinstance(conversation_context.get("commercial_draft"), dict) else None),
    }
    for turn in turn_details:
        for tool_call in turn.get("tool_calls", []):
            if tool_call.get("name") != "confirmar_pedido_y_generar_pdf":
                continue
            pdf_signal["called"] = True
            parsed = parse_jsonish(tool_call.get("result"))
            if isinstance(parsed, dict):
                pdf_signal["success"] = bool(parsed.get("exito"))
                pdf_signal["channel"] = parsed.get("canal")
                pdf_signal["archivo"] = parsed.get("archivo") or parsed.get("archivo_pdf")
                pdf_signal["mensaje"] = parsed.get("mensaje")
                pdf_signal["order_id"] = parsed.get("order_id")
    if pdf_signal["draft_pdf_id"]:
        pdf_signal["success"] = True
    return pdf_signal


def detect_iva_double(response_text: str) -> bool:
    lowered = (response_text or "").lower()
    return "subtotal" in lowered and ("iva 19" in lowered or "iva (19" in lowered)


def build_case_terms(case: dict) -> list[str]:
    terms = []
    for key in ("expected_terms", "forbidden_terms"):
        for term in case.get(key, []):
            if term not in terms:
                terms.append(term)
    return terms


def agent_request(payload: dict) -> tuple[dict, int]:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        started = time.time()
        try:
            response = requests.post(
                AGENT_URL,
                headers={"x-admin-key": ADMIN_KEY, "Content-Type": "application/json"},
                json=payload,
                timeout=TIMEOUT_SECONDS,
            )
            elapsed_ms = int((time.time() - started) * 1000)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(f"Backend sin ok=true: {json.dumps(data, ensure_ascii=False)}")
            return data.get("result") or {}, elapsed_ms
        except Exception as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                raise

    raise last_error or RuntimeError("No se pudo completar la solicitud al agente")


def summarize_case(case: dict, turn_details: list[dict], conversation_context: dict) -> dict:
    errors = []
    warnings = []
    all_tools = []
    tool_text_parts = []
    all_responses = []
    inventory_calls = 0
    technical_calls = 0

    for turn in turn_details:
        all_responses.append(turn.get("response_text") or "")
        for tool_name in turn.get("tools", []):
            if tool_name not in all_tools:
                all_tools.append(tool_name)
            if tool_name in {"consultar_inventario", "consultar_inventario_lote"}:
                inventory_calls += 1
            if tool_name == "consultar_conocimiento_tecnico":
                technical_calls += 1
        tool_text_parts.append(flatten_tool_text(turn.get("tool_calls") or []))

    quote_items = extract_quote_items(conversation_context)
    final_turn = turn_details[-1] if turn_details else {}
    final_response = final_turn.get("response_text") or ""
    final_text = "\n".join(all_responses + [item["descripcion"] for item in quote_items])
    tool_text = "\n".join(tool_text_parts + [json.dumps(quote_items, ensure_ascii=False)])
    case_terms = build_case_terms(case)
    final_detected_terms = detect_terms(case_terms, final_text)
    supported_terms = detect_terms(case_terms, tool_text)
    unsupported_terms = [term for term in final_detected_terms if term not in supported_terms]
    expected_hits = detect_terms(case.get("expected_terms", []), final_text)
    forbidden_hits = detect_terms(case.get("forbidden_terms", []), final_text)
    draft = conversation_context.get("commercial_draft") or {}
    draft_ready = bool(draft.get("ready_to_close"))
    pdf_signal = extract_pdf_signals(turn_details, conversation_context)

    if any(turn.get("battery_error") for turn in turn_details):
        errors.append("La conversacion tuvo un error de bateria o timeout.")

    if case.get("require_initial_diagnostic") and turn_details:
        first_turn = turn_details[0]
        if not response_has_question(first_turn.get("response_text") or ""):
            errors.append("El primer turno no hizo pregunta diagnostica clara.")
        first_turn_tools = set(first_turn.get("tools") or [])
        if first_turn_tools.intersection({"consultar_conocimiento_tecnico", "consultar_inventario", "consultar_inventario_lote", "confirmar_pedido_y_generar_pdf"}):
            errors.append("El agente salto a herramientas antes de completar diagnostico inicial.")

    if case.get("must_call_technical") and technical_calls == 0:
        errors.append("Nunca llamo consultar_conocimiento_tecnico.")

    if case.get("must_call_inventory") and inventory_calls == 0:
        errors.append("Nunca llamo consultar_inventario ni consultar_inventario_lote.")

    if case.get("min_inventory_calls") and inventory_calls < case["min_inventory_calls"]:
        errors.append(f"Se esperaban al menos {case['min_inventory_calls']} llamadas de inventario y solo hubo {inventory_calls}.")

    if forbidden_hits:
        errors.append(f"Aparecieron terminos prohibidos en la respuesta o draft: {', '.join(forbidden_hits)}.")

    if unsupported_terms:
        errors.append(f"Aparecieron terminos auditados no respaldados por herramientas: {', '.join(unsupported_terms)}.")

    if case.get("expected_terms") and not expected_hits:
        errors.append(f"No aparecio ninguno de los terminos esperados: {', '.join(case['expected_terms'])}.")

    if case.get("should_quote"):
        minimum_quote_items = case.get("min_quote_items", 1)
        if len(quote_items) < minimum_quote_items and not draft_ready and not pdf_signal["called"]:
            errors.append("No quedo cotizacion estructurada suficiente en el draft.")
        if detect_iva_double(final_response):
            errors.append("La respuesta final mostro subtotal + IVA por separado.")
    else:
        if quote_items:
            errors.append("No se esperaba cotizacion, pero quedaron items en el draft comercial.")
        if pdf_signal["called"] or pdf_signal["draft_pdf_id"]:
            errors.append("No se esperaba PDF, pero el flujo genero o intento generar uno.")

    if case.get("should_pdf"):
        if not pdf_signal["called"] and not pdf_signal["draft_pdf_id"]:
            errors.append("No se llamo confirmar_pedido_y_generar_pdf ni quedo pdf_id en el draft.")
        if not pdf_signal["success"]:
            errors.append("El flujo de PDF no quedo marcado como exitoso.")
        expected_channel = case.get("expected_pdf_channel")
        if expected_channel and pdf_signal.get("channel") and pdf_signal["channel"] != expected_channel:
            errors.append(f"El PDF salio por canal {pdf_signal['channel']} y se esperaba {expected_channel}.")
        if not pdf_signal.get("archivo") and not pdf_signal.get("draft_pdf_id"):
            warnings.append("No se capturo nombre de archivo PDF en el resultado de herramienta.")

    if technical_calls and inventory_calls:
        first_tech_index = next((idx for idx, turn in enumerate(turn_details, start=1) if "consultar_conocimiento_tecnico" in turn.get("tools", [])), None)
        first_inv_index = next((idx for idx, turn in enumerate(turn_details, start=1) if set(turn.get("tools", [])).intersection({"consultar_inventario", "consultar_inventario_lote"})), None)
        if first_inv_index is not None and first_tech_index is not None and first_inv_index < first_tech_index:
            warnings.append("Inventario ocurrio antes de la consulta tecnica; revisar si el flujo quedo demasiado comercial.")

    status = "FAIL" if errors else ("WARN" if warnings else "PASS")

    return {
        "id": case["id"],
        "name": case["name"],
        "case": case["case"],
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "tools_used": all_tools,
        "technical_calls": technical_calls,
        "inventory_calls": inventory_calls,
        "expected_hits": expected_hits,
        "forbidden_hits": forbidden_hits,
        "unsupported_terms": unsupported_terms,
        "quote_items": quote_items,
        "quote_ready": draft_ready,
        "pdf": pdf_signal,
        "final_response": final_response,
        "turns": turn_details,
        "conversation_context": conversation_context,
    }


def render_markdown(results: list[dict]) -> str:
    lines = [
        "# Bateria E2E Agente Ferreinox (20 casos)",
        "",
        f"- Endpoint evaluado: {AGENT_URL}",
        f"- Casos: {len(results)}",
        f"- PASS: {sum(1 for item in results if item['status'] == 'PASS')}",
        f"- WARN: {sum(1 for item in results if item['status'] == 'WARN')}",
        f"- FAIL: {sum(1 for item in results if item['status'] == 'FAIL')}",
        f"- Artefactos por turno: {ARTIFACT_DIR}",
        "",
        "## Resumen Ejecutivo",
        "",
    ]

    for item in results:
        lines.append(
            f"- {item['id']} | {item['status']} | {item['name']} | tools: {', '.join(item['tools_used']) or 'ninguna'} | draft_items: {len(item['quote_items'])} | pdf: {'si' if item['pdf']['success'] else 'no'}"
        )

    lines.append("")
    lines.append("## Detalle Por Caso")
    lines.append("")

    for item in results:
        lines.append(f"### {item['id']} - {item['name']}")
        lines.append("")
        lines.append(f"- Estado: {item['status']}")
        lines.append(f"- Caso: {item['case']}")
        lines.append(f"- Herramientas usadas: {', '.join(item['tools_used']) or 'ninguna'}")
        lines.append(f"- Llamadas tecnicas: {item['technical_calls']} | llamadas inventario: {item['inventory_calls']}")
        lines.append(f"- Productos esperados encontrados: {', '.join(item['expected_hits']) or 'ninguno'}")
        lines.append(f"- Productos prohibidos encontrados: {', '.join(item['forbidden_hits']) or 'ninguno'}")
        lines.append(f"- Terminos no respaldados: {', '.join(item['unsupported_terms']) or 'ninguno'}")
        lines.append(f"- Draft listo para cerrar: {'si' if item['quote_ready'] else 'no'}")
        lines.append(f"- Items en draft: {len(item['quote_items'])}")
        lines.append(
            f"- PDF: llamado={'si' if item['pdf']['called'] else 'no'}, exito={'si' if item['pdf']['success'] else 'no'}, canal={item['pdf'].get('channel') or 'n/a'}, archivo={item['pdf'].get('archivo') or item['pdf'].get('draft_pdf_id') or 'n/a'}"
        )
        if item["errors"]:
            lines.append("- Errores:")
            for error in item["errors"]:
                lines.append(f"  - {error}")
        if item["warnings"]:
            lines.append("- Advertencias:")
            for warning in item["warnings"]:
                lines.append(f"  - {warning}")
        lines.append("")
        lines.append("#### Log Resumido")
        lines.append("")
        for turn in item["turns"]:
            lines.append(f"- Turno {turn['turn_index']} usuario: {turn['user_message']}")
            lines.append(f"- Turno {turn['turn_index']} tools: {', '.join(turn['tools']) or 'ninguna'}")
            lines.append(f"- Turno {turn['turn_index']} respuesta: {(turn['response_text'] or '').replace(chr(10), ' ')}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    ensure_dirs()
    results = []

    for index, case in enumerate(CASES, start=1):
        print(f"[{index}/{len(CASES)}] {case['id']} - {case['name']}", flush=True)
        conversation_context = {}
        recent_messages = []
        context = {
            "conversation_id": 240000 + index,
            "contact_id": 240000 + index,
            "cliente_id": None,
            "telefono_e164": "+573001234567",
            "nombre_visible": "Bateria E2E 20",
        }
        turn_details = []

        for turn_index, user_message in enumerate(case["turns"], start=1):
            try:
                result, elapsed_ms = agent_request(
                    {
                        "profile_name": "Bateria E2E 20",
                        "conversation_context": conversation_context,
                        "recent_messages": recent_messages,
                        "user_message": user_message,
                        "context": context,
                    }
                )
            except Exception as exc:
                elapsed_ms = 0
                result = {
                    "response_text": f"ERROR EN BATERIA: {exc}",
                    "tool_calls": [],
                    "context_updates": {},
                    "battery_error": str(exc),
                }
                print(f"  turno {turn_index}: ERROR {exc}", flush=True)
            else:
                print(f"  turno {turn_index}: {elapsed_ms}ms", flush=True)

            response_text = result.get("response_text", "")
            tool_calls = result.get("tool_calls", [])
            tools = [tool_call.get("name") for tool_call in tool_calls if tool_call.get("name")]
            context_updates = result.get("context_updates") or {}
            for key, value in context_updates.items():
                if value is not None:
                    conversation_context[key] = value

            recent_messages.append({"direction": "inbound", "contenido": user_message, "message_type": "text"})
            recent_messages.append({"direction": "outbound", "contenido": response_text, "message_type": "text"})

            artifact_payload = {
                "case_id": case["id"],
                "case_name": case["name"],
                "turn_index": turn_index,
                "elapsed_ms": elapsed_ms,
                "user_message": user_message,
                "result": result,
                "conversation_context_after_turn": conversation_context,
                "parsed_tool_results": [parse_jsonish(tool_call.get("result")) for tool_call in tool_calls],
            }
            artifact_path = ARTIFACT_DIR / f"{case['id'].lower()}_turn_{turn_index:02d}.json"
            artifact_path.write_text(json.dumps(artifact_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

            turn_details.append(
                {
                    "turn_index": turn_index,
                    "elapsed_ms": elapsed_ms,
                    "user_message": user_message,
                    "response_text": response_text,
                    "tools": tools,
                    "tool_calls": tool_calls,
                    "battery_error": result.get("battery_error"),
                }
            )

            if result.get("battery_error"):
                break

        results.append(summarize_case(case, turn_details, conversation_context))

    REPORT_PATH.write_text(render_markdown(results), encoding="utf-8")
    JSON_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(
        json.dumps(
            {
                "report_path": str(REPORT_PATH),
                "json_path": str(JSON_PATH),
                "pass": sum(1 for item in results if item["status"] == "PASS"),
                "warn": sum(1 for item in results if item["status"] == "WARN"),
                "fail": sum(1 for item in results if item["status"] == "FAIL"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()