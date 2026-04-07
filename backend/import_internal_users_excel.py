import argparse
import json
import re
import secrets
import sys
from pathlib import Path

import pandas as pd

ROOT_PATH = Path(__file__).resolve().parent.parent
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from backend.main import InternalBootstrapUserRequest, upsert_internal_user


EXPECTED_COLUMN_ALIASES = {
    "nombre": ["nombre", "nombre ", "empleado", "full_name"],
    "cedula": ["cedula", "cedula ", "cédula", "documento", "id"],
    "telefono": ["telefono", "telefono ", "teléfono", "celular", "phone"],
    "correo": ["correo", "correo ", "email", "mail"],
    "rol": ["rol", "cargo_rol", "role"],
    # ERP vendor code used in raw_ventas_detalle.codigo_vendedor (e.g. "154011")
    # Enables precise seller matching in BI queries without relying on name ILIKE patterns
    "codigo_vendedor": ["codigo_vendedor", "código_vendedor", "cod_vendedor", "codigovendedor", "erp_code", "vendor_code"],
}


def normalize_header(value: str):
    value = str(value or "").strip().lower()
    value = value.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    return re.sub(r"\s+", " ", value)


def resolve_column(df: pd.DataFrame, logical_name: str):
    aliases = EXPECTED_COLUMN_ALIASES.get(logical_name, [])
    normalized_map = {normalize_header(column): column for column in df.columns}
    for alias in aliases:
        if normalize_header(alias) in normalized_map:
            return normalized_map[normalize_header(alias)]
    return None


def slugify_username_seed(value: str):
    value = normalize_header(value)
    value = re.sub(r"[^a-z0-9._-]+", ".", value)
    value = re.sub(r"\.+", ".", value).strip("._-")
    return value or "usuario"


def build_username(row: dict, used_usernames: set[str]):
    email_value = str(row.get("correo") or "").strip().lower()
    if email_value and "@" in email_value:
        base = slugify_username_seed(email_value.split("@", 1)[0])
    else:
        base = slugify_username_seed(str(row.get("nombre") or "usuario"))
    username = base
    suffix = 2
    while username in used_usernames:
        username = f"{base}{suffix}"
        suffix += 1
    used_usernames.add(username)
    return username


def clean_phone(value):
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return digits or None


def clean_document(value):
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return digits or None


def load_role_overrides(path: Path | None):
    if not path:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(key).strip().lower(): str(value).strip().lower() for key, value in payload.items()}


def build_initial_password(mode: str, cedula: str, fixed_password: str | None):
    if mode == "fixed":
        if not fixed_password:
            raise SystemExit("Si usas --password-mode fixed debes enviar --fixed-password.")
        return fixed_password
    if mode == "cedula":
        return cedula if len(cedula) >= 8 else f"Fx{cedula}2025"
    return secrets.token_urlsafe(9)


def main():
    parser = argparse.ArgumentParser(description="Importa usuarios internos desde datos_empleados.xlsx hacia agent_user.")
    parser.add_argument("--excel", default="datos_empleados.xlsx", help="Ruta al archivo Excel de empleados.")
    parser.add_argument("--sheet", default=None, help="Nombre de la hoja. Si no se envía, usa la primera.")
    parser.add_argument("--default-role", default="vendedor", help="Rol por defecto para filas sin rol explícito.")
    parser.add_argument("--role-overrides-json", default=None, help="JSON opcional con overrides por correo, cédula o nombre.")
    parser.add_argument("--password-mode", choices=["random", "cedula", "fixed"], default="random", help="Modo de contraseña inicial.")
    parser.add_argument("--fixed-password", default=None, help="Contraseña fija si password-mode=fixed.")
    parser.add_argument("--dry-run", action="store_true", help="Solo prepara el payload sin escribir usuarios en base de datos.")
    parser.add_argument("--output-json", default="backend/internal_user_import_result.json", help="Archivo donde se guarda el resultado del import o dry-run.")
    args = parser.parse_args()

    excel_path = Path(args.excel)
    if not excel_path.exists():
        raise SystemExit(f"No existe el archivo: {excel_path}")

    workbook = pd.ExcelFile(excel_path)
    sheet_name = args.sheet or workbook.sheet_names[0]
    df = pd.read_excel(excel_path, sheet_name=sheet_name)

    column_map = {logical_name: resolve_column(df, logical_name) for logical_name in ["nombre", "cedula", "telefono", "correo", "rol"]}
    if not column_map["nombre"] or not column_map["cedula"]:
        raise SystemExit(f"El Excel debe traer al menos nombre y cédula. Columnas detectadas: {list(df.columns)}")

    role_overrides = load_role_overrides(Path(args.role_overrides_json)) if args.role_overrides_json else {}
    used_usernames: set[str] = set()
    processed = []

    for _, raw_row in df.iterrows():
        nombre = str(raw_row.get(column_map["nombre"]) or "").strip()
        cedula = clean_document(raw_row.get(column_map["cedula"]))
        telefono = clean_phone(raw_row.get(column_map["telefono"])) if column_map["telefono"] else None
        correo = str(raw_row.get(column_map["correo"]) or "").strip().lower() if column_map["correo"] else None
        role_value = str(raw_row.get(column_map["rol"]) or "").strip().lower() if column_map["rol"] else ""

        if not nombre or not cedula:
            continue

        override_key_candidates = [correo or "", cedula, normalize_header(nombre)]
        override_role = next((role_overrides[key] for key in override_key_candidates if key and key in role_overrides), None)
        role = override_role or role_value or args.default_role

        password = build_initial_password(args.password_mode, cedula, args.fixed_password)

        row_payload = {
            "nombre": nombre,
            "cedula": cedula,
            "telefono": telefono,
            "correo": correo,
        }
        username = build_username(row_payload, used_usernames)
        request = InternalBootstrapUserRequest(
            username=username,
            password=password,
            role=role,
            full_name=nombre,
            phone_number=telefono,
            email=correo,
            scopes=[],
        )
        if args.dry_run:
            result = {"phone_e164": request.phone_number}
        else:
            result = upsert_internal_user(request)
        processed.append(
            {
                "username": username,
                "role": role,
                "full_name": nombre,
                "phone_e164": result.get("phone_e164"),
                "email": correo,
                "temporary_password": password,
                "password_mode": args.password_mode,
            }
        )

    summary = {"sheet": sheet_name, "imported": len(processed), "dry_run": args.dry_run, "users": processed}
    output_path = Path(args.output_json)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()