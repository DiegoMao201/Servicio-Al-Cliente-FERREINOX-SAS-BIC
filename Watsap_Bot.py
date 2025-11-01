# -*- coding: utf-8 -*-
import os
import json
import requests
import logging
import threading
import gspread
import tempfile
import glob
import re
import unicodedata
import dropbox
from io import StringIO, BytesIO
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime
from flask import Flask, request, make_response
import google.generativeai as genai

# --- CONFIGURACIÓN DE LOGGING Y FLASK ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)

# ----------------------------------------------------------------------
## 🔑 CARGAR VARIABLES DE ENTORNO
# ----------------------------------------------------------------------

# --- WhatsApp (Webhooks) ---
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')

# --- Gemini ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# --- Dropbox (Cartera y Base de Clientes) ---
DBX_APP_KEY_CARTERA = os.environ.get('DBX_APP_KEY_CARTERA')
DBX_APP_SECRET_CARTERA = os.environ.get('DBX_APP_SECRET_CARTERA')
DBX_REFRESH_TOKEN_CARTERA = os.environ.get('DBX_REFRESH_TOKEN_CARTERA')
DBX_FILE_PATH_CARTERA = os.environ.get('DBX_FILE_PATH_CARTERA')
DBX_FILE_PATH_BASE_CLIENTES = os.environ.get('DBX_FILE_PATH_BASE_CLIENTES') # ¡NUEVO!

# --- Dropbox (Inventario) ---
DBX_APP_KEY_INVENTARIO = os.environ.get('DBX_APP_KEY_INVENTARIO')
DBX_APP_SECRET_INVENTARIO = os.environ.get('DBX_APP_SECRET_INVENTARIO')
DBX_REFRESH_TOKEN_INVENTARIO = os.environ.get('DBX_REFRESH_TOKEN_INVENTARIO')
DBX_FILE_PATH_INVENTARIO = os.environ.get('DBX_FILE_PATH_INVENTARIO')
DBX_FILE_PATH_PROVEEDORES = os.environ.get('DBX_FILE_PATH_PROVEEDORES')

# --- Dropbox (Ventas) ---
DBX_APP_KEY_VENTAS = os.environ.get('DBX_APP_KEY_VENTAS')
DBX_APP_SECRET_VENTAS = os.environ.get('DBX_APP_SECRET_VENTAS')
DBX_REFRESH_TOKEN_VENTAS = os.environ.get('DBX_REFRESH_TOKEN_VENTAS')
DBX_FILE_PATH_VENTAS = os.environ.get('DBX_FILE_PATH_VENTAS')
DBX_FILE_PATH_COBROS = os.environ.get('DBX_FILE_PATH_COBROS')
DBX_FILE_PATH_CL4 = os.environ.get('DBX_FILE_PATH_CL4')

# --- Google Sheets (Credencial Única) ---
GCP_JSON_STR = os.environ.get('GCP_SERVICE_ACCOUNT_JSON')

# --- Google Sheets (Log de Chat) ---
GOOGLE_SHEET_NAME_LOG = os.environ.get('GOOGLE_SHEET_NAME')
GOOGLE_WORKSHEET_NAME_LOG = os.environ.get('GOOGLE_WORKSHEET_NAME')

# --- Google Sheets (Maestro de Productos) ---
GOOGLE_SHEET_NAME_PRODUCTOS = os.environ.get('GOOGLE_SHEET_NAME_PRODUCTOS')
GOOGLE_WORKSHEET_NAME_PRODUCTOS = os.environ.get('GOOGLE_WORKSHEET_NAME_PRODUCTOS')

# --- Google Sheets (Usuarios y Consentimiento) ---
GOOGLE_SHEET_NAME_USUARIOS = os.environ.get('GOOGLE_SHEET_NAME_USUARIOS') # ¡NUEVO!
GOOGLE_WORKSHEET_NAME_USUARIOS = os.environ.get('GOOGLE_WORKSHEET_NAME_USUARIOS') # ¡NUEVO!


# ----------------------------------------------------------------------
## 💾 ESTADO EN MEMORIA (CACHE GLOBAL)
# ----------------------------------------------------------------------
user_chats = {}
processed_message_ids = set()
consented_users = set() # ¡NUEVO! Cache para usuarios que dieron permiso

# --- Caches de Datos de Negocio ---
CARTERA_PROCESADA_DF = pd.DataFrame()
BASE_CLIENTES_DF = pd.DataFrame() # ¡NUEVO!
INVENTARIO_ANALIZADO_DF = pd.DataFrame()
PROVEEDORES_DF = pd.DataFrame()
VENTAS_DF = pd.DataFrame()
COBROS_DF = pd.DataFrame()
CL4_DF = pd.DataFrame()
PRODUCTOS_MAESTRO_DF = pd.DataFrame()

# ----------------------------------------------------------------------
## 📊 INICIALIZACIÓN DE GOOGLE SHEETS (ACTUALIZADO)
# ----------------------------------------------------------------------
worksheet_log = None
worksheet_productos = None
worksheet_usuarios = None # ¡NUEVO!
temp_creds_file_path = None

def init_google_sheets():
    """Inicializa la conexión a las TRES Hojas de Google (Log, Productos, Usuarios)."""
    global worksheet_log, worksheet_productos, worksheet_usuarios, temp_creds_file_path, consented_users
    
    if not GCP_JSON_STR:
        app.logger.warning("GCP_SERVICE_ACCOUNT_JSON no configurado. Google Sheets está desactivado.")
        return

    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(GCP_JSON_STR)
            temp_creds_file_path = temp_file.name
        
        client_gspread = gspread.service_account(filename=temp_creds_file_path)

        # 1. Conectar al Log de Chats
        if GOOGLE_SHEET_NAME_LOG and GOOGLE_WORKSHEET_NAME_LOG:
            sheet_log = client_gspread.open(GOOGLE_SHEET_NAME_LOG)
            worksheet_log = sheet_log.worksheet(GOOGLE_WORKSHEET_NAME_LOG)
            if not worksheet_log.get_all_values():
                worksheet_log.append_row(["Timestamp", "Numero_Usuario", "Mensaje_Usuario", "Respuesta_Bot", "Herramienta_Usada"])
            app.logger.info(f"Conectado a Google Sheets (Log): {GOOGLE_SHEET_NAME_LOG}")
        else:
            app.logger.warning("Variables de Log de Google Sheets no configuradas.")

        # 2. Conectar al Maestro de Productos
        if GOOGLE_SHEET_NAME_PRODUCTOS and GOOGLE_WORKSHEET_NAME_PRODUCTOS:
            sheet_productos = client_gspread.open(GOOGLE_SHEET_NAME_PRODUCTOS)
            worksheet_productos = sheet_productos.worksheet(GOOGLE_WORKSHEET_NAME_PRODUCTOS)
            app.logger.info(f"Conectado a Google Sheets (Productos): {GOOGLE_SHEET_NAME_PRODUCTOS}")
        else:
            app.logger.warning("Variables de Productos de Google Sheets no configuradas.")

        # 3. Conectar a la Base de Usuarios (Consentimiento)
        if GOOGLE_SHEET_NAME_USUARIOS and GOOGLE_WORKSHEET_NAME_USUARIOS:
            sheet_usuarios = client_gspread.open(GOOGLE_SHEET_NAME_USUARIOS)
            worksheet_usuarios = sheet_usuarios.worksheet(GOOGLE_WORKSHEET_NAME_USUARIOS)
            
            # Poblar el cache de usuarios con consentimiento
            records = worksheet_usuarios.get_all_values()
            if not records:
                worksheet_usuarios.append_row(["Timestamp", "Telefono"])
                app.logger.info("Hoja de Usuarios (Consentimiento) inicializada.")
            else:
                # Cargar todos los teléfonos (columna 2, índice 1) excepto el encabezado
                consented_users.update([row[1] for row in records[1:] if len(row) > 1])
                app.logger.info(f"Cargados {len(consented_users)} usuarios con consentimiento desde GSheets.")
        else:
            app.logger.warning("Variables de Usuarios (Consentimiento) de Google Sheets no configuradas. El bot no funcionará.")

    except Exception as e:
        app.logger.error(f"Error al inicializar Google Sheets: {e}")
    finally:
        if temp_creds_file_path and os.path.exists(temp_creds_file_path):
            os.remove(temp_creds_file_path)
            temp_creds_file_path = None

# ----------------------------------------------------------------------
## 🗃️ LÓGICA DE CARGA DE DATOS (ACTUALIZADA)
# ----------------------------------------------------------------------

def normalizar_nombre(nombre: str) -> str:
    if not isinstance(nombre, str): return ""
    nombre = nombre.upper().strip().replace('.', '')
    nombre = ''.join(c for c in unicodedata.normalize('NFD', nombre) if unicodedata.category(c) != 'Mn')
    return ' '.join(nombre.split())

def _conectar_y_descargar_dropbox(app_key, app_secret, refresh_token, file_path) -> BytesIO | None:
    """Función genérica para descargar un archivo de Dropbox."""
    if not all([app_key, app_secret, refresh_token, file_path]):
        app.logger.error(f"Credenciales de Dropbox incompletas para el archivo: {file_path}.")
        return None
    
    try:
        with dropbox.Dropbox(app_key=app_key, app_secret=app_secret, oauth2_refresh_token=refresh_token) as dbx:
            metadata, res = dbx.files_download(path=file_path)
            return BytesIO(res.content)
    except Exception as e:
        app.logger.error(f"Error al descargar {file_path} desde Dropbox: {e}")
        return None

# --- LÓGICA DE CARTERA ---
def procesar_cartera(df: pd.DataFrame) -> pd.DataFrame:
    df_proc = df.copy()
    df_proc.rename(columns=lambda x: normalizar_nombre(x).lower().replace(' ', '_'), inplace=True)
    df_proc['importe'] = pd.to_numeric(df_proc['importe'], errors='coerce').fillna(0)
    df_proc['numero'] = pd.to_numeric(df_proc['numero'], errors='coerce').fillna(0)
    df_proc.loc[df_proc['numero'] < 0, 'importe'] *= -1
    df_proc['dias_vencido'] = pd.to_numeric(df_proc['dias_vencido'], errors='coerce').fillna(0)
    df_proc['nomvendedor_norm'] = df_proc['nomvendedor'].apply(normalizar_nombre)
    
    ZONAS_SERIE = { "PEREIRA": [155, 189, 158, 439], "MANIZALES": [157, 238], "ARMENIA": [156] }
    ZONAS_SERIE_STR = {zona: [str(s) for s in series] for zona, series in ZONAS_SERIE.items()}
    def asignar_zona_robusta(valor_serie):
        if pd.isna(valor_serie): return "OTRAS ZONAS"
        numeros_en_celda = re.findall(r'\d+', str(valor_serie))
        if not numeros_en_celda: return "OTRAS ZONAS"
        for zona, series_clave_str in ZONAS_SERIE_STR.items():
            if set(numeros_en_celda) & set(series_clave_str): return zona
        return "OTRAS ZONAS"
    
    df_proc['zona'] = df_proc['serie'].apply(asignar_zona_robusta)
    bins = [-float('inf'), 0, 15, 30, 60, float('inf')]
    labels = ['Al día', '1-15 días', '16-30 días', '31-60 días', 'Más de 60 días']
    df_proc['edad_cartera'] = pd.cut(df_proc['dias_vencido'], bins=bins, labels=labels, right=True)
    return df_proc

def cargar_datos_cartera() -> pd.DataFrame:
    app.logger.info("Iniciando carga de Cartera...")
    file_content_stream = _conectar_y_descargar_dropbox(
        DBX_APP_KEY_CARTERA, DBX_APP_SECRET_CARTERA, DBX_REFRESH_TOKEN_CARTERA, DBX_FILE_PATH_CARTERA
    )
    if file_content_stream is None: return pd.DataFrame()
    try:
        contenido_csv = file_content_stream.getvalue().decode('latin-1')
        nombres_columnas_originales = [
            'Serie', 'Numero', 'Fecha Documento', 'Fecha Vencimiento', 'Cod Cliente',
            'NombreCliente', 'Nit', 'Poblacion', 'Provincia', 'Telefono1', 'Telefono2',
            'NomVendedor', 'Entidad Autoriza', 'E-Mail', 'Importe', 'Descuento',
            'Cupo Aprobado', 'Dias Vencido'
        ]
        df = pd.read_csv(StringIO(contenido_csv), header=None, names=nombres_columnas_originales, sep='|', engine='python')
        df_procesado = procesar_cartera(df)
        app.logger.info(f"Carga de Cartera exitosa. {len(df_procesado)} registros.")
        return df_procesado
    except Exception as e:
        app.logger.error(f"Error al procesar datos de Cartera: {e}")
        return pd.DataFrame()

# --- ¡NUEVA LÓGICA DE BASE DE CLIENTES! ---
def cargar_datos_base_clientes() -> pd.DataFrame:
    """Carga la base de datos maestra de clientes."""
    app.logger.info("Iniciando carga de Base de Clientes...")
    file_content_stream = _conectar_y_descargar_dropbox(
        DBX_APP_KEY_CARTERA, DBX_APP_SECRET_CARTERA, DBX_REFRESH_TOKEN_CARTERA, DBX_FILE_PATH_BASE_CLIENTES
    )
    if file_content_stream is None: return pd.DataFrame()
    try:
        # Asumimos que es un CSV y que podemos auto-detectar las columnas.
        # Ajusta esto si el archivo tiene un formato específico como '|'
        df = pd.read_csv(file_content_stream, encoding='latin-1') 
        
        # Normalizar columnas clave para la búsqueda
        if 'Nit' in df.columns:
             df['Nit_norm'] = df['Nit'].astype(str).str.strip()
        if 'NombreCliente' in df.columns:
             df['Nombre_norm'] = df['NombreCliente'].apply(normalizar_nombre)
        
        app.logger.info(f"Carga de Base de Clientes exitosa. {len(df)} registros.")
        return df
    except Exception as e:
        app.logger.error(f"Error al procesar Base de Clientes: {e}")
        return pd.DataFrame()

# --- LÓGICA DE INVENTARIO ---
def cargar_datos_inventario() -> (pd.DataFrame, pd.DataFrame):
    app.logger.info("Iniciando carga de Inventario...")
    df_inventario = pd.DataFrame()
    file_content_stream = _conectar_y_descargar_dropbox(
        DBX_APP_KEY_INVENTARIO, DBX_APP_SECRET_INVENTARIO, DBX_REFRESH_TOKEN_INVENTARIO, DBX_FILE_PATH_INVENTARIO
    )
    if file_content_stream:
        try:
            nombres_columnas_csv = [
                'DEPARTAMENTO', 'REFERENCIA', 'DESCRIPCION', 'MARCA', 'PESO_ARTICULO',
                'UNIDADES_VENDIDAS', 'STOCK', 'COSTO_PROMEDIO_UND', 'CODALMACEN',
                'LEAD_TIME_PROVEEDOR', 'HISTORIAL_VENTAS'
            ]
            df_inventario = pd.read_csv(
                file_content_stream, encoding='latin1', delimiter='|', header=None,
                names=nombres_columnas_csv,
                dtype={'REFERENCIA': str, 'CODALMACEN': str}
            )
            df_inventario['REFERENCIA'] = df_inventario['REFERENCIA'].str.strip()
            df_inventario['DESCRIPCION_NORM'] = df_inventario['DESCRIPCION'].apply(normalizar_nombre)
            df_inventario['STOCK'] = pd.to_numeric(df_inventario['STOCK'], errors='coerce').fillna(0)
            
            # (Aquí irá la lógica de análisis de inventario de tu script)
            # Por ahora, pivotamos para tener el stock por tienda
            ALMACEN_NOMBRE_MAPPING = {
                '155': 'Stock CEDI', '156': 'Stock ARMENIA', '157': 'Stock Manizales',
                '158': 'Stock Opalo', '189': 'Stock Olaya', '238': 'Stock Laureles',
                '439': 'Stock FerreBox',
            }
            df_inventario['NOMBRE_TIENDA'] = df_inventario['CODALMACEN'].map(ALMACEN_NOMBRE_MAPPING).fillna('Stock Desconocido')
            
            df_pivot = df_inventario.pivot_table(
                index=['REFERENCIA', 'DESCRIPCION', 'DESCRIPCION_NORM'],
                columns='NOMBRE_TIENDA',
                values='STOCK',
                aggfunc='sum',
                fill_value=0
            ).reset_index()
            
            df_costo = df_inventario.groupby('REFERENCIA')['COSTO_PROMEDIO_UND'].mean().reset_index()
            df_analizado = pd.merge(df_pivot, df_costo, on='REFERENCIA', how='left')
            
            app.logger.info(f"Carga y análisis de Inventario exitosa. {len(df_analizado)} SKUs.")
            df_inventario = df_analizado # Reemplazamos el DF crudo por el analizado
            
        except Exception as e:
            app.logger.error(f"Error al procesar datos de Inventario: {e}")

    df_proveedores = pd.DataFrame()
    file_content_stream_prov = _conectar_y_descargar_dropbox(
        DBX_APP_KEY_INVENTARIO, DBX_APP_SECRET_INVENTARIO, DBX_REFRESH_TOKEN_INVENTARIO, DBX_FILE_PATH_PROVEEDORES
    )
    if file_content_stream_prov:
        try:
            df_proveedores = pd.read_excel(file_content_stream_prov, dtype={'REFERENCIA': str, 'COD PROVEEDOR': str})
            df_proveedores.rename(columns={'REFERENCIA': 'SKU', 'PROVEEDOR': 'Proveedor'}, inplace=True)
            app.logger.info(f"Carga de Proveedores exitosa. {len(df_proveedores)} registros.")
        except Exception as e:
            app.logger.error(f"Error al procesar datos de Proveedores: {e}")

    return df_inventario, df_proveedores

# --- LÓGICA DE VENTAS ---
def cargar_datos_ventas() -> (pd.DataFrame, pd.DataFrame, pd.DataFrame):
    app.logger.info("Iniciando carga de Ventas, Cobros y CL4...")
    df_ventas = pd.DataFrame()
    stream_ventas = _conectar_y_descargar_dropbox(
        DBX_APP_KEY_VENTAS, DBX_APP_SECRET_VENTAS, DBX_REFRESH_TOKEN_VENTAS, DBX_FILE_PATH_VENTAS
    )
    if stream_ventas:
        try:
            nombres_cols = ['anio', 'mes', 'fecha_venta', 'Serie', 'TipoDocumento', 'codigo_vendedor', 'nomvendedor', 'cliente_id', 'nombre_cliente', 'codigo_articulo', 'nombre_articulo', 'categoria_producto', 'linea_producto', 'marca_producto', 'valor_venta', 'unidades_vendidas', 'costo_unitario', 'super_categoria']
            contenido_csv = stream_ventas.getvalue().decode('latin-1')
            df_ventas = pd.read_csv(StringIO(contenido_csv), header=None, names=nombres_cols, sep='|', engine='python', quoting=3)
            df_ventas['fecha_venta'] = pd.to_datetime(df_ventas['fecha_venta'], errors='coerce')
            df_ventas['cliente_id'] = df_ventas['cliente_id'].astype(str)
            df_ventas['nombre_articulo'] = df_ventas['nombre_articulo'].apply(normalizar_nombre)
            df_ventas['nombre_cliente'] = df_ventas['nombre_cliente'].apply(normalizar_nombre)
            app.logger.info(f"Carga de Ventas exitosa. {len(df_ventas)} registros.")
        except Exception as e:
            app.logger.error(f"Error al procesar datos de Ventas: {e}")

    df_cobros = pd.DataFrame()
    stream_cobros = _conectar_y_descargar_dropbox(
        DBX_APP_KEY_VENTAS, DBX_APP_SECRET_VENTAS, DBX_REFRESH_TOKEN_VENTAS, DBX_FILE_PATH_COBROS
    )
    if stream_cobros:
        try:
            nombres_cols = ['anio', 'mes', 'fecha_cobro', 'codigo_vendedor', 'valor_cobro']
            contenido_csv = stream_cobros.getvalue().decode('latin-1')
            df_cobros = pd.read_csv(StringIO(contenido_csv), header=None, names=nombres_cols, sep='|', engine='python', quoting=3)
            app.logger.info(f"Carga de Cobros exitosa. {len(df_cobros)} registros.")
        except Exception as e:
            app.logger.error(f"Error al procesar datos de Cobros: {e}")

    df_cl4 = pd.DataFrame()
    stream_cl4 = _conectar_y_descargar_dropbox(
        DBX_APP_KEY_VENTAS, DBX_APP_SECRET_VENTAS, DBX_REFRESH_TOKEN_VENTAS, DBX_FILE_PATH_CL4
    )
    if stream_cl4:
        try:
            df_cl4 = pd.read_excel(stream_cl4)
            df_cl4.columns = [normalizar_nombre(col) for col in df_cl4.columns]
            if 'ID CLIENTE' in df_cl4.columns:
                df_cl4.rename(columns={'ID CLIENTE': 'cliente_id'}, inplace=True)
            df_cl4['cliente_id'] = df_cl4['cliente_id'].astype(str)
            app.logger.info(f"Carga de CL4 exitosa. {len(df_cl4)} registros.")
        except Exception as e:
            app.logger.error(f"Error al procesar datos de CL4: {e}")
            
    return df_ventas, df_cobros, df_cl4

# --- LÓGICA DE PRODUCTOS (GSheets) ---
def cargar_maestro_productos() -> pd.DataFrame:
    global worksheet_productos
    if worksheet_productos is None:
        app.logger.warning("Worksheet de Productos no inicializado.")
        return pd.DataFrame()
    try:
        app.logger.info("Iniciando carga del Maestro de Productos desde GSheets...")
        records = worksheet_productos.get_all_records()
        df = pd.DataFrame(records)
        if 'Referencia' in df.columns:
            df['Referencia'] = df['Referencia'].astype(str).str.strip()
        
        # Usamos el nombre de columna del script Cotizador
        col_nombre_producto = 'DESCRIPCION' 
        if col_nombre_producto not in df.columns:
             # Fallback por si el nombre es diferente
             col_nombre_producto = next((col for col in df.columns if 'DESCRIPCION' in normalizar_nombre(col)), None)

        if col_nombre_producto:
             df['Nombre_Producto_Norm'] = df[col_nombre_producto].apply(normalizar_nombre)
        else:
             app.logger.error("No se encontró la columna 'DESCRIPCION' en el Maestro de Productos.")
             df['Nombre_Producto_Norm'] = ""
        
        # Extraer columnas de precio
        df['PRECIO 1'] = pd.to_numeric(df.get('PRECIO 1', 0), errors='coerce').fillna(0) # Asumiendo 'PRECIO 1'
        
        app.logger.info(f"Carga de Maestro de Productos exitosa. {len(df)} registros.")
        return df
    except Exception as e:
        app.logger.error(f"Error al cargar Maestro de Productos desde GSheets: {e}")
        return pd.DataFrame()


# --- ORQUESTADOR GLOBAL DE CARGA ---
def cargar_y_procesar_datos_global():
    """Orquesta la carga de TODOS los datos y los guarda en caché."""
    global CARTERA_PROCESADA_DF, BASE_CLIENTES_DF, INVENTARIO_ANALIZADO_DF, PROVEEDORES_DF, VENTAS_DF, COBROS_DF, CL4_DF, PRODUCTOS_MAESTRO_DF

    app.logger.info("Iniciando carga de datos globales...")
    
    if CARTERA_PROCESADA_DF.empty:
        CARTERA_PROCESADA_DF = cargar_datos_cartera()
    
    if BASE_CLIENTES_DF.empty: # ¡NUEVO!
        BASE_CLIENTES_DF = cargar_datos_base_clientes()

    if INVENTARIO_ANALIZADO_DF.empty or PROVEEDORES_DF.empty:
        INVENTARIO_ANALIZADO_DF, PROVEEDORES_DF = cargar_datos_inventario()

    if VENTAS_DF.empty or COBROS_DF.empty or CL4_DF.empty:
        VENTAS_DF, COBROS_DF, CL4_DF = cargar_datos_ventas()
        
    if PRODUCTOS_MAESTRO_DF.empty:
        PRODUCTOS_MAESTRO_DF = cargar_maestro_productos()

    app.logger.info("Carga de datos globales finalizada.")
    return True


# ----------------------------------------------------------------------
## 🛡️ FUNCIONES DE HERRAMIENTA (TOOLS) PARA GEMINI (ACTUALIZADO)
# ----------------------------------------------------------------------

def consultar_estado_cliente_seguro(nit: str, codigo_cliente: str) -> str:
    """
    [TOOL] Consulta el estado de cuenta (cartera/deuda). Requiere credenciales validadas.
    Retorna un resumen de la deuda total y vencida.
    """
    if not nit or not codigo_cliente:
        return "Error: Faltan el NIT o el Código de Cliente para realizar la consulta."
    try:
        if CARTERA_PROCESADA_DF.empty:
            app.logger.warning("CARTERA_PROCESADA_DF está vacío. Recargando...")
            cargar_datos_cartera()
            if CARTERA_PROCESADA_DF.empty:
                 return "Los datos de cartera no han podido ser cargados. Intenta más tarde."

        if 'nit' not in CARTERA_PROCESADA_DF.columns or 'cod_cliente' not in CARTERA_PROCESADA_DF.columns:
            return "Error interno: El formato de los datos de cartera no es válido."

        datos_cliente_seleccionado = CARTERA_PROCESADA_DF[
            (CARTERA_PROCESADA_DF['nit'].astype(str) == str(nit).strip()) &
            (CARTERA_PROCESADA_DF['cod_cliente'].astype(str) == str(codigo_cliente).strip())
        ].copy()

        if datos_cliente_seleccionado.empty:
            return "Las credenciales no coinciden o no hay un estado de cuenta activo con esos datos. Por favor, verifica el NIT y el Código de Cliente."

        total_cartera_cliente = datos_cliente_seleccionado['importe'].sum()
        facturas_vencidas_cliente = datos_cliente_seleccionado[datos_cliente_seleccionado['dias_vencido'] > 0]
        total_vencido_cliente = facturas_vencidas_cliente['importe'].sum()
        nombre_cliente = datos_cliente_seleccionado.iloc[0]['nombrecliente']
        portal_link = "https://ferreinoxtiendapintuco.epayco.me/recaudo/ferreinoxrecaudoenlinea/"
        
        if total_vencido_cliente > 0:
            dias_max_vencido = int(facturas_vencidas_cliente['dias_vencido'].max())
            respuesta = (
                f"Hola {nombre_cliente}. Tu *deuda total es de ${total_cartera_cliente:,.0f}*. "
                f"De este monto, *${total_vencido_cliente:,.0f} está vencido*. "
                f"La factura con más antigüedad tiene {dias_max_vencido} días vencida. "
                f"Puedes pagar en nuestro portal: {portal_link}"
            )
        else:
            respuesta = (
                f"¡Hola {nombre_cliente}! ¡Felicitaciones! *No tienes facturas vencidas*. "
                f"Tu cartera total activa es de ${total_cartera_cliente:,.0f}. "
            )
        return respuesta
    except Exception as e:
        app.logger.error(f"Error en consultar_estado_cliente_seguro: {e}")
        return "Lo siento, hubo un error interno al consultar tu estado de cuenta."

# --- ¡NUEVA HERRAMIENTA DE BASE DE CLIENTES! ---
def verificar_cliente_existente(nit: str) -> str:
    """
    [TOOL] Verifica si un cliente existe en la base de datos maestra usando su NIT.
    """
    if not nit:
        return "Error: Necesito el NIT para poder buscarte."
        
    if BASE_CLIENTES_DF.empty:
        app.logger.warning("BASE_CLIENTES_DF está vacío. Recargando...")
        cargar_datos_base_clientes()
        if BASE_CLIENTES_DF.empty:
            return "Lo siento, no puedo acceder a la base de datos de clientes en este momento."

    try:
        # Asumimos que la columna 'Nit_norm' se creó durante la carga
        if 'Nit_norm' not in BASE_CLIENTES_DF.columns:
             return "Error interno: El archivo de base de clientes no tiene una columna 'Nit' identificable."

        nit_busqueda = str(nit).strip()
        cliente = BASE_CLIENTES_DF[BASE_CLIENTES_DF['Nit_norm'] == nit_busqueda]
        
        if cliente.empty:
            return f"No te encontré en nuestra base de clientes con el NIT {nit_busqueda}. ¿El NIT es correcto? Si eres nuevo, ¡bienvenido a Ferreinox!"
        else:
            nombre_cliente = cliente.iloc[0].get('NombreCliente', 'Cliente') # Asume la columna 'NombreCliente'
            return f"¡Hola {nombre_cliente}! Sí te encontré en nuestra base de datos. ¿En qué te puedo ayudar hoy? ¿Quizás consultar tu estado de cuenta o el stock de un producto?"

    except Exception as e:
        app.logger.error(f"Error en verificar_cliente_existente: {e}")
        return "Tuve un problema al verificar tu información de cliente."

# --- HERRAMIENTA DE INVENTARIO (ACTUALIZADA) ---
def consultar_stock_producto(nombre_producto_o_referencia: str) -> str:
    """
    [TOOL] Consulta el stock (inventario) disponible de un producto en todas las tiendas.
    """
    if INVENTARIO_ANALIZADO_DF.empty:
        app.logger.warning("INVENTARIO_ANALIZADO_DF está vacío. Recargando...")
        cargar_datos_inventario()
        if INVENTARIO_ANALIZADO_DF.empty:
            return "Lo siento, no puedo acceder a la información de inventario en este momento."

    termino_busqueda = normalizar_nombre(nombre_producto_o_referencia)
    
    resultados = INVENTARIO_ANALIZADO_DF[
        (INVENTARIO_ANALIZADO_DF['REFERENCIA'].astype(str) == termino_busqueda) |
        (INVENTARIO_ANALIZADO_DF['DESCRIPCION_NORM'].str.contains(termino_busqueda, na=False))
    ]
    
    if resultados.empty:
        return f"No encontré ningún producto que coincida con '{nombre_producto_o_referencia}'."

    # Agrupar resultados (puede haber varios matches)
    producto = resultados.iloc[0]
    nombre_real = producto['DESCRIPCION']
    
    # Encontrar todas las columnas que empiezan con "Stock "
    columnas_stock = [col for col in producto.index if col.startswith('Stock ')]
    
    if not columnas_stock:
        return f"Encontré el producto '{nombre_real}', pero no tengo información de stock por tienda."

    stock_total = 0
    mensajes_stock = []
    for col in columnas_stock:
        stock_tienda = pd.to_numeric(producto[col], errors='coerce').fillna(0)
        if stock_tienda > 0:
            nombre_tienda = col.replace('Stock ', '')
            mensajes_stock.append(f"* {stock_tienda:,.0f} unidades en {nombre_tienda}")
            stock_total += stock_tienda
    
    if stock_total > 0:
        respuesta = f"¡Buenas noticias! Para '{nombre_real}' (Ref: {producto['REFERENCIA']}) tenemos un total de {stock_total:,.0f} unidades, distribuidas así:\n"
        respuesta += "\n".join(mensajes_stock)
        return respuesta
    else:
        return f"Ups, parece que el producto '{nombre_real}' (Ref: {producto['REFERENCIA']}) está agotado en todas las tiendas en este momento."

# --- HERRAMIENTA DE PRECIOS (ACTUALIZADA) ---
def consultar_precio_producto(nombre_producto_o_referencia: str) -> str:
    """
    [TOOL] Consulta el precio de lista de un producto desde el maestro de productos.
    """
    if PRODUCTOS_MAESTRO_DF.empty:
        app.logger.warning("PRODUCTOS_MAESTRO_DF está vacío. Recargando...")
        cargar_maestro_productos()
        if PRODUCTOS_MAESTRO_DF.empty:
            return "Lo siento, no puedo acceder a la lista de precios en este momento."

    termino_busqueda = normalizar_nombre(nombre_producto_o_referencia)
    
    resultados = PRODUCTOS_MAESTRO_DF[
        (PRODUCTOS_MAESTRO_DF['Referencia'].astype(str) == termino_busqueda) |
        (PRODUCTOS_MAESTRO_DF['Nombre_Producto_Norm'].str.contains(termino_busqueda, na=False))
    ]
    
    if resultados.empty:
        return f"No encontré un precio para '{nombre_producto_o_referencia}'."
    try:
        producto = resultados.iloc[0]
        precio_lista = pd.to_numeric(producto.get('PRECIO 1', 0), errors='coerce').fillna(0)
        nombre_real = producto.get('DESCRIPCION', 'Producto') # Usamos 'DESCRIPCION'
        
        if precio_lista > 0:
            return f"El precio de lista para '{nombre_real}' (Ref: {producto['Referencia']}) es de ${precio_lista:,.0f} (antes de IVA)."
        else:
            return f"Encontré el producto '{nombre_real}', pero no tiene un precio de lista asignado."
    except Exception as e:
        app.logger.error(f"Error en consulta de precio: {e}")
        return "Error al consultar el precio."

# --- HERRAMIENTA DE VENTAS (HISTORIAL) ---
def consultar_historial_compras_cliente(nit: str, codigo_cliente: str) -> str:
    """
    [TOOL] Consulta las compras recientes (últimos 60 días) de un cliente. Requiere credenciales validadas.
    """
    if not nit or not codigo_cliente:
        return "Error: Faltan el NIT o el Código de Cliente para realizar la consulta."

    # 1. Validar identidad con Cartera
    if CARTERA_PROCESADA_DF.empty: cargar_datos_cartera()
    if CARTERA_PROCESADA_DF.empty: return "Error: No puedo validar tu identidad (Cartera no disponible)."
    
    cliente_valido = CARTERA_PROCESADA_DF[
        (CARTERA_PROCESADA_DF['nit'].astype(str) == str(nit).strip()) &
        (CARTERA_PROCESADA_DF['cod_cliente'].astype(str) == str(codigo_cliente).strip())
    ]
    if cliente_valido.empty:
        return "Las credenciales no coinciden. No puedo mostrar el historial de compras."

    # 2. Consultar el historial de Ventas
    if VENTAS_DF.empty:
        cargar_datos_ventas()
        if VENTAS_DF.empty:
            return "Estoy teniendo problemas para acceder al historial de ventas. Intenta más tarde."

    # 3. Mapear 'cod_cliente' (cartera) al 'cliente_id' (ventas)
    id_cliente_ventas = cliente_valido.iloc[0].get('cod_cliente') # Asumiendo que es el mismo ID
    if id_cliente_ventas is None:
         return "Error interno: No se pudo encontrar tu ID de cliente."

    df_ventas_cliente = VENTAS_DF[VENTAS_DF['cliente_id'].astype(str) == str(id_cliente_ventas)]
    if df_ventas_cliente.empty:
        return "¡Hola! Veo que tus credenciales son correctas, pero no encuentro un historial de compras para ti."

    # 4. Filtrar por últimos 60 días
    fecha_limite = datetime.now() - pd.Timedelta(days=60)
    df_ventas_recientes = df_ventas_cliente[df_ventas_cliente['fecha_venta'] > fecha_limite]
    
    if df_ventas_recientes.empty:
        return "No he encontrado compras en los últimos 60 días. ¿Te gustaría consultar un rango de fechas anterior?"

    # 5. Resumir compras
    total_comprado = df_ventas_recientes['valor_venta'].sum()
    productos_comprados = df_ventas_recientes.groupby('nombre_articulo')['valor_venta'].sum().nlargest(3)
    
    respuesta = f"En los últimos 60 días, has comprado un total de ${total_comprado:,.0f}. Tus productos más comprados fueron: \n"
    for producto, valor in productos_comprados.items():
        respuesta += f"* {producto} (${valor:,.0f})\n"
    
    return respuesta

# ----------------------------------------------------------------------
## 🧠 INICIALIZACIÓN DE GEMINI (ACTUALIZADO)
# ----------------------------------------------------------------------
model = None
try:
    if not GEMINI_API_KEY:
        raise ValueError("Error: La variable 'GEMINI_API_KEY' no está configurada.")

    genai.configure(api_key=GEMINI_API_KEY)

    system_instruction = (
        "Eres **Ferreinox CRM AI**, el asistente experto en servicio al cliente, inventarios y análisis de cartera para **FERREINOX SAS BIC**."
        "Tu misión es ayudar a los clientes con sus consultas de forma amable, cercana y natural. Tutea al cliente."
        "Tu página web de referencia es www.ferreinox.co."
        "Tienes varias capacidades:"
        "1.  **Verificar Cliente:** Si un cliente pregunta '¿soy cliente?' o da un NIT, usa `verificar_cliente_existente`."
        "2.  **Consultar Deudas (Cartera):** Si un cliente verificado pide su deuda o estado de cuenta, *DEBES* pedirle su **NIT** y su **Código de Cliente** para usar `consultar_estado_cliente_seguro`."
        "3.  **Consultar Historial de Compras:** Si un cliente verificado pregunta por sus compras pasadas, *DEBES* pedirle su **NIT** y **Código de Cliente** para usar `consultar_historial_compras_cliente`."
        "4.  **Consultar Inventario (Stock):** Si el cliente pregunta '¿tienes...?' o '¿hay stock de...?', usa `consultar_stock_producto`."
        "5.  **Consultar Precios:** Si el cliente pregunta por el precio de un producto, usa `consultar_precio_producto`."
        "**PROTOCOLO DE SEGURIDAD MÁXIMA:** Nunca entregues información financiera (deudas o historial de compras) sin validar al cliente con NIT y Código de Cliente usando las herramientas seguras."
    )
    
    tools_list = [
        verificar_cliente_existente,       # ¡NUEVO!
        consultar_estado_cliente_seguro,     
        consultar_stock_producto,          
        consultar_precio_producto,           
        consultar_historial_compras_cliente,
    ]
    
    model = genai.GenerativeModel(
        model_name="models/gemini-flash-latest",
        system_instruction=system_instruction,
        tools=tools_list
    )

    app.logger.info("Modelo Gemini (Ferreinox CRM AI v3) inicializado exitosamente con Tools.")

except Exception as e:
    app.logger.error(f"Error fatal al configurar Google AI Studio o Tools: {e}")
    model = None

# ----------------------------------------------------------------------
## 💬 FUNCIONES AUXILIARES DE CHAT (ACTUALIZADO)
# ----------------------------------------------------------------------

def send_whatsapp_message(to_number, message_text):
    """Envía un mensaje de texto de WhatsApp."""
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        app.logger.error("Error: Tokens de WhatsApp no configurados.")
        return
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": message_text}}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        app.logger.info(f"Respuesta enviada a {to_number}")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error al enviar mensaje de WhatsApp: {e}")
        if e.response is not None: app.logger.error(f"Respuesta del error: {e.response.text}")

def log_to_google_sheet(timestamp, phone, user_msg, bot_msg, tool_used="N/A"):
    """Registra la conversación en la hoja de Log."""
    global worksheet_log
    if worksheet_log is None: return
    try:
        worksheet_log.append_row([timestamp, phone, user_msg, bot_msg, tool_used])
    except Exception as e:
        app.logger.error(f"Error al escribir en Google Sheets (Log): {e}")
        if "APIError" in str(e):
             app.logger.info("Intentando reconectar a Google Sheets (Log)...")
             init_google_sheets()

# --- ¡NUEVA FUNCIÓN DE CONSENTIMIENTO! ---
def log_user_consent(phone_number: str):
    """Registra el consentimiento del usuario en la hoja de Usuarios."""
    global worksheet_usuarios, consented_users
    
    if worksheet_usuarios is None:
        app.logger.error("No se puede registrar consentimiento, worksheet_usuarios no está configurado.")
        return
    
    try:
        timestamp = datetime.now().isoformat()
        worksheet_usuarios.append_row([timestamp, phone_number])
        consented_users.add(phone_number) # Actualizar el cache local
        app.logger.info(f"Consentimiento registrado en Google Sheets para {phone_number}")
    except Exception as e:
        app.logger.error(f"Error al escribir en Google Sheets (Usuarios): {e}")
        if "APIError" in str(e):
             app.logger.info("Intentando reconectar a Google Sheets (Usuarios)...")
             init_google_sheets()

def process_message_in_thread(user_phone_number, user_message, message_id):
    """
    Función principal de procesamiento de mensajes, ahora con portal de consentimiento.
    """
    global model, user_chats, processed_message_ids, consented_users

    if message_id in processed_message_ids:
        app.logger.warning(f"Mensaje duplicado (ID: {message_id}). Ignorando.")
        return
    processed_message_ids.add(message_id)
    if len(processed_message_ids) > 1000: processed_message_ids.clear()

    if model is None:
        send_whatsapp_message(user_phone_number, "Lo siento, el servicio de IA de Ferreinox no está disponible.")
        return

    timestamp = datetime.now().isoformat()
    user_message_lower = user_message.strip().lower()

    # --- ¡NUEVO PORTAL DE CONSENTIMIENTO! ---
    if user_phone_number not in consented_users:
        if user_message_lower in ['si', 'sí', 'acepto', 'sii', 'claro']:
            log_user_consent(user_phone_number)
            gemini_reply = "¡Perfecto, muchas gracias! Tus datos están protegidos con Ferreinox SAS BIC. Ahora sí, ¿en qué te puedo ayudar hoy?"
            send_whatsapp_message(user_phone_number, gemini_reply)
            log_to_google_sheet(timestamp, user_phone_number, user_message, gemini_reply, "Consentimiento_Aceptado")
            return
        
        elif user_message_lower in ['no', 'no acepto']:
            gemini_reply = "Entendido. No puedo procesar tus datos ni ayudarte con tus consultas sin tu permiso. Si cambias de opinión, escribe 'Sí' en cualquier momento. ¡Que tengas un buen día!"
            send_whatsapp_message(user_phone_number, gemini_reply)
            log_to_google_sheet(timestamp, user_phone_number, user_message, gemini_reply, "Consentimiento_Rechazado")
            return
            
        else:
            # Es el primer mensaje del usuario o habla sin haber aceptado
            gemini_reply = (
                "¡Hola! Soy el asistente virtual de Ferreinox SAS BIC. 🤖\n\n"
                "Para poder ayudarte y gestionar tus consultas (como deudas, pedidos o inventario), "
                "necesito tu permiso para el tratamiento de tus datos personales (como tu número de teléfono), "
                "de acuerdo con nuestra política de Habeas Data.\n\n"
                "¿Aceptas el tratamiento de tus datos? Por favor, responde solo *'Sí'* o *'No'*."
            )
            send_whatsapp_message(user_phone_number, gemini_reply)
            log_to_google_sheet(timestamp, user_phone_number, user_message, gemini_reply, "Consentimiento_Solicitado")
            return
    
    # --- FIN DEL PORTAL DE CONSENTIMIENTO ---
    # Si el código llega aquí, el usuario YA HA DADO SU CONSENTIMIENTO.

    if user_phone_number not in user_chats:
        app.logger.info(f"Creando nueva sesión de chat para {user_phone_number}")
        user_chats[user_phone_number] = model.start_chat(history=[])
    
    chat_session = user_chats[user_phone_number]
    
    if user_message.strip().lower() == "/reset":
        user_chats[user_phone_number] = model.start_chat(history=[])
        gemini_reply = "¡Listo! Empecemos de nuevo. ¿En qué te puedo ayudar?"
        send_whatsapp_message(user_phone_number, gemini_reply)
        log_to_google_sheet(timestamp, user_phone_number, user_message, gemini_reply, "Reset")
        return

    gemini_reply = "Perdona, hubo un error en la comunicación. ¿Puedes repetirme tu pregunta?"
    tool_function_name = "N/A"

    try:
        app.logger.info(f"Enviando a Gemini (Usuario consentido)...")
        response = chat_session.send_message(user_message)
        
        while (response.candidates and 
               len(response.candidates) > 0 and 
               response.candidates[0].content.parts and
               response.candidates[0].content.parts[0].function_call):
            
            function_call = response.candidates[0].content.parts[0].function_call
            tool_function_name = function_call.name
            app.logger.info(f"Gemini quiere llamar a la función: {tool_function_name}")
            
            func_to_call = globals().get(tool_function_name)
            tool_calls_list = []

            if not func_to_call:
                tool_output = f"Error: Herramienta {tool_function_name} no encontrada."
            else:
                try:
                    args = dict(function_call.args)
                    app.logger.info(f"Argumentos para {tool_function_name}: {args}")
                    tool_output = func_to_call(**args)
                except Exception as e:
                    app.logger.error(f"Error al ejecutar la herramienta {tool_function_name}: {e}")
                    tool_output = f"Error en la ejecución de la función: {e}"
            
            tool_calls_list.append({
                "function_response": {
                    'name': tool_function_name,
                    'response': {'result': tool_output}
                }
            })
            
            if tool_calls_list:
                response = chat_session.send_message(tool_calls_list)
            else:
                break
        
        gemini_reply = response.text
        app.logger.info(f"Respuesta final de Gemini: {gemini_reply[:50]}...")

    except Exception as e:
        app.logger.error(f"Error fatal en el proceso de chat o Tool Calling: {e}", exc_info=True)
        if user_phone_number in user_chats:
            del user_chats[user_phone_number]

    send_whatsapp_message(user_phone_number, gemini_reply)
    log_to_google_sheet(timestamp, user_phone_number, user_message, gemini_reply, tool_function_name)


# ----------------------------------------------------------------------
## 🌐 RUTAS DEL WEBHOOK (Sin cambios)
# ----------------------------------------------------------------------
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == WHATSAPP_VERIFY_TOKEN:
            app.logger.info("¡Webhook verificado!")
            return make_response(request.args.get('hub.challenge'), 200)
        else:
            app.logger.warning("Error de verificación. Tokens no coinciden.")
            return make_response('Error de verificación', 403)

    if request.method == 'POST':
        data = request.get_json()
        try:
            if (data.get('entry') and 
                data['entry'][0].get('changes') and 
                data['entry'][0]['changes'][0].get('value') and 
                data['entry'][0]['changes'][0]['value'].get('messages') and
                data['entry'][0]['changes'][0]['value']['messages'][0]):

                message_info = data['entry'][0]['changes'][0]['value']['messages'][0]

                if message_info['type'] == 'text':
                    user_message = message_info['text']['body']
                    user_phone_number = message_info['from']
                    message_id = message_info['id']

                    app.logger.info(f"Mensaje de {user_phone_number} (ID: {message_id}): {user_message}")

                    processing_thread = threading.Thread(
                        target=process_message_in_thread,
                        args=(user_phone_number, user_message, message_id)
                    )
                    processing_thread.start()
                    
                    return make_response('EVENT_RECEIVED', 200)

            return make_response('EVENT_RECEIVED', 200)

        except Exception as e:
            app.logger.error(f"Error general procesando el webhook POST: {e}", exc_info=True)
            return make_response('EVENT_RECEIVED', 200)

# ----------------------------------------------------------------------
## ▶️ INICIO DE LA APLICACIÓN
# ----------------------------------------------------------------------

# 1. Ejecutar inicialización de Google Sheets (Log, Productos y Usuarios)
init_google_sheets()

# 2. Ejecutar la carga inicial de TODOS los datos
try:
    cargar_y_procesar_datos_global()
except Exception as e:
    app.logger.error(f"Error en la carga inicial de datos globales al iniciar la aplicación: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
