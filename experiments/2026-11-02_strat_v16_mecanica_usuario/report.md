# V16 — 2026-11-02
> Resultado EXPLORATORIO (ADR-007): primera prueba de una regla derivada del análisis, NO una validación definitiva. Estructura sobre proxy spot AUD/USD, no el futuro real 6A (ADR-006). Una hipótesis predefinida => sin Deflated Sharpe; ajustar parámetros tras ver esto activa el control de tests múltiples (6.2).

**507 ops** → evidencia preliminar, no concluyente (100-999 ops, ADR-009). Días con puerta abierta: 43.1% de 1649 (V15: 43.1%).

## PRIMARIA (todas las entradas, costo REAL 6A, 1 tick en stops)
exp(A)=-0.044R (n=248) vs exp(B+C)=-0.010R (n=225); dif=-0.035R, IC95 dif [-0.29,+0.21] -> NO se confirma A > B+C
{'n': 507, 'win': 0.389, 'exp_net': -0.048, 'ic95': '[-0.17,+0.07]', 'exp_bruta': 0.049, 'costo_R': 0.098, 'avg_win': 1.649, 'avg_loss': -1.127, 'veredicto': 'IC cruza 0'}

### sensibilidad slippage 0 tick(s): {'n': 507, 'win': 0.389, 'exp_net': -0.003, 'ic95': '[-0.12,+0.11]', 'exp_bruta': 0.049, 'costo_R': 0.052, 'avg_win': 1.649, 'avg_loss': -1.053, 'veredicto': 'IC cruza 0'}
### sensibilidad slippage 2 tick(s): {'n': 507, 'win': 0.389, 'exp_net': -0.094, 'ic95': '[-0.22,+0.03]', 'exp_bruta': 0.049, 'costo_R': 0.143, 'avg_win': 1.649, 'avg_loss': -1.201, 'veredicto': 'IC cruza 0'}

## Con costo del modelo viejo (referencia)
exp(A)=-0.159R (n=248) vs exp(B+C)=-0.142R (n=225); dif=-0.017R, IC95 dif [-0.26,+0.22] -> NO se confirma A > B+C
{'n': 507, 'win': 0.389, 'exp_net': -0.174, 'ic95': '[-0.29,-0.06]', 'exp_bruta': 0.049, 'costo_R': 0.223, 'avg_win': 1.48, 'avg_loss': -1.225, 'veredicto': 'IC<0'}

## 2026+ (costo real 1 tick) n=67
{'n': 67, 'win': 0.388, 'exp_net': -0.058, 'ic95': '[-0.39,+0.27]', 'exp_bruta': 0.048, 'costo_R': 0.106, 'avg_win': 1.644, 'avg_loss': -1.137, 'veredicto': 'IC cruza 0'}
## < 2026 (costo real 1 tick) n=440
{'n': 440, 'win': 0.389, 'exp_net': -0.047, 'ic95': '[-0.17,+0.08]', 'exp_bruta': 0.049, 'costo_R': 0.096, 'avg_win': 1.649, 'avg_loss': -1.125, 'veredicto': 'IC cruza 0'}

### por bucket (costo real 1 tick)
      n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
A   248  0.387  -0.044  [-0.21,+0.13]     0.045    0.09   1.653   -1.116  IC cruza 0
A0   34  0.294  -0.334  [-0.74,+0.09]    -0.206   0.128   1.623   -1.149  IC cruza 0
B   143  0.413   0.014  [-0.22,+0.24]     0.114     0.1   1.647   -1.133  IC cruza 0
C    82   0.39   -0.05  [-0.35,+0.26]     0.054   0.104   1.648   -1.137  IC cruza 0

### por confirm_type (costo real 1 tick)
          n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
3velas  229  0.389  -0.044  [-0.22,+0.14]     0.049   0.093   1.652   -1.122  IC cruza 0
ifvg    278  0.388  -0.052  [-0.21,+0.11]     0.049   0.101   1.646    -1.13  IC cruza 0

### por gate_tipo (costo real 1 tick)
               n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
dos_neutral  278  0.371  -0.095  [-0.26,+0.06]       0.0   0.096    1.65   -1.122  IC cruza 0
tres         229   0.41   0.008  [-0.17,+0.18]     0.108     0.1   1.647   -1.133  IC cruza 0

### por pm_rel (costo real 1 tick)
             n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
a_favor    121  0.421   0.045  [-0.19,+0.29]     0.138   0.093   1.649   -1.123  IC cruza 0
en_contra  126  0.429   0.063  [-0.17,+0.30]     0.157   0.094   1.645   -1.124  IC cruza 0
neutral    260  0.354  -0.146  [-0.31,+0.02]    -0.045   0.101    1.65    -1.13  IC cruza 0

### por trigger (costo real 1 tick)
                  n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
eq_extremo      196  0.398  -0.025  [-0.21,+0.17]     0.074     0.1   1.647   -1.131  IC cruza 0
eq_vwap         112  0.402  -0.009  [-0.26,+0.25]     0.085   0.094   1.653   -1.125  IC cruza 0
sweep_extremo   112  0.339  -0.185  [-0.41,+0.06]    -0.084   0.101   1.648   -1.126  IC cruza 0
sweep_interior   87  0.414   0.024  [-0.26,+0.31]     0.117   0.093   1.646   -1.121  IC cruza 0

### por candle_aligned (costo real 1 tick)
         n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
False  181  0.354  -0.143  [-0.33,+0.06]    -0.045   0.097   1.649   -1.122  IC cruza 0
True   326  0.408   0.004  [-0.14,+0.15]     0.102   0.098   1.649    -1.13  IC cruza 0

## Sensibilidad: solo riesgo <= $500 con 6 contratos n=312 de 507
{'n': 312, 'win': 0.385, 'exp_net': -0.084, 'ic95': '[-0.24,+0.07]', 'exp_bruta': 0.038, 'costo_R': 0.123, 'avg_win': 1.636, 'avg_loss': -1.159, 'veredicto': 'IC cruza 0'}
      n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   130    0.4  -0.038  [-0.27,+0.20]      0.08   0.118   1.639   -1.155         IC cruza 0
A0   28  0.357  -0.173  [-0.67,+0.33]    -0.036   0.137   1.623   -1.171  inconcluso (n<30)
B    91  0.363  -0.149  [-0.42,+0.13]    -0.021   0.129   1.631   -1.162         IC cruza 0
C    63  0.397  -0.046  [-0.36,+0.31]     0.071   0.117   1.641   -1.155         IC cruza 0

## Por año (costo real 1 tick)
       n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
2020  36  0.417   0.036  [-0.41,+0.50]     0.125   0.089   1.657   -1.122  IC cruza 0
2021  74  0.405  -0.002  [-0.30,+0.30]     0.095   0.097   1.652    -1.13  IC cruza 0
2022  91  0.374  -0.073  [-0.35,+0.20]     0.009   0.082   1.655   -1.103  IC cruza 0
2023  77  0.325   -0.22  [-0.50,+0.07]    -0.123   0.097   1.652    -1.12  IC cruza 0
2024  77  0.351  -0.167  [-0.46,+0.14]    -0.053   0.113    1.64   -1.142  IC cruza 0
2025  85  0.471   0.172  [-0.12,+0.47]     0.271   0.099   1.645   -1.137  IC cruza 0
2026  67  0.388  -0.058  [-0.39,+0.27]     0.048   0.106   1.644   -1.137  IC cruza 0