#!/bin/sh
set -eu

if [ -n "${STREAMLIT_SECRETS_TOML:-}" ]; then
  mkdir -p /app/.streamlit
  printf '%s\n' "$STREAMLIT_SECRETS_TOML" > /app/.streamlit/secrets.toml
fi

exec streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0