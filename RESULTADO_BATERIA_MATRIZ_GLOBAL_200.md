# Resultado bateria matriz global 200 casos

## Estado final

- Suite ejecutada sin OpenAI.
- Resultado final: OK.
- Cobertura masiva: 200 subcasos determinísticos.
- Cobertura total corrida junto con la suite anterior: 18 tests `unittest` aprobados.

## Comando ejecutado

```powershell
& "c:/Users/Diego Mauricio/Desktop/CRM_Ferreinox/.venv/Scripts/python.exe" -m unittest test_global_policy_matrix.py test_global_policy_matrix_200.py
```

## Salida final de la corrida

```text
2026-04-11 18:01:15,687 [ferreinox_agent] INFO: Loaded 2097 color formulas from C:\Users\Diego Mauricio\Desktop\CRM_Ferreinox\data\color_formulas.json
2026-04-11 18:01:15,690 [ferreinox_agent] INFO: Loaded 357 international product refs from C:\Users\Diego Mauricio\Desktop\CRM_Ferreinox\data\international_products.json
..................
----------------------------------------------------------------------
Ran 18 tests in 0.095s

OK
```

## Hallazgo real que destapo la bateria

En la primera corrida de la suite masiva aparecio un bug real de clasificacion:

- Caso afectado: `piso industrial exterior al sol con sistema epoxico`
- Error observado: el clasificador lo mandaba a `fachada_exterior`
- Causa raiz: prioridad incorrecta en `_infer_problem_class_from_rag_query`
- Correccion aplicada: en [backend/main.py](backend/main.py#L1923) se priorizo la deteccion de piso industrial antes de la ruta generica de fachada.

## Archivo de prueba

- Suite masiva: [test_global_policy_matrix_200.py](test_global_policy_matrix_200.py)
- Suite base previa: [test_global_policy_matrix.py](test_global_policy_matrix.py)

## Estructura de la bateria de 200 casos

La bateria usa 25 familias tecnicas. Cada familia se prueba con 8 redacciones distintas. Total: `25 x 8 = 200`.

### Plantillas de redaccion usadas en cada familia

1. `{ancla}`
2. `Necesito {ancla}`
3. `Que sistema recomiendas para {ancla}`
4. `Cliente consulta: {ancla}`
5. `Tengo {ancla}, que va?`
6. `Quiero cotizar {ancla}`
7. `Me sirve algo para {ancla}`
8. `Asesoria tecnica: {ancla}`

## Matriz de cobertura

| # | Familia | Ancla tecnica | Clase esperada | Politica esperada | Requiere | Prohibe / obliga |
|---|---|---|---|---|---|---|
| 1 | humedad_capilaridad | muro interior con salitre y humedad que sube desde la base del muro | humedad_interior_capilaridad | humedad_interior_negativa | Aquablock | Prohibe Koraza |
| 2 | humedad_general | pared interior con humedad, moho y filtracion lateral | humedad_interior_general | humedad_interior_negativa | Aquablock | Prohibe Pintuco Fill |
| 3 | fachada_exterior | fachada exterior expuesta a lluvia y sol con pintura soplada | fachada_exterior | fachada_alta_exposicion | Koraza | Prohibe Intervinil |
| 4 | eternit_exterior | techo de eternit exterior repintado y envejecido | eternit_fibrocemento | eternit_fibrocemento_exterior | Sellomax, Koraza | Prohibe Intervinil |
| 5 | ladrillo_vista | ladrillo a la vista exterior sin cambiar apariencia | ladrillo_vista | ladrillo_a_la_vista | Construcleaner Limpiador Desengrasante, Siliconite 7 | Prohibe Koraza |
| 6 | metal_alquidico_viejo | reja con esmalte sintetico viejo y anticorrosivo alquidico | metal_pintado_alquidico | metal_pintado_alquidico | - | Obliga llegar a metal desnudo; prohibe Interseal e Interthane 990 |
| 7 | metal_oxidado | reja metalica con oxido superficial y corrosion | metal_oxidado | metal_oxidado_mantenimiento | Pintoxido, Corrotec | Prohibe Viniltex |
| 8 | metal_galvanizado | lamina zinc galvanizada nueva para pintar | - | metal_nuevo_galvanizado | Wash Primer | Prohibe Pintucoat |
| 9 | piso_pesado | piso industrial de concreto para montacargas y estibadores | piso_industrial | piso_industrial_trafico_pesado | Intergard 2002, Arena de Cuarzo ref 5891610 | Prohibe Pintucoat |
| 10 | piso_medio | garaje de concreto interior con trafico medio | piso_industrial | piso_industrial_trafico_medio | Interseal gris RAL 7038, Pintucoat | Prohibe Primer 50RS |
| 11 | piso_exterior_uv | piso industrial exterior al sol con sistema epoxico | piso_industrial | piso_exterior_uv | Interthane 990 + Catalizador | Obliga poliuretano UV |
| 12 | concreto_sin_curado | piso de concreto nuevo recien fundido sin curar | piso_industrial | concreto_sin_curado | - | Obliga esperar 28 dias |
| 13 | madera_exterior | deck de madera exterior expuesto a sol y lluvia | madera | madera_exterior | Barnex, Wood Stain | Prohibe Poliuretano Alto Trafico 1550/1551 |
| 14 | madera_interior_vitrificado | escalera interior de madera para vitrificar con alto trafico | madera | madera_interior_alto_trafico | Poliuretano Alto Trafico 1550/1551 | Prohibe Barnex |
| 15 | techo_concreto_grietas | techo de concreto con grietas y fisuras en terraza | - | techo_concreto_grietas | Pintuco Fill | Prohibe Koraza |
| 16 | bano_antihongos | baño con hongos por condensacion en muro interior | - | bano_cocina_antihongos | Viniltex Baños y Cocinas | Prohibe Koraza |
| 17 | cancha_deportiva | cancha deportiva exterior y sendero peatonal | - | cancha_sendero_peatonal | Pintura Canchas | Prohibe Pintucoat |
| 18 | inmersion_agua_potable | tanque de agua potable con sistema para inmersion | - | inmersion_agua_potable_condicional | - | Obliga condicion NSF; prohibe Pintucoat |
| 19 | proteccion_incendio | estructura metalica con proteccion pasiva contra incendio e intumescente | - | proteccion_pasiva_incendio | Interchar | Obliga espesor requerido |
| 20 | alta_estetica_industrial | acabado industrial de alta estetica con alta retencion de color | - | acabado_industrial_alta_estetica | Interfine | Prohibe Corrotec |
| 21 | ambiente_quimico | planta industrial con ambiente quimico severo y corrosion industrial | - | ambiente_quimico_industrial | Intergard, Interseal, Interthane 990 + Catalizador | Prohibe Koraza |
| 22 | espuma_poliuretano | espuma de poliuretano para sellar huecos y aislamiento termico | - | espuma_poliuretano_sellado | Espuma de Poliuretano | Prohibe Pintuco Fill |
| 23 | esmalte_decorativo | esmalte top quality brillante para metal decorativo de mantenimiento liviano | - | esmalte_decorativo_mantenimiento | Esmaltes Top Quality | Prohibe Interseal |
| 24 | arquitectonico_base_agua | muro de casa con pintura base agua y vinilo existente | - | arquitectonico_sobre_base_agua | - | Obliga compatibilidad agua con agua; prohibe Interthane 990 y Pintucoat |
| 25 | interior_koraza_redirect | koraza para muro interior de sala y pasillo cerrado | - | interior_koraza_redirect | Viniltex Advanced | Prohibe Koraza |

## Lectura rapida de lo que valida la suite

- Que la clasificacion tecnica no se desvie por wording superficial.
- Que cada familia active la politica dura correcta.
- Que entren productos obligatorios cuando corresponde.
- Que queden bloqueados productos incompatibles o peligrosos para el caso.
- Que aparezcan pasos obligatorios cuando la seguridad tecnica depende de una condicion previa.

## Limites actuales de la bateria

- Es deterministica y valida motor de reglas, no respuesta final del LLM.
- Varias familias validan politica contextual sin exigir una `problem_class` fija, porque en esos casos lo critico es la activacion de la regla dura.
- No cubre aun combinaciones multi-superficie en una misma consulta larga.
- No cubre aun contradicciones deliberadas del usuario tipo "quiero Koraza para baño interior" con doble conflicto en una sola frase.

## Espacio para tus sugerencias

Si quieres, podemos revisar el reporte con esta estructura:

1. Familias faltantes.
2. Productos mal exigidos o mal prohibidos.
3. Redacciones que hoy no representen bien el lenguaje real del cliente.
4. Casos donde quieras endurecer mas la politica.
5. Casos donde quieras darle mas libertad al agente.