import json
import os
import psycopg2


def exportar_conocimiento():
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DB_URI")
    if not db_url:
        raise RuntimeError("Falta DATABASE_URL o POSTGRES_DB_URI")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, cedula_experto, nombre_experto, contexto_tags,
               producto_recomendado, producto_desestimado,
               nota_comercial, tipo, activo,
               created_at::text AS created_at
        FROM public.agent_expert_knowledge
        WHERE activo = true
        ORDER BY id
    """)
    columnas = [desc[0] for desc in cur.description]
    resultados = [dict(zip(columnas, fila)) for fila in cur.fetchall()]
    cur.close()
    conn.close()

    with open("reglas_experto_ferreinox.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    print(f"✅ Exportadas {len(resultados)} reglas a reglas_experto_ferreinox.json")


if __name__ == "__main__":
    exportar_conocimiento()
