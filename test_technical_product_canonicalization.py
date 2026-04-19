from tests.internal.test_technical_product_canonicalization import *
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