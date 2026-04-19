"""
Audit: RAG technical sheets vs real portfolio mapping.
Checks which key products have fichas técnicas and what detail level exists.
"""
import json

with open("rag_diag.json", encoding="utf-8") as f:
    data = json.load(f)

docs = data["documentos"]
familias = [d["familia"] for d in docs if d["familia"]]

# ── Key products that must have RAG coverage ──
KEY_PRODUCTS = {
    # Impermeabilizantes / humedad
    "AQUABLOCK": "Sellador humedad interna, presión negativa",
    "AQUABLOCK ULTRA": "Impermeabilizante muros int/ext",
    "SELLAMUR": "Sellador de muros",
    "SILICONITE": "Sellador siliconado",
    "PINTUCO FILL": "Impermeabilizante techos/cubiertas (Fill 7, Fill 12)",
    "KORAZA": "Fachadas exteriores SOLAMENTE",
    # Anticorrosivos
    "CORROTEC": "Anticorrosivo para metal",
    "PINTOXIDO": "Desoxidante/convertidor",
    "WASH PRIMER": "Fondo metales nuevos/galvanizados",
    # Pisos
    "PINTUCOAT": "Epóxica pisos industriales",
    "CANCHAS": "Pisos de concreto, andenes, garajes",
    # Esmaltes
    "PINTULUX": "Esmalte premium",
    "DOMESTICO": "Esmalte económico",
    # Vinilos
    "VINILTEX": "Vinilo premium tipo 1",
    "INTERVINIL": "Vinilo tipo 2",
    "PINTURAMA": "Vinilo tipo 3 económico",
    "VINIL LATEX": "Vinilo tipo 2",
    "VINIL PLUS": "Vinilo tipo 1",
    # Aerosoles
    "AEROCOLOR": "Aerosol Pintuco",
    # Lacas/barnices
    "PINTULAC": "Laca para madera",
    "BARNIZ": "Barniz/protección madera",
    # International/AkzoNobel
    "INTERSEAL": "Epóxica industrial International",
    "INTERTHANE": "Poliuretano International",
    "INTERGARD": "Primer epóxico International",
    "INTERCHAR": "Intumescente International",
    "INTERFINE": "Acabado International",
    # Complementarios
    "ESTUCO": "Preparación superficies",
    "IMPRIMANTE": "Fondo/sellador",
    "THINNER": "Diluyente",
    # Sika
    "SIKA": "Impermeabilizante complementario",
}

print("=" * 80)
print("AUDITORÍA: COBERTURA RAG vs PORTAFOLIO REAL FERREINOX")
print("=" * 80)
print(f"\nTotal documentos RAG: {len(docs)}")
print(f"Total chunks RAG: {data['total_chunks']}")
print(f"Familias únicas: {len(set(familias))}")

print("\n" + "─" * 80)
print("COBERTURA POR PRODUCTO CLAVE:")
print("─" * 80)

covered = 0
not_covered = 0
partial = 0

for product, desc in KEY_PRODUCTS.items():
    # Find matching RAG docs
    matches = []
    for d in docs:
        fam = (d.get("familia") or "").upper()
        archivo = (d.get("archivo") or "").upper()
        if product.upper() in fam or product.upper() in archivo:
            matches.append(d)
    
    total_chunks = sum(m["chunks"] for m in matches)
    
    if matches:
        # Separate fichas técnicas from hojas de seguridad
        fichas = [m for m in matches if "FDS" not in (m.get("archivo") or "").upper() 
                  and "HOJA DE SEGURIDAD" not in (m.get("archivo") or "").upper()
                  and "CERTIFICADO" not in (m.get("archivo") or "").upper()
                  and "CERTIFICACION" not in (m.get("archivo") or "").upper()]
        hds = [m for m in matches if "FDS" in (m.get("archivo") or "").upper() 
               or "HOJA DE SEGURIDAD" in (m.get("archivo") or "").upper()]
        
        status = "✅ CUBIERTO" if fichas else "⚠️ SOLO HDS"
        if fichas:
            covered += 1
        else:
            partial += 1
        
        print(f"\n{status} | {product} ({desc})")
        print(f"  Docs: {len(matches)} | Fichas técnicas: {len(fichas)} | HDS: {len(hds)} | Chunks: {total_chunks}")
        for m in fichas[:5]:
            print(f"  📄 FT: {m['archivo']} ({m['chunks']} chunks)")
        for m in hds[:3]:
            print(f"  🔒 HDS: {m['archivo']} ({m['chunks']} chunks)")
    else:
        not_covered += 1
        print(f"\n❌ SIN COBERTURA | {product} ({desc})")
        print(f"  ⚠️ No hay fichas técnicas ni hojas de seguridad en el RAG")

print("\n" + "=" * 80)
print(f"RESUMEN: {covered} cubiertos | {partial} parcial (solo HDS) | {not_covered} sin cobertura")
print(f"Tasa de cobertura: {covered}/{len(KEY_PRODUCTS)} = {covered*100//len(KEY_PRODUCTS)}%")
print("=" * 80)

# ── Check for CRITICAL USE CASES ──
print("\n" + "─" * 80)
print("CASOS CRÍTICOS DE USO - ¿El RAG puede distinguir?")
print("─" * 80)

critical_cases = [
    ("HUMEDAD INTERNA / PRESIÓN NEGATIVA", ["AQUABLOCK", "SELLAMUR", "ESTUCO ANTI HUMEDAD"]),
    ("FACHADA EXTERIOR / LLUVIA+SOL", ["KORAZA", "KORAZA DOBLE VIDA", "KORAZA IMPERMEABLE", "KORAZA SOL Y LLUVIA"]),
    ("PISO INDUSTRIAL / TRÁFICO PESADO", ["PINTUCOAT", "C-FLOOR"]),
    ("PISO RESIDENCIAL / CANCHAS", ["CANCHAS"]),
    ("METAL OXIDADO / ANTICORROSIVO", ["CORROTEC", "PINTOXIDO", "ANTICORROSIVO"]),
    ("TECHO / CUBIERTA IMPERMEABILIZAR", ["PINTUCO FILL", "ALUTAX", "AISLANTE PARA TECHOS"]),
    ("PISCINA / INMERSIÓN EN AGUA", []),  # Should have NO products
    ("MADERA EXTERIOR / INTEMPERIE", ["BARNEX", "WOOD STAIN", "IMPREGNANTE"]),
]

for case_name, expected_products in critical_cases:
    print(f"\n🔍 {case_name}:")
    found_any = False
    for prod in expected_products:
        matches = [d for d in docs if prod.upper() in (d.get("familia") or "").upper() 
                   or prod.upper() in (d.get("archivo") or "").upper()]
        fichas_only = [m for m in matches if "FDS" not in (m.get("archivo") or "").upper()
                       and "HOJA DE SEGURIDAD" not in (m.get("archivo") or "").upper()]
        if fichas_only:
            found_any = True
            print(f"  ✅ {prod}: {len(fichas_only)} fichas técnicas ({sum(m['chunks'] for m in fichas_only)} chunks)")
    if not expected_products:
        print(f"  🚫 Correcto: NO debe haber producto para esto → redirigir a asesor")
    elif not found_any:
        print(f"  ❌ Sin cobertura técnica para este caso de uso")
