# Auditoria RAG desde baterias de politicas

- Generado: 2026-04-11 18:45:35
- Escenarios auditados: 5
- Fuente: RAG local real + diagnóstico/guía/políticas filtradas para lectura humana
- Objetivo: ver portafolio sugerido/prohibido y señales de sistema completo sin leer logs interminables

## Vista global

### Productos recomendados mas visibles

- Aquablock: 2
- Viniltex Advanced: 2
- Intervinil: 2
- Pinturama: 2
- Koraza: 2
- ESTUCO ACRILICO PINTUCO /KILO: 2
- ESTUCO ACRILICO PINTUCO / CUARTO: 2
- Aquablock Ultra - 2 manos con brocha para cargar producto.: 1
- Estuco Acrílico después del Aquablock para nivelar. NUNCA antes.: 1
- ESTUCOR BULTO *25 KLS MOLDURA: 1
- ESTUCOR BULTO *25 KL LISTO: 1
- PQ AQUABLOCK ULTRA MAT BLANC 27070 3.79L: 1
- PQ AQUABLOCK ULTRA MAT BLANC 27070 0.95L: 1
- Viniltex Baños y Cocinas: 1
- Aquablock / Aquablock Ultra según presión negativa y severidad.: 1
- Estuco Acrílico si se requiere nivelación después del bloqueador de humedad.: 1
- ALTAS TEMPERATURAS 902 UEA800/3.7L/AA7: 1
- SILICONA ACETICA ALTA TEMP GRIS 50GR BLI: 1
- PQ PINTUCO FILL 12 GRIS 27505 20K: 1
- PQ PINTUCO FILL 12 BASE ACCENT 20K: 1
- Viniltex: 1
- PQ KORAZA MAT BLANCO 2650 18.93L: 1
- PQ KORAZA MAT ACCENT BASE 127477 3.79L: 1
- Sellomax: 1
- Sellomax antes del acabado si el eternit ya esta pintado o envejecido.: 1

### Productos prohibidos mas visibles

- Koraza: 3
- Pintuco Fill: 2
- Intervinil: 2
- Pinturama: 2
- vinilos interiores: 2
- Koraza como imprimante o acabado interior: 1
- Pintuco Fill como solución principal para capilaridad interior desde la base del muro: 1
- Cotizar por galones sugeridos por el cliente sin metraje: 1
- Koraza como imprimante o acabado interior.: 1
- Pintuco Fill como solución principal para capilaridad interior desde la base del muro.: 1
- Cotizar por galones sugeridos por el cliente sin metraje.: 1
- Koraza como sellador de humedad interior: 1
- Pintucoat: 1
- Interseal: 1
- Intergard: 1
- Interthane 990: 1
- Koraza como sellador de humedad interior.: 1
- Intervinil o Pinturama como acabado en fachadas de alta exposicion: 1
- Aquablock como acabado exterior: 1
- Aquablock: 1
- Intervinil o Pinturama como acabado en fachadas de alta exposicion.: 1
- Aquablock como acabado exterior.: 1
- Pinturama o vinilos interiores como acabado exterior: 1
- rasqueteo o preparacion mecanica que genere polvo: 1
- Intervinil, Pinturama o vinilos interiores como acabado exterior.: 1

### Politicas activas mas frecuentes

- humedad_interior_negativa: 2
- bano_cocina_antihongos: 1
- fachada_alta_exposicion: 1
- eternit_fibrocemento_exterior: 1
- ladrillo_a_la_vista: 1

### Acabados o familias finales mas repetidas

- Viniltex Advanced: 2
- Intervinil: 2
- Pinturama: 2
- Koraza: 2
- Viniltex: 1
- Siliconite 7: 1

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
- Portafolio relacionado por inventario/RAG: SELLO SISMO LADRILLO CLARO CANECA 30 KG, PINTURA EN AERO AZUL CLARO 350ML/250 GR, CONSTRUCLEANER RESTAURADOR FACHA 52.83G, CONSTRUCLEANER RINSE LADRILLO ROJ 52.83G
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

