---
applyTo: "**/*.py"
description: Reglas de código para el motor cuantitativo
---
- Type hints y docstring corto con supuestos en funciones públicas.
- Timestamps siempre tz-aware en UTC. Nunca uses hora local.
- Features y señales con `shift`/merge_asof backward; prohibido usar la barra actual para decidir algo que ocurre antes de que cierre.
- Cada función nueva de features/estrategia lleva test sintético con respuesta conocida y test anti-look-ahead.
- Sin números mágicos: parámetros en constantes con nombre y comentario de por qué ese default.
- No cambies defaults de ADR-004/008/009 sin ADR y sin anotarlo como test múltiple.
