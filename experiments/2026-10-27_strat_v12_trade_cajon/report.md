# V12 — efectividad por setup — 2026-10-27

> Resultado EXPLORATORIO (ADR-007): primera prueba de una regla derivada del análisis, NO una validación definitiva. Estructura sobre proxy spot AUD/USD, no el futuro real 6A (ADR-006). Una hipótesis predefinida => sin Deflated Sharpe; ajustar parámetros tras ver esto activa el control de tests múltiples (6.2).

**118 operaciones** → evidencia preliminar, no concluyente (100-999 ops, ADR-009) (ADR-009). Una corrida registrada.

## Hipótesis primaria (fijada antes)
exp(A)=-0.480R (n=43) vs exp(B+C)=-0.195R (n=66); dif=-0.285R, IC95 dif [-0.77,+0.20] -> NO se confirma A > B+C

## Global
{'n': 118, 'win': 0.356, 'exp_net': -0.316, 'ic95': '[-0.54,-0.08]', 'exp_bruta': -0.065, 'costo_R': 0.25, 'avg_win': 1.394, 'avg_loss': -1.26, 'veredicto': 'IC<0'}

## Bucket horario — test_2024-25
     n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   16  0.125  -0.956  [-1.31,-0.46]    -0.675   0.281   1.371   -1.288  inconcluso (n<30)
A0   4   0.25  -0.643  [-1.32,+0.64]     -0.35   0.293   1.278   -1.283  inconcluso (n<30)
B   22  0.455  -0.045  [-0.56,+0.54]       0.2   0.245   1.405   -1.253  inconcluso (n<30)
C   12    0.5   0.056  [-0.61,+0.73]     0.316    0.26   1.331   -1.218  inconcluso (n<30)

## Bucket horario — train_2020-23
     n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   27  0.407  -0.197  [-0.67,+0.29]     0.059   0.257    1.35   -1.261  inconcluso (n<30)
A0   5    0.4  -0.239  [-1.36,+0.89]      0.04   0.279   1.436   -1.356  inconcluso (n<30)
B   22  0.364  -0.243  [-0.76,+0.30]    -0.036   0.206   1.486   -1.231  inconcluso (n<30)
C   10    0.2  -0.721  [-1.29,+0.08]     -0.47   0.251   1.442   -1.261  inconcluso (n<30)

## Bucket horario — TODO
     n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   43  0.302   -0.48  [-0.84,-0.11]    -0.214   0.266   1.354   -1.274               IC<0
A0   9  0.333  -0.419  [-1.27,+0.48]    -0.133   0.285   1.383   -1.319  inconcluso (n<30)
B   44  0.409  -0.144  [-0.52,+0.24]     0.082   0.226   1.441   -1.241         IC cruza 0
C   22  0.364  -0.297  [-0.79,+0.25]    -0.041   0.256   1.358   -1.243  inconcluso (n<30)

## Tipo de disparador
                n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
eq_extremo     58  0.397  -0.208  [-0.54,+0.13]     0.043   0.251   1.402   -1.266         IC cruza 0
eq_vwap        35  0.257  -0.587  [-0.96,-0.20]    -0.326   0.261   1.365   -1.263               IC<0
sweep_extremo  25    0.4  -0.186  [-0.70,+0.34]     0.048   0.234   1.401   -1.244  inconcluso (n<30)

## Vela previa == hoy == dirección (candle_aligned)
        n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
False  89   0.36  -0.306  [-0.57,-0.04]    -0.055    0.25   1.393   -1.259               IC<0
True   29  0.345  -0.346  [-0.80,+0.13]    -0.097    0.25   1.398   -1.265  inconcluso (n<30)

## n alineadas (3 ó 4 de 4)
     n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
3  103  0.359  -0.302  [-0.55,-0.05]    -0.055   0.247   1.395   -1.253               IC<0
4   15  0.333  -0.409  [-1.00,+0.29]    -0.133   0.276   1.387   -1.307  inconcluso (n<30)

## Profundidad del sweep (terciles, descriptivo)
        n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
baja   40    0.3  -0.449  [-0.80,-0.06]    -0.205   0.244   1.397   -1.241        IC<0
media  39  0.487   0.035  [-0.38,+0.45]     0.269   0.234   1.408   -1.269  IC cruza 0
alta   39  0.282  -0.529  [-0.88,-0.13]    -0.256   0.273   1.367   -1.274        IC<0

## PERFECTO (A ∧ vela alineada ∧ eq_vwap) vs resto
         n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
False  111  0.369   -0.28  [-0.52,-0.04]     -0.03    0.25   1.394   -1.261               IC<0
True     7  0.143  -0.877  [-1.30,-0.11]    -0.629   0.249    1.38   -1.254  inconcluso (n<30)

## Por cohorte (año)
       n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
2020   5    0.2  -0.756  [-1.36,+0.32]     -0.48   0.276   1.367   -1.287  inconcluso (n<30)
2021  24  0.417   -0.16  [-0.70,+0.40]     0.087   0.248   1.403   -1.276  inconcluso (n<30)
2022  16   0.25  -0.519  [-1.03,+0.02]    -0.337   0.182   1.462    -1.18  inconcluso (n<30)
2023  19  0.421  -0.165  [-0.75,+0.44]     0.105   0.271   1.407   -1.309  inconcluso (n<30)
2024  20    0.3  -0.506  [-1.02,+0.03]    -0.215   0.291   1.322   -1.289  inconcluso (n<30)
2025  21  0.333  -0.369  [-0.89,+0.15]    -0.124   0.246   1.394   -1.251  inconcluso (n<30)
2026  13  0.462  -0.023  [-0.67,+0.70]     0.223   0.246   1.393   -1.237  inconcluso (n<30)

## Zona usada para TP
          n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
day_hi   41   0.39  -0.234  [-0.61,+0.15]      0.02   0.254   1.342   -1.242         IC cruza 0
day_lo   34  0.353  -0.318  [-0.73,+0.12]    -0.082   0.236   1.383   -1.246         IC cruza 0
fvg_h1   10    0.4  -0.138  [-0.95,+0.68]     0.059   0.197   1.486   -1.221  inconcluso (n<30)
pdh       5    0.4  -0.226  [-1.34,+0.89]      0.04   0.266   1.402   -1.312  inconcluso (n<30)
pdl       4   0.25  -0.592  [-1.32,+0.76]     -0.35   0.242   1.417   -1.262  inconcluso (n<30)
rr_base  24  0.292  -0.498  [-0.97,+0.01]    -0.212   0.286   1.474    -1.31  inconcluso (n<30)
