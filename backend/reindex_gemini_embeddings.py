#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging

from ingest_technical_sheets import run_ingestion

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Reindexa chunks técnicos y perfiles multimodales con gemini-embedding-2")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra el plan sin escribir embeddings")
    parser.add_argument("--profiles-only", action="store_true", help="Reconstruye perfiles y multimodal sin reinsertar chunks")
    args = parser.parse_args()

    logger.info("Iniciando reindexación Gemini (1536 dims, chunk index + multimodal product index)")
    run_ingestion(
        full_mode=not args.dry_run,
        dry_run=args.dry_run,
        profiles_only=args.profiles_only,
        rebuild_profiles_from_db=False,
    )
    logger.info("Reindexación Gemini completada")


if __name__ == "__main__":
    main()