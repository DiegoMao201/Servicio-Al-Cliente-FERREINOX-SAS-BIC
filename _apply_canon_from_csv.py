"""
Script para:
1. Generar las reglas de canonización desde el CSV validado por el usuario
2. Depurar del RAG los 66 productos sin referencia (descontinuados)
3. Aplicar ambos cambios
"""
import csv
import json
import re
import unicodedata
import os
import sys

CSV_PATH = "artifacts/rag_product_universe/validacion_canon_faltantes.csv"
CANON_FILE = "backend/technical_product_canonicalization.py"


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


def generate_rules(rows):
    """Genera reglas para productos CON referencia"""
    existing_labels = set()
    rules = []
    
    for row in rows:
        ref = (row.get("REFERENCIA_CORRECTA") or "").strip()
        if not ref:
            continue
        
        familia = (row.get("familia_rag") or "").strip()
        texto = (row.get("TEXTO_BUSQUEDA_INVENTARIO") or "").strip()
        
        if not familia:
            continue
        
        # canonical_label = familia_rag limpio
        label = familia
        # Quitar prefijo "PINTUCO " redundante para label corto
        label_clean = re.sub(r"^PINTUCO\s+", "", label, flags=re.IGNORECASE).strip()
        
        # Evitar duplicados
        label_key = _normalize(label_clean)
        if label_key in existing_labels:
            continue
        existing_labels.add(label_key)
        
        # preferred_lookup_text = lo que el usuario puso en TEXTO, o la referencia
        lookup = texto if texto else ref
        
        # aliases: familia original + variantes
        aliases_set = set()
        aliases_set.add(_normalize(familia))
        aliases_set.add(_normalize(label_clean))
        # Si tiene código numérico tipo "21209", agregarlo como alias parcial
        nums = re.findall(r"\b\d{4,6}\b", familia)
        for n in nums:
            parent = re.sub(r"\b" + n + r"\b", "", _normalize(familia)).strip()
            if parent and len(parent) > 3:
                aliases_set.add(parent)
        
        aliases_set.discard("")
        aliases = sorted(aliases_set, key=len, reverse=True)
        
        # brand detection
        brands = []
        fam_lower = familia.lower()
        if "pintuco" in fam_lower or any(k in fam_lower for k in ["viniltex", "koraza", "pintulux", "pinturama"]):
            brands.append("pintuco")
        if "abracol" in fam_lower:
            brands.append("abracol")
        if "norton" in fam_lower or "saint-gobain" in fam_lower:
            brands.append("norton")
        if "segurex" in fam_lower:
            brands.append("segurex")
        if "terinsa" in fam_lower:
            brands.append("terinsa")
        if "graniplast" in fam_lower:
            brands.append("graniplast")
        
        rule = {
            "canonical_label": label_clean,
            "preferred_lookup_text": lookup,
            "brand_filters": brands,
            "aliases": aliases,
            "inventory_ref": ref,
        }
        rules.append(rule)
    
    return rules


def get_products_to_depurate(rows):
    """Productos SIN referencia = descontinuados"""
    families = []
    for row in rows:
        ref = (row.get("REFERENCIA_CORRECTA") or "").strip()
        if ref:
            continue
        familia = (row.get("familia_rag") or "").strip()
        if familia:
            families.append(familia)
    return families


def format_rules_python(rules):
    """Formatea las reglas como código Python"""
    lines = []
    for r in rules:
        line = '    {"canonical_label": %s, "preferred_lookup_text": %s, "brand_filters": %s, "aliases": %s},' % (
            json.dumps(r["canonical_label"], ensure_ascii=False),
            json.dumps(r["preferred_lookup_text"], ensure_ascii=False),
            json.dumps(r["brand_filters"], ensure_ascii=False),
            json.dumps(r["aliases"], ensure_ascii=False),
        )
        lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    rows = load_csv()
    print(f"Total filas CSV: {len(rows)}")
    
    new_rules = generate_rules(rows)
    print(f"Reglas nuevas a generar: {len(new_rules)}")
    
    depurate = get_products_to_depurate(rows)
    print(f"Productos a depurar del RAG: {len(depurate)}")
    
    # Mostrar reglas generadas
    print("\n=== PRIMERAS 5 REGLAS GENERADAS ===")
    for r in new_rules[:5]:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    
    print(f"\n=== PRODUCTOS A DEPURAR ===")
    for p in depurate:
        print(f"  - {p}")
    
    # Generar bloque Python
    python_block = format_rules_python(new_rules)
    
    # Guardar a archivo temporal para revisión
    with open("_new_canon_rules.py.txt", "w", encoding="utf-8") as f:
        f.write("# === REGLAS GENERADAS DESDE CSV VALIDADO ===\n")
        f.write("# Total: %d reglas\n\n" % len(new_rules))
        f.write(python_block)
    
    print(f"\nReglas guardadas en _new_canon_rules.py.txt")
    print("Listo para integrar en {CANON_FILE}")
