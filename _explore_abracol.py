"""Explora el archivo Abracol desde Dropbox (hoja Productos)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import pandas as pd
from io import BytesIO
from frontend.config import get_dropbox_sources
from frontend.dropbox_sync_service import get_dropbox_client

# Conectar con rotacion
sources = get_dropbox_sources()
rotacion = None
for key, cfg in sources.items():
    if "rotaci" in key.lower():
        rotacion = cfg
        break

if not rotacion:
    print("ERROR: No se encontró config dropbox_rotacion")
    sys.exit(1)

dbx = get_dropbox_client(rotacion)
folder = rotacion.get("folder", "/data")

# Listar archivos
print(f"Listando carpeta: {folder}")
result = dbx.files_list_folder(folder)
abracol_path = None
for entry in result.entries:
    flag = " <<<" if "abracol" in entry.name.lower() else ""
    print(f"  {entry.name}{flag}")
    if "abracol" in entry.name.lower() and entry.name.lower().endswith((".xlsx", ".xls")):
        abracol_path = entry.path_lower

if not abracol_path:
    # Buscar recursivamente
    print("\nBuscando Abracol recursivamente...")
    search = dbx.files_search_v2("Abracol")
    for m in search.matches:
        md = m.metadata.get_metadata()
        print(f"  {md.name} -> {md.path_lower}")
        if md.name.lower().endswith((".xlsx", ".xls")):
            abracol_path = md.path_lower

if not abracol_path:
    print("ERROR: No se encontró archivo Abracol")
    sys.exit(1)

print(f"\nDescargando: {abracol_path}")
_, response = dbx.files_download(abracol_path)
content = response.content

# Explorar hojas
xls = pd.ExcelFile(BytesIO(content))
print(f"\nHojas: {xls.sheet_names}")

# Leer hoja Productos
df = pd.read_excel(BytesIO(content), sheet_name="Productos", dtype=str)
print(f"\nHoja 'Productos': {len(df)} filas x {len(df.columns)} columnas")
print(f"Columnas: {list(df.columns)}")
print(f"\nPrimeras 10 filas:")
pd.set_option('display.max_colwidth', 50)
pd.set_option('display.width', 200)
print(df.head(10).to_string())

print(f"\nValores únicos por columna:")
for col in df.columns:
    nunique = df[col].nunique()
    if nunique <= 30:
        vals = df[col].dropna().unique()[:15]
        print(f"  {col}: {nunique} únicos -> {list(vals)}")
    else:
        print(f"  {col}: {nunique} únicos (top 10: {list(df[col].value_counts().head(10).index)})")

# Guardar localmente para trabajo
df.to_csv("data/abracol_productos.csv", index=False, encoding="utf-8")
print(f"\nGuardado en data/abracol_productos.csv")
