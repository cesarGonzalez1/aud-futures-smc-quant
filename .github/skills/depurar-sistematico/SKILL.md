---
name: depurar-sistematico
description: Método para encontrar la causa de un error o resultado raro en cualquier código. Usar cuando algo falla o los números no cuadran.
---
1. Reproduce el problema con el comando exacto y guarda el mensaje completo.
2. Reduce: encuentra el caso más chico que falla.
3. Formula 2-3 hipótesis y verifica cada una con un dato o una prueba, no con intuición.
4. Cambia UNA cosa a la vez. Si algo no se pudo verificar, dilo.
5. Al arreglar, agrega un test que falle antes y pase después.
6. Explica la causa real en 2 líneas.
