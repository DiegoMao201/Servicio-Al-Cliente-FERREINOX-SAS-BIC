# Auditoria RAG desde baterias de politicas

- Generado: 2026-04-11 19:08:18
- Escenarios auditados: 91
- Fuente: RAG local real + diagnóstico/guía/políticas filtradas para lectura humana
- Objetivo: ver portafolio sugerido/prohibido y señales de sistema completo sin leer logs interminables

## Vista global

### Productos recomendados mas visibles

- AJUSTADOR XILOL 21204 GTA007/20L/AA7: 25
- AJUSTADOR MEDIO TRAFICO BOTELLA 204: 25
- P7 PINTUCOAT 517 COMP A 3.44L: 22
- P7 PINTUCOAT 13227 COMP B 0.37L: 22
- Interseal gris RAL 7038 para concreto cuando aplique.: 18
- Pintucoat: 18
- Intergard 740: 18
- Intergard 2002 + cuarzo: 18
- PQ KORAZA MAT BLANCO 2650 18.93L: 16
- Viniltex Baños y Cocinas: 14
- Pintulux 3 en 1: 14
- Koraza: 13
- Pintóxido si hay óxido profundo.: 13
- Corrotec o Corrotec Premium como anticorrosivo.: 13
- Viniltex Advanced: 10
- Interchar: 10
- PQ VINILTEX ADV MAT BLANCO 1501 18.93L: 10
- P7 KORAZA ELASTOMERICA GEN ACCENT 18.93L: 9
- Viniltex: 8
- Pintóxido: 8
- Corrotec: 8
- PQ CORROTEC PREMIUM MAT GRIS 507 3.79L: 8
- KORAZA ELASTOMERICA 2651 NOGAL 5 GL: 8
- Pintura Canchas: 8
- P7 KORAZA ELASTOMERICA GEN DEEP 18.93L: 7

### Productos prohibidos mas visibles

- Koraza: 60
- Pintucoat: 49
- Viniltex: 39
- Interseal: 32
- Intergard: 27
- Interthane 990: 27
- Pintulux 3 en 1: 24
- Intervinil: 18
- Pinturama: 18
- No cotizar sin m² ni sin protocolo diagnóstico del piso: 18
- No cotizar sin m² ni sin protocolo diagnóstico del piso.: 18
- vinilos interiores: 13
- Pintuco Fill: 11
- Intervinil o Pinturama como acabado en fachadas de alta exposicion: 8
- Aquablock como acabado exterior: 8
- Aquablock: 8
- Intervinil o Pinturama como acabado en fachadas de alta exposicion.: 8
- Aquablock como acabado exterior.: 8
- Intergard 2002: 8
- Intergard 740: 8
- Corrotec: 8
- acido muriatico: 6
- Pinturama o vinilos interiores como acabado exterior: 5
- rasqueteo o preparacion mecanica que genere polvo: 5
- Intervinil, Pinturama o vinilos interiores como acabado exterior.: 5

### Politicas activas mas frecuentes

- bano_cocina_antihongos: 14
- inmersion_agua_potable_condicional: 11
- proteccion_pasiva_incendio: 10
- arquitectonico_sobre_base_agua: 10
- fachada_alta_exposicion: 8
- metal_oxidado_mantenimiento: 8
- cancha_sendero_peatonal: 8
- ladrillo_a_la_vista: 6
- techo_concreto_grietas: 6
- espuma_poliuretano_sellado: 6
- interior_koraza_redirect: 6
- humedad_interior_negativa: 5
- eternit_fibrocemento_exterior: 5
- metal_nuevo_galvanizado: 5
- concreto_sin_curado: 5
- madera_exterior: 4
- madera_interior_alto_trafico: 4
- acabado_industrial_alta_estetica: 4
- ambiente_quimico_industrial: 4
- metal_oxidado_preparacion_incorrecta: 3
- concreto_sin_curado_acido_incorrecto: 3
- piso_industrial_trafico_pesado: 2
- piso_industrial_trafico_medio: 2
- piso_exterior_uv: 2
- esmalte_decorativo_mantenimiento: 2

### Acabados o familias finales mas repetidas

- Pintucoat: 18
- Intergard 740: 18
- Intergard 2002 + cuarzo: 18
- Pintulux 3 en 1: 14
- Koraza: 13
- Viniltex: 8
- Barnex: 6
- Wood Stain: 6
- Esmalte Doméstico: 6
- Pintulux Máxima Protección: 6
- Viniltex Advanced: 5
- Intervinil: 5
- Pinturama: 5
- Siliconite 7: 4

## Grupo: base

### base_200 :: humedad_capilaridad

- Consulta: muro interior con salitre y humedad que sube desde la base del muro
- Problema inferido: humedad_interior_capilaridad
- Similitud RAG: 0.5338
- Prioridad dominante: high
- Politicas: humedad_interior_negativa
- Politicas criticas: ninguna
- Dominantes: humedad_interior_negativa
- Sistema recomendado estructurado: Aquablock, Aquablock Ultra - 2 manos con brocha para cargar producto., Estuco Acrílico después del Aquablock para nivelar. NUNCA antes., Viniltex Advanced, Intervinil, Pinturama
- Portafolio relacionado por inventario/RAG: ESTUCOR BULTO *25 KLS MOLDURA, ESTUCOR BULTO *25 KL LISTO, PQ AQUABLOCK ULTRA MAT BLANC 27070 3.79L, PQ AQUABLOCK ULTRA MAT BLANC 27070 0.95L
- Productos prohibidos: Koraza como imprimante o acabado interior, Pintuco Fill como solución principal para capilaridad interior desde la base del muro, Cotizar por galones sugeridos por el cliente sin metraje, Koraza, Pintuco Fill, Koraza como imprimante o acabado interior., Pintuco Fill como solución principal para capilaridad interior desde la base del muro., Cotizar por galones sugeridos por el cliente sin metraje.
- Base / imprimante: Aquablock Ultra - 2 manos con brocha para cargar producto.
- Intermedios: Estuco Acrílico después del Aquablock para nivelar. NUNCA antes.
- Acabados finales: Viniltex Advanced, Intervinil, Pinturama
- Herramientas: Brocha Goya Profesional, Rodillo, Lija / raspado para preparación
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Remover por completo pintura soplada/descascarada y salitre hasta base sana.; Si el revoque está quemado o meteorizado, reemplazarlo antes del sistema nuevo.; Retirar acabado soplado, salitre y base floja hasta sustrato sano antes del bloqueador.; Bloquear la humedad primero y solo despues reconstruir el acabado decorativo.
- Preguntas pendientes: Confirmar origen de humedad desde base del muro/piso/jardinera.; Validar estado del revoque o base soplada.; Solicitar m² reales antes de cotizar.
- Archivos fuente: ESTUCOR MOLDURAS.pdf, AQUABLOCK ULTRA.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf

### base_200 :: humedad_general

- Consulta: pared interior con humedad, moho y filtracion lateral
- Problema inferido: humedad_interior_general
- Similitud RAG: 0.5461
- Prioridad dominante: high
- Politicas: humedad_interior_negativa, bano_cocina_antihongos
- Politicas criticas: ninguna
- Dominantes: humedad_interior_negativa
- Sistema recomendado estructurado: Aquablock, Viniltex Baños y Cocinas, Aquablock / Aquablock Ultra según presión negativa y severidad., Estuco Acrílico si se requiere nivelación después del bloqueador de humedad., Viniltex Advanced, Intervinil, Pinturama
- Portafolio relacionado por inventario/RAG: ALTAS TEMPERATURAS 902 UEA800/3.7L/AA7, SILICONA ACETICA ALTA TEMP GRIS 50GR BLI, PQ PINTUCO FILL 12 GRIS 27505 20K, PQ PINTUCO FILL 12 BASE ACCENT 20K
- Productos prohibidos: Koraza como sellador de humedad interior, Koraza, Pintuco Fill, Pintucoat, Interseal, Intergard, Interthane 990, Koraza como sellador de humedad interior.
- Base / imprimante: Aquablock / Aquablock Ultra según presión negativa y severidad.
- Intermedios: Estuco Acrílico si se requiere nivelación después del bloqueador de humedad.
- Acabados finales: Viniltex Advanced, Intervinil, Pinturama
- Herramientas: Brocha, Rodillo, Lija / raspado para preparación
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Diagnosticar causa de humedad antes de pintar.; Remover base dañada y salitre donde aplique.; Retirar acabado soplado, salitre y base floja hasta sustrato sano antes del bloqueador.; Bloquear la humedad primero y solo despues reconstruir el acabado decorativo.; Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.
- Preguntas pendientes: Confirmar causa: base del muro, arriba, lateral o temporada.; Validar estado de la base/revoque.; Solicitar m² reales antes de cotizar.
- Archivos fuente: ALTA TEMPERATURA GRIS 902.pdf, PINTUCO FILL 12.pdf, INTERVINIL.pdf, PINTUCO FILL 7.pdf, AQUABLOCK ULTRA.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf

### base_200 :: fachada_exterior

- Consulta: fachada exterior expuesta a lluvia y sol con pintura soplada
- Problema inferido: fachada_exterior
- Similitud RAG: 0.6342
- Prioridad dominante: normal
- Politicas: fachada_alta_exposicion
- Politicas criticas: ninguna
- Dominantes: fachada_alta_exposicion
- Sistema recomendado estructurado: Koraza, Viniltex
- Portafolio relacionado por inventario/RAG: ESTUCO ACRILICO PINTUCO /KILO, ESTUCO ACRILICO PINTUCO / CUARTO, PQ KORAZA MAT BLANCO 2650 18.93L, PQ KORAZA MAT ACCENT BASE 127477 3.79L
- Productos prohibidos: Intervinil o Pinturama como acabado en fachadas de alta exposicion, Aquablock como acabado exterior, Intervinil, Pinturama, vinilos interiores, Aquablock, Intervinil o Pinturama como acabado en fachadas de alta exposicion., Aquablock como acabado exterior.
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Koraza, Viniltex
- Herramientas: Lija Abracol, Brocha Goya Profesional, Rodillo
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Remover pintura suelta o base soplada antes de repintar.; Retirar pintura suelta o base soplada antes del acabado exterior.
- Preguntas pendientes: Confirmar si es exterior real y nivel de deterioro.; Solicitar m² reales antes de cotizar.
- Archivos fuente: ESTUCO ACRILICO EXTERIOR FICHA TECNICA ACTUALIZADA.pdf, FICHA TECNICA KORAZA® PROTECCIÓN SOL & LLUVIA PINTURA IMPERMEABILIZANTE.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf, KORAZA IMPERMEABLE.pdf

### base_200 :: eternit_exterior

- Consulta: techo de eternit exterior repintado y envejecido
- Problema inferido: eternit_fibrocemento
- Similitud RAG: 0.5791
- Prioridad dominante: normal
- Politicas: eternit_fibrocemento_exterior
- Politicas criticas: ninguna
- Dominantes: eternit_fibrocemento_exterior
- Sistema recomendado estructurado: Sellomax, Koraza, Sellomax antes del acabado si el eternit ya esta pintado o envejecido.
- Portafolio relacionado por inventario/RAG: ESTUCO ACRILICO PINTUCO /KILO, ESTUCO ACRILICO PINTUCO / CUARTO, PQ PINTUCO FILL 7 GRIS 2753 20K, PQ PINTUCO FILL 7 GRIS 2753 4.2K
- Productos prohibidos: Intervinil, Pinturama o vinilos interiores como acabado exterior, rasqueteo o preparacion mecanica que genere polvo, Pinturama, vinilos interiores, Intervinil, Pinturama o vinilos interiores como acabado exterior., Lijado en seco, rasqueteo o preparacion mecanica que genere polvo.
- Base / imprimante: Sellomax antes del acabado si el eternit ya esta pintado o envejecido.
- Intermedios: ninguno
- Acabados finales: Koraza
- Herramientas: Hidrolavadora, Cepillo, Escoba de cerdas duras, Brocha, Rodillo
- Herramientas obligatorias: hidrolavadora, cepillo
- Herramientas prohibidas: Lijado en seco, lijas, rasqueta, preparacion mecanica
- Pasos obligatorios: Preparacion humeda con hidrolavadora, jabon, hipoclorito y cepillo; nunca lijar en seco ni rasquetear.; Retirar solo material flojo sin generar polvo.; Preparacion humeda obligatoria; nunca lijar en seco ni rasquetear.; En eternit envejecido o repintado, Sellomax va antes del acabado exterior.; Preparación húmeda obligatoria; nunca lijar en seco ni rasquetear.
- Preguntas pendientes: Confirmar si el fibrocemento es exterior y si ya esta pintado o envejecido.; Validar si hay polvo de asbesto o deterioro que obligue a preparacion humeda.; Solicitar m2 reales antes de cotizar.
- Archivos fuente: ESTUCO ACRILICO EXTERIOR FICHA TECNICA ACTUALIZADA.pdf

### base_200 :: ladrillo_vista

- Consulta: ladrillo a la vista exterior sin cambiar apariencia
- Problema inferido: ladrillo_vista
- Similitud RAG: 0.5162
- Prioridad dominante: normal
- Politicas: ladrillo_a_la_vista
- Politicas criticas: ninguna
- Dominantes: ladrillo_a_la_vista
- Sistema recomendado estructurado: Construcleaner Limpiador Desengrasante, Siliconite 7, Construcleaner Limpiador Desengrasante como limpieza previa.
- Portafolio relacionado por inventario/RAG: CONSTRUCLEANER RINSE LADRILLO ROJ 52.83G, SELLO SISMO LADRILLO CLARO CANECA 30 KG, CONSTRUCLEANER RESTAURADOR FACHA 52.83G, KORAZA LADRILLO SEMIMATE ROJO COL 1G
- Productos prohibidos: Acido muriatico para limpieza, Koraza si el objetivo es conservar el ladrillo a la vista, Koraza, acido muriatico, Acido muriatico para limpieza., Koraza si el objetivo es conservar el ladrillo a la vista.
- Base / imprimante: Construcleaner Limpiador Desengrasante como limpieza previa.
- Intermedios: ninguno
- Acabados finales: Siliconite 7
- Herramientas: Cepillo, Brocha, Rodillo segun absorcion
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Limpieza tecnica del ladrillo antes de protegerlo.; Limpiar el ladrillo con limpiador adecuado antes de hidrofugar.; Conservar la apariencia del sustrato; proteger sin formar pelicula opaca.
- Preguntas pendientes: Confirmar si el cliente quiere conservar la apariencia natural del ladrillo.; Validar si requiere solo limpieza o limpieza mas hidrofugacion.; Solicitar m2 reales antes de cotizar.
- Archivos fuente: CONSTRUCLEANER LADRILLO CLARO.pdf, CONSTRUCLEANER RESTAURADOR FACHADAS.pdf, CONSTRUCLEANER LADRILLO ROJO.pdf, CONSTRUCLEANER LIMPIADOR ECOLOGICO LADRILLO.pdf, ESTUCOR MOLDURAS.pdf, CONSTRUCLEANER LIMPIADOR NO CORROSIVO.pdf

### base_200 :: metal_alquidico_viejo

- Consulta: reja con esmalte sintetico viejo y anticorrosivo alquidico
- Problema inferido: metal_pintado_alquidico
- Similitud RAG: 0.548
- Prioridad dominante: normal
- Politicas: metal_pintado_alquidico
- Politicas criticas: ninguna
- Dominantes: metal_pintado_alquidico
- Sistema recomendado estructurado: Corrotec si se mantiene sistema alquidico. Wash Primer o sistema epoxico solo despues de remocion total., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: ESMALTE POLIURETANO AZUL INTENSO 11334 G, INTERTHANE 990 PHA130/3.7L/AA7, ESMALTE MAQUINARIA 11271 UFA102/3.7L/AA7, INTERSEAL 670HS EGA130/20L/AA7
- Productos prohibidos: Aplicar epoxicos o poliuretanos directamente sobre esmalte sintetico o anticorrosivo alquidico viejo, Interseal 670, Interseal, Intergard, Interthane 990, Pintucoat, Aplicar epoxicos o poliuretanos directamente sobre esmalte sintetico o anticorrosivo alquidico viejo.
- Base / imprimante: Corrotec si se mantiene sistema alquidico. Wash Primer o sistema epoxico solo despues de remocion total.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Lija Abracol, Brocha Goya Profesional
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Remocion total hasta metal desnudo antes de migrar a sistema epoxico o poliuretano.; Remocion total hasta metal desnudo antes de migrar a epoxicos o poliuretanos.
- Preguntas pendientes: Confirmar si la base actual es esmalte sintetico, anticorrosivo alquidico o pintura de aceite.; Validar si aceptan remocion total hasta metal desnudo.; Solicitar m2 o dimensiones antes de cotizar.
- Archivos fuente: ESMALTE POLIURETANO 113XX-11351 [ES].pdf, ESMALTE MAQUINARIA 11271 UFA102 [ES].pdf, DOMESTICO.pdf

### base_200 :: metal_oxidado

- Consulta: reja metalica con oxido superficial y corrosion
- Problema inferido: metal_oxidado
- Similitud RAG: 0.5598
- Prioridad dominante: normal
- Politicas: metal_oxidado_mantenimiento
- Politicas criticas: ninguna
- Dominantes: metal_oxidado_mantenimiento
- Sistema recomendado estructurado: Pintóxido, Corrotec, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: PQ CORROTEC PREMIUM MAT GRIS 507 3.79L, PQ CORROTEC PREMIUM MAT NEGRO 200 3.79L, FLASH RUST INHIBIT 10076 UEA700/20L/AA7, EPOXY PRIMER 10050 UEA301/3.7L/AA7
- Productos prohibidos: Viniltex, Koraza, Pintucoat
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Separar oxido superficial de corrosion profunda antes de definir transformador o remocion mecanica intensiva.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: CORROTEC.pdf, INHIBIDOR FLASH RUST 10076 UEA700 [ES].pdf, EPOXY PRIMER 10050 UEA301 - UEA302 [ES].pdf, PINTOXIDO.pdf

### base_200 :: metal_galvanizado

- Consulta: lamina zinc galvanizada nueva para pintar
- Problema inferido: none
- Similitud RAG: 0.5379
- Prioridad dominante: normal
- Politicas: metal_nuevo_galvanizado
- Politicas criticas: ninguna
- Dominantes: metal_nuevo_galvanizado
- Sistema recomendado estructurado: Wash Primer
- Portafolio relacionado por inventario/RAG: INTERZINC 52 EPA175/20L/AA7, INTERZINC 52 EPA177/3.7L/AA7, CORROTEC PRIMER EPOXICO 13350 PARTE B 5G, PQ CORROTEC PREMIUM MAT GRIS 507 3.79L
- Productos prohibidos: Interseal gris RAL 7038, Pintucoat
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: En galvanizado o metal no ferroso primero resolver adherencia con wash primer antes del anticorrosivo o acabado.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERZINC 52.pdf, corrotec-primer-epoxico-10070-13350.pdf, DOMESTICO.pdf, EPOXY ZINC PRIMER 10055 UEA650 - 10056 UEA651- 13267 UEA652 [ES].pdf

### base_200 :: piso_pesado

- Consulta: piso industrial de concreto para montacargas y estibadores
- Problema inferido: piso_industrial
- Similitud RAG: 0.3714
- Prioridad dominante: normal
- Politicas: piso_industrial_trafico_pesado
- Politicas criticas: ninguna
- Dominantes: piso_industrial_trafico_pesado
- Sistema recomendado estructurado: Interseal gris RAL 7038, Intergard 2002, Arena de Cuarzo ref 5891610, Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Pintucoat, Primer 50RS, Epoxy Primer 50RS, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Preparacion mecanica y desengrase profundo antes del sistema epoxico.; Confirmar m2, estado del concreto y tipo de trafico antes de cerrar sistema o cantidades.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### base_200 :: piso_medio

- Consulta: garaje de concreto interior con trafico medio
- Problema inferido: piso_industrial
- Similitud RAG: 0.4729
- Prioridad dominante: normal
- Politicas: piso_industrial_trafico_medio
- Politicas criticas: ninguna
- Dominantes: piso_industrial_trafico_medio
- Sistema recomendado estructurado: Interseal gris RAL 7038, Pintucoat, Interseal gris RAL 7038 para concreto cuando aplique., Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: PQ CANCHAS MAT BASE ACCENT 1876 18.93L, PQ CANCHAS MAT BASE ACCENT 1876 3.79L, MEG PRIMER ANTIC VERDE OLIV 513 AC 3.78L, MEG PRIMER PARA PLASTICOS 28600 AC 0.94L
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Primer 50RS, Epoxy Primer 50RS, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Confirmar si el piso es nuevo o ya pintado antes de definir compatibilidad.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: CANCHAS.pdf, IMPRIMANTE ACRILICO TRAFICO.pdf, IMPRIMANTE PARA TRAFICO ACRILICO NEGRO 10255632.pdf, MADETEC VITRIFLEX PARTE B.pdf

### base_200 :: piso_exterior_uv

- Consulta: piso industrial exterior al sol con sistema epoxico
- Problema inferido: piso_industrial
- Similitud RAG: 0.5196
- Prioridad dominante: normal
- Politicas: piso_exterior_uv
- Politicas criticas: ninguna
- Dominantes: piso_exterior_uv
- Sistema recomendado estructurado: Interthane 990 + Catalizador, Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Todo sistema epoxico de piso exterior expuesto al sol debe cerrarse con poliuretano UV.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### base_200 :: concreto_sin_curado

- Consulta: piso de concreto nuevo recien fundido sin curar
- Problema inferido: piso_industrial
- Similitud RAG: 0.5254
- Prioridad dominante: high
- Politicas: concreto_sin_curado
- Politicas criticas: ninguna
- Dominantes: concreto_sin_curado
- Sistema recomendado estructurado: Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: PQ PINTUCO FILL 12 GRIS 27505 20K, PQ PINTUCO FILL 12 BASE ACCENT 20K, ESTUCOR BULTO *25 KL LISTO, INTERSEAL670HS PA RAL7001 EGA130/1 0.85G
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Esperar minimo 28 dias de curado y validar humedad antes de pintar.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: PINTUCO FILL 12.pdf, ESTUCOR LISTO.pdf, INTERGARD 2002.pdf, CONSTRUCRIL.pdf, ESTUCOMASTIC 2 EN 1.pdf

### base_200 :: madera_exterior

- Consulta: deck de madera exterior expuesto a sol y lluvia
- Problema inferido: madera
- Similitud RAG: 0.5744
- Prioridad dominante: normal
- Politicas: madera_exterior
- Politicas criticas: ninguna
- Dominantes: madera_exterior
- Sistema recomendado estructurado: Barnex, Wood Stain, Esmalte Doméstico, Pintulux Máxima Protección
- Portafolio relacionado por inventario/RAG: ESTUCO ACRILICO PINTUCO /KILO, ESTUCO ACRILICO PINTUCO / CUARTO, K BARNEX EXTRA INCOLOR 7G GTS BARNIZ SD1, K BARNEX EXTRA INCOLOR 2G GTS BARNIZ SD1
- Productos prohibidos: Poliuretano Alto Trafico 1550/1551
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Barnex, Wood Stain, Esmalte Doméstico, Pintulux Máxima Protección
- Herramientas: Brocha Goya Profesional, Lijas Abracol 80-100 y 220-320, Removedor Pintuco
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Diagnosticar si es interior/exterior y si quiere transparente o color sólido.; En madera exterior usar sistema con proteccion UV y no un poliuretano transparente de piso interior.
- Preguntas pendientes: Confirmar si es interior o exterior.; Confirmar si quiere acabado transparente o color sólido.; Solicitar área o dimensiones antes de cotizar.
- Archivos fuente: ESTUCO ACRILICO EXTERIOR FICHA TECNICA ACTUALIZADA.pdf, BARNEX EXTRA PROTECCION.pdf, BARNIZ BARNEX 557.pdf, BARNEX EXTRA PROTECCIÓN.pdf

### base_200 :: madera_interior_vitrificado

- Consulta: escalera interior de madera para vitrificar con alto trafico
- Problema inferido: madera
- Similitud RAG: 0.5646
- Prioridad dominante: normal
- Politicas: madera_interior_alto_trafico
- Politicas criticas: ninguna
- Dominantes: madera_interior_alto_trafico
- Sistema recomendado estructurado: Poliuretano Alto Trafico 1550/1551, Barnex, Wood Stain, Esmalte Doméstico, Pintulux Máxima Protección
- Portafolio relacionado por inventario/RAG: MH VITRIFLEX SM 2130 3.79L, EPOXY PRIMER 50RS UEA402/3.7L/AA7, PQ PINTULUX WASH PRIMER 509A PT A 1 GL, MADETEC BO 2K LACA BA MATE 28452 1G
- Productos prohibidos: Barnex, Pintulac, barniz arquitectonico
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Barnex, Wood Stain, Esmalte Doméstico, Pintulux Máxima Protección
- Herramientas: Brocha Goya Profesional, Lijas Abracol 80-100 y 220-320, Removedor Pintuco
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Diagnosticar si es interior/exterior y si quiere transparente o color sólido.; Mezclar A+B y respetar el lijado fino entre manos en el sistema poliuretano interior.
- Preguntas pendientes: Confirmar si es interior o exterior.; Confirmar si quiere acabado transparente o color sólido.; Solicitar área o dimensiones antes de cotizar.
- Archivos fuente: MADETEC VITRIFLEX PARTE B.pdf, MADETEC VITRIFLEX PARTE A.pdf

### base_200 :: techo_concreto_grietas

- Consulta: techo de concreto con grietas y fisuras en terraza
- Problema inferido: none
- Similitud RAG: 0.5154
- Prioridad dominante: normal
- Politicas: techo_concreto_grietas
- Politicas criticas: ninguna
- Dominantes: techo_concreto_grietas
- Sistema recomendado estructurado: Pintuco Fill
- Portafolio relacionado por inventario/RAG: P7 KORAZA ELASTOMERICA GEN DEEP 18.93L, P7 KORAZA ELASTOMERICA GEN TINT 18.93L, PQ PINTUCO FILL 12 GRIS 27505 20K, PQ PINTUCO FILL 12 BASE ACCENT 20K
- Productos prohibidos: Koraza, Viniltex, Intervinil, Pinturama
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: En techos de concreto con grietas tratar la impermeabilizacion como sistema de cubierta, no como pintura decorativa.; Definir si requiere refuerzo de tela o tratamiento de fisuras antes del acabado final.
- Preguntas pendientes: ninguna
- Archivos fuente: KORAZA PROTECCION 3 EN 1.pdf, PINTUCO FILL 12.pdf, ESTUCOMASTIC 2 EN 1.pdf, KORAZA PRO 750 ELASTOMERICA.pdf, ESTUCO ACRILICO EXTERIOR FICHA TECNICA ACTUALIZADA.pdf

### base_200 :: bano_antihongos

- Consulta: baño con hongos por condensacion en muro interior
- Problema inferido: none
- Similitud RAG: 0.5283
- Prioridad dominante: normal
- Politicas: bano_cocina_antihongos
- Politicas criticas: ninguna
- Dominantes: bano_cocina_antihongos
- Sistema recomendado estructurado: Viniltex Baños y Cocinas
- Portafolio relacionado por inventario/RAG: PQ AQUABLOCK ULTRA MAT BLANC 27070 3.79L, PQ AQUABLOCK ULTRA MAT BLANC 27070 0.95L, KORAZA ELASTOMERICA 2651 NOGAL 5 GL, KORAZA ELASTOMERICA 2798 BALSO CANEC 5GL
- Productos prohibidos: Koraza, Pintucoat, Interseal, Intergard, Interthane 990
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.
- Preguntas pendientes: ninguna
- Archivos fuente: AQUABLOCK ULTRA.pdf, KORAZA 5.pdf, PINTURA ACRILICA PARA MANTENIMIENTO.pdf, ALTA TEMPERATURA GRIS 902.pdf, KORAZA IMPERMEABLE.pdf, ESTUCOR MOLDURAS.pdf

### base_200 :: cancha_deportiva

- Consulta: cancha deportiva exterior y sendero peatonal
- Problema inferido: fachada_exterior
- Similitud RAG: 0.5486
- Prioridad dominante: normal
- Politicas: fachada_alta_exposicion, cancha_sendero_peatonal
- Politicas criticas: ninguna
- Dominantes: fachada_alta_exposicion
- Sistema recomendado estructurado: Koraza, Pintura Canchas, Viniltex
- Portafolio relacionado por inventario/RAG: PQ CANCHAS MAT BASE ACCENT 1876 18.93L, PQ CANCHAS MAT BASE ACCENT 1876 3.79L, PINTURA CANCHAS RIO CUDALOSO AZ033-A 5GL, PINTURA CANCHAS AZ057-A CAUDAL AZUL 5 GL
- Productos prohibidos: Intervinil o Pinturama como acabado en fachadas de alta exposicion, Aquablock como acabado exterior, Intervinil, Pinturama, vinilos interiores, Aquablock, Pintucoat, Intergard 2002, Intergard 740, Intervinil o Pinturama como acabado en fachadas de alta exposicion., Aquablock como acabado exterior.
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Koraza, Viniltex
- Herramientas: Lija Abracol, Brocha Goya Profesional, Rodillo
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Remover pintura suelta o base soplada antes de repintar.; Retirar pintura suelta o base soplada antes del acabado exterior.; No mezclar la ruta deportiva con pisos industriales de montacargas o bodegas.
- Preguntas pendientes: Confirmar si es exterior real y nivel de deterioro.; Solicitar m² reales antes de cotizar.
- Archivos fuente: CANCHAS.pdf

### base_200 :: inmersion_agua_potable

- Consulta: tanque de agua potable con sistema para inmersion
- Problema inferido: none
- Similitud RAG: 0.3595
- Prioridad dominante: critical
- Politicas: inmersion_agua_potable_condicional
- Politicas criticas: inmersion_agua_potable_condicional
- Dominantes: inmersion_agua_potable_condicional
- Sistema recomendado estructurado: ninguno
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204
- Productos prohibidos: Pintucoat, Viniltex, Koraza, Pintulux 3 en 1
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### base_200 :: proteccion_incendio

- Consulta: estructura metalica con proteccion pasiva contra incendio e intumescente
- Problema inferido: metal_oxidado
- Similitud RAG: 0.4397
- Prioridad dominante: critical
- Politicas: proteccion_pasiva_incendio
- Politicas criticas: proteccion_pasiva_incendio
- Dominantes: proteccion_pasiva_incendio
- Sistema recomendado estructurado: Interchar, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Koraza, Viniltex, Pintulux 3 en 1
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Definir rating de fuego, perfil estructural y espesor requerido antes de recomendar el sistema intumescente.; No tratar la proteccion pasiva contra incendio como una pintura decorativa comun.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### base_200 :: alta_estetica_industrial

- Consulta: acabado industrial de alta estetica con alta retencion de color
- Problema inferido: none
- Similitud RAG: 0.4993
- Prioridad dominante: normal
- Politicas: acabado_industrial_alta_estetica
- Politicas criticas: ninguna
- Dominantes: acabado_industrial_alta_estetica
- Sistema recomendado estructurado: Interfine
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Corrotec, Pintulux 3 en 1
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Usar Interfine solo como acabado de altas prestaciones sobre sistema industrial compatible, no como primer.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### base_200 :: ambiente_quimico

- Consulta: planta industrial con ambiente quimico severo y corrosion industrial
- Problema inferido: metal_oxidado
- Similitud RAG: 0.4507
- Prioridad dominante: high
- Politicas: ambiente_quimico_industrial
- Politicas criticas: ninguna
- Dominantes: ambiente_quimico_industrial
- Sistema recomendado estructurado: Intergard, Interseal, Interthane 990 + Catalizador, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Corrotec, Pintulux 3 en 1, Viniltex, Koraza
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Resolver preparacion de superficie y ambiente de exposición antes de cerrar un sistema industrial anticorrosivo.; No degradar una consulta industrial severa a soluciones arquitectonicas o esmaltes domesticos.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### base_200 :: espuma_poliuretano

- Consulta: espuma de poliuretano para sellar huecos y aislamiento termico
- Problema inferido: none
- Similitud RAG: 0.7462
- Prioridad dominante: normal
- Politicas: espuma_poliuretano_sellado
- Politicas criticas: ninguna
- Dominantes: espuma_poliuretano_sellado
- Sistema recomendado estructurado: Espuma de Poliuretano
- Portafolio relacionado por inventario/RAG: ESPUMA DE POLIURETANO AFIX 500 ML, INTERTHANE 990 PHA130/20L/AA7, CINTA AISLANTE TEMFLEX PEQUEÑA, CINTA AISLANTE ELÉCTRICA NG 18MM * 5MT
- Productos prohibidos: Koraza, Viniltex, Pintuco Fill, Interseal
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Usar la espuma como sistema de sellado o relleno sobre superficie limpia, no como pintura o acabado decorativo.
- Preguntas pendientes: ninguna
- Archivos fuente: ESPUMA DE POLIURETANO.pdf

### base_200 :: esmalte_decorativo

- Consulta: esmalte top quality brillante para metal decorativo de mantenimiento liviano
- Problema inferido: metal_oxidado
- Similitud RAG: 0.6832
- Prioridad dominante: normal
- Politicas: esmalte_decorativo_mantenimiento
- Politicas criticas: ninguna
- Dominantes: esmalte_decorativo_mantenimiento
- Sistema recomendado estructurado: Esmaltes Top Quality, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: TOP QUALITY PLUS BLANCO SEMI BTE 1G, PQ PINTULUX 3EN1 BR NEGRO 95 3.79L, PQ PINTULUX 3EN1 BR BLANCO 11 3.79L, PQ CORROTEC PREMIUM MAT GRIS 507 3.79L
- Productos prohibidos: Interseal, Intergard, Interthane 990
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Tratar el caso como acabado decorativo o mantenimiento liviano, no como sistema industrial 2K.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: ESMALTES TOP QUALITY.pdf, PINTULUX 3 EN 1 BRILLANTE.pdf, DOMESTICO.pdf

### base_200 :: arquitectonico_base_agua

- Consulta: muro de casa con pintura base agua y vinilo existente
- Problema inferido: none
- Similitud RAG: 0.5546
- Prioridad dominante: normal
- Politicas: arquitectonico_sobre_base_agua
- Politicas criticas: ninguna
- Dominantes: arquitectonico_sobre_base_agua
- Sistema recomendado estructurado: ninguno
- Portafolio relacionado por inventario/RAG: PINTUCOAT BASE AGUA GRIS 1G, PINTUCOAT BASE AGUA NEGRO 1G, PQ VINILTEX ADV MAT BLANCO 1501 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L
- Productos prohibidos: Interthane 990, Interseal, Intergard, Pintucoat
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Mantener compatibilidad de familia: agua con agua sobre sistemas arquitectonicos existentes.
- Preguntas pendientes: ninguna
- Archivos fuente: EPÓXICA BASE AGUA.pdf, PINTURA ANTIGRAFITTI.pdf, KORAZA PROTECCION 3 EN 1.pdf, AQUABLOCK ULTRA.pdf

### base_200 :: interior_koraza_redirect

- Consulta: koraza para muro interior de sala y pasillo cerrado
- Problema inferido: none
- Similitud RAG: 0.5603
- Prioridad dominante: normal
- Politicas: interior_koraza_redirect
- Politicas criticas: ninguna
- Dominantes: interior_koraza_redirect
- Sistema recomendado estructurado: Viniltex Advanced
- Portafolio relacionado por inventario/RAG: KORAZA ELASTOMERICA 2651 NOGAL 5 GL, KORAZA ELASTOMERICA 2677 CIPRES CANEC 5G, P7 KORAZA ELASTOMERICA GEN PASTEL 18.93L, P7 KORAZA ELASTOMERICA GEN DEEP 18.93L
- Productos prohibidos: Koraza
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Si el cliente pide Koraza para interior cerrado, reconducir a un vinilo premium compatible con ese uso.
- Preguntas pendientes: ninguna
- Archivos fuente: KORAZA PROTECCION 3 EN 1.pdf, KORAZA IMPERMEABLE.pdf, KORAZA PRO 750 ELASTOMERICA.pdf, ESTUCOR MOLDURAS.pdf

## Grupo: multi_surface

### multisurface_320 :: fachada_y_bano

- Consulta: fachada exterior con pintura soplada y ademas baño interior con hongos por condensacion
- Problema inferido: fachada_exterior
- Similitud RAG: 0.5826
- Prioridad dominante: normal
- Politicas: fachada_alta_exposicion, bano_cocina_antihongos
- Politicas criticas: ninguna
- Dominantes: fachada_alta_exposicion
- Sistema recomendado estructurado: Koraza, Viniltex Baños y Cocinas, Viniltex
- Portafolio relacionado por inventario/RAG: KORAZA ELASTOMERICA 2677 CIPRES CANEC 5G, KORAZA ELASTOMERICA 2651 NOGAL 5 GL, PQ DOMESTICO BR BLANCO P-11 3.79L, PQ DOMESTICO BR NEGRO P-95 3.79L
- Productos prohibidos: Intervinil o Pinturama como acabado en fachadas de alta exposicion, Aquablock como acabado exterior, Intervinil, Pinturama, vinilos interiores, Aquablock, Koraza, Pintucoat, Interseal, Intergard, Interthane 990, Intervinil o Pinturama como acabado en fachadas de alta exposicion., Aquablock como acabado exterior.
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Koraza, Viniltex
- Herramientas: Lija Abracol, Brocha Goya Profesional, Rodillo
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Remover pintura suelta o base soplada antes de repintar.; Retirar pintura suelta o base soplada antes del acabado exterior.; Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.
- Preguntas pendientes: Confirmar si es exterior real y nivel de deterioro.; Solicitar m² reales antes de cotizar.
- Archivos fuente: KORAZA PROTECCION 3 EN 1.pdf, DOMESTICO.pdf, PINTURA ACRILICA PARA MANTENIMIENTO.pdf, ESTUCO ACRILICO EXTERIOR FICHA TECNICA ACTUALIZADA.pdf, KORAZA DOBLE VIDA.pdf, CONSTRUCLEANER RESTAURADOR FACHADAS.pdf

### multisurface_320 :: ladrillo_y_bano

- Consulta: ladrillo a la vista exterior sin cambiar apariencia y además baño interior con hongos
- Problema inferido: ladrillo_vista
- Similitud RAG: 0.5486
- Prioridad dominante: normal
- Politicas: ladrillo_a_la_vista, bano_cocina_antihongos
- Politicas criticas: ninguna
- Dominantes: ladrillo_a_la_vista
- Sistema recomendado estructurado: Construcleaner Limpiador Desengrasante, Siliconite 7, Viniltex Baños y Cocinas, Construcleaner Limpiador Desengrasante como limpieza previa.
- Portafolio relacionado por inventario/RAG: CONSTRUCLEANER RINSE LADRILLO ROJ 52.83G, PQ KORAZA MAT LADRILLO 2804 3.79L, SELLO SISMO LADRILLO CLARO CANECA 30 KG, KORAZA LADRILLO SEMIMATE ROJO COL 1G
- Productos prohibidos: Acido muriatico para limpieza, Koraza si el objetivo es conservar el ladrillo a la vista, Koraza, acido muriatico, Pintucoat, Interseal, Intergard, Interthane 990, Acido muriatico para limpieza., Koraza si el objetivo es conservar el ladrillo a la vista.
- Base / imprimante: Construcleaner Limpiador Desengrasante como limpieza previa.
- Intermedios: ninguno
- Acabados finales: Siliconite 7
- Herramientas: Cepillo, Brocha, Rodillo segun absorcion
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Limpieza tecnica del ladrillo antes de protegerlo.; Limpiar el ladrillo con limpiador adecuado antes de hidrofugar.; Conservar la apariencia del sustrato; proteger sin formar pelicula opaca.; Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.
- Preguntas pendientes: Confirmar si el cliente quiere conservar la apariencia natural del ladrillo.; Validar si requiere solo limpieza o limpieza mas hidrofugacion.; Solicitar m2 reales antes de cotizar.
- Archivos fuente: CONSTRUCLEANER RINSE LADRILLO ROJO.pdf, CONSTRUCLEANER LADRILLO CLARO.pdf, CONSTRUCLEANER LADRILLO ROJO.pdf, CONSTRUCLEANER LIMPIADOR ECOLOGICO LADRILLO.pdf, CONSTRUCLEANER RESTAURADOR FACHADAS.pdf

### multisurface_320 :: eternit_y_grietas

- Consulta: techo de eternit exterior envejecido y tambien techo de concreto con grietas en terraza
- Problema inferido: eternit_fibrocemento
- Similitud RAG: 0.532
- Prioridad dominante: normal
- Politicas: eternit_fibrocemento_exterior, techo_concreto_grietas
- Politicas criticas: ninguna
- Dominantes: eternit_fibrocemento_exterior
- Sistema recomendado estructurado: Sellomax, Koraza, Pintuco Fill, Sellomax antes del acabado si el eternit ya esta pintado o envejecido.
- Portafolio relacionado por inventario/RAG: ESTUCO ACRILICO PINTUCO /KILO, ESTUCO ACRILICO PINTUCO / CUARTO, KORAZA ELASTOMERICA NE-017-P SENALROS 5G, PQ KORAZA MAT BLANCO 2650 18.93L
- Productos prohibidos: Intervinil, Pinturama o vinilos interiores como acabado exterior, rasqueteo o preparacion mecanica que genere polvo, Pinturama, vinilos interiores, Koraza, Viniltex, Intervinil, Pinturama o vinilos interiores como acabado exterior., Lijado en seco, rasqueteo o preparacion mecanica que genere polvo.
- Base / imprimante: Sellomax antes del acabado si el eternit ya esta pintado o envejecido.
- Intermedios: ninguno
- Acabados finales: Koraza
- Herramientas: Hidrolavadora, Cepillo, Escoba de cerdas duras, Brocha, Rodillo
- Herramientas obligatorias: hidrolavadora, cepillo
- Herramientas prohibidas: Lijado en seco, lijas, rasqueta, preparacion mecanica
- Pasos obligatorios: Preparacion humeda con hidrolavadora, jabon, hipoclorito y cepillo; nunca lijar en seco ni rasquetear.; Retirar solo material flojo sin generar polvo.; Preparacion humeda obligatoria; nunca lijar en seco ni rasquetear.; En eternit envejecido o repintado, Sellomax va antes del acabado exterior.; En techos de concreto con grietas tratar la impermeabilizacion como sistema de cubierta, no como pintura decorativa.; Definir si requiere refuerzo de tela o tratamiento de fisuras antes del acabado final.; Preparación húmeda obligatoria; nunca lijar en seco ni rasquetear.
- Preguntas pendientes: Confirmar si el fibrocemento es exterior y si ya esta pintado o envejecido.; Validar si hay polvo de asbesto o deterioro que obligue a preparacion humeda.; Solicitar m2 reales antes de cotizar.
- Archivos fuente: ESTUCO ACRILICO EXTERIOR FICHA TECNICA ACTUALIZADA.pdf, KORAZA PRO 750 ELASTOMERICA.pdf, KORAZA DOBLE VIDA.pdf, PINTUCO FILL 12.pdf, KORAZA IMPERMEABLE.pdf

### multisurface_320 :: tanque_e_incendio

- Consulta: tanque de agua potable con zona sumergida y estructura con proteccion pasiva contra incendio e intumescente
- Problema inferido: none
- Similitud RAG: 0.4057
- Prioridad dominante: critical
- Politicas: inmersion_agua_potable_condicional, proteccion_pasiva_incendio
- Politicas criticas: inmersion_agua_potable_condicional, proteccion_pasiva_incendio
- Dominantes: inmersion_agua_potable_condicional, proteccion_pasiva_incendio
- Sistema recomendado estructurado: Interchar
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, PINTURA INTUMESCENTE BLANC CANECA DE 5 G, PINTURA INTUMESCENTE BLANC BASE AGUA CAN
- Productos prohibidos: Pintucoat, Viniltex, Koraza, Pintulux 3 en 1
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.; Definir rating de fuego, perfil estructural y espesor requerido antes de recomendar el sistema intumescente.; No tratar la proteccion pasiva contra incendio como una pintura decorativa comun.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: techo_y_galvanizado

- Consulta: techo de concreto con grietas en terraza y tambien lamina galvanizada nueva para pintar
- Problema inferido: none
- Similitud RAG: 0.5408
- Prioridad dominante: normal
- Politicas: techo_concreto_grietas, metal_nuevo_galvanizado
- Politicas criticas: ninguna
- Dominantes: techo_concreto_grietas
- Sistema recomendado estructurado: Pintuco Fill, Wash Primer
- Portafolio relacionado por inventario/RAG: PQ PINTUCO FILL 12 GRIS 27505 20K, PQ PINTUCO FILL 12 BASE ACCENT 20K, P7 KORAZA ELASTOMERICA GEN DEEP 18.93L, P7 KORAZA ELASTOMERICA GEN TINT 18.93L
- Productos prohibidos: Koraza, Viniltex, Intervinil, Pinturama, Interseal gris RAL 7038, Pintucoat
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: En techos de concreto con grietas tratar la impermeabilizacion como sistema de cubierta, no como pintura decorativa.; Definir si requiere refuerzo de tela o tratamiento de fisuras antes del acabado final.; En galvanizado o metal no ferroso primero resolver adherencia con wash primer antes del anticorrosivo o acabado.
- Preguntas pendientes: ninguna
- Archivos fuente: PINTUCO FILL 12.pdf, KORAZA PROTECCION 3 EN 1.pdf, DOMESTICO.pdf, KORAZA DOBLE VIDA.pdf

### multisurface_320 :: madera_exterior_e_interior

- Consulta: deck exterior de madera expuesto al sol y lluvia y ademas escalera interior de madera para vitrificar
- Problema inferido: madera
- Similitud RAG: 0.5383
- Prioridad dominante: normal
- Politicas: madera_exterior, madera_interior_alto_trafico
- Politicas criticas: ninguna
- Dominantes: madera_exterior
- Sistema recomendado estructurado: Barnex, Wood Stain, Poliuretano Alto Trafico 1550/1551, Esmalte Doméstico, Pintulux Máxima Protección
- Portafolio relacionado por inventario/RAG: ESTUCOR BULTO *25 KLS MOLDURA, ESTUCOR BULTO *25 KL LISTO, INTERTHANE 990 PHA130/20L/AA7, INTERTHANE 990 PHA130/3.7L/AA7
- Productos prohibidos: Poliuretano Alto Trafico 1550/1551, Barnex, Pintulac, barniz arquitectonico
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Barnex, Wood Stain, Esmalte Doméstico, Pintulux Máxima Protección
- Herramientas: Brocha Goya Profesional, Lijas Abracol 80-100 y 220-320, Removedor Pintuco
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Diagnosticar si es interior/exterior y si quiere transparente o color sólido.; En madera exterior usar sistema con proteccion UV y no un poliuretano transparente de piso interior.; Mezclar A+B y respetar el lijado fino entre manos en el sistema poliuretano interior.
- Preguntas pendientes: Confirmar si es interior o exterior.; Confirmar si quiere acabado transparente o color sólido.; Solicitar área o dimensiones antes de cotizar.
- Archivos fuente: ESTUCOR MOLDURAS.pdf, ESMALTE POLIURETANO MADERA.pdf, DESMOLDANTE GLASST PRIME.pdf, ESTUCO ACRILICO EXTERIOR FICHA TECNICA ACTUALIZADA.pdf, MADETEC VITRIFLEX PARTE A.pdf

### multisurface_320 :: sendero_y_galvanizado

- Consulta: sendero peatonal exterior y porton galvanizado nuevo para pintar en el mismo proyecto
- Problema inferido: fachada_exterior
- Similitud RAG: 0.512
- Prioridad dominante: normal
- Politicas: fachada_alta_exposicion, cancha_sendero_peatonal, metal_nuevo_galvanizado
- Politicas criticas: ninguna
- Dominantes: fachada_alta_exposicion
- Sistema recomendado estructurado: Koraza, Pintura Canchas, Wash Primer, Viniltex
- Portafolio relacionado por inventario/RAG: PQ VINILTEX ADV MAT BLANCO 1501 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L, PQ CANCHAS MAT BASE ACCENT 1876 18.93L, PQ CANCHAS MAT BASE ACCENT 1876 3.79L
- Productos prohibidos: Intervinil o Pinturama como acabado en fachadas de alta exposicion, Aquablock como acabado exterior, Intervinil, Pinturama, vinilos interiores, Aquablock, Pintucoat, Intergard 2002, Intergard 740, Interseal gris RAL 7038, Intervinil o Pinturama como acabado en fachadas de alta exposicion., Aquablock como acabado exterior.
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Koraza, Viniltex
- Herramientas: Lija Abracol, Brocha Goya Profesional, Rodillo
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Remover pintura suelta o base soplada antes de repintar.; Retirar pintura suelta o base soplada antes del acabado exterior.; No mezclar la ruta deportiva con pisos industriales de montacargas o bodegas.; En galvanizado o metal no ferroso primero resolver adherencia con wash primer antes del anticorrosivo o acabado.
- Preguntas pendientes: Confirmar si es exterior real y nivel de deterioro.; Solicitar m² reales antes de cotizar.
- Archivos fuente: PINTURA PARA CANCHAS.pdf, CANCHAS.pdf, DOMESTICO.pdf, PINTURA PARA TRAFICO ACRÍLICA TERTRAFICO 29205 BLANCA(TERINSA).pdf, Interseal 670 HS.pdf

### multisurface_320 :: espuma_y_bano

- Consulta: espuma de poliuretano para sellar huecos en un punto y además baño interior con hongos
- Problema inferido: none
- Similitud RAG: 0.7016
- Prioridad dominante: normal
- Politicas: bano_cocina_antihongos, espuma_poliuretano_sellado
- Politicas criticas: ninguna
- Dominantes: bano_cocina_antihongos
- Sistema recomendado estructurado: Viniltex Baños y Cocinas, Espuma de Poliuretano
- Portafolio relacionado por inventario/RAG: ESPUMA DE POLIURETANO AFIX 500 ML, INTERTHANE 990 PHA130/20L/AA7, CINTA AISLANTE TEMFLEX PEQUEÑA, CINTA AISLANTE ELÉCTRICA NG 18MM * 5MT
- Productos prohibidos: Koraza, Pintucoat, Interseal, Intergard, Interthane 990, Viniltex, Pintuco Fill
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.; Usar la espuma como sistema de sellado o relleno sobre superficie limpia, no como pintura o acabado decorativo.
- Preguntas pendientes: ninguna
- Archivos fuente: ESPUMA DE POLIURETANO.pdf

### multisurface_320 :: agua_potable_y_galvanizado

- Consulta: tanque de agua potable y lamina zinc galvanizada nueva para pintar en otra zona
- Problema inferido: none
- Similitud RAG: 0.4155
- Prioridad dominante: critical
- Politicas: metal_nuevo_galvanizado, inmersion_agua_potable_condicional
- Politicas criticas: inmersion_agua_potable_condicional
- Dominantes: inmersion_agua_potable_condicional
- Sistema recomendado estructurado: Wash Primer
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Interseal gris RAL 7038, Pintucoat, Viniltex, Koraza, Pintulux 3 en 1
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: En galvanizado o metal no ferroso primero resolver adherencia con wash primer antes del anticorrosivo o acabado.; Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: incendio_y_alta_estetica

- Consulta: estructura con proteccion contra incendio intumescente y acabado industrial de alta estetica con retencion de color
- Problema inferido: none
- Similitud RAG: 0.5314
- Prioridad dominante: critical
- Politicas: proteccion_pasiva_incendio, acabado_industrial_alta_estetica
- Politicas criticas: proteccion_pasiva_incendio
- Dominantes: proteccion_pasiva_incendio
- Sistema recomendado estructurado: Interchar, Interfine
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Koraza, Viniltex, Pintulux 3 en 1, Corrotec
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Definir rating de fuego, perfil estructural y espesor requerido antes de recomendar el sistema intumescente.; No tratar la proteccion pasiva contra incendio como una pintura decorativa comun.; Usar Interfine solo como acabado de altas prestaciones sobre sistema industrial compatible, no como primer.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: ambiente_quimico_e_incendio

- Consulta: planta industrial con ambiente quimico severo y ademas proteccion pasiva contra incendio en estructura metalica
- Problema inferido: metal_oxidado
- Similitud RAG: 0.5045
- Prioridad dominante: critical
- Politicas: proteccion_pasiva_incendio, ambiente_quimico_industrial
- Politicas criticas: proteccion_pasiva_incendio
- Dominantes: proteccion_pasiva_incendio
- Sistema recomendado estructurado: Interchar, Intergard, Interseal, Interthane 990 + Catalizador, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Koraza, Viniltex, Pintulux 3 en 1, Corrotec
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Definir rating de fuego, perfil estructural y espesor requerido antes de recomendar el sistema intumescente.; No tratar la proteccion pasiva contra incendio como una pintura decorativa comun.; Resolver preparacion de superficie y ambiente de exposición antes de cerrar un sistema industrial anticorrosivo.; No degradar una consulta industrial severa a soluciones arquitectonicas o esmaltes domesticos.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: eternit_y_ladrillo

- Consulta: cubierta de eternit exterior envejecida y muro de ladrillo a la vista que se quiere conservar
- Problema inferido: eternit_fibrocemento
- Similitud RAG: 0.5366
- Prioridad dominante: normal
- Politicas: eternit_fibrocemento_exterior, ladrillo_a_la_vista
- Politicas criticas: ninguna
- Dominantes: eternit_fibrocemento_exterior
- Sistema recomendado estructurado: Sellomax, Koraza, Construcleaner Limpiador Desengrasante, Siliconite 7, Sellomax antes del acabado si el eternit ya esta pintado o envejecido.
- Portafolio relacionado por inventario/RAG: CONSTRUCLEANER RESTAURADOR FACHA 52.83G, CONSTRUCLEANER RINSE LADRILLO ROJ 52.83G, KORAZA LADRILLO LIMPIADOR INCOLO 2801 1G, P7 KORAZA ELASTOMERICA GEN ACCENT 18.93L
- Productos prohibidos: Intervinil, Pinturama o vinilos interiores como acabado exterior, rasqueteo o preparacion mecanica que genere polvo, Pinturama, vinilos interiores, Koraza, acido muriatico, Intervinil, Pinturama o vinilos interiores como acabado exterior., Lijado en seco, rasqueteo o preparacion mecanica que genere polvo.
- Base / imprimante: Sellomax antes del acabado si el eternit ya esta pintado o envejecido.
- Intermedios: ninguno
- Acabados finales: Koraza
- Herramientas: Hidrolavadora, Cepillo, Escoba de cerdas duras, Brocha, Rodillo
- Herramientas obligatorias: hidrolavadora, cepillo
- Herramientas prohibidas: Lijado en seco, lijas, rasqueta, preparacion mecanica
- Pasos obligatorios: Preparacion humeda con hidrolavadora, jabon, hipoclorito y cepillo; nunca lijar en seco ni rasquetear.; Retirar solo material flojo sin generar polvo.; Preparacion humeda obligatoria; nunca lijar en seco ni rasquetear.; En eternit envejecido o repintado, Sellomax va antes del acabado exterior.; Limpiar el ladrillo con limpiador adecuado antes de hidrofugar.; Conservar la apariencia del sustrato; proteger sin formar pelicula opaca.; Preparación húmeda obligatoria; nunca lijar en seco ni rasquetear.
- Preguntas pendientes: Confirmar si el fibrocemento es exterior y si ya esta pintado o envejecido.; Validar si hay polvo de asbesto o deterioro que obligue a preparacion humeda.; Solicitar m2 reales antes de cotizar.
- Archivos fuente: CONSTRUCLEANER RESTAURADOR FACHADAS.pdf, CONSTRUCLEANER LIMPIADOR ECOLOGICO LADRILLO.pdf, KORAZA IMPERMEABLE.pdf, CONSTRUCLEANER LIMPIADOR NO CORROSIVO.pdf, KORAZA 5.pdf

### multisurface_320 :: cancha_y_bano

- Consulta: cancha deportiva exterior y ademas baño interior con hongos en el mismo complejo
- Problema inferido: fachada_exterior
- Similitud RAG: 0.4314
- Prioridad dominante: normal
- Politicas: fachada_alta_exposicion, bano_cocina_antihongos, cancha_sendero_peatonal
- Politicas criticas: ninguna
- Dominantes: fachada_alta_exposicion
- Sistema recomendado estructurado: Koraza, Viniltex Baños y Cocinas, Pintura Canchas, Viniltex
- Portafolio relacionado por inventario/RAG: PQ CANCHAS MAT BASE ACCENT 1876 18.93L, PQ CANCHAS MAT BASE ACCENT 1876 3.79L, PQ VINILTEX ADV MAT BLANCO 1501 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L
- Productos prohibidos: Intervinil o Pinturama como acabado en fachadas de alta exposicion, Aquablock como acabado exterior, Intervinil, Pinturama, vinilos interiores, Aquablock, Koraza, Pintucoat, Interseal, Intergard, Interthane 990, Intergard 2002, Intergard 740, Intervinil o Pinturama como acabado en fachadas de alta exposicion., Aquablock como acabado exterior.
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Koraza, Viniltex
- Herramientas: Lija Abracol, Brocha Goya Profesional, Rodillo
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Remover pintura suelta o base soplada antes de repintar.; Retirar pintura suelta o base soplada antes del acabado exterior.; Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.; No mezclar la ruta deportiva con pisos industriales de montacargas o bodegas.
- Preguntas pendientes: Confirmar si es exterior real y nivel de deterioro.; Solicitar m² reales antes de cotizar.
- Archivos fuente: CANCHAS.pdf, PINTURA PARA CANCHAS.pdf, PINTUCO FILL 7.pdf

### multisurface_320 :: espuma_y_terraza

- Consulta: espuma expansiva para sellar paso de tuberia y tambien techo de concreto con grietas en terraza
- Problema inferido: none
- Similitud RAG: 0.6301
- Prioridad dominante: normal
- Politicas: techo_concreto_grietas, espuma_poliuretano_sellado
- Politicas criticas: ninguna
- Dominantes: techo_concreto_grietas
- Sistema recomendado estructurado: Pintuco Fill, Espuma de Poliuretano
- Portafolio relacionado por inventario/RAG: ESPUMA DE POLIURETANO AFIX 500 ML, INTERTHANE 990 PHA130/20L/AA7, PQ ESTUCOMASTIC 2 EN 1 WHITE 1K, PQ ESTUCOMASTIC BLANCO 18070 3.79L 5K
- Productos prohibidos: Koraza, Viniltex, Intervinil, Pinturama, Pintuco Fill, Interseal
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: En techos de concreto con grietas tratar la impermeabilizacion como sistema de cubierta, no como pintura decorativa.; Definir si requiere refuerzo de tela o tratamiento de fisuras antes del acabado final.; Usar la espuma como sistema de sellado o relleno sobre superficie limpia, no como pintura o acabado decorativo.
- Preguntas pendientes: ninguna
- Archivos fuente: ESPUMA DE POLIURETANO.pdf, ESTUCOMASTIC 2 EN 1.pdf, PINTUCO FILL 12.pdf

### multisurface_320 :: bano_y_koraza_interior

- Consulta: baño interior con hongos y adicionalmente muro interior de sala donde el cliente menciona Koraza
- Problema inferido: none
- Similitud RAG: 0.62
- Prioridad dominante: normal
- Politicas: bano_cocina_antihongos, interior_koraza_redirect
- Politicas criticas: ninguna
- Dominantes: bano_cocina_antihongos
- Sistema recomendado estructurado: Viniltex Baños y Cocinas, Viniltex Advanced
- Portafolio relacionado por inventario/RAG: P7 KORAZA ELASTOMERICA GEN ACCENT 18.93L, P7 KORAZA ELASTOMERICA GEN DEEP 18.93L, KORAZA ELASTOMERICA 2651 NOGAL 5 GL, KORAZA ELASTOMERICA 2798 BALSO CANEC 5GL
- Productos prohibidos: Koraza, Pintucoat, Interseal, Intergard, Interthane 990
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.; Si el cliente pide Koraza para interior cerrado, reconducir a un vinilo premium compatible con ese uso.
- Preguntas pendientes: ninguna
- Archivos fuente: KORAZA IMPERMEABLE.pdf, KORAZA 5.pdf, KORAZA DOBLE VIDA.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf, FICHA TECNICA KORAZA® PROTECCIÓN SOL & LLUVIA PINTURA IMPERMEABILIZANTE.pdf, KORAZA PROTECCION 3 EN 1.pdf

### multisurface_320 :: agua_potable_y_espuma

- Consulta: tanque de agua potable y sellado de pasos con espuma de poliuretano en otra zona del proyecto
- Problema inferido: none
- Similitud RAG: 0.406
- Prioridad dominante: critical
- Politicas: espuma_poliuretano_sellado, inmersion_agua_potable_condicional
- Politicas criticas: inmersion_agua_potable_condicional
- Dominantes: inmersion_agua_potable_condicional
- Sistema recomendado estructurado: Espuma de Poliuretano
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Koraza, Viniltex, Pintuco Fill, Interseal, Pintucoat, Pintulux 3 en 1
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Usar la espuma como sistema de sellado o relleno sobre superficie limpia, no como pintura o acabado decorativo.; Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

## Grupo: contradiction

### multisurface_320 :: koraza_en_bano_interior

- Consulta: quiero Koraza para baño interior con hongos y condensacion
- Problema inferido: none
- Similitud RAG: 0.6413
- Prioridad dominante: normal
- Politicas: bano_cocina_antihongos, interior_koraza_redirect
- Politicas criticas: ninguna
- Dominantes: bano_cocina_antihongos
- Sistema recomendado estructurado: Viniltex Baños y Cocinas, Viniltex Advanced
- Portafolio relacionado por inventario/RAG: P7 KORAZA ELASTOMERICA GEN ACCENT 18.93L, P7 KORAZA ELASTOMERICA GEN PASTEL 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L, PQ KORAZA MAT ACCENT BASE 127477 3.79L
- Productos prohibidos: Koraza, Pintucoat, Interseal, Intergard, Interthane 990
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.; Si el cliente pide Koraza para interior cerrado, reconducir a un vinilo premium compatible con ese uso.
- Preguntas pendientes: ninguna
- Archivos fuente: KORAZA IMPERMEABLE.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf, FICHA TECNICA KORAZA® PROTECCIÓN SOL & LLUVIA PINTURA IMPERMEABILIZANTE.pdf, KORAZA PROTECCION 3 EN 1.pdf, KORAZA 5.pdf

### multisurface_320 :: koraza_en_humedad_interior

- Consulta: quiero Koraza para muro interior con humedad, moho y salitre
- Problema inferido: humedad_interior_general
- Similitud RAG: 0.6699
- Prioridad dominante: high
- Politicas: humedad_interior_negativa, interior_koraza_redirect
- Politicas criticas: ninguna
- Dominantes: humedad_interior_negativa
- Sistema recomendado estructurado: Aquablock, Viniltex Advanced, Aquablock / Aquablock Ultra según presión negativa y severidad., Estuco Acrílico si se requiere nivelación después del bloqueador de humedad., Intervinil, Pinturama
- Portafolio relacionado por inventario/RAG: P7 KORAZA ELASTOMERICA GEN ACCENT 18.93L, P7 KORAZA ELASTOMERICA GEN PASTEL 18.93L, KORAZA ELASTOMERICA 2651 NOGAL 5 GL, KORAZA ELASTOMERICA 2798 BALSO CANEC 5GL
- Productos prohibidos: Koraza como sellador de humedad interior, Koraza, Pintuco Fill, Koraza como sellador de humedad interior.
- Base / imprimante: Aquablock / Aquablock Ultra según presión negativa y severidad.
- Intermedios: Estuco Acrílico si se requiere nivelación después del bloqueador de humedad.
- Acabados finales: Viniltex Advanced, Intervinil, Pinturama
- Herramientas: Brocha, Rodillo, Lija / raspado para preparación
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Diagnosticar causa de humedad antes de pintar.; Remover base dañada y salitre donde aplique.; Retirar acabado soplado, salitre y base floja hasta sustrato sano antes del bloqueador.; Bloquear la humedad primero y solo despues reconstruir el acabado decorativo.; Si el cliente pide Koraza para interior cerrado, reconducir a un vinilo premium compatible con ese uso.
- Preguntas pendientes: Confirmar causa: base del muro, arriba, lateral o temporada.; Validar estado de la base/revoque.; Solicitar m² reales antes de cotizar.
- Archivos fuente: KORAZA IMPERMEABLE.pdf, KORAZA 5.pdf, KORAZA DOBLE VIDA.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf

### multisurface_320 :: pintucoat_en_cancha

- Consulta: quiero Pintucoat para cancha deportiva exterior
- Problema inferido: piso_industrial
- Similitud RAG: 0.7256
- Prioridad dominante: normal
- Politicas: piso_exterior_uv, cancha_sendero_peatonal
- Politicas criticas: ninguna
- Dominantes: piso_exterior_uv
- Sistema recomendado estructurado: Interthane 990 + Catalizador, Pintura Canchas, Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: PQ VINILTEX ADV MAT BLANCO 1501 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L, MEG PRIMER ANTIC VERDE OLIV 513 AC 3.78L, MEG PRIMER ANTIC NEGRO 513N AC 3.78L
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Pintucoat, Intergard 2002, Intergard 740, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Todo sistema epoxico de piso exterior expuesto al sol debe cerrarse con poliuretano UV.; No mezclar la ruta deportiva con pisos industriales de montacargas o bodegas.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: PINTURA PARA CANCHAS.pdf

### multisurface_320 :: pintucoat_en_galvanizado

- Consulta: quiero Pintucoat para lamina galvanizada nueva
- Problema inferido: piso_industrial
- Similitud RAG: 0.6221
- Prioridad dominante: normal
- Politicas: metal_nuevo_galvanizado
- Politicas criticas: ninguna
- Dominantes: metal_nuevo_galvanizado
- Sistema recomendado estructurado: Wash Primer, Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: CORROTEC PRIMER EPOXICO 13350 PARTE B 5G, PQ CORROTEC PREMIUM MAT GRIS 507 3.79L, PQ CORROTEC PREMIUM MAT NEGRO 200 3.79L, PQ DOMESTICO BR BLANCO P-11 3.79L
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Interseal gris RAL 7038, Pintucoat, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; En galvanizado o metal no ferroso primero resolver adherencia con wash primer antes del anticorrosivo o acabado.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: corrotec-primer-epoxico-10070-13350.pdf, CORROTEC PREMIUM.pdf, DOMESTICO.pdf, PINTULUX 3 EN 1 BRILLANTE.pdf, PINTULUX 3 EN 1 MATE.pdf, PINTURAMA.pdf

### multisurface_320 :: viniltex_en_reja_oxidada

- Consulta: quiero Viniltex para reja oxidada con corrosion superficial
- Problema inferido: metal_oxidado
- Similitud RAG: 0.5923
- Prioridad dominante: normal
- Politicas: arquitectonico_sobre_base_agua, metal_oxidado_mantenimiento
- Politicas criticas: ninguna
- Dominantes: arquitectonico_sobre_base_agua
- Sistema recomendado estructurado: Pintóxido, Corrotec, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: EPOXY ZINC PRIMER 10073P UEA603/20L/AA7, EPOXI ZINC IND 10073 2K PART A GRIS 2.4G, PQ CORROTEC PREMIUM MAT GRIS 507 3.79L, PQ CORROTEC PREMIUM MAT NEGRO 200 3.79L
- Productos prohibidos: Interthane 990, Interseal, Intergard, Pintucoat, Viniltex, Koraza
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Mantener compatibilidad de familia: agua con agua sobre sistemas arquitectonicos existentes.; Separar oxido superficial de corrosion profunda antes de definir transformador o remocion mecanica intensiva.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: CORROTEC EPOXI ZINC 2K 10073.pdf, CORROTEC.pdf, ACRILTEX VINILTEX.pdf, corrotec-primer-epoxico-10070-13350.pdf

### multisurface_320 :: barnex_en_escalera_interior

- Consulta: quiero Barnex para escalera interior de madera con alto trafico
- Problema inferido: madera
- Similitud RAG: 0.633
- Prioridad dominante: normal
- Politicas: madera_interior_alto_trafico
- Politicas criticas: ninguna
- Dominantes: madera_interior_alto_trafico
- Sistema recomendado estructurado: Poliuretano Alto Trafico 1550/1551, Barnex, Wood Stain, Esmalte Doméstico, Pintulux Máxima Protección
- Portafolio relacionado por inventario/RAG: MEG PINTULACA NEGRO MATIZ 7589 AC 3.78L, MEG PINTULACA NEGRO 7518 AC 3.78L, K BARNEX EXTRA INCOLOR 2G GTS BARNIZ SD1, K BARNEX EXTRA INCOLOR 7G GTS BARNIZ SD1
- Productos prohibidos: Barnex, Pintulac, barniz arquitectonico
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Barnex, Wood Stain, Esmalte Doméstico, Pintulux Máxima Protección
- Herramientas: Brocha Goya Profesional, Lijas Abracol 80-100 y 220-320, Removedor Pintuco
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Diagnosticar si es interior/exterior y si quiere transparente o color sólido.; Mezclar A+B y respetar el lijado fino entre manos en el sistema poliuretano interior.
- Preguntas pendientes: Confirmar si es interior o exterior.; Confirmar si quiere acabado transparente o color sólido.; Solicitar área o dimensiones antes de cotizar.
- Archivos fuente: BARNIZ BARNEX 557.pdf, BARNEX EXTRA PROTECCION.pdf, BARNEX EXTRA PROTECCIÓN.pdf, BASE INMUNIZANTE BARNEX.pdf, MADETEC VITRIFLEX PARTE B.pdf

### multisurface_320 :: poliuretano_1550_en_deck

- Consulta: quiero poliuretano 1550 para deck exterior de madera
- Problema inferido: madera
- Similitud RAG: 0.6006
- Prioridad dominante: normal
- Politicas: madera_exterior
- Politicas criticas: ninguna
- Dominantes: madera_exterior
- Sistema recomendado estructurado: Barnex, Wood Stain, Esmalte Doméstico, Pintulux Máxima Protección
- Portafolio relacionado por inventario/RAG: EPOXY ESTRUCTURAS UEA552 /0.5L/AA7, ESM POLIURETANO 11323 UFA468/3.7L/AA7, ESM POLIURETANO 13603 UFA453/3.7L/AA7, ESPUMA DE POLIURETANO AFIX 500 ML
- Productos prohibidos: Poliuretano Alto Trafico 1550/1551
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Barnex, Wood Stain, Esmalte Doméstico, Pintulux Máxima Protección
- Herramientas: Brocha Goya Profesional, Lijas Abracol 80-100 y 220-320, Removedor Pintuco
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Diagnosticar si es interior/exterior y si quiere transparente o color sólido.; En madera exterior usar sistema con proteccion UV y no un poliuretano transparente de piso interior.
- Preguntas pendientes: Confirmar si es interior o exterior.; Confirmar si quiere acabado transparente o color sólido.; Solicitar área o dimensiones antes de cotizar.
- Archivos fuente: EPOXY ESTRUCTURAS UEA550-UEA551-UEA552 [ES].pdf, ESMALTE POLIURETANO MADERA.pdf, ESPUMA DE POLIURETANO.pdf

### multisurface_320 :: koraza_en_terraza_grietas

- Consulta: quiero Koraza para techo de concreto con grietas en terraza
- Problema inferido: none
- Similitud RAG: 0.6544
- Prioridad dominante: normal
- Politicas: techo_concreto_grietas
- Politicas criticas: ninguna
- Dominantes: techo_concreto_grietas
- Sistema recomendado estructurado: Pintuco Fill
- Portafolio relacionado por inventario/RAG: KORAZA ELASTOMERICA NE-017-P SENALROS 5G, PQ KORAZA MAT BLANCO 2650 18.93L, KORAZA ELASTOMERICA 2677 CIPRES CANEC 5G, KORAZA ELASTOMERICA 2651 NOGAL 5 GL
- Productos prohibidos: Koraza, Viniltex, Intervinil, Pinturama
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: En techos de concreto con grietas tratar la impermeabilizacion como sistema de cubierta, no como pintura decorativa.; Definir si requiere refuerzo de tela o tratamiento de fisuras antes del acabado final.
- Preguntas pendientes: ninguna
- Archivos fuente: KORAZA PRO 750 ELASTOMERICA.pdf, KORAZA PROTECCION 3 EN 1.pdf, KORAZA 5.pdf, KORAZA DOBLE VIDA.pdf, KORAZA IMPERMEABLE.pdf

### multisurface_320 :: intervinil_en_eternit

- Consulta: quiero Intervinil para techo de eternit exterior envejecido
- Problema inferido: eternit_fibrocemento
- Similitud RAG: 0.6672
- Prioridad dominante: normal
- Politicas: eternit_fibrocemento_exterior, arquitectonico_sobre_base_agua
- Politicas criticas: ninguna
- Dominantes: eternit_fibrocemento_exterior
- Sistema recomendado estructurado: Sellomax, Koraza, Sellomax antes del acabado si el eternit ya esta pintado o envejecido.
- Portafolio relacionado por inventario/RAG: P7 INTERVINIL PRO 200 MAT BL 2596 18.93L, PQ INTERVINIL MAT BLANCO 2501 18.93L, P7 INTERVINIL PRO 400 MAT BL 2501 18.93L, PQ PINTUCO FILL 7 GRIS 2753 20K
- Productos prohibidos: Intervinil, Pinturama o vinilos interiores como acabado exterior, rasqueteo o preparacion mecanica que genere polvo, Pinturama, vinilos interiores, Interthane 990, Interseal, Intergard, Pintucoat, Intervinil, Pinturama o vinilos interiores como acabado exterior., Lijado en seco, rasqueteo o preparacion mecanica que genere polvo.
- Base / imprimante: Sellomax antes del acabado si el eternit ya esta pintado o envejecido.
- Intermedios: ninguno
- Acabados finales: Koraza
- Herramientas: Hidrolavadora, Cepillo, Escoba de cerdas duras, Brocha, Rodillo
- Herramientas obligatorias: hidrolavadora, cepillo
- Herramientas prohibidas: Lijado en seco, lijas, rasqueta, preparacion mecanica
- Pasos obligatorios: Preparacion humeda con hidrolavadora, jabon, hipoclorito y cepillo; nunca lijar en seco ni rasquetear.; Retirar solo material flojo sin generar polvo.; Preparacion humeda obligatoria; nunca lijar en seco ni rasquetear.; En eternit envejecido o repintado, Sellomax va antes del acabado exterior.; Mantener compatibilidad de familia: agua con agua sobre sistemas arquitectonicos existentes.; Preparación húmeda obligatoria; nunca lijar en seco ni rasquetear.
- Preguntas pendientes: Confirmar si el fibrocemento es exterior y si ya esta pintado o envejecido.; Validar si hay polvo de asbesto o deterioro que obligue a preparacion humeda.; Solicitar m2 reales antes de cotizar.
- Archivos fuente: INTERVINIL.pdf, INTERVINIL PRO 400.pdf, INTERVINIL PRO 200.pdf

### multisurface_320 :: acido_en_ladrillo_vista

- Consulta: quiero acido muriatico para limpiar ladrillo a la vista exterior
- Problema inferido: ladrillo_vista
- Similitud RAG: 0.6766
- Prioridad dominante: normal
- Politicas: ladrillo_a_la_vista
- Politicas criticas: ninguna
- Dominantes: ladrillo_a_la_vista
- Sistema recomendado estructurado: Construcleaner Limpiador Desengrasante, Siliconite 7, Construcleaner Limpiador Desengrasante como limpieza previa.
- Portafolio relacionado por inventario/RAG: BROCHA GOYA POPULAR 2""", BROCHA GOYA POPULAR 3""", CONSTRUCLEANER RINSE LADRILLO ROJ 52.83G, PQ KORAZA MAT LADRILLO 2804 3.79L
- Productos prohibidos: Acido muriatico para limpieza, Koraza si el objetivo es conservar el ladrillo a la vista, Koraza, acido muriatico, Acido muriatico para limpieza., Koraza si el objetivo es conservar el ladrillo a la vista.
- Base / imprimante: Construcleaner Limpiador Desengrasante como limpieza previa.
- Intermedios: ninguno
- Acabados finales: Siliconite 7
- Herramientas: Cepillo, Brocha, Rodillo segun absorcion
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Limpieza tecnica del ladrillo antes de protegerlo.; Limpiar el ladrillo con limpiador adecuado antes de hidrofugar.; Conservar la apariencia del sustrato; proteger sin formar pelicula opaca.
- Preguntas pendientes: Confirmar si el cliente quiere conservar la apariencia natural del ladrillo.; Validar si requiere solo limpieza o limpieza mas hidrofugacion.; Solicitar m2 reales antes de cotizar.
- Archivos fuente: CONSTRUCLEANER LIMPIADOR NO CORROSIVO.pdf, CONSTRUCLEANER RINSE LADRILLO ROJO.pdf, CONSTRUCLEANER LADRILLO ROJO.pdf, CONSTRUCLEANER LIMPIADOR ECOLOGICO LADRILLO.pdf

### multisurface_320 :: pintucoat_en_agua_potable

- Consulta: quiero Pintucoat para tanque de agua potable en inmersion
- Problema inferido: piso_industrial
- Similitud RAG: 0.5235
- Prioridad dominante: critical
- Politicas: inmersion_agua_potable_condicional
- Politicas criticas: inmersion_agua_potable_condicional
- Dominantes: inmersion_agua_potable_condicional
- Sistema recomendado estructurado: Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Pintucoat, Viniltex, Koraza, Pintulux 3 en 1, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: koraza_en_agua_potable

- Consulta: quiero Koraza para tanque de agua potable sumergido
- Problema inferido: none
- Similitud RAG: 0.3451
- Prioridad dominante: critical
- Politicas: inmersion_agua_potable_condicional
- Politicas criticas: inmersion_agua_potable_condicional
- Dominantes: inmersion_agua_potable_condicional
- Sistema recomendado estructurado: ninguno
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Pintucoat, Viniltex, Koraza, Pintulux 3 en 1
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: pintulux_en_incendio

- Consulta: quiero Pintulux 3 en 1 para proteccion pasiva contra incendio
- Problema inferido: none
- Similitud RAG: 0.6656
- Prioridad dominante: critical
- Politicas: proteccion_pasiva_incendio
- Politicas criticas: proteccion_pasiva_incendio
- Dominantes: proteccion_pasiva_incendio
- Sistema recomendado estructurado: Interchar
- Portafolio relacionado por inventario/RAG: PQ PINTULUX 3EN1 BR NEGRO 95 3.79L, PQ PINTULUX 3EN1 BR AMARILLO 18 3.79L, PQ PINTULUX 3EN1 BR BLANCO 11 3.79L, PQ PINTULUX 3EN1 BR NEGRO 95 0.95L
- Productos prohibidos: Koraza, Viniltex, Pintulux 3 en 1
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Definir rating de fuego, perfil estructural y espesor requerido antes de recomendar el sistema intumescente.; No tratar la proteccion pasiva contra incendio como una pintura decorativa comun.
- Preguntas pendientes: ninguna
- Archivos fuente: PINTULUX 3 EN 1 MATE.pdf, PINTULUX TRES EN UNO.pdf, PINTULUX MAXIMA PROTECCION.pdf, pintulux-maxima-proteccion-brillante-1.pdf

### multisurface_320 :: corrotec_en_alta_estetica

- Consulta: quiero Corrotec para acabado industrial de alta estetica y retencion de color
- Problema inferido: metal_oxidado
- Similitud RAG: 0.5388
- Prioridad dominante: normal
- Politicas: acabado_industrial_alta_estetica
- Politicas criticas: ninguna
- Dominantes: acabado_industrial_alta_estetica
- Sistema recomendado estructurado: Interfine, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Corrotec, Pintulux 3 en 1
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Usar Interfine solo como acabado de altas prestaciones sobre sistema industrial compatible, no como primer.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: koraza_en_ambiente_quimico

- Consulta: quiero Koraza para planta industrial con ambiente quimico severo
- Problema inferido: none
- Similitud RAG: 0.3982
- Prioridad dominante: high
- Politicas: ambiente_quimico_industrial
- Politicas criticas: ninguna
- Dominantes: ambiente_quimico_industrial
- Sistema recomendado estructurado: Intergard, Interseal, Interthane 990 + Catalizador
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, KORAZA ELASTOMERICA 2651 NOGAL 5 GL, KORAZA ELASTOMERICA 2798 BALSO CANEC 5GL
- Productos prohibidos: Corrotec, Pintulux 3 en 1, Viniltex, Koraza
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Resolver preparacion de superficie y ambiente de exposición antes de cerrar un sistema industrial anticorrosivo.; No degradar una consulta industrial severa a soluciones arquitectonicas o esmaltes domesticos.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: interseal_en_bano

- Consulta: quiero Interseal para baño interior con hongos
- Problema inferido: none
- Similitud RAG: 0.4451
- Prioridad dominante: normal
- Politicas: bano_cocina_antihongos
- Politicas criticas: ninguna
- Dominantes: bano_cocina_antihongos
- Sistema recomendado estructurado: Viniltex Baños y Cocinas
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Koraza, Pintucoat, Interseal, Intergard, Interthane 990
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: interthane_en_base_agua

- Consulta: quiero Interthane 990 para muro de casa con pintura base agua existente
- Problema inferido: none
- Similitud RAG: 0.5133
- Prioridad dominante: normal
- Politicas: arquitectonico_sobre_base_agua
- Politicas criticas: ninguna
- Dominantes: arquitectonico_sobre_base_agua
- Sistema recomendado estructurado: ninguno
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Interthane 990, Interseal, Intergard, Pintucoat
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Mantener compatibilidad de familia: agua con agua sobre sistemas arquitectonicos existentes.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: primer50_en_piso_medio

- Consulta: quiero Primer 50RS para garaje de concreto interior con trafico medio
- Problema inferido: piso_industrial
- Similitud RAG: 0.5035
- Prioridad dominante: normal
- Politicas: piso_industrial_trafico_medio
- Politicas criticas: ninguna
- Dominantes: piso_industrial_trafico_medio
- Sistema recomendado estructurado: Interseal gris RAL 7038, Pintucoat, Interseal gris RAL 7038 para concreto cuando aplique., Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: EPOXY PRIMER 50RS UEA402/3.7L/AA7, P7 PINTUTRAF BS BLANCO 29205 18.93L, EPOXY PRIMER 70RS UEA501/3.7L/AA7, EPOXY PRIMER 70RS UEA500/20L/AA7
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Primer 50RS, Epoxy Primer 50RS, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Confirmar si el piso es nuevo o ya pintado antes de definir compatibilidad.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: EPOXY PRIMER 50RS UEA400-UEA401-UEA402 [ES].pdf, PINTURA PARA TRAFICO ACRÍLICA TERTRAFICO 29205 BLANCA(TERINSA).pdf, EPOXY PRIMER 70RS  UEA500-UEA501 [ES].pdf, PINTUTRAFICO ACRILICO BASE SOLVENTE 13754 55 56.pdf

### multisurface_320 :: pintucoat_en_piso_pesado

- Consulta: quiero Pintucoat para piso industrial de montacargas y estibadores
- Problema inferido: piso_industrial
- Similitud RAG: 0.5507
- Prioridad dominante: normal
- Politicas: piso_industrial_trafico_pesado
- Politicas criticas: ninguna
- Dominantes: piso_industrial_trafico_pesado
- Sistema recomendado estructurado: Interseal gris RAL 7038, Intergard 2002, Arena de Cuarzo ref 5891610, Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Pintucoat, Primer 50RS, Epoxy Primer 50RS, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Preparacion mecanica y desengrase profundo antes del sistema epoxico.; Confirmar m2, estado del concreto y tipo de trafico antes de cerrar sistema o cantidades.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### multisurface_320 :: viniltex_en_terraza_grietas

- Consulta: quiero Viniltex para techo de concreto con grietas en terraza
- Problema inferido: none
- Similitud RAG: 0.6293
- Prioridad dominante: normal
- Politicas: arquitectonico_sobre_base_agua, techo_concreto_grietas
- Politicas criticas: ninguna
- Dominantes: arquitectonico_sobre_base_agua
- Sistema recomendado estructurado: Pintuco Fill
- Portafolio relacionado por inventario/RAG: PQ VINILTEX ADV MAT BLANCO 1501 18.93L, PQ VINILTEX ACRILTEX SA BLAN 2761 18.93L, PQ VINILTEX ADV MAT BLANCO 1501 3.79L PE, PQ PINTUCO FILL 7 GRIS 2753 20K
- Productos prohibidos: Interthane 990, Interseal, Intergard, Pintucoat, Koraza, Viniltex, Intervinil, Pinturama
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Mantener compatibilidad de familia: agua con agua sobre sistemas arquitectonicos existentes.; En techos de concreto con grietas tratar la impermeabilizacion como sistema de cubierta, no como pintura decorativa.; Definir si requiere refuerzo de tela o tratamiento de fisuras antes del acabado final.
- Preguntas pendientes: ninguna
- Archivos fuente: ACRILTEX VINILTEX.pdf

### multisurface_320 :: koraza_en_ladrillo_vista

- Consulta: quiero Koraza para ladrillo a la vista exterior sin cambiar apariencia
- Problema inferido: ladrillo_vista
- Similitud RAG: 0.6192
- Prioridad dominante: normal
- Politicas: ladrillo_a_la_vista
- Politicas criticas: ninguna
- Dominantes: ladrillo_a_la_vista
- Sistema recomendado estructurado: Construcleaner Limpiador Desengrasante, Siliconite 7, Construcleaner Limpiador Desengrasante como limpieza previa.
- Portafolio relacionado por inventario/RAG: KORAZA ELASTOMERICA 2651 NOGAL 5 GL, KORAZA ELASTOMERICA 2798 BALSO CANEC 5GL, P7 KORAZA ELASTOMERICA GEN ACCENT 18.93L, P7 KORAZA ELASTOMERICA GEN PASTEL 18.93L
- Productos prohibidos: Acido muriatico para limpieza, Koraza si el objetivo es conservar el ladrillo a la vista, Koraza, acido muriatico, Acido muriatico para limpieza., Koraza si el objetivo es conservar el ladrillo a la vista.
- Base / imprimante: Construcleaner Limpiador Desengrasante como limpieza previa.
- Intermedios: ninguno
- Acabados finales: Siliconite 7
- Herramientas: Cepillo, Brocha, Rodillo segun absorcion
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Limpieza tecnica del ladrillo antes de protegerlo.; Limpiar el ladrillo con limpiador adecuado antes de hidrofugar.; Conservar la apariencia del sustrato; proteger sin formar pelicula opaca.
- Preguntas pendientes: Confirmar si el cliente quiere conservar la apariencia natural del ladrillo.; Validar si requiere solo limpieza o limpieza mas hidrofugacion.; Solicitar m2 reales antes de cotizar.
- Archivos fuente: KORAZA 5.pdf, KORAZA IMPERMEABLE.pdf, KORAZA DOBLE VIDA.pdf, KORAZA PRO 750 ELASTOMERICA.pdf, KORAZA PROTECCION 3 EN 1.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf

### multisurface_320 :: pintucoat_en_bano

- Consulta: quiero Pintucoat para baño interior con hongos
- Problema inferido: piso_industrial
- Similitud RAG: 0.6161
- Prioridad dominante: normal
- Politicas: bano_cocina_antihongos
- Politicas criticas: ninguna
- Dominantes: bano_cocina_antihongos
- Sistema recomendado estructurado: Viniltex Baños y Cocinas, Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: PQ KORAZA MAT BLANCO 2650 18.93L, PQ VINILTEX ADV MAT BLANCO 1501 18.93L, PQ PINTUCO FILL 7 GRIS 2753 20K, PQ PINTUCO FILL 7 GRIS 2753 4.2K
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Koraza, Pintucoat, Interseal, Intergard, Interthane 990, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: PINTURA ACRILICA ALTA ASEPSIA.pdf, PINTUCO FILL 7.pdf, PINTURAMA.pdf

### multisurface_320 :: viniltex_en_incendio

- Consulta: quiero Viniltex para estructura con proteccion pasiva contra incendio
- Problema inferido: none
- Similitud RAG: 0.613
- Prioridad dominante: critical
- Politicas: arquitectonico_sobre_base_agua, proteccion_pasiva_incendio
- Politicas criticas: proteccion_pasiva_incendio
- Dominantes: proteccion_pasiva_incendio
- Sistema recomendado estructurado: Interchar
- Portafolio relacionado por inventario/RAG: PQ VINILTEX ADV MAT BLANCO 1501 18.93L, PQ VINILTEX ACRILTEX SA BLAN 2761 18.93L, P7 INTERVINIL PRO 200 MAT BL 2596 18.93L, P7 INTERVINIL PRO 400 MAT BL 2501 18.93L
- Productos prohibidos: Interthane 990, Interseal, Intergard, Pintucoat, Koraza, Viniltex, Pintulux 3 en 1
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Mantener compatibilidad de familia: agua con agua sobre sistemas arquitectonicos existentes.; Definir rating de fuego, perfil estructural y espesor requerido antes de recomendar el sistema intumescente.; No tratar la proteccion pasiva contra incendio como una pintura decorativa comun.
- Preguntas pendientes: ninguna
- Archivos fuente: ACRILTEX VINILTEX.pdf, INTERVINIL PRO 400.pdf

### multisurface_320 :: pintuco_fill_en_espuma

- Consulta: quiero Pintuco Fill para sellar huecos con espuma expansiva
- Problema inferido: none
- Similitud RAG: 0.7329
- Prioridad dominante: normal
- Politicas: espuma_poliuretano_sellado
- Politicas criticas: ninguna
- Dominantes: espuma_poliuretano_sellado
- Sistema recomendado estructurado: Espuma de Poliuretano
- Portafolio relacionado por inventario/RAG: ESPUMA DE POLIURETANO AFIX 500 ML, INTERTHANE 990 PHA130/20L/AA7, PQ PINTUCO FILL 12 GRIS 27505 20K, PQ PINTUCO FILL 12 BASE ACCENT 20K
- Productos prohibidos: Koraza, Viniltex, Pintuco Fill, Interseal
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Usar la espuma como sistema de sellado o relleno sobre superficie limpia, no como pintura o acabado decorativo.
- Preguntas pendientes: ninguna
- Archivos fuente: ESPUMA DE POLIURETANO.pdf, PINTUCO FILL 12.pdf, PINTUCO FILL 7.pdf

## Grupo: preparation

### prep_priority_negation_208 :: metal_oxidado_agua_jabon

- Consulta: voy a lavar el metal oxidado con agua y jabon y luego aplico Pintoxido
- Problema inferido: metal_oxidado
- Similitud RAG: 0.7271
- Prioridad dominante: high
- Politicas: metal_oxidado_mantenimiento, metal_oxidado_preparacion_incorrecta
- Politicas criticas: ninguna
- Dominantes: metal_oxidado_preparacion_incorrecta
- Sistema recomendado estructurado: Pintóxido, Corrotec, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: PQ PINTULUX DESOXID PINTOXIDO 514 3.79L, PQ CORROTEC PREMIUM MAT GRIS 507 3.79L, PQ CORROTEC PREMIUM MAT NEGRO 200 3.79L, PQ PINTULUX 3EN1 BR BLANCO 11 3.79L
- Productos prohibidos: Viniltex, Koraza, Pintucoat
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: grata, lija
- Herramientas prohibidas: agua y jabon
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Separar oxido superficial de corrosion profunda antes de definir transformador o remocion mecanica intensiva.; En metal oxidado no usar agua y jabón como preparación principal; retirar óxido y cascarilla con grata o lija antes del convertidor o anticorrosivo.; Aplicar el sistema solo sobre metal seco y con el óxido flojo removido.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: PINTOXIDO.pdf, CORROTEC.pdf

### prep_priority_negation_208 :: metal_oxidado_lavar_con_agua

- Consulta: quiero lavar la reja oxidada con agua antes del anticorrosivo
- Problema inferido: metal_oxidado
- Similitud RAG: 0.5882
- Prioridad dominante: high
- Politicas: metal_oxidado_mantenimiento, metal_oxidado_preparacion_incorrecta
- Politicas criticas: ninguna
- Dominantes: metal_oxidado_preparacion_incorrecta
- Sistema recomendado estructurado: Pintóxido, Corrotec, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: PQ CORROTEC PREMIUM MAT NEGRO 200 3.79L, PQ CORROTEC ALUMINIO BR ECP100 3.79L, ANTICORROSIVO GRIS PINTUCO 1/16G, PQ CORROTEC PREMIUM MAT GRIS 507 3.79L
- Productos prohibidos: Viniltex, Koraza, Pintucoat
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: grata, lija
- Herramientas prohibidas: agua y jabon
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Separar oxido superficial de corrosion profunda antes de definir transformador o remocion mecanica intensiva.; En metal oxidado no usar agua y jabón como preparación principal; retirar óxido y cascarilla con grata o lija antes del convertidor o anticorrosivo.; Aplicar el sistema solo sobre metal seco y con el óxido flojo removido.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: ANTICORROSIVO VERDE 513.pdf, ANTICORROSIVO AMARILLO  505.pdf, ANTICORROSIVO INDUSTRIAL 210003.pdf, CONSTRUCLEANER RINSE LADRILLO ROJO.pdf

### prep_priority_negation_208 :: metal_oxidado_jabonoso

- Consulta: el aplicador piensa usar agua jabonosa en la reja oxidada y despues Corrotec
- Problema inferido: metal_oxidado
- Similitud RAG: 0.6517
- Prioridad dominante: high
- Politicas: metal_oxidado_mantenimiento, metal_oxidado_preparacion_incorrecta
- Politicas criticas: ninguna
- Dominantes: metal_oxidado_preparacion_incorrecta
- Sistema recomendado estructurado: Pintóxido, Corrotec, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: PQ CORROTEC PREMIUM MAT GRIS 507 3.79L, PQ CORROTEC PREMIUM MAT NEGRO 200 3.79L, PQ PINTULUX WASH PRIMER 509A PT A 1 GL, PQ PINTULUX WASH PRIMER 509B PT B 1 GL
- Productos prohibidos: Viniltex, Koraza, Pintucoat
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: grata, lija
- Herramientas prohibidas: agua y jabon
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Separar oxido superficial de corrosion profunda antes de definir transformador o remocion mecanica intensiva.; En metal oxidado no usar agua y jabón como preparación principal; retirar óxido y cascarilla con grata o lija antes del convertidor o anticorrosivo.; Aplicar el sistema solo sobre metal seco y con el óxido flojo removido.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: CORROTEC PREMIUM.pdf, CORROTEC.pdf, CORROTEC EPOXI ZINC 2K 10073.pdf

### prep_priority_negation_208 :: concreto_fresco_acido

- Consulta: quiero aplicar acido muriatico al piso de concreto recien fundido para curarlo rapido
- Problema inferido: piso_industrial
- Similitud RAG: 0.5619
- Prioridad dominante: high
- Politicas: concreto_sin_curado, concreto_sin_curado_acido_incorrecto
- Politicas criticas: ninguna
- Dominantes: concreto_sin_curado, concreto_sin_curado_acido_incorrecto
- Sistema recomendado estructurado: Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: PINTUTRAFICO ACRILICO BASE SOLV AZUL 1G, P7 PINTUTRAFICO ACRYL 13754-653 18.93l, ESTUCOR BULTO *25 KL LISTO, EPOXY HS 13233 UEA204/3.7L/AA7
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: acido muriatico
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Esperar minimo 28 dias de curado y validar humedad antes de pintar.; No usar ácido muriático para forzar curado ni preparación temprana del concreto recién fundido.; Esperar el curado mínimo, validar humedad y luego definir el tratamiento de superficie correcto.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: PINTUTRÁFICO ACRILICO BASE SOLVENTE.pdf, ESTUCOR LISTO.pdf, PINTUTRAFICO ACRILICO BASE SOLVENTE 13754 55 56.pdf, EPOXY HS 13200  UEA203-13233 UEA204 [ES].pdf, CONSTRUCRIL.pdf, PINTURA EPOXICA PARA CONCRETO.pdf

### prep_priority_negation_208 :: concreto_nuevo_acido_antes_pintar

- Consulta: al concreto nuevo sin curar le voy a echar acido muriatico antes del sistema
- Problema inferido: piso_industrial
- Similitud RAG: 0.5091
- Prioridad dominante: high
- Politicas: concreto_sin_curado, concreto_sin_curado_acido_incorrecto
- Politicas criticas: ninguna
- Dominantes: concreto_sin_curado, concreto_sin_curado_acido_incorrecto
- Sistema recomendado estructurado: Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: BROCHA GOYA POPULAR 2""", BROCHA GOYA POPULAR 3""", ACRILICA BASE AGUA UDA600/3.7L/AA7, ESTUCOR BULTO *25 KL LISTO
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: acido muriatico
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Esperar minimo 28 dias de curado y validar humedad antes de pintar.; No usar ácido muriático para forzar curado ni preparación temprana del concreto recién fundido.; Esperar el curado mínimo, validar humedad y luego definir el tratamiento de superficie correcto.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: CONSTRUCLEANER LIMPIADOR NO CORROSIVO.pdf, ACRILICA BASE AGUA UDA600 [ES].pdf, ESTUCOR LISTO.pdf, CONSTRUCLEANER RINSE LADRILLO ROJO.pdf

### prep_priority_negation_208 :: obra_gris_acido

- Consulta: en obra gris recien vaciada quiero usar acido muriatico para acelerar la preparacion
- Problema inferido: piso_industrial
- Similitud RAG: 0.5698
- Prioridad dominante: high
- Politicas: concreto_sin_curado, concreto_sin_curado_acido_incorrecto
- Politicas criticas: ninguna
- Dominantes: concreto_sin_curado, concreto_sin_curado_acido_incorrecto
- Sistema recomendado estructurado: Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: EPOXY HS 13233 UEA204/3.7L/AA7, ANTICORROSIVO FENOLICO ATOXICO AMARI 1G, BROCHA GOYA POPULAR 2""", CONSTRUCLEANER RINSE LADRILLO ROJ 52.83G
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: acido muriatico
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Esperar minimo 28 dias de curado y validar humedad antes de pintar.; No usar ácido muriático para forzar curado ni preparación temprana del concreto recién fundido.; Esperar el curado mínimo, validar humedad y luego definir el tratamiento de superficie correcto.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: EPOXY HS 13200  UEA203-13233 UEA204 [ES].pdf, CONSTRUCLEANER LIMPIADOR NO CORROSIVO.pdf, CONSTRUCLEANER RINSE LADRILLO ROJO.pdf, ACRILICA BASE AGUA UDA600 [ES].pdf, CONSTRUCRIL.pdf

## Grupo: priority

### prep_priority_negation_208 :: agua_potable_y_fachada

- Consulta: necesito pintar un tanque de agua potable y la fachada de la casa
- Problema inferido: fachada_exterior
- Similitud RAG: 0.4313
- Prioridad dominante: critical
- Politicas: fachada_alta_exposicion, inmersion_agua_potable_condicional
- Politicas criticas: inmersion_agua_potable_condicional
- Dominantes: inmersion_agua_potable_condicional
- Sistema recomendado estructurado: Koraza, Viniltex
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Intervinil o Pinturama como acabado en fachadas de alta exposicion, Aquablock como acabado exterior, Intervinil, Pinturama, vinilos interiores, Aquablock, Pintucoat, Viniltex, Koraza, Pintulux 3 en 1, Intervinil o Pinturama como acabado en fachadas de alta exposicion., Aquablock como acabado exterior.
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Koraza, Viniltex
- Herramientas: Lija Abracol, Brocha Goya Profesional, Rodillo
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Remover pintura suelta o base soplada antes de repintar.; Retirar pintura suelta o base soplada antes del acabado exterior.; Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.
- Preguntas pendientes: Confirmar si es exterior real y nivel de deterioro.; Solicitar m² reales antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### prep_priority_negation_208 :: agua_potable_y_bano

- Consulta: tengo un tanque de agua potable y además un baño interior con hongos
- Problema inferido: none
- Similitud RAG: 0.3374
- Prioridad dominante: critical
- Politicas: bano_cocina_antihongos, inmersion_agua_potable_condicional
- Politicas criticas: inmersion_agua_potable_condicional
- Dominantes: inmersion_agua_potable_condicional
- Sistema recomendado estructurado: Viniltex Baños y Cocinas
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Koraza, Pintucoat, Interseal, Intergard, Interthane 990, Viniltex, Pintulux 3 en 1
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.; Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### prep_priority_negation_208 :: incendio_y_esmalte_decorativo

- Consulta: hay una estructura con proteccion pasiva contra incendio y aparte un metal decorativo con esmalte brillante
- Problema inferido: metal_oxidado
- Similitud RAG: 0.5728
- Prioridad dominante: critical
- Politicas: esmalte_decorativo_mantenimiento, proteccion_pasiva_incendio
- Politicas criticas: proteccion_pasiva_incendio
- Dominantes: proteccion_pasiva_incendio
- Sistema recomendado estructurado: Esmaltes Top Quality, Interchar, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: ESMALTE MAQUINARIA 11271 UFA102/3.7L/AA7, TOP QUALITY PLUS BLANCO SEMI BTE 1G, PQ PINTULUX 3EN1 BR NEGRO 95 3.79L, K BARNEX EXTRA INCOLOR 7G GTS BARNIZ SD1
- Productos prohibidos: Interseal, Intergard, Interthane 990, Koraza, Viniltex, Pintulux 3 en 1
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Tratar el caso como acabado decorativo o mantenimiento liviano, no como sistema industrial 2K.; Definir rating de fuego, perfil estructural y espesor requerido antes de recomendar el sistema intumescente.; No tratar la proteccion pasiva contra incendio como una pintura decorativa comun.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: ESMALTE MAQUINARIA 11271 UFA102 [ES].pdf, ESMALTES TOP QUALITY.pdf, BARNEX EXTRA PROTECCION.pdf, PINTULUX 3 EN 1 BRILLANTE.pdf, pintulux-maxima-proteccion-brillante-1.pdf

### prep_priority_negation_208 :: incendio_y_fachada

- Consulta: estructura metalica con proteccion contra incendio y también fachada exterior de la casa
- Problema inferido: fachada_exterior
- Similitud RAG: 0.5792
- Prioridad dominante: critical
- Politicas: fachada_alta_exposicion, proteccion_pasiva_incendio
- Politicas criticas: proteccion_pasiva_incendio
- Dominantes: proteccion_pasiva_incendio
- Sistema recomendado estructurado: Koraza, Interchar, Viniltex
- Portafolio relacionado por inventario/RAG: INTERCHAR 2060 HFA060/20L/EU, INTERNATIONAL GVA134/1GL/UH, PQ PINTULUX 3EN1 BR BLANCO 11 3.79L, PQ PINTULUX 3EN1 BR GRIS PLATA 84 3.79L
- Productos prohibidos: Intervinil o Pinturama como acabado en fachadas de alta exposicion, Aquablock como acabado exterior, Intervinil, Pinturama, vinilos interiores, Aquablock, Koraza, Viniltex, Pintulux 3 en 1, Intervinil o Pinturama como acabado en fachadas de alta exposicion., Aquablock como acabado exterior.
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Koraza, Viniltex
- Herramientas: Lija Abracol, Brocha Goya Profesional, Rodillo
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Remover pintura suelta o base soplada antes de repintar.; Retirar pintura suelta o base soplada antes del acabado exterior.; Definir rating de fuego, perfil estructural y espesor requerido antes de recomendar el sistema intumescente.; No tratar la proteccion pasiva contra incendio como una pintura decorativa comun.
- Preguntas pendientes: Confirmar si es exterior real y nivel de deterioro.; Solicitar m² reales antes de cotizar.
- Archivos fuente: PPF calculo y especificación - Intumescente.pdf, INTERCHAR 2060 [ES] (1).pdf, pintulux-maxima-proteccion-brillante-1.pdf, DOMESTICO.pdf

### prep_priority_negation_208 :: agua_potable_y_cancha

- Consulta: tanque de agua potable por un lado y cancha deportiva exterior por otro
- Problema inferido: fachada_exterior
- Similitud RAG: 0.3208
- Prioridad dominante: critical
- Politicas: fachada_alta_exposicion, cancha_sendero_peatonal, inmersion_agua_potable_condicional
- Politicas criticas: inmersion_agua_potable_condicional
- Dominantes: inmersion_agua_potable_condicional
- Sistema recomendado estructurado: Koraza, Pintura Canchas, Viniltex
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Intervinil o Pinturama como acabado en fachadas de alta exposicion, Aquablock como acabado exterior, Intervinil, Pinturama, vinilos interiores, Aquablock, Pintucoat, Intergard 2002, Intergard 740, Viniltex, Koraza, Pintulux 3 en 1, Intervinil o Pinturama como acabado en fachadas de alta exposicion., Aquablock como acabado exterior.
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Koraza, Viniltex
- Herramientas: Lija Abracol, Brocha Goya Profesional, Rodillo
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Remover pintura suelta o base soplada antes de repintar.; Retirar pintura suelta o base soplada antes del acabado exterior.; No mezclar la ruta deportiva con pisos industriales de montacargas o bodegas.; Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.
- Preguntas pendientes: Confirmar si es exterior real y nivel de deterioro.; Solicitar m² reales antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### prep_priority_negation_208 :: agua_potable_e_incendio

- Consulta: tengo un tanque de agua potable y una estructura con proteccion pasiva contra incendio
- Problema inferido: none
- Similitud RAG: 0.3951
- Prioridad dominante: critical
- Politicas: inmersion_agua_potable_condicional, proteccion_pasiva_incendio
- Politicas criticas: inmersion_agua_potable_condicional, proteccion_pasiva_incendio
- Dominantes: inmersion_agua_potable_condicional, proteccion_pasiva_incendio
- Sistema recomendado estructurado: Interchar
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Pintucoat, Viniltex, Koraza, Pintulux 3 en 1
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.; Definir rating de fuego, perfil estructural y espesor requerido antes de recomendar el sistema intumescente.; No tratar la proteccion pasiva contra incendio como una pintura decorativa comun.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

## Grupo: negation

### prep_priority_negation_208 :: humedad_no_quiere_koraza

- Consulta: tengo humedad en un muro interior y no quiero usar Koraza porque ya vi que se sopla
- Problema inferido: humedad_interior_general
- Similitud RAG: 0.6363
- Prioridad dominante: high
- Politicas: humedad_interior_negativa
- Politicas criticas: ninguna
- Dominantes: humedad_interior_negativa
- Sistema recomendado estructurado: Aquablock, Aquablock / Aquablock Ultra según presión negativa y severidad., Estuco Acrílico si se requiere nivelación después del bloqueador de humedad., Viniltex Advanced, Intervinil, Pinturama
- Portafolio relacionado por inventario/RAG: P7 KORAZA ELASTOMERICA GEN ACCENT 18.93L, P7 KORAZA ELASTOMERICA GEN DEEP 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L, PQ KORAZA MAT ACCENT BASE 127477 3.79L
- Productos prohibidos: Koraza como sellador de humedad interior, Koraza, Pintuco Fill, Koraza como sellador de humedad interior.
- Base / imprimante: Aquablock / Aquablock Ultra según presión negativa y severidad.
- Intermedios: Estuco Acrílico si se requiere nivelación después del bloqueador de humedad.
- Acabados finales: Viniltex Advanced, Intervinil, Pinturama
- Herramientas: Brocha, Rodillo, Lija / raspado para preparación
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Diagnosticar causa de humedad antes de pintar.; Remover base dañada y salitre donde aplique.; Retirar acabado soplado, salitre y base floja hasta sustrato sano antes del bloqueador.; Bloquear la humedad primero y solo despues reconstruir el acabado decorativo.
- Preguntas pendientes: Confirmar causa: base del muro, arriba, lateral o temporada.; Validar estado de la base/revoque.; Solicitar m² reales antes de cotizar.
- Archivos fuente: KORAZA IMPERMEABLE.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf, KORAZA 5.pdf, FICHA TECNICA KORAZA® PROTECCIÓN SOL & LLUVIA PINTURA IMPERMEABILIZANTE.pdf, KORAZA PROTECCION 3 EN 1.pdf

### prep_priority_negation_208 :: bano_no_quiere_koraza

- Consulta: es un baño interior con hongos y no quiero usar Koraza porque no me convence
- Problema inferido: none
- Similitud RAG: 0.5836
- Prioridad dominante: normal
- Politicas: bano_cocina_antihongos
- Politicas criticas: ninguna
- Dominantes: bano_cocina_antihongos
- Sistema recomendado estructurado: Viniltex Baños y Cocinas
- Portafolio relacionado por inventario/RAG: P7 KORAZA ELASTOMERICA GEN ACCENT 18.93L, P7 KORAZA ELASTOMERICA GEN DEEP 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L, PQ KORAZA MAT ACCENT BASE 127477 3.79L
- Productos prohibidos: Koraza, Pintucoat, Interseal, Intergard, Interthane 990
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.
- Preguntas pendientes: ninguna
- Archivos fuente: KORAZA IMPERMEABLE.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf, KORAZA 5.pdf, FICHA TECNICA KORAZA® PROTECCIÓN SOL & LLUVIA PINTURA IMPERMEABILIZANTE.pdf, KORAZA PROTECCION 3 EN 1.pdf

### prep_priority_negation_208 :: interior_descarta_koraza

- Consulta: muro interior de sala, no quiero usar Koraza, que vinilo recomiendan
- Problema inferido: none
- Similitud RAG: 0.5691
- Prioridad dominante: normal
- Politicas: arquitectonico_sobre_base_agua
- Politicas criticas: ninguna
- Dominantes: arquitectonico_sobre_base_agua
- Sistema recomendado estructurado: ninguno
- Portafolio relacionado por inventario/RAG: PQ KORAZA MAT BLANCO 2650 18.93L, PQ KORAZA MAT DEEP BASE 127476 3.79L, PQ VINILTEX ADV MAT BLANCO 1501 18.93L, PQ VINILTEX ACRILTEX SA BLAN 2761 18.93L
- Productos prohibidos: Interthane 990, Interseal, Intergard, Pintucoat
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Mantener compatibilidad de familia: agua con agua sobre sistemas arquitectonicos existentes.
- Preguntas pendientes: ninguna
- Archivos fuente: KORAZA DOBLE VIDA.pdf, ACRILTEX VINILTEX.pdf, INTERVINIL.pdf, KORAZA PROTECCION 3 EN 1.pdf, KORAZA IMPERMEABLE.pdf

### prep_priority_negation_208 :: metal_no_lavar_con_agua

- Consulta: la reja oxidada no la voy a lavar con agua y jabon, la preparare con grata y lija
- Problema inferido: metal_oxidado
- Similitud RAG: 0.3903
- Prioridad dominante: normal
- Politicas: metal_oxidado_mantenimiento
- Politicas criticas: ninguna
- Dominantes: metal_oxidado_mantenimiento
- Sistema recomendado estructurado: Pintóxido, Corrotec, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: LIJA SECA PREMIER RED 9X11 GRANO #150, LIJA SECA PREMIER RED 9X11 GRANO #320, EPOXY PRIMER 13350 UEA352/3.7L/AA7, CORROTE P. EPOX 10070 BLAN 1G Y 13350 1G
- Productos prohibidos: Viniltex, Koraza, Pintucoat
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Separar oxido superficial de corrosion profunda antes de definir transformador o remocion mecanica intensiva.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: Ficha tecnica Lija Premier Red - hojas.pdf, INTERTHERM 3350.pdf, INTERLINE 859.pdf, Ficha técnica Discos Flap Classic.pdf

### prep_priority_negation_208 :: concreto_no_usar_acido

- Consulta: el piso de concreto recien fundido no quiero tratarlo con acido muriatico, prefiero esperar el curado
- Problema inferido: piso_industrial
- Similitud RAG: 0.5828
- Prioridad dominante: high
- Politicas: concreto_sin_curado
- Politicas criticas: ninguna
- Dominantes: concreto_sin_curado
- Sistema recomendado estructurado: Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: PINTUTRAFICO ACRILICO BASE SOLV AZUL 1G, P7 PINTUTRAFICO ACRYL 13754-653 18.93l, EPOXY HS 13233 UEA204/3.7L/AA7, ACRILICA BASE AGUA UDA600/3.7L/AA7
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Esperar minimo 28 dias de curado y validar humedad antes de pintar.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: PINTUTRÁFICO ACRILICO BASE SOLVENTE.pdf, EPOXY HS 13200  UEA203-13233 UEA204 [ES].pdf, ACRILICA BASE AGUA UDA600 [ES].pdf, ESTUCOR LISTO.pdf, PINTUTRAFICO ACRILICO BASE SOLVENTE 13754 55 56.pdf, INTERGARD 2002.pdf

### prep_priority_negation_208 :: humedad_descarta_koraza_y_pide_opcion

- Consulta: muro interior con humedad y salitre, no usaré Koraza, busco una ruta correcta
- Problema inferido: humedad_interior_general
- Similitud RAG: 0.6152
- Prioridad dominante: high
- Politicas: humedad_interior_negativa
- Politicas criticas: ninguna
- Dominantes: humedad_interior_negativa
- Sistema recomendado estructurado: Aquablock, Aquablock / Aquablock Ultra según presión negativa y severidad., Estuco Acrílico si se requiere nivelación después del bloqueador de humedad., Viniltex Advanced, Intervinil, Pinturama
- Portafolio relacionado por inventario/RAG: P7 KORAZA ELASTOMERICA GEN ACCENT 18.93L, P7 KORAZA ELASTOMERICA GEN PASTEL 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L, PQ KORAZA MAT ACCENT BASE 127477 3.79L
- Productos prohibidos: Koraza como sellador de humedad interior, Koraza, Pintuco Fill, Koraza como sellador de humedad interior.
- Base / imprimante: Aquablock / Aquablock Ultra según presión negativa y severidad.
- Intermedios: Estuco Acrílico si se requiere nivelación después del bloqueador de humedad.
- Acabados finales: Viniltex Advanced, Intervinil, Pinturama
- Herramientas: Brocha, Rodillo, Lija / raspado para preparación
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Diagnosticar causa de humedad antes de pintar.; Remover base dañada y salitre donde aplique.; Retirar acabado soplado, salitre y base floja hasta sustrato sano antes del bloqueador.; Bloquear la humedad primero y solo despues reconstruir el acabado decorativo.
- Preguntas pendientes: Confirmar causa: base del muro, arriba, lateral o temporada.; Validar estado de la base/revoque.; Solicitar m² reales antes de cotizar.
- Archivos fuente: KORAZA IMPERMEABLE.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf, KORAZA 5.pdf, FICHA TECNICA KORAZA® PROTECCIÓN SOL & LLUVIA PINTURA IMPERMEABILIZANTE.pdf, KORAZA PRO 750 ELASTOMERICA.pdf, KORAZA DOBLE VIDA.pdf

## Grupo: double_contradiction

### prep_priority_negation_208 :: pintucoat_y_viniltex

- Consulta: quiero Pintucoat para la cancha y Viniltex para la reja oxidada
- Problema inferido: piso_industrial
- Similitud RAG: 0.6611
- Prioridad dominante: normal
- Politicas: arquitectonico_sobre_base_agua, cancha_sendero_peatonal, metal_oxidado_mantenimiento
- Politicas criticas: ninguna
- Dominantes: arquitectonico_sobre_base_agua
- Sistema recomendado estructurado: Pintura Canchas, Pintóxido, Corrotec, Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: PQ VINILTEX ADV MAT BLANCO 1501 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L, MEG PRIMER ANTIC VERDE OLIV 513 AC 3.78L, MEG PRIMER ANTIC NEGRO 513N AC 3.78L
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Interthane 990, Interseal, Intergard, Pintucoat, Intergard 2002, Intergard 740, Viniltex, Koraza, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Mantener compatibilidad de familia: agua con agua sobre sistemas arquitectonicos existentes.; No mezclar la ruta deportiva con pisos industriales de montacargas o bodegas.; Separar oxido superficial de corrosion profunda antes de definir transformador o remocion mecanica intensiva.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: PINTURA PARA CANCHAS.pdf

### prep_priority_negation_208 :: koraza_y_pintucoat

- Consulta: quiero Koraza para baño interior con hongos y Pintucoat para la cancha
- Problema inferido: piso_industrial
- Similitud RAG: 0.666
- Prioridad dominante: normal
- Politicas: bano_cocina_antihongos, interior_koraza_redirect, cancha_sendero_peatonal
- Politicas criticas: ninguna
- Dominantes: bano_cocina_antihongos
- Sistema recomendado estructurado: Viniltex Baños y Cocinas, Viniltex Advanced, Pintura Canchas, Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: P7 KORAZA ELASTOMERICA GEN PASTEL 18.93L, P7 KORAZA ELASTOMERICA GEN TINT 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L, PQ KORAZA MAT ACCENT BASE 127477 3.79L
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Koraza, Pintucoat, Interseal, Intergard, Interthane 990, Intergard 2002, Intergard 740, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.; Si el cliente pide Koraza para interior cerrado, reconducir a un vinilo premium compatible con ese uso.; No mezclar la ruta deportiva con pisos industriales de montacargas o bodegas.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: KORAZA IMPERMEABLE.pdf, FICHA TECNICA KORAZA® PROTECCIÓN SOL & LLUVIA PINTURA IMPERMEABILIZANTE.pdf, KORAZA PROTECCION 3 EN 1.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf

### prep_priority_negation_208 :: intervinil_y_koraza_ladrillo

- Consulta: quiero Intervinil para techo de eternit exterior y Koraza para ladrillo a la vista
- Problema inferido: eternit_fibrocemento
- Similitud RAG: 0.5837
- Prioridad dominante: normal
- Politicas: eternit_fibrocemento_exterior, ladrillo_a_la_vista, arquitectonico_sobre_base_agua
- Politicas criticas: ninguna
- Dominantes: eternit_fibrocemento_exterior
- Sistema recomendado estructurado: Sellomax, Koraza, Construcleaner Limpiador Desengrasante, Siliconite 7, Sellomax antes del acabado si el eternit ya esta pintado o envejecido.
- Portafolio relacionado por inventario/RAG: P7 INTERVINIL PRO 200 MAT BL 2596 18.93L, PQ INTERVINIL MAT BLANCO 2501 18.93L, P7 KORAZA ELASTOMERICA GEN ACCENT 18.93L, P7 KORAZA ELASTOMERICA GEN DEEP 18.93L
- Productos prohibidos: Intervinil, Pinturama o vinilos interiores como acabado exterior, rasqueteo o preparacion mecanica que genere polvo, Pinturama, vinilos interiores, Koraza, acido muriatico, Interthane 990, Interseal, Intergard, Pintucoat, Intervinil, Pinturama o vinilos interiores como acabado exterior., Lijado en seco, rasqueteo o preparacion mecanica que genere polvo.
- Base / imprimante: Sellomax antes del acabado si el eternit ya esta pintado o envejecido.
- Intermedios: ninguno
- Acabados finales: Koraza
- Herramientas: Hidrolavadora, Cepillo, Escoba de cerdas duras, Brocha, Rodillo
- Herramientas obligatorias: hidrolavadora, cepillo
- Herramientas prohibidas: Lijado en seco, lijas, rasqueta, preparacion mecanica
- Pasos obligatorios: Preparacion humeda con hidrolavadora, jabon, hipoclorito y cepillo; nunca lijar en seco ni rasquetear.; Retirar solo material flojo sin generar polvo.; Preparacion humeda obligatoria; nunca lijar en seco ni rasquetear.; En eternit envejecido o repintado, Sellomax va antes del acabado exterior.; Limpiar el ladrillo con limpiador adecuado antes de hidrofugar.; Conservar la apariencia del sustrato; proteger sin formar pelicula opaca.; Mantener compatibilidad de familia: agua con agua sobre sistemas arquitectonicos existentes.; Preparación húmeda obligatoria; nunca lijar en seco ni rasquetear.
- Preguntas pendientes: Confirmar si el fibrocemento es exterior y si ya esta pintado o envejecido.; Validar si hay polvo de asbesto o deterioro que obligue a preparacion humeda.; Solicitar m2 reales antes de cotizar.
- Archivos fuente: INTERVINIL.pdf, KORAZA IMPERMEABLE.pdf, KORAZA 5.pdf, KORAZA PROTECCION 3 EN 1.pdf, KORAZA SOL Y LLUVIA IMPERMEABILIZANTE.pdf

### prep_priority_negation_208 :: barnex_y_poliuretano_exterior_interior

- Consulta: quiero Barnex para escalera interior de madera y poliuretano 1550 para deck exterior
- Problema inferido: madera
- Similitud RAG: 0.6714
- Prioridad dominante: normal
- Politicas: madera_exterior, madera_interior_alto_trafico
- Politicas criticas: ninguna
- Dominantes: madera_exterior
- Sistema recomendado estructurado: Barnex, Wood Stain, Poliuretano Alto Trafico 1550/1551, Esmalte Doméstico, Pintulux Máxima Protección
- Portafolio relacionado por inventario/RAG: MEG PINTULACA NEGRO MATIZ 7589 AC 3.78L, MEG PINTULACA NEGRO 7518 AC 3.78L, K BARNEX EXTRA INCOLOR 7G GTS BARNIZ SD1, K BARNEX EXTRA INCOLOR 2G GTS BARNIZ SD1
- Productos prohibidos: Poliuretano Alto Trafico 1550/1551, Barnex, Pintulac, barniz arquitectonico
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: Barnex, Wood Stain, Esmalte Doméstico, Pintulux Máxima Protección
- Herramientas: Brocha Goya Profesional, Lijas Abracol 80-100 y 220-320, Removedor Pintuco
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Diagnosticar si es interior/exterior y si quiere transparente o color sólido.; En madera exterior usar sistema con proteccion UV y no un poliuretano transparente de piso interior.; Mezclar A+B y respetar el lijado fino entre manos en el sistema poliuretano interior.
- Preguntas pendientes: Confirmar si es interior o exterior.; Confirmar si quiere acabado transparente o color sólido.; Solicitar área o dimensiones antes de cotizar.
- Archivos fuente: BARNIZ BARNEX 557.pdf, BARNEX EXTRA PROTECCIÓN.pdf, BARNEX EXTRA PROTECCION.pdf, BASE INMUNIZANTE BARNEX.pdf

### prep_priority_negation_208 :: pintucoat_y_pintulux_criticos

- Consulta: quiero Pintucoat para tanque de agua potable y Pintulux 3 en 1 para proteccion contra incendio
- Problema inferido: piso_industrial
- Similitud RAG: 0.5621
- Prioridad dominante: critical
- Politicas: inmersion_agua_potable_condicional, proteccion_pasiva_incendio
- Politicas criticas: inmersion_agua_potable_condicional, proteccion_pasiva_incendio
- Dominantes: inmersion_agua_potable_condicional, proteccion_pasiva_incendio
- Sistema recomendado estructurado: Interchar, Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Pintucoat, Viniltex, Koraza, Pintulux 3 en 1, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; Validar ficha tecnica, certificacion aplicable y preparacion Sa 2.5 o SSPC-SP10 antes de recomendar un sistema de inmersion o agua potable.; Si se trata de agua potable, confirmar la condicion NSF/ANSI 61 y el volumen del tanque antes de cerrar el sistema.; Definir rating de fuego, perfil estructural y espesor requerido antes de recomendar el sistema intumescente.; No tratar la proteccion pasiva contra incendio como una pintura decorativa comun.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### prep_priority_negation_208 :: corrotec_y_viniltex

- Consulta: quiero Corrotec para acabado industrial de alta estetica y Viniltex para la reja oxidada
- Problema inferido: metal_oxidado
- Similitud RAG: 0.4978
- Prioridad dominante: normal
- Politicas: arquitectonico_sobre_base_agua, metal_oxidado_mantenimiento, acabado_industrial_alta_estetica
- Politicas criticas: ninguna
- Dominantes: arquitectonico_sobre_base_agua
- Sistema recomendado estructurado: Pintóxido, Corrotec, Interfine, Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo., Pintulux 3 en 1
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Interthane 990, Interseal, Intergard, Pintucoat, Viniltex, Koraza, Corrotec, Pintulux 3 en 1
- Base / imprimante: Pintóxido si hay óxido profundo., Corrotec o Corrotec Premium como anticorrosivo.
- Intermedios: ninguno
- Acabados finales: Pintulux 3 en 1
- Herramientas: Disco flap, Grata, Brocha Goya Profesional, Lija Abracol
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Preparación mecánica con lija, disco flap o grata según el grado de óxido.; Mantener compatibilidad de familia: agua con agua sobre sistemas arquitectonicos existentes.; Separar oxido superficial de corrosion profunda antes de definir transformador o remocion mecanica intensiva.; Usar Interfine solo como acabado de altas prestaciones sobre sistema industrial compatible, no como primer.
- Preguntas pendientes: Confirmar grado de oxidación.; Confirmar si es interior o exterior.; Solicitar m² o dimensiones antes de cotizar.
- Archivos fuente: INTERNATIONAL 21204.pdf

### prep_priority_negation_208 :: interseal_y_koraza

- Consulta: quiero Interseal para baño interior con hongos y Koraza para planta con ambiente quimico severo
- Problema inferido: none
- Similitud RAG: 0.4245
- Prioridad dominante: high
- Politicas: bano_cocina_antihongos, interior_koraza_redirect, ambiente_quimico_industrial
- Politicas criticas: ninguna
- Dominantes: ambiente_quimico_industrial
- Sistema recomendado estructurado: Viniltex Baños y Cocinas, Viniltex Advanced, Intergard, Interseal, Interthane 990 + Catalizador
- Portafolio relacionado por inventario/RAG: AJUSTADOR XILOL 21204 GTA007/20L/AA7, AJUSTADOR MEDIO TRAFICO BOTELLA 204, P7 PINTUCOAT 517 COMP A 3.44L, P7 PINTUCOAT 13227 COMP B 0.37L
- Productos prohibidos: Koraza, Pintucoat, Interseal, Intergard, Interthane 990, Corrotec, Pintulux 3 en 1, Viniltex
- Base / imprimante: ninguno
- Intermedios: ninguno
- Acabados finales: ninguno
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Separar condensacion o hongos superficiales de una humedad estructural real antes de definir el sistema.; Si el cliente pide Koraza para interior cerrado, reconducir a un vinilo premium compatible con ese uso.; Resolver preparacion de superficie y ambiente de exposición antes de cerrar un sistema industrial anticorrosivo.; No degradar una consulta industrial severa a soluciones arquitectonicas o esmaltes domesticos.
- Preguntas pendientes: ninguna
- Archivos fuente: INTERNATIONAL 21204.pdf

### prep_priority_negation_208 :: pintuco_fill_y_pintucoat

- Consulta: quiero Pintuco Fill para sellar huecos con espuma expansiva y Pintucoat para la cancha deportiva
- Problema inferido: piso_industrial
- Similitud RAG: 0.6862
- Prioridad dominante: normal
- Politicas: cancha_sendero_peatonal, espuma_poliuretano_sellado
- Politicas criticas: ninguna
- Dominantes: cancha_sendero_peatonal
- Sistema recomendado estructurado: Pintura Canchas, Espuma de Poliuretano, Interseal gris RAL 7038 para concreto cuando aplique., Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Portafolio relacionado por inventario/RAG: GANCHO TEJA MADERA ZINCADO T1304-0004, PQ VINILTEX ADV MAT BLANCO 1501 18.93L, PQ KORAZA MAT BLANCO 2650 18.93L, PQ PINTUCO FILL 7 GRIS 2753 20K
- Productos prohibidos: No cotizar sin m² ni sin protocolo diagnóstico del piso, Pintucoat, Intergard 2002, Intergard 740, Koraza, Viniltex, Pintuco Fill, Interseal, No cotizar sin m² ni sin protocolo diagnóstico del piso.
- Base / imprimante: Interseal gris RAL 7038 para concreto cuando aplique.
- Intermedios: ninguno
- Acabados finales: Pintucoat, Intergard 740, Intergard 2002 + cuarzo
- Herramientas: ninguna
- Herramientas obligatorias: ninguna
- Herramientas prohibidas: ninguna
- Pasos obligatorios: Confirmar estado del piso y preparación mecánica adecuada.; No mezclar la ruta deportiva con pisos industriales de montacargas o bodegas.; Usar la espuma como sistema de sellado o relleno sobre superficie limpia, no como pintura o acabado decorativo.
- Preguntas pendientes: Confirmar si es concreto nuevo o viejo/ya pintado.; Confirmar curado de 28 días si es nuevo.; Confirmar tipo de tráfico y si es interior/exterior.; Solicitar m² reales antes de cotizar.
- Archivos fuente: ESTABILIDAD DE PRODUCTOS2.pdf, PINTURA PARA CANCHAS.pdf, CANCHAS.pdf, ESPUMA DE POLIURETANO.pdf

