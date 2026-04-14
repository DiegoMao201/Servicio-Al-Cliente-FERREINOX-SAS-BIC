# Guía de Renombre de Fichas RAG Contra Inventario

Objetivo: que el nombre del archivo técnico se parezca lo máximo posible a la familia comercial real que vive en inventario, ventas y stock, sin volver la ficha demasiado específica a una sola presentación o color.

## Regla madre

El nombre correcto de una ficha no es el nombre bonito de mercadeo ni una frase genérica.

El nombre correcto es:

`MARCA_O_PREFIJO + FAMILIA_BASE_ERP + CODIGO_FAMILIA_ESTABLE`

Solo agrega color o presentación cuando esa ficha represente una variante única y no una familia.

## Qué sí funciona

- Usa el mismo tronco de nombre con el que aparece el 95% de las referencias en inventario.
- Conserva prefijos útiles si realmente distinguen la familia en ERP: `PQ`, `MEG`, `INTER`, `UFA`, `AC`.
- Conserva códigos de familia estables cuando ayudan a unir ficha e inventario: `9400`, `28600`, `P502`, `G300N`, `2060`.
- Prioriza familia sobre presentación. Mejor una ficha llamada `MEG CRYSTAL CLEAR 9400 AC` que `MEG CRYSTAL CLEAR 9400 AC 3.78L`.
- Prioriza familia sobre color, salvo que la ficha sea realmente de una variante color-específica.

## Qué no debes hacer

- No usar nombres genéricos como `PINTURA EN AEROSOL`, `THINNER`, `PRIMER`, `BARNIZ`, `AEROSOL TEKBOND`.
- No meter descripciones de vendedor o frases humanas como `para plástico`, `para baño`, `de exteriores` si no existen así en ERP como familia principal.
- No usar una sola presentación como nombre maestro de la ficha si existen galón, cuarto, cuñete o aerosol para la misma familia.
- No dejar errores tipográficos. Un typo rompe RAG, matching, universo y auditoría.

## Convención recomendada

Usa una de estas tres formas, en este orden de preferencia:

### 1. Familia ERP exacta

Ejemplo:

- `MEG PRIMER PARA PLASTICOS 28600 AC`
- `THINNER UNIVERSAL P502 MEG AC`
- `ARENA QUARZO G300N UFA850`

### 2. Familia ERP exacta sin presentación ni color

Cuando el archivo técnico aplica a varias referencias:

- `PQ VINILTEX BYC SA BLANCO 2001` solo si toda la familia gira alrededor de ese tronco estable
- mejor aún: `VINILTEX BYC SA 2001` si internamente todas las variantes cuelgan de ese nombre

### 3. Familia canónica controlada + alias ERP documentados

Úsalo solo cuando el inventario tiene muchas variantes muy sucias pero el producto técnico es uno solo:

- `Viniltex Baños y Cocinas`
- `Interthane 990 + Catalizador`
- `Pintulux 3 en 1`

En este caso debes dejar documentado el lookup ERP preferido en la plantilla de mapeo.

## Regla por tipo de producto

### Arquitectónicos

- Usa la familia de producto y no una sola presentación.
- Si el ERP trae un tronco muy claro, úsalo.
- Ejemplo bueno: `PQ VINILTEX BYC SA BLANCO 2001`
- Ejemplo malo: `Viniltex baño galón blanco`

### Industriales

- Conserva serie o código técnico.
- Ejemplo bueno: `INTERCHAR 2060`
- Ejemplo malo: `Pintura intumescente`

### Solventes y ajustadores

- Conserva código técnico siempre.
- Ejemplo bueno: `THINNER UNIVERSAL P502 MEG AC`
- Ejemplo malo: `Thinner universal`

### Aerosoles

- No dejes la ficha al nivel de `PQ AEROCOLOR` si el portafolio tiene subfamilias reales.
- Baja un nivel más: `PQ AEROCOLOR MULTIS`, `PQ AEROCOLOR ELECTRODOMESTICOS`, `PQ AEROCOLOR RINES`, etc.

## Evaluación de tus ejemplos

### Sí o casi sí

- `THINNER UNIVERSAL P502 MEG`
  Recomendación: mejor `THINNER UNIVERSAL P502 MEG AC`
  Motivo: en inventario apareció como `THINNER UNIVERSAL P502 MEG AC 3.78L`

- `MEG CRYSTAL CLEAR 9400`
  Recomendación: mejor `MEG CRYSTAL CLEAR 9400 AC`
  Motivo: en inventario apareció como `MEG CRYSTAL CLEAR 9400 AC 3.78L` y `0.94L`

- `ARENA QUARZO G300N`
  Recomendación: mejor `ARENA QUARZO G300N UFA850`
  Motivo: en inventario apareció como `ARENA QUARZO G300N UFA850/25KG/AA7`

- `MEG PRIMER PARA PLASTICOS 28600 AC`
  Recomendación: está bien
  Motivo: coincide casi exacto con inventario

### No

- `INTERCHARD 2060`
  Recomendación: corregir a `INTERCHAR 2060`
  Motivo: el typo te rompe recuperación, matching y canonización

- `PINTURA EN AEROSOL - TEKBOND`
  Recomendación: no usar
  Motivo: demasiado genérico y no apareció así en inventario

- `PQ AEROCOLOR`
  Recomendación: usar solo como nivel padre en documentación, no como nombre final de ficha si tienes subfamilia detectable
  Motivo: sí existe como tronco, pero es muy amplio; conviene bajarlo a subfamilia real

## Regla práctica para saber si el nombre quedó bien

Hazte estas 5 preguntas:

1. Si busco este nombre contra inventario, ¿aparecen primero referencias de la familia correcta?
2. ¿El nombre diferencia esta familia de otras cercanas de la misma marca?
3. ¿El nombre evita depender de una sola presentación?
4. ¿El nombre evita depender de un solo color, salvo que sea obligatorio?
5. ¿El nombre está libre de typos y palabras genéricas?

Si la respuesta a una de esas preguntas es no, el nombre todavía no está listo.

## Estructura de documentación que sí conviene crear

No basta con renombrar PDFs. Debes dejar una tabla maestra por cada familia.

Columnas mínimas:

- `archivo_actual`
- `archivo_nuevo_propuesto`
- `familia_canonica`
- `lookup_inventario_preferido`
- `marca`
- `subfamilia`
- `codigo_familia`
- `presentaciones_detectadas`
- `colores_detectados`
- `alias_cliente`
- `alias_rag`
- `ref_erp_ejemplo`
- `estado_validacion`
- `observaciones`

## Criterio de oro

El PDF debe quedar nombrado como familia técnica.

La tabla de mapeo debe resolver el resto.

No intentes meter toda la inteligencia dentro del nombre del archivo.

## Recomendación final

Sí, vas por buen camino si usas nombres que se parezcan a como viven en ventas y stock.

Pero la forma más adecuada no es `cualquier nombre parecido`.

La forma más adecuada es:

- nombre de ficha = familia ERP estable
- plantilla de mapeo = alias, variantes, referencias ejemplo y lookup preferido
- canonización = puente final entre lenguaje humano, RAG e inventario
