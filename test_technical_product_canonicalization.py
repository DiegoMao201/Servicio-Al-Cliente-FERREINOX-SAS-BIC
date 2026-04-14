from backend.technical_product_canonicalization import canonicalize_technical_product_term


def test_viniltex_banos_fragment_canonicalizes_full_family():
    resolved = canonicalize_technical_product_term("Viniltex Baños")
    assert resolved is not None
    assert resolved["canonical_label"] == "Viniltex Baños y Cocinas"
    assert resolved["preferred_lookup_text"] == "viniltex byc blanco 2001"


def test_viniltex_byc_inventory_phrase_canonicalizes_full_family():
    resolved = canonicalize_technical_product_term("PQ VINILTEX BYC SA BLANCO 2001 3.79L")
    assert resolved is not None
    assert resolved["canonical_label"] == "Viniltex Baños y Cocinas"
    assert resolved["preferred_lookup_text"] == "viniltex byc blanco 2001"


def test_aquablock_guide_phrase_canonicalizes_family():
    resolved = canonicalize_technical_product_term("Aquablock / Aquablock Ultra según presión negativa y severidad.")
    assert resolved is not None
    assert resolved["canonical_label"] == "Aquablock"
    assert resolved["preferred_lookup_text"] == "aquablock ultra"


def test_estuco_prof_ext_alias_canonicalizes_estuco_acrilico_exterior():
    resolved = canonicalize_technical_product_term("Aplicar estuco prof ext blanco después del Aquablock")
    assert resolved is not None
    assert resolved["canonical_label"] == "ESTUCO ACRILICO EXTERIOR"
    assert resolved["preferred_lookup_text"] == "PQ ESTUCO PROF EXT BL 27060 18.93L 30K"


def test_interthane_with_catalyst_canonicalizes_lookup():
    resolved = canonicalize_technical_product_term("Interthane 990 + Catalizador")
    assert resolved is not None
    assert resolved["canonical_label"] == "Interthane 990 + Catalizador"
    assert resolved["preferred_lookup_text"] == "interthane 990"


def test_generic_fragment_is_ignored():
    assert canonicalize_technical_product_term("Cocinas") is None