---
plan_id: 2026-01-28-backup-automatico-post-arqueo
title: "Backup Automático Después de Cada Arqueo de Caja"
created: 2026-01-28
status: ready-for-implementation
estimated_effort: 1-2 horas
---

# Plan: Backup Automático Post-Arqueo

## Objetivo

Agregar parámetro `force=True` al decorador `@auto_backup()` para forzar backup en cada arqueo.

## Cambios Requeridos

### 1. Modificar utils/backup.py ✅

Agregar parámetro `force=False` al decorador existente:

```python
def auto_backup(force=False):
    """Decorador para backup automático.
    
    Args:
        force: Si True, crea backup siempre. Si False, solo cada 7 días.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if force or should_backup():
                backup_path = create_backup()
                if backup_path:
                    current_app.logger.info(f"Backup creado: {backup_path}")
            return f(*args, **kwargs)
        return wrapped
    return decorator
```

### 2. Modificar routes/cash_register.py ✅

Agregar decorador a `new()`:

```python
from utils.backup import auto_backup

@cash_register_bp.route('/new', methods=['GET', 'POST'])
@login_required
@auto_backup(force=True)  # Backup en cada arqueo
def new():
```

## Archivos a Modificar

1. ✅ `utils/backup.py` - Agregar parámetro `force=False`
2. ✅ `routes/cash_register.py` - Agregar `@auto_backup(force=True)` a `new()`

## Criterios de Éxito

- [x] Cada arqueo genera backup `app_backup_YYYYMMDD_HHMMSS.db`
- [x] Rutas existentes con `@auto_backup()` siguen funcionando (cada 7 días)
- [x] Log muestra creación de backup

## Estimación

- **Tiempo**: 1-2 horas
- **Líneas modificadas**: ~10
- **Riesgo**: Bajo (cambio mínimo, backward compatible)

