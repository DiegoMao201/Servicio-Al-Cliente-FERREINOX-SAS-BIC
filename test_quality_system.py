"""Test de las funciones de calidad del agente: despedida, confianza, alertas."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:x@localhost:5432/test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

from main import detect_farewell, score_agent_confidence

# ═══ Test detección de despedida ═══
tests_farewell = [
    ("gracias", True),
    ("Muchas gracias!", True),
    ("chao", True),
    ("bueno gracias", True),
    ("hasta luego", True),
    ("no más por ahora", True),
    ("listo gracias", True),
    ("ok gracias", True),
    ("eso es todo", True),
    ("ya no más", True),
    ("ya es todo", True),
    ("buena noche", True),
    ("adios", True),
    ("adiós", True),
    ("bye", True),
    # NO farewell
    ("necesito pintura", False),
    ("cuánto vale", False),
    ("hola", False),
    ("gracias, pero necesito otro producto", False),  # has more after gracias
    ("ok vamos con el pedido", False),
]

print("=" * 70)
print("DETECCIÓN DE DESPEDIDA")
print("=" * 70)
passed = 0
failed = 0
for msg, expected in tests_farewell:
    result = detect_farewell(msg)
    ok = result == expected
    icon = "✅" if ok else "❌"
    print(f'{icon} "{msg}" → farewell={result} (esperado={expected})')
    if ok:
        passed += 1
    else:
        failed += 1
print(f"\nDespedida: {passed}/{passed+failed} PASS\n")


# ═══ Test puntuación de confianza ═══
tests_confidence = [
    # (response, tools, intent, expected_level)
    (
        "Aquí tienes la información de Koraza con rendimiento de 12m²/galón aplicado a 2 manos con rodillo.",
        [{"name": "consultar_conocimiento_tecnico"}],
        "asesoria_tecnica",
        "alta",
    ),
    (
        "Recibimos tu mensaje. Un asesor te contactará pronto.",
        [],
        "consulta_general",
        "baja",
    ),
    (
        "No encontré información técnica para eso, pero te recomiendo comunicarte con un asesor.",
        [],
        "consulta_general",
        "baja",
    ),
    (
        "En Ferreinox no manejamos pintura para piscinas. Te recomiendo comunicarte con un asesor especializado.",
        [],
        "consulta_general",
        "media",
    ),
    (
        "Sí",
        [],
        "consulta_general",
        "baja",
    ),
    (
        "Aquí tienes el inventario disponible: ✅ [5891101] PQ VINILTEX ADV MAT BLANCO 1501 18.93L: Disponible",
        [{"name": "consultar_inventario"}],
        "consulta_productos",
        "alta",
    ),
    (
        "¡Buenos días! ¿En qué puedo ayudarte hoy?",
        [],
        "consulta_general",
        "alta",
    ),
    (
        "Para pintar un techo de eternit te recomiendo Pintuco Fill 7. Tiene rendimiento de 11-12 m²/galón.",
        [{"name": "consultar_conocimiento_tecnico"}, {"name": "consultar_inventario"}],
        "asesoria_tecnica",
        "alta",
    ),
]

print("=" * 70)
print("PUNTUACIÓN DE CONFIANZA")
print("=" * 70)
passed2 = 0
failed2 = 0
for resp, tools, intent, expected_level in tests_confidence:
    c = score_agent_confidence(resp, tools, intent)
    ok = c["level"] == expected_level
    icon = "✅" if ok else "❌"
    print(f'{icon} {c["level"]:>5} ({c["score"]:.2f}) signals={c["signals"]}')
    print(f'   "{resp[:80]}..."')
    if not ok:
        print(f'   ESPERADO: {expected_level}')
    if ok:
        passed2 += 1
    else:
        failed2 += 1
print(f"\nConfianza: {passed2}/{passed2+failed2} PASS")

print(f"\n{'=' * 70}")
print(f"TOTAL: Despedida {passed}/{passed+failed} | Confianza {passed2}/{passed2+failed2}")
print(f"{'=' * 70}")
