"""
Aplica los cambios:
1. Agrega 136 reglas de canonización al archivo backend/technical_product_canonicalization.py
2. Depura 66 productos del RAG en la BD (marca como 'deprecated')
3. Agrega regla de política para teja metálica
"""
import csv
import json
import os
import re
import sys
import unicodedata

# --- Configuración ---
CSV_PATH = "artifacts/rag_product_universe/validacion_canon_faltantes.csv"
CANON_FILE = "backend/technical_product_canonicalization.py"
MAIN_FILE = "backend/main.py"
DATABASE_URL = "postgresql://postgres:o5S3X9VIYcbBWqd525hqT24UhYAc8AdjtevyHtlZHhGxJkfMQVZXReCTxkcjSOAX@192.81.216.49:3000/postgres"


def _normalize(text):
    text = str(text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_csv():
    with open(CSV_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


# =====================================================
# PASO 1: Agregar reglas al archivo de canonización
# =====================================================
def step1_add_canon_rules():
    print("=" * 60)
    print("PASO 1: Agregando reglas de canonización")
    print("=" * 60)
    
    rows = load_csv()
    
    # Leer archivo actual
    with open(CANON_FILE, encoding="utf-8") as f:
        content = f.read()
    
    # Extraer reglas existentes para evitar duplicados
    existing_labels = set()
    for m in re.finditer(r'"canonical_label":\s*"([^"]+)"', content):
        existing_labels.add(_normalize(m.group(1)))
    
    print(f"  Reglas existentes: {len(existing_labels)}")
    
    # Generar nuevas reglas
    new_rules_lines = []
    added = 0
    skipped_dup = 0
    
    for row in rows:
        ref = (row.get("REFERENCIA_CORRECTA") or "").strip()
        if not ref:
            continue
        
        familia = (row.get("familia_rag") or "").strip()
        texto = (row.get("TEXTO_BUSQUEDA_INVENTARIO") or "").strip()
        if not familia:
            continue
        
        label = re.sub(r"^PINTUCO\s+", "", familia, flags=re.IGNORECASE).strip()
        label_key = _normalize(label)
        
        if label_key in existing_labels:
            skipped_dup += 1
            continue
        existing_labels.add(label_key)
        
        lookup = texto if texto else ref
        
        aliases_set = set()
        aliases_set.add(_normalize(familia))
        aliases_set.add(_normalize(label))
        nums = re.findall(r"\b\d{4,6}\b", familia)
        for n in nums:
            parent = re.sub(r"\b" + n + r"\b", "", _normalize(familia)).strip()
            if parent and len(parent) > 3:
                aliases_set.add(parent)
        aliases_set.discard("")
        aliases = sorted(aliases_set, key=len, reverse=True)
        
        brands = []
        fam_lower = familia.lower()
        if "pintuco" in fam_lower or any(k in fam_lower for k in ["viniltex", "koraza", "pintulux"]):
            brands.append("pintuco")
        if "terinsa" in fam_lower:
            brands.append("terinsa")
        if "graniplast" in fam_lower:
            brands.append("graniplast")
        
        line = '    {"canonical_label": %s, "preferred_lookup_text": %s, "brand_filters": %s, "aliases": %s},' % (
            json.dumps(label, ensure_ascii=False),
            json.dumps(lookup, ensure_ascii=False),
            json.dumps(brands, ensure_ascii=False),
            json.dumps(aliases, ensure_ascii=False),
        )
        new_rules_lines.append(line)
        added += 1
    
    print(f"  Reglas nuevas a agregar: {added}")
    print(f"  Duplicados omitidos: {skipped_dup}")
    
    # Insertar antes del cierre de la lista ]
    # Buscar la última regla y agregar después
    insert_marker = '    {"canonical_label": "Altas Temperaturas"'
    insert_pos = content.find(insert_marker)
    if insert_pos == -1:
        print("  ERROR: No se encontró el marcador de inserción")
        return False
    
    # Encontrar el final de esa línea (la última regla actual)
    end_of_line = content.find("\n", insert_pos)
    
    # Insertar las nuevas reglas después de la última regla existente
    new_block = "\n    # === REGLAS GENERADAS DESDE CSV VALIDADO POR USUARIO (136 reglas) ===\n"
    new_block += "\n".join(new_rules_lines)
    new_block += "\n"
    
    new_content = content[:end_of_line + 1] + new_block + content[end_of_line + 1:]
    
    with open(CANON_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"  ✓ {added} reglas agregadas a {CANON_FILE}")
    return True


# =====================================================
# PASO 2: Depurar productos del RAG
# =====================================================
def step2_depurate_rag():
    print("\n" + "=" * 60)
    print("PASO 2: Depurando 66 productos del RAG")
    print("=" * 60)
    
    try:
        import psycopg2
    except ImportError:
        print("  Instalando psycopg2...")
        os.system(f"{sys.executable} -m pip install psycopg2-binary -q")
        import psycopg2
    
    rows = load_csv()
    families_to_depurate = []
    for row in rows:
        ref = (row.get("REFERENCIA_CORRECTA") or "").strip()
        if ref:
            continue
        familia = (row.get("familia_rag") or "").strip()
        if familia:
            families_to_depurate.append(familia)
    
    print(f"  Productos a depurar: {len(families_to_depurate)}")
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Verificar cuántos existen en agent_technical_profile
    placeholders = ",".join(["%s"] * len(families_to_depurate))
    cur.execute(f"""
        SELECT canonical_family, extraction_status 
        FROM public.agent_technical_profile 
        WHERE canonical_family IN ({placeholders})
    """, families_to_depurate)
    existing = cur.fetchall()
    print(f"  Encontrados en RAG: {len(existing)}")
    
    # Marcar como 'deprecated' en vez de borrar (reversible)
    cur.execute(f"""
        UPDATE public.agent_technical_profile 
        SET extraction_status = 'deprecated_no_inventory'
        WHERE canonical_family IN ({placeholders})
        AND extraction_status = 'ready'
    """, families_to_depurate)
    
    affected = cur.rowcount
    conn.commit()
    
    print(f"  ✓ {affected} perfiles marcados como 'deprecated_no_inventory'")
    
    # Verificar estado final
    cur.execute("""
        SELECT extraction_status, COUNT(*) 
        FROM public.agent_technical_profile 
        GROUP BY extraction_status 
        ORDER BY COUNT(*) DESC
    """)
    for status, count in cur.fetchall():
        print(f"    {status}: {count}")
    
    cur.close()
    conn.close()
    return True


# =====================================================
# EJECUTAR
# =====================================================
if __name__ == "__main__":
    if len(sys.argv) > 1:
        step = sys.argv[1]
        if step == "1":
            step1_add_canon_rules()
        elif step == "2":
            step2_depurate_rag()
    else:
        ok1 = step1_add_canon_rules()
        if ok1:
            step2_depurate_rag()
        print("\n✓ LISTO. Falta agregar la regla de política para teja metálica manualmente.")
