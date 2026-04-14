# Pintuco Público: Cómo Enriquecer Sin Contaminar el RAG

## Regla base

La web pública de Pintuco no entra directo al RAG ni al agente.

Solo puede entrar como `enriquecimiento estructurado en cuarentena`, nunca como fuente maestra de producto.

## Qué sí aporta la web pública

- usos recomendados
- beneficios declarados
- rendimientos públicos
- preparación y aplicación básica
- presentaciones públicas
- enlace a ficha técnica pública
- taxonomía por superficies, ambientes y categorías

## Qué NO debe gobernar desde la web pública

- nombre final maestro de familia ERP
- referencia comercial final Ferreinox
- compatibilidad final contra inventario
- reglas duras del agente
- selección final de productos recomendados

## Flujo seguro

1. Extraer la web pública a artefactos separados.
2. Clasificar cada registro en `seguro`, `cuarentena` o `rechazado`.
3. Solo revisar manualmente los `seguro` y algunos `cuarentena`.
4. Convertir el enriquecimiento aprobado a campos estructurados compatibles con `agent_technical_profile`.
5. Mantener la resolución final de producto siempre contra inventario ERP y canonización interna.

## Archivos de control ya generados

- `artifacts/pintuco_public_site/pintuco_public_products.csv`
- `artifacts/pintuco_public_site/pintuco_public_products_safe.csv`
- `artifacts/pintuco_public_site/pintuco_public_products_quarantine.csv`
- `artifacts/pintuco_public_site/pintuco_public_products_rejected.csv`
- `artifacts/pintuco_public_site/pintuco_public_quarantine_summary.json`

## Criterio de aceptación fuerte

Un producto público solo puede considerarse `seguro_para_enriquecimiento` si cumple todo esto:

- tiene ficha técnica pública enlazada
- el match de inventario no parece kit, promo, accesorio o basura comercial
- el score de match es fuerte
- el nombre público y el inventario tienen superposición semántica suficiente
- la página tiene texto técnico útil, no solo marketing

## Criterio de rechazo automático

- match a kits o combos
- match a brochas, cintas u otros accesorios cuando la página es de pintura
- match a `gastos`, `varios`, promociones o artefactos administrativos
- nombre público demasiado genérico sin correspondencia clara
- ausencia de ficha pública cuando la página no aporta suficiente estructura

## Cómo usarlo bien con tu agente

Si más adelante decides aprovechar esta fuente, úsala solo para complementar estos campos del perfil técnico:

- `commercial_context.summary`
- `surface_targets`
- `application_methods`
- `application.surface_preparation`
- `application.dilution.ratio_texts`
- `diagnostic_questions`
- `alerts`

No uses esta fuente para autogenerar directamente:

- `required_products`
- `forbidden_products`
- alias ERP finales
- familias canónicas finales

## Decisión recomendada hoy

No fusionar nada aún en producción.

Primero trabajar solo sobre `pintuco_public_products_safe.csv` y revisar manualmente un subconjunto de `quarantine` de alto valor, por ejemplo:

- Viniltex
- Koraza
- Pintulux
- Corrotec
- Pintucoat
- Aquablock