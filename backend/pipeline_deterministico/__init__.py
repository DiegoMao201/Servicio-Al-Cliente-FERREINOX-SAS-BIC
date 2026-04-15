"""
Pipeline Determinístico de Cotización — Ferreinox CRM v4

Arquitectura de 3 capas estrictas:
  1. LLM → Solo diagnóstico + recomendación estructurada (JSON)
  2. Backend → Validación, match de inventario, precios (FUENTE DE VERDAD)
  3. Generador → Cotización/PDF sin LLM

El LLM NUNCA toca precios, SKUs reales ni genera cotizaciones.
"""
