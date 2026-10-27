# V13 — 2026-10-26
> Resultado EXPLORATORIO (ADR-007): primera prueba de una regla derivada del análisis, NO una validación definitiva. Estructura sobre proxy spot AUD/USD, no el futuro real 6A (ADR-006). Una hipótesis predefinida => sin Deflated Sharpe; ajustar parámetros tras ver esto activa el control de tests múltiples (6.2).

**235 ops** → evidencia preliminar, no concluyente (100-999 ops, ADR-009). Días con bias 'alta': 30.6% de 1304 (V12: 9%).

## Primaria A>B+C
exp(A)=+0.058R (n=112) vs exp(B+C)=-0.236R (n=106); dif=+0.293R, IC95 dif [-0.06,+0.63] -> NO se confirma A > B+C

## Global
{'n': 235, 'win': 0.438, 'exp_net': -0.095, 'ic95': '[-0.26,+0.08]', 'exp_bruta': 0.147, 'costo_R': 0.242, 'avg_win': 1.381, 'avg_loss': -1.247, 'veredicto': 'IC cruza 0'}

## TODO n=235
{'n': 235, 'win': 0.438, 'exp_net': -0.095, 'ic95': '[-0.26,+0.07]', 'exp_bruta': 0.147, 'costo_R': 0.242, 'avg_win': 1.381, 'avg_loss': -1.247, 'veredicto': 'IC cruza 0'}
      n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   112  0.491   0.058  [-0.18,+0.29]     0.283   0.225   1.387   -1.224         IC cruza 0
A0   17  0.412  -0.226  [-0.83,+0.40]     0.071   0.297     1.3   -1.294  inconcluso (n<30)
B    61  0.393   -0.21  [-0.53,+0.11]     0.033   0.243    1.38   -1.242         IC cruza 0
C    45  0.378   -0.27  [-0.64,+0.12]    -0.009   0.261   1.397   -1.282         IC cruza 0
                 n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
eq_extremo     108  0.481   0.014  [-0.23,+0.26]     0.259   0.245    1.37   -1.246  IC cruza 0
eq_vwap         69   0.42  -0.143  [-0.45,+0.16]       0.1   0.243   1.386   -1.251  IC cruza 0
sweep_extremo   58  0.379  -0.241  [-0.57,+0.09]    -0.006   0.235   1.401   -1.244  IC cruza 0
         n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
False   61  0.508   0.094  [-0.23,+0.43]     0.329   0.236   1.391   -1.247  IC cruza 0
True   174  0.414  -0.161  [-0.35,+0.03]     0.083   0.244   1.377   -1.247  IC cruza 0

## SIN 2024 (calibración) n=187
{'n': 187, 'win': 0.471, 'exp_net': 0.002, 'ic95': '[-0.18,+0.20]', 'exp_bruta': 0.232, 'costo_R': 0.23, 'avg_win': 1.39, 'avg_loss': -1.232, 'veredicto': 'IC cruza 0'}
     n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   95  0.526    0.16  [-0.09,+0.42]     0.375   0.215   1.395   -1.212         IC cruza 0
A0  14  0.357  -0.365  [-0.97,+0.29]    -0.071   0.293     1.3   -1.289  inconcluso (n<30)
B   43  0.395  -0.196  [-0.57,+0.18]     0.042   0.238   1.384   -1.228         IC cruza 0
C   35  0.457  -0.037  [-0.44,+0.41]       0.2   0.237   1.411   -1.256         IC cruza 0
                n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
eq_extremo     86    0.5   0.071  [-0.21,+0.35]     0.308   0.237   1.378   -1.235  IC cruza 0
eq_vwap        55  0.473   0.012  [-0.34,+0.35]     0.238   0.226   1.398   -1.231  IC cruza 0
sweep_extremo  46  0.413  -0.139  [-0.50,+0.25]     0.084   0.222   1.408   -1.227  IC cruza 0
         n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
False   49  0.571   0.275  [-0.10,+0.65]     0.495    0.22   1.399   -1.223  IC cruza 0
True   138  0.435  -0.095  [-0.31,+0.12]     0.139   0.234   1.386   -1.234  IC cruza 0

## Por año
       n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
2020  17  0.353  -0.321  [-0.93,+0.30]    -0.071   0.251   1.382   -1.251  inconcluso (n<30)
2021  43  0.465   -0.01  [-0.39,+0.37]      0.22    0.23    1.38   -1.218         IC cruza 0
2022  54  0.426  -0.079  [-0.42,+0.28]     0.116   0.195    1.44   -1.206         IC cruza 0
2023  42  0.476  -0.003  [-0.40,+0.39]      0.24   0.243    1.39    -1.27         IC cruza 0
2024  48  0.312  -0.474  [-0.81,-0.13]    -0.185   0.288   1.328   -1.292               IC<0
2025  31  0.613   0.344  [-0.10,+0.78]     0.606   0.262   1.343   -1.238         IC cruza 0