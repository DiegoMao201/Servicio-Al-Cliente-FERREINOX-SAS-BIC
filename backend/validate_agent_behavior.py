from pathlib import Path
import os
import sys
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def configure_db_env() -> None:
    secrets = tomllib.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    os.environ["DATABASE_URL"] = secrets["postgres"]["db_uri"]


def main() -> None:
    configure_db_env()

    from backend.main import (
        build_direct_reply,
        extract_technical_document_request,
        extract_product_request,
        fetch_latest_purchase_detail,
        find_cliente_contexto_by_document,
        is_greeting_message,
        is_identity_verification_message,
        lookup_product_context,
        search_technical_documents,
    )

    print("GREETING TYPO CHECK:")
    print("hola buena stardes =>", is_greeting_message("hola buena stardes"))

    verification_context = {
        "awaiting_verification": True,
        "pending_intent": "consulta_cartera",
        "last_direct_intent": "consulta_productos",
        "last_product_request": {"search_terms": ["t11"]},
    }
    print("VERIFICATION ROUTING CHECK:")
    print("1053774777 =>", is_identity_verification_message("1053774777", verification_context))

    document_context = {
        "last_product_request": extract_product_request("necesito saber si tienes inventario de 1501 viniltex en pereira")
    }
    document_request = extract_technical_document_request(
        "pintulux es la ficha tecnica que necesito",
        extract_product_request("pintulux es la ficha tecnica que necesito"),
        document_context,
    )
    document_matches = search_technical_documents(document_request)
    print("DOCUMENT REFINEMENT CHECK:")
    print(document_request)
    print([row["name"] for row in document_matches[:4]])

    product_message = "1501 en cuñete en pereira hay ?"
    product_request = extract_product_request(product_message)
    product_context = lookup_product_context(product_message, product_request)
    product_reply = build_direct_reply(
        "consulta_productos",
        None,
        product_context,
        "DiegoMao",
        product_request,
        product_message,
        {},
    )
    print("PRODUCT RESPONSE:")
    print(product_reply["response_text"])

    cliente_contexto = find_cliente_contexto_by_document("31400752")
    print("\nCLIENTE CODIGO:", cliente_contexto["cliente_codigo"] if cliente_contexto else None)
    if cliente_contexto:
        latest_purchase = fetch_latest_purchase_detail(cliente_contexto["cliente_codigo"])
        print("\nLATEST PURCHASE DETAIL:")
        print(latest_purchase)
        followup_reply = build_direct_reply(
            "consulta_compras",
            cliente_contexto,
            [],
            "DiegoMao",
            None,
            "que productos compre ese dia?",
            {
                "last_direct_intent": "consulta_compras",
                "last_purchase_date": latest_purchase["fecha_venta"] if latest_purchase else None,
            },
        )
        print("\nFOLLOWUP RESPONSE:")
        print(followup_reply["response_text"] if followup_reply else None)


if __name__ == "__main__":
    main()