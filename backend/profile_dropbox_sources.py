import csv
import json
from collections import Counter
from io import StringIO
from pathlib import Path
from statistics import mean
import tomllib

import dropbox
import pandas as pd


ENCODINGS = ["utf-8", "latin1", "cp1252"]
DELIMITERS = [",", "|", ";", "\t", "{"]
SECRETS_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
JSON_REPORT_PATH = Path(__file__).resolve().parent / "dropbox_profile_report.json"
MARKDOWN_REPORT_PATH = Path(__file__).resolve().parent / "dropbox_profile_report.md"
SOURCE_LABELS = {
    "dropbox_rotacion": "Rotación Inventarios",
    "dropbox_cartera": "Cartera Ferreinox",
    "dropbox_ventas": "Ventas Ferreinox",
}


def load_secrets():
    """Carga secrets.toml local para perfilar Dropbox fuera de Streamlit."""
    if not SECRETS_PATH.exists():
        raise FileNotFoundError(f"No se encontró el archivo de secrets: {SECRETS_PATH}")
    return tomllib.loads(SECRETS_PATH.read_text(encoding="utf-8"))


def get_dropbox_client(config):
    """Construye cliente Dropbox autenticado sin exponer credenciales."""
    return dropbox.Dropbox(
        oauth2_refresh_token=config["refresh_token"],
        app_key=config["app_key"],
        app_secret=config["app_secret"],
    )


def detect_delimiter(text_content):
    """Detecta delimitador preferido del archivo."""
    sample = text_content[:2048]
    try:
        return csv.Sniffer().sniff(sample, delimiters=DELIMITERS).delimiter
    except Exception:
        return ","


def profile_delimiter_shape(text_content, delimiter):
    """Mide la forma del archivo con un delimitador dado usando csv.reader."""
    reader = csv.reader(StringIO(text_content), delimiter=delimiter)
    widths = []
    sample_rows = []
    for index, row in enumerate(reader):
        widths.append(len(row))
        if index < 5:
            sample_rows.append([str(value) for value in row])
    width_counter = Counter(widths)
    most_common_width, most_common_count = width_counter.most_common(1)[0] if width_counter else (0, 0)
    bad_rows = sum(count for width, count in width_counter.items() if width != most_common_width)
    return {
        "delimiter": delimiter,
        "row_count": len(widths),
        "most_common_width": most_common_width,
        "most_common_ratio": (most_common_count / len(widths)) if widths else 0,
        "bad_rows": bad_rows,
        "sample_rows": sample_rows,
    }


def detect_best_delimiter(text_content):
    """Elige el delimitador más consistente aunque existan filas irregulares."""
    candidates = [profile_delimiter_shape(text_content, delimiter) for delimiter in DELIMITERS]
    candidates.sort(key=lambda item: (item["most_common_width"], item["most_common_ratio"], -item["bad_rows"]), reverse=True)
    return candidates[0], candidates


def analyze_header_candidate(first_row):
    """Heurística simple para estimar si la primera fila parece encabezado."""
    cleaned = [str(value).strip() for value in first_row]
    non_empty = [value for value in cleaned if value]
    if not non_empty:
        return False

    unique_ratio = len(set(non_empty)) / max(len(non_empty), 1)
    alpha_ratio = mean(1 if any(char.isalpha() for char in value) else 0 for value in non_empty)
    numeric_ratio = mean(1 if value.replace(".", "", 1).replace(",", "", 1).isdigit() else 0 for value in non_empty)
    return unique_ratio >= 0.9 and alpha_ratio >= 0.6 and numeric_ratio <= 0.3


def profile_csv_file(dbx, entry):
    """Descarga un CSV y devuelve perfil técnico y de contenido."""
    _, response = dbx.files_download(entry.path_lower)
    content = response.content

    for encoding in ENCODINGS:
        try:
            text_content = content.decode(encoding)
            detected = detect_delimiter(text_content)
            best_profile, all_profiles = detect_best_delimiter(text_content)
            delimiter = best_profile["delimiter"] or detected
            raw_df = pd.read_csv(StringIO(text_content), sep=delimiter, header=None, engine="python", on_bad_lines="warn")
            first_row = raw_df.iloc[0].fillna("").astype(str).tolist() if not raw_df.empty else []
            has_header_candidate = analyze_header_candidate(first_row)
            header_df = pd.read_csv(StringIO(text_content), sep=delimiter, header=0, engine="python", on_bad_lines="skip") if has_header_candidate else None

            return {
                "file_name": entry.name,
                "file_path": entry.path_lower,
                "encoding": encoding,
                "delimiter": delimiter,
                "delimiter_profiles": all_profiles,
                "row_count_raw": int(len(raw_df)),
                "column_count_raw": int(len(raw_df.columns)),
                "irregular_rows_estimate": int(best_profile["bad_rows"]),
                "first_row": first_row,
                "suggested_has_header": has_header_candidate,
                "suggested_columns": [str(column) for column in header_df.columns] if has_header_candidate and header_df is not None else [],
                "sample_rows_raw": raw_df.head(5).fillna("").astype(str).values.tolist(),
            }
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            return {
                "file_name": entry.name,
                "file_path": entry.path_lower,
                "error": str(exc),
            }

    return {
        "file_name": entry.name,
        "file_path": entry.path_lower,
        "error": "No se pudo decodificar el archivo con utf-8, latin1 o cp1252.",
    }


def build_markdown_report(report):
    """Convierte el perfil recolectado en un resumen Markdown legible."""
    lines = ["# Dropbox Profile Report", ""]
    for source in report["sources"]:
        lines.append(f"## {source['source_label']}")
        lines.append("")
        lines.append(f"- Folder: {source['folder']}")
        lines.append(f"- CSV files: {len(source['files'])}")
        lines.append("")
        for file_profile in source["files"]:
            lines.append(f"### {file_profile['file_name']}")
            lines.append("")
            if "error" in file_profile:
                lines.append(f"- Error: {file_profile['error']}")
                lines.append("")
                continue
            lines.append(f"- Path: {file_profile['file_path']}")
            lines.append(f"- Encoding: {file_profile['encoding']}")
            lines.append(f"- Delimiter: {repr(file_profile['delimiter'])}")
            lines.append(f"- Rows (raw): {file_profile['row_count_raw']}")
            lines.append(f"- Columns (raw): {file_profile['column_count_raw']}")
            lines.append(f"- Irregular rows estimate: {file_profile['irregular_rows_estimate']}")
            lines.append(f"- Suggested has header: {file_profile['suggested_has_header']}")
            if file_profile["suggested_columns"]:
                lines.append(f"- Suggested columns: {', '.join(file_profile['suggested_columns'])}")
            lines.append("- First row values:")
            lines.append(f"  {file_profile['first_row']}")
            lines.append("- Sample rows:")
            for sample_row in file_profile["sample_rows_raw"]:
                lines.append(f"  {sample_row}")
            lines.append("")
    return "\n".join(lines)


def main():
    secrets = load_secrets()
    report = {"sources": []}

    for secret_name, source_label in SOURCE_LABELS.items():
        if secret_name not in secrets:
            continue
        config = secrets[secret_name]
        dbx = get_dropbox_client(config)
        folder = config.get("folder", "/")
        entries = dbx.files_list_folder(folder).entries
        csv_entries = [entry for entry in entries if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith(".csv")]

        source_report = {
            "source_label": source_label,
            "folder": folder,
            "files": [profile_csv_file(dbx, entry) for entry in csv_entries],
        }
        report["sources"].append(source_report)

    JSON_REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    MARKDOWN_REPORT_PATH.write_text(build_markdown_report(report), encoding="utf-8")
    print(f"JSON report: {JSON_REPORT_PATH}")
    print(f"Markdown report: {MARKDOWN_REPORT_PATH}")


if __name__ == "__main__":
    main()