CATALOG_SPECS = [
    {
        "source_label": "Ventas Ferreinox",
        "file_name": "ventas_detalle.csv",
        "source_role": "base_oficial_csv",
        "updates_postgrest": True,
        "target_table": "raw_ventas_detalle",
        "columns": [
            "anio",
            "mes",
            "fecha_venta",
            "serie",
            "tipo_documento",
            "codigo_vendedor",
            "nom_vendedor",
            "cliente_id",
            "nombre_cliente",
            "codigo_articulo",
            "nombre_articulo",
            "categoria_producto",
            "linea_producto",
            "marca_producto",
            "valor_venta",
            "unidades_vendidas",
            "costo_unitario",
            "super_categoria",
        ],
        "postgrest_views": ["vw_ventas_netas", "vw_albaranes_pendientes"],
        "business_entities": ["cliente", "producto", "venta", "venta_linea"],
        "notes": "Base comercial principal. Contiene facturas, notas credito y albaranes.",
    },
    {
        "source_label": "Rotación Inventarios",
        "file_name": "Rotacion.csv",
        "source_role": "base_oficial_csv",
        "updates_postgrest": True,
        "target_table": "raw_rotacion_inventarios",
        "columns": [
            "departamento",
            "referencia",
            "descripcion",
            "marca",
            "peso_articulo",
            "unidades_vendidas",
            "stock",
            "costo_promedio_und",
            "cod_almacen",
            "lead_time_proveedor",
            "historial_ventas",
        ],
        "postgrest_views": [],
        "business_entities": ["categoria_producto", "producto", "ubicacion", "stock_por_ubicacion", "movimiento_stock"],
        "notes": "Alimenta inventario, rotacion y abastecimiento.",
    },
    {
        "source_label": "Cartera Ferreinox",
        "file_name": "cartera_detalle.csv",
        "source_role": "base_oficial_csv",
        "updates_postgrest": True,
        "target_table": "raw_cartera_detalle",
        "columns": [
            "serie",
            "numero_documento",
            "fecha_documento",
            "fecha_vencimiento",
            "cod_cliente",
            "nombre_cliente",
            "nit",
            "poblacion",
            "provincia",
            "telefono1",
            "telefono2",
            "nom_vendedor",
            "entidad_autoriza",
            "email",
            "importe",
            "descuento",
            "cupo_aprobado",
            "dias_vencido",
        ],
        "postgrest_views": ["vw_estado_cartera"],
        "business_entities": ["cliente", "cartera_cliente"],
        "notes": "Estado detallado de cuentas por cobrar con reglas de zona, mora y exclusiones.",
    },
    {
        "source_label": "Cartera Ferreinox",
        "file_name": "cobros_detalle.csv",
        "source_role": "base_oficial_csv",
        "updates_postgrest": True,
        "target_table": "raw_cobros_detalle",
        "columns": ["anio", "mes", "fecha_cobro", "codigo_vendedor", "valor_cobro"],
        "postgrest_views": ["vw_recaudos"],
        "business_entities": ["cartera_cliente"],
        "notes": "Recaudos historicos. Comparte tabla raw con el origen de ventas.",
    },
    {
        "source_label": "Ventas Ferreinox",
        "file_name": "cobros_detalle.csv",
        "source_role": "base_oficial_csv",
        "updates_postgrest": True,
        "target_table": "raw_cobros_detalle",
        "columns": ["anio", "mes", "fecha_cobro", "codigo_vendedor", "valor_cobro"],
        "postgrest_views": ["vw_recaudos"],
        "business_entities": ["cartera_cliente"],
        "notes": "Recaudos complementarios. Se consolida con Cartera Ferreinox en la misma raw.",
    },
    {
        "source_label": "Cartera Ferreinox",
        "file_name": "Proveedores.csv",
        "source_role": "base_oficial_csv",
        "updates_postgrest": True,
        "target_table": "raw_proveedores_pagos",
        "columns": [
            "nombre_proveedor_erp",
            "serie",
            "num_entrada_erp",
            "num_factura",
            "doc_erp",
            "fecha_emision_erp",
            "fecha_vencimiento_erp",
            "valor_total_erp",
        ],
        "postgrest_views": ["vw_cuentas_por_pagar"],
        "business_entities": ["orden_compra", "orden_compra_linea"],
        "notes": "Cuentas por pagar y notas credito de proveedores.",
    },
]


def classify_source_role(file_name, canonical_spec=None):
    if canonical_spec:
        return "Base oficial CSV"
    lowered_name = file_name.lower()
    if lowered_name.endswith((".xlsx", ".xls")):
        return "Excel de apoyo"
    if lowered_name.endswith(".csv"):
        return "CSV pendiente de mapping"
    return "Archivo no clasificado"


def get_canonical_spec(source_label, file_name):
    lowered_name = file_name.lower()
    for spec in CATALOG_SPECS:
        if spec["source_label"] == source_label and spec["file_name"].lower() == lowered_name:
            return spec
    return None


def get_catalog_rows():
    rows = []
    for spec in CATALOG_SPECS:
        rows.append(
            {
                "Fuente Dropbox": spec["source_label"],
                "Archivo": spec["file_name"],
                "Rol": "Base oficial CSV",
                "Actualiza PostgREST": "Si" if spec["updates_postgrest"] else "No",
                "Tabla raw": spec["target_table"],
                "Vistas PostgREST": ", ".join(spec["postgrest_views"]) or "Sin vista directa",
                "Modelo alimentado": ", ".join(spec["business_entities"]),
                "Columnas": len(spec["columns"]),
                "Notas": spec["notes"],
            }
        )
    return rows