"""
Script para enriquecer TODAS las guías de solución con:
1. Viniltex Ultralavable como especialidad superior en jerarquías interior
2. Koraza Doble Vida como especialidad superior en jerarquías fachada
3. Fijar wording: NO usar "económico" para Koraza/Viniltex Advanced
4. Estuco Acrílico Multiuso nota aclaratoria
5. Pintulux 3 en 1 info en guías de metal
6. Mejores argumentos de sistema
"""
import json, os, re, copy

BASE = os.path.dirname(os.path.abspath(__file__))

def load(fname):
    fp = os.path.join(BASE, fname)
    with open(fp, 'r', encoding='utf-8') as f:
        return json.load(f)

def save(fname, data):
    fp = os.path.join(BASE, fname)
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ Saved: {fname}")

def find_guide(guides, gid):
    for g in guides:
        if g.get("id") == gid:
            return g
    return None

changes = []

# ============================================================
# SECCION 1: HUMEDAD
# ============================================================
print("\n=== SECCION 1: HUMEDAD ===")
s1 = load("guias_solucion_seccion_1_humedad.json")

# GS-HUM-001: Add Viniltex Ultralavable to interior hierarchy
g = find_guide(s1, "GS-HUM-001")
if g:
    h = g["sistema_recomendado"]["jerarquia_acabados"]
    # Add Ultralavable at top
    ultra = {
        "producto": "Viniltex Ultralavable",
        "nivel": "especialidad superior",
        "precio_relativo": "alto",
        "argumento_cliente": "Viniltex Ultralavable repele líquidos y evita que las manchas penetren la superficie. Antibacterial 99%. En una zona que tuvo humedad, esta tecnología hidrofóbica es ideal porque si le cae agua no la absorbe. Dura 10+ años.",
        "busqueda_inventario": "viniltex ultralav blanco galon"
    }
    # Check if already exists
    if not any(p["producto"] == "Viniltex Ultralavable" for p in h):
        h.insert(0, ultra)
        changes.append("GS-HUM-001: Added Viniltex Ultralavable as top specialty")
    
    # Fix nota_tecnica that says "Alternativas más económicas"
    for paso in g["sistema_recomendado"]["pasos"]:
        if "nota_tecnica" in paso and "Alternativas más económicas" in paso.get("nota_tecnica", ""):
            paso["nota_tecnica"] = "Viniltex Advanced es el acabado premium para interiores con máxima lavabilidad. Viniltex Ultralavable es la especialidad superior con tecnología hidrofóbica antimanchas. Otras opciones: Intervinil (buena relación precio/calidad) o Pinturama (presupuesto ajustado)."
            changes.append("GS-HUM-001: Fixed nota_tecnica — removed 'económicas' label")
    
    # Fix regla_opciones
    g["sistema_recomendado"]["regla_opciones"] = "SIEMPRE presenta las opciones como SISTEMAS COMPLETOS con precio total. La base técnica (Aquablock + Estuco) NO cambia entre opciones — solo cambia el acabado final. Presenta TODAS las opciones disponibles de mayor a menor prestación: Ultralavable → Advanced → Intervinil → Pinturama. NO rotules ninguna marca top como 'económica'."
    changes.append("GS-HUM-001: Updated regla_opciones")

# GS-HUM-003: Add Koraza Doble Vida + fix "más económico" en Viniltex Advanced
g = find_guide(s1, "GS-HUM-003")
if g:
    h = g["sistema_recomendado"]["jerarquia_acabados_fachada"]
    # Add Koraza Doble Vida at top
    kdv = {
        "producto": "Koraza Doble Vida",
        "nivel": "especialidad máxima duración",
        "descripcion": "Koraza con tecnología Doble Vida — 10 años de protección garantizada",
        "argumento_cliente": "Koraza Doble Vida tiene tecnología de doble protección que garantiza 10 años sin repintar. Si la fachada tiene alta exposición a sol y lluvia, esta es la máxima inversión disponible.",
        "busqueda_inventario": "koraza doble vida blanco galon"
    }
    if not any(p["producto"] == "Koraza Doble Vida" for p in h):
        h.insert(0, kdv)
        changes.append("GS-HUM-003: Added Koraza Doble Vida as top specialty")
    
    # Fix Koraza normal description
    for p in h:
        if p["producto"] == "Koraza":
            p["nivel"] = "premium"
            p["argumento_cliente"] = "Koraza es una pintura impermeabilizante elastomérica que sella microfisuras y resiste lluvia directa. Excelente protección para fachadas. Dura 5 años en condiciones normales."
            changes.append("GS-HUM-003: Fixed Koraza to 5 years (was 10-12)")
        if p["producto"] == "Viniltex Advanced":
            p["argumento_cliente"] = "Viniltex Advanced es una pintura premium de alta lavabilidad. Funciona en exteriores con exposición moderada (fachada protegida). Diferente tecnología que Koraza — no es elastomérica pero tiene excelente acabado. Dura 5-7 años en fachada."
            changes.append("GS-HUM-003: Fixed Viniltex Advanced — removed 'más económico'")

# GS-HUM-004: Add ultralavable to productos_segun_ubicacion
g = find_guide(s1, "GS-HUM-004")
if g:
    psu = g.get("sistema_recomendado", {}).get("productos_segun_ubicacion", {})
    if psu:
        for k, v in psu.items():
            if isinstance(v, dict) and v.get("acabado") == "Viniltex Advanced":
                v["acabado"] = "Viniltex Ultralavable / Viniltex Advanced"
                v["nota"] = "Ultralavable para máxima protección antimanchas; Advanced para máxima lavabilidad"
                changes.append(f"GS-HUM-004: Added Ultralavable option to {k}")
            elif isinstance(v, str) and v == "Viniltex Advanced":
                psu[k] = "Viniltex Ultralavable / Viniltex Advanced"
                changes.append(f"GS-HUM-004: Added Ultralavable option to {k}")

save("guias_solucion_seccion_1_humedad.json", s1)

# ============================================================
# SECCION 2: FACHADAS EXTERIORES
# ============================================================
print("\n=== SECCION 2: FACHADAS EXTERIORES ===")
s2 = load("guias_solucion_seccion_2_fachadas_exteriores.json")

# GS-FAC-001: Add Koraza Doble Vida + fix wording
g = find_guide(s2, "GS-FAC-001")
if g:
    h = g["sistema_recomendado"]["jerarquia_acabados_fachada"]
    kdv = {
        "producto": "Koraza Doble Vida",
        "nivel": "especialidad máxima duración",
        "descripcion": "Koraza con tecnología Doble Vida — 10 años de protección garantizada",
        "rendimiento": "20-25 m²/galón",
        "argumento_cliente": "Koraza Doble Vida tiene tecnología de doble protección que garantiza 10 años sin repintar. La máxima inversión para fachadas con alta exposición.",
        "busqueda_inventario": "koraza doble vida blanco galon"
    }
    if not any(p["producto"] == "Koraza Doble Vida" for p in h):
        h.insert(0, kdv)
        changes.append("GS-FAC-001: Added Koraza Doble Vida")
    
    for p in h:
        if p["producto"] == "Koraza":
            p["argumento_cliente"] = "Koraza es una pintura impermeabilizante elastomérica que sella microfisuras y protege contra lluvia directa y rayos UV. Gran inversión para fachadas expuestas. Dura 5 años en condiciones normales."
            changes.append("GS-FAC-001: Fixed Koraza to 5 years")
        if p["producto"] == "Viniltex Advanced":
            p["argumento_cliente"] = "Viniltex Advanced es una pintura premium de alta lavabilidad, ideal para fachadas con exposición moderada (protegidas, sin lluvia directa constante). Diferente tecnología que Koraza — excelente acabado sin protección elastomérica. Dura 5-7 años en fachada."
            changes.append("GS-FAC-001: Fixed Viniltex Advanced wording")
        if p["producto"] == "Intervinil":
            p["descripcion"] = "Opción decorativa para zonas protegidas."
            p["argumento_cliente"] = "Intervinil tiene buena relación precio/calidad para exteriores protegidos. No es elastomérica. Si la fachada recibe sol y lluvia directa, considere Koraza. Repintado cada 3-4 años."
            changes.append("GS-FAC-001: Fixed Intervinil wording")
    
    # Fix regla_opciones
    g["sistema_recomendado"]["regla_opciones"] = "SIEMPRE presenta las opciones como SISTEMAS COMPLETOS (base + acabado + herramientas). Presenta TODAS las opciones de mayor a menor prestación: Koraza Doble Vida → Koraza → Viniltex Advanced → Intervinil → Pinturama. Argumenta las diferencias técnicas (elastomérica, lavabilidad, duración). NO rotules marcas top como 'económicas'."
    changes.append("GS-FAC-001: Updated regla_opciones")

# GS-FAC-004: Add Viniltex Ultralavable to interior hierarchy
g = find_guide(s2, "GS-FAC-004")
if g:
    h = g["sistema_recomendado"]["jerarquia_acabados_interior"]
    ultra = {
        "producto": "Viniltex Ultralavable",
        "nivel": "especialidad antimanchas",
        "descripcion": "Repele líquidos, máxima resistencia a manchas, antibacterial 99%",
        "rendimiento": "20-25 m²/galón",
        "argumento_cliente": "Viniltex Ultralavable repele líquidos y evita que las manchas penetren. Tecnología hidrofóbica superior. Ideal para interiores de alto tráfico o familias con niños. Dura 10+ años.",
        "busqueda_inventario": "viniltex ultralav blanco galon"
    }
    if not any(p["producto"] == "Viniltex Ultralavable" for p in h):
        h.insert(0, ultra)
        changes.append("GS-FAC-004: Added Viniltex Ultralavable")
    
    # Fix nota_tecnica with "económico"
    for paso in g["sistema_recomendado"]["pasos"]:
        nt = paso.get("nota_tecnica", "")
        if "Viniltex Advanced (premium), Intervinil (intermedio), Pinturama (económico)" in nt:
            paso["nota_tecnica"] = nt.replace(
                "Viniltex Advanced (premium), Intervinil (intermedio), Pinturama (económico)",
                "Viniltex Ultralavable (antimanchas), Viniltex Advanced (máxima lavabilidad), Intervinil (buena calidad/precio), Pinturama (presupuesto ajustado)"
            )
            changes.append("GS-FAC-004: Fixed nota_tecnica hierarchy wording")
    
    # Add regla_opciones
    g["sistema_recomendado"]["regla_opciones"] = "SIEMPRE presenta las opciones como SISTEMAS COMPLETOS. Presenta de mayor a menor prestación: Ultralavable → Advanced → Baños y Cocinas (para zonas húmedas) → Intervinil → Pinturama. NO rotules marcas top como 'económicas'."
    changes.append("GS-FAC-004: Added regla_opciones")

# GS-FAC-002, GS-FAC-006, GS-FAC-007: Add Koraza Doble Vida mention where Koraza is main recommendation
for gid in ["GS-FAC-002", "GS-FAC-006", "GS-FAC-007"]:
    g = find_guide(s2, gid)
    if g:
        sr = g.get("sistema_recomendado", {})
        pasos = sr.get("pasos", [])
        for paso in pasos:
            nt = paso.get("nota_tecnica", "")
            if "Koraza" in nt and "Koraza Doble Vida" not in nt and "prohibido" not in nt.lower():
                if "PREMIUM" in nt or "premium" in nt or "impermeabilizante" in nt.lower():
                    paso["nota_tecnica"] = nt.rstrip(".") + ". Para máxima duración (10 años), existe Koraza Doble Vida como especialidad superior."
                    changes.append(f"{gid}: Added Koraza Doble Vida mention in nota_tecnica")
                    break

save("guias_solucion_seccion_2_fachadas_exteriores.json", s2)

# ============================================================
# SECCION 3: METALES — Enrich Pintulux 3en1 info
# ============================================================
print("\n=== SECCION 3: METALES ===")
s3 = load("guias_solucion_seccion_3_metales.json")

for g in s3:
    sr = g.get("sistema_recomendado", {})
    pasos = sr.get("pasos", [])
    for paso in pasos:
        prod = paso.get("producto", "") or ""
        nt = paso.get("nota_tecnica", "") or ""
        # Add Pintulux 3en1 description where it's mentioned but not explained
        if "Pintulux 3 en 1" in prod and "Prepara, protege y decora" not in nt:
            paso["nota_tecnica"] = nt.rstrip(".") + ". Pintulux 3 en 1 integra anticorrosivo + acabado en un solo producto: prepara, protege y decora en un solo paso. Es una solución DECORATIVA (ambientes C1 residencial/comercial), no para ambientes industriales C2+."
            changes.append(f"{g['id']}: Enriched Pintulux 3en1 description")
        # Similarly for generic "Pintulux" mentions
        elif "Pintulux" in prod and "3 en 1" not in prod and "Máxima" not in prod:
            paso["nota_tecnica"] = nt.rstrip(".") + ". Nota: Pintulux 3 en 1 (decorativo, incluye anticorrosivo) vs Pintulux Máxima Protección (mayor resistencia)."
            changes.append(f"{g['id']}: Added Pintulux variant clarification")

save("guias_solucion_seccion_3_metales.json", s3)

# ============================================================
# SECCION 5: MADERA — Add Pintulux 3en1 option in GS-MAD-005
# ============================================================
print("\n=== SECCION 5: MADERA ===")
s5 = load("guias_solucion_seccion_5_madera_especiales.json")

g = find_guide(s5, "GS-MAD-005")
if g:
    sr = g.get("sistema_recomendado", {})
    pasos = sr.get("pasos", [])
    for paso in pasos:
        prod = paso.get("producto", "") or ""
        nt = paso.get("nota_tecnica", "") or ""
        if "Pintulux Máxima Protección" in prod and "3 en 1" not in nt:
            paso["producto"] = "Pintulux Máxima Protección / Pintulux 3 en 1"
            paso["nota_tecnica"] = nt.rstrip(".") + ". Alternativa: Pintulux 3 en 1 (incluye anticorrosivo en un solo paso, acabado decorativo). Pintulux Máxima Protección ofrece mayor resistencia."
            changes.append("GS-MAD-005: Added Pintulux 3en1 as option")

save("guias_solucion_seccion_5_madera_especiales.json", s5)

# ============================================================
# SECCION 6: DRYWALL/TEXTURAS — Add Ultralavable where Viniltex Advanced is mentioned
# ============================================================
print("\n=== SECCION 6: DRYWALL/TEXTURAS ===")
s6 = load("guias_solucion_seccion_6_drywall_texturas_alcalinos.json")

for g in s6:
    sr = g.get("sistema_recomendado", {})
    pasos = sr.get("pasos", [])
    for paso in pasos:
        prod = paso.get("producto", "") or ""
        nt = paso.get("nota_tecnica", "") or ""
        if prod == "Viniltex Advanced" and "Ultralavable" not in nt:
            paso["producto"] = "Viniltex Ultralavable / Viniltex Advanced"
            paso["nota_tecnica"] = nt.rstrip(".") + ". Viniltex Ultralavable es la especialidad antimanchas (repele líquidos, 10+ años). Viniltex Advanced: máxima lavabilidad y antibacterial (8-10 años). Ambos son marcas top."
            changes.append(f"{g['id']}: Added Ultralavable option alongside Advanced")
        # Also add Koraza Doble Vida where Koraza is exterior option 
        if "Koraza" in prod and "Doble Vida" not in prod and "Doble Vida" not in nt:
            if "exterior" in nt.lower() or "fachada" in nt.lower() or "exterior" in paso.get("accion", "").lower():
                paso["nota_tecnica"] = nt.rstrip(".") + ". Para máxima duración exterior (10 años), existe Koraza Doble Vida."
                changes.append(f"{g['id']}: Added Koraza Doble Vida mention")

save("guias_solucion_seccion_6_drywall_texturas_alcalinos.json", s6)

# ============================================================
# ALL SECTIONS: Add estuco clarification where needed
# ============================================================
print("\n=== GLOBAL: Estuco clarification ===")
for fname in [
    "guias_solucion_seccion_1_humedad.json",
    "guias_solucion_seccion_2_fachadas_exteriores.json",
    "guias_solucion_seccion_6_drywall_texturas_alcalinos.json",
]:
    data = load(fname)
    for g in data:
        sr = g.get("sistema_recomendado", {})
        pasos = sr.get("pasos", [])
        for paso in pasos:
            prod = paso.get("producto", "") or ""
            nt = paso.get("nota_tecnica", "") or ""
            if "Estuco Profesional Exterior" in prod and "Multiuso" not in nt and "buscar:" not in nt.lower():
                paso["nota_tecnica"] = nt.rstrip(".") + ". Buscar en inventario: 'estuco prof ext blanco'. NOTA: El Estuco Acrílico Multiuso (presentación 1kg) es para retoques pequeños — para sistemas completos usar siempre Estuco Profesional Exterior en presentación galón."
                changes.append(f"{g['id']}: Added estuco search hint + multiuso clarification")
    save(fname, data)

# ============================================================
# Print summary
# ============================================================
print(f"\n{'='*60}")
print(f"TOTAL CHANGES: {len(changes)}")
print(f"{'='*60}")
for c in changes:
    print(f"  • {c}")
