#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import statistics
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import create_engine, text

from backend.gemini_embeddings import generate_query_embedding
from backend.ingest_technical_sheets import get_database_url


@dataclass(frozen=True)
class StressQuery:
    query: str
    expected_terms: tuple[str, ...]
    notes: str = ""


DEFAULT_STRESS_QUERIES: list[StressQuery] = [
    StressQuery(
        query="epoxico para tanque de agua potable",
        expected_terms=("epox", "tanque", "agua potable"),
        notes="Debe privilegiar sistemas epóxicos con mención de inmersión o agua potable.",
    ),
    StressQuery(
        query="poliuretano para estructura metalica expuesta al sol",
        expected_terms=("poliuret", "metal", "sol", "estructura"),
        notes="Debe arrastrar acabados poliuretano para intemperie o UV.",
    ),
    StressQuery(
        query="pintura para piso de concreto con trafico pesado",
        expected_terms=("piso", "concreto", "trafico", "pesado"),
        notes="Debe favorecer sistemas para pisos industriales o alto tráfico.",
    ),
    StressQuery(
        query="anticorrosivo para reja galvanizada en ambiente marino",
        expected_terms=("anticorros", "galvan", "marino", "reja"),
        notes="Debe filtrar soluciones compatibles con galvanizado y alta corrosión.",
    ),
    StressQuery(
        query="impermeabilizante para muro con humedad por capilaridad",
        expected_terms=("humedad", "capilar", "muro", "imperme"),
        notes="Debe traer sistemas de humedad interior/capilaridad, no pintura decorativa genérica.",
    ),
]


@dataclass
class SearchHit:
    source: str
    rank: int
    label: str
    similarity: float
    distance: float
    matched_terms: list[str]
    matched_expected: bool
    preview: str
    filename: str


def _normalize(text_value: str) -> str:
    normalized = unicodedata.normalize("NFKD", text_value or "")
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(ascii_only.lower().split())


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    return lower_value + (upper_value - lower_value) * (position - lower)


def _safe_round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _distribution_summary(values: list[float]) -> dict:
    if not values:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "min": None,
            "p05": None,
            "p10": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "max": None,
        }
    return {
        "count": len(values),
        "avg": _safe_round(statistics.fmean(values)),
        "median": _safe_round(statistics.median(values)),
        "min": _safe_round(min(values)),
        "p05": _safe_round(_percentile(values, 0.05)),
        "p10": _safe_round(_percentile(values, 0.10)),
        "p25": _safe_round(_percentile(values, 0.25)),
        "p50": _safe_round(_percentile(values, 0.50)),
        "p75": _safe_round(_percentile(values, 0.75)),
        "p90": _safe_round(_percentile(values, 0.90)),
        "p95": _safe_round(_percentile(values, 0.95)),
        "max": _safe_round(max(values)),
    }


def _cohort_metrics(hits: list[SearchHit]) -> dict:
    positive_similarities = [hit.similarity for hit in hits if hit.matched_expected]
    negative_similarities = [hit.similarity for hit in hits if not hit.matched_expected]
    positive_distances = [hit.distance for hit in hits if hit.matched_expected]
    negative_distances = [hit.distance for hit in hits if not hit.matched_expected]
    return {
        "positives": {
            "similarity": _distribution_summary(positive_similarities),
            "distance": _distribution_summary(positive_distances),
        },
        "negatives": {
            "similarity": _distribution_summary(negative_similarities),
            "distance": _distribution_summary(negative_distances),
        },
    }


def _score_hit(source: str, rank: int, row: dict, expected_terms: tuple[str, ...]) -> SearchHit:
    label = row.get("label") or row.get("familia_producto") or row.get("canonical_family") or row.get("doc_filename") or row.get("source_doc_filename") or "?"
    preview = row.get("preview") or row.get("chunk_text") or row.get("summary_text") or ""
    haystack = _normalize(" ".join([
        label,
        preview,
        row.get("doc_filename") or "",
        row.get("source_doc_filename") or "",
    ]))
    matched_terms = [term for term in expected_terms if _normalize(term) in haystack]
    similarity = float(row.get("similarity") or 0.0)
    return SearchHit(
        source=source,
        rank=rank,
        label=label,
        similarity=similarity,
        distance=float(row.get("distance") or (1 - similarity)),
        matched_terms=matched_terms,
        matched_expected=bool(matched_terms),
        preview=(preview or "")[:220].replace("\n", " "),
        filename=row.get("doc_filename") or row.get("source_doc_filename") or "",
    )


def _fetch_technical_hits(engine, embedding_literal: str, top_k: int) -> list[dict]:
    sql = text(
        """
        SELECT
            doc_filename,
            familia_producto,
            LEFT(chunk_text, 220) AS preview,
            1 - (embedding <=> CAST(:embedding AS vector)) AS similarity,
            (embedding <=> CAST(:embedding AS vector)) AS distance
        FROM public.agent_technical_doc_chunk
        WHERE tipo_documento IN ('ficha_tecnica', 'ficha_tecnica_experto')
          AND COALESCE(metadata ->> 'document_scope', 'primary') = 'primary'
          AND COALESCE(metadata ->> 'quality_tier', 'primary') <> 'rejected'
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
        """
    )
    with engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(sql, {"embedding": embedding_literal, "top_k": top_k})]


def _fetch_multimodal_hits(engine, embedding_literal: str, top_k: int) -> list[dict]:
    sql = text(
        """
        SELECT
            source_doc_filename,
            canonical_family,
            LEFT(summary_text, 220) AS preview,
            1 - (embedding <=> CAST(:embedding AS vector)) AS similarity,
            (embedding <=> CAST(:embedding AS vector)) AS distance
        FROM public.agent_product_multimodal_index
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
        """
    )
    with engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(sql, {"embedding": embedding_literal, "top_k": top_k})]


def _suggest_threshold(hits: list[SearchHit]) -> dict:
    positives = [hit.similarity for hit in hits if hit.matched_expected]
    negatives = [hit.similarity for hit in hits if not hit.matched_expected]
    p10_positive = _percentile(positives, 0.10)
    p25_positive = _percentile(positives, 0.25)
    p90_negative = _percentile(negatives, 0.90)
    max_negative = max(negatives) if negatives else None
    min_positive = min(positives) if positives else None

    if positives and negatives:
        if min_positive is not None and max_negative is not None and min_positive > max_negative:
            suggested = (min_positive + max_negative) / 2
            rationale = "Hay separación limpia entre resultados esperados y ruido en el top-k."
        else:
            suggested = max((p90_negative or 0.0) + 0.015, (p25_positive or 0.0) - 0.02)
            rationale = "Las distribuciones se pisan; se prioriza precisión elevando el corte sobre el ruido alto."
    elif positives:
        suggested = max((p10_positive or 0.0) - 0.03, 0.0)
        rationale = "Solo aparecieron resultados plausibles; el corte se ancla al piso empírico de positivos."
    else:
        suggested = None
        rationale = "No hubo matches plausibles según términos esperados; revisa corpus o queries de calibración."

    return {
        "positives": len(positives),
        "negatives": len(negatives),
        "positive_min": _safe_round(min_positive),
        "positive_p10": _safe_round(p10_positive),
        "positive_p25": _safe_round(p25_positive),
        "negative_p90": _safe_round(p90_negative),
        "negative_max": _safe_round(max_negative),
        "suggested_threshold": _safe_round(suggested),
        "rationale": rationale,
    }


def _global_summary(hits: list[SearchHit]) -> dict:
    similarities = [hit.similarity for hit in hits]
    return {
        "count": len(hits),
        "avg_similarity": _safe_round(statistics.fmean(similarities)) if similarities else None,
        "median_similarity": _safe_round(statistics.median(similarities)) if similarities else None,
        "best_similarity": _safe_round(max(similarities)) if similarities else None,
        "worst_similarity": _safe_round(min(similarities)) if similarities else None,
    }


def _print_hit(hit: SearchHit):
    matched = ", ".join(hit.matched_terms) if hit.matched_terms else "sin match esperado"
    print(
        f"  {hit.rank}. sim={hit.similarity:.4f} dist={hit.distance:.4f} expected={str(hit.matched_expected).lower()} "
        f"label={hit.label} file={hit.filename} terms=[{matched}]"
    )
    if hit.preview:
        print(f"     preview: {hit.preview}")


def _build_queries(extra_queries: list[str]) -> list[StressQuery]:
    queries = list(DEFAULT_STRESS_QUERIES)
    for item in extra_queries:
        queries.append(StressQuery(query=item, expected_terms=tuple(), notes="Consulta ad-hoc sin términos esperados."))
    return queries


def main():
    parser = argparse.ArgumentParser(description="Audita similitud Gemini y sugiere thresholds de corte para pgvector")
    parser.add_argument("--top-k", type=int, default=3, help="Resultados por índice para cada consulta")
    parser.add_argument("--query", action="append", default=[], help="Consulta extra a evaluar")
    parser.add_argument(
        "--json-out",
        default="artifacts/rag/gemini_threshold_audit.json",
        help="Ruta donde guardar el reporte JSON",
    )
    args = parser.parse_args()

    engine = create_engine(get_database_url())
    queries = _build_queries(args.query)

    report = {
        "embedding_model": "gemini-embedding-2",
        "dimensions": 1536,
        "top_k": args.top_k,
        "queries": [],
        "thresholds": {},
    }

    all_technical_hits: list[SearchHit] = []
    all_multimodal_hits: list[SearchHit] = []

    print("=" * 88)
    print("AUDITORIA DE THRESHOLDS GEMINI")
    print("=" * 88)

    for index, stress_query in enumerate(queries, start=1):
        query_embedding = generate_query_embedding(stress_query.query)
        embedding_literal = "[" + ",".join(str(value) for value in query_embedding) + "]"
        technical_rows = _fetch_technical_hits(engine, embedding_literal, args.top_k)
        multimodal_rows = _fetch_multimodal_hits(engine, embedding_literal, args.top_k)

        technical_hits = [
            _score_hit("technical_chunks", rank, row, stress_query.expected_terms)
            for rank, row in enumerate(technical_rows, start=1)
        ]
        multimodal_hits = [
            _score_hit("product_multimodal", rank, row, stress_query.expected_terms)
            for rank, row in enumerate(multimodal_rows, start=1)
        ]

        all_technical_hits.extend(technical_hits)
        all_multimodal_hits.extend(multimodal_hits)

        print(f"\n[{index}] Query: {stress_query.query}")
        if stress_query.notes:
            print(f"     intent: {stress_query.notes}")

        print("  technical_chunks:")
        for hit in technical_hits:
            _print_hit(hit)

        print("  product_multimodal:")
        for hit in multimodal_hits:
            _print_hit(hit)

        report["queries"].append({
            "query": stress_query.query,
            "expected_terms": list(stress_query.expected_terms),
            "notes": stress_query.notes,
            "technical_hits": [asdict(hit) for hit in technical_hits],
            "multimodal_hits": [asdict(hit) for hit in multimodal_hits],
        })

    report["thresholds"] = {
        "technical_chunks": {
            **_global_summary(all_technical_hits),
            "cohorts": _cohort_metrics(all_technical_hits),
            **_suggest_threshold(all_technical_hits),
        },
        "product_multimodal": {
            **_global_summary(all_multimodal_hits),
            "cohorts": _cohort_metrics(all_multimodal_hits),
            **_suggest_threshold(all_multimodal_hits),
        },
        "global_recommended_threshold": max(
            value
            for value in [
                _suggest_threshold(all_technical_hits).get("suggested_threshold"),
                _suggest_threshold(all_multimodal_hits).get("suggested_threshold"),
            ]
            if value is not None
        ) if any(
            value is not None
            for value in [
                _suggest_threshold(all_technical_hits).get("suggested_threshold"),
                _suggest_threshold(all_multimodal_hits).get("suggested_threshold"),
            ]
        ) else None,
    }

    print("\n" + "=" * 88)
    print("RESUMEN DE THRESHOLDS")
    print("=" * 88)
    for index_name in ("technical_chunks", "product_multimodal"):
        summary = report["thresholds"][index_name]
        print(
            f"{index_name}: suggested={summary['suggested_threshold']} avg={summary['avg_similarity']} "
            f"median={summary['median_similarity']} pos={summary['positives']} neg={summary['negatives']}"
        )
        positive_similarity = summary["cohorts"]["positives"]["similarity"]
        negative_similarity = summary["cohorts"]["negatives"]["similarity"]
        positive_distance = summary["cohorts"]["positives"]["distance"]
        negative_distance = summary["cohorts"]["negatives"]["distance"]
        print(
            "  positives_similarity: "
            f"avg={positive_similarity['avg']} p10={positive_similarity['p10']} p25={positive_similarity['p25']} "
            f"p50={positive_similarity['p50']} p75={positive_similarity['p75']} p90={positive_similarity['p90']}"
        )
        print(
            "  negatives_similarity: "
            f"avg={negative_similarity['avg']} p10={negative_similarity['p10']} p25={negative_similarity['p25']} "
            f"p50={negative_similarity['p50']} p75={negative_similarity['p75']} p90={negative_similarity['p90']}"
        )
        print(
            "  positives_distance: "
            f"avg={positive_distance['avg']} p10={positive_distance['p10']} p25={positive_distance['p25']} "
            f"p50={positive_distance['p50']} p75={positive_distance['p75']} p90={positive_distance['p90']}"
        )
        print(
            "  negatives_distance: "
            f"avg={negative_distance['avg']} p10={negative_distance['p10']} p25={negative_distance['p25']} "
            f"p50={negative_distance['p50']} p75={negative_distance['p75']} p90={negative_distance['p90']}"
        )
        print(f"  rationale: {summary['rationale']}")
    print(f"global_recommended_threshold: {report['thresholds']['global_recommended_threshold']}")

    output_path = Path(args.json_out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"reporte_json: {output_path}")


if __name__ == "__main__":
    main()