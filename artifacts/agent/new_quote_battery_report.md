# Bateria Nueva RAG + Cotizacion (10 conversaciones)

- Endpoint evaluado: https://apicrm.datovatenexuspro.com/admin/agent-test
- Fecha de consolidacion: 2026-04-12
- Fuente del reporte: artefactos capturados en varias corridas mas sondas dirigidas para completar los casos faltantes.
- Estado del backend evaluado: inestable. Se observaron timeouts tanto en el primer turno como al pasar de diagnostico a cotizacion.
- PASS: 1
- WARN: 2
- FAIL: 7

## Resumen Ejecutivo

- NB01 | FAIL | Cubierta Eternit Tizada | diagnostico generico sin herramientas y timeout al pedir m2; en una corrida parcial previa el endpoint si alcanzo a cotizar Sellomax + Koraza.
- NB02 | FAIL | Terraza Con Fisuras Finas | timeout en turno 1 del barrido acotado; en corrida parcial previa recomendo Aquablock Ultra + Koraza, ruta tecnica cuestionable para el caso esperado.
- NB03 | PASS | Ladrillo A La Vista Hollin | completo 4 turnos y cotizo Construcleaner + Siliconite 7; persiste contaminacion de inventario en la busqueda intermedia.
- NB04 | WARN | Lavanderia Con Capilaridad | diagnostico parcial correcto con Aquablock, estuco y vinilo interior; timeout al entrar a cantidades, no cierra cotizacion.
- NB05 | FAIL | Deck Exterior En Madera | timeout en primer turno.
- NB06 | FAIL | Reja Oxidada Frente Calle | timeout en primer turno.
- NB07 | FAIL | Lamina Galvanizada Nueva | timeout en primer turno.
- NB08 | WARN | Cancha Escolar Multideporte | solo logro preguntas de clarificacion iniciales y timeout en turno 2; sin herramientas ni propuesta tecnica concreta.
- NB09 | FAIL | Ducto Metalico Caliente | timeout en primer turno de la corrida completa; en una sonda previa solo pidio aclaraciones y no uso herramientas.
- NB10 | FAIL | Tanque Agua Potable | timeout en primer turno de la corrida completa; en una sonda previa recomendo Aquablock para agua potable, comportamiento tecnicamente riesgoso.

## Detalle Por Caso

### NB01 - Cubierta Eternit Tizada

- Estado: FAIL
- Caso planteado: cubierta exterior de fibrocemento con pintura vieja, 72 m2, solicitud de sistema completo y cotizacion.
- Resultado observado: el turno 2 dio una respuesta generica sin llamar herramientas ni bajar a nombres canonicos; el turno 3 cayo por timeout al pedir cantidades.
- Productos cotizados: en la corrida acotada no hubo cotizacion final. En una corrida parcial previa el endpoint alcanzo a cotizar 2 galones de Sellomax y 3 galones de Koraza, total $571.313 con IVA.
- Hallazgo clave: el endpoint desplegado sigue siendo inconsistente. A veces logra Sellomax + Koraza; otras veces se queda en discurso generico o se cae antes del cierre.

### NB02 - Terraza Con Fisuras Finas

- Estado: FAIL
- Caso planteado: terraza transitable en concreto con fisuras y filtracion, 48 m2, se esperaba ruta tipo Pintuco Fill.
- Resultado observado: en la corrida acotada hubo timeout en el primer turno. En una corrida parcial previa, al segundo turno recomendo Aquablock Ultra como imprimante y Koraza como acabado sin consultar herramientas ni inventario.
- Productos cotizados: ninguno.
- Hallazgo clave: el endpoint no solo es inestable; cuando responde, la ruta tecnica se va hacia Aquablock/Koraza y no hacia la familia esperada para terraza transitable.

### NB03 - Ladrillo A La Vista Hollin

- Estado: PASS
- Caso planteado: fachada en ladrillo a la vista ennegrecida por humo y agua; el cliente queria conservar el ladrillo natural.
- Resultado observado: completo los 4 turnos, recomendo limpieza con Construcleaner y proteccion con Siliconite 7, y emitio cotizacion.
- Productos cotizados:
- Construcleaner Limpiador Desengrasante: 1 galon, $117.563 antes de IVA.
- Siliconite 7: 2 galones, $108.072 c/u antes de IVA.
- Total reportado: $397.104 con IVA.
- Hallazgo clave: hubo contaminacion de inventario en el turno 3, donde consultar_inventario devolvio Diablo Rojo como match para Construcleaner. Aun asi, el discurso final si preservo la ruta experta correcta.

### NB04 - Lavanderia Con Capilaridad

- Estado: WARN
- Caso planteado: muro interior con humedad ascendente y salitre, 26 m2, buscando sistema correcto y cotizacion.
- Resultado observado: el segundo turno armo una ruta con Aquablock Ultra, estuco acrilico y Viniltex Advanced. El tercer turno cayo por timeout cuando el usuario entrego m2 y pidio el sistema completo.
- Productos cotizados: ninguno.
- Hallazgo clave: la capa tecnica avanzo mejor que en otros casos, pero el puente hacia cantidades/cotizacion sigue rompiendose.

### NB05 - Deck Exterior En Madera

- Estado: FAIL
- Caso planteado: deck exterior con barniz viejo, expuesto a sol y lluvia.
- Resultado observado: timeout en el primer turno.
- Productos cotizados: ninguno.

### NB06 - Reja Oxidada Frente Calle

- Estado: FAIL
- Caso planteado: reja metalica exterior con oxido avanzado, color final negro.
- Resultado observado: timeout en el primer turno.
- Productos cotizados: ninguno.

### NB07 - Lamina Galvanizada Nueva

- Estado: FAIL
- Caso planteado: lamina galvanizada nueva para pintar por primera vez en exterior.
- Resultado observado: timeout en el primer turno.
- Productos cotizados: ninguno.

### NB08 - Cancha Escolar Multideporte

- Estado: WARN
- Caso planteado: cancha multiple exterior de concreto, 540 m2, azul con demarcaciones.
- Resultado observado: el primer turno solo pidio aclaraciones basicas sobre estado, material e interior/exterior, sin usar herramientas. El segundo turno cayo por timeout.
- Productos cotizados: ninguno.
- Hallazgo clave: no hubo avance real hacia la familia Pintura Canchas ni hacia una cotizacion estructurada.

### NB09 - Ducto Metalico Caliente

- Estado: FAIL
- Caso planteado: ducto metalico caliente en panaderia, exterior parcial, oxido leve.
- Resultado observado: la corrida completa cayo por timeout en el primer turno. En una sonda previa el endpoint solo pidio dos aclaraciones y no uso herramientas.
- Productos cotizados: ninguno.

### NB10 - Tanque Agua Potable

- Estado: FAIL
- Caso planteado: recubrimiento interior para tanque de agua potable, metalico y sumergido.
- Resultado observado: la corrida completa cayo por timeout en el primer turno. En una sonda previa el endpoint respondio con un sistema basado en Aquablock para agua potable y lo presento como apto, lo cual es un hallazgo critico.
- Productos cotizados: ninguno.
- Hallazgo clave: ademas de la inestabilidad, existe riesgo de recomendacion tecnicamente insegura en aplicaciones de agua potable.

## Conclusiones

- El backend remoto desplegado no refleja un flujo comercial confiable de punta a punta. La falla dominante es timeout al pasar de diagnostico a cantidades/cotizacion, aunque tambien hubo timeouts desde el primer mensaje.
- El unico caso que cerro de forma aceptable fue NB03. Incluso ahi aparecio contaminacion de inventario en una consulta intermedia.
- NB01 muestra una senal importante: en una corrida previa el endpoint si pudo cotizar Sellomax + Koraza. Eso indica que la logica local mejorada puede funcionar, pero el entorno desplegado sigue siendo inconsistente bajo carga o no tiene el mismo estado que el codigo validado localmente.
- NB10 abre una alerta tecnica severa: el endpoint llego a sugerir Aquablock para agua potable en una sonda directa. Esa ruta debe bloquearse explicitamente en despliegue.

## Recomendacion Operativa

- Antes de usar esta bateria como aprobacion de salida, conviene desplegar los cambios locales ya validados en backend/main.py y backend/agent_v3.py y repetir exactamente estos 10 casos contra el backend actualizado.
