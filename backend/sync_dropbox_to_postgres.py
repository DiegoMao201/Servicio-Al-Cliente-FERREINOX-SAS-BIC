import os
import dropbox
import pandas as pd
import psycopg2
from io import BytesIO

# Configuración
DROPBOX_ACCESS_TOKEN = os.getenv('DROPBOX_ACCESS_TOKEN', 'TU_TOKEN_DROPBOX')
DROPBOX_FOLDER = '/carpeta_ejemplo'  # Cambia por la ruta de tu carpeta en Dropbox
POSTGRES_CONFIG = {
    'host': 'TU_HOST',
    'port': 5432,
    'dbname': 'TU_DB',
    'user': 'TU_USUARIO',
    'password': 'TU_PASSWORD'
}

def get_dropbox_client():
    return dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def list_csv_files(dbx, folder):
    files = dbx.files_list_folder(folder).entries
    return [f for f in files if isinstance(f, dropbox.files.FileMetadata) and f.name.endswith('.csv')]

def download_csv(dbx, file_path):
    _, res = dbx.files_download(file_path)
    return pd.read_csv(BytesIO(res.content))

def upload_to_postgres(df, table_name, conn):
    # Asume que la tabla ya existe y tiene las columnas correctas
    cursor = conn.cursor()
    for _, row in df.iterrows():
        placeholders = ','.join(['%s'] * len(row))
        sql = f"INSERT INTO {table_name} VALUES ({placeholders}) ON CONFLICT DO NOTHING;"
        cursor.execute(sql, tuple(row))
    conn.commit()
    cursor.close()

def main():
    dbx = get_dropbox_client()
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    csv_files = list_csv_files(dbx, DROPBOX_FOLDER)
    for file in csv_files:
        print(f"Procesando {file.name}")
        df = download_csv(dbx, file.path_lower)
        table_name = os.path.splitext(file.name)[0].lower()
        upload_to_postgres(df, table_name, conn)
    conn.close()

if __name__ == "__main__":
    main()
