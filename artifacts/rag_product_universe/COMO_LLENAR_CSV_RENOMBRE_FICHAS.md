# Cómo Llenar el CSV de Renombre

Archivo principal:

- `artifacts/rag_product_universe/plantilla_mapeo_fichas_rag_inventario.csv`

La idea es que el CSV te sirva para decidir rápido qué hacer con cada PDF sin enredarte.

## Columnas que sí debes mirar siempre

| Columna | Qué pones ahí | Ejemplo real |
|---|---|---|
| `tipo_documento` | Qué clase de archivo es. Usa: `ficha_tecnica`, `fds`, `hds`, `certificado`, `guia`. | `ficha_tecnica` |
| `archivo_actual` | El nombre exacto como hoy existe el PDF. | `AJUSTADOR XILOL 21204.pdf` |
| `nombre_recomendado` | El nombre final que quieres dejar. Debe ser limpio, sin `(1)`, sin `copia`, sin `actualizada`, sin `slug` raro. | `AJUSTADOR XILOL 21204.pdf` |
| `accion` | Lo que debes hacer con ese archivo. Usa solo: `mantener`, `renombrar`, `revisar`, `separar_tipo_documental`. | `renombrar` |
| `nota` | Explicación corta de por qué. | `Quitar ruido documental y dejar solo la familia` |

## Columnas útiles pero opcionales

| Columna | Para qué sirve | Ejemplo |
|---|---|---|
| `lookup_inventario_sugerido` | Texto que usaríamos para buscar esa familia en inventario. | `ajustador xilol 21204` |
| `ejemplo_erp_encontrado` | Un ejemplo de cómo aparece esa familia en ERP/inventario. | `AJUSTADOR XILOL 21204 GTA007/20L/AA7` |
| `ref_erp_ejemplo` | Referencia real de ejemplo. | `5891066` |
| `familia_canonica` | Nombre maestro de la familia que quieres que gobierne la RAG. | `AJUSTADOR XILOL 21204` |
| `marca` | Marca si es importante para distinguir la familia. | `PINTUCO` |
| `estado_validacion` | Qué tan seguro está el mapeo. | `validado_inventario` |

## Qué significa cada acción

| Acción | Cuándo usarla | Ejemplo |
|---|---|---|
| `mantener` | El nombre ya está bien y no necesita cambio. | `INTERTHANE 990.pdf` |
| `renombrar` | El nombre sí sirve, pero hay que limpiarlo o alinearlo mejor a inventario. | `QUARZ G300N.pdf -> ARENA QUARZO G300N UFA850.pdf` |
| `revisar` | Aún no está claro si la familia exacta coincide con ERP. | `VINILTEX VIDA.pdf` |
| `separar_tipo_documental` | No debe entrar como ficha técnica principal. Aplica a FDS, HDS, certificados, brochures, guías. | `FDS - INTERTHANE 990 CAT B.pdf` |

## Regla simple para nombrar bien

Usa este orden mental:

1. Marca o familia real si ayuda a distinguir.
2. Nombre comercial estable.
3. Código técnico si realmente diferencia la familia.
4. No metas color, presentación o parte A/B en la ficha principal, salvo que el PDF sea exclusivamente de esa variante.

## Qué no debe quedar en el nombre maestro

- `(1)`
- `(2)`
- `copia`
- `actualizada`
- `final`
- nombres tipo slug: `primer-epoxi-zinc`
- prefijos documentales redundantes como `FICHA TECNICA`, si ya sabes que el archivo vive en carpeta de fichas

## Ejemplos exactos de cómo llenarlo

### Ejemplo 1: ficha técnica bien resuelta

```csv
tipo_documento,archivo_actual,nombre_recomendado,accion,nota,lookup_inventario_sugerido,ejemplo_erp_encontrado,ref_erp_ejemplo,familia_canonica,marca,estado_validacion
ficha_tecnica,AJUSTADOR XILOL 21204.pdf,AJUSTADOR XILOL 21204.pdf,mantener,Ya está suficientemente alineado con inventario,ajustador xilol 21204,AJUSTADOR XILOL 21204 GTA007/20L/AA7,5891066,AJUSTADOR XILOL 21204,,validado_inventario
```

### Ejemplo 2: ficha técnica que sí toca renombrar

```csv
ficha_tecnica,QUARZ G300N.pdf,ARENA QUARZO G300N UFA850.pdf,renombrar,Alinear al nombre técnico con código reconocido por inventario,quarz g300n,ARENA QUARZO G300N UFA850/25KG/AA7,5891610,ARENA QUARZO G300N UFA850,,validado_inventario
```

### Ejemplo 3: documento que no debe ir como ficha principal

```csv
fds,FDS - INTERTHANE 990 CAT B.pdf,FDS - INTERTHANE 990 CAT B.pdf,separar_tipo_documental,Catalizador y FDS deben vivir aparte de la ficha maestra,interthane 990 cat b,,,INTERTHANE 990,INTERNATIONAL,no_reingestar_como_ficha
```

## Qué necesito de ti si quieres que yo te lo siga llenando

Me basta con una de estas 2 opciones:

1. Una lista de nombres tal como salen hoy.
2. Fotos como las que mandaste.

Si tú no sabes el nombre correcto en ERP, no pasa nada. Yo te puedo dejar:

- `nombre_recomendado`
- `accion`
- `nota`
- y cuando sea posible, `ejemplo_erp_encontrado` con `ref_erp_ejemplo`

## Cómo leer rápido el CSV que te dejé

- Si ves `mantener`: ese archivo casi puede quedarse como está.
- Si ves `renombrar`: cambia el nombre al valor de `nombre_recomendado`.
- Si ves `revisar`: ese archivo necesita validación manual antes de reingesta.
- Si ves `separar_tipo_documental`: no lo metas al corpus principal de fichas técnicas.

## Script para cruzarlo automáticamente con inventario

Te dejé un script listo en la raíz del repo:

- `cruzar_fichas_con_inventario.py`

Qué hace:

- Lee el CSV de fichas.
- Usa primero el buscador real del backend contra `vw_inventario_agente`.
- Si hace falta, usa fuzzy matching sobre inventario completo.
- Llena `ejemplo_erp_encontrado`, `ref_erp_ejemplo`, `match_score` y `nombre_recomendado_auto`.
- También ajusta `accion` y `estado_validacion` cuando encuentra un match fuerte.

Comando normal usando la base actual:

```powershell
python cruzar_fichas_con_inventario.py
```

Comando usando un archivo externo de ERP en CSV o Excel:

```powershell
python cruzar_fichas_con_inventario.py --inventory-source "C:\ruta\articulos.xlsx"
```

Salida generada:

- `artifacts/rag_product_universe/mapeo_fichas_erp_cruzado.csv`

Columnas nuevas que agrega el script:

| Columna | Qué significa |
|---|---|
| `match_source` | De dónde salió el match: backend o archivo externo |
| `match_score` | Qué tan fuerte fue la coincidencia |
| `match_query_usada` | Qué texto usó el motor para buscar |
| `nombre_recomendado_auto` | Propuesta automática de nombre maestro |
| `accion_auto` | Acción calculada por el script |
| `estado_validacion_auto` | Estado de confianza del cruce |
| `nota_auto` | Explicación corta del cruce automático |