# Skill: plan-verification

## Proposito
Refinar planes de implementacion mediante dialogo interactivo con el usuario, editando directamente el plan hasta que sea ejecutable y completo.

## Entrada esperada
- Ruta de plan en `.context/active/plans/`.

## Flujo minimo
1. Leer plan y contexto base (architecture, patterns, conventions, constraints).
2. Identificar areas que necesitan refinamiento (objetivos, fases, testing, rollback, riesgos).
3. Priorizar gaps por criticidad.
4. Para cada gap:
   - Hacer pregunta tecnica especifica al usuario.
   - Esperar respuesta.
   - Actualizar el plan directamente con la informacion.
   - Confirmar actualizacion brevemente.
5. Validar consistencia tecnica (rutas, CLI, convenciones).
6. Cuando plan este completo, pedir confirmacion final al usuario.
7. Si usuario aprueba, sugerir handoff a `implementator`.

## Reglas
- Siempre editar el plan original, nunca crear reportes separados.
- Una pregunta y edicion por respuesta del usuario.
- Preguntas concretas y tecnicas, evitar genericas.
- No inventar informacion: si falta, preguntar.
- Preservar formato markdown y estructura del plan.
- Agregar evidencia concreta: rutas, lineas, comandos.
- No aprobar hasta confirmacion explicita del usuario.

## Salida
- Plan actualizado con mejoras basadas en feedback del usuario.
- Confirmacion final cuando plan listo para `implementator`.
