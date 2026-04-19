#!/usr/bin/env python3
"""
Auditoría de Conocimiento Experto — CRM Ferreinox
Ejecutar: python audit_expert_knowledge.py

Muestra TODOS los registros de agent_expert_knowledge ordenados por fecha,
con detalle completo de contexto_tags, nota_comercial, tipo, y experto.
"""
import os, sys
try:
    from sqlalchemy import create_engine, text
except ImportError:
    sys.exit("Instala sqlalchemy: pip install sqlalchemy psycopg2-binary")

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:o5S3X9VIYcbBWqd525hqT24UhYAc8AdjtevyHtlZHhGxJkfMQVZXReCTxkcjSOAX@192.81.216.49:3000/postgres",
)

engine = create_engine(DB_URL)

QUERY = text("""
    SELECT id, cedula_experto, nombre_experto, contexto_tags,
           producto_recomendado, producto_desestimado,
           nota_comercial, tipo, activo, created_at
    FROM public.agent_expert_knowledge
    ORDER BY created_at DESC
""")

with engine.connect() as conn:
    rows = conn.execute(QUERY).mappings().all()

if not rows:
    print("\n⚠️  NO hay registros en agent_expert_knowledge. La tabla está vacía.\n")
    sys.exit(0)

print(f"\n{'='*80}")
print(f"  AUDITORÍA DE CONOCIMIENTO EXPERTO — {len(rows)} registros totales")
print(f"{'='*80}\n")

for r in rows:
    status = "✅ ACTIVO" if r["activo"] else "❌ INACTIVO"
    print(f"── ID {r['id']} | {r['created_at']} | {status} ──")
    print(f"   Experto:    {r['nombre_experto']} (CC {r['cedula_experto']})")
    print(f"   Tipo:       {r['tipo']}")
    print(f"   Tags:       {r['contexto_tags']}")
    if r["producto_recomendado"]:
        print(f"   Recomendar: {r['producto_recomendado']}")
    if r["producto_desestimado"]:
        print(f"   Evitar:     {r['producto_desestimado']}")
    print(f"   Nota:       {r['nota_comercial']}")
    print()

# Resumen por experto
from collections import Counter
por_experto = Counter(r["nombre_experto"] for r in rows)
por_tipo = Counter(r["tipo"] for r in rows)
print(f"{'─'*80}")
print("RESUMEN:")
for exp, cnt in por_experto.most_common():
    print(f"  {exp}: {cnt} registros")
for tipo, cnt in por_tipo.most_common():
    print(f"  Tipo '{tipo}': {cnt}")
print(f"{'─'*80}\n")
