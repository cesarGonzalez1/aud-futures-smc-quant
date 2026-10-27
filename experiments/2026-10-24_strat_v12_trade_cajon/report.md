# V12 — efectividad por setup — 2026-10-24

> Resultado EXPLORATORIO (ADR-007): primera prueba de una regla derivada del análisis, NO una validación definitiva. Estructura sobre proxy spot AUD/USD, no el futuro real 6A (ADR-006). Una hipótesis predefinida => sin Deflated Sharpe; ajustar parámetros tras ver esto activa el control de tests múltiples (6.2).

**95 operaciones** → muestra insuficiente para cualquier conclusión (<100 ops, ADR-009) (ADR-009). Una corrida registrada.

## Hipótesis primaria (fijada antes)
exp(A)=-0.434R (n=34) vs exp(B+C)=-0.262R (n=54); dif=-0.173R, IC95 dif [-0.72,+0.36] -> NO se confirma A > B+C

## Global
{'n': 95, 'win': 0.358, 'exp_net': -0.318, 'ic95': '[-0.57,-0.06]', 'exp_bruta': -0.061, 'costo_R': 0.257, 'avg_win': 1.388, 'avg_loss': -1.269, 'veredicto': 'IC<0'}

## Bucket horario — test_2024-25
     n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A    7    0.0  -1.316  [-1.40,-1.24]      -1.0   0.316     NaN   -1.316  inconcluso (n<30)
A0   2    0.5  -0.053  [-1.37,+1.27]       0.3   0.353   1.267   -1.373  inconcluso (n<30)
B   15  0.467  -0.012  [-0.69,+0.68]     0.233   0.245   1.381    -1.23  inconcluso (n<30)
C    7  0.429  -0.166  [-0.95,+0.91]     0.114   0.281   1.306   -1.271  inconcluso (n<30)

## Bucket horario — train_2020-23
     n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   27  0.407  -0.206  [-0.69,+0.29]     0.059   0.265   1.342    -1.27  inconcluso (n<30)
A0   5    0.4  -0.249  [-1.37,+0.88]      0.04   0.289    1.43   -1.368  inconcluso (n<30)
B   22  0.364   -0.25  [-0.76,+0.27]    -0.036   0.213    1.48   -1.238  inconcluso (n<30)
C   10    0.2  -0.729  [-1.30,+0.06]     -0.47   0.259   1.435    -1.27  inconcluso (n<30)

## Bucket horario — TODO
     n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   34  0.324  -0.434  [-0.84,-0.02]    -0.159   0.276   1.342   -1.284               IC<0
A0   7  0.429  -0.193  [-1.00,+0.95]     0.114   0.307   1.376   -1.369  inconcluso (n<30)
B   37  0.405  -0.153  [-0.59,+0.28]     0.073   0.226   1.434   -1.235         IC cruza 0
C   17  0.294  -0.497  [-1.00,+0.12]    -0.229   0.268   1.357    -1.27  inconcluso (n<30)

## Tipo de disparador
                n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
eq_extremo     47  0.383  -0.252  [-0.61,+0.13]     0.004   0.256   1.393   -1.273         IC cruza 0
eq_vwap        28   0.25  -0.623  [-1.02,-0.17]    -0.343    0.28   1.355   -1.283  inconcluso (n<30)
sweep_extremo  20   0.45  -0.048  [-0.60,+0.50]      0.18   0.228   1.404   -1.235  inconcluso (n<30)

## Vela previa == hoy == dirección (candle_aligned)
        n   win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
False  75  0.36  -0.312  [-0.60,-0.02]    -0.056   0.256   1.387   -1.268               IC<0
True   20  0.35  -0.341  [-0.88,+0.20]     -0.08   0.261   1.392   -1.274  inconcluso (n<30)

## n alineadas (3 ó 4 de 4)
    n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
3  81   0.37  -0.278  [-0.55,+0.01]    -0.027   0.251   1.391    -1.26         IC cruza 0
4  14  0.286  -0.551  [-1.14,+0.10]    -0.257   0.293   1.367   -1.317  inconcluso (n<30)

## Profundidad del sweep (terciles, descriptivo)
        n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
baja   32  0.281  -0.507  [-0.91,-0.09]    -0.259   0.248   1.362   -1.239        IC<0
media  31  0.452  -0.072  [-0.53,+0.38]     0.177    0.25   1.409   -1.292  IC cruza 0
alta   32  0.344  -0.368  [-0.80,+0.10]    -0.094   0.274   1.382   -1.285  IC cruza 0

## PERFECTO (A ∧ vela alineada ∧ eq_vwap) vs resto
        n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
False  90  0.367  -0.296  [-0.56,-0.02]    -0.038   0.258   1.388   -1.271               IC<0
True    5    0.2  -0.726  [-1.31,+0.34]     -0.48   0.246   1.373   -1.251  inconcluso (n<30)

## Por cohorte (año)
       n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
2020   5    0.2  -0.765  [-1.37,+0.31]     -0.48   0.285   1.359   -1.296  inconcluso (n<30)
2021  24  0.417  -0.168  [-0.71,+0.38]     0.087   0.256   1.396   -1.286  inconcluso (n<30)
2022  16   0.25  -0.525  [-1.04,+0.12]    -0.337   0.188   1.456   -1.186  inconcluso (n<30)
2023  19  0.421  -0.174  [-0.76,+0.43]     0.105    0.28   1.399   -1.319  inconcluso (n<30)
2024  20    0.3  -0.515  [-1.03,+0.01]    -0.215     0.3   1.312   -1.299  inconcluso (n<30)
2025  11  0.455  -0.032  [-0.76,+0.70]       0.2   0.232   1.395   -1.221  inconcluso (n<30)

## Zona usada para TP
          n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
day_hi   33  0.364  -0.315  [-0.72,+0.12]    -0.048   0.266   1.343   -1.262         IC cruza 0
day_lo   29  0.345   -0.34  [-0.79,+0.12]    -0.103   0.237   1.379   -1.245  inconcluso (n<30)
fvg_h1    6    0.5   0.092  [-0.86,+1.03]       0.3   0.208   1.466   -1.281  inconcluso (n<30)
pdh       3  0.667   0.539  [-1.17,+1.46]     0.733   0.194   1.396   -1.174  inconcluso (n<30)
pdl       3  0.333  -0.343  [-1.24,+1.41]    -0.133    0.21   1.411    -1.22  inconcluso (n<30)
rr_base  21  0.286  -0.531  [-1.05,+0.04]    -0.229   0.302   1.447   -1.322  inconcluso (n<30)
