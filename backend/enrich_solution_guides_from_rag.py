#!/usr/bin/env python3
"""Enriquece masivamente las guías de solución usando perfiles técnicos ya cargados.

Objetivo:
- Multiplicar cobertura semántica de cada guía con jerga común, frases coloquiales,
  preguntas alternativas y rutas de decisión.
- Anclar el enriquecimiento a perfiles técnicos reales ya presentes en RAG
  (`agent_technical_profile`) para no inventar productos ni restricciones.
- Escribir nuevos campos top-level en cada guía para luego serializarlos al RAG.

Uso:
    python backend/enrich_solution_guides_from_rag.py
"""

from __future__ import annotations

import glob
import json
import os
import re
from collections import defaultdict

from sqlalchemy import create_engine, text

from ingest_technical_sheets import get_database_url


GUIDE_FILES_PATTERN = "guias_solucion_seccion_*.json"


def normalize(value: str) -> str:
    value = (value or "").lower()
    replacements = str.maketrans({
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
    })
    value = value.translate(replacements)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


PRODUCT_HINTS = {
    "aquablock": "Aquablock Ultra",
    "koraza": "Koraza",
    "viniltex": "Viniltex",
    "intervinil": "Intervinil",
    "pinturama": "Pinturama",
    "banos y cocinas": "Viniltex Baños y Cocinas",
    "ultralavable": "Viniltex Ultralavable",
    "sellomax": "Sellomax",
    "sellamur": "Sellamur",
    "siliconite": "Siliconite",
    "construcleaner": "Construcleaner",
    "pintuco fill": "Pintuco Fill",
    "pintuco flex": "Pintuco Flex",
    "revofast": "Revofast",
    "estuco profesional exterior": "Estuco Profesional Exterior",
    "estuco plastico": "Estuco Plástico",
    "wash primer": "Wash Primer",
    "corrotec": "Corrotec",
    "pintoxido": "Pintóxido",
    "pintulux": "Pintulux 3 en 1",
    "removedor": "Removedor Pintuco",
    "interseal": "Interseal 670HS",
    "interthane": "Interthane 990",
    "intergard": "Intergard 740",
    "pintucoat": "Pintucoat",
    "pintura de trafico": "Pintura de Tráfico",
    "thinner 21204": "Thinner 21204",
}


DOMAIN_BANKS = {
    "humedad": {
        "frases": [
            "la pared me esta llorando",
            "el muro me suda",
            "se me esta botando la pintura",
            "la pared se me abombo",
            "se me soplo el muro",
            "me sale polvillo blanco",
            "la pared escupe la pintura",
            "me vuelve y me sale la humedad",
            "se me mancha otra vez aunque repinte",
            "la base del muro siempre amanece mojada",
            "el zocalo se esta pudriendo",
            "la pared esta empapada por dentro",
            "me quedo olor a guardado",
            "la pintura se me globo",
            "la pared se me pela desde abajo",
            "se me pone amarilla la pared",
            "el muro se me puso negro",
            "me salen hongos cada rato",
            "cuando llueve se me marca la pared",
            "la humedad me sigue saliendo aunque la pinte",
        ],
        "preguntas": [
            "¿La humedad arranca desde el piso o viene desde arriba?",
            "¿Sale salitre blanco o solo manchas oscuras/moho?",
            "¿Eso aparece solo en invierno o vive así todo el tiempo?",
            "¿Al otro lado hay jardinera, terreno, baño o cocina?",
            "¿La pared está fría/húmeda al tacto o solo se ve manchada?",
        ],
        "rutas": [
            "Si el daño se concentra en los primeros 50-80 cm y hay salitre blanco, priorizar capilaridad/presión negativa.",
            "Si el daño está del enchape hacia arriba o en el cielo raso de baño, priorizar condensación por vapor.",
            "Si la mancha aparece cuando llueve duro y coincide con una grieta o fachada exterior, priorizar filtración desde exterior.",
            "Si el revoque se deshace con la mano, bloquear pintura y mandar a reconstrucción del sustrato.",
        ],
        "errores": [
            "Repintar encima de salitre o base soplada sin retirar lo dañado.",
            "Aplicar estuco antes del bloqueador en muros con presión negativa.",
            "Confundir condensación de baño con capilaridad del muro.",
            "Cotizar galones sin pedir m² reales del paño afectado.",
        ],
        "casos": [
            "closet con olor a guardado",
            "cielo raso de baño que se descaracha",
            "muro medianero que se moja en invierno",
            "pared detrás de jardinera o tierra",
            "mancha negra recurrente en cuarto poco ventilado",
        ],
    },
    "fachada": {
        "frases": [
            "quiero arreglar el frente de la casa",
            "la cara de la casa se ve fea",
            "la lluvia me lava la pintura",
            "el sol me quemo la fachada",
            "la pared de afuera se me descascara",
            "se me cuarteo la fachada",
            "la pared por fuera se ve manchada",
            "quiero dejar la fachada como nueva",
            "el frente se puso opaco",
            "la pintura de afuera ya no da mas",
            "se me soplo el estuco por fuera",
            "la fachada esta chorreada",
            "la casa por fuera se ve cansada",
            "la pared de afuera se pela por pedazos",
            "quiero una pintura que aguante sol y agua",
        ],
        "preguntas": [
            "¿Le pega lluvia directa o está protegida por alero?",
            "¿La base está firme o suena hueca/soplada?",
            "¿Quiere solo cambiar color o también corregir grietas/fisuras?",
            "¿Es ladrillo a la vista, fibrocemento, pañete, estuco o textura?",
            "¿La humedad está abajo en el zócalo o por toda la fachada?",
        ],
        "rutas": [
            "Si la base suena hueca o está soplada, tumbar y reconstruir antes del acabado.",
            "Si el cliente quiere conservar ladrillo visible, priorizar hidrofugante transparente en vez de acabado opaco.",
            "Si hay fisuras que meten agua, sellar la falla mecánica antes de impermeabilizar el paño.",
            "Si es fibrocemento, bloquear cualquier preparación en seco por riesgo de asbesto.",
        ],
        "errores": [
            "Pintar fachada con vinilos interiores o económicos en alta exposición.",
            "Aplicar Koraza encima de base soplada o húmeda sin reparar soporte.",
            "Confundir capilaridad en la base con simple lluvia superficial.",
        ],
        "casos": [
            "frente de casa descolorido",
            "fachada con fisuras de telaraña",
            "muro exterior con moho verde por escurrimiento",
            "eternit envejecido y verdoso",
            "ladrillo a la vista que absorbe agua",
        ],
    },
    "metal": {
        "frases": [
            "la reja se me herrumbro",
            "se lo esta comiendo el oxido",
            "el porton sangra oxido",
            "la baranda esta picada",
            "se me pela como un plastico",
            "el tubo escupe la pintura",
            "la lamina esta herrumbrada",
            "el soldador le echo pintura y se cayo",
            "la estructura se esta descascarando",
            "quiero salvar una reja muy oxidada",
            "la pintura del zinc se levanto toda",
            "el techo metalico se pela por placas",
            "quiero pasar de esmalte a epoxico",
            "la puerta de hierro esta comida",
            "el tubo galvanizado no agarra pintura",
            "la pintura se me arrugo en el metal",
            "esa reja esta vuelta nada de oxido",
            "quiero anticorrosivo para una reja vieja",
            "la teja de zinc ya no aguanta mas sol",
            "el pasamanos se me pica cada invierno",
        ],
        "preguntas": [
            "¿Es hierro/acero negro, galvanizado, aluminio o ya tiene pintura vieja?",
            "¿Está a la intemperie, bajo techo o en ambiente químico/industrial?",
            "¿Quiere mantenimiento convencional o subir a sistema industrial?",
            "¿La pintura vieja está firme, arrugada o se pela como cáscara/plástico?",
            "¿Hay óxido superficial, corrosión profunda o metal ya perforado?",
        ],
        "rutas": [
            "Si es galvanizado/aluminio, el Wash Primer es la ruta prioritaria antes de anticorrosivo o acabado.",
            "Si el metal ya tiene base alquídica y quieren epóxico, remover totalmente hasta metal desnudo.",
            "Si es estructura exterior industrial, cerrar sistemas epóxicos con acabado resistente a UV.",
            "Si es oxidación convencional a la intemperie, el sistema mínimo debe incluir preparación, anticorrosivo y acabado.",
        ],
        "errores": [
            "Pintar galvanizado directo sin Wash Primer.",
            "Dejar Corrotec solo como acabado final exterior.",
            "Recomendar epóxico sobre esmalte alquídico viejo.",
            "Cruzar problemas de metal con soluciones de humedad de muro.",
        ],
        "casos": [
            "reja oxidada de casa",
            "tubería galvanizada mal pintada",
            "techo de zinc o pérgola metálica",
            "estructura con pintura de aceite vieja",
            "baranda exterior expuesta a lluvia y sol",
        ],
    },
    "piso": {
        "frases": [
            "el piso se me pela con el trafico",
            "la pintura del garaje no duro nada",
            "quiero pintar el piso del local",
            "el parqueadero se me gasta rapido",
            "la cancha se me borro",
            "el concreto me esta soltando polvo",
            "quiero demarcar lineas de parqueadero",
            "el piso se me pone jabonoso",
            "quiero un piso que aguante montacargas",
            "el piso del taller se me mancha con aceite",
        ],
        "preguntas": [
            "¿Es peatonal, vehicular liviano o montacargas/pesado?",
            "¿El piso está nuevo, viejo, ya pintado o contaminado con grasa?",
            "¿Es interior, exterior o recibe lluvia directa?",
            "¿Busca demarcación de líneas o recubrimiento completo?",
        ],
        "rutas": [
            "Si es demarcación de líneas, usar ruta de pintura de tráfico y no recubrimiento epóxico general.",
            "Si hay grasa, aceite o piso contaminado, priorizar descontaminación antes de cualquier acabado.",
        ],
        "errores": [
            "No pedir tipo de tráfico antes de recomendar el sistema del piso.",
            "Confundir demarcación con pintura integral de piso.",
        ],
        "casos": [
            "garaje residencial",
            "parqueadero comercial",
            "cancha o zona recreativa",
            "piso de bodega o taller",
        ],
    },
    "madera": {
        "frases": [
            "la madera se me puso fea por el sol",
            "quiero revivir un porton de madera",
            "la puerta de madera esta reseca",
            "el barniz se me cayo",
            "la madera me chupa todo",
            "quiero proteger la pergola",
            "la mesa exterior se me mancho",
            "quiero que se vea la veta",
        ],
        "preguntas": [
            "¿Quiere dejar veta visible o cubrir completamente?",
            "¿Es interior o exterior?",
            "¿La madera está nueva, barnizada, pintada o deteriorada?",
        ],
        "rutas": [
            "Si quieren ver la veta, priorizar barnices/tintes y no esmaltes opacos.",
            "Si la madera está exterior y reseca, reforzar protección UV y humedad.",
        ],
        "errores": [
            "Vender sistema opaco cuando el cliente quería conservar veta.",
            "No definir si la madera está interior o exterior.",
        ],
        "casos": [
            "porton de madera exterior",
            "mueble interior",
            "pergola o deck",
        ],
    },
    "drywall": {
        "frases": [
            "el drywall se me marco",
            "se me ven todas las juntas",
            "quiero arreglar cielo raso en drywall",
            "el muro en panel yeso se me fisuro",
            "quiero textura para una pared lisa",
            "la pared se me alcalinizo",
        ],
        "preguntas": [
            "¿Es panel yeso, masilla, revoque o concreto?",
            "¿Busca alisar, texturizar o solo repintar?",
            "¿Hay fisuras, juntas marcadas o alcalinidad?",
        ],
        "rutas": [
            "Si es panel yeso muy absorbente o reparado, considerar sellado/base antes del acabado.",
            "Si es alcalinidad o sustrato fresco, bloquear curado y preparación antes del acabado decorativo.",
        ],
        "errores": [
            "Pintar panel reparado sin uniformar absorción.",
            "No diferenciar textura decorativa de reparación de juntas.",
        ],
        "casos": [
            "cielo raso de drywall",
            "muro interior resanado",
            "pared con juntas marcadas",
        ],
    },
    "industrial": {
        "frases": [
            "quiero algo bien industrial",
            "necesito maxima resistencia",
            "eso va para planta o fabrica",
            "quiero un sistema pesado de verdad",
            "eso va a recibir quimicos",
            "necesito algo para alto desempeño",
        ],
        "preguntas": [
            "¿La exposición es química, abrasiva, UV, inmersión o solo ambiente severo?",
            "¿Es un ambiente interior o exterior?",
            "¿La base actual es alquídica, epóxica o metal/concreto desnudo?",
        ],
        "rutas": [
            "Si el ambiente es exterior, no dejar epóxico convencional como acabado final expuesto al sol.",
            "Si el sustrato tiene sistema viejo incompatible, remover completamente antes de migrar.",
        ],
        "errores": [
            "Vender sistema industrial sin revisar compatibilidad con la base existente.",
            "No cerrar con acabado UV un sistema epóxico exterior.",
        ],
        "casos": [
            "planta industrial",
            "estructura metálica de alto desempeño",
            "ambiente químico o abrasivo",
        ],
    },
    "selladores": {
        "frases": [
            "quiero sellar una junta",
            "la silicona se me solto",
            "quiero que no me entre agua por la union",
            "la junta me esta llorando",
        ],
        "preguntas": [
            "¿Es junta de dilatación, fisura, ventana, baño o cubierta?",
            "¿El sustrato es poroso, liso o metálico?",
        ],
        "rutas": [
            "Si hay movimiento de junta, priorizar sellador flexible y no resane rígido.",
        ],
        "errores": [
            "Tapar juntas móviles con materiales rígidos.",
        ],
        "casos": [
            "ventana",
            "baño",
            "junta exterior",
        ],
    },
}


STANDARD_TOP_LEVEL_KEYS = {
    "id", "titulo", "doc_type", "escenario", "palabras_clave_cliente",
    "diagnostico", "sistema_recomendado", "productos_prohibidos",
    "rendimientos_referencia", "alerta_metraje", "ejemplo_cotizacion",
    "caso_especial_humedad_base_fachada", "productos_segun_ubicacion",
    "alerta_color", "regla_compatibilidad", "regla_uv",
}


def infer_domains(guide: dict) -> list[str]:
    blob = normalize(json.dumps(guide, ensure_ascii=False))
    domains = []
    if any(token in blob for token in ("humedad", "salitre", "capilaridad", "condensacion", "moho", "hongo", "gotera")):
        domains.append("humedad")
    if any(token in blob for token in ("fachada", "eternit", "fibrocemento", "ladrillo", "exterior", "koraza")):
        domains.append("fachada")
    if any(token in blob for token in ("metal", "reja", "porton", "galvan", "corrotec", "pintulux", "wash primer", "interseal", "interthane")):
        domains.append("metal")
    if any(token in blob for token in ("piso", "parqueadero", "trafico", "cancha", "demarc")):
        domains.append("piso")
    if any(token in blob for token in ("madera", "barniz", "wood stain", "barnex", "sellador madera")):
        domains.append("madera")
    if any(token in blob for token in ("drywall", "panel yeso", "textura", "alcalin")):
        domains.append("drywall")
    if any(token in blob for token in ("industrial", "epox", "poliuret", "intergard", "pintucoat", "interseal", "interthane")):
        domains.append("industrial")
    if any(token in blob for token in ("silicona", "sellador", "junta")):
        domains.append("selladores")
    return domains or ["fachada"]


def collect_existing_strings(node, out: list[str]):
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str):
                out.append(value)
            else:
                collect_existing_strings(value, out)
    elif isinstance(node, list):
        for item in node:
            collect_existing_strings(item, out)


def extract_product_hints(guide: dict) -> list[str]:
    strings = []
    collect_existing_strings(guide, strings)
    blob = normalize(" ".join(strings))
    hits = []
    for token, label in PRODUCT_HINTS.items():
        if token in blob and label not in hits:
            hits.append(label)
    return hits


def load_profiles() -> list[dict]:
    engine = create_engine(get_database_url())
    query = text(
        """
        SELECT canonical_family, source_doc_filename, marca, profile_json
        FROM public.agent_technical_profile
        WHERE extraction_status = 'ready'
        ORDER BY completeness_score DESC NULLS LAST, canonical_family
        """
    )
    with engine.connect() as conn:
        return list(conn.execute(query).mappings())


def match_profiles(guide: dict, profiles: list[dict]) -> list[dict]:
    guide_blob = normalize(json.dumps(guide, ensure_ascii=False))
    product_hits = [normalize(item) for item in extract_product_hints(guide)]
    ranked = []
    for row in profiles:
        canonical_family = normalize(row.get("canonical_family") or "")
        source_name = normalize(row.get("source_doc_filename") or "")
        profile_json = row.get("profile_json") or {}
        profile_blob = normalize(json.dumps(profile_json, ensure_ascii=False))
        score = 0
        for prod in product_hits:
            if prod and (prod in canonical_family or prod in source_name or prod in profile_blob):
                score += 8
        for token in ("fachada", "humedad", "metal", "madera", "piso", "interior", "exterior", "galvanizado", "ladrillo", "fibrocemento"):
            if token in guide_blob and token in profile_blob:
                score += 1
        if score > 0:
            ranked.append((score, row))
    ranked.sort(key=lambda item: (-item[0], item[1].get("canonical_family") or ""))
    seen = set()
    selected = []
    for _, row in ranked:
        family = row.get("canonical_family") or row.get("source_doc_filename")
        if family in seen:
            continue
        seen.add(family)
        selected.append(row)
        if len(selected) >= 6:
            break
    return selected


def unique_keep_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        clean = re.sub(r"\s+", " ", (value or "").strip())
        if not clean:
            continue
        key = normalize(clean)
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def generate_keyword_variants(keywords: list[str]) -> list[str]:
    variants = []
    for keyword in keywords:
        k = (keyword or "").strip()
        if not k:
            continue
        variants.append(k)
        nk = normalize(k)
        if nk.startswith("pintar "):
            target = k[7:]
            variants.extend([
                f"con qué pinto {target}",
                f"qué le echo a {target}",
                f"qué sistema lleva {target}",
                f"cómo preparo {target} antes de pintar",
            ])
        if nk.startswith("repintar "):
            target = k[9:]
            variants.extend([
                f"cómo repinto {target}",
                f"qué me recomienda para {target}",
            ])
        if "humedad" in nk:
            variants.extend([
                k.replace("humedad", "mancha de humedad"),
                k.replace("humedad", "salitre"),
            ])
        if "grieta" in nk or "fisura" in nk:
            variants.extend([
                k.replace("grietas", "rajitas"),
                k.replace("fisuras", "cuarteado"),
            ])
        if "oxid" in nk:
            variants.extend([
                k.replace("oxidado", "herrumbrado"),
                k.replace("óxido", "herrumbre"),
            ])
    return unique_keep_order(variants)


def build_rag_anchors(matched_profiles: list[dict]) -> tuple[list[dict], list[str], list[str]]:
    anchors = []
    extra_questions = []
    extra_errors = []
    for row in matched_profiles:
        profile_json = row.get("profile_json") or {}
        summary = ((profile_json.get("commercial_context") or {}).get("summary") or "").strip()
        alerts = [str(item).strip() for item in (profile_json.get("alerts") or [])[:4] if str(item).strip()]
        diag = [str(item).strip() for item in (profile_json.get("diagnostic_questions") or [])[:5] if str(item).strip()]
        restricted = [str(item).strip() for item in (profile_json.get("restricted_surfaces") or [])[:5] if str(item).strip()]
        surfaces = [str(item).strip() for item in (profile_json.get("surface_targets") or [])[:6] if str(item).strip()]
        excerpts = [str(item).strip() for item in (profile_json.get("source_excerpts") or [])[:2] if str(item).strip()]
        anchors.append({
            "familia_tecnica": row.get("canonical_family"),
            "fuente": row.get("source_doc_filename"),
            "superficies_compatibles": surfaces,
            "superficies_restringidas": restricted,
            "preguntas_diagnosticas_ficha": diag,
            "alertas_ficha": alerts,
            "resumen_ficha": summary,
            "extractos_clave": excerpts,
        })
        extra_questions.extend(diag)
        for item in restricted:
            extra_errors.append(f"No cruzar este sistema sobre superficie restringida: {item}.")
        for item in alerts:
            extra_errors.append(f"Advertencia técnica de ficha: {item}")
    return anchors, unique_keep_order(extra_questions), unique_keep_order(extra_errors)


def enrich_guide(guide: dict, profiles: list[dict]) -> dict:
    enriched = json.loads(json.dumps(guide, ensure_ascii=False))
    domains = infer_domains(guide)
    matched_profiles = match_profiles(guide, profiles)
    anchors, profile_questions, profile_errors = build_rag_anchors(matched_profiles)

    domain_phrases = []
    domain_questions = []
    domain_routes = []
    domain_errors = []
    domain_cases = []
    for domain in domains:
        bank = DOMAIN_BANKS.get(domain, {})
        domain_phrases.extend(bank.get("frases") or [])
        domain_questions.extend(bank.get("preguntas") or [])
        domain_routes.extend(bank.get("rutas") or [])
        domain_errors.extend(bank.get("errores") or [])
        domain_cases.extend(bank.get("casos") or [])

    existing_keywords = guide.get("palabras_clave_cliente") or []
    existing_questions = ((guide.get("diagnostico") or {}).get("preguntas_obligatorias") or [])
    prohibited = guide.get("productos_prohibidos") or []
    prohibited_errors = [
        f"Error común a bloquear: {item.get('producto')}. Razón: {item.get('razon')}"
        for item in prohibited
        if item.get("producto") and item.get("razon")
    ]

    enriched["frases_cliente_equivalentes"] = unique_keep_order(
        generate_keyword_variants(existing_keywords) + domain_phrases
    )[:60]
    enriched["preguntas_diagnostico_alternativas"] = unique_keep_order(
        existing_questions + domain_questions + profile_questions
    )[:30]
    enriched["rutas_de_decision"] = unique_keep_order(domain_routes)[:16]
    enriched["casos_vecinos_mismo_resultado"] = unique_keep_order(domain_cases)[:20]
    enriched["errores_comunes_cliente"] = unique_keep_order(
        domain_errors + prohibited_errors + profile_errors
    )[:30]
    enriched["productos_relacionados_rag"] = extract_product_hints(guide)
    enriched["anclas_tecnicas_rag"] = anchors

    # Señales coloquiales más cercanas al síntoma real del cliente.
    symptom_words = []
    diag = guide.get("diagnostico") or {}
    symptom_words.extend(diag.get("señales_confirmatorias") or [])
    if not symptom_words:
        symptom_words.extend(domain_phrases[:10])
    enriched["senales_cliente_coloquiales"] = unique_keep_order(symptom_words + domain_phrases)[:25]

    return enriched


def main():
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    files = sorted(glob.glob(os.path.join(workspace_root, GUIDE_FILES_PATTERN)))
    if not files:
        print("No guide files found")
        return

    profiles = load_profiles()
    updated_files = 0
    updated_guides = 0

    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            guides = json.load(f)
        enriched_guides = []
        changed = False
        for guide in guides:
            enriched = enrich_guide(guide, profiles)
            if json.dumps(enriched, ensure_ascii=False, sort_keys=True) != json.dumps(guide, ensure_ascii=False, sort_keys=True):
                changed = True
                updated_guides += 1
            enriched_guides.append(enriched)
        if changed:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(enriched_guides, f, ensure_ascii=False, indent=2)
                f.write("\n")
            updated_files += 1
            print(f"UPDATED: {os.path.basename(filepath)} ({len(enriched_guides)} guías)")
        else:
            print(f"SKIP: {os.path.basename(filepath)}")

    print(f"DONE: files={updated_files} guides={updated_guides}")


if __name__ == "__main__":
    main()