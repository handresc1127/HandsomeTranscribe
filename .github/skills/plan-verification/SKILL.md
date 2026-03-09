# Skill: plan-verification

## Proposito
Validar que un plan sea claro, viable y verificable antes de ejecutar implementacion.

## Entrada esperada
- Ruta de plan en `.context/active/plans/`.

## Flujo minimo
1. Leer plan completo.
2. Verificar estructura minima (fases, testing, rollback, cierre).
3. Validar coherencia tecnica con `.context/project/*`.
4. Emitir decision: APPROVED | APPROVED_WITH_NOTES | CHANGES_REQUIRED.

## Verificaciones
- Coherencia con arquitectura y constraints.
- Cobertura minima de pruebas definida.
- Riesgo y rollback contemplados.
- Fases con entregables y criterios observables.

## Salida
- Reporte de verificacion en `.context/active/plans/verification-{plan-file-name}.md`.
