from pathlib import Path
import os
import sys
import tomllib


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
        extract_product_request,
        fetch_latest_purchase_detail,
        find_cliente_contexto_by_document,
        lookup_product_context,
    )

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