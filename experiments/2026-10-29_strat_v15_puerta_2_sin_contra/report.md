# V15 — 2026-10-29
> Resultado EXPLORATORIO (ADR-007): primera prueba de una regla derivada del análisis, NO una validación definitiva. Estructura sobre proxy spot AUD/USD, no el futuro real 6A (ADR-006). Una hipótesis predefinida => sin Deflated Sharpe; ajustar parámetros tras ver esto activa el control de tests múltiples (6.2).

**390 ops** → evidencia preliminar, no concluyente (100-999 ops, ADR-009). Días con puerta abierta: 43.1% de 1649 (V14: 19.2%).

## PRIMARIA (todas las entradas, costo REAL 6A, 1 tick en stops)
exp(A)=+0.072R (n=180) vs exp(B+C)=-0.052R (n=190); dif=+0.124R, IC95 dif [-0.15,+0.40] -> NO se confirma A > B+C
{'n': 390, 'win': 0.421, 'exp_net': 0.003, 'ic95': '[-0.13,+0.14]', 'exp_bruta': 0.103, 'costo_R': 0.1, 'avg_win': 1.568, 'avg_loss': -1.134, 'veredicto': 'IC cruza 0'}

### sensibilidad slippage 0 tick(s): {'n': 390, 'win': 0.421, 'exp_net': 0.048, 'ic95': '[-0.07,+0.18]', 'exp_bruta': 0.103, 'costo_R': 0.055, 'avg_win': 1.568, 'avg_loss': -1.055, 'veredicto': 'IC cruza 0'}
### sensibilidad slippage 2 tick(s): {'n': 390, 'win': 0.421, 'exp_net': -0.043, 'ic95': '[-0.18,+0.10]', 'exp_bruta': 0.103, 'costo_R': 0.146, 'avg_win': 1.568, 'avg_loss': -1.212, 'veredicto': 'IC cruza 0'}

## Con costo del modelo viejo (referencia)
exp(A)=-0.052R (n=180) vs exp(B+C)=-0.190R (n=190); dif=+0.138R, IC95 dif [-0.13,+0.40] -> NO se confirma A > B+C
{'n': 390, 'win': 0.421, 'exp_net': -0.132, 'ic95': '[-0.26,-0.00]', 'exp_bruta': 0.103, 'costo_R': 0.235, 'avg_win': 1.39, 'avg_loss': -1.237, 'veredicto': 'IC<0'}

## 2026+ (costo real 1 tick) n=55
{'n': 55, 'win': 0.4, 'exp_net': -0.058, 'ic95': '[-0.40,+0.29]', 'exp_bruta': 0.049, 'costo_R': 0.107, 'avg_win': 1.566, 'avg_loss': -1.141, 'veredicto': 'IC cruza 0'}
## < 2026 (costo real 1 tick) n=335
{'n': 335, 'win': 0.424, 'exp_net': 0.013, 'ic95': '[-0.13,+0.15]', 'exp_bruta': 0.112, 'costo_R': 0.099, 'avg_win': 1.568, 'avg_loss': -1.132, 'veredicto': 'IC cruza 0'}

### por bucket (costo real 1 tick)
      n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   180  0.444   0.072  [-0.12,+0.27]     0.161   0.089   1.563   -1.121         IC cruza 0
A0   20    0.4  -0.105  [-0.65,+0.45]      0.04   0.145   1.512   -1.183  inconcluso (n<30)
B   107  0.449   0.081  [-0.17,+0.33]     0.178   0.097   1.573   -1.132         IC cruza 0
C    83  0.337  -0.224  [-0.49,+0.05]    -0.106   0.118    1.59   -1.148         IC cruza 0

### por gate_tipo (costo real 1 tick)
               n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
dos_neutral  199  0.407  -0.028  [-0.21,+0.15]      0.07   0.098   1.575   -1.129  IC cruza 0
tres         191  0.435   0.035  [-0.15,+0.22]     0.137   0.103   1.562   -1.139  IC cruza 0

### por pm_rel (costo real 1 tick)
             n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
a_favor     82  0.537   0.316  [+0.02,+0.61]     0.407    0.09   1.571   -1.136        IC>0
en_contra   94  0.436   0.048  [-0.21,+0.32]     0.145   0.097   1.559   -1.121  IC cruza 0
neutral    214  0.369  -0.138  [-0.31,+0.04]    -0.032   0.106   1.571   -1.138  IC cruza 0

### por trigger (costo real 1 tick)
                 n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
eq_extremo     180  0.467   0.126  [-0.06,+0.32]     0.225   0.099   1.569   -1.136  IC cruza 0
eq_vwap        106  0.415  -0.012  [-0.26,+0.24]     0.087   0.099   1.565   -1.131  IC cruza 0
sweep_extremo  104  0.346  -0.197  [-0.44,+0.04]    -0.093   0.104    1.57   -1.132  IC cruza 0

### por candle_aligned (costo real 1 tick)
         n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
False  130  0.408  -0.029  [-0.25,+0.19]     0.069   0.098   1.565   -1.126  IC cruza 0
True   260  0.427   0.018  [-0.14,+0.19]      0.12   0.101    1.57   -1.137  IC cruza 0

## Sensibilidad: solo riesgo <= $500 con 6 contratos n=251 de 390
{'n': 251, 'win': 0.41, 'exp_net': -0.046, 'ic95': '[-0.21,+0.12]', 'exp_bruta': 0.08, 'costo_R': 0.127, 'avg_win': 1.563, 'avg_loss': -1.167, 'veredicto': 'IC cruza 0'}
      n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   102  0.471   0.118  [-0.15,+0.38]     0.234   0.115   1.558   -1.161         IC cruza 0
A0   19  0.421  -0.053  [-0.63,+0.53]     0.095   0.147   1.512   -1.191  inconcluso (n<30)
B    66  0.394   -0.09  [-0.42,+0.24]     0.038   0.128   1.562   -1.164         IC cruza 0
C    64  0.328  -0.262  [-0.57,+0.05]    -0.125   0.137   1.595   -1.169         IC cruza 0

## Por año (costo real 1 tick)
       n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
2020  26  0.423   0.024  [-0.49,+0.54]     0.112   0.087   1.579   -1.116  inconcluso (n<30)
2021  57  0.474   0.141  [-0.20,+0.48]      0.24   0.099   1.566    -1.14         IC cruza 0
2022  74  0.378  -0.087  [-0.38,+0.21]    -0.005   0.082   1.587   -1.105         IC cruza 0
2023  58  0.397  -0.066  [-0.39,+0.26]     0.034   0.101    1.56   -1.135         IC cruza 0
2024  56  0.375  -0.138  [-0.48,+0.21]    -0.018    0.12   1.556   -1.154         IC cruza 0
2025  64    0.5    0.21  [-0.13,+0.55]     0.316   0.105   1.565   -1.144         IC cruza 0
2026  55    0.4  -0.058  [-0.41,+0.29]     0.049   0.107   1.566   -1.141         IC cruza 0