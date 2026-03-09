# Skill: implementator

## Proposito
Ejecutar planes tecnicos aprobados con cambios acotados, por fases y con verificacion.

## Entrada esperada
- Ruta de plan en `.context/active/plans/`.

## Flujo minimo
1. Leer plan completo y archivos objetivo.
2. Implementar una fase a la vez.
3. Ejecutar verificacion automatizada por fase.
4. Registrar resultado y continuar.

## Reglas
- No romper comandos CLI existentes sin actualizar tests y README.
- Preferir `pathlib.Path` para portabilidad.
- Reportar resultados de pruebas o limitaciones de ejecucion.
- Evitar refactors no relacionados con la fase en curso.
