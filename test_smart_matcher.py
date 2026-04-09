"""End-to-end test of the Smart Matcher engine."""
import sys, os, time
sys.path.insert(0, ".")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:o5S3X9VIYcbBWqd525hqT24UhYAc8AdjtevyHtlZHhGxJkfMQVZXReCTxkcjSOAX@192.81.216.49:3000/postgres",
)
from sqlalchemy import create_engine
from backend.main import (
    fetch_rotation_cache,
    fetch_smart_product_rows,
    spanish_phonetic_key,
    spanish_phonetic_similarity,
    detect_brand_anchor,
    lookup_product_context,
    prepare_product_request_for_search,
    expand_search_terms_with_variants,
)

engine = create_engine(os.environ["DATABASE_URL"])

# 1. Rotation cache (test TTL caching)
with engine.connect() as conn:
    t0 = time.time()
    cache = fetch_rotation_cache(conn)
    t1 = time.time()
    print(f"Rotation cache: {len(cache)} products ({(t1-t0)*1000:.0f}ms)")
    # Second call should be instant (cached)
    t2 = time.time()
    cache2 = fetch_rotation_cache(conn)
    t3 = time.time()
    print(f"Rotation cache (cached): {len(cache2)} products ({(t3-t2)*1000:.0f}ms)")

    # 2. Abbreviation variants
    print("\n--- Abbreviation variants ---")
    variants = expand_search_terms_with_variants(["PROFESIONAL", "GOYA", "BROCHA"])
    print(f"  PROFESIONAL+GOYA+BROCHA -> {variants}")

    # 3. CRITICAL TEST: brocha profesional goya 3 — must find BOTH "PROFESIONAL" and "PROF." entries
    print("\n--- brocha profesional goya 3 (MUST find PROF. entries) ---")
    t0 = time.time()
    results = fetch_smart_product_rows(conn, "brocha profesional goya 3", ["BROCHA", "PROFESIONAL", "GOYA", "3"], {}, [], 15)
    t1 = time.time()
    print(f"  {len(results)} results ({(t1-t0)*1000:.0f}ms)")
    for r in results[:8]:
        code = r.get("producto_codigo", r.get("referencia", "?"))
        desc = r.get("descripcion", "?")
        ms = r.get("match_score", 0)
        ro = r.get("rotation_score", 0)
        print(f"  {code}: {desc} | match={ms} rot={ro:.3f}")
    # Verify PROF. entries are included
    descs = [r.get("descripcion", "").upper() for r in results]
    has_prof_dot = any("PROF." in d for d in descs)
    has_profesional = any("PROFESIONAL" in d for d in descs)
    print(f"  Has PROF. entries: {has_prof_dot}")
    print(f"  Has PROFESIONAL entries: {has_profesional}")

    # 4. brocha popular goya — must NOT return professional
    print("\n--- brocha popular goya 2 ---")
    results_pop = fetch_smart_product_rows(conn, "brocha popular goya 2", ["BROCHA", "POPULAR", "GOYA", "2"], {}, [], 10)
    print(f"  {len(results_pop)} results")
    for r in results_pop[:5]:
        code = r.get("producto_codigo", r.get("referencia", "?"))
        desc = r.get("descripcion", "?")
        ms = r.get("match_score", 0)
        print(f"  {code}: {desc} | match={ms}")

    # 5. Speed test: full lookup_product_context
    print("\n--- Speed: lookup_product_context ---")
    test_queries = [
        "8 galones viniltex blanco 1501",
        "9 cuartos barniz sd1 brillante",
        "2 galones pintulux 3en1 blanco t-11",
        "brocha profesional goya 3",
        "rodillo felpa 9",
    ]
    for q in test_queries:
        t0 = time.time()
        rows = lookup_product_context(q, prepare_product_request_for_search(q))
        t1 = time.time()
        top = rows[0].get("descripcion", "?") if rows else "NO RESULTS"
        print(f"  '{q}' -> {len(rows)} results, {(t1-t0)*1000:.0f}ms | top: {top}")

print("\nDONE")
