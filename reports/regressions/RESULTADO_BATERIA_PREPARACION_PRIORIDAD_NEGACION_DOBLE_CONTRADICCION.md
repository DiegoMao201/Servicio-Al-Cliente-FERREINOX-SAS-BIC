# Resultado bateria preparacion prioridad negacion doble contradiccion

## Estado final

- Suite ejecutada sin OpenAI.
- Resultado final de la suite nueva: OK.
- Cobertura nueva: 208 subcasos determinísticos.
- Desglose:
  - 48 subcasos de preparación incorrecta.
  - 48 subcasos de priorización de rutas críticas.
  - 48 subcasos de negación y falso positivo.
  - 64 subcasos de doble contradicción simultánea.
- Corrida conjunta con todas las baterías determinísticas actuales: 24 tests `unittest` aprobados.

## Archivo de prueba

- Suite nueva: [test_global_policy_matrix_preparation_priority_negation.py](test_global_policy_matrix_preparation_priority_negation.py)
- Suite 320 casos mixtos: [test_global_policy_matrix_multisurface_contradictions.py](test_global_policy_matrix_multisurface_contradictions.py)
- Suite 200 casos base: [test_global_policy_matrix_200.py](test_global_policy_matrix_200.py)
- Suite base previa: [test_global_policy_matrix.py](test_global_policy_matrix.py)

## Comandos ejecutados

### Suite nueva sola

```powershell
& "c:/Users/Diego Mauricio/Desktop/CRM_Ferreinox/.venv/Scripts/python.exe" -m unittest test_global_policy_matrix_preparation_priority_negation.py
```

### Corrida conjunta de todas las baterías determinísticas

```powershell
& "c:/Users/Diego Mauricio/Desktop/CRM_Ferreinox/.venv/Scripts/python.exe" -m unittest test_global_policy_matrix.py test_global_policy_matrix_200.py test_global_policy_matrix_multisurface_contradictions.py test_global_policy_matrix_preparation_priority_negation.py
```

## Salida final de la suite nueva

```text
2026-04-11 18:27:31,705 [ferreinox_agent] INFO: Loaded 2097 color formulas from C:\Users\Diego Mauricio\Desktop\CRM_Ferreinox\data\color_formulas.json
2026-04-11 18:27:31,709 [ferreinox_agent] INFO: Loaded 357 international product refs from C:\Users\Diego Mauricio\Desktop\CRM_Ferreinox\data\international_products.json
....
----------------------------------------------------------------------
Ran 4 tests in 0.190s

OK
```

## Salida final de la corrida conjunta

```text
2026-04-11 18:27:47,842 [ferreinox_agent] INFO: Loaded 2097 color formulas from C:\Users\Diego Mauricio\Desktop\CRM_Ferreinox\data\color_formulas.json
2026-04-11 18:27:47,847 [ferreinox_agent] INFO: Loaded 357 international product refs from C:\Users\Diego Mauricio\Desktop\CRM_Ferreinox\data\international_products.json
........................
----------------------------------------------------------------------
Ran 24 tests in 0.788s

OK
```

## Refuerzos de código que quedaron activos

### 1. Preparación incorrecta ya entra como política dura

Se añadieron reglas nuevas en [backend/main.py](backend/main.py):

- `metal_oxidado_preparacion_incorrecta`
  - bloquea preparación con `agua y jabón` como ruta principal
  - obliga `grata` o `lija`
  - exige que el metal quede seco antes del sistema
- `concreto_sin_curado_acido_incorrecto`
  - bloquea `ácido muriático` sobre concreto recién fundido o sin curar
  - obliga respetar `28 días` y `curado`

### 2. Prioridad crítica para rutas de riesgo

El motor ahora expone en `politicas_duras_contexto`:

- `critical_policy_names`
- `dominant_policy_names`
- `highest_priority_level`

Esto permite que consultas como agua potable o protección pasiva contra incendio no queden tratadas al mismo nivel que una ruta decorativa. El payload técnico ahora obliga a priorizar esas rutas al inicio de la asesoría desde [backend/main.py](backend/main.py) y la corrección post-LLM en [backend/agent_v3.py](backend/agent_v3.py) también las resalta.

### 3. Negación más precisa

La lógica de matching ahora distingue mejor entre:

- una solicitud real de uso incorrecto
- una mención negativa o histórica del producto

Ejemplo corregido:

- `No quiero usar Koraza porque ya vi que se sopla`

Con esto se evita activar rutas de redirección como si el usuario estuviera insistiendo en Koraza cuando en realidad la está descartando.

### 4. Acumulación de doble contradicción

Las consultas con dos errores simultáneos ya se validan para que el motor acumule ambas prohibiciones y ambas rutas correctas, en lugar de quedarse en la primera coincidencia.

## Hallazgos reales que destapó esta batería

La primera versión de esta suite detectó tres huecos reales del motor:

1. `metal_oxidado_mantenimiento` seguía dependiendo demasiado del clasificador único y se perdía en consultas mixtas.
   - Corrección: la política ahora también se activa por señales textuales directas como `reja oxidada` o `metal oxidado`.

2. El clasificador de `piso_industrial` no reconocía bien frases de concreto fresco si el usuario no decía literalmente `piso`.
   - Corrección: ahora contempla `concreto nuevo`, `recién fundido`, `recién vaciado`, `sin curar`, `obra gris`.

3. La negación estaba siendo demasiado agresiva y tomaba `sin curar` como si negara el uso de `ácido muriático`.
   - Corrección: la negación se volvió más específica para acciones reales como `no usar`, `no quiero`, `prohibido`, evitando apagar reglas correctas por frases técnicas descriptivas.

## Cómo está construida la suite

La suite nueva se divide en 4 bloques:

1. `test_preparation_hardening_matrix`
   - valida superficie correcta vs preparación incorrecta
2. `test_priority_dominance_matrix`
   - valida que rutas críticas dominen frente a rutas decorativas o secundarias
3. `test_negation_false_positive_matrix`
   - valida que la mención negativa o histórica de un producto no active un falso positivo
4. `test_double_contradiction_matrix`
   - valida acumulación de dos contradicciones simultáneas en una sola consulta

Cada familia se prueba con 8 redacciones distintas.

## Cobertura de preparación incorrecta

6 familias x 8 redacciones = 48 subcasos.

| # | Familia | Validación principal |
|---|---|---|
| 1 | metal_oxidado_agua_jabon | Bloquea agua y jabón; obliga grata/lija |
| 2 | metal_oxidado_lavar_con_agua | Bloquea lavado con agua antes del anticorrosivo |
| 3 | metal_oxidado_jabonoso | Bloquea agua jabonosa en reja oxidada |
| 4 | concreto_fresco_acido | Bloquea ácido muriático para “curar” concreto fresco |
| 5 | concreto_nuevo_acido_antes_pintar | Bloquea ácido sobre concreto nuevo sin curar |
| 6 | obra_gris_acido | Bloquea ácido muriático en obra gris recién vaciada |

## Cobertura de prioridad crítica

6 familias x 8 redacciones = 48 subcasos.

| # | Familia | Ruta crítica dominante esperada |
|---|---|---|
| 1 | agua_potable_y_fachada | `inmersion_agua_potable_condicional` |
| 2 | agua_potable_y_bano | `inmersion_agua_potable_condicional` |
| 3 | incendio_y_esmalte_decorativo | `proteccion_pasiva_incendio` |
| 4 | incendio_y_fachada | `proteccion_pasiva_incendio` |
| 5 | agua_potable_y_cancha | `inmersion_agua_potable_condicional` |
| 6 | agua_potable_e_incendio | ambas críticas como dominantes |

## Cobertura de negación y falso positivo

6 familias x 8 redacciones = 48 subcasos.

| # | Familia | Qué evita |
|---|---|---|
| 1 | humedad_no_quiere_koraza | No activa `interior_koraza_redirect` si Koraza está rechazada |
| 2 | bano_no_quiere_koraza | No trata el rechazo de Koraza como insistencia del cliente |
| 3 | interior_descarta_koraza | Evita ruta falsa solo por mención histórica de Koraza |
| 4 | metal_no_lavar_con_agua | No activa la regla de preparación incorrecta si el usuario niega esa práctica |
| 5 | concreto_no_usar_acido | No activa falso positivo del ácido si el usuario lo descarta |
| 6 | humedad_descarta_koraza_y_pide_opcion | Mantiene la ruta correcta de humedad sin asumir que quiere Koraza |

## Cobertura de doble contradicción simultánea

8 familias x 8 redacciones = 64 subcasos.

| # | Familia | Doble contradicción validada |
|---|---|---|
| 1 | pintucoat_y_viniltex | Pintucoat en cancha + Viniltex en reja oxidada |
| 2 | koraza_y_pintucoat | Koraza en baño interior + Pintucoat en cancha |
| 3 | intervinil_y_koraza_ladrillo | Intervinil en eternit + Koraza en ladrillo visto |
| 4 | barnex_y_poliuretano_exterior_interior | Barnex en escalera interior + poliuretano 1550 en deck exterior |
| 5 | pintucoat_y_pintulux_criticos | Pintucoat en agua potable + Pintulux 3 en 1 en intumescente |
| 6 | corrotec_y_viniltex | Corrotec en alta estética + Viniltex en reja oxidada |
| 7 | interseal_y_koraza | Interseal en baño interior + Koraza en ambiente químico severo |
| 8 | pintuco_fill_y_pintucoat | Pintuco Fill para espuma + Pintucoat para cancha |

## Qué valida esta suite nueva

- Que la matriz no solo valide producto vs superficie, sino también método vs superficie.
- Que las rutas críticas de salud, certificación o seguridad estructural queden etiquetadas como dominantes.
- Que una mención negativa de un producto no se confunda con una solicitud real del mismo.
- Que dos errores simultáneos se acumulen en la política en vez de detenerse en el primero.

## Límites actuales

- Sigue siendo validación determinística del motor de reglas, no del texto final del LLM.
- No separa todavía una consulta compleja en subrespuestas independientes por frente técnico.
- Aún no modela explícitamente preparaciones incorrectas para más superficies aparte de metal oxidado y concreto fresco.

## Siguiente endurecimiento útil

1. Preparación incorrecta en eternit, ladrillo visto y madera.
2. Consultas con triple contradicción simultánea.
3. Priorización dominante cuando el usuario mezcla riesgo crítico + alto tráfico + marcas ya decididas.
4. Reglas de “detener cotización” cuando la preparación propuesta hace técnicamente inviable cerrar el sistema.