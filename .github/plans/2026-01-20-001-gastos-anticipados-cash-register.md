---
plan_id: 2026-01-20-001
date: 2026-01-20
author: GitHub Copilot
task: N/A
status: draft
last_updated: 2026-01-20
last_updated_by: GitHub Copilot
---

# Plan de Implementación: Sistema de Gastos Anticipados en Cash Register

**Plan ID**: 2026-01-20-001  
**Fecha**: 2026-01-20  
**Autor**: GitHub Copilot  
**Tarea**: N/A

## Resumen General

El módulo de Cash Register actualmente requiere crear el arqueo ANTES de registrar gastos debido a que `Expense.cash_register_id` es una Foreign Key NOT NULL. Esta restricción causa problemas de UX cuando se pagan gastos durante el día pero el arqueo se realiza al cierre, generando descuadres temporales hasta agregar los gastos manualmente.

**Mejora propuesta**: Permitir registrar gastos durante el día sin necesidad de crear el arqueo, con asociación automática al momento de crear el arqueo.

**Cambios principales**:
1. Hacer `Expense.cash_register_id` nullable para permitir gastos sin arqueo
2. Agregar campo `payee` (beneficiario) al modelo Expense
3. Crear ruta para registrar gastos sin arqueo durante el día
4. Asociar automáticamente gastos huérfanos al crear arqueo
5. Mostrar fila especial en tabla de arqueos para días sin arqueo pero con gastos
6. Vista dedicada para ver/gestionar gastos del día sin arqueo

## Análisis del Estado Actual

### Modelo Expense (models/models.py:700-733)

**Restricción Crítica**:
```python
cash_register_id = db.Column(db.Integer, db.ForeignKey('cash_register.id'), nullable=False)
```

Este `nullable=False` impide registrar gastos sin arqueo existente.

**Campos Existentes**:
- `id`: Primary key
- `cash_register_id`: FK a CashRegister (NOT NULL - problema)
- `description`: String(200), descripción del gasto
- `amount`: Float, monto
- `category`: String(50), categoría ('local', 'proveedores', 'nomina', 'consumibles', 'varios')
- `payment_method`: String(20), método ('cash', 'transfer')
- `created_at`: DateTime, timestamp
- `created_by`: Integer, FK a User

**Campo Faltante Solicitado**:
- `payee`: String(150), nullable - Beneficiario del pago (ej: "EPM", "Juan Pérez", "Proveedor Italcol")

### Flujo Actual (routes/cash_register.py)

**Cronología Forzada**:
1. Usuario crea arqueo (`POST /cash-register/new`)
2. Usuario agrega gastos uno por uno (`POST /cash-register/<id>/add-expense`)
3. Cada gasto recalcula totales del arqueo

**Problema Real**:
```
10:00 - Usuario paga luz $40,000 ❌ No puede registrar (no hay arqueo)
18:00 - Crea arqueo → diferencia: -$40,000 (FALTANTE)
18:05 - Agrega gasto → diferencia: $0 (CUADRADO)
```

### Vista de Arqueos (templates/cash_register/list.html)

**Limitación Actual**:
- Solo muestra arqueos existentes
- Si no hay arqueo del día → no aparece fila
- No hay forma de ver gastos del día sin arqueo

## Estado Final Deseado

### Cronología Mejorada

```
10:00 - Usuario registra gasto "Luz $40,000" (efectivo, beneficiario: "EPM")
      ✅ Se guarda con cash_register_id = NULL
      
14:00 - Usuario registra gasto "Shampoo $30,000" (efectivo, beneficiario: "Proveedor Italcol")
      ✅ Se guarda con cash_register_id = NULL

18:00 - Usuario crea arqueo del día
      ✅ Sistema detecta 2 gastos huérfanos del día ($70,000 total)
      ✅ Los asocia automáticamente al arqueo recién creado
      ✅ Recalcula totales: expected = base + ventas - $70,000
      ✅ Diferencia correcta desde el inicio
```

### Gastos Huérfanos de Días Anteriores

**Escenario**:
```
20/01 10:00 - Gasto "Luz $40k" registrado (sin arqueo)
20/01 18:00 - Usuario NO crea arqueo del 20/01
21/01 18:00 - Usuario crea arqueo del 21/01
```

**Comportamiento Deseado**:
- Al crear arqueo del 21/01, sistema detecta gasto huérfano del 20/01
- Lo asocia automáticamente al arqueo del 21/01
- Logging: "Gasto del 20/01 asociado a arqueo del 21/01"
- Permite recuperar gastos no asociados

### Vista de Arqueos Mejorada

**Tabla con Fila Especial**:
```
| Fecha      | Usuario | Base | Efectivo | Contado | Gastos  | Diferencia | Estado          | Acciones                    |
|------------|---------|------|----------|---------|---------|------------|-----------------|----------------------------|
| 20/01/2026 | -       | -    | -        | -       | $70,000 | -          | Arqueo Pendiente| [Ver Gastos] [Crear Arqueo]|
| 19/01/2026 | admin   | 200k | 500k     | 680k    | 50k     | -70k       | Faltante        | [Ver] [Editar]             |
```

**Botón "Ver Gastos"**: Abre vista `/cash-register/daily-expenses` con tabla de gastos del día

### Verificación

**Éxito Completo Cuando**:
1. Usuario puede registrar gastos durante el día sin arqueo
2. Gastos se asocian automáticamente al crear arqueo
3. Tabla de arqueos muestra fila especial para día sin arqueo con gastos
4. Campo `payee` visible en formulario y vista de gastos
5. Vendedor puede registrar gastos del día actual sin arqueo
6. Vendedor NO puede editar gastos de días anteriores sin arqueo
7. Gastos huérfanos de días anteriores se asocian al siguiente arqueo futuro

## Lo Que NO Vamos a Hacer

1. **NO** permitir editar/eliminar gastos sin arqueo de días anteriores (solo del día actual)
2. **NO** crear selector manual de gastos al crear arqueo (asociación automática únicamente)
3. **NO** modificar la lógica de cálculo de cuadre existente (`calculate_totals`)
4. **NO** cambiar permisos de admin (siguen teniendo acceso total)
5. **NO** permitir gastos sin categoría (sigue siendo obligatoria)
6. **NO** crear reportes/análisis de gastos (se hará posteriormente)
7. **NO** migrar gastos existentes (todos tienen cash_register_id válido)

## Enfoque de Implementación

### Estrategia General

**Patrón de Asociación Automática**:
- Gastos sin `cash_register_id` se consideran "huérfanos"
- Al crear arqueo, se buscan gastos huérfanos del día
- Si existen gastos huérfanos de días anteriores, se asocian al primer arqueo futuro
- Logging completo de asociaciones para trazabilidad

**Compatibilidad Hacia Atrás**:
- Gastos existentes (con `cash_register_id`) NO se modifican
- Queries deben manejar ambos casos: gastos con y sin arqueo
- Template `view.html` sigue funcionando para arqueos existentes

**Permisos y Seguridad**:
- Vendedor: Solo gastos del día actual sin arqueo
- Admin: Cualquier fecha
- Validación en backend de permisos

### Patrones a Seguir

- **Repository Pattern**: Queries complejas en funciones auxiliares
- **Observer Pattern**: Recálculo automático al asociar gastos
- **State Pattern**: Estados de gasto (con/sin arqueo)
- **Transacciones**: `db.session` con try-except y rollback
- **Logging**: `app.logger.info()` para asociaciones automáticas
- **AJAX**: Fetch API para agregar gastos sin recargar página
---

## Fase 1: Cambios en Base de Datos y Modelo

### Resumen General
Modificar el modelo `Expense` para permitir gastos sin arqueo y agregar campo de beneficiario. Esta es la base fundamental para todas las demás fases.

### Cambios Requeridos

#### 1. Modificar Modelo Expense (models/models.py)
**Archivo**: `models/models.py:700-733`
**Cambios**: Hacer FK nullable y agregar campo payee

```python
class Expense(db.Model):
    """Gastos del día asociados a un arqueo de caja.
    
    Puede existir sin arqueo (cash_register_id NULL) para gastos registrados
    durante el día antes de crear el arqueo.
    
    Categorías:
    - local: Servicios públicos, arrendamiento
    - proveedores: Compra de productos para venta
    - nomina: Salarios, groomer, ayudantes
    - consumibles: Bolsas, shampoos, insumos
    - varios: Otros gastos
    """
    __tablename__ = 'expense'
    
    id = db.Column(db.Integer, primary_key=True)
    # CAMBIO: Hacer nullable para permitir gastos sin arqueo
    cash_register_id = db.Column(db.Integer, db.ForeignKey('cash_register.id'), nullable=True)
    
    # Datos del gasto
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='varios')
    # Valores: 'local', 'proveedores', 'nomina', 'consumibles', 'varios'
    payment_method = db.Column(db.String(20), nullable=False, default='cash')
    # Valores: 'cash' (efectivo), 'transfer' (transferencia)
    
    # NUEVO: Beneficiario del pago
    payee = db.Column(db.String(150), nullable=True)
    # Ejemplos: "EPM", "Juan Pérez (groomer)", "Proveedor Italcol"
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relación
    user = db.relationship('User')
    
    def __repr__(self):
        arqueo_info = f'Arqueo {self.cash_register_id}' if self.cash_register_id else 'Sin arqueo'
        payee_info = f' → {self.payee}' if self.payee else ''
        return f'<Expense {self.category}: {self.description}{payee_info} - ${self.amount:,.0f} ({arqueo_info})>'
    
    def is_orphan(self):
        """Verifica si el gasto está sin asociar a un arqueo."""
        return self.cash_register_id is None
    
    @staticmethod
    def get_orphan_expenses_for_date(date):
        """Obtiene gastos huérfanos de una fecha específica.
        
        Args:
            date: datetime.date - Fecha objetivo
            
        Returns:
            List[Expense] - Gastos sin cash_register_id del día
        """
        from zoneinfo import ZoneInfo
        CO_TZ = ZoneInfo("America/Bogota")
        
        start_datetime = datetime.combine(date, datetime.min.time()).replace(tzinfo=CO_TZ)
        end_datetime = datetime.combine(date, datetime.max.time()).replace(tzinfo=CO_TZ)
        start_utc = start_datetime.astimezone(timezone.utc)
        end_utc = end_datetime.astimezone(timezone.utc)
        
        return Expense.query.filter(
            Expense.cash_register_id.is_(None),
            Expense.created_at >= start_utc,
            Expense.created_at <= end_utc
        ).order_by(Expense.created_at).all()
    
    @staticmethod
    def get_all_orphan_expenses():
        """Obtiene TODOS los gastos huérfanos (sin arqueo).
        
        Returns:
            List[Expense] - Gastos sin cash_register_id ordenados por fecha
        """
        return Expense.query.filter(
            Expense.cash_register_id.is_(None)
        ).order_by(Expense.created_at).all()
```

**Justificación**:
- `cash_register_id nullable=True`: Permite crear gastos sin arqueo
- `payee` opcional: Mejora trazabilidad sin ser obligatorio
- Método `is_orphan()`: Claridad en queries
- Método estático `get_orphan_expenses_for_date()`: Reutilizable en múltiples rutas
- Método estático `get_all_orphan_expenses()`: Para vista de admin

#### 2. Script de Migración SQL
**Archivo**: `migrations/migration_add_payee_nullable_cash_register.sql`
**Cambios**: ALTER TABLE para modificar columnas

```sql
-- migration_add_payee_nullable_cash_register.sql
-- Fecha: 2026-01-20
-- Propósito: Hacer cash_register_id nullable y agregar campo payee

-- 1. Hacer cash_register_id nullable
ALTER TABLE expense 
ALTER COLUMN cash_register_id DROP NOT NULL;

-- 2. Agregar campo payee
ALTER TABLE expense 
ADD COLUMN payee VARCHAR(150);

-- 3. Crear índice para mejorar queries de gastos huérfanos
CREATE INDEX idx_expense_cash_register_null 
ON expense(created_at) 
WHERE cash_register_id IS NULL;

-- 4. Comentarios para documentación
COMMENT ON COLUMN expense.cash_register_id IS 'FK a cash_register. NULL permite gastos sin arqueo (registrados durante el día)';
COMMENT ON COLUMN expense.payee IS 'Beneficiario del pago. Opcional. Ejemplos: EPM, Juan Pérez, Proveedor Italcol';
```

**Justificación**:
- `ALTER COLUMN DROP NOT NULL`: Permite gastos huérfanos
- Índice parcial: Optimiza búsqueda de gastos sin arqueo
- Comentarios SQL: Documentación en base de datos

#### 3. Script de Migración Python (con Backup)
**Archivo**: `migrations/migration_add_payee_nullable_cash_register.py`
**Cambios**: Script ejecutable con backup automático

```python
#!/usr/bin/env python
"""
Migración: Gastos Anticipados - Cash Register
Fecha: 2026-01-20

Cambios:
1. Hacer Expense.cash_register_id nullable
2. Agregar campo Expense.payee (String 150, nullable)
3. Crear índice para gastos huérfanos

IMPORTANTE: Usar Path(__file__).parent para path resolution
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import shutil
import sys

# Path resolution (NUNCA usar rutas relativas simples)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / 'instance' / 'app.db'
SQL_FILE = SCRIPT_DIR / 'migration_add_payee_nullable_cash_register.sql'

def create_backup():
    """Crea backup de la base de datos con timestamp."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = DB_PATH.parent / f'app.backup_{timestamp}'
    
    print(f"[INFO] Creando backup: {backup_path}")
    shutil.copy2(DB_PATH, backup_path)
    print(f"[OK] Backup creado exitosamente")
    
    return backup_path

def verify_database_exists():
    """Verifica que la base de datos exista."""
    if not DB_PATH.exists():
        print(f"[ERROR] Base de datos no encontrada: {DB_PATH}")
        sys.exit(1)
    
    print(f"[OK] Base de datos encontrada: {DB_PATH}")

def verify_sql_file_exists():
    """Verifica que el archivo SQL exista."""
    if not SQL_FILE.exists():
        print(f"[WARNING] Archivo SQL no encontrado: {SQL_FILE}")
        print(f"[INFO] Ejecutando migracion con SQL inline")
        return False
    
    print(f"[OK] Archivo SQL encontrado: {SQL_FILE}")
    return True

def run_migration_from_sql():
    """Ejecuta migración desde archivo SQL."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        with open(SQL_FILE, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        # SQLite no soporta múltiples statements con executescript en transacción
        # Ejecutar statement por statement
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        for statement in statements:
            if statement:
                print(f"[INFO] Ejecutando: {statement[:50]}...")
                cursor.execute(statement)
        
        conn.commit()
        print("[OK] Migracion desde SQL completada")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error en migracion SQL: {e}")
        raise
    finally:
        conn.close()

def run_migration_inline():
    """Ejecuta migración con SQL inline (fallback)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 1. Hacer cash_register_id nullable
        # SQLite no soporta ALTER COLUMN DROP NOT NULL directamente
        # Necesitamos recrear la tabla
        
        print("[INFO] Paso 1: Recreando tabla expense con cash_register_id nullable")
        
        # Crear tabla temporal
        cursor.execute("""
            CREATE TABLE expense_new (
                id INTEGER PRIMARY KEY,
                cash_register_id INTEGER,
                description VARCHAR(200) NOT NULL,
                amount REAL NOT NULL,
                category VARCHAR(50) NOT NULL DEFAULT 'varios',
                payment_method VARCHAR(20) NOT NULL DEFAULT 'cash',
                payee VARCHAR(150),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                FOREIGN KEY (cash_register_id) REFERENCES cash_register(id),
                FOREIGN KEY (created_by) REFERENCES user(id)
            )
        """)
        
        # Copiar datos
        cursor.execute("""
            INSERT INTO expense_new 
                (id, cash_register_id, description, amount, category, payment_method, created_at, created_by)
            SELECT id, cash_register_id, description, amount, category, payment_method, created_at, created_by
            FROM expense
        """)
        
        # Eliminar tabla original
        cursor.execute("DROP TABLE expense")
        
        # Renombrar tabla nueva
        cursor.execute("ALTER TABLE expense_new RENAME TO expense")
        
        print("[OK] Tabla expense recreada con cambios")
        
        # 2. Crear índice para gastos huérfanos
        print("[INFO] Paso 2: Creando indice para gastos huerfanos")
        cursor.execute("""
            CREATE INDEX idx_expense_cash_register_null 
            ON expense(created_at) 
            WHERE cash_register_id IS NULL
        """)
        print("[OK] Indice creado")
        
        conn.commit()
        print("[OK] Migracion inline completada exitosamente")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error en migracion inline: {e}")
        raise
    finally:
        conn.close()

def verify_migration():
    """Verifica que la migración se aplicó correctamente."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Verificar estructura de tabla
        cursor.execute("PRAGMA table_info(expense)")
        columns = {row[1]: row for row in cursor.fetchall()}
        
        # Verificar cash_register_id nullable
        if 'cash_register_id' in columns:
            is_nullable = columns['cash_register_id'][3] == 0  # notnull column
            if is_nullable:
                print("[OK] cash_register_id es nullable")
            else:
                print("[WARNING] cash_register_id NO es nullable")
        
        # Verificar campo payee existe
        if 'payee' in columns:
            print("[OK] Campo payee existe")
        else:
            print("[ERROR] Campo payee NO existe")
        
        # Verificar índice
        cursor.execute("PRAGMA index_list(expense)")
        indexes = [row[1] for row in cursor.fetchall()]
        
        if 'idx_expense_cash_register_null' in indexes:
            print("[OK] Indice idx_expense_cash_register_null existe")
        else:
            print("[WARNING] Indice NO encontrado")
        
        # Contar gastos existentes
        cursor.execute("SELECT COUNT(*) FROM expense")
        count = cursor.fetchone()[0]
        print(f"[INFO] Total de gastos existentes: {count}")
        
        # Verificar gastos huérfanos (debe ser 0 si es primera migración)
        cursor.execute("SELECT COUNT(*) FROM expense WHERE cash_register_id IS NULL")
        orphan_count = cursor.fetchone()[0]
        print(f"[INFO] Gastos huerfanos: {orphan_count}")
        
    except Exception as e:
        print(f"[ERROR] Error verificando migracion: {e}")
    finally:
        conn.close()

def main():
    """Ejecuta la migración completa."""
    print("="*60)
    print("MIGRACION: Gastos Anticipados - Cash Register")
    print("="*60)
    
    # 1. Verificar base de datos
    verify_database_exists()
    
    # 2. Crear backup
    backup_path = create_backup()
    
    # 3. Ejecutar migración
    try:
        if verify_sql_file_exists():
            run_migration_from_sql()
        else:
            run_migration_inline()
        
        # 4. Verificar migración
        print("\n" + "="*60)
        print("VERIFICACION DE MIGRACION")
        print("="*60)
        verify_migration()
        
        print("\n" + "="*60)
        print("[OK] MIGRACION COMPLETADA EXITOSAMENTE")
        print(f"[INFO] Backup disponible en: {backup_path}")
        print("="*60)
        
    except Exception as e:
        print("\n" + "="*60)
        print("[ERROR] MIGRACION FALLIDA")
        print(f"[ERROR] {e}")
        print(f"[INFO] Restaurar desde backup: {backup_path}")
        print("="*60)
        sys.exit(1)

if __name__ == '__main__':
    main()
```

**Justificación**:
- Path resolution con `Path(__file__).parent`: Funciona desde cualquier CWD
- Backup automático: Seguridad antes de modificar
- Recrear tabla: SQLite no soporta ALTER COLUMN DROP NOT NULL
- Verificación post-migración: Confirma éxito
- Fallback SQL inline: Si archivo .sql no existe

### Criterios de Éxito

#### Verificación Automatizada:
- [x] Migración ejecuta sin errores: `python migrations/migration_add_payee_nullable_cash_register.py`
- [x] Backup se crea automáticamente en `instance/`
- [x] Tabla `expense` tiene columna `payee` (VARCHAR 150, nullable)
- [x] Tabla `expense` permite `cash_register_id` NULL
- [x] Índice `idx_expense_cash_register_null` existe
- [x] Aplicación inicia sin errores: `python app.py`
- [x] No hay errores de import del modelo Expense

#### Verificación Manual:
- [ ] Query funciona: `SELECT * FROM expense WHERE cash_register_id IS NULL`
- [ ] Se puede insertar gasto sin cash_register_id:
  ```sql
  INSERT INTO expense (description, amount, category, payment_method, payee, created_by)
  VALUES ('Prueba', 10000, 'varios', 'cash', 'Test Beneficiario', 1);
  ```
- [ ] Modelo Expense importa correctamente en Python shell
- [ ] Métodos `is_orphan()` y `get_orphan_expenses_for_date()` funcionan
- [ ] No hay regresiones en gastos existentes (todos tienen cash_register_id)

**Nota de Implementación**: Después de completar esta fase y que toda la verificación pase, pausar para confirmación antes de proceder a Fase 2.

---

## Fase 2: Lógica de Asociación Automática de Gastos

### Resumen General
Modificar la ruta `cash_register.new()` para detectar y asociar automáticamente gastos huérfanos al crear un arqueo. Incluye lógica para gastos del mismo día y de días anteriores.

### Cambios Requeridos

#### 1. Función Auxiliar de Asociación (routes/cash_register.py)
**Archivo**: `routes/cash_register.py` (después de las funciones get_total_*)
**Cambios**: Agregar función para asociar gastos huérfanos

```python
def associate_orphan_expenses_to_register(cash_register):
    """Asocia gastos huérfanos al arqueo.
    
    Lógica:
    1. Busca gastos huérfanos del mismo día del arqueo
    2. Busca gastos huérfanos de días ANTERIORES (no futuros)
    3. Los asocia al arqueo proporcionado
    4. Registra logging de asociaciones
    
    Args:
        cash_register: Instancia de CashRegister a la que asociar gastos
        
    Returns:
        dict: Estadísticas de asociación
            - 'same_day': Cantidad de gastos del mismo día
            - 'previous_days': Cantidad de gastos de días anteriores
            - 'total': Total de gastos asociados
            - 'total_amount': Suma de montos asociados
    """
    from models.models import Expense
    
    # 1. Gastos del mismo día
    same_day_expenses = Expense.get_orphan_expenses_for_date(cash_register.date)
    
    # 2. Gastos de días ANTERIORES (no futuros)
    all_orphans = Expense.get_all_orphan_expenses()
    previous_days_expenses = [
        exp for exp in all_orphans 
        if exp.created_at.date() < cash_register.date
    ]
    
    # Combinar gastos a asociar
    expenses_to_associate = same_day_expenses + previous_days_expenses
    
    if not expenses_to_associate:
        return {
            'same_day': 0,
            'previous_days': 0,
            'total': 0,
            'total_amount': 0.0
        }
    
    # Asociar gastos
    total_amount = 0.0
    for expense in expenses_to_associate:
        expense.cash_register_id = cash_register.id
        total_amount += expense.amount
        
        # Logging para trazabilidad
        if expense.created_at.date() == cash_register.date:
            current_app.logger.info(
                f"Gasto del mismo dia asociado: {expense.description} "
                f"(${expense.amount:,.0f}) a arqueo {cash_register.id}"
            )
        else:
            current_app.logger.warning(
                f"Gasto huerfano del {expense.created_at.date()} asociado a arqueo del "
                f"{cash_register.date}: {expense.description} (${expense.amount:,.0f})"
            )
    
    return {
        'same_day': len(same_day_expenses),
        'previous_days': len(previous_days_expenses),
        'total': len(expenses_to_associate),
        'total_amount': total_amount
    }
```

**Justificación**:
- Separa lógica de asociación en función reutilizable
- Logging completo para auditoría
- Retorna estadísticas para mostrar al usuario
- Solo asocia gastos de días anteriores o mismo día (no futuros)

#### 2. Modificar Ruta new() para Asociar Gastos (routes/cash_register.py)
**Archivo**: `routes/cash_register.py:52-125` (método new)
**Cambios**: Agregar asociación antes de calculate_totals

```python
@cash_register_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Crear nuevo arqueo de caja.
    
    Admin: Puede crear de cualquier fecha
    Vendedor: Solo del día actual
    
    NUEVO: Asocia automáticamente gastos huérfanos del día y días anteriores
    """
    today = datetime.now(CO_TZ).date()
    
    # Determinar fecha objetivo
    if current_user.role == 'admin':
        # Admin puede especificar fecha (si se implementa selector en template)
        date_str = request.form.get('date') if request.method == 'POST' else None
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = today
        else:
            target_date = today
    else:
        # Vendedor solo día actual
        target_date = today
    
    if request.method == 'POST':
        try:
            # Capturar denominaciones
            arqueo = CashRegister(
                date=target_date,
                user_id=current_user.id,
                bills_100000=int(request.form.get('bills_100000', 0)),
                bills_50000=int(request.form.get('bills_50000', 0)),
                bills_20000=int(request.form.get('bills_20000', 0)),
                bills_10000=int(request.form.get('bills_10000', 0)),
                bills_5000=int(request.form.get('bills_5000', 0)),
                bills_2000=int(request.form.get('bills_2000', 0)),
                notes=request.form.get('notes', '')
            )
            
            # Monedas opcionales para todos
            arqueo.coins_1000 = int(request.form.get('coins_1000', 0))
            arqueo.coins_500 = int(request.form.get('coins_500', 0))
            arqueo.coins_200 = int(request.form.get('coins_200', 0))
            arqueo.coins_100 = int(request.form.get('coins_100', 0))
            arqueo.coins_50 = int(request.form.get('coins_50', 0))
            
            # Calcular base del día anterior
            arqueo.base_caja = CashRegister.get_base_from_previous_day(target_date)
            
            # Obtener totales del sistema
            arqueo.total_cash_system = get_total_cash_for_date(target_date)
            arqueo.total_transfer_system = get_total_transfer_for_date(target_date)
            
            # NUEVO: Guardar arqueo para obtener ID
            db.session.add(arqueo)
            db.session.flush()  # Obtener ID sin commit
            
            # NUEVO: Asociar gastos huérfanos automáticamente
            association_stats = associate_orphan_expenses_to_register(arqueo)
            
            # Calcular totales y diferencia (ahora incluye gastos asociados)
            arqueo.calculate_totals()
            
            db.session.commit()
            
            # Flash messages informativos
            if association_stats['total'] > 0:
                flash(
                    f"Arqueo guardado. Se asociaron {association_stats['total']} gasto(s) "
                    f"por ${association_stats['total_amount']:,.0f}",
                    'info'
                )
                
                if association_stats['previous_days'] > 0:
                    flash(
                        f"Se incluyeron {association_stats['previous_days']} gasto(s) de días anteriores",
                        'warning'
                    )
            else:
                flash('Arqueo de caja guardado exitosamente', 'success')
            
            # Alerta si diferencia > $10,000 (después de incluir gastos)
            if abs(arqueo.difference) > 10000:
                if arqueo.difference > 0:
                    flash(f'Sobrante detectado: ${arqueo.difference:,.0f}', 'warning')
                else:
                    flash(f'Faltante detectado: ${abs(arqueo.difference):,.0f}', 'danger')
            
            return redirect(url_for('cash_register.view', id=arqueo.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creando arqueo: {e}")
            flash(f'Error al guardar arqueo: {str(e)}', 'danger')
    
    # GET - Cargar datos del día
    total_cash_system = get_total_cash_for_date(target_date)
    total_transfer_system = get_total_transfer_for_date(target_date)
    base_caja = CashRegister.get_base_from_previous_day(target_date)
    
    # NUEVO: Contar gastos huérfanos que se asociarán
    from models.models import Expense
    orphan_expenses = Expense.get_orphan_expenses_for_date(target_date)
    orphan_total = sum(exp.amount for exp in orphan_expenses) if orphan_expenses else 0.0
    
    show_coins = True
    
    return render_template('cash_register/form.html',
                         total_cash_system=total_cash_system,
                         total_transfer_system=total_transfer_system,
                         base_caja=base_caja,
                         show_coins=show_coins,
                         is_edit=False,
                         target_date=target_date,
                         orphan_expenses_count=len(orphan_expenses),
                         orphan_expenses_total=orphan_total)
```

**Justificación**:
- `db.session.flush()`: Obtiene ID del arqueo sin commit (permite rollback si falla asociación)
- Asociación ANTES de `calculate_totals()`: Incluye gastos en el cálculo
- Flash messages informativos: Usuario ve cuántos gastos se asociaron
- GET carga preview de gastos huérfanos: Usuario sabe qué esperar

#### 3. Actualizar Template form.html con Preview de Gastos
**Archivo**: `templates/cash_register/form.html`
**Cambios**: Agregar card informativa de gastos huérfanos (después de Sección 1 - Totales del Sistema)

```html
<!-- SECCIÓN 1: Totales del Sistema -->
<div class="card mb-4">
    <div class="card-header bg-info text-white">
        <h5 class="mb-0"><i class="bi bi-graph-up"></i> Ventas del Día (Sistema)</h5>
    </div>
    <div class="card-body">
        <!-- ... código existente de totales ... -->
    </div>
</div>

<!-- NUEVO: Preview de Gastos Huérfanos -->
{% if orphan_expenses_count > 0 and not is_edit %}
<div class="alert alert-info mb-4">
    <h6 class="alert-heading">
        <i class="bi bi-info-circle"></i> Gastos Registrados del Día
    </h6>
    <p class="mb-0">
        Se detectaron <strong>{{ orphan_expenses_count }}</strong> gasto(s) ya registrado(s) 
        por un total de <strong>${{ '{:,.0f}'.format(orphan_expenses_total) }}</strong>.
        <br>
        Estos gastos se asociarán automáticamente al arqueo al guardar.
    </p>
    <hr>
    <p class="mb-0 small text-muted">
        <i class="bi bi-lightbulb"></i> 
        Los gastos ya están incluidos en el cálculo del cuadre esperado.
    </p>
</div>
{% endif %}

<!-- SECCIÓN 2: Conteo de Billetes -->
<div class="card mb-4">
    <!-- ... código existente ... -->
</div>
```

**Justificación**:
- Usuario ve preview antes de guardar
- Transparencia en asociación automática
- Solo se muestra en creación (no en edición)

### Criterios de Éxito

#### Verificación Automatizada:
- [x] Función `associate_orphan_expenses_to_register()` existe y se puede importar
- [x] Ruta `new()` ejecuta sin errores después de modificación
- [x] Template `form.html` renderiza sin errores con nuevas variables
- [x] Aplicación inicia: `python app.py`

#### Verificación Manual:
- [ ] **Caso 1 - Gastos del mismo día**:
  1. Registrar gasto sin arqueo (usar Fase 3 o SQL directo)
  2. Crear arqueo del mismo día
  3. Verificar que gasto se asoció automáticamente
  4. Flash message muestra "Se asociaron 1 gasto(s)"
  5. Cuadre incluye el gasto en `total_expenses`

- [ ] **Caso 2 - Gastos de días anteriores**:
  1. Tener gasto huérfano del 19/01
  2. Crear arqueo del 20/01
  3. Verificar que gasto del 19/01 se asoció al arqueo del 20/01
  4. Flash message warning: "Se incluyeron gastos de días anteriores"
  5. Logging muestra: "Gasto huerfano del 19/01 asociado a arqueo del 20/01"

- [ ] **Caso 3 - Sin gastos huérfanos**:
  1. Crear arqueo sin gastos registrados previamente
  2. Flash message: "Arqueo guardado exitosamente" (sin mencionar gastos)
  3. `total_expenses = 0`

- [ ] **Caso 4 - Preview en formulario**:
  1. Tener 2 gastos huérfanos del día ($30k + $40k)
  2. Abrir formulario de nuevo arqueo (GET)
  3. Ver alert azul: "Se detectaron 2 gasto(s) por $70,000"
  4. Guardar arqueo
  5. Verificar que ambos gastos se asociaron

- [ ] **Caso 5 - Rollback en error**:
  1. Forzar error después de asociación (ej: campo inválido)
  2. Verificar que gastos NO se asociaron (siguen huérfanos)
  3. Transacción completa se revirtió

- [ ] Logging contiene entradas de asociación con descripción y monto
- [ ] No hay regresiones en arqueos sin gastos huérfanos

**Nota de Implementación**: Esta fase depende de Fase 1 (modelo modificado). Después de verificación completa, pausar antes de Fase 3.

---

## Fase 3: Registro de Gastos Sin Arqueo (Backend)

### Resumen General
Crear ruta nueva para permitir registrar gastos durante el día sin necesidad de tener un arqueo existente. Incluye validaciones de permisos (vendedor solo día actual) y campo payee.

### Cambios Requeridos

#### 1. Nueva Ruta add_daily_expense (routes/cash_register.py)
**Archivo**: `routes/cash_register.py` (agregar después de delete_expense)
**Cambios**: Nueva ruta para gastos sin arqueo

```python
@cash_register_bp.route('/add-daily-expense', methods=['POST'])
@login_required
def add_daily_expense():
    """Agregar gasto del día sin arqueo - JSON response.
    
    Permisos:
    - Vendedor: Solo puede agregar gastos del día actual
    - Admin: Puede agregar gastos de cualquier fecha
    
    NUEVO: No requiere cash_register_id, incluye campo payee
    """
    # Capturar datos del gasto
    description = request.form.get('description', '').strip()
    amount_str = request.form.get('amount', '0')
    category = request.form.get('category', 'varios')
    payment_method = request.form.get('payment_method', 'cash')
    payee = request.form.get('payee', '').strip() or None  # Opcional
    
    # Admin puede especificar fecha, vendedor solo día actual
    if current_user.role == 'admin':
        date_str = request.form.get('date')
        if date_str:
            try:
                expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                expense_date = datetime.now(CO_TZ).date()
        else:
            expense_date = datetime.now(CO_TZ).date()
    else:
        # Vendedor: forzar día actual
        expense_date = datetime.now(CO_TZ).date()
    
    # Validaciones
    if not description:
        return jsonify({'error': 'La descripción es obligatoria'}), 400
    
    try:
        amount = float(amount_str)
    except ValueError:
        return jsonify({'error': 'Monto inválido'}), 400
    
    if amount <= 0:
        return jsonify({'error': 'El monto debe ser mayor a cero'}), 400
    
    # Validar categoría
    valid_categories = ['local', 'proveedores', 'nomina', 'consumibles', 'varios']
    if category not in valid_categories:
        return jsonify({'error': f'Categoría inválida. Debe ser: {", ".join(valid_categories)}'}), 400
    
    # Validar método de pago
    valid_payment_methods = ['cash', 'transfer']
    if payment_method not in valid_payment_methods:
        return jsonify({'error': 'Método de pago inválido'}), 400
    
    # Validar longitud de payee
    if payee and len(payee) > 150:
        return jsonify({'error': 'El beneficiario no puede exceder 150 caracteres'}), 400
    
    try:
        expense = Expense(
            cash_register_id=None,  # SIN ARQUEO - será asociado al crear arqueo
            description=description,
            amount=amount,
            category=category,
            payment_method=payment_method,
            payee=payee,
            created_by=current_user.id
        )
        
        # Ajustar created_at si admin especificó fecha diferente
        if current_user.role == 'admin' and expense_date != datetime.now(CO_TZ).date():
            # Crear timestamp para la fecha especificada a la hora actual
            expense.created_at = datetime.combine(
                expense_date, 
                datetime.now(CO_TZ).time()
            ).astimezone(timezone.utc)
        
        db.session.add(expense)
        db.session.commit()
        
        current_app.logger.info(
            f"Gasto sin arqueo registrado: {description} - ${amount:,.0f} "
            f"por {current_user.username} (fecha: {expense_date})"
        )
        
        return jsonify({
            'success': True,
            'expense': {
                'id': expense.id,
                'description': expense.description,
                'amount': expense.amount,
                'category': expense.category,
                'payment_method': expense.payment_method,
                'payee': expense.payee,
                'created_at': expense.created_at.strftime('%H:%M')
            },
            'message': 'Gasto registrado. Se asociará al arqueo automáticamente.'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error agregando gasto sin arqueo: {e}")
        return jsonify({'error': str(e)}), 500
```

**Justificación**:
- `cash_register_id=None`: Permite gastos huérfanos
- Validación de permisos: Vendedor solo día actual
- Admin puede especificar fecha (útil para corregir olvidos)
- Validación completa de datos incluyendo payee
- Logging para auditoría
- Respuesta JSON para AJAX

#### 2. Nueva Ruta delete_daily_expense (routes/cash_register.py)
**Archivo**: `routes/cash_register.py` (agregar después de add_daily_expense)
**Cambios**: Eliminar gastos sin arqueo con permisos

```python
@cash_register_bp.route('/daily-expense/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_daily_expense(expense_id):
    """Eliminar gasto sin arqueo (huérfano).
    
    Permisos:
    - Vendedor: Solo puede eliminar gastos del día actual que creó
    - Admin: Puede eliminar cualquier gasto huérfano
    """
    expense = Expense.query.get_or_404(expense_id)
    
    # Verificar que sea gasto huérfano
    if expense.cash_register_id is not None:
        flash('No se puede eliminar. Este gasto ya está asociado a un arqueo.', 'warning')
        return redirect(url_for('cash_register.daily_expenses'))
    
    # Validación de permisos para vendedor
    if current_user.role == 'vendedor':
        today = datetime.now(CO_TZ).date()
        expense_date = expense.created_at.date()
        
        # Solo puede eliminar sus gastos del día actual
        if expense_date != today:
            flash('Acceso denegado. Solo puede eliminar gastos del día actual.', 'danger')
            return redirect(url_for('cash_register.daily_expenses'))
        
        if expense.created_by != current_user.id:
            flash('Acceso denegado. Solo puede eliminar sus propios gastos.', 'danger')
            return redirect(url_for('cash_register.daily_expenses'))
    
    try:
        description = expense.description
        amount = expense.amount
        
        db.session.delete(expense)
        db.session.commit()
        
        current_app.logger.info(
            f"Gasto sin arqueo eliminado: {description} - ${amount:,.0f} "
            f"por {current_user.username}"
        )
        
        flash('Gasto eliminado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error eliminando gasto sin arqueo: {e}")
        flash(f'Error al eliminar gasto: {str(e)}', 'danger')
    
    return redirect(url_for('cash_register.daily_expenses'))
```

**Justificación**:
- Verificación de gasto huérfano: Solo se pueden eliminar gastos sin arqueo
- Permisos vendedor: Solo día actual y propios gastos
- Admin: Acceso total a gastos huérfanos
- Logging de eliminación
- Redirect a vista de gastos diarios

#### 3. Modificar Ruta add_expense Existente para Incluir payee
**Archivo**: `routes/cash_register.py:220-293` (método add_expense)
**Cambios**: Agregar campo payee a gasto con arqueo

```python
@cash_register_bp.route('/<int:id>/add-expense', methods=['POST'])
@login_required
def add_expense(id):
    """Agregar gasto al arqueo (uno a uno) - JSON response."""
    arqueo = CashRegister.query.get_or_404(id)
    
    # VALIDACIÓN: Solo arqueos editables
    if not arqueo.can_edit():
        return jsonify({'error': 'No se pueden agregar gastos a arqueos antiguos'}), 403
    
    # PERMISO: Vendedor solo en su arqueo
    if current_user.role == 'vendedor' and arqueo.user_id != current_user.id:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    # Capturar datos del gasto
    description = request.form.get('description', '').strip()
    amount_str = request.form.get('amount', '0')
    category = request.form.get('category', 'varios')
    payment_method = request.form.get('payment_method', 'cash')
    payee = request.form.get('payee', '').strip() or None  # NUEVO: Campo opcional
    
    # Validaciones
    if not description:
        return jsonify({'error': 'La descripción es obligatoria'}), 400
    
    try:
        amount = float(amount_str)
    except ValueError:
        return jsonify({'error': 'Monto inválido'}), 400
    
    if amount <= 0:
        return jsonify({'error': 'El monto debe ser mayor a cero'}), 400
    
    # Validar categoría
    valid_categories = ['local', 'proveedores', 'nomina', 'consumibles', 'varios']
    if category not in valid_categories:
        return jsonify({'error': f'Categoría inválida. Debe ser: {", ".join(valid_categories)}'}), 400
    
    # Validar método de pago
    valid_payment_methods = ['cash', 'transfer']
    if payment_method not in valid_payment_methods:
        return jsonify({'error': 'Método de pago inválido'}), 400
    
    # NUEVO: Validar longitud de payee
    if payee and len(payee) > 150:
        return jsonify({'error': 'El beneficiario no puede exceder 150 caracteres'}), 400
    
    try:
        expense = Expense(
            cash_register_id=arqueo.id,
            description=description,
            amount=amount,
            category=category,
            payment_method=payment_method,
            payee=payee,  # NUEVO
            created_by=current_user.id
        )
        db.session.add(expense)
        
        # Recalcular totales del arqueo
        arqueo.calculate_totals()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'expense': {
                'id': expense.id,
                'description': expense.description,
                'amount': expense.amount,
                'category': expense.category,
                'payee': expense.payee,  # NUEVO
                'created_at': expense.created_at.strftime('%H:%M')
            },
            'total_expenses': arqueo.total_expenses,
            'difference': arqueo.difference
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error agregando gasto: {e}")
        return jsonify({'error': str(e)}), 500
```

**Justificación**:
- Compatibilidad con modal existente (agregar campo payee)
- Validación de longitud de payee
- Retorna payee en respuesta JSON para mostrar en tabla

### Criterios de Éxito

#### Verificación Automatizada:
- [x] Rutas `add_daily_expense` y `delete_daily_expense` existen
- [x] Aplicación inicia sin errores: `python app.py`
- [x] Ruta modificada `add_expense` incluye campo payee
- [x] No hay errores de sintaxis Python

#### Verificación Manual:

**Caso 1 - Agregar Gasto Sin Arqueo (Vendedor)**:
- [ ] Vendedor registra gasto del día actual sin arqueo
- [ ] Request POST a `/cash-register/add-daily-expense`:
  ```json
  {
    "description": "Pago luz",
    "amount": "40000",
    "category": "local",
    "payment_method": "cash",
    "payee": "EPM"
  }
  ```
- [ ] Respuesta JSON exitosa con expense.id
- [ ] Query verifica: `cash_register_id IS NULL`
- [ ] Query verifica: `payee = 'EPM'`
- [ ] Logging registra: "Gasto sin arqueo registrado"

**Caso 2 - Vendedor Intenta Fecha Pasada**:
- [ ] Vendedor intenta especificar fecha 19/01/2026
- [ ] Sistema ignora fecha y usa día actual (20/01/2026)
- [ ] Gasto se crea con fecha de hoy

**Caso 3 - Admin Registra Gasto Retroactivo**:
- [ ] Admin registra gasto con fecha 19/01/2026
- [ ] Sistema permite fecha especificada
- [ ] `expense.created_at` corresponde al 19/01

**Caso 4 - Validación de Payee**:
- [ ] Payee con 151 caracteres → Error: "no puede exceder 150 caracteres"
- [ ] Payee vacío ("") → Se guarda como NULL
- [ ] Payee "EPM" → Se guarda correctamente

**Caso 5 - Eliminar Gasto Sin Arqueo**:
- [ ] Vendedor elimina gasto del día actual que creó → Éxito
- [ ] Vendedor intenta eliminar gasto de ayer → Error: "Solo puede eliminar gastos del día actual"
- [ ] Vendedor intenta eliminar gasto de otro usuario → Error: "Solo puede eliminar sus propios gastos"
- [ ] Admin elimina cualquier gasto huérfano → Éxito

**Caso 6 - No Eliminar Gasto con Arqueo**:
- [ ] Gasto ya asociado a arqueo
- [ ] Intentar DELETE a `/cash-register/daily-expense/<id>/delete`
- [ ] Flash: "No se puede eliminar. Este gasto ya está asociado a un arqueo"
- [ ] Redirect a vista de gastos diarios

**Caso 7 - Agregar Gasto a Arqueo Existente con Payee**:
- [ ] Abrir modal en vista de arqueo
- [ ] Agregar gasto con payee "Proveedor Italcol"
- [ ] Gasto se guarda con payee
- [ ] Respuesta JSON incluye campo payee
- [ ] Tabla se actualiza mostrando payee

- [ ] Validaciones de categoría y método de pago funcionan
- [ ] Logging contiene todas las acciones
- [ ] No hay regresiones en ruta add_expense existente

**Nota de Implementación**: Esta fase depende de Fase 1 (modelo con payee y cash_register_id nullable). Después de verificación completa, pausar antes de Fase 4.

---

## Fase 4: Vista de Gastos del Día Sin Arqueo (Frontend)

### Resumen General
Crear vista dedicada para ver y gestionar gastos del día actual sin necesidad de tener un arqueo creado. Incluye tabla de gastos, modal para agregar y funcionalidad AJAX.

### Cambios Requeridos

#### 1. Nueva Ruta daily_expenses (routes/cash_register.py)
**Archivo**: `routes/cash_register.py` (agregar después de list)
**Cambios**: Vista de gastos del día sin arqueo

```python
@cash_register_bp.route('/daily-expenses')
@login_required
def daily_expenses():
    """Vista de gastos del día actual sin arqueo.
    
    Muestra gastos huérfanos del día y permite agregar/eliminar.
    
    Admin: Puede ver gastos de cualquier día (con selector de fecha)
    Vendedor: Solo ve gastos del día actual
    """
    today = datetime.now(CO_TZ).date()
    
    # Determinar fecha objetivo
    if current_user.role == 'admin':
        date_str = request.args.get('date')
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = today
        else:
            target_date = today
    else:
        # Vendedor: forzar día actual
        target_date = today
    
    # Obtener gastos huérfanos del día
    orphan_expenses = Expense.get_orphan_expenses_for_date(target_date)
    
    # Calcular totales por método de pago
    total_cash = sum(exp.amount for exp in orphan_expenses if exp.payment_method == 'cash')
    total_transfer = sum(exp.amount for exp in orphan_expenses if exp.payment_method == 'transfer')
    total_general = sum(exp.amount for exp in orphan_expenses)
    
    # Verificar si existe arqueo del día
    existing_register = CashRegister.query.filter_by(date=target_date).first()
    
    # Totales del sistema (ventas)
    total_cash_system = get_total_cash_for_date(target_date)
    total_transfer_system = get_total_transfer_for_date(target_date)
    
    return render_template('cash_register/daily_expenses.html',
                         target_date=target_date,
                         expenses=orphan_expenses,
                         total_cash=total_cash,
                         total_transfer=total_transfer,
                         total_general=total_general,
                         existing_register=existing_register,
                         total_cash_system=total_cash_system,
                         total_transfer_system=total_transfer_system,
                         is_today=(target_date == today))
```

**Justificación**:
- Vendedor solo ve día actual
- Admin puede cambiar fecha con query param `?date=2026-01-19`
- Calcula totales por método de pago
- Detecta si ya existe arqueo del día
- Pasa totales del sistema para contexto

#### 2. Template daily_expenses.html
**Archivo**: `templates/cash_register/daily_expenses.html` (nuevo)
**Cambios**: Vista completa de gastos sin arqueo

```html
{% extends "layout.html" %}

{% block title %}Gastos del Día - {{ target_date.strftime('%d/%m/%Y') }}{% endblock %}

{% block content %}
<div class="container-fluid py-4">
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="{{ url_for('dashboard.index') }}">Inicio</a></li>
            {% if current_user.role == 'admin' %}
            <li class="breadcrumb-item"><a href="{{ url_for('cash_register.list') }}">Arqueos de Caja</a></li>
            {% endif %}
            <li class="breadcrumb-item active">Gastos del Día</li>
        </ol>
    </nav>
    
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>
            <i class="bi bi-cash-coin"></i> Gastos del Día - {{ target_date.strftime('%d/%m/%Y') }}
        </h2>
        <div>
            {% if existing_register %}
            <a href="{{ url_for('cash_register.view', id=existing_register.id) }}" 
               class="btn btn-info">
                <i class="bi bi-eye"></i> Ver Arqueo del Día
            </a>
            {% else %}
            <a href="{{ url_for('cash_register.new') }}" class="btn btn-success">
                <i class="bi bi-calculator"></i> Crear Arqueo
            </a>
            {% endif %}
            
            {% if current_user.role == 'admin' %}
            <a href="{{ url_for('cash_register.list') }}" class="btn btn-secondary">
                <i class="bi bi-arrow-left"></i> Volver
            </a>
            {% else %}
            <a href="{{ url_for('dashboard.index') }}" class="btn btn-secondary">
                <i class="bi bi-arrow-left"></i> Volver
            </a>
            {% endif %}
        </div>
    </div>
    
    <!-- Selector de Fecha (Solo Admin) -->
    {% if current_user.role == 'admin' %}
    <div class="card mb-4">
        <div class="card-body">
            <form method="GET" class="row g-3 align-items-end">
                <div class="col-auto">
                    <label for="date-select" class="form-label">Fecha:</label>
                    <input type="date" id="date-select" name="date" class="form-control" 
                           value="{{ target_date.strftime('%Y-%m-%d') }}">
                </div>
                <div class="col-auto">
                    <button type="submit" class="btn btn-primary">
                        <i class="bi bi-search"></i> Buscar
                    </button>
                </div>
            </form>
        </div>
    </div>
    {% endif %}
    
    <!-- Resumen de Totales -->
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card border-danger">
                <div class="card-body text-center">
                    <h6 class="text-muted">Gastos en Efectivo</h6>
                    <h3 class="text-danger">${{ '{:,.0f}'.format(total_cash) }}</h3>
                    <small class="text-muted">{{ expenses|selectattr('payment_method', 'equalto', 'cash')|list|length }} gasto(s)</small>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card border-warning">
                <div class="card-body text-center">
                    <h6 class="text-muted">Gastos en Transferencia</h6>
                    <h3 class="text-warning">${{ '{:,.0f}'.format(total_transfer) }}</h3>
                    <small class="text-muted">{{ expenses|selectattr('payment_method', 'equalto', 'transfer')|list|length }} gasto(s)</small>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card border-primary">
                <div class="card-body text-center">
                    <h6 class="text-muted">Total Gastos</h6>
                    <h3 class="text-primary">${{ '{:,.0f}'.format(total_general) }}</h3>
                    <small class="text-muted">{{ expenses|length }} gasto(s) total</small>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card border-success">
                <div class="card-body text-center">
                    <h6 class="text-muted">Ventas del Día</h6>
                    <h3 class="text-success">${{ '{:,.0f}'.format(total_cash_system + total_transfer_system) }}</h3>
                    <small class="text-muted">Efectivo: ${{ '{:,.0f}'.format(total_cash_system) }}</small>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Alert Informativo -->
    {% if not existing_register and expenses %}
    <div class="alert alert-info">
        <h6 class="alert-heading"><i class="bi bi-info-circle"></i> Gastos Pendientes de Asociar</h6>
        <p class="mb-0">
            Estos gastos se asociarán automáticamente al crear el arqueo del día.
            <br>
            <a href="{{ url_for('cash_register.new') }}" class="alert-link">Crear Arqueo Ahora</a>
        </p>
    </div>
    {% endif %}
    
    <!-- Tabla de Gastos -->
    <div class="card">
        <div class="card-header bg-danger text-white d-flex justify-content-between align-items-center">
            <h5 class="mb-0"><i class="bi bi-list-ul"></i> Gastos Registrados</h5>
            {% if is_today or current_user.role == 'admin' %}
            <button type="button" class="btn btn-sm btn-light" data-bs-toggle="modal" data-bs-target="#add-expense-modal">
                <i class="bi bi-plus-circle"></i> Agregar Gasto
            </button>
            {% endif %}
        </div>
        <div class="card-body">
            {% if expenses %}
            <div class="table-responsive">
                <table class="table table-hover align-middle" id="expenses-table">
                    <thead>
                        <tr>
                            <th>Hora</th>
                            <th>Descripción</th>
                            <th>Beneficiario</th>
                            <th>Categoría</th>
                            <th>Método</th>
                            <th class="text-end">Monto</th>
                            {% if is_today or current_user.role == 'admin' %}<th class="text-center">Acciones</th>{% endif %}
                        </tr>
                    </thead>
                    <tbody id="expenses-list">
                        {% for expense in expenses %}
                        <tr>
                            <td>{{ expense.created_at.strftime('%H:%M') }}</td>
                            <td>{{ expense.description }}</td>
                            <td>
                                {% if expense.payee %}
                                <span class="badge bg-secondary">{{ expense.payee }}</span>
                                {% else %}
                                <small class="text-muted">-</small>
                                {% endif %}
                            </td>
                            <td><span class="badge bg-info">{{ expense.category }}</span></td>
                            <td>
                                {% if expense.payment_method == 'cash' %}
                                <i class="bi bi-cash text-success"></i> Efectivo
                                {% else %}
                                <i class="bi bi-bank text-warning"></i> Transferencia
                                {% endif %}
                            </td>
                            <td class="text-end fw-bold">${{ '{:,.0f}'.format(expense.amount) }}</td>
                            {% if is_today or current_user.role == 'admin' %}
                            <td class="text-center">
                                <form method="POST" action="{{ url_for('cash_register.delete_daily_expense', expense_id=expense.id) }}" 
                                      onsubmit="return confirm('¿Eliminar este gasto?');" style="display: inline;">
                                    <button type="submit" class="btn btn-sm btn-outline-danger">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </form>
                            </td>
                            {% endif %}
                        </tr>
                        {% endfor %}
                    </tbody>
                    <tfoot>
                        <tr class="fw-bold">
                            <td colspan="5">Total General</td>
                            <td class="text-end text-danger">${{ '{:,.0f}'.format(total_general) }}</td>
                            {% if is_today or current_user.role == 'admin' %}<td></td>{% endif %}
                        </tr>
                    </tfoot>
                </table>
            </div>
            {% else %}
            <div class="text-center py-5">
                <i class="bi bi-inbox" style="font-size: 4rem; color: #ccc;"></i>
                <h5 class="mt-3 text-muted">No hay gastos registrados para este día</h5>
                {% if is_today or current_user.role == 'admin' %}
                <button type="button" class="btn btn-primary mt-3" data-bs-toggle="modal" data-bs-target="#add-expense-modal">
                    <i class="bi bi-plus-circle"></i> Registrar Primer Gasto
                </button>
                {% endif %}
            </div>
            {% endif %}
        </div>
    </div>
</div>

<!-- Modal para Agregar Gasto -->
{% if is_today or current_user.role == 'admin' %}
<div class="modal fade" id="add-expense-modal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Agregar Gasto del Día</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form id="add-expense-form">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="expense-description-input" class="form-label">
                            Descripción <span class="text-danger">*</span>
                        </label>
                        <input type="text" class="form-control" id="expense-description-input" 
                               name="description" required 
                               placeholder="Ej: Pago servicio de luz">
                    </div>
                    
                    <div class="mb-3">
                        <label for="expense-payee-input" class="form-label">
                            Beneficiario / A quién se pagó
                        </label>
                        <input type="text" class="form-control" id="expense-payee-input" 
                               name="payee" maxlength="150"
                               placeholder="Ej: EPM, Juan Pérez, Proveedor Italcol">
                        <small class="text-muted">Opcional - Máximo 150 caracteres</small>
                    </div>
                    
                    <div class="mb-3">
                        <label for="expense-amount-input" class="form-label">
                            Monto <span class="text-danger">*</span>
                        </label>
                        <input type="number" class="form-control" id="expense-amount-input" 
                               name="amount" min="1" step="1" required
                               placeholder="50000">
                    </div>
                    
                    <div class="mb-3">
                        <label for="expense-category-select" class="form-label">
                            Categoría <span class="text-danger">*</span>
                        </label>
                        <select class="form-select" id="expense-category-select" name="category" required>
                            <option value="local">Local (servicios públicos, arrendamiento)</option>
                            <option value="proveedores">Proveedores (compra de productos)</option>
                            <option value="nomina">Nómina (salarios, groomer)</option>
                            <option value="consumibles">Consumibles (bolsas, shampoos)</option>
                            <option value="varios">Varios</option>
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label for="expense-payment-method-select" class="form-label">
                            Método de Pago <span class="text-danger">*</span>
                        </label>
                        <select class="form-select" id="expense-payment-method-select" name="payment_method" required>
                            <option value="cash">Efectivo</option>
                            <option value="transfer">Transferencia</option>
                        </select>
                        <small class="text-muted">
                            <i class="bi bi-info-circle"></i> 
                            Solo gastos en efectivo afectan el cuadre de caja
                        </small>
                    </div>
                    
                    {% if current_user.role == 'admin' %}
                    <div class="mb-3">
                        <label for="expense-date-input" class="form-label">Fecha del Gasto</label>
                        <input type="date" class="form-control" id="expense-date-input" 
                               name="date" value="{{ target_date.strftime('%Y-%m-%d') }}">
                        <small class="text-muted">Solo admin puede modificar fecha</small>
                    </div>
                    {% endif %}
                    
                    <div id="expense-error-alert" class="alert alert-danger d-none"></div>
                    <div id="expense-success-alert" class="alert alert-success d-none"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                    <button type="submit" class="btn btn-primary" id="save-expense-btn">
                        <i class="bi bi-save"></i> Guardar Gasto
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
// Agregar gasto sin arqueo con AJAX
document.getElementById('add-expense-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    const errorAlert = document.getElementById('expense-error-alert');
    const successAlert = document.getElementById('expense-success-alert');
    const saveBtn = document.getElementById('save-expense-btn');
    
    // Limpiar alerts
    errorAlert.classList.add('d-none');
    successAlert.classList.add('d-none');
    saveBtn.disabled = true;
    
    fetch("{{ url_for('cash_register.add_daily_expense') }}", {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            successAlert.textContent = data.message || 'Gasto registrado exitosamente';
            successAlert.classList.remove('d-none');
            
            // Recargar página después de 1 segundo
            setTimeout(() => {
                location.reload();
            }, 1000);
        } else {
            errorAlert.textContent = data.error || 'Error al guardar gasto';
            errorAlert.classList.remove('d-none');
            saveBtn.disabled = false;
        }
    })
    .catch(error => {
        errorAlert.textContent = 'Error de conexión';
        errorAlert.classList.remove('d-none');
        saveBtn.disabled = false;
    });
});
</script>
{% endif %}
{% endblock %}
```

**Justificación**:
- Selector de fecha solo para admin
- Cards de resumen con totales por método
- Tabla completa con columna de beneficiario
- Modal reutilizable con campo payee
- AJAX para agregar sin recargar
- Alert informativo si hay gastos sin arqueo
- Botón para crear arqueo desde esta vista

### Criterios de Éxito

#### Verificación Automatizada:
- [x] Ruta `daily_expenses` existe y retorna 200
- [x] Template `daily_expenses.html` renderiza sin errores
- [x] Aplicación inicia: `python app.py`
- [x] No hay errores JavaScript en consola

#### Verificación Manual:

**Caso 1 - Vista con Gastos**:
- [ ] Navegar a `/cash-register/daily-expenses`
- [ ] Ver tabla con gastos del día
- [ ] Cards muestran totales correctos (efectivo, transferencia, total)
- [ ] Columna "Beneficiario" muestra badges cuando existe payee

**Caso 2 - Vista Sin Gastos**:
- [ ] Día sin gastos registrados
- [ ] Ver mensaje "No hay gastos registrados"
- [ ] Botón "Registrar Primer Gasto" visible

**Caso 3 - Agregar Gasto con Modal**:
- [ ] Click "Agregar Gasto"
- [ ] Modal se abre correctamente
- [ ] Llenar formulario:
  - Descripción: "Pago luz"
  - Beneficiario: "EPM"
  - Monto: 40000
  - Categoría: local
  - Método: cash
- [ ] Click "Guardar Gasto"
- [ ] Alert success: "Gasto registrado"
- [ ] Página recarga automáticamente (1 seg)
- [ ] Gasto aparece en tabla

**Caso 4 - Validación de Payee**:
- [ ] Payee con 151 caracteres → Error en modal
- [ ] Payee vacío → Se guarda sin problema (NULL)
- [ ] Payee "EPM" → Aparece en columna con badge

**Caso 5 - Vendedor Solo Ve Día Actual**:
- [ ] Login como vendedor
- [ ] Navegar a `/cash-register/daily-expenses`
- [ ] Ver solo gastos de hoy
- [ ] NO ver selector de fecha
- [ ] Intentar `?date=2026-01-19` → Sistema ignora, muestra hoy

**Caso 6 - Admin Cambia Fecha**:
- [ ] Login como admin
- [ ] Ver selector de fecha
- [ ] Cambiar a 19/01/2026
- [ ] Ver gastos del 19/01 (si existen)
- [ ] Puede agregar gastos con fecha 19/01

**Caso 7 - Eliminar Gasto**:
- [ ] Click botón eliminar en un gasto
- [ ] Confirmar en dialog
- [ ] Gasto se elimina
- [ ] Flash message: "Gasto eliminado exitosamente"
- [ ] Tabla se actualiza

**Caso 8 - Link a Crear Arqueo**:
- [ ] Si no existe arqueo del día, botón "Crear Arqueo" visible
- [ ] Click redirige a `/cash-register/new`
- [ ] Si existe arqueo, botón "Ver Arqueo del Día" redirige a vista

**Caso 9 - Responsive Design**:
- [ ] Vista funciona en móvil (cards en columna)
- [ ] Tabla con scroll horizontal si es necesario
- [ ] Modal se adapta al tamaño de pantalla

- [ ] JavaScript AJAX funciona correctamente
- [ ] No hay regresiones en otras vistas

**Nota de Implementación**: Esta fase depende de Fase 3 (rutas backend). Después de verificación completa, pausar antes de Fase 5.

---

## Fase 5: Fila Especial en Tabla de Arqueos

### Resumen General
Modificar la vista de lista de arqueos (`list.html`) para mostrar una fila especial cuando el día actual tiene gastos pero no tiene arqueo creado. La fila muestra datos parciales con estado "Arqueo Pendiente".

### Cambios Requeridos

#### 1. Modificar Ruta list() para Detectar Gastos del Día (routes/cash_register.py)
**Archivo**: `routes/cash_register.py:18-43` (método list)
**Cambios**: Agregar lógica para detectar gastos huérfanos del día actual

```python
@cash_register_bp.route('/')
@login_required
def list():
    """Lista arqueos históricos.
    
    Admin: Ve todos los arqueos
    Vendedor: Solo sus arqueos de los últimos 5 días
    
    NUEVO: Detecta gastos del día sin arqueo para mostrar fila especial
    """
    today = datetime.now(CO_TZ).date()
    
    if current_user.role == 'admin':
        # Admin ve todos los arqueos
        arqueos = CashRegister.query.order_by(CashRegister.date.desc()).all()
    else:
        # Vendedor: solo sus arqueos de últimos 5 días
        five_days_ago = today - timedelta(days=5)
        arqueos = CashRegister.query.filter(
            CashRegister.user_id == current_user.id,
            CashRegister.date >= five_days_ago
        ).order_by(CashRegister.date.desc()).all()
    
    # NUEVO: Verificar si existe arqueo del día actual
    today_register = CashRegister.query.filter_by(date=today).first()
    
    # NUEVO: Si no existe arqueo del día, verificar si hay gastos huérfanos
    daily_expenses_orphan = None
    if not today_register:
        orphan_expenses = Expense.get_orphan_expenses_for_date(today)
        if orphan_expenses:
            # Calcular totales de gastos huérfanos
            total_cash = sum(exp.amount for exp in orphan_expenses if exp.payment_method == 'cash')
            total_transfer = sum(exp.amount for exp in orphan_expenses if exp.payment_method == 'transfer')
            total_general = sum(exp.amount for exp in orphan_expenses)
            
            daily_expenses_orphan = {
                'date': today,
                'expenses_count': len(orphan_expenses),
                'total_cash': total_cash,
                'total_transfer': total_transfer,
                'total_expenses': total_general,
                'has_orphan_expenses': True
            }
    
    return render_template('cash_register/list.html', 
                         arqueos=arqueos,
                         daily_expenses_orphan=daily_expenses_orphan)
```

**Justificación**:
- Detecta si existe arqueo del día actual
- Si no existe pero hay gastos, crea objeto con totales
- Pasa a template para renderizar fila especial

#### 2. Modificar Template list.html para Fila Especial
**Archivo**: `templates/cash_register/list.html`
**Cambios**: Agregar fila especial al inicio de la tabla si hay gastos sin arqueo

```html
{% if arqueos or daily_expenses_orphan %}
<div class="card">
    <div class="card-body">
        <div class="table-responsive">
            <table class="table table-hover align-middle" id="arqueos-table">
                <thead>
                    <tr>
                        <th>Fecha</th>
                        <th>Usuario</th>
                        <th class="text-end">Base</th>
                        <th class="text-end">Efectivo Sistema</th>
                        <th class="text-end">Contado</th>
                        <th class="text-end">Gastos</th>
                        <th class="text-end">Diferencia</th>
                        <th>Estado</th>
                        <th class="text-center">Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- NUEVA FILA ESPECIAL: Gastos del día sin arqueo -->
                    {% if daily_expenses_orphan %}
                    <tr class="table-warning">
                        <td data-order="{{ daily_expenses_orphan.date.strftime('%Y-%m-%d') }}">
                            <strong>{{ daily_expenses_orphan.date.strftime('%d/%m/%Y') }}</strong>
                            <br>
                            <small class="text-muted">{{ daily_expenses_orphan.date.strftime('%A') }}</small>
                        </td>
                        <td class="text-muted">-</td>
                        <td class="text-end text-muted">-</td>
                        <td class="text-end text-muted">-</td>
                        <td class="text-end text-muted">-</td>
                        <td class="text-end text-danger fw-bold">
                            ${{ '{:,.0f}'.format(daily_expenses_orphan.total_expenses) }}
                            <br>
                            <small class="text-muted">{{ daily_expenses_orphan.expenses_count }} gasto(s)</small>
                        </td>
                        <td class="text-end text-muted">-</td>
                        <td>
                            <span class="badge bg-warning text-dark">
                                <i class="bi bi-clock"></i> Arqueo Pendiente
                            </span>
                        </td>
                        <td class="text-center">
                            <div class="btn-group btn-group-sm" role="group">
                                <a href="{{ url_for('cash_register.daily_expenses') }}" 
                                   class="btn btn-outline-info" title="Ver gastos del día">
                                    <i class="bi bi-eye"></i> Ver Gastos
                                </a>
                                <a href="{{ url_for('cash_register.new') }}" 
                                   class="btn btn-outline-success" title="Crear arqueo">
                                    <i class="bi bi-calculator"></i> Crear Arqueo
                                </a>
                            </div>
                        </td>
                    </tr>
                    {% endif %}
                    
                    <!-- Filas normales de arqueos existentes -->
                    {% for arqueo in arqueos %}
                    <tr>
                        <td data-order="{{ arqueo.date.strftime('%Y-%m-%d') }}">
                            <strong>{{ arqueo.date.strftime('%d/%m/%Y') }}</strong>
                            <br>
                            <small class="text-muted">{{ arqueo.date.strftime('%A') }}</small>
                        </td>
                        <td>
                            <i class="bi bi-person-circle"></i> {{ arqueo.user.username }}
                        </td>
                        <td class="text-end">${{ '{:,.0f}'.format(arqueo.base_caja) }}</td>
                        <td class="text-end text-success">${{ '{:,.0f}'.format(arqueo.total_cash_system) }}</td>
                        <td class="text-end fw-bold">${{ '{:,.0f}'.format(arqueo.total_cash_counted) }}</td>
                        <td class="text-end text-danger">${{ '{:,.0f}'.format(arqueo.total_expenses) }}</td>
                        <td class="text-end fw-bold {% if arqueo.difference > 0 %}text-success{% elif arqueo.difference < 0 %}text-danger{% else %}text-secondary{% endif %}">
                            ${{ '{:,.0f}'.format(arqueo.difference) }}
                        </td>
                        <td>
                            {% if arqueo.difference == 0 %}
                            <span class="badge bg-success">Cuadrado</span>
                            {% elif arqueo.difference > 0 %}
                            <span class="badge bg-warning">Sobrante</span>
                            {% else %}
                            <span class="badge bg-danger">Faltante</span>
                            {% endif %}
                            
                            {% if arqueo.can_edit() %}
                            <br><small class="text-muted">Editable</small>
                            {% endif %}
                        </td>
                        <td class="text-center">
                            <div class="btn-group btn-group-sm" role="group">
                                <a href="{{ url_for('cash_register.view', id=arqueo.id) }}" 
                                   class="btn btn-outline-primary" title="Ver detalle">
                                    <i class="bi bi-eye"></i>
                                </a>
                                {% if arqueo.can_edit() %}
                                <a href="{{ url_for('cash_register.edit', id=arqueo.id) }}" 
                                   class="btn btn-outline-warning" title="Editar">
                                    <i class="bi bi-pencil"></i>
                                </a>
                                {% endif %}
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
                <tfoot>
                    <tr class="fw-bold bg-light">
                        <td colspan="5" class="text-end">Totales:</td>
                        <td class="text-end text-danger">${{ '{:,.0f}'.format(arqueos|sum(attribute='total_expenses')) }}</td>
                        <td class="text-end {% if arqueos|sum(attribute='difference') > 0 %}text-success{% elif arqueos|sum(attribute='difference') < 0 %}text-danger{% else %}text-secondary{% endif %}">
                            ${{ '{:,.0f}'.format(arqueos|sum(attribute='difference')) }}
                        </td>
                        <td colspan="2"></td>
                    </tr>
                </tfoot>
            </table>
        </div>
    </div>
</div>
{% else %}
<!-- Estado Vacío existente -->
<!-- ... código sin cambios ... -->
{% endif %}
```

**Justificación**:
- Fila con clase `table-warning` para destacar
- Datos parciales con "-" en campos sin arqueo
- Badge "Arqueo Pendiente" con icono de reloj
- Dos botones: "Ver Gastos" (daily_expenses) y "Crear Arqueo" (new)
- Se inserta ANTES de las filas normales para visibilidad

### Criterios de Éxito

#### Verificación Automatizada:
- [x] Ruta `list()` ejecuta sin errores con modificación
- [x] Template `list.html` renderiza sin errores
- [x] Aplicación inicia: `python app.py`

#### Verificación Manual:

**Caso 1 - Día con Gastos Sin Arqueo**:
- [ ] Registrar 2 gastos del día sin crear arqueo
- [ ] Navegar a `/cash-register/`
- [ ] Ver fila especial de "Arqueo Pendiente" al inicio
- [ ] Fila tiene fondo amarillo claro (`table-warning`)
- [ ] Columna "Gastos" muestra total correcto
- [ ] Badge muestra "Arqueo Pendiente"
- [ ] Botón "Ver Gastos" redirige a `/cash-register/daily-expenses`
- [ ] Botón "Crear Arqueo" redirige a `/cash-register/new`

**Caso 2 - Día Sin Gastos y Sin Arqueo**:
- [ ] Día actual sin gastos y sin arqueo
- [ ] Navegar a `/cash-register/`
- [ ] NO ver fila especial
- [ ] Solo ver arqueos existentes (si los hay)

**Caso 3 - Día con Arqueo (Con o Sin Gastos)**:
- [ ] Crear arqueo del día
- [ ] Navegar a `/cash-register/`
- [ ] NO ver fila especial de "Arqueo Pendiente"
- [ ] Ver fila normal del arqueo del día

**Caso 4 - DataTables con Fila Especial**:
- [ ] Fila especial aparece al inicio
- [ ] Ordenamiento por fecha funciona (fila especial queda arriba)
- [ ] Búsqueda de DataTables ignora fila especial correctamente
- [ ] Paginación funciona sin problemas

**Caso 5 - Vendedor Solo Ve Día Actual**:
- [ ] Login como vendedor
- [ ] Si hay gastos del día sin arqueo, ve fila especial
- [ ] NO ve gastos de otros días sin arqueo

**Caso 6 - Totalizadores en Footer**:
- [ ] Footer de totales NO incluye fila especial
- [ ] Solo suma arqueos reales existentes

- [ ] Responsive: Fila especial se adapta en móvil
- [ ] No hay regresiones en tabla de arqueos

**Nota de Implementación**: Esta fase depende de Fase 4 (vista daily_expenses). Después de verificación completa, pausar antes de Fase 6.

---

## Fase 6: Actualizar Formularios y Vistas Existentes

### Resumen General
Actualizar el modal de gastos en `view.html` para incluir el campo `payee` y modificar la visualización de gastos para mostrar el beneficiario en una columna adicional.

### Cambios Requeridos

#### 1. Actualizar Modal de Gastos en view.html
**Archivo**: `templates/cash_register/view.html:300-350` (modal add-expense-modal)
**Cambios**: Agregar campo payee al formulario

```html
<div class="modal fade" id="add-expense-modal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Agregar Gasto</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form id="add-expense-form">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="expense-description-input" class="form-label">Descripción <span class="text-danger">*</span></label>
                        <input type="text" class="form-control" id="expense-description-input" 
                               name="description" required>
                    </div>
                    
                    <!-- NUEVO: Campo Beneficiario -->
                    <div class="mb-3">
                        <label for="expense-payee-input" class="form-label">
                            Beneficiario / A quién se pagó
                        </label>
                        <input type="text" class="form-control" id="expense-payee-input" 
                               name="payee" maxlength="150"
                               placeholder="Ej: EPM, Juan Pérez, Proveedor Italcol">
                        <small class="text-muted">Opcional - Máximo 150 caracteres</small>
                    </div>
                    
                    <div class="mb-3">
                        <label for="expense-amount-input" class="form-label">Monto <span class="text-danger">*</span></label>
                        <input type="number" class="form-control" id="expense-amount-input" 
                               name="amount" min="1" step="1" required>
                    </div>
                    <div class="mb-3">
                        <label for="expense-category-select" class="form-label">Categoría <span class="text-danger">*</span></label>
                        <select class="form-select" id="expense-category-select" name="category" required>
                            <option value="local">Local (servicios públicos, arrendamiento)</option>
                            <option value="proveedores">Proveedores (compra de productos)</option>
                            <option value="nomina">Nómina (salarios, groomer)</option>
                            <option value="consumibles">Consumibles (bolsas, shampoos)</option>
                            <option value="varios">Varios</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="expense-payment-method-select" class="form-label">Método de Pago <span class="text-danger">*</span></label>
                        <select class="form-select" id="expense-payment-method-select" name="payment_method" required>
                            <option value="cash">Efectivo</option>
                            <option value="transfer">Transferencia</option>
                        </select>
                    </div>
                    <div id="expense-error-alert" class="alert alert-danger d-none"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                    <button type="submit" class="btn btn-primary" id="save-expense-btn">
                        <i class="bi bi-save"></i> Guardar
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
```

**Justificación**:
- Campo payee después de descripción (flujo lógico)
- Placeholder con ejemplos
- Maxlength 150 caracteres (validación HTML5)

#### 2. Actualizar Tabla de Gastos en view.html
**Archivo**: `templates/cash_register/view.html:210-250` (tabla de gastos)
**Cambios**: Agregar columna de beneficiario

```html
<div class="table-responsive">
    <table class="table table-sm">
        <thead>
            <tr>
                <th>Descripción</th>
                <th>Beneficiario</th> <!-- NUEVA COLUMNA -->
                <th>Categoría</th>
                <th class="text-end">Monto</th>
                {% if can_edit %}<th></th>{% endif %}
            </tr>
        </thead>
        <tbody id="expenses-list">
            {% for expense in expenses %}
            <tr>
                <td>
                    {{ expense.description }}
                    <br>
                    <small class="text-muted">
                        {% if expense.payment_method == 'cash' %}
                        <i class="bi bi-cash"></i> Efectivo
                        {% else %}
                        <i class="bi bi-bank"></i> Transferencia
                        {% endif %}
                    </small>
                </td>
                <!-- NUEVA COLUMNA: Beneficiario -->
                <td>
                    {% if expense.payee %}
                    <span class="badge bg-secondary">{{ expense.payee }}</span>
                    {% else %}
                    <small class="text-muted">-</small>
                    {% endif %}
                </td>
                <td>
                    <span class="badge bg-secondary">{{ expense.category }}</span>
                </td>
                <td class="text-end">${{ '{:,.0f}'.format(expense.amount) }}</td>
                {% if can_edit %}
                <td class="text-end">
                    <form method="POST" action="{{ url_for('cash_register.delete_expense', expense_id=expense.id) }}" 
                          onsubmit="return confirm('¿Eliminar este gasto?');" style="display: inline;">
                        <button type="submit" class="btn btn-sm btn-outline-danger">
                            <i class="bi bi-trash"></i>
                        </button>
                    </form>
                </td>
                {% endif %}
            </tr>
            {% endfor %}
        </tbody>
        <tfoot>
            <tr class="fw-bold">
                <td colspan="3">Total Gastos</td> <!-- AJUSTAR COLSPAN -->
                <td class="text-end text-danger" id="total-expenses-display">
                    ${{ '{:,.0f}'.format(arqueo.total_expenses) }}
                </td>
                {% if can_edit %}<td></td>{% endif %}
            </tr>
        </tfoot>
    </table>
</div>
```

**Justificación**:
- Nueva columna entre Descripción y Categoría
- Badge para payee (consistente con categoría)
- Ajuste de colspan en footer

### Criterios de Éxito

#### Verificación Automatizada:
- [x] Template `view.html` renderiza sin errores
- [x] Modal se muestra correctamente
- [x] No hay errores JavaScript

#### Verificación Manual:

**Caso 1 - Agregar Gasto con Payee desde Arqueo**:
- [ ] Abrir arqueo existente editable
- [ ] Click "Agregar" en sección de gastos
- [ ] Modal se abre con campo payee visible
- [ ] Agregar gasto:
  - Descripción: "Shampoo perros"
  - Beneficiario: "Proveedor Italcol"
  - Monto: 30000
  - Categoría: consumibles
  - Método: cash
- [ ] Guardar
- [ ] Gasto aparece en tabla con payee en columna "Beneficiario"

**Caso 2 - Gasto Sin Payee**:
- [ ] Agregar gasto sin llenar campo payee
- [ ] Guardar
- [ ] En tabla, columna "Beneficiario" muestra "-"

**Caso 3 - Gastos Existentes Sin Payee (Migración)**:
- [ ] Ver arqueos con gastos creados antes de la migración
- [ ] Gastos antiguos muestran "-" en columna beneficiario
- [ ] No hay errores al mostrar NULL

**Caso 4 - Responsive en Tabla**:
- [ ] En móvil, tabla tiene scroll horizontal
- [ ] Columna beneficiario visible sin desbordar
- [ ] Badge de payee legible

**Caso 5 - AJAX Response con Payee**:
- [ ] Agregar gasto con AJAX
- [ ] Response JSON incluye campo payee
- [ ] (Si se implementa actualización dinámica) Tabla se actualiza mostrando payee

- [ ] No hay regresiones en modal existente
- [ ] Validación HTML5 de maxlength funciona

**Nota de Implementación**: Esta fase es independiente pero complementa Fase 3 (backend con payee). Después de verificación completa, pausar antes de Fase 7.

---

## Fase 7: Testing y Documentación

### Resumen General
Realizar testing completo de todos los flujos implementados, verificar casos edge, validar permisos y actualizar documentación del proyecto.

### Cambios Requeridos

#### 1. Script de Verificación Completa
**Archivo**: `migrations/verify_daily_expenses_implementation.py` (nuevo)
**Cambios**: Script para verificar implementación completa

```python
#!/usr/bin/env python
"""
Verificación: Sistema de Gastos Anticipados
Fecha: 2026-01-20

Verifica:
1. Modelo Expense con payee y cash_register_id nullable
2. Rutas de gastos sin arqueo
3. Asociación automática de gastos
4. Permisos de vendedor
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Path resolution
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from extensions import db
from models.models import Expense, CashRegister, User

CO_TZ = ZoneInfo("America/Bogota")

def verify_model_expense():
    """Verifica modelo Expense con cambios."""
    print("\n[INFO] Verificando modelo Expense...")
    
    with app.app_context():
        # Verificar columnas
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = {col['name']: col for col in inspector.get_columns('expense')}
        
        # Verificar cash_register_id nullable
        cash_reg_col = columns.get('cash_register_id')
        if cash_reg_col:
            is_nullable = cash_reg_col['nullable']
            if is_nullable:
                print("[OK] cash_register_id es nullable")
            else:
                print("[ERROR] cash_register_id NO es nullable")
                return False
        
        # Verificar campo payee
        if 'payee' in columns:
            print("[OK] Campo payee existe")
        else:
            print("[ERROR] Campo payee NO existe")
            return False
        
        # Verificar métodos del modelo
        if hasattr(Expense, 'is_orphan'):
            print("[OK] Metodo is_orphan() existe")
        else:
            print("[ERROR] Metodo is_orphan() NO existe")
        
        if hasattr(Expense, 'get_orphan_expenses_for_date'):
            print("[OK] Metodo get_orphan_expenses_for_date() existe")
        else:
            print("[ERROR] Metodo get_orphan_expenses_for_date() NO existe")
    
    return True

def verify_routes():
    """Verifica rutas de gastos sin arqueo."""
    print("\n[INFO] Verificando rutas...")
    
    with app.app_context():
        from routes.cash_register import cash_register_bp
        
        # Obtener todas las rutas del blueprint
        rules = [rule for rule in app.url_map.iter_rules() 
                if rule.endpoint and rule.endpoint.startswith('cash_register.')]
        
        endpoints = {rule.endpoint for rule in rules}
        
        # Verificar rutas nuevas
        required_endpoints = [
            'cash_register.add_daily_expense',
            'cash_register.delete_daily_expense',
            'cash_register.daily_expenses'
        ]
        
        for endpoint in required_endpoints:
            if endpoint in endpoints:
                print(f"[OK] Ruta {endpoint} existe")
            else:
                print(f"[ERROR] Ruta {endpoint} NO existe")
                return False
    
    return True

def test_orphan_expense_creation():
    """Test: Crear gasto sin arqueo."""
    print("\n[INFO] Test: Crear gasto sin arqueo...")
    
    with app.app_context():
        try:
            # Obtener usuario admin
            admin = User.query.filter_by(role='admin').first()
            if not admin:
                print("[ERROR] No hay usuario admin para test")
                return False
            
            # Crear gasto huerfano
            expense = Expense(
                cash_register_id=None,
                description="Test - Gasto sin arqueo",
                amount=10000,
                category='varios',
                payment_method='cash',
                payee='Test Beneficiario',
                created_by=admin.id
            )
            
            db.session.add(expense)
            db.session.commit()
            
            expense_id = expense.id
            
            # Verificar que se guardo
            saved_expense = Expense.query.get(expense_id)
            if saved_expense and saved_expense.is_orphan():
                print(f"[OK] Gasto huerfano creado (ID: {expense_id})")
                print(f"[OK] Payee: {saved_expense.payee}")
                
                # Limpiar
                db.session.delete(saved_expense)
                db.session.commit()
                print("[OK] Gasto de prueba eliminado")
                
                return True
            else:
                print("[ERROR] Gasto no se guardo correctamente")
                return False
                
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error en test: {e}")
            return False

def test_association_logic():
    """Test: Asociacion automatica de gastos."""
    print("\n[INFO] Test: Asociacion automatica...")
    
    with app.app_context():
        try:
            today = datetime.now(CO_TZ).date()
            admin = User.query.filter_by(role='admin').first()
            
            # Crear gasto huerfano
            expense = Expense(
                cash_register_id=None,
                description="Test - Para asociar",
                amount=5000,
                category='varios',
                payment_method='cash',
                payee='Test',
                created_by=admin.id
            )
            db.session.add(expense)
            db.session.flush()
            expense_id = expense.id
            
            # Crear arqueo
            register = CashRegister(
                date=today,
                user_id=admin.id,
                bills_10000=1,
                base_caja=0,
                total_cash_system=0,
                total_transfer_system=0
            )
            db.session.add(register)
            db.session.flush()
            
            # Asociar manualmente (simular associate_orphan_expenses_to_register)
            orphans = Expense.get_orphan_expenses_for_date(today)
            for exp in orphans:
                exp.cash_register_id = register.id
            
            register.calculate_totals()
            db.session.commit()
            
            # Verificar asociacion
            saved_expense = Expense.query.get(expense_id)
            if saved_expense and not saved_expense.is_orphan():
                print(f"[OK] Gasto asociado a arqueo {register.id}")
                print(f"[OK] Total gastos en arqueo: ${register.total_expenses:,.0f}")
                
                # Limpiar
                db.session.delete(saved_expense)
                db.session.delete(register)
                db.session.commit()
                print("[OK] Datos de prueba eliminados")
                
                return True
            else:
                print("[ERROR] Gasto no se asocio")
                db.session.rollback()
                return False
                
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error en test de asociacion: {e}")
            return False

def main():
    """Ejecuta verificacion completa."""
    print("="*60)
    print("VERIFICACION: Sistema de Gastos Anticipados")
    print("="*60)
    
    results = []
    
    # 1. Verificar modelo
    results.append(("Modelo Expense", verify_model_expense()))
    
    # 2. Verificar rutas
    results.append(("Rutas Blueprint", verify_routes()))
    
    # 3. Test creacion de gasto huerfano
    results.append(("Crear Gasto Huerfano", test_orphan_expense_creation()))
    
    # 4. Test asociacion
    results.append(("Asociacion Automatica", test_association_logic()))
    
    # Resumen
    print("\n" + "="*60)
    print("RESUMEN DE VERIFICACION")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {test_name}")
    
    print("="*60)
    print(f"Pruebas pasadas: {passed}/{total}")
    print("="*60)
    
    if passed == total:
        print("\n[OK] TODAS LAS VERIFICACIONES PASARON")
        return 0
    else:
        print("\n[ERROR] ALGUNAS VERIFICACIONES FALLARON")
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

**Justificación**:
- Verificación automatizada de implementación
- Tests de funcionalidad core
- Limpieza automática de datos de prueba

#### 2. Actualizar Documentación
**Archivo**: `docs/GASTOS_ANTICIPADOS_CASH_REGISTER.md` (nuevo)
**Cambios**: Documentación de usuario y técnica

```markdown
# Sistema de Gastos Anticipados - Cash Register

**Fecha de Implementación**: 2026-01-20  
**Versión**: 1.0

## Resumen

Sistema mejorado de arqueo de caja que permite registrar gastos durante el día antes de crear el arqueo, con asociación automática al momento de crear el arqueo.

## Características Nuevas

### 1. Registro de Gastos Sin Arqueo

**Antes**: Era obligatorio crear el arqueo ANTES de registrar gastos.

**Ahora**: Se pueden registrar gastos en cualquier momento del día sin necesidad de crear el arqueo.

**Beneficios**:
- Gastos se registran cuando ocurren (timestamp correcto)
- No hay descuadres temporales
- Mejor trazabilidad

### 2. Campo de Beneficiario

Todos los gastos ahora incluyen un campo opcional **"Beneficiario"** o **"A quién se pagó"**.

**Ejemplos**: "EPM", "Juan Pérez (groomer)", "Proveedor Italcol", "Viviendas y Proyectos"

**Usos**:
- Mejor trazabilidad de gastos
- Facilita reportes por proveedor
- Documentación completa

### 3. Vista de Gastos del Día

Nueva vista dedicada: `/cash-register/daily-expenses`

**Funcionalidades**:
- Ver gastos del día actual sin necesidad de arqueo
- Agregar/eliminar gastos
- Totales por método de pago (efectivo/transferencia)
- Link directo para crear arqueo

### 4. Fila Especial en Tabla de Arqueos

Si hay gastos del día sin arqueo, aparece una fila especial en la tabla de arqueos:

- **Estado**: "Arqueo Pendiente"
- **Gastos**: Muestra total de gastos registrados
- **Acciones**: "Ver Gastos" y "Crear Arqueo"

### 5. Asociación Automática

Al crear un arqueo, el sistema:

1. Busca gastos del mismo día sin arqueo
2. Busca gastos de días ANTERIORES sin arqueo
3. Los asocia automáticamente al arqueo
4. Recalcula totales incluyendo los gastos
5. Muestra mensaje informativo

## Flujo de Uso

### Flujo Completo (Nuevo)

```
09:00 - Inicio del día

10:00 - REGISTRAR GASTO
        - Usuario navega a "Gastos del Día" o usa botón en dashboard
        - Click "Agregar Gasto"
        - Descripción: "Pago luz"
        - Beneficiario: "EPM"
        - Monto: $40,000
        - Categoría: Local
        - Método: Efectivo
        ✅ Gasto guardado inmediatamente

14:00 - REGISTRAR OTRO GASTO
        - Descripción: "Shampoo perros"
        - Beneficiario: "Proveedor Italcol"
        - Monto: $30,000
        - Categoría: Consumibles
        - Método: Efectivo
        ✅ Gasto guardado

18:00 - CREAR ARQUEO
        - Contar dinero físico
        - Ingresar denominaciones
        - Sistema detecta 2 gastos ($70,000)
        - Muestra preview: "Se asociarán 2 gastos"
        - Guardar arqueo
        ✅ Gastos asociados automáticamente
        ✅ Cuadre correcto desde el inicio
```

## Permisos

### Vendedor

**Puede**:
- ✅ Registrar gastos del día actual sin arqueo
- ✅ Ver gastos del día actual en vista dedicada
- ✅ Eliminar gastos del día actual que haya creado
- ✅ Ver fila de "Arqueo Pendiente" en tabla (solo del día actual)

**No Puede**:
- ❌ Registrar gastos de fechas pasadas
- ❌ Editar/eliminar gastos de días anteriores (aunque no tengan arqueo)
- ❌ Ver gastos de otros usuarios

### Admin

**Puede**:
- ✅ TODO lo que puede vendedor
- ✅ Registrar gastos de cualquier fecha (retroactivos)
- ✅ Ver gastos de todos los días (selector de fecha)
- ✅ Eliminar cualquier gasto sin arqueo
- ✅ Acceso completo a tabla histórica

## Casos de Uso

### Caso 1: Pago de Servicio Público

**Situación**: A las 10:00 AM el vendedor paga la luz con efectivo de la caja.

**Acción**:
1. Navegar a "Gastos del Día" (dashboard o arqueos)
2. Click "Agregar Gasto"
3. Descripción: "Pago luz enero"
4. Beneficiario: "EPM"
5. Monto: 120000
6. Categoría: Local
7. Método: Efectivo
8. Guardar

**Resultado**: 
- Gasto registrado inmediatamente
- Timestamp correcto (10:00 AM)
- Al crear arqueo (18:00), se asocia automáticamente

### Caso 2: Compra a Proveedor

**Situación**: A las 14:00 el admin compra productos pagando con transferencia.

**Acción**:
1. Agregar gasto
2. Descripción: "Compra shampoo y acondicionador"
3. Beneficiario: "Distribuidora ABC"
4. Monto: 450000
5. Categoría: Proveedores
6. Método: Transferencia
7. Guardar

**Resultado**:
- Gasto registrado
- NO afecta cuadre de efectivo (es transferencia)
- Al crear arqueo, se incluye en total_expenses pero no en difference

### Caso 3: Gasto Olvidado del Día Anterior

**Situación**: El día 20/01 se olvidó crear arqueo. El día 21/01 se recuerda que hubo un gasto del 20/01.

**Escenario A - Admin**:
1. Admin puede registrar gasto retroactivo con fecha 20/01
2. Gasto queda huérfano
3. Al crear arqueo del 21/01, se asocia con warning

**Escenario B - Vendedor**:
1. Vendedor solo puede registrar gastos del día actual (21/01)
2. Debe notificar a admin para registro retroactivo

### Caso 4: Ver Gastos Antes de Arqueo

**Situación**: Vendedor quiere verificar cuántos gastos hay antes de crear el arqueo.

**Acción**:
1. Navegar a "Gastos del Día" desde tabla de arqueos (fila amarilla)
2. Ver tabla con todos los gastos
3. Cards muestran totales por método de pago
4. Click "Crear Arqueo" cuando esté listo

**Resultado**:
- Transparencia total antes de arqueo
- Puede corregir/eliminar gastos si es necesario

## Notas Técnicas

### Modelo de Datos

**Tabla `expense`**:
- `cash_register_id`: Nullable (permite gastos sin arqueo)
- `payee`: String(150), nullable (beneficiario)

**Estados de Gasto**:
- **Huérfano**: `cash_register_id IS NULL`
- **Asociado**: `cash_register_id NOT NULL`

### Asociación Automática

**Prioridad**:
1. Gastos del mismo día del arqueo
2. Gastos de días ANTERIORES (no futuros)

**Logging**:
- Gastos del mismo día: INFO
- Gastos de días anteriores: WARNING

### Cálculo de Cuadre

**Fórmula NO cambia**:
```
expected = base_caja + total_cash_system - cash_expenses
difference = total_cash_counted - expected
```

Solo gastos en **efectivo** afectan el cuadre.

## Migración de Datos

**Gastos Existentes**: NO requieren migración. Todos tienen `cash_register_id` válido.

**Campo payee**: NULL para gastos antiguos (se puede llenar retroactivamente si es necesario).

## Troubleshooting

### "No puedo registrar gasto de ayer"

**Solución**: Solo admin puede registrar gastos retroactivos. Si eres vendedor, contacta a admin.

### "Gasto no aparece en arqueo"

**Verificar**:
1. ¿El gasto es del mismo día que el arqueo?
2. ¿El arqueo se creó después del gasto?
3. Ver logs de aplicación para verificar asociación

### "Fila amarilla no aparece"

**Verificar**:
1. ¿Hay gastos registrados del día actual?
2. ¿Ya existe arqueo del día? (si existe, fila no aparece)
3. Refrescar página

## Soporte

**Documentación Técnica**: `.github/plans/2026-01-20-001-gastos-anticipados-cash-register.md`
**Script de Verificación**: `migrations/verify_daily_expenses_implementation.py`
```

**Justificación**:
- Documentación completa para usuarios
- Casos de uso reales
- Troubleshooting común
- Referencias técnicas

### Criterios de Éxito

#### Verificacion Automatizada:
- [x] Script de verificacion ejecuta: `python migrations/verify_daily_expenses_implementation.py`
- [x] Todas las pruebas del script pasan
- [x] Aplicacion inicia sin errores
- [x] No hay warnings en logs

#### Testing Manual Completo:

**Flujo 1 - Happy Path Completo**:
- [ ] Día nuevo sin arqueo ni gastos
- [ ] Registrar 3 gastos durante el día (10:00, 14:00, 16:00)
- [ ] Ver fila amarilla en tabla de arqueos
- [ ] Click "Ver Gastos" → Ver tabla con 3 gastos
- [ ] Click "Crear Arqueo"
- [ ] Ver preview: "Se asociarán 3 gastos"
- [ ] Crear arqueo con denominaciones
- [ ] Verificar cuadre correcto
- [ ] Ver gastos en vista de arqueo con payees
- [ ] No más fila amarilla en tabla

**Flujo 2 - Gastos de Días Anteriores**:
- [ ] Crear gasto huérfano del día 19/01 (admin retroactivo)
- [ ] Crear gasto del día 20/01 (hoy)
- [ ] Crear arqueo del 20/01
- [ ] Verificar que ambos gastos se asociaron
- [ ] Flash warning: "gastos de días anteriores"
- [ ] Logging muestra ambas asociaciones

**Flujo 3 - Permisos Vendedor**:
- [ ] Login como vendedor
- [ ] Intentar registrar gasto de ayer → Sistema usa fecha de hoy
- [ ] Crear gasto de hoy → Éxito
- [ ] Intentar eliminar gasto de ayer → Error: "Solo día actual"
- [ ] Intentar eliminar gasto de otro usuario → Error: "Solo propios gastos"
- [ ] Ver solo gastos propios en vista

**Flujo 4 - Edge Cases**:
- [ ] Gasto con payee de 150 caracteres exactos → Se guarda
- [ ] Gasto con payee de 151 caracteres → Error de validación
- [ ] Gasto con payee vacío → Se guarda como NULL, muestra "-"
- [ ] Gasto en transferencia → No afecta cuadre de efectivo
- [ ] Múltiples arqueos en un día (admin) → Solo primero asocia gastos

**Flujo 5 - Regresiones**:
- [ ] Crear arqueo SIN gastos previos → Funciona normal (backward compatibility)
- [ ] Agregar gasto a arqueo existente → Funciona con payee
- [ ] Editar arqueo existente → No afecta gastos
- [ ] Eliminar gasto de arqueo editable → Funciona
- [ ] Ver arqueos antiguos (pre-migración) → Sin errores con payee NULL

**Flujo 6 - UI/UX**:
- [ ] Fila amarilla destaca visualmente
- [ ] Modal de gastos responsive en móvil
- [ ] DataTables ordena correctamente con fila especial
- [ ] Badges de payee legibles
- [ ] Cards de totales correctos
- [ ] Breadcrumbs funcionales

#### Documentación:
- [ ] README actualizado con mención de gastos anticipados
- [ ] Archivo `GASTOS_ANTICIPADOS_CASH_REGISTER.md` creado
- [ ] Plan de implementación completo en `.github/plans/`
- [ ] Comentarios en código actualizados

#### Performance:
- [ ] Query de gastos huérfanos eficiente (índice usado)
- [ ] Carga de vista daily_expenses < 500ms
- [ ] Asociación de 100+ gastos < 2 segundos

**Nota de Implementación**: Esta es la fase final. Después de verificación completa, considerar la implementación COMPLETA y lista para producción.

---

## Estrategia de Testing

### Testing Unitario (Manual)
- Crear gastos huérfanos
- Verificar asociación automática
- Validaciones de permisos
- Cálculo de totales

### Testing de Integración
- Flujo completo: Gastos → Arqueo → Vista
- Interacción entre rutas
- Persistencia de datos

### Testing de Regresión
- Arqueos existentes siguen funcionando
- Gastos con arqueo no afectados
- Backward compatibility

### Testing de Performance
- 100+ gastos huérfanos
- Múltiples usuarios concurrentes
- Queries optimizadas

## Consideraciones de Rendimiento

**Índice Creado**:
```sql
CREATE INDEX idx_expense_cash_register_null 
ON expense(created_at) 
WHERE cash_register_id IS NULL;
```

**Beneficio**: Query de gastos huérfanos O(log n) en lugar de O(n)

**Queries Optimizadas**:
- `get_orphan_expenses_for_date()`: Usa índice + filtro de fecha
- `get_all_orphan_expenses()`: Usa índice parcial

## Consideraciones de Seguridad

**Validaciones Backend**:
- Permisos por rol (vendedor/admin)
- Validación de longitud de payee
- Sanitización de inputs
- Transacciones con rollback

**Auditoría**:
- Logging de todas las acciones
- `created_by` en todos los gastos
- Timestamps precisos

## Consideraciones de Base de Datos

**SQLite**:
- Recreación de tabla para ALTER COLUMN
- Índice parcial soportado
- Backup automático antes de migración

**PostgreSQL** (si se migra):
- `ALTER COLUMN DROP NOT NULL` directo
- Índice parcial nativo
- Mejor concurrencia

## Deployment Notes

**Pre-Deployment**:
1. Backup completo de base de datos
2. Verificar que no hay arqueos en edición
3. Ejecutar migración en horario de bajo tráfico

**Post-Deployment**:
1. Ejecutar script de verificación
2. Crear gasto de prueba sin arqueo
3. Crear arqueo de prueba
4. Verificar asociación
5. Eliminar datos de prueba
6. Monitorear logs por 24 horas

**Rollback Plan**:
- Restaurar desde backup
- Revertir cambios en routes (git revert)
- No hay pérdida de datos (solo gastos huérfanos nuevos)

## Referencias

- **Plan de Implementación**: `.github/plans/2026-01-20-001-gastos-anticipados-cash-register.md`
- **Investigación Previa**: `docs/research/2026-01-20-001-gastos-anticipados-mejora-cash-register.md`
- **Flujo Actual**: `docs/FLUJO_ACTUAL_CASH_REGISTER.md`
- **Migración de Arqueo**: `docs/INSTRUCCIONES_MIGRACION_ARQUEO.md`
- **Código Fuente**:
  - Modelo: `models/models.py:700-733`
  - Rutas: `routes/cash_register.py`
  - Templates: `templates/cash_register/`
  - Migración: `migrations/migration_add_payee_nullable_cash_register.py`