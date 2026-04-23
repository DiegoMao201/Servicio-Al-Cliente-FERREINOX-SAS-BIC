import argparse
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.main import admin_rag_buscar  # noqa: E402

REMOTE_URL = "https://apicrm.datovatenexuspro.com/admin/rag-buscar"
ADMIN_KEY = "ferreinox_admin_2024"


def query_remote(query: str, top_k: int) -> dict:
    response = requests.get(
        REMOTE_URL,
        params={"q": query, "top_k": top_k},
        headers={"x-admin-key": ADMIN_KEY},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def query_local(query: str, top_k: int) -> dict:
    return admin_rag_buscar(q=query, top_k=top_k, producto="", admin_key=ADMIN_KEY)


def compact(payload: dict) -> dict:
    return {
        "productos_candidatos": payload.get("productos_candidatos") or [],
        "top_families": [item.get("familia") for item in (payload.get("resultados") or [])[:6]],
        "top_files": [item.get("archivo") for item in (payload.get("resultados") or [])[:6]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compara la salida local del pipeline RAG con el endpoint remoto publicado.")
    parser.add_argument("query", help="Consulta a comparar.")
    parser.add_argument("--top-k", type=int, default=6)
    args = parser.parse_args()

    remote = query_remote(args.query, args.top_k)
    local = query_local(args.query, args.top_k)

    print(json.dumps({
        "query": args.query,
        "remote": compact(remote),
        "local": compact(local),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())