import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.main import (  # noqa: E402
    _filter_profiles_by_surface_compatibility,
    _filter_rag_candidates_by_surface_and_policy,
    _infer_surface_types_from_query,
    build_rag_context,
    extract_candidate_products_from_rag_context,
    fetch_technical_profiles,
    search_technical_chunks,
)


def trace_query(query: str, top_k: int) -> dict:
    chunks = search_technical_chunks(query, top_k=top_k)
    rag_context = build_rag_context(chunks, max_chunks=4)
    base_candidates = extract_candidate_products_from_rag_context(rag_context, original_question=query)
    surfaces = _infer_surface_types_from_query(query)
    chunk_families = list(
        dict.fromkeys(
            (chunk.get("metadata") or {}).get("canonical_family") or chunk.get("familia_producto")
            for chunk in chunks
            if chunk.get("similarity", 0) >= 0.25
        )
    )
    profiles = fetch_technical_profiles(chunk_families, limit=8)
    restricted_families = _filter_profiles_by_surface_compatibility(profiles, surfaces, query_text=query)
    final_candidates = _filter_rag_candidates_by_surface_and_policy(base_candidates, [], restricted_families)

    return {
        "query": query,
        "surfaces": surfaces,
        "chunk_families": chunk_families,
        "chunks": [
            {
                "familia": chunk.get("familia_producto"),
                "archivo": chunk.get("doc_filename"),
                "similarity": round(chunk.get("similarity", 0), 4),
            }
            for chunk in chunks
        ],
        "profiles": [
            {
                "canonical_family": profile.get("canonical_family"),
                "surface_targets": (profile.get("profile_json") or {}).get("surface_targets") or [],
                "restricted_surfaces": (profile.get("profile_json") or {}).get("restricted_surfaces") or [],
            }
            for profile in profiles
        ],
        "base_candidates": base_candidates,
        "restricted_families": restricted_families,
        "final_candidates": final_candidates,
        "rag_context_preview": rag_context[:800],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Traza el pipeline local del RAG técnico por etapas.")
    parser.add_argument("query", help="Consulta a inspeccionar.")
    parser.add_argument("--top-k", type=int, default=6, help="Cantidad de chunks a consultar.")
    args = parser.parse_args()

    result = trace_query(args.query, args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())