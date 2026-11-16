---
name: registrar-trade-journal
description: Ordena un trade real o de simulación en el formato del journal para análisis posterior. Usar cuando César cuente o pegue un trade.
---
Pide solo lo que falte y arma una fila con las propiedades de la base de Notion del journal (Date = fecha CDMX del día que operó; `Dia del testing` se deja VACÍO en trades vivos o de sim, solo se llena en backtests manuales) más estas nuevas: Hora entrada (CDMX), Confirmación (IFVG / 3 velas), Sweep (cercano 3h / de todo el día), Resultado R (número), Salida (TP / SL / manual). Columnas de referencia:
fecha de la sesión, lado (Long/Short), hora de entrada en CDMX, entry, sl, tp, RR, resultado en R, tipo de confirmación (IFVG o 3 velas), tipo de sweep (cercano o de todo el día), BIAS D1/4H/NY AM/NY PM, se siguió el plan (sí/no), error cometido, comentario corto.
Marca si es trade VIVO o de BACKTEST manual: no se mezclan al analizar.
No inventes precios ni resultados que César no dio.
