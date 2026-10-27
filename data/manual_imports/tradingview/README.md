# Importación manual de TradingView (ADR-020)

## Cómo exportar (con tu prueba gratuita Plus/Premium)

1. Abre el gráfico del futuro 6A en TradingView, en la temporalidad que quieras
   (M1/M5/H1/H4/D1).
2. Desplázate hacia atrás / haz zoom out en el eje X para cargar TODA la
   historia que quieras — la exportación solo incluye lo que ya está cargado
   en pantalla, no descarga más atrás automáticamente.
3. Menú ☰ (arriba) → "Download chart data..." (o "Export chart data...") →
   elige formato de fecha **"ISO time"** → Exportar.
4. Límite por exportación: ~10,000 velas (Plus) o ~20,000 (Premium). Si
   necesitas más historia, desplázate más atrás y exporta de nuevo — puedes
   guardar varios archivos del mismo símbolo/temporalidad, el adaptador los
   concatena y deduplica automáticamente.

## Dónde guardar los archivos

Pon los CSV en esta carpeta con el nombre:

```
{SYMBOL}_{TIMEFRAME}.csv
```

Por ejemplo: `6A_H1.csv`, `6A_M5.csv`, `6A_D1.csv`.

Si necesitaste varias exportaciones para el mismo símbolo/temporalidad
(por el límite de velas), nombra los adicionales con cualquier sufijo tras
`__`:

```
6A_M5.csv
6A_M5__2.csv
6A_M5__3.csv
```

## Cómo ingerirlo

```bash
python -m data.import_tradingview 6A H1
```

Esto lee los CSV de esta carpeta, los valida (mismo chequeo de calidad que
el resto del proyecto) y los guarda en `data/raw/6A/H1/` — mismo formato que
cualquier otra fuente, listo para usarse en backtests/`make signal`.

## Realismo sobre el esfuerzo manual por temporalidad

Con ~21h/semana de sesión (FX/futuros, 24/5):

| Temporalidad | Esfuerzo |
|---|---|
| D1, H4 | 1 sola exportación cubre años — fácil |
| H1 | 1-2 exportaciones para ~2-3 años — fácil |
| M5 | ~5-6 exportaciones POR AÑO — tedioso pero viable |
| M1 | Impráctico por este método para más de unas semanas — usa Interactive Brokers si necesitas M1 profundo (ver ADR-018 en CLAUDE.md) |

## Nota legal (no es asesoría legal)

Uso personal para tu propio backtesting es la práctica aceptada.
Redistribuir los datos de TradingView comercialmente no lo es. Este proyecto
es uso personal.
