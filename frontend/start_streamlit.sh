#!/bin/sh
set -eu

if [ -n "${STREAMLIT_SECRETS_TOML:-}" ]; then
  mkdir -p /app/.streamlit
  case "$STREAMLIT_SECRETS_TOML" in
    *"\n"*|*"
"*)
      printf '%b\n' "$STREAMLIT_SECRETS_TOML" > /app/.streamlit/secrets.toml
      ;;
    *)
      rm -f /app/.streamlit/secrets.toml
      echo "STREAMLIT_SECRETS_TOML omitido: el valor no tiene saltos de linea validos para TOML" >&2
      ;;
  esac
fi

exec streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0