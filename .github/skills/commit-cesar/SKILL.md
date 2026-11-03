---
name: commit-cesar
description: Hace commits chicos a nombre de César, sin co-autor, y sube con pull --rebase. Usar al guardar cambios en git.
---
1. `git status` y revisa qué entra; no incluyas `data/` ni archivos grandes.
2. Un commit por cambio lógico, mensaje corto en español, en imperativo.
3. NO agregues `Co-Authored-By` ni ningún trailer de asistente.
4. `git pull --rebase origin main` y luego `git push`.
5. Si hay conflicto, para y explica; no hagas force push sin permiso.
