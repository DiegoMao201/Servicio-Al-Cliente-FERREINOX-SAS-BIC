import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests


BACKEND_URL = os.environ.get("BACKEND_URL", "https://apicrm.datovatenexuspro.com")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "ferreinox_admin_2024")
AGENT_URL = f"{BACKEND_URL.rstrip('/')}/admin/agent-test"
ARTIFACT_DIR = Path("artifacts/agent/new_quote_battery")
REPORT_PATH = Path("artifacts/agent/new_quote_battery_report.md")
JSON_PATH = Path("artifacts/agent/new_quote_battery_report.json")
TIMEOUT_SECONDS = 20
REQUEST_WALL_TIMEOUT_SECONDS = TIMEOUT_SECONDS + 5


CONVERSATIONS = [
    {
        "id": "NB01",
        "name": "Cubierta Eternit Tizada",
        "case": "Cubierta exterior de fibrocemento con pintura vieja y acabado de cotización completa.",
        "should_quote": True,
        "expected_products": ["Sellomax", "Koraza"],
        "turns": [
            "Hola, necesito recuperar una cubierta de fibrocemento que ya está toda tizada y fea.",
            "Es exterior, ya tiene pintura vieja como de muchos años y no quiero levantar polvo porque está bastante deteriorada.",
            "Son 72 metros cuadrados. Sí quiero que me armes el sistema completo con lo necesario.",
            "Perfecto, cotízamelo y déjalo a nombre de Pradera Canina SAS."
        ],
    },
    {
        "id": "NB02",
        "name": "Terraza Con Fisuras Finas",
        "case": "Terraza peatonal en concreto con fisuras y filtración hacia el piso inferior.",
        "should_quote": True,
        "expected_products": ["Pintuco Fill"],
        "turns": [
            "Buenas, tengo una terraza transitable que cuando llueve moja el cuarto de abajo.",
            "Es una placa de concreto ya pintada hace años, tiene fisuras finas y tránsito peatonal normal.",
            "El área real es de 48 metros cuadrados. Quiero la ruta correcta para impermeabilizarla.",
            "Listo, necesito la cotización formal a nombre de Andrés Felipe Gómez."
        ],
    },
    {
        "id": "NB03",
        "name": "Ladrillo A La Vista Hollín",
        "case": "Fachada en ladrillo a la vista con suciedad y deseo de conservar apariencia natural.",
        "should_quote": True,
        "expected_products": ["Construcleaner", "Siliconite"],
        "turns": [
            "Tengo una fachada de ladrillo a la vista y se puso negra por humo y agua.",
            "La idea NO es pintarla, sino limpiarla y dejarla protegida conservando el ladrillo natural.",
            "Son 95 metros cuadrados y quiero saber qué sistema sí va de verdad.",
            "Sí, cotízame el sistema completo a nombre de Café Ladera Boutique."
        ],
    },
    {
        "id": "NB04",
        "name": "Lavandería Con Capilaridad",
        "case": "Muro interior de lavandería con humedad ascendente y salitre, buscando ruta completa y cotización.",
        "should_quote": True,
        "expected_products": ["Aquablock", "Viniltex"],
        "turns": [
            "Necesito arreglar un muro interior de la zona de ropas porque se está descascarando desde abajo.",
            "Es interior, sale salitre desde la base y no quiero que me manden una solución cosmética que se vuelva a soplar.",
            "El muro tiene 26 metros cuadrados. Quiero el sistema correcto completo.",
            "Ahora sí, hazme la cotización a nombre de Laura Marcela Ríos."
        ],
    },
    {
        "id": "NB05",
        "name": "Deck Exterior En Madera",
        "case": "Deck de madera exterior expuesto a lluvia y sol, con barniz viejo desgastado.",
        "should_quote": True,
        "expected_products": ["Barnex", "Wood Stain"],
        "turns": [
            "Hola, necesito renovar un deck de madera exterior de una casa campestre.",
            "Le pega sol y lluvia, tiene un barniz viejo muy gastado y quiero que siga viéndose la veta.",
            "Son 34 metros cuadrados y me interesa algo durable, no una salida barata.",
            "Sí, cotízame eso a nombre de Reserva El Mirador."
        ],
    },
    {
        "id": "NB06",
        "name": "Reja Oxidada Frente Calle",
        "case": "Reja exterior con óxido avanzado y deseo de cotización del sistema completo.",
        "should_quote": True,
        "expected_products": ["Pintóxido", "Corrotec"],
        "turns": [
            "Necesito recuperar una reja metálica que da a la calle y ya tiene bastante óxido.",
            "Está en exterior total, el óxido ya está saliendo por varias zonas y la quiero terminar en negro.",
            "Calculamos unos 22 metros cuadrados. Quiero el sistema completo bien armado.",
            "Perfecto, genera la cotización a nombre de Edificio San Telmo."
        ],
    },
    {
        "id": "NB07",
        "name": "Lámina Galvanizada Nueva",
        "case": "Cubierta o cerramiento en lámina galvanizada nueva para pintar por primera vez.",
        "should_quote": True,
        "expected_products": ["Wash Primer", "Corrotec"],
        "turns": [
            "Voy a pintar unas láminas galvanizadas nuevas y no quiero que se levante la pintura.",
            "Es exterior, material nuevo sin óxido, y luego quiero terminarlo en blanco.",
            "El proyecto suma 40 metros cuadrados. Necesito que me armes la ruta correcta.",
            "Sí, cotízame el sistema a nombre de Bodega Industrial Arrayanes."
        ],
    },
    {
        "id": "NB08",
        "name": "Cancha Escolar Multideporte",
        "case": "Cancha escolar en concreto con desgaste y requerimiento de cotización.",
        "should_quote": True,
        "expected_products": ["Pintura Canchas"],
        "turns": [
            "Necesito repintar una cancha múltiple de colegio porque ya se borraron las líneas y se ve muy desgastada.",
            "Es una placa de concreto exterior, uso peatonal y deportivo, no montacargas ni tráfico industrial.",
            "El área total es de 540 metros cuadrados y la quieren en azul con demarcaciones.",
            "Hazme la cotización del sistema a nombre de Colegio Nueva Semilla."
        ],
    },
    {
        "id": "NB09",
        "name": "Ducto Metálico Caliente",
        "case": "Ducto metálico sometido a temperatura y expuesto en exterior, buscando recomendación y cotización.",
        "should_quote": True,
        "expected_products": ["Altas Temperaturas"],
        "turns": [
            "Buenas, necesito pintar un ducto metálico que trabaja caliente en una panadería.",
            "Está en exterior parcial, ya tiene óxido leve y soporta temperatura alta cerca a la salida del horno.",
            "El área es pequeña, unos 14 metros cuadrados, pero quiero hacerlo bien desde el inicio.",
            "Sí, cotízame el sistema a nombre de Panadería San Bruno."
        ],
    },
    {
        "id": "NB10",
        "name": "Tanque Agua Potable",
        "case": "Aplicación condicional de agua potable para medir si el agente evita una cotización falsa.",
        "should_quote": False,
        "expected_products": ["Interseal", "agua potable"],
        "turns": [
            "Necesito un sistema para pintar por dentro un tanque de agua potable.",
            "Va sumergido, es metálico y necesito algo que no me vaya a contaminar el agua.",
            "Son 30 metros cuadrados y quiero saber si ustedes manejan la ruta correcta.",
            "Si aplica, me interesa una cotización; si no aplica, prefiero que me lo digas claro."
        ],
    },
]


def normalize_text(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def ensure_dirs() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)


def _agent_request_worker(payload: dict) -> dict:
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
        return {"result": data.get("result") or {}, "elapsed_ms": elapsed_ms}
    except Exception as exc:
        return {"error": str(exc)}


def _worker_cli(payload_path: str, output_path: str) -> int:
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    result = _agent_request_worker(payload)
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


def agent_request(payload: dict) -> tuple[dict, int]:
    with tempfile.TemporaryDirectory(prefix="quote_battery_") as temp_dir:
        temp_dir_path = Path(temp_dir)
        payload_path = temp_dir_path / "payload.json"
        output_path = temp_dir_path / "output.json"
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        try:
            subprocess.run(
                [sys.executable, __file__, "--worker", str(payload_path), str(output_path)],
                check=False,
                timeout=REQUEST_WALL_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Tiempo de pared excedido ({REQUEST_WALL_TIMEOUT_SECONDS}s) consultando {AGENT_URL}") from exc

        if not output_path.exists():
            raise RuntimeError("El worker terminó sin devolver resultado")

        worker_result = json.loads(output_path.read_text(encoding="utf-8"))

    if worker_result.get("error"):
        raise RuntimeError(worker_result["error"])
    return worker_result["result"], worker_result["elapsed_ms"]


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


def summarize_case(case: dict, turns_output: list[dict], conversation_context: dict) -> dict:
    all_tools = []
    had_battery_error = any(turn.get("battery_error") for turn in turns_output)
    for turn in turns_output:
        for tool in turn.get("tools", []):
            if tool not in all_tools:
                all_tools.append(tool)

    final_turn = turns_output[-1] if turns_output else {}
    final_response = final_turn.get("response_text") or ""
    quote_items = extract_quote_items(conversation_context)
    joined_output = normalize_text(final_response + " " + " ".join(item["descripcion"] for item in quote_items))
    expected_hits = [term for term in case.get("expected_products", []) if normalize_text(term) in joined_output]
    quote_ready = bool((conversation_context.get("commercial_draft") or {}).get("ready_to_close"))
    quote_generated = any("confirmar_pedido_y_generar_pdf" in turn.get("tools", []) for turn in turns_output)

    if had_battery_error:
        status = "FAIL"
    elif case.get("should_quote"):
        if quote_items and (quote_ready or quote_generated or len(expected_hits) >= 1):
            status = "PASS"
        elif any(tool in all_tools for tool in ["consultar_conocimiento_tecnico", "consultar_inventario", "consultar_inventario_lote"]):
            status = "WARN"
        else:
            status = "FAIL"
    else:
        if quote_items or quote_generated:
            status = "FAIL"
        elif any(tool in all_tools for tool in ["consultar_conocimiento_tecnico", "consultar_inventario", "consultar_inventario_lote"]):
            status = "PASS"
        else:
            status = "WARN"

    return {
        "id": case["id"],
        "name": case["name"],
        "case": case["case"],
        "status": status,
        "should_quote": case.get("should_quote", False),
        "expected_products": case.get("expected_products", []),
        "expected_hits": expected_hits,
        "tools_used": all_tools,
        "quote_items": quote_items,
        "quote_ready": quote_ready,
        "quote_generated": quote_generated,
        "had_battery_error": had_battery_error,
        "final_response": final_response,
        "turns": turns_output,
        "conversation_context": conversation_context,
    }


def render_markdown(results: list[dict]) -> str:
    lines = [
        "# Batería Nueva RAG + Cotización (10 conversaciones)",
        "",
        f"- Endpoint evaluado: {AGENT_URL}",
        f"- Conversaciones: {len(results)}",
        f"- PASS: {sum(1 for item in results if item['status'] == 'PASS')}",
        f"- WARN: {sum(1 for item in results if item['status'] == 'WARN')}",
        f"- FAIL: {sum(1 for item in results if item['status'] == 'FAIL')}",
        "",
        "## Resumen Ejecutivo",
        "",
    ]

    for item in results:
        lines.append(f"- {item['id']} | {item['status']} | {item['name']} | herramientas: {', '.join(item['tools_used']) or 'ninguna'} | cotizados: {len(item['quote_items'])}")

    lines.append("")
    lines.append("## Detalle Por Caso")
    lines.append("")

    for item in results:
        lines.append(f"### {item['id']} — {item['name']}")
        lines.append("")
        lines.append(f"- Estado: {item['status']}")
        lines.append(f"- Caso planteado: {item['case']}")
        lines.append(f"- ¿Se esperaba cotización?: {'Sí' if item['should_quote'] else 'No'}")
        lines.append(f"- Herramientas usadas: {', '.join(item['tools_used']) or 'ninguna'}")
        lines.append(f"- Productos esperados: {', '.join(item['expected_products']) or 'N/A'}")
        lines.append(f"- Productos detectados en respuesta/cotización: {', '.join(item['expected_hits']) or 'ninguno'}")
        lines.append(f"- Draft listo para cerrar: {'Sí' if item['quote_ready'] else 'No'}")
        lines.append(f"- PDF/confirmación ejecutada: {'Sí' if item['quote_generated'] else 'No'}")
        lines.append("")
        lines.append("#### Turnos")
        lines.append("")
        for turn in item["turns"]:
            lines.append(f"- Turno {turn['turn_index']} usuario: {turn['user_message']}")
            lines.append(f"- Turno {turn['turn_index']} tools: {', '.join(turn['tools']) or 'ninguna'}")
            lines.append(f"- Turno {turn['turn_index']} respuesta: {turn['response_text']}")
        lines.append("")
        lines.append("#### Productos Cotizados")
        lines.append("")
        if item["quote_items"]:
            for quote_item in item["quote_items"]:
                lines.append(
                    f"- [{quote_item['referencia'] or 'sin-ref'}] {quote_item['descripcion']} | cantidad: {quote_item['cantidad']} | unidad: {quote_item['unidad']} | origen: {quote_item['source']}"
                )
        else:
            lines.append("- No quedaron productos cotizados en el draft final.")
        lines.append("")
        lines.append("#### Respuesta Final")
        lines.append("")
        lines.append(item["final_response"] or "Sin respuesta final registrada.")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    ensure_dirs()
    all_results = []

    for index, case in enumerate(CONVERSATIONS, start=1):
        print(f"[{index}/{len(CONVERSATIONS)}] {case['id']} - {case['name']}", flush=True)
        conversation_context = {}
        recent_messages = []
        context = {
            "conversation_id": 230000 + index,
            "contact_id": 230000 + index,
            "cliente_id": None,
            "telefono_e164": "+573001234567",
            "nombre_visible": "Bateria Nueva",
        }
        turns_output = []

        for turn_index, user_message in enumerate(case["turns"], start=1):
            try:
                result, elapsed_ms = agent_request(
                    {
                        "profile_name": "Bateria Nueva",
                        "conversation_context": conversation_context,
                        "recent_messages": recent_messages,
                        "user_message": user_message,
                        "context": context,
                    }
                )
            except Exception as exc:
                elapsed_ms = 0
                result = {
                    "response_text": f"ERROR EN BATERÍA: {exc}",
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
            }
            artifact_path = ARTIFACT_DIR / f"{case['id'].lower()}_turn_{turn_index:02d}.json"
            artifact_path.write_text(json.dumps(artifact_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            turns_output.append(
                {
                    "turn_index": turn_index,
                    "elapsed_ms": elapsed_ms,
                    "user_message": user_message,
                    "response_text": response_text,
                    "tools": tools,
                    "battery_error": result.get("battery_error"),
                }
            )

            if result.get("battery_error"):
                break

        all_results.append(summarize_case(case, turns_output, conversation_context))

    REPORT_PATH.write_text(render_markdown(all_results), encoding="utf-8")
    JSON_PATH.write_text(json.dumps(all_results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(json.dumps(
        {
            "report_path": str(REPORT_PATH),
            "json_path": str(JSON_PATH),
            "pass": sum(1 for item in all_results if item["status"] == "PASS"),
            "warn": sum(1 for item in all_results if item["status"] == "WARN"),
            "fail": sum(1 for item in all_results if item["status"] == "FAIL"),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        raise SystemExit(_worker_cli(sys.argv[2], sys.argv[3]))
    main()