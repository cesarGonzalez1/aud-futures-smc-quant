# V14 — 2026-10-28
> Resultado EXPLORATORIO (ADR-007): primera prueba de una regla derivada del análisis, NO una validación definitiva. Estructura sobre proxy spot AUD/USD, no el futuro real 6A (ADR-006). Una hipótesis predefinida => sin Deflated Sharpe; ajustar parámetros tras ver esto activa el control de tests múltiples (6.2).

**192 ops** (dev 170, limpia 2026+ 22). Días con puerta abierta: 19.2% de 1649.

## PRIMARIA (limpia, entrada >= 2026-01-01) n=22 → muestra insuficiente para cualquier conclusión (<100 ops, ADR-009)
exp(A)=+0.035R (n=10) vs exp(B+C)=-0.756R (n=10); dif=+0.791R, IC95 dif [-0.29,+1.86] -> NO se confirma A > B+C
{'n': 22, 'win': 0.364, 'exp_net': -0.328, 'ic95': '[-0.84,+0.20]', 'exp_bruta': -0.05, 'costo_R': 0.278, 'avg_win': 1.358, 'avg_loss': -1.292, 'veredicto': 'inconcluso (n<30)'}
### por bucket
     n   win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   10   0.5   0.035  [-0.80,+0.86]       0.3   0.265   1.393   -1.323  inconcluso (n<30)
A0   2   0.5  -0.007  [-1.26,+1.25]       0.3   0.307   1.248   -1.261  inconcluso (n<30)
B    8  0.25  -0.634  [-1.31,+0.31]    -0.337   0.296   1.324   -1.286  inconcluso (n<30)
C    2   0.0  -1.246  [-1.34,-1.15]      -1.0   0.246     NaN   -1.246  inconcluso (n<30)

### por pm_rel
            n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
a_favor     3  0.667   0.427  [-1.37,+1.34]     0.733   0.306   1.326    -1.37  inconcluso (n<30)
en_contra   9  0.444  -0.087  [-0.96,+0.79]     0.167   0.253   1.367   -1.249  inconcluso (n<30)
neutral    10    0.2  -0.773  [-1.33,+0.02]     -0.48   0.293   1.371   -1.309  inconcluso (n<30)

### por trigger
                n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
eq_extremo     10    0.6   0.302  [-0.49,+1.08]      0.57   0.268   1.343    -1.26  inconcluso (n<30)
eq_vwap         5    0.2  -0.774  [-1.42,+0.36]     -0.48   0.294   1.494   -1.341  inconcluso (n<30)
sweep_extremo   7  0.143  -0.911  [-1.38,-0.14]    -0.629   0.283   1.309   -1.281  inconcluso (n<30)

### por candle_aligned
        n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
False   3  0.333  -0.445  [-1.32,+1.25]    -0.133   0.312   1.248   -1.292  inconcluso (n<30)
True   19  0.368   -0.31  [-0.88,+0.27]    -0.037   0.273   1.373   -1.292  inconcluso (n<30)


## DESCRIPTIVA (dev, < 2026) n=170 — V13 ya vio estos datos; no es prueba
{'n': 170, 'win': 0.441, 'exp_net': -0.084, 'ic95': '[-0.28,+0.12]', 'exp_bruta': 0.155, 'costo_R': 0.239, 'avg_win': 1.381, 'avg_loss': -1.241, 'veredicto': 'IC cruza 0'}
### por bucket
     n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
A   83  0.494   0.079  [-0.21,+0.36]     0.291   0.212   1.396   -1.208         IC cruza 0
A0   9  0.444  -0.213  [-1.06,+0.65]     0.156   0.368   1.218   -1.357  inconcluso (n<30)
B   40  0.425  -0.132  [-0.52,+0.28]     0.115   0.247   1.362   -1.237         IC cruza 0
C   38  0.342  -0.358  [-0.77,+0.06]      -0.1   0.258    1.41   -1.278         IC cruza 0

### por pm_rel
            n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss   veredicto
a_favor    31  0.484   0.041  [-0.40,+0.48]      0.27   0.229   1.404   -1.237  IC cruza 0
en_contra  44  0.409  -0.182  [-0.54,+0.20]      0.07   0.252    1.32   -1.221  IC cruza 0
neutral    95  0.442   -0.08  [-0.34,+0.18]     0.157   0.236     1.4   -1.252  IC cruza 0

## Por año
       n    win exp_net           ic95 exp_bruta costo_R avg_win avg_loss          veredicto
2020  13  0.462  -0.027  [-0.69,+0.72]     0.215   0.242    1.39   -1.241  inconcluso (n<30)
2021  27  0.444  -0.065  [-0.54,+0.42]     0.162   0.227   1.375   -1.217  inconcluso (n<30)
2022  38  0.421  -0.095  [-0.51,+0.32]     0.107   0.202   1.432   -1.206         IC cruza 0
2023  28  0.464  -0.036  [-0.52,+0.46]     0.211   0.247   1.399    -1.28  inconcluso (n<30)
2024  34  0.353  -0.356  [-0.75,+0.05]    -0.082   0.274   1.339   -1.281         IC cruza 0
2025  30  0.533   0.152  [-0.30,+0.61]       0.4   0.248   1.349   -1.217         IC cruza 0
2026  22  0.364  -0.328  [-0.84,+0.19]     -0.05   0.278   1.358   -1.292  inconcluso (n<30)