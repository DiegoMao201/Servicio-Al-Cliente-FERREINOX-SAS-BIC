# Guia Para Ensenar Reglas Atomicas

Objetivo: registrar conocimiento experto sin contaminar el agente con reglas ambiguas, mezcladas o demasiado generales.

## Regla base

Usa una sola regla por mensaje.

Formato recomendado:

```text
ENSEÑAR: contexto=<sustrato + ubicacion + estado>; etapa=<preparacion|sellado|acabado|herramientas|ventas>; recomendar=<producto(s) obligatorios>; evitar=<producto(s) o herramienta(s) prohibidos>; tipo=<recomendar|evitar|proceso|alerta_superficie>; regla=<instruccion completa y concreta>
```

## Principios

- Una regla debe cubrir un solo contexto técnico.
- No mezcles varios sustratos en la misma enseñanza.
- No mezcles preparación, acabado y ventas en una sola regla.
- Si hay productos obligatorios y productos prohibidos, declara ambos.
- Si una herramienta está prohibida, regístrala como `evitar`.
- Si el riesgo es de seguridad, usa `tipo=alerta_superficie`.

## Buenos ejemplos

```text
ENSEÑAR: contexto=techo eternit exterior repintado; etapa=preparacion; evitar=lijas, rasqueta, lijado en seco; recomendar=hidrolavadora, jabon, hipoclorito, cepillo; tipo=alerta_superficie; regla=En techos de eternit o fibrocemento repintados, la preparacion debe ser humeda. Nunca lijar ni rasquetear por riesgo de polvo de asbesto.
```

```text
ENSEÑAR: contexto=techo eternit exterior repintado; etapa=sellado; recomendar=Sellomax; tipo=proceso; regla=En eternit exterior ya pintado, aplicar Sellomax antes del acabado final para mejorar adherencia y uniformidad del sistema.
```

```text
ENSEÑAR: contexto=techo eternit exterior repintado; etapa=acabado; recomendar=Koraza; evitar=Intervinil, Pinturama; tipo=evitar; regla=Para techos exteriores de eternit usar acabado 100 por ciento exterior como Koraza. No usar Intervinil ni Pinturama en este contexto.
```

## Malos ejemplos

```text
ENSEÑAR: en eternit no uses lijas, y tambien vende Sellomax con Koraza, y no metas Intervinil, y ademas recuerda que en ladrillo no va Koraza.
```

Problema: mezcla varios contextos y varias decisiones en una sola nota.

```text
ENSEÑAR: Koraza siempre es mejor.
```

Problema: no tiene contexto, no tiene etapa y contamina consultas fuera de lugar.

## Plantilla rapida

```text
ENSEÑAR: contexto=<contexto exacto>; etapa=<etapa>; recomendar=<si aplica>; evitar=<si aplica>; tipo=<tipo>; regla=<regla concreta>
```

## Secuencia recomendada para un caso complejo

Si un caso necesita 4 reglas, envia 4 mensajes separados:

1. Preparacion.
2. Sellado o imprimacion.
3. Acabado.
4. Herramientas o restriccion comercial.

Ese formato reduce ruido, mejora recuperacion y hace mas facil aplicar bloqueos deterministas.