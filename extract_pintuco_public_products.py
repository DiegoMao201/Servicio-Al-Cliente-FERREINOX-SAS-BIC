from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import cruzar_fichas_con_inventario as inventory_matcher
except Exception:
    inventory_matcher = None


SITEMAP_INDEX_URL = "https://www.pintuco.com.co/sitemap.xml"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "pintuco_public_site"
USER_AGENT = "FerreinoxRAGBot/1.0 (+public metadata enrichment)"

HEADING_VARIANTS = {
    "descripcion_general": ["descripcion general", "informacion general"],
    "acabado": ["acabado"],
    "preparacion_superficie": ["prepara la superficie"],
    "aplicacion": ["prepara el producto y aplicalo", "prepara el producto y aplícalo", "modo de uso"],
    "rendimiento": ["rendimiento", "rendimiento practico aprox", "rendimiento práctico aprox"],
    "beneficios": ["beneficios"],
}

SURFACE_KEYWORDS = {
    "metal": ["metal", "acero", "reja", "ventana", "porton", "portón", "aluminio", "galvanizado", "zinc", "rines"],
    "madera": ["madera", "puerta", "mesa", "silla", "ventana en exteriores", "zocalo", "zócalo"],
    "mamposteria": ["pared", "muro", "fachada", "revoque", "estuco", "bloque", "ladrillo", "techo", "fibrocemento"],
    "interior": ["interior", "bano", "baño", "cocina", "sala", "comedor", "pasillo", "cuarto"],
    "exterior": ["exterior", "fachada", "intemperie", "lluvia", "sol"],
    "piso": ["piso", "demarcacion", "demarcación", "cancha", "trafico", "tráfico"],
}

BENEFIT_PATTERNS = {
    "antibacterial": ["bacter", "elimina", "99.9%", "99% de las bacterias"],
    "antihongos": ["antihong", "hongos", "moho"],
    "impermeable": ["imperme", "filtracion", "filtración", "humedad", "vapor"],
    "anticorrosivo": ["anticorros", "oxido", "óxido", "corrosion", "corrosión"],
    "ultralavable": ["ultra lav", "lavabilidad", "lavable", "antimanchas", "repele liquidos", "repele líquidos"],
    "alto_cubrimiento": ["alto cubrimiento", "poder cubriente", "cubrimiento"],
    "rapido_secado": ["rapido secado", "rápido secado", "secado"],
    "durabilidad": ["durable", "durabilidad", "retencion de color", "retención de color", "resistente"],
}

APPLICATION_METHODS = ["brocha", "rodillo", "pistola", "airless", "llana", "espatula", "espátula"]

RELATED_PRODUCT_PATTERNS = [
    "wash primer",
    "sellomax",
    "removedor",
    "ajustador",
    "estuco",
    "pintucoat",
    "corrotec",
    "viniltex",
    "koraza",
    "pintulux",
]


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def session_get(url: str, session: requests.Session, *, timeout: int = 30) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_sitemap_urls(session: requests.Session) -> tuple[list[str], list[str]]:
    xml_text = session_get(SITEMAP_INDEX_URL, session)
    root = ET.fromstring(xml_text)
    sitemap_urls = [elem.text.strip() for elem in root.iter() if elem.tag.endswith("loc") and elem.text]
    product_sitemaps = [url for url in sitemap_urls if re.search(r"/productos-sitemap\.xml$", url)]
    category_sitemaps = [url for url in sitemap_urls if "cat_productos-sitemap" in url]
    return product_sitemaps, category_sitemaps


def fetch_url_list_from_sitemap(sitemap_url: str, session: requests.Session) -> list[str]:
    xml_text = session_get(sitemap_url, session)
    root = ET.fromstring(xml_text)
    urls = [elem.text.strip() for elem in root.iter() if elem.tag.endswith("loc") and elem.text]
    return [url for url in urls if url.startswith("https://www.pintuco.com.co/")]


def clean_block_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def collect_section_text(soup: BeautifulSoup, heading_options: list[str]) -> str:
    normalized_options = {normalize_text(item) for item in heading_options}
    headings = soup.find_all(re.compile(r"^h[1-6]$"))
    for heading in headings:
        heading_text = normalize_text(heading.get_text(" ", strip=True))
        if heading_text not in normalized_options:
            continue
        collected: list[str] = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) and re.fullmatch(r"h[1-6]", sibling.name or ""):
                break
            sibling_text = ""
            if hasattr(sibling, "get_text"):
                sibling_text = sibling.get_text(" ", strip=True)
            else:
                sibling_text = str(sibling).strip()
            sibling_text = clean_block_text(sibling_text)
            if sibling_text:
                collected.append(sibling_text)
        if collected:
            return "\n".join(collected)
    return ""


def extract_links_by_text(soup: BeautifulSoup, pattern: str) -> Optional[str]:
    regex = re.compile(pattern, re.IGNORECASE)
    for anchor in soup.find_all("a", href=True):
        text = clean_block_text(anchor.get_text(" ", strip=True))
        if regex.search(text):
            return anchor["href"].strip()
    return None


def extract_presentations(page_text: str) -> list[str]:
    found = []
    for pattern in [r"\b1/4 gal[oó]n\b", r"\bgal[oó]n\b", r"\b5 galones\b", r"\bcu[ñn]ete\b", r"\b20 litros\b"]:
        for match in re.finditer(pattern, page_text, flags=re.IGNORECASE):
            value = clean_block_text(match.group(0)).lower()
            if value not in found:
                found.append(value)
    return found


def extract_coverage(text: str) -> list[str]:
    patterns = [
        r"\b\d+\s*[–-]\s*\d+\s*m²/gal[^.\n]*",
        r"\b\d+\s*a\s*\d+\s*m2/gal[^.\n]*",
        r"\b\d+\s*[-–]\s*\d+\s*m2/gal[^.\n]*",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            value = clean_block_text(match.group(0))
            if value and value not in found:
                found.append(value)
    return found[:6]


def extract_drying_times(text: str) -> list[str]:
    patterns = [
        r"\b\d+\s*(?:a\s*\d+\s*)?horas?[^.\n]*secad[oa][^.\n]*",
        r"\bminimo\s*\d+\s*horas?[^.\n]*",
        r"\bdeje transcurrir[^.\n]*\d+\s*horas?[^.\n]*",
        r"\b\d+\s*d[ií]a[s]?[^.\n]*",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            value = clean_block_text(match.group(0))
            if value and value not in found:
                found.append(value)
    return found[:6]


def extract_dilution_hints(text: str) -> list[str]:
    patterns = [
        r"brocha o rodillo[^\n]{0,120}",
        r"pistola convencional[^\n]{0,120}",
        r"pistola airless[^\n]{0,120}",
        r"maximo\s*\d+%[^.\n]*",
        r"\b\d+%[^.\n]*agua[^.\n]*",
    ]
    found: list[str] = []
    normalized_text = normalize_text(text)
    original = clean_block_text(text)
    for pattern in patterns:
        for match in re.finditer(pattern, original, flags=re.IGNORECASE):
            value = clean_block_text(match.group(0))
            if value and value not in found:
                found.append(value)
    if not found and "dilu" in normalized_text:
        found.append("Contiene instrucciones de dilución en la página pública")
    return found[:6]


def detect_surfaces(text: str) -> list[str]:
    normalized = normalize_text(text)
    found: list[str] = []
    for label, keywords in SURFACE_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            found.append(label)
    return found


def detect_benefit_tags(text: str) -> list[str]:
    normalized = normalize_text(text)
    found: list[str] = []
    for label, keywords in BENEFIT_PATTERNS.items():
        if any(keyword in normalized for keyword in keywords):
            found.append(label)
    return found


def detect_application_methods(text: str) -> list[str]:
    normalized = normalize_text(text)
    found = [method for method in APPLICATION_METHODS if method in normalized]
    return found


def extract_related_products(text: str) -> list[str]:
    normalized = normalize_text(text)
    found = []
    for token in RELATED_PRODUCT_PATTERNS:
        if token in normalized and token not in found:
            found.append(token)
    return found


def first_sentence(text: str) -> str:
    clean = clean_block_text(text)
    if not clean:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", clean)
    return parts[0][:320].strip()


def extract_product_record(url: str, session: requests.Session, inventory_rows: list[dict]) -> dict:
    html = session_get(url, session)
    soup = BeautifulSoup(html, "html.parser")
    page_text = clean_block_text(soup.get_text(" ", strip=True))

    title_node = soup.find("h1")
    title = clean_block_text(title_node.get_text(" ", strip=True)) if title_node else url.rstrip("/").split("/")[-1]

    sections = {key: collect_section_text(soup, headings) for key, headings in HEADING_VARIANTS.items()}
    combined_text = "\n".join(value for value in sections.values() if value)

    ficha_url = extract_links_by_text(soup, r"descargar ficha t[eé]cnica")
    buy_url = next((a["href"].strip() for a in soup.find_all("a", href=True) if "tienda.pintuco.com" in a["href"]), None)
    calculator_url = extract_links_by_text(soup, r"cu[aá]nta pintura necesitas")

    inventory_match = None
    if inventory_matcher is not None:
        try:
            pseudo_row = pd.Series(
                {
                    "lookup_inventario_sugerido": title,
                    "nombre_recomendado": f"{title}.pdf",
                    "familia_canonica": title,
                    "archivo_actual": f"{title}.pdf",
                    "tipo_documento": "ficha_tecnica",
                    "accion": "revisar",
                }
            )
            inventory_match = inventory_matcher.choose_best_match(pseudo_row, inventory_rows)
        except Exception:
            inventory_match = None

    record = {
        "product_name": title,
        "page_url": url,
        "technical_sheet_url": ficha_url or "",
        "buy_url": buy_url or "",
        "calculator_url": calculator_url or "",
        "summary_public": first_sentence(sections.get("descripcion_general") or combined_text),
        "finish": first_sentence(sections.get("acabado") or ""),
        "recommended_use": first_sentence(combined_text),
        "surface_targets": detect_surfaces(combined_text),
        "benefit_tags": detect_benefit_tags(combined_text),
        "application_methods": detect_application_methods(combined_text),
        "related_products": extract_related_products(combined_text),
        "coverage_ranges": extract_coverage(combined_text),
        "drying_times": extract_drying_times(combined_text),
        "dilution_hints": extract_dilution_hints(sections.get("aplicacion") or combined_text),
        "presentations": extract_presentations(page_text),
        "inventory_match_name": inventory_match.description if inventory_match else "",
        "inventory_match_ref": inventory_match.reference if inventory_match else "",
        "inventory_match_score": round(inventory_match.score, 2) if inventory_match else "",
        "inventory_match_source": inventory_match.source if inventory_match else "",
        "canonical_family_from_inventory": inventory_matcher.cleanup_erp_family(inventory_match.description) if inventory_matcher and inventory_match else "",
    }
    return record


def dataframe_for_export(records: list[dict]) -> pd.DataFrame:
    rows = []
    for record in records:
        row = dict(record)
        for key in [
            "surface_targets",
            "benefit_tags",
            "application_methods",
            "related_products",
            "coverage_ranges",
            "drying_times",
            "dilution_hints",
            "presentations",
        ]:
            row[key] = " | ".join(record.get(key) or [])
        rows.append(row)
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extrae metadata pública de productos Pintuco y la cruza con inventario Ferreinox.")
    parser.add_argument("--limit", type=int, default=0, help="Límite de productos a procesar; 0 = todos")
    parser.add_argument("--delay", type=float, default=0.15, help="Pausa entre requests")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    product_sitemaps, category_sitemaps = fetch_sitemap_urls(session)
    product_urls: list[str] = []
    for sitemap_url in product_sitemaps:
        product_urls.extend(fetch_url_list_from_sitemap(sitemap_url, session))

    category_urls: list[str] = []
    for sitemap_url in category_sitemaps:
        category_urls.extend(fetch_url_list_from_sitemap(sitemap_url, session))

    # Keep only product detail pages.
    product_urls = [url for url in product_urls if "/productos/" in url and url.rstrip("/").count("/") >= 4]
    product_urls = list(dict.fromkeys(product_urls))
    category_urls = list(dict.fromkeys(category_urls))

    total_product_urls = len(product_urls)
    if args.limit > 0:
        product_urls = product_urls[: args.limit]

    inventory_rows = []
    if inventory_matcher is not None:
        try:
            inventory_rows = inventory_matcher.load_db_inventory()
        except Exception:
            inventory_rows = []

    records: list[dict] = []
    for index, url in enumerate(product_urls, start=1):
        try:
            record = extract_product_record(url, session, inventory_rows)
            records.append(record)
        except Exception as exc:
            records.append({"product_name": url.rstrip("/").split("/")[-1], "page_url": url, "error": str(exc)})
        if args.delay:
            time.sleep(args.delay)
        if index % 25 == 0:
            print(f"Procesados {index}/{len(product_urls)} productos públicos...")

    json_path = args.output_dir / "pintuco_public_products.json"
    csv_path = args.output_dir / "pintuco_public_products.csv"
    summary_path = args.output_dir / "pintuco_public_summary.json"

    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    dataframe_for_export(records).to_csv(csv_path, index=False, encoding="utf-8-sig")

    summary = {
        "product_sitemaps": product_sitemaps,
        "category_sitemaps": category_sitemaps,
        "total_product_urls_available": total_product_urls,
        "total_product_urls": len(product_urls),
        "total_category_urls": len(category_urls),
        "with_ficha_tecnica": sum(1 for item in records if item.get("technical_sheet_url")),
        "with_inventory_match": sum(1 for item in records if item.get("inventory_match_name")),
        "output_json": str(json_path),
        "output_csv": str(csv_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())