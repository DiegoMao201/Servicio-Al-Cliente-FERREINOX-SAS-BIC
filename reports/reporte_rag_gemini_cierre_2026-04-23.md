# Reporte RAG Gemini - Cierre Parcial 2026-04-23

## Estado del corpus técnico

- Fuente curada usada por el ingestor: `336` PDFs canónicos.
- Documentos con chunks persistidos: `327`.
- Perfiles persistidos: `327` documentos distintos.
- Índice multimodal persistido: `327` documentos distintos.
- Chunks totales: `10162`.
- Duplicados colapsados por curación: `306`.
- PDFs cuarentenados por curación: `4`.

### PDFs canónicos faltantes en chunks

1. `ACRILICA MANTENIMIENTO 13795 VERDE RAL6025.pdf`
2. `EQUIPOS GRACO.pdf`
3. `FDC ANTICORROSIVO VERDE OLIVA 513.pdf`
4. `Ficha Técnica Bisagras de Piso.pdf`
5. `INTERSEAL 670HS [EN] (1).pdf`
6. `INTERTHANE990 [ES] (1).pdf`
7. `PINTULAC NEGRO MATIZ 7589.pdf`
8. `Steelcraft_Sweets.pdf`
9. `hoja_de_seguridad_mtn_94.pdf`

### PDFs con perfil y multimodal, pero sin chunks

1. `ACRILICA MANTENIMIENTO 13795 VERDE RAL6025.pdf`
2. `EQUIPOS GRACO.pdf`
3. `FDC ANTICORROSIVO VERDE OLIVA 513.pdf`
4. `Steelcraft_Sweets.pdf`
5. `hoja_de_seguridad_mtn_94.pdf`

### PDFs completamente ausentes del índice principal

1. `Ficha Técnica Bisagras de Piso.pdf`
2. `INTERSEAL 670HS [EN] (1).pdf`
3. `INTERTHANE990 [ES] (1).pdf`
4. `PINTULAC NEGRO MATIZ 7589.pdf`

## Resultado del stress test

Archivo fuente: [artifacts/rag/gemini_threshold_audit.json](../artifacts/rag/gemini_threshold_audit.json)

### Resumen global

- `global_recommended_threshold = 0.5296`
- Conclusión del auditor: hay separación limpia entre resultados esperados y ruido en el top-k.

### Índice `technical_chunks`

- `count = 75`
- `avg_similarity = 0.7393`
- `median_similarity = 0.7390`
- `best_similarity = 0.7979`
- `worst_similarity = 0.6838`
- `avg_net_score = 0.4895`
- `median_net_score = 0.7485`
- `best_net_score = 1.0`
- `worst_net_score = 0.0`
- `positives = 39`
- `negatives = 36`
- `positive_min = 0.7447`
- `positive_p10 = 0.7698`
- `positive_p25 = 0.7988`
- `negative_p90 = 0.1629`
- `negative_max = 0.3146`
- `suggested_threshold = 0.5296`

#### Cohorte positiva `technical_chunks`

- `similarity avg = 0.7349`
- `similarity p10 = 0.6975`
- `similarity p25 = 0.7259`
- `similarity p50 = 0.7381`
- `similarity p75 = 0.7443`
- `similarity p90 = 0.7739`
- `net_score avg = 0.8686`
- `net_score p10 = 0.7698`
- `net_score p25 = 0.7988`
- `net_score p50 = 0.9110`
- `net_score p75 = 0.9213`
- `net_score p90 = 0.9358`

#### Cohorte negativa `technical_chunks`

- `similarity avg = 0.7440`
- `similarity p10 = 0.7230`
- `similarity p25 = 0.7333`
- `similarity p50 = 0.7452`
- `similarity p75 = 0.7544`
- `similarity p90 = 0.7629`
- `net_score avg = 0.0787`
- `net_score p10 = 0.0`
- `net_score p25 = 0.0`
- `net_score p50 = 0.1145`
- `net_score p75 = 0.1230`
- `net_score p90 = 0.1629`

### Índice `product_multimodal`

- `count = 75`
- `avg_similarity = 0.6267`
- `median_similarity = 0.6220`
- `best_similarity = 0.7012`
- `worst_similarity = 0.5843`
- `avg_net_score = 0.2223`
- `median_net_score = 0.0699`
- `best_net_score = 0.8443`
- `worst_net_score = 0.0`
- `positives = 21`
- `negatives = 54`
- `positive_min = 0.6443`
- `positive_p10 = 0.6535`
- `positive_p25 = 0.6794`
- `negative_p90 = 0.0812`
- `negative_max = 0.2066`
- `suggested_threshold = 0.4254`

#### Cohorte positiva `product_multimodal`

- `similarity avg = 0.6226`
- `similarity p10 = 0.5935`
- `similarity p25 = 0.6064`
- `similarity p50 = 0.6252`
- `similarity p75 = 0.6367`
- `similarity p90 = 0.6461`
- `net_score avg = 0.7188`
- `net_score p10 = 0.6535`
- `net_score p25 = 0.6794`
- `net_score p50 = 0.6941`
- `net_score p75 = 0.7864`
- `net_score p90 = 0.8191`

#### Cohorte negativa `product_multimodal`

- `similarity avg = 0.6283`
- `similarity p10 = 0.6056`
- `similarity p25 = 0.6161`
- `similarity p50 = 0.6219`
- `similarity p75 = 0.6417`
- `similarity p90 = 0.6593`
- `net_score avg = 0.0293`
- `net_score p10 = 0.0`
- `net_score p25 = 0.0`
- `net_score p50 = 0.0`
- `net_score p75 = 0.0725`
- `net_score p90 = 0.0812`

## Hallazgos técnicos del stress test

### Fortalezas claras

1. `technical_chunks` ya discrimina muy bien entre candidatos útiles y ruido químicamente peligroso cuando se usa `net_score`.
2. Casos fuertes observados:
   - `FT INTERLINE 399` para novolac y resistencia química severa.
   - `INTERTHANE 990` para poliuretano alifático exterior.
   - `EPÓXICA BASE AGUA` para interior de bajo olor con resistencia mecánica y química moderada.
   - `INTERZINC 52` y `EPOXY ZINC PRIMER` para esquemas ricos en zinc.
3. La penalización por `forbidden_terms` elimina resultados peligrosos aunque tengan buena similitud vectorial.
4. La penalización por falta de señal bicomponente separa coincidencias superficiales de coincidencias técnicamente válidas.

### Debilidades observadas

1. El índice `product_multimodal` todavía aporta menos precisión que `technical_chunks`.
2. Varios resultados multimodales quedan rechazados por lenguaje comercial o decorativo contenido en resúmenes válidos pero ambiguos.
3. Consultas de inmersión, agua potable y algunas de mantenimiento industrial todavía dependen más del índice textual que del multimodal.
4. Los casos de pisos y recubrimientos decorativos/industriales mezclados siguen siendo sensibles a contaminación semántica por palabras como `decorar`.

## Error de despliegue backend

### Síntoma

El backend en producción fallaba con `ModuleNotFoundError: No module named 'backend'`.

### Causa raíz

El contenedor backend estaba construido copiando `backend/` directamente dentro de `/app` y arrancando con `uvicorn main:app`. Ese empaquetado elimina el paquete `backend` dentro del contenedor, pero el código real usa muchos imports del tipo `backend.*`.

### Corrección aplicada

1. El `Dockerfile` del backend ahora instala dependencias desde [requirements.txt](../requirements.txt).
2. El contenedor ahora copia `backend/` a `/app/backend/`.
3. También copia recursos de runtime requeridos por el backend:
   - `data/`
   - `artifacts/`
   - `.streamlit/`
   - `LOGO FERREINOX SAS BIC 2024.png`
4. El arranque quedó corregido a `uvicorn backend.main:app --host 0.0.0.0 --port 8000`.

Nota: `datos_empleados.xlsx` no se copia en la imagen porque no forma parte del repositorio desplegado en Coolify. El backend tolera su ausencia en arranque y usa fallback vacío o resolución desde base de datos cuando aplica.

### Archivos corregidos

- [backend/Dockerfile](../backend/Dockerfile)
- [docker-compose.yml](../docker-compose.yml)
- [DESPLIEGUE_SERVIDOR_DETALLADO.md](../DESPLIEGUE_SERVIDOR_DETALLADO.md)
- [GUIA_COOLIFY_CRM_FERREINOX.md](../GUIA_COOLIFY_CRM_FERREINOX.md)

## Conclusión ejecutiva

1. La base técnica actual ya muestra fuerza real en `technical_chunks`.
2. El threshold más sólido hoy para corte global es `0.5296`.
3. El multimodal sirve como apoyo, no como índice principal.
4. Los `9` faltantes no cambian la conclusión estructural del RAG, aunque sí conviene complementar con más fichas técnicas valiosas para robustecer cobertura futura.
5. El error de despliegue backend no era del modelo ni de la base vectorial; era un problema de empaquetado del contenedor.