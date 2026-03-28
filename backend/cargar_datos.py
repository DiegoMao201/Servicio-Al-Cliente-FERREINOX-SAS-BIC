import pandas as pd
from sqlalchemy import create_engine
import os
import glob
import csv

# --- CONFIGURACIÓN BASE DE DATOS ---
def get_database_url():
    """Obtiene la conexión desde DATABASE_URL o variables DB_* del entorno."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "db")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "ferreinox_db")

    if not db_user or not db_password:
        raise RuntimeError("Faltan variables DB_USER/DB_PASSWORD o DATABASE_URL para conectar a PostgreSQL.")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


engine = create_engine(get_database_url())

def limpiar_columna(col):
    """Limpia nombres de columnas para SQL"""
    # Se eliminan caracteres que rompen las bases de datos
    return str(col).strip().lower().replace(" ", "_").replace("ñ", "n").replace(".", "").replace("/", "_").replace("(", "").replace(")", "").replace("{", "").replace("}", "")

def cargar_csv_multiformato(archivo):
    """
    Prueba múltiples separadores y codificaciones hasta que uno funcione.
    """
    # Lista de intentos: (Separador, Encoding)
    intentos = [
        (';', 'latin-1'),  # Excel Colombia
        ('|', 'latin-1'),  # Pipes
        ('{', 'latin-1'),  # ¡Tus archivos con llaves!
        (';', 'utf-8'),    
        ('|', 'utf-8'),
        ('{', 'utf-8'),
        (',', 'utf-8'),    # Estándar internacional
        ('\t', 'utf-16'),  # Copiar/Pegar Excel
    ]

    for sep, enc in intentos:
        try:
            print(f"   ...Probando: Separador='{sep}' | Encoding='{enc}'")
            
            # Leemos el archivo
            df = pd.read_csv(
                archivo, 
                sep=sep, 
                encoding=enc,
                on_bad_lines='skip', # Ignora líneas rotas
                low_memory=False
            )
            
            # PRUEBA DE FUEGO: Si tiene más de 1 columna, encontramos el formato correcto
            if df.shape[1] > 1:
                print(f"   ✅ ¡Detectado! Formato correcto: Separador '{sep}'")
                return df
            
        except Exception:
            continue # Si falla, prueba el siguiente
            
    return None

def main():
    print("--- INICIANDO CARGA UNIVERSAL (Soporte ;, |, {) ---")
    
    # Busca todos los archivos
    archivos = glob.glob("*.xlsx") + glob.glob("*.xls") + glob.glob("*.csv")

    if not archivos:
        print("❌ No encontré archivos en la carpeta backend.")

    for archivo in archivos:
        print(f"\n📂 Procesando archivo: {archivo}...")
        
        try:
            df = None
            
            # A. Estrategia para Excel
            if archivo.endswith(".xlsx") or archivo.endswith(".xls"):
                df = pd.read_excel(archivo)
                
            # B. Estrategia para CSV / Texto Plano
            elif archivo.endswith(".csv"):
                df = cargar_csv_multiformato(archivo)
                
            # C. Si logramos leer algo...
            if df is not None:
                # Limpieza de cabeceras
                df.columns = [limpiar_columna(c) for c in df.columns]
                
                # Nombre de tabla limpio
                nombre_tabla = os.path.splitext(archivo)[0].lower().replace(" ", "_")
                
                # Inyectar a PostgreSQL
                print(f"   💾 Guardando en base de datos tabla '{nombre_tabla}'...")
                df.to_sql(nombre_tabla, engine, if_exists='replace', index=False, chunksize=5000)
                
                print(f"   ✨ ÉXITO: {len(df)} registros cargados en '{nombre_tabla}'.")
            else:
                print(f"   ❌ FALLÓ: No pude leer {archivo}. Verifica que no esté vacío.")

        except Exception as e:
            print(f"   ⛔ Error Crítico en {archivo}: {e}")

    print("\n--- PROCESO FINALIZADO ---")

if __name__ == "__main__":
    main()