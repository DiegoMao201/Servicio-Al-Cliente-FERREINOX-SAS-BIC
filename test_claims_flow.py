"""
Test Flujo de Reclamaciones CRM Ferreinox
==========================================
Valida el flujo completo de reclamaciones en 3 niveles:

  PARTE 1 (sin BD): Emails con resumen estructurado, no conversación
  PARTE 2 (sin BD): Herramienta radicar_reclamo (duplicados, validación)
  PARTE 3 (con BD + OpenAI): Conversaciones multi-turno del flujo de 5 fases

Uso:
  .venv\\Scripts\\python.exe test_claims_flow.py
"""

import json
import os
import sys
import time
import re
import traceback
from unittest.mock import patch, MagicMock
from html import escape

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:x@localhost:5432/test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1: EMAILS DE RECLAMO — Resumen estructurado, NO conversación
# ══════════════════════════════════════════════════════════════════════════════

def test_email_reclamo_interno():
    """El email interno al área de calidad contiene resumen, NO la conversación."""
    from main import build_operational_email_payload

    detail = {
        "product_label": "Viniltex Blanco 5 Galones",
        "issue_summary": "La pintura no cubre, parece aguada, aplicó 3 manos y sigue transparente",
        "diagnostico_previo": "El cliente reporta que aplicó 3 manos de Viniltex Blanco sobre pared de estuco sin lijar ni sellar. "
                              "Según la ficha técnica, Viniltex requiere sellador previo sobre estuco poroso. "
                              "La falta de sellador causa absorción excesiva y baja cobertura. Sin embargo, el cliente "
                              "insiste en que ha usado Viniltex antes sin sellador y le funcionaba. Se radica para revisión de lote.",
        "evidence_note": "Foto enviada por WhatsApp. Lote: L2024-5891",
        "contact_email": "cliente@test.com",
        "case_reference": "CRM-12345",
        "store_name": "Cali",
    }

    # Simulamos recent_messages con conversación que NO debe aparecer en el email
    recent_messages = [
        {"direction": "inbound", "contenido": "Esa pintura me salió mala, parece agua"},
        {"direction": "outbound", "contenido": "Lamento escuchar eso. ¿Puedo preguntarle cómo preparó la superficie?"},
        {"direction": "inbound", "contenido": "No hice nada, pinté directo"},
        {"direction": "outbound", "contenido": "Para el Viniltex sobre estuco, la ficha técnica recomienda sellador previo..."},
        {"direction": "inbound", "contenido": "Pero yo siempre lo he usado así y funciona"},
        {"direction": "outbound", "contenido": "Entiendo. Voy a radicarte el reclamo para revisión de lote."},
    ]

    # Mock sendgrid config
    with patch("main.get_sendgrid_config", return_value={
        "from_email": "crm@ferreinox.com",
        "reclamos_to_email": "calidad@ferreinox.com",
    }):
        payload = build_operational_email_payload("reclamos", "Juan Pérez", None, detail, recent_messages)

    errors = []

    if payload is None:
        errors.append("Payload es None")
        return errors

    html = payload["html_content"]
    text = payload["text_content"]

    # DEBE contener: resumen estructurado
    must_contain = [
        "Viniltex Blanco 5 Galones",         # producto
        "no cubre",                            # problema
        "sellador previo",                     # diagnóstico
        "Lote: L2024-5891",                    # evidencia
        "CRM-12345",                           # referencia
        "Diagnóstico técnico",                 # sección de diagnóstico
    ]
    for keyword in must_contain:
        if keyword not in html and keyword not in text:
            errors.append(f"Email NO contiene '{keyword}'")

    # NO DEBE contener: mensajes de la conversación literal
    must_not_contain = [
        "Esa pintura me salió mala",           # mensaje del cliente
        "Lamento escuchar eso",                # mensaje del agente
        "No hice nada, pinté directo",         # mensaje del cliente
        "Pero yo siempre lo he usado así",     # mensaje del cliente
        "Historial reciente",                  # sección de historial
    ]
    for keyword in must_not_contain:
        if keyword in html or keyword in text:
            errors.append(f"Email CONTIENE conversación literal: '{keyword}'")

    # Verificar que el subject incluye el caso
    if "CRM-12345" not in payload["subject"]:
        errors.append("Subject no contiene referencia del caso")

    return errors


def test_email_confirmacion_cliente():
    """El email al cliente contiene resumen + diagnóstico, NO la conversación."""
    from main import build_customer_claim_confirmation_email

    detail = {
        "product_label": "Koraza Terracota Galón",
        "issue_summary": "Se descascara la pintura de la fachada a los 2 meses de pintar",
        "diagnostico_previo": "El cliente aplicó Koraza directamente sobre pintura antigua con polvo sin lijar ni aplicar wash primer. "
                              "La ficha técnica indica que sobre superficies previamente pintadas se debe lijar y aplicar sellador. "
                              "El cliente confirma que no preparó la superficie. Se radica igualmente por la cantidad de producto perdido.",
        "evidence_note": "Foto de la fachada descascarada. Sin número de lote disponible.",
        "contact_email": "maria@test.com",
        "case_reference": "CRM-67890",
        "store_name": "Bogotá",
    }

    payload = build_customer_claim_confirmation_email(12345, "María López", None, detail)

    errors = []

    if payload is None:
        errors.append("Payload es None")
        return errors

    html = payload["html_content"]
    text = payload["text_content"]

    # DEBE contener: resumen + diagnóstico
    must_contain = [
        "Koraza Terracota",                    # producto
        "descascara",                          # problema
        "Diagnóstico técnico",                 # sección
        "lijar",                               # del diagnóstico
        "CRM-67890",                           # referencia
    ]
    for keyword in must_contain:
        if keyword not in html and keyword not in text:
            errors.append(f"Email cliente NO contiene '{keyword}'")

    # Verificar que va al correo correcto
    if payload["to_email"] != "maria@test.com":
        errors.append(f"Email va a '{payload['to_email']}' en vez de 'maria@test.com'")

    return errors


def test_email_sin_correo_cliente():
    """Si no hay correo, build_customer_claim_confirmation_email retorna None."""
    from main import build_customer_claim_confirmation_email

    detail = {
        "product_label": "Test Producto",
        "issue_summary": "test",
        "contact_email": "",  # sin correo
    }

    payload = build_customer_claim_confirmation_email(1, "Test", None, detail)
    errors = []
    if payload is not None:
        errors.append("Debería retornar None sin correo cliente")
    return errors


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2: HERRAMIENTA radicar_reclamo — Validación y duplicados
# ══════════════════════════════════════════════════════════════════════════════

def test_radicar_reclamo_datos_incompletos():
    """Sin producto o descripción, debe rechazar."""
    from main import _handle_tool_radicar_reclamo

    context = {"conversation_id": 99999, "cliente_id": None, "nombre_visible": "Test"}
    conv_context = {}

    # Sin producto
    result = json.loads(_handle_tool_radicar_reclamo(
        {"producto_reclamado": "", "descripcion_problema": "se despegó", "diagnostico_previo": "test", "correo_cliente": "x@x.com"},
        context, conv_context
    ))
    errors = []
    if result.get("status") != "error":
        errors.append(f"Debería ser error sin producto, pero status='{result.get('status')}'")

    # Sin descripción
    result2 = json.loads(_handle_tool_radicar_reclamo(
        {"producto_reclamado": "Viniltex", "descripcion_problema": "", "diagnostico_previo": "test", "correo_cliente": "x@x.com"},
        context, conv_context
    ))
    if result2.get("status") != "error":
        errors.append(f"Debería ser error sin descripción, pero status='{result2.get('status')}'")

    return errors


def test_radicar_reclamo_duplicado():
    """Si ya se radicó el mismo producto, no debe duplicar."""
    from main import _handle_tool_radicar_reclamo

    context = {"conversation_id": 99998, "cliente_id": None, "nombre_visible": "Test"}
    conv_context = {
        "claim_case": {
            "submitted": True,
            "case_reference": "CRM-99998",
            "product_label": "Viniltex Blanco Galón",
            "issue_summary": "No cubre",
        }
    }

    result = json.loads(_handle_tool_radicar_reclamo(
        {
            "producto_reclamado": "Viniltex Blanco Galón",
            "descripcion_problema": "La pintura no cubre",
            "diagnostico_previo": "test",
            "correo_cliente": "x@x.com",
        },
        context, conv_context
    ))
    errors = []
    if result.get("status") != "ya_radicado":
        errors.append(f"Duplicado no detectado: status='{result.get('status')}'")
    if "CRM-99998" not in result.get("numero_caso", ""):
        errors.append("Duplicado no devolvió número de caso original")

    return errors


def test_radicar_reclamo_exitoso():
    """Radicación exitosa con todos los datos — verifica task y emails."""
    from main import _handle_tool_radicar_reclamo

    context = {"conversation_id": 99997, "cliente_id": 123, "nombre_visible": "Carlos Muñoz"}
    conv_context = {}

    # Mock las funciones que tocan BD y SendGrid
    with patch("main.upsert_agent_task") as mock_task, \
         patch("main.update_conversation_context") as mock_ctx, \
         patch("main.get_cliente_contexto", return_value={"ciudad": "Medellín", "nombre_cliente": "Carlos Muñoz", "cliente_codigo": "C-123"}), \
         patch("main.load_recent_conversation_messages", return_value=[]), \
         patch("main.send_sendgrid_email") as mock_email, \
         patch("main.build_operational_email_payload", return_value={
             "to_email": "calidad@ferreinox.com",
             "subject": "Reclamo test",
             "html_content": "<p>test</p>",
             "text_content": "test",
         }) as mock_internal_email, \
         patch("main.build_customer_claim_confirmation_email", return_value={
             "to_email": "carlos@test.com",
             "subject": "Confirmación test",
             "html_content": "<p>confirm</p>",
             "text_content": "confirm",
         }) as mock_customer_email, \
         patch("main.store_outbound_message"):

        result = json.loads(_handle_tool_radicar_reclamo(
            {
                "producto_reclamado": "Koraza Roja Cuñete",
                "descripcion_problema": "Se despega de la fachada a los 3 meses",
                "diagnostico_previo": "El cliente aplicó sin sellador sobre pared con polvo. La ficha técnica indica que se requiere lijar y sellar. Cliente insiste en defecto de fábrica.",
                "correo_cliente": "carlos@test.com",
                "evidencia": "Foto de fachada descascarada, Lote L2024-8877",
            },
            context, conv_context
        ))

    errors = []

    # Verificar resultado exitoso
    if result.get("status") != "exito":
        errors.append(f"Status no es 'exito': {result.get('status')}")
        return errors

    if "CRM-99997" not in result.get("numero_caso", ""):
        errors.append(f"Número de caso incorrecto: {result.get('numero_caso')}")

    # Verificar que se creó la tarea
    if not mock_task.called:
        errors.append("No se llamó upsert_agent_task")
    else:
        call_args = mock_task.call_args
        task_type = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("task_type")
        if task_type != "reclamo_servicio":
            errors.append(f"Tipo de tarea incorrecto: {task_type}")
        task_priority = call_args[0][5] if len(call_args[0]) > 5 else call_args[1].get("priority")
        if task_priority != "alta":
            errors.append(f"Prioridad de tarea incorrecta: {task_priority}")

    # Verificar que se construyeron los emails
    if not mock_internal_email.called:
        errors.append("No se llamó build_operational_email_payload para email interno")
    else:
        # Verificar que se pasa intent "reclamos"
        intent_arg = mock_internal_email.call_args[0][0]
        if intent_arg != "reclamos":
            errors.append(f"Intent del email interno: '{intent_arg}' (esperado: 'reclamos')")

    if not mock_customer_email.called:
        errors.append("No se llamó build_customer_claim_confirmation_email")

    # Verificar que se intentó enviar los emails
    email_calls = mock_email.call_count
    if email_calls < 2:
        errors.append(f"Se enviaron {email_calls} emails (esperado: 2 — interno + cliente)")

    # Verificar que se actualizó el contexto de conversación
    if not mock_ctx.called:
        errors.append("No se llamó update_conversation_context con claim_case")
    else:
        ctx_data = mock_ctx.call_args[0][1]
        claim = ctx_data.get("claim_case", {})
        if not claim.get("submitted"):
            errors.append("claim_case.submitted no es True")

    # Verificar que el claim_detail pasado al email tiene diagnóstico
    if mock_internal_email.called:
        detail_arg = mock_internal_email.call_args[0][3]
        if not detail_arg.get("diagnostico_previo"):
            errors.append("Email interno NO recibió diagnostico_previo")
        if not detail_arg.get("evidence_note"):
            errors.append("Email interno NO recibió evidence_note")

    return errors


def test_claim_detail_tiene_resumen_completo():
    """El claim_detail que se guarda debe tener todos los campos del resumen."""
    from main import _handle_tool_radicar_reclamo

    context = {"conversation_id": 99996, "cliente_id": None, "nombre_visible": "Test"}
    conv_context = {}

    with patch("main.upsert_agent_task") as mock_task, \
         patch("main.update_conversation_context"), \
         patch("main.load_recent_conversation_messages", return_value=[]), \
         patch("main.send_sendgrid_email"), \
         patch("main.build_operational_email_payload", return_value=None), \
         patch("main.build_customer_claim_confirmation_email", return_value=None), \
         patch("main.store_outbound_message"):

        _handle_tool_radicar_reclamo(
            {
                "producto_reclamado": "Pintulux Azul",
                "descripcion_problema": "Se cuarteó en la ventana metálica",
                "diagnostico_previo": "No usó anticorrosivo. La ficha indica Corrotec primero.",
                "correo_cliente": "test@test.com",
                "evidencia": "Lote XY-2024",
            },
            context, conv_context
        )

    errors = []

    if mock_task.called:
        task_detail = mock_task.call_args[0][4] if len(mock_task.call_args[0]) > 4 else {}
        required_fields = ["product_label", "issue_summary", "diagnostico_previo", "evidence_note", "contact_email", "case_reference"]
        for field in required_fields:
            if not task_detail.get(field):
                errors.append(f"claim_detail falta campo '{field}': {task_detail.get(field)}")
    else:
        errors.append("upsert_agent_task no se llamó")

    return errors


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 3: CONVERSACIONES MULTI-TURNO — Flujo de 5 fases del reclamo
# ══════════════════════════════════════════════════════════════════════════════

CLAIM_CONVERSATIONS = [
    # ── Conversación 1: Reclamo típico con diagnóstico de error de aplicación ──
    {
        "name": "Reclamo pintura no cubre — error de aplicación (sellador faltante)",
        "category": "reclamo_diagnostico",
        "turns": [
            (
                "Necesito poner un reclamo, la pintura Viniltex que compré no sirve, la pinté directo sobre el estuco, le metí 3 manos y sigue transparente",
                {
                    # FASE 2: El agente debe hacer diagnóstico técnico con esa info
                    # Puede pedir cédula en paralelo o después, pero debe abordar la técnica
                    "tools_not_called": ["radicar_reclamo"],
                    "response_contains_any": ["sellador", "sella", "fondo", "imprimante", "prim", "preparar", "estuco", "superficie", "dilución", "manos", "cédula", "NIT", "cómo aplicó", "cuéntame"],
                },
            ),
            (
                "Pero yo siempre la he pintado así y nunca me pasó eso. Quiero poner el reclamo igual.",
                {
                    # FASE 4: Cliente insiste → el agente acepta radicar, pide datos
                    "tools_not_called": ["radicar_reclamo"],
                    "response_contains_any": ["correo", "foto", "lote", "evidencia", "email", "cédula", "NIT", "radicar"],
                },
            ),
            (
                "Mi correo es juan@test.com, el lote es L-2024-5891. Mi cédula es 900123456",
                {
                    # FASE 5: Ahora SÍ debe radicar
                    "tools_called": ["radicar_reclamo"],
                    "response_contains_any": ["CRM", "radicado", "registrado", "caso"],
                },
            ),
        ],
    },

    # ── Conversación 2: Reclamación legítima — defecto de fábrica ──
    {
        "name": "Reclamo legítimo — pintura con grumos y mal olor",
        "category": "reclamo_defecto",
        "turns": [
            (
                "Compré un galón de Koraza y cuando lo abrí estaba lleno de grumos y con un olor raro, como podrido",
                {
                    # Defecto evidente, pero el agente debería preguntar algo antes de radicar
                    "tools_not_called": ["radicar_reclamo"],
                    "check_diagnostic": True,
                },
            ),
            (
                "Lo acabo de comprar ayer, está sellado. Tengo la factura y todo. Mi cédula es 1234567890",
                {
                    # El agente debería verificar identidad y consultar compra
                    "response_contains_any": ["verificar", "identidad", "compra", "registr", "encontr", "factura", "lote", "foto", "correo"],
                },
            ),
            (
                "Mi correo es maria@test.com, aquí le mando la foto del galón. El lote dice LK-2024-0912",
                {
                    # Con toda la evidencia de defecto claro, debe radicar
                    "tools_called": ["radicar_reclamo"],
                    "response_contains_any": ["CRM", "radicado", "caso", "registr"],
                },
            ),
        ],
    },

    # ── Conversación 3: Queja que se resuelve con asesoría (no se radica) ──
    {
        "name": "Queja resuelta con asesoría técnica — pintura se pela del metal",
        "category": "reclamo_resuelto_asesoria",
        "turns": [
            (
                "Quiero hacer un reclamo, pinté una reja de hierro con Pintulux y se está pelando toda",
                {
                    "tools_not_called": ["radicar_reclamo"],
                    "check_diagnostic": True,
                },
            ),
            (
                "La pinté con brocha directamente sobre el hierro después de lijar el óxido. No le puse nada antes.",
                {
                    # Diagnóstico: falta anticorrosivo. El agente puede usar RAG o conocimiento propio.
                    "tools_not_called": ["radicar_reclamo"],
                    "response_contains_any": ["anticorrosivo", "corrotec", "primer", "imprimante", "base", "óxido", "preparación", "fondo"],
                },
            ),
            (
                "Ahhh o sea que necesitaba otro producto antes? Cuál me recomienda?",
                {
                    # El agente ofrece solución (primer/anticorrosivo) — esto es Fase 3
                    "tools_not_called": ["radicar_reclamo"],
                    "response_contains_any": ["corrotec", "anticorrosivo", "wash primer", "pintoxido", "primer"],
                },
            ),
        ],
    },

    # ── Conversación 4: Reclamo con verificación de compra ──
    {
        "name": "Reclamo con verificación de compra e identidad",
        "category": "reclamo_verificacion",
        "turns": [
            (
                "Buenas, necesito hacer una reclamación por un impermeabilizante que compré",
                {
                    "tools_not_called": ["radicar_reclamo"],
                    "check_diagnostic": True,
                    "response_contains_any": ["producto", "cuál", "qué", "problema", "cuent", "pasó"],
                },
            ),
            (
                "Es un Pintuco Fill 7 para el techo. Lo apliqué hace un mes y ya se está filtrando de nuevo",
                {
                    "tools_not_called": ["radicar_reclamo"],
                    "response_contains_any": ["mano", "aplicó", "preparó", "superficie", "grieta", "malla", "tela", "cómo", "limpi"],
                },
            ),
            (
                "Le apliqué 2 manos con rodillo, primero limpié el techo. Pero las grietas eran anchas. Igual necesito el reclamo.",
                {
                    # Grietas anchas necesitan malla/tela → el agente lo explica
                    "tools_not_called": ["radicar_reclamo"],
                    "response_contains_any": ["correo", "foto", "lote", "email", "grieta", "malla"],
                },
            ),
            (
                "Ok, mi correo es pedro@test.com. No tengo el lote pero sí fotos.",
                {
                    "tools_called": ["radicar_reclamo"],
                    "response_contains_any": ["CRM", "radicado", "caso"],
                },
            ),
        ],
    },
]


def normalize(text):
    """Normaliza texto para comparaciones."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text


def run_claim_conversation_tests():
    """Parte 3: Ejecuta conversaciones multi-turno de reclamaciones con el LLM."""
    print("\n\n" + "=" * 90)
    print("PARTE 3: FLUJO DE RECLAMACIÓN — Conversaciones multi-turno con LLM")
    print("=" * 90)

    try:
        from main import generate_agent_reply_v2
    except ImportError as e:
        print(f"\n  No se pudo importar generate_agent_reply_v2: {e}")
        return 0, 0, 0

    total_turns = sum(len(conv["turns"]) for conv in CLAIM_CONVERSATIONS)
    passed = 0
    warned = 0
    failed = 0

    for conv_idx, conv in enumerate(CLAIM_CONVERSATIONS, 1):
        conv_name = conv["name"]
        conv_category = conv["category"]
        print(f"\n{'━' * 90}")
        print(f"  CONVERSACIÓN {conv_idx}: {conv_name} [{conv_category}]")
        print(f"{'━' * 90}")

        conversation_context = {}
        recent_messages = []
        context = {
            "conversation_id": 88880 + conv_idx,
            "contact_id": 88880 + conv_idx,
            "cliente_id": None,
            "telefono_e164": "+573009876543",
            "nombre_visible": "Cliente Test Reclamo",
        }

        for turn_idx, (user_message, validations) in enumerate(conv["turns"], 1):
            print(f"\n  Cliente turno {turn_idx}: \"{user_message}\"")

            try:
                t0 = time.time()
                result = generate_agent_reply_v2(
                    profile_name="Cliente Test Reclamo",
                    conversation_context=conversation_context,
                    recent_messages=recent_messages,
                    user_message=user_message,
                    context=context,
                )
                elapsed_ms = int((time.time() - t0) * 1000)
            except Exception as e:
                print(f"  ERROR: {e}")
                traceback.print_exc()
                failed += 1
                continue

            response_text = result.get("response_text", "")
            tool_calls = result.get("tool_calls", [])
            tools_used = [tc["name"] for tc in tool_calls]

            # Update conversation history
            recent_messages.append({"direction": "inbound", "contenido": user_message, "message_type": "text"})
            recent_messages.append({"direction": "outbound", "contenido": response_text, "message_type": "text"})

            # Update context
            ctx_updates = result.get("context_updates", {})
            for k, v in ctx_updates.items():
                if v is not None:
                    conversation_context[k] = v

            # Display
            response_preview = response_text[:350].replace("\n", " | ")
            print(f"  Agente [{elapsed_ms}ms] Tools: {tools_used or '—'}")
            print(f"     \"{response_preview}\"")

            # Validate
            turn_errors = []
            turn_warnings = []

            # Required tools
            if "tools_called" in validations:
                for tool in validations["tools_called"]:
                    if tool not in tools_used:
                        turn_errors.append(f"Tool '{tool}' NO fue llamada (usó: {tools_used})")

            # Forbidden tools
            if "tools_not_called" in validations:
                for tool in validations["tools_not_called"]:
                    if tool in tools_used:
                        turn_errors.append(f"Tool '{tool}' NO debía llamarse en esta fase")

            # Response contains ANY (at least one)
            if "response_contains_any" in validations:
                resp_norm = normalize(response_text)
                found_any = False
                for keyword in validations["response_contains_any"]:
                    kw_norm = normalize(keyword)
                    if kw_norm in resp_norm:
                        found_any = True
                        break
                if not found_any:
                    turn_warnings.append(f"Respuesta no contiene ninguna de: {validations['response_contains_any']}")

            # Response excludes
            if "response_excludes" in validations:
                resp_norm = normalize(response_text)
                for keyword in validations["response_excludes"]:
                    kw_norm = normalize(keyword)
                    if kw_norm in resp_norm:
                        turn_errors.append(f"Respuesta contiene '{keyword}' (PROHIBIDO en esta fase)")

            # Check diagnostic
            if validations.get("check_diagnostic"):
                if "?" not in response_text:
                    turn_warnings.append("Se esperaba pregunta diagnóstica pero no hay '?'")

            # Result
            if turn_errors:
                status = "FAIL"
                failed += 1
            elif turn_warnings:
                status = "WARN"
                warned += 1
            else:
                status = "PASS"
                passed += 1

            icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}[status]
            print(f"  {icon} Turno {turn_idx}: {status}")
            for e in turn_errors:
                print(f"     ❌ {e}")
            for w in turn_warnings:
                print(f"     ⚠️  {w}")

    print(f"\n{'─' * 90}")
    print(f"RECLAMOS RESUMEN: PASS={passed}  WARN={warned}  FAIL={failed}  Total={total_turns}")
    return passed, warned, failed


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 90)
    print("  TEST FLUJO DE RECLAMACIONES — CRM Ferreinox")
    print("  Emails | Herramienta | Conversaciones multi-turno")
    print("=" * 90)

    total_pass = 0
    total_fail = 0

    # ── PARTE 1: Emails ──
    print("\n" + "=" * 90)
    print("PARTE 1: EMAILS DE RECLAMO (resumen estructurado, NO conversación)")
    print("=" * 90)

    email_tests = [
        ("Email interno al área de calidad", test_email_reclamo_interno),
        ("Email confirmación al cliente", test_email_confirmacion_cliente),
        ("Email sin correo retorna None", test_email_sin_correo_cliente),
    ]

    for name, test_fn in email_tests:
        try:
            errors = test_fn()
            if errors:
                print(f"  ❌ {name}")
                for e in errors:
                    print(f"     → {e}")
                total_fail += 1
            else:
                print(f"  ✅ {name}")
                total_pass += 1
        except Exception as e:
            print(f"  ❌ {name} — EXCEPCIÓN: {e}")
            traceback.print_exc()
            total_fail += 1

    # ── PARTE 2: Herramienta radicar_reclamo ──
    print("\n" + "=" * 90)
    print("PARTE 2: HERRAMIENTA radicar_reclamo (validación, duplicados, datos)")
    print("=" * 90)

    tool_tests = [
        ("Rechazo por datos incompletos", test_radicar_reclamo_datos_incompletos),
        ("Detección de duplicado", test_radicar_reclamo_duplicado),
        ("Radicación exitosa completa", test_radicar_reclamo_exitoso),
        ("Resumen tiene todos los campos", test_claim_detail_tiene_resumen_completo),
    ]

    for name, test_fn in tool_tests:
        try:
            errors = test_fn()
            if errors:
                print(f"  ❌ {name}")
                for e in errors:
                    print(f"     → {e}")
                total_fail += 1
            else:
                print(f"  ✅ {name}")
                total_pass += 1
        except Exception as e:
            print(f"  ❌ {name} — EXCEPCIÓN: {e}")
            traceback.print_exc()
            total_fail += 1

    # ── PARTE 3: Conversaciones multi-turno ──
    if os.environ.get("DATABASE_URL") and "localhost" not in os.environ["DATABASE_URL"] and os.environ.get("OPENAI_API_KEY") and "test" not in os.environ["OPENAI_API_KEY"]:
        conv_pass, conv_warn, conv_fail = run_claim_conversation_tests()
        total_pass += conv_pass
        total_fail += conv_fail
    else:
        print("\n" + "=" * 90)
        print("PARTE 3: SALTADA — necesita DATABASE_URL y OPENAI_API_KEY reales")
        print("=" * 90)

    # ── Resumen final ──
    print(f"\n{'═' * 90}")
    print(f"  RESULTADO FINAL: ✅ {total_pass} PASS | ❌ {total_fail} FAIL")
    print(f"{'═' * 90}")

    sys.exit(1 if total_fail > 0 else 0)
