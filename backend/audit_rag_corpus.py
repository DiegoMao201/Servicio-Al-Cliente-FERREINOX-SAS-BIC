#!/usr/bin/env python3
"""Auditoría de corpus RAG técnico antes de reingesta.

Lista PDFs desde Dropbox, aplica la misma canonización/deduplicación de la ingesta
y genera un reporte claro de:
 - fichas técnicas canónicas supervivientes
 - grupos duplicados
 - documentos secundarios descartados
"""

from __future__ import annotations

import json
from pathlib import Path

from ingest_technical_sheets import (
    build_corpus_report,
    curate_pdf_entries,
    get_dropbox_client,
    list_dropbox_pdfs,
)


def main():
    dbx = get_dropbox_client()
    pdf_entries = list_dropbox_pdfs(dbx)
    curated_entries, duplicate_groups, skipped_entries = curate_pdf_entries(pdf_entries)
    report = build_corpus_report(curated_entries, duplicate_groups, skipped_entries)

    output_dir = Path(__file__).resolve().parent.parent / "artifacts" / "rag"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "rag_corpus_audit.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 80)
    print("AUDITORÍA DE CORPUS RAG")
    print("=" * 80)
    print(f"PDFs detectados: {len(pdf_entries)}")
    print(f"Fichas técnicas canónicas: {report['curated_documents']}")
    print(f"Grupos duplicados: {report['duplicate_groups']}")
    print(f"Duplicados eliminables: {report['duplicates_removed']}")
    print(f"Documentos omitidos: {report['skipped_documents']}")
    print(f"Reporte: {output_path}")

    if duplicate_groups:
        print("\nTop duplicados:")
        for group in duplicate_groups[:15]:
            print(f"- {group['canonical_family']} -> survivor={group['survivor']} | dupes={len(group['duplicates'])}")

    if skipped_entries:
        print("\nTop omitidos:")
        for item in skipped_entries[:15]:
            print(f"- {item['reason']}: {item['name']}")


if __name__ == "__main__":
    main()