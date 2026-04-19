# Resultado bateria multi-superficie y contradicciones

## Estado final

- Suite ejecutada sin OpenAI.
- Resultado final de la suite nueva: OK.
- Cobertura nueva: 320 subcasos determinísticos.
- Desglose:
  - 128 subcasos de combinaciones multi-superficie.
  - 192 subcasos de contradicciones deliberadas.
- Corrida conjunta con las baterias anteriores: 20 tests `unittest` aprobados.

## Archivo de prueba

- Suite nueva: [test_global_policy_matrix_multisurface_contradictions.py](test_global_policy_matrix_multisurface_contradictions.py)
- Suite base 200 casos: [test_global_policy_matrix_200.py](test_global_policy_matrix_200.py)
- Suite base previa: [test_global_policy_matrix.py](test_global_policy_matrix.py)

## Comandos ejecutados

### Suite nueva sola

```powershell
& "c:/Users/Diego Mauricio/Desktop/CRM_Ferreinox/.venv/Scripts/python.exe" -m unittest test_global_policy_matrix_multisurface_contradictions.py
```

### Corrida conjunta de todas las baterias deterministicas

```powershell
& "c:/Users/Diego Mauricio/Desktop/CRM_Ferreinox/.venv/Scripts/python.exe" -m unittest test_global_policy_matrix.py test_global_policy_matrix_200.py test_global_policy_matrix_multisurface_contradictions.py
```

## Salida final de la suite nueva

```text
2026-04-11 18:13:33,932 [ferreinox_agent] INFO: Loaded 2097 color formulas from C:\Users\Diego Mauricio\Desktop\CRM_Ferreinox\data\color_formulas.json
2026-04-11 18:13:33,937 [ferreinox_agent] INFO: Loaded 357 international product refs from C:\Users\Diego Mauricio\Desktop\CRM_Ferreinox\data\international_products.json
..
----------------------------------------------------------------------
Ran 2 tests in 0.248s

OK
```

## Salida final de la corrida conjunta

```text
2026-04-11 18:13:58,421 [ferreinox_agent] INFO: Loaded 2097 color formulas from C:\Users\Diego Mauricio\Desktop\CRM_Ferreinox\data\color_formulas.json
2026-04-11 18:13:58,425 [ferreinox_agent] INFO: Loaded 357 international product refs from C:\Users\Diego Mauricio\Desktop\CRM_Ferreinox\data\international_products.json
....................
----------------------------------------------------------------------
Ran 20 tests in 0.405s

OK
```

## Hallazgo real que destapo esta bateria

La primera version de esta suite encontro un hueco real en consultas mixtas:

- Caso: `cubierta de eternit exterior envejecida y muro de ladrillo a la vista que se quiere conservar`
- Problema: activaba `eternit_fibrocemento_exterior` pero perdia `ladrillo_a_la_vista`
- Causa raiz: la regla de ladrillo dependia demasiado del clasificador unico y no de señales textuales directas
- Correccion aplicada: en [backend/main.py](backend/main.py) la politica `ladrillo_a_la_vista` ahora tambien se activa por `match_any` textual, para no desaparecer en consultas multi-superficie

## Como esta construida la bateria

La suite nueva se divide en 2 bloques:

1. `test_multisurface_policy_matrix`
   - valida consultas largas que mezclan dos o mas superficies o contextos tecnicos en un mismo mensaje
2. `test_contradiction_policy_matrix`
   - valida consultas donde el usuario pide explicitamente un producto incompatible con el contexto tecnico

Cada familia se prueba con 8 redacciones distintas para evitar que la cobertura dependa de una sola frase fija.

## Plantillas de redaccion usadas

### Multi-superficie

1. `{ancla}`
2. `Cliente con varias superficies en el mismo proyecto: {ancla}`
3. `Necesito resolver esto en una sola asesoria: {ancla}`
4. `Caso mixto para cotizar: {ancla}`
5. `Tengo dos frentes tecnicos y quiero criterio correcto: {ancla}`
6. `Antes de cotizar revisa esta consulta larga: {ancla}`
7. `Asesoria tecnica para proyecto combinado: {ancla}`
8. `Consulta completa del cliente: {ancla}`

### Contradicciones

1. `{ancla}`
2. `Aunque el cliente insiste, quiere esto asi: {ancla}`
3. `El cliente lo pide textual aunque sospecho conflicto: {ancla}`
4. `Necesito que detectes la contradiccion tecnica en este pedido: {ancla}`
5. `Caso deliberadamente conflictivo: {ancla}`
6. `Quieren cotizar esto aunque parece incompatible: {ancla}`
7. `Asesoria tecnica con producto pedido por el cliente: {ancla}`
8. `Consulta larga con contradiccion incluida: {ancla}`

## Cobertura multi-superficie

16 familias x 8 redacciones = 128 subcasos.

| # | Familia | Mezcla validada | Politicas esperadas |
|---|---|---|---|
| 1 | fachada_y_bano | fachada exterior + baño interior con hongos | `fachada_alta_exposicion` + `bano_cocina_antihongos` |
| 2 | ladrillo_y_bano | ladrillo a la vista + baño interior | `ladrillo_a_la_vista` + `bano_cocina_antihongos` |
| 3 | eternit_y_grietas | eternit exterior + techo concreto con grietas | `eternit_fibrocemento_exterior` + `techo_concreto_grietas` |
| 4 | tanque_e_incendio | agua potable + proteccion pasiva contra incendio | `inmersion_agua_potable_condicional` + `proteccion_pasiva_incendio` |
| 5 | techo_y_galvanizado | cubierta con grietas + lamina galvanizada | `techo_concreto_grietas` + `metal_nuevo_galvanizado` |
| 6 | madera_exterior_e_interior | deck exterior + escalera interior vitrificada | `madera_exterior` + `madera_interior_alto_trafico` |
| 7 | sendero_y_galvanizado | sendero peatonal + porton galvanizado | `cancha_sendero_peatonal` + `metal_nuevo_galvanizado` |
| 8 | espuma_y_bano | espuma expansiva + baño interior | `espuma_poliuretano_sellado` + `bano_cocina_antihongos` |
| 9 | agua_potable_y_galvanizado | tanque agua potable + zinc galvanizado | `inmersion_agua_potable_condicional` + `metal_nuevo_galvanizado` |
| 10 | incendio_y_alta_estetica | intumescente + acabado industrial estético | `proteccion_pasiva_incendio` + `acabado_industrial_alta_estetica` |
| 11 | ambiente_quimico_e_incendio | planta quimica + fuego | `ambiente_quimico_industrial` + `proteccion_pasiva_incendio` |
| 12 | eternit_y_ladrillo | eternit exterior + ladrillo a la vista | `eternit_fibrocemento_exterior` + `ladrillo_a_la_vista` |
| 13 | cancha_y_bano | cancha exterior + baño interior | `cancha_sendero_peatonal` + `bano_cocina_antihongos` |
| 14 | espuma_y_terraza | espuma sellado + terraza con grietas | `espuma_poliuretano_sellado` + `techo_concreto_grietas` |
| 15 | bano_y_koraza_interior | baño interior + solicitud de Koraza en sala | `bano_cocina_antihongos` + `interior_koraza_redirect` |
| 16 | agua_potable_y_espuma | inmersion potable + sellado con espuma | `inmersion_agua_potable_condicional` + `espuma_poliuretano_sellado` |

## Cobertura de contradicciones deliberadas

24 familias x 8 redacciones = 192 subcasos.

| # | Familia | Contradiccion validada | Politicas esperadas | Bloqueo principal |
|---|---|---|---|---|
| 1 | koraza_en_bano_interior | Koraza para baño interior | `bano_cocina_antihongos` + `interior_koraza_redirect` | Prohibe `Koraza` |
| 2 | koraza_en_humedad_interior | Koraza para humedad/salitre interior | `humedad_interior_negativa` + `interior_koraza_redirect` | Prohibe `Koraza` |
| 3 | pintucoat_en_cancha | Pintucoat para cancha | `cancha_sendero_peatonal` | Prohibe `Pintucoat` |
| 4 | pintucoat_en_galvanizado | Pintucoat para galvanizado nuevo | `metal_nuevo_galvanizado` | Prohibe `Pintucoat` |
| 5 | viniltex_en_reja_oxidada | Viniltex para reja oxidada | `metal_oxidado_mantenimiento` | Prohibe `Viniltex` |
| 6 | barnex_en_escalera_interior | Barnex para escalera interior alto trafico | `madera_interior_alto_trafico` | Prohibe `Barnex` |
| 7 | poliuretano_1550_en_deck | Poliuretano 1550 para deck exterior | `madera_exterior` | Prohibe `Poliuretano Alto Trafico 1550/1551` |
| 8 | koraza_en_terraza_grietas | Koraza para techo con grietas | `techo_concreto_grietas` | Prohibe `Koraza` |
| 9 | intervinil_en_eternit | Intervinil para eternit exterior | `eternit_fibrocemento_exterior` | Prohibe `Intervinil` |
| 10 | acido_en_ladrillo_vista | Acido muriatico para ladrillo visto | `ladrillo_a_la_vista` | Prohibe `acido muriatico` |
| 11 | pintucoat_en_agua_potable | Pintucoat para inmersion potable | `inmersion_agua_potable_condicional` | Prohibe `Pintucoat` |
| 12 | koraza_en_agua_potable | Koraza para tanque sumergido | `inmersion_agua_potable_condicional` | Prohibe `Koraza` |
| 13 | pintulux_en_incendio | Pintulux 3 en 1 para fuego | `proteccion_pasiva_incendio` | Prohibe `Pintulux 3 en 1` |
| 14 | corrotec_en_alta_estetica | Corrotec para acabado industrial premium | `acabado_industrial_alta_estetica` | Prohibe `Corrotec` |
| 15 | koraza_en_ambiente_quimico | Koraza en planta quimica severa | `ambiente_quimico_industrial` | Prohibe `Koraza` |
| 16 | interseal_en_bano | Interseal para baño interior | `bano_cocina_antihongos` | Prohibe `Interseal` |
| 17 | interthane_en_base_agua | Interthane sobre muro base agua | `arquitectonico_sobre_base_agua` | Prohibe `Interthane 990` |
| 18 | primer50_en_piso_medio | Primer 50RS para garaje de concreto | `piso_industrial_trafico_medio` | Prohibe `Primer 50RS` |
| 19 | pintucoat_en_piso_pesado | Pintucoat para montacargas/estibadores | `piso_industrial_trafico_pesado` | Prohibe `Pintucoat` |
| 20 | viniltex_en_terraza_grietas | Viniltex para techo con grietas | `techo_concreto_grietas` | Prohibe `Viniltex` |
| 21 | koraza_en_ladrillo_vista | Koraza para ladrillo que se quiere conservar | `ladrillo_a_la_vista` | Prohibe `Koraza` |
| 22 | pintucoat_en_bano | Pintucoat para baño interior | `bano_cocina_antihongos` | Prohibe `Pintucoat` |
| 23 | viniltex_en_incendio | Viniltex para sistema intumescente | `proteccion_pasiva_incendio` | Prohibe `Viniltex` |
| 24 | pintuco_fill_en_espuma | Pintuco Fill para sellado con espuma | `espuma_poliuretano_sellado` | Prohibe `Pintuco Fill` |

## Que valida esta suite nueva

- Que una consulta larga no tape por completo una segunda superficie relevante.
- Que el motor agregue varias politicas duras cuando la consulta mezcla subproblemas reales.
- Que el producto explicitamente pedido por el usuario pueda quedar bloqueado si es incompatible.
- Que aparezcan productos de redireccion cuando el usuario insiste en una ruta equivocada.
- Que los pasos obligatorios sigan activos en escenarios condicionados como inmersion potable o intumescencia.

## Lectura tecnica importante

En consultas multi-superficie puede aparecer el mismo producto como requerido para una zona y prohibido para otra. Eso no es necesariamente un bug: significa que la consulta mete dos frentes distintos en una sola frase y la politica global esta preservando cada ruta por separado.

## Limites actuales

- Sigue siendo una validacion deterministica del motor de reglas, no del texto final generado por el LLM.
- No intenta partir una sola consulta en presupuestos separados por superficie; solo verifica que las politicas queden visibles.
- Todavia no modela prioridades comerciales cuando el usuario mezcla 3 o 4 frentes con cantidades, m2 y marcas ya decididas.

## Espacio para sugerencias

Si quieres endurecer esta bateria, las siguientes direcciones son las mas utiles:

1. Consultas de 3 superficies en una sola frase.
2. Contradicciones con dos productos incorrectos al mismo tiempo.
3. Casos donde el cliente mezcla superficie correcta con preparacion incorrecta.
4. Casos donde quieras que la politica no solo bloquee, sino que priorice una sola ruta dominante.