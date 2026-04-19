# Continuidad Agente Interno 2026-04-18

## Estado Real

- No se ha hecho `push`.
- No se ha hecho `commit`.
- El trabajo actual existe solo en el working tree local sobre `main`.
- El backend ya soporta perfil `internal` por variable `AGENT_PROFILE`.
- El contenedor real del backend usa Python 3.11.
- El workspace local ya fue recreado sobre `.venv` con Python 3.11.15.
- VS Code ya quedó fijado a ese interprete en [.vscode/settings.json](../.vscode/settings.json).

## Cambios Ya Implementados

### Runtime Del Agente

- Se creo [backend/agent_profiles.py](../backend/agent_profiles.py) para seleccionar perfil y toolset.
- Se creo [backend/agent_prompt_internal.py](../backend/agent_prompt_internal.py) con prompt dedicado para WhatsApp interno.
- Se creo [backend/agent_prompt_customer.py](../backend/agent_prompt_customer.py) con prompt dedicado para WhatsApp de clientes.
- Se adapto [backend/agent_v3.py](../backend/agent_v3.py) para cargar prompt, tools y guardias segun perfil.
- Se adapto [backend/main.py](../backend/main.py) para bloquear traslados, despachos y reclamos fuera de alcance en `internal`.
- Se adapto [backend/main.py](../backend/main.py) para que el despliegue `customer` no active el flujo de autenticacion interna.
- Se expone `agent_profile` en `/` y `/health`.

### Despliegue

- Se actualizo [.env.example](../.env.example) con `AGENT_PROFILE`, `OPENAI_MODEL` y `APP_VERSION_LABEL`.
- Se actualizo [docker-compose.yml](../docker-compose.yml) para inyectar `AGENT_PROFILE`, `OPENAI_MODEL` y `APP_VERSION_LABEL` al backend.
- El despliegue actual solo se comportara como `internal` despues de redeploy con `AGENT_PROFILE=internal`.

### Orden Del Repo

- Se crearon carpetas base: `tests/internal`, `tests/customer`, `tests/regression`, `reports`, `tools/audits`, `tools/diagnostics`, `tools/exploration`.
- Ya se movieron primeras pruebas internas a `tests/internal` con wrappers en raiz.
- Ya se movieron tres reportes markdown a `reports/regressions` con stubs en raiz.
- Ya se movieron dos resultados `.txt` de regresion a `reports/regressions` con stubs en raiz.
- En esta sesion se movieron pruebas simples de regresion a `tests/regression` con wrappers en raiz.

## Estado De Pruebas

### Validacion Python 3.11 Cerrada

- `.venv` recreado con Python 3.11.15.
- Dependencias de [backend/requirements.txt](../backend/requirements.txt) instaladas en ese entorno.
- Bateria interna validada en Python 3.11 con resultado OK:
	- `tests.internal.test_internal_profile`
	- `tests.internal.test_internal_latency_config`
	- `tests.internal.test_agent_v3_preload`
	- `tests.internal.test_inventory_flow_regression`
	- `tests.internal.test_technical_product_canonicalization`

### Internal Ya Ubicadas

- `tests/internal/test_internal_profile.py`
- `tests/internal/test_agent_v3_preload.py`
- `tests/internal/test_inventory_flow_regression.py`
- `tests/internal/test_technical_product_canonicalization.py`

### Regression Ubicadas En Esta Sesion

- `tests/regression/test_name_confirm.py`
- `tests/regression/test_question_filter.py`
- `tests/regression/test_quality_system.py`
- `tests/regression/test_behavioral_rules.py`
- `tests/regression/test_diagnostic_first.py`

## Lo Que Falta

### Operativo Inmediato

1. Redeploy del backend actual con `AGENT_PROFILE=internal`.
2. Verificar `/health` y `/` devolviendo `agent_profile: internal`.
3. Probar el numero actual de WhatsApp con casos reales internos.

### Repo Y Pruebas

1. Seguir moviendo resultados estaticos a `reports/` sin romper scripts que aun escriben en raiz.
2. Seguir separando pruebas por familia: `internal`, `customer`, `rag`, `regression`.
3. Mover auditorias y diagnosticos a `tools/` con compatibilidad temporal.

### Arquitectura Siguiente

1. Separar guardias y reglas de negocio por perfil en vez de compartir ramas legacy.
2. Preparar despliegue operativo de `customer` con numero y webhook propios.
3. Reducir codigo muerto o inaccesible para el runtime `internal`.

## Riesgos Reales

- El repo tiene muchos scripts sueltos en raiz que todavia leen o escriben rutas antiguas.
- No conviene mover en bloque archivos JSON o TXT que siguen siendo outputs directos de scripts hasta introducir rutas centralizadas.
- La validacion local con `/usr/bin/python3` no es representativa del despliegue porque el contenedor usa Python 3.11.

## Siguiente Secuencia Recomendada

1. Terminar limpieza segura del repo: tests simples, reportes estaticos, auditorias de bajo acoplamiento.
2. Ejecutar validacion focalizada dentro del entorno Python 3.11 del proyecto.
3. Preparar corte de despliegue `internal` y checklist de prueba en WhatsApp.
4. Luego abrir `customer` como segundo despliegue.

## Nota De Continuidad

Si otra sesion retoma este trabajo, debe partir de este criterio:

- no inventar compatibilidades falsas con Python 3.9,
- no mezclar el alcance `internal` con pedidos o cotizaciones,
- no mover masivamente resultados o scripts sin wrappers o sin revisar consumidores,
- priorizar siempre despliegue verificable sobre limpieza cosmetica.