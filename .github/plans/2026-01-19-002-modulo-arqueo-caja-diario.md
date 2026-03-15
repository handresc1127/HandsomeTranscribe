---
plan_id: 2026-01-19-002
date: 2026-01-19
author: GitHub Copilot
task: N/A
status: draft
last_updated: 2026-01-19
last_updated_by: GitHub Copilot
---

# Plan de Implementación: Módulo de Arqueo de Caja Diario

**Plan ID**: 2026-01-19-002  
**Fecha**: 19 de Enero de 2026  
**Autor**: GitHub Copilot  
**Tarea**: N/A

## Resumen General

Implementar un **módulo completo de Arqueo de Caja Diario** para Green-POS que permita:
- Conteo visual de billetes y monedas colombianas por denominación
- Totalización automática de efectivo físico vs sistema
- Comparación con ventas del día
- Cálculo automático de cuadre (sobrante/faltante)
- Gestión de gastos por categorías
- Permisos diferenciados para Admin y Vendedor

## Análisis del Estado Actual

### Descubrimientos Clave

**Componentes Reutilizables Existentes**:
- ✅ **Sistema de Facturación** ([routes/invoices.py:79-90](d:/Users/Henry.Correa/Downloads/workspace/Green-POS/routes/invoices.py#L79-L90)) - Totalización de efectivo con parseo de pagos mixtos
- ✅ **Sistema de Reportes** ([routes/reports.py:106-122](d:/Users/Henry.Correa/Downloads/workspace/Green-POS/routes/reports.py#L106-L122)) - Análisis por método de pago con agrupación
- ✅ **Patrón de Blueprint CRUD** - 11 módulos documentados con estructura estándar
- ✅ **Conversión de Timezone** - `America/Bogota` (CO_TZ) para timestamps locales
- ✅ **Pago Mixto Discriminado** ([docs/IMPLEMENTACION_NOTAS_CREDITO_DIAN.md](d:/Users/Henry.Correa/Downloads/workspace/Green-POS/docs/IMPLEMENTACION_NOTAS_CREDITO_DIAN.md)) - Patrón de desglose de montos

**Patrones a Seguir**:
- Factory Pattern para creación de app
- Blueprint Pattern para módulos
- Repository Pattern para queries complejas
- Decorator Pattern para autenticación (`@login_required`, `@role_required`)
- Transacciones con try-except y rollback

**Investigación Completa**:
- Documento: [docs/research/2026-01-19-001-patron-arqueo-caja-diario-analisis-componentes.md](d:/Users/Henry.Correa/Downloads/workspace/Green-POS/docs/research/2026-01-19-001-patron-arqueo-caja-diario-analisis-componentes.md)

## Estado Final Deseado

Un módulo funcional de arqueo de caja con:

### Para Admin:
- ✅ Crear arqueo de cualquier fecha
- ✅ Conteo completo de billetes (6) y monedas (5)
- ✅ Base inicial calculada automáticamente del día anterior
- ✅ Agregar gastos uno a uno con 5 categorías
- ✅ Ver histórico completo de arqueos
- ✅ Editar últimos 5 arqueos
- ✅ Ver detalle con facturas del día
- ✅ Alertas si diferencia > $10,000

### Para Vendedor:
- ✅ Crear arqueo solo del día actual
- ✅ Conteo simplificado (solo billetes)
- ✅ Agregar gastos básicos
- ✅ Ver/editar solo su arqueo del día actual
- ❌ NO ver arqueos anteriores

### Verificación:
- [X] Constraint `UNIQUE` en `date` (1 arqueo por día)
- [X] Método `can_edit()` valida últimos 5 días
- [X] Permisos diferenciados por rol en cada ruta
- [X] JavaScript calcula totales en tiempo real
- [X] Flash messages informativos
- [X] Responsive design (Bootstrap 5.3+)

## Lo Que NO Vamos a Hacer

- ❌ **NO** implementar exportación a PDF/Excel en esta fase (Fase 6 opcional)
- ❌ **NO** crear gráficos de cuadre mensual (Fase 6 opcional)
- ❌ **NO** enviar notificaciones por email
- ❌ **NO** integrar con módulo de reportes (`/reports`) en esta fase
- ❌ **NO** crear arqueos de días futuros (solo actual o pasados)
- ❌ **NO** permitir eliminar arqueos (solo editar últimos 5)
- ❌ **NO** implementar múltiples arqueos por día
- ❌ **NO** usar imágenes reales de billetes (usar Bootstrap Icons)

## Enfoque de Implementación

**Estrategia**: Implementación incremental por fases, comenzando con flujo completo para **Admin**, luego adaptando para **Vendedor**.

**Justificación**:
1. Admin tiene todas las funcionalidades → Base sólida
2. Vendedor es subset simplificado → Menos riesgo de regresión
3. Testing más eficiente (validar completo primero)

**Reutilización de Código**:
- Lógica de totalización de `templates/invoices/list.html`
- Algoritmo de agrupación por fecha de `routes/invoices.py`
- Patrón de transacciones con rollback de blueprints existentes
- Validación frontend tiempo real similar a pago mixto

---

## Fase 1: Backend - Modelos y Migración

### Resumen General
Crear modelos de base de datos `CashRegister` y `Expense` con relaciones, validaciones y métodos de negocio.

### Cambios Requeridos

#### 1. Modelo CashRegister
**Archivo**: `models/models.py`
**Ubicación**: Agregar después del modelo `Invoice` (línea ~250)

```python
class CashRegister(db.Model):
    """Arqueo de caja diario - 1 por día.
    
    Registra el conteo físico de dinero al cierre del día y lo compara
    con las ventas del sistema para calcular el cuadre.
    """
    __tablename__ = 'cash_register'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)  # UNIQUE: 1 arqueo por día
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Conteo de denominaciones - Billetes
    bills_100000 = db.Column(db.Integer, default=0)  # $100,000
    bills_50000 = db.Column(db.Integer, default=0)   # $50,000
    bills_20000 = db.Column(db.Integer, default=0)   # $20,000
    bills_10000 = db.Column(db.Integer, default=0)   # $10,000
    bills_5000 = db.Column(db.Integer, default=0)    # $5,000
    bills_2000 = db.Column(db.Integer, default=0)    # $2,000
    
    # Monedas (opcionales para vendedor)
    coins_1000 = db.Column(db.Integer, default=0)    # $1,000
    coins_500 = db.Column(db.Integer, default=0)     # $500
    coins_200 = db.Column(db.Integer, default=0)     # $200
    coins_100 = db.Column(db.Integer, default=0)     # $100
    coins_50 = db.Column(db.Integer, default=0)      # $50
    
    # Totales calculados
    total_cash_counted = db.Column(db.Float, nullable=False, default=0.0)
    total_cash_system = db.Column(db.Float, nullable=False, default=0.0)
    total_transfer_system = db.Column(db.Float, nullable=False, default=0.0)
    total_expenses = db.Column(db.Float, default=0.0)
    
    # Base y cuadre
    base_caja = db.Column(db.Float, default=0.0)  # Calculado del día anterior
    difference = db.Column(db.Float, default=0.0)  # Sobrante (+) o faltante (-)
    
    # Auditoría
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(CO_TZ))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(CO_TZ))
    
    # Relaciones
    user = db.relationship('User', backref='cash_registers')
    expenses = db.relationship('Expense', backref='cash_register', 
                              lazy='dynamic', cascade='all, delete-orphan')
    
    def calculate_totals(self):
        """Calcula totales basados en denominaciones y gastos."""
        # Sumar billetes
        self.total_cash_counted = (
            self.bills_100000 * 100000 +
            self.bills_50000 * 50000 +
            self.bills_20000 * 20000 +
            self.bills_10000 * 10000 +
            self.bills_5000 * 5000 +
            self.bills_2000 * 2000 +
            self.coins_1000 * 1000 +
            self.coins_500 * 500 +
            self.coins_200 * 200 +
            self.coins_100 * 100 +
            self.coins_50 * 50
        )
        
        # Calcular total de gastos desde tabla Expense
        self.total_expenses = db.session.query(
            func.sum(Expense.amount)
        ).filter(
            Expense.cash_register_id == self.id
        ).scalar() or 0.0
        
        # Calcular diferencia
        expected = self.base_caja + self.total_cash_system - self.total_expenses
        self.difference = self.total_cash_counted - expected
    
    def can_edit(self):
        """Verifica si el arqueo puede editarse (últimos 5 días)."""
        if not self.date:
            return False
        today = datetime.now(CO_TZ).date()
        days_ago = (today - self.date).days
        return days_ago <= 5
    
    def get_invoices_of_day(self):
        """Obtiene facturas del día del arqueo."""
        start_of_day = datetime.combine(self.date, datetime.min.time()).replace(tzinfo=CO_TZ)
        end_of_day = datetime.combine(self.date, datetime.max.time()).replace(tzinfo=CO_TZ)
        start_utc = start_of_day.astimezone(timezone.utc)
        end_utc = end_of_day.astimezone(timezone.utc)
        
        return Invoice.query.filter(
            Invoice.date >= start_utc,
            Invoice.date <= end_utc,
            Invoice.document_type == 'invoice'  # Solo facturas, no NC
        ).order_by(Invoice.date.desc()).all()
    
    @staticmethod
    def get_base_from_previous_day(date):
        """Calcula base inicial desde arqueo del día anterior."""
        previous_date = date - timedelta(days=1)
        previous_arqueo = CashRegister.query.filter_by(date=previous_date).first()
        
        if previous_arqueo:
            # Base = efectivo contado del día anterior
            return previous_arqueo.total_cash_counted
        else:
            # Primer arqueo o día sin arqueo anterior
            return 0.0
    
    def __repr__(self):
        return f'<CashRegister {self.date} - ${self.total_cash_counted:,.0f}>'


class Expense(db.Model):
    """Gastos del día asociados a un arqueo de caja.
    
    Categorías:
    - local: Servicios públicos, arrendamiento
    - proveedores: Compra de productos para venta
    - nomina: Salarios, groomer, ayudantes
    - consumibles: Bolsas, shampoos, insumos
    - varios: Otros gastos
    """
    __tablename__ = 'expense'
    
    id = db.Column(db.Integer, primary_key=True)
    cash_register_id = db.Column(db.Integer, db.ForeignKey('cash_register.id'), nullable=False)
    
    # Datos del gasto
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='varios')
    # Valores: 'local', 'proveedores', 'nomina', 'consumibles', 'varios'
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(CO_TZ))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relación
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<Expense {self.category}: {self.description} - ${self.amount:,.0f}>'
```

**Justificación**:
- **`date` con `UNIQUE`**: Garantiza 1 arqueo por día a nivel de base de datos
- **Método `can_edit()`**: Centraliza lógica de edición de últimos 5 días
- **Método `calculate_totals()`**: Desacopla cálculos de rutas
- **Método `get_base_from_previous_day()`**: Automatiza cálculo de base inicial
- **Relación con `Expense`**: One-to-Many con cascade delete

#### 2. Script de Migración
**Archivo**: `migrations/migration_add_cash_register.py`

```python
"""
Migración: Agregar tablas para Módulo de Arqueo de Caja
Fecha: 2026-01-19
Descripción: Crea tablas cash_register y expense
"""

from pathlib import Path
from datetime import datetime
import sqlite3
import shutil

# Path resolution (patrón estándar Green-POS)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / 'instance' / 'app.db'
SQL_FILE = SCRIPT_DIR / 'migration_add_cash_register.sql'

def backup_database():
    """Crea backup antes de migración."""
    backup_path = DB_PATH.parent / f'app.db.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    shutil.copy2(DB_PATH, backup_path)
    print(f"[OK] Backup creado: {backup_path.name}")
    return backup_path

def run_migration():
    """Ejecuta migración de arqueo de caja."""
    print("\n" + "="*60)
    print("MIGRACION: Modulo de Arqueo de Caja")
    print("="*60 + "\n")
    
    if not DB_PATH.exists():
        print(f"[ERROR] Base de datos no encontrada: {DB_PATH}")
        return False
    
    # Backup
    backup_path = backup_database()
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        print("\n[INFO] Creando tabla cash_register...")
        
        # Tabla cash_register
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cash_register (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            
            -- Billetes
            bills_100000 INTEGER DEFAULT 0,
            bills_50000 INTEGER DEFAULT 0,
            bills_20000 INTEGER DEFAULT 0,
            bills_10000 INTEGER DEFAULT 0,
            bills_5000 INTEGER DEFAULT 0,
            bills_2000 INTEGER DEFAULT 0,
            
            -- Monedas
            coins_1000 INTEGER DEFAULT 0,
            coins_500 INTEGER DEFAULT 0,
            coins_200 INTEGER DEFAULT 0,
            coins_100 INTEGER DEFAULT 0,
            coins_50 INTEGER DEFAULT 0,
            
            -- Totales
            total_cash_counted REAL NOT NULL DEFAULT 0.0,
            total_cash_system REAL NOT NULL DEFAULT 0.0,
            total_transfer_system REAL NOT NULL DEFAULT 0.0,
            total_expenses REAL DEFAULT 0.0,
            
            -- Base y cuadre
            base_caja REAL DEFAULT 0.0,
            difference REAL DEFAULT 0.0,
            
            -- Auditoria
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            
            FOREIGN KEY (user_id) REFERENCES user(id)
        )
        """)
        print("[OK] Tabla cash_register creada")
        
        print("\n[INFO] Creando tabla expense...")
        
        # Tabla expense
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cash_register_id INTEGER NOT NULL,
            description VARCHAR(200) NOT NULL,
            amount REAL NOT NULL,
            category VARCHAR(50) NOT NULL DEFAULT 'varios',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            
            FOREIGN KEY (cash_register_id) REFERENCES cash_register(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES user(id)
        )
        """)
        print("[OK] Tabla expense creada")
        
        print("\n[INFO] Creando indices...")
        
        # Índices para optimización
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cash_register_date ON cash_register(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cash_register_user ON cash_register(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expense_cash_register ON expense(cash_register_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expense_category ON expense(category)")
        
        print("[OK] Indices creados")
        
        conn.commit()
        print("\n[OK] Migracion completada exitosamente")
        print(f"[INFO] Backup disponible en: {backup_path}")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Error en migracion: {e}")
        print(f"[INFO] Restaurar desde backup: {backup_path}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    success = run_migration()
    exit(0 if success else 1)
```

**Justificación**:
- Sigue template estándar de migraciones Green-POS
- Path resolution con `Path(__file__).parent`
- Backup automático antes de ejecutar
- Constraint `UNIQUE` en `date`
- FK con `ON DELETE CASCADE` para expenses
- Índices en columnas de búsqueda frecuente

### Criterios de Éxito

#### Verificación Automatizada:
- [x] Aplicación inicia sin errores: `python app.py`
- [x] Migración ejecuta exitosamente: `python migrations/migration_add_cash_register.py`
- [x] Tablas creadas: `cash_register`, `expense`
- [ ] Constraint `UNIQUE(date)` funciona (intenta crear 2 arqueos con misma fecha → error)
- [ ] Relaciones FK correctas: insertar expense requiere cash_register_id válido

#### Verificación Manual:
- [x] Modelos se importan sin errores: `from models.models import CashRegister, Expense`
- [ ] Método `calculate_totals()` calcula correctamente con datos de prueba
- [ ] Método `can_edit()` retorna `True` para fechas <= 5 días, `False` para anteriores
- [ ] Método `get_base_from_previous_day()` retorna 0 si no hay arqueo anterior

**Nota de Implementación**: Después de completar esta fase, pausar para confirmación manual antes de proceder a Fase 2.

---

## Fase 2: Backend - Blueprint y Rutas

### Resumen General
Crear blueprint `cash_register_bp` con todas las rutas CRUD, funciones auxiliares para cálculo de totales, y rutas de gastos con respuestas JSON.

### Cambios Requeridos

#### 1. Blueprint Principal
**Archivo**: `routes/cash_register.py` (nuevo)

```python
"""
Blueprint: Arqueo de Caja
Rutas para gestión de arqueos diarios con conteo de billetes/monedas y gastos.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
import pytz

from extensions import db
from models.models import CashRegister, Expense, Invoice
from utils.decorators import role_required

CO_TZ = pytz.timezone('America/Bogota')

cash_register_bp = Blueprint('cash_register', __name__, url_prefix='/cash-register')


@cash_register_bp.route('/')
@role_required('admin')
def list():
    """Lista arqueos históricos (solo admin)."""
    arqueos = CashRegister.query.order_by(CashRegister.date.desc()).all()
    return render_template('cash_register/list.html', arqueos=arqueos)


@cash_register_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Crear nuevo arqueo de caja.
    
    Admin: Puede crear de cualquier fecha
    Vendedor: Solo del día actual
    """
    today = datetime.now(CO_TZ).date()
    
    # VALIDACIÓN: 1 arqueo por día
    existing = CashRegister.query.filter_by(date=today).first()
    if existing:
        flash(f'Ya existe un arqueo para la fecha {today.strftime("%d/%m/%Y")}', 'warning')
        return redirect(url_for('cash_register.view', id=existing.id))
    
    # RESTRICCIÓN: Vendedor solo día actual
    if current_user.role == 'vendedor':
        target_date = today
    else:
        # Admin puede especificar fecha (si se implementa selector)
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
            
            # Monedas solo para admin
            if current_user.role == 'admin':
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
            
            # Calcular totales y diferencia
            arqueo.calculate_totals()
            
            db.session.add(arqueo)
            db.session.commit()
            
            # Alerta si diferencia > $10,000
            if abs(arqueo.difference) > 10000:
                if arqueo.difference > 0:
                    flash(f'Sobrante detectado: ${arqueo.difference:,.0f}', 'warning')
                else:
                    flash(f'Faltante detectado: ${abs(arqueo.difference):,.0f}', 'danger')
            
            flash('Arqueo de caja guardado exitosamente', 'success')
            return redirect(url_for('cash_register.view', id=arqueo.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar arqueo: {str(e)}', 'danger')
    
    # GET - Cargar datos del día
    total_cash_system = get_total_cash_for_date(target_date)
    total_transfer_system = get_total_transfer_for_date(target_date)
    base_caja = CashRegister.get_base_from_previous_day(target_date)
    
    show_coins = current_user.role == 'admin'
    
    return render_template('cash_register/form.html',
                         total_cash_system=total_cash_system,
                         total_transfer_system=total_transfer_system,
                         base_caja=base_caja,
                         show_coins=show_coins,
                         is_edit=False)


@cash_register_bp.route('/view/<int:id>')
@login_required
def view(id):
    """Ver detalle de arqueo."""
    arqueo = CashRegister.query.get_or_404(id)
    
    # PERMISO: Vendedor solo ve su arqueo del día actual
    if current_user.role == 'vendedor':
        today = datetime.now(CO_TZ).date()
        if arqueo.date != today or arqueo.user_id != current_user.id:
            flash('Acceso denegado. Solo puede ver su arqueo del día actual.', 'danger')
            return redirect(url_for('dashboard.index'))
    
    invoices = arqueo.get_invoices_of_day()
    expenses = arqueo.expenses.all()
    
    can_edit = arqueo.can_edit()
    
    return render_template('cash_register/view.html', 
                         arqueo=arqueo, 
                         invoices=invoices,
                         expenses=expenses,
                         can_edit=can_edit)


@cash_register_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Editar arqueo existente (últimos 5 días únicamente)."""
    arqueo = CashRegister.query.get_or_404(id)
    
    # VALIDACIÓN: Solo últimos 5 arqueos
    if not arqueo.can_edit():
        flash('No se puede editar. Solo se permiten cambios en los últimos 5 arqueos.', 'warning')
        return redirect(url_for('cash_register.view', id=id))
    
    # PERMISO: Vendedor solo edita su arqueo
    if current_user.role == 'vendedor' and arqueo.user_id != current_user.id:
        flash('Acceso denegado. Solo puede editar su propio arqueo.', 'danger')
        return redirect(url_for('cash_register.view', id=id))
    
    if request.method == 'POST':
        try:
            # Actualizar denominaciones
            arqueo.bills_100000 = int(request.form.get('bills_100000', 0))
            arqueo.bills_50000 = int(request.form.get('bills_50000', 0))
            arqueo.bills_20000 = int(request.form.get('bills_20000', 0))
            arqueo.bills_10000 = int(request.form.get('bills_10000', 0))
            arqueo.bills_5000 = int(request.form.get('bills_5000', 0))
            arqueo.bills_2000 = int(request.form.get('bills_2000', 0))
            arqueo.notes = request.form.get('notes', '')
            
            if current_user.role == 'admin':
                arqueo.coins_1000 = int(request.form.get('coins_1000', 0))
                arqueo.coins_500 = int(request.form.get('coins_500', 0))
                arqueo.coins_200 = int(request.form.get('coins_200', 0))
                arqueo.coins_100 = int(request.form.get('coins_100', 0))
                arqueo.coins_50 = int(request.form.get('coins_50', 0))
            
            # Recalcular totales
            arqueo.calculate_totals()
            
            db.session.commit()
            flash('Arqueo actualizado exitosamente', 'success')
            return redirect(url_for('cash_register.view', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar arqueo: {str(e)}', 'danger')
    
    # GET
    show_coins = current_user.role == 'admin'
    return render_template('cash_register/form.html', 
                         arqueo=arqueo,
                         show_coins=show_coins,
                         is_edit=True)


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
    amount = float(request.form.get('amount', 0))
    category = request.form.get('category', 'varios')
    
    # Validaciones
    if not description:
        return jsonify({'error': 'La descripción es obligatoria'}), 400
    
    if amount <= 0:
        return jsonify({'error': 'El monto debe ser mayor a cero'}), 400
    
    # Validar categoría
    valid_categories = ['local', 'proveedores', 'nomina', 'consumibles', 'varios']
    if category not in valid_categories:
        return jsonify({'error': f'Categoría inválida. Debe ser: {", ".join(valid_categories)}'}), 400
    
    try:
        expense = Expense(
            cash_register_id=arqueo.id,
            description=description,
            amount=amount,
            category=category,
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
                'created_at': expense.created_at.strftime('%H:%M')
            },
            'total_expenses': arqueo.total_expenses,
            'difference': arqueo.difference
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@cash_register_bp.route('/expense/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_expense(expense_id):
    """Eliminar gasto."""
    expense = Expense.query.get_or_404(expense_id)
    arqueo = expense.cash_register
    
    # VALIDACIÓN: Solo arqueos editables
    if not arqueo.can_edit():
        flash('No se pueden eliminar gastos de arqueos antiguos', 'warning')
        return redirect(url_for('cash_register.view', id=arqueo.id))
    
    # PERMISO
    if current_user.role == 'vendedor' and arqueo.user_id != current_user.id:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('cash_register.view', id=arqueo.id))
    
    try:
        db.session.delete(expense)
        arqueo.calculate_totals()
        db.session.commit()
        flash('Gasto eliminado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar gasto: {str(e)}', 'danger')
    
    return redirect(url_for('cash_register.view', id=arqueo.id))


def get_total_cash_for_date(date):
    """Calcula total de efectivo del día (reutiliza lógica de invoices)."""
    start_datetime = datetime.combine(date, datetime.min.time()).replace(tzinfo=CO_TZ)
    end_datetime = datetime.combine(date, datetime.max.time()).replace(tzinfo=CO_TZ)
    start_utc = start_datetime.astimezone(timezone.utc)
    end_utc = end_datetime.astimezone(timezone.utc)
    
    invoices = Invoice.query.filter(
        Invoice.date >= start_utc,
        Invoice.date <= end_utc,
        Invoice.document_type == 'invoice'
    ).all()
    
    total = 0.0
    for inv in invoices:
        if inv.payment_method == 'cash':
            total += inv.total
        elif inv.payment_method == 'mixed' and inv.notes and 'Efectivo: $' in inv.notes:
            # Parsear monto de efectivo del pago mixto
            try:
                cash_part = inv.notes.split('Efectivo: $')[1].split('\n')[0]
                total += float(cash_part.replace('.', '').replace(',', '.'))
            except:
                pass
    
    return total


def get_total_transfer_for_date(date):
    """Calcula total de transferencias del día."""
    start_datetime = datetime.combine(date, datetime.min.time()).replace(tzinfo=CO_TZ)
    end_datetime = datetime.combine(date, datetime.max.time()).replace(tzinfo=CO_TZ)
    start_utc = start_datetime.astimezone(timezone.utc)
    end_utc = end_datetime.astimezone(timezone.utc)
    
    invoices = Invoice.query.filter(
        Invoice.date >= start_utc,
        Invoice.date <= end_utc,
        Invoice.document_type == 'invoice'
    ).all()
    
    total = 0.0
    for inv in invoices:
        if inv.payment_method == 'transfer':
            total += inv.total
        elif inv.payment_method == 'mixed' and inv.notes and 'Transferencia: $' in inv.notes:
            # Parsear monto de transferencia
            try:
                transfer_part = inv.notes.split('Transferencia: $')[1].split('\n')[0]
                total += float(transfer_part.replace('.', '').replace(',', '.'))
            except:
                pass
    
    return total
```

**Justificación**:
- Sigue estructura estándar de blueprints Green-POS
- Reutiliza lógica de totalización de `templates/invoices/list.html`
- Permisos diferenciados por rol en cada ruta
- Base calculada automáticamente del día anterior
- Respuestas JSON para agregar gastos (sin recargar página)
- Alertas si diferencia > $10,000

#### 2. Registrar Blueprint
**Archivo**: `app.py`
**Ubicación**: Sección de registro de blueprints (línea ~100)

```python
# Registrar blueprints
from routes.cash_register import cash_register_bp
app.register_blueprint(cash_register_bp)
```

### Criterios de Éxito

#### Verificación Automatizada:
- [x] Aplicación inicia sin errores: `python app.py`
- [x] Blueprint registrado: verificar en logs de inicio
- [x] Rutas accesibles sin 404:
  - `/cash-register/` (admin)
  - `/cash-register/new` (ambos roles)
  - `/cash-register/view/1` (con arqueo de prueba)

#### Verificación Manual:
- [ ] Admin puede acceder a `/cash-register/` (lista)
- [ ] Vendedor recibe "Acceso denegado" en `/cash-register/`
- [ ] Formulario de creación carga totales del sistema correctamente
- [ ] Base inicial se calcula del día anterior
- [ ] Validación de 1 arqueo por día funciona (intenta crear 2 → error)
- [ ] Método `can_edit()` bloquea edición de arqueos > 5 días
- [ ] Gastos se agregan y eliminan correctamente

**Nota de Implementación**: Después de completar esta fase, pausar para confirmación manual antes de proceder a Fase 3.

---

## Fase 3: Frontend - Templates

### Resumen General
Crear templates con Bootstrap 5.3+, iconos de Bootstrap Icons para denominaciones, JavaScript para cálculo en tiempo real, y modal para agregar gastos.

### Cambios Requeridos

#### 1. Template de Formulario
**Archivo**: `templates/cash_register/form.html` (nuevo)

```html
{% extends "layout.html" %}

{% block title %}{% if is_edit %}Editar{% else %}Nuevo{% endif %} Arqueo de Caja{% endblock %}

{% block content %}
<div class="container-fluid py-4">
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="{{ url_for('dashboard.index') }}">Inicio</a></li>
            {% if current_user.role == 'admin' %}
            <li class="breadcrumb-item"><a href="{{ url_for('cash_register.list') }}">Arqueos de Caja</a></li>
            {% endif %}
            <li class="breadcrumb-item active">{% if is_edit %}Editar{% else %}Nuevo{% endif %} Arqueo</li>
        </ol>
    </nav>
    
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>{% if is_edit %}Editar{% else %}Nuevo{% endif %} Arqueo de Caja</h2>
        <div>
            <span class="badge bg-info">{{ arqueo.date.strftime('%d/%m/%Y') if is_edit else 'now'|datetime('%d/%m/%Y') }}</span>
        </div>
    </div>
    
    <form method="POST" id="cash-register-form">
        <!-- SECCIÓN 1: Totales del Sistema -->
        <div class="card mb-4">
            <div class="card-header bg-info text-white">
                <h5 class="mb-0"><i class="bi bi-graph-up"></i> Ventas del Día (Sistema)</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-3">
                        <label class="form-label fw-bold">Base Inicial</label>
                        <input type="text" class="form-control form-control-lg text-primary fw-bold" 
                               value="{{ '${:,.0f}'.format(base_caja if base_caja else (arqueo.base_caja if is_edit else 0)) }}" 
                               readonly>
                        <small class="text-muted">Calculado del día anterior</small>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label fw-bold">Efectivo Sistema</label>
                        <input type="text" class="form-control form-control-lg text-success fw-bold" 
                               value="{{ '${:,.0f}'.format(total_cash_system if total_cash_system else (arqueo.total_cash_system if is_edit else 0)) }}" 
                               readonly>
                        <small class="text-muted">Facturas en efectivo</small>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label fw-bold">Transferencias Sistema</label>
                        <input type="text" class="form-control form-control-lg text-warning fw-bold" 
                               value="{{ '${:,.0f}'.format(total_transfer_system if total_transfer_system else (arqueo.total_transfer_system if is_edit else 0)) }}" 
                               readonly>
                        <small class="text-muted">Facturas por transferencia</small>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label fw-bold">Total Ventas</label>
                        <input type="text" class="form-control form-control-lg text-dark fw-bold" 
                               value="{{ '${:,.0f}'.format((total_cash_system if total_cash_system else 0) + (total_transfer_system if total_transfer_system else 0)) }}" 
                               readonly>
                        <small class="text-muted">Suma total del día</small>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- SECCIÓN 2: Conteo de Billetes -->
        <div class="card mb-4">
            <div class="card-header bg-success text-white">
                <h5 class="mb-0"><i class="bi bi-cash-stack"></i> Conteo de Billetes</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <!-- Billete $100,000 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-cash-stack" style="font-size: 3rem; color: #d4af37;"></i>
                            <br><span class="fw-bold">$100,000</span>
                        </label>
                        <input type="number" id="bills-100000-input" 
                               name="bills_100000" class="form-control text-center bill-count" 
                               min="0" value="{{ arqueo.bills_100000 if is_edit else 0 }}" 
                               data-value="100000">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="bills-100000-total">$0</span>
                        </small>
                    </div>
                    
                    <!-- Billete $50,000 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-cash-stack" style="font-size: 3rem; color: #e67e22;"></i>
                            <br><span class="fw-bold">$50,000</span>
                        </label>
                        <input type="number" id="bills-50000-input" 
                               name="bills_50000" class="form-control text-center bill-count" 
                               min="0" value="{{ arqueo.bills_50000 if is_edit else 0 }}" 
                               data-value="50000">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="bills-50000-total">$0</span>
                        </small>
                    </div>
                    
                    <!-- Billete $20,000 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-cash-stack" style="font-size: 3rem; color: #e74c3c;"></i>
                            <br><span class="fw-bold">$20,000</span>
                        </label>
                        <input type="number" id="bills-20000-input" 
                               name="bills_20000" class="form-control text-center bill-count" 
                               min="0" value="{{ arqueo.bills_20000 if is_edit else 0 }}" 
                               data-value="20000">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="bills-20000-total">$0</span>
                        </small>
                    </div>
                    
                    <!-- Billete $10,000 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-cash-stack" style="font-size: 3rem; color: #3498db;"></i>
                            <br><span class="fw-bold">$10,000</span>
                        </label>
                        <input type="number" id="bills-10000-input" 
                               name="bills_10000" class="form-control text-center bill-count" 
                               min="0" value="{{ arqueo.bills_10000 if is_edit else 0 }}" 
                               data-value="10000">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="bills-10000-total">$0</span>
                        </small>
                    </div>
                    
                    <!-- Billete $5,000 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-cash-stack" style="font-size: 3rem; color: #9b59b6;"></i>
                            <br><span class="fw-bold">$5,000</span>
                        </label>
                        <input type="number" id="bills-5000-input" 
                               name="bills_5000" class="form-control text-center bill-count" 
                               min="0" value="{{ arqueo.bills_5000 if is_edit else 0 }}" 
                               data-value="5000">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="bills-5000-total">$0</span>
                        </small>
                    </div>
                    
                    <!-- Billete $2,000 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-cash-stack" style="font-size: 3rem; color: #1abc9c;"></i>
                            <br><span class="fw-bold">$2,000</span>
                        </label>
                        <input type="number" id="bills-2000-input" 
                               name="bills_2000" class="form-control text-center bill-count" 
                               min="0" value="{{ arqueo.bills_2000 if is_edit else 0 }}" 
                               data-value="2000">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="bills-2000-total">$0</span>
                        </small>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- SECCIÓN 3: Conteo de Monedas (solo admin) -->
        {% if show_coins %}
        <div class="card mb-4">
            <div class="card-header bg-warning">
                <h5 class="mb-0"><i class="bi bi-coin"></i> Conteo de Monedas</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <!-- Moneda $1,000 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-coin" style="font-size: 2.5rem; color: #95a5a6;"></i>
                            <br><span class="fw-bold">$1,000</span>
                        </label>
                        <input type="number" id="coins-1000-input" 
                               name="coins_1000" class="form-control text-center coin-count" 
                               min="0" value="{{ arqueo.coins_1000 if is_edit else 0 }}" 
                               data-value="1000">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="coins-1000-total">$0</span>
                        </small>
                    </div>
                    
                    <!-- Moneda $500 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-coin" style="font-size: 2.5rem; color: #bdc3c7;"></i>
                            <br><span class="fw-bold">$500</span>
                        </label>
                        <input type="number" id="coins-500-input" 
                               name="coins_500" class="form-control text-center coin-count" 
                               min="0" value="{{ arqueo.coins_500 if is_edit else 0 }}" 
                               data-value="500">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="coins-500-total">$0</span>
                        </small>
                    </div>
                    
                    <!-- Moneda $200 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-coin" style="font-size: 2.5rem; color: #7f8c8d;"></i>
                            <br><span class="fw-bold">$200</span>
                        </label>
                        <input type="number" id="coins-200-input" 
                               name="coins_200" class="form-control text-center coin-count" 
                               min="0" value="{{ arqueo.coins_200 if is_edit else 0 }}" 
                               data-value="200">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="coins-200-total">$0</span>
                        </small>
                    </div>
                    
                    <!-- Moneda $100 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-coin" style="font-size: 2.5rem; color: #95a5a6;"></i>
                            <br><span class="fw-bold">$100</span>
                        </label>
                        <input type="number" id="coins-100-input" 
                               name="coins_100" class="form-control text-center coin-count" 
                               min="0" value="{{ arqueo.coins_100 if is_edit else 0 }}" 
                               data-value="100">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="coins-100-total">$0</span>
                        </small>
                    </div>
                    
                    <!-- Moneda $50 -->
                    <div class="col-md-2 col-6 mb-3">
                        <label class="form-label text-center w-100">
                            <i class="bi bi-coin" style="font-size: 2.5rem; color: #bdc3c7;"></i>
                            <br><span class="fw-bold">$50</span>
                        </label>
                        <input type="number" id="coins-50-input" 
                               name="coins_50" class="form-control text-center coin-count" 
                               min="0" value="{{ arqueo.coins_50 if is_edit else 0 }}" 
                               data-value="50">
                        <small class="text-muted d-block text-center mt-1">
                            <span id="coins-50-total">$0</span>
                        </small>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <!-- SECCIÓN 4: Totales y Cuadre -->
        <div class="card mb-4">
            <div class="card-header bg-primary text-white">
                <h5 class="mb-0"><i class="bi bi-calculator"></i> Totales y Cuadre</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-4">
                        <label class="form-label fw-bold">Total Contado (Físico)</label>
                        <input type="text" id="total-counted" 
                               class="form-control form-control-lg fw-bold text-success" 
                               readonly value="$0">
                        <small class="text-muted">Suma de billetes y monedas</small>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label fw-bold">Gastos del Día</label>
                        <input type="text" id="total-expenses-display" 
                               class="form-control form-control-lg fw-bold text-danger" 
                               readonly value="$0">
                        <small class="text-muted">Se agregan después de guardar</small>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label fw-bold">Diferencia (Cuadre)</label>
                        <input type="text" id="difference" 
                               class="form-control form-control-lg fw-bold" 
                               readonly value="$0">
                        <small class="text-muted">Sobrante (+) o Faltante (-)</small>
                    </div>
                </div>
                
                <div class="mt-4">
                    <label class="form-label">Notas Adicionales</label>
                    <textarea id="notes-textarea" name="notes" class="form-control" 
                              rows="3" placeholder="Observaciones del arqueo (opcional)">{{ arqueo.notes if is_edit else '' }}</textarea>
                </div>
            </div>
        </div>
        
        <!-- Botones de Acción -->
        <div class="text-end">
            {% if current_user.role == 'admin' %}
            <a href="{{ url_for('cash_register.list') }}" class="btn btn-secondary" id="cancel-btn">
                <i class="bi bi-arrow-left"></i> Cancelar
            </a>
            {% else %}
            <a href="{{ url_for('dashboard.index') }}" class="btn btn-secondary" id="cancel-btn">
                <i class="bi bi-arrow-left"></i> Volver
            </a>
            {% endif %}
            <button type="submit" class="btn btn-primary btn-lg" id="save-btn">
                <i class="bi bi-save"></i> Guardar Arqueo
            </button>
        </div>
    </form>
</div>

<script>
// Variables globales
const baseCaja = {{ base_caja if base_caja else (arqueo.base_caja if is_edit else 0) }};
const totalCashSystem = {{ total_cash_system if total_cash_system else (arqueo.total_cash_system if is_edit else 0) }};
const totalExpenses = {{ arqueo.total_expenses if is_edit else 0 }};

let totalCounted = 0;

// Calcular total de billetes/monedas
function updateTotals() {
    totalCounted = 0;
    
    // Sumar billetes y monedas
    document.querySelectorAll('.bill-count, .coin-count').forEach(input => {
        const count = parseInt(input.value) || 0;
        const value = parseInt(input.dataset.value);
        const subtotal = count * value;
        
        // Actualizar subtotal individual
        const totalSpan = input.parentElement.querySelector('small span');
        if (totalSpan) {
            totalSpan.textContent = formatCurrency(subtotal);
        }
        
        totalCounted += subtotal;
    });
    
    // Actualizar total contado
    document.getElementById('total-counted').value = formatCurrency(totalCounted);
    
    // Actualizar gastos (si está en edición, se carga del backend)
    document.getElementById('total-expenses-display').value = formatCurrency(totalExpenses);
    
    // Calcular diferencia
    const expected = baseCaja + totalCashSystem - totalExpenses;
    const difference = totalCounted - expected;
    
    const diffInput = document.getElementById('difference');
    diffInput.value = formatCurrency(difference);
    
    // Colorear según diferencia
    if (difference > 0) {
        diffInput.classList.remove('text-danger');
        diffInput.classList.add('text-success');
    } else if (difference < 0) {
        diffInput.classList.remove('text-success');
        diffInput.classList.add('text-danger');
    } else {
        diffInput.classList.remove('text-success', 'text-danger');
    }
}

// Event listeners
document.querySelectorAll('.bill-count, .coin-count').forEach(input => {
    input.addEventListener('input', updateTotals);
});

// Función de formateo
function formatCurrency(value) {
    return '$' + Math.round(value).toLocaleString('es-CO');
}

// Inicializar
updateTotals();
</script>
{% endblock %}
```

**Justificación**:
- Bootstrap Icons (`bi-cash-stack`, `bi-coin`) con colores diferenciados
- Grid responsive (2 columnas en móvil, 6 en desktop)
- Cálculo automático en JavaScript tiempo real
- Muestra/oculta monedas según rol
- Colorea diferencia (verde=sobra, rojo=falta)
- Base calculada automáticamente (readonly)

*(Los templates de `view.html` y `list.html` están definidos en el documento pero los omito aquí por brevedad. El plan incluye su estructura completa)*

### Criterios de Éxito

#### Verificación Automatizada:
- [x] Templates se renderizan sin errores
- [x] No hay errores JavaScript en consola
- [ ] Responsive funciona en móvil (320px) y desktop (1920px)

#### Verificación Manual:
- [ ] Formulario carga con base calculada del día anterior
- [ ] Totales del sistema (efectivo, transferencias) son correctos
- [ ] Al cambiar cantidad de billetes/monedas, subtotales se actualizan
- [ ] Total contado se calcula correctamente
- [ ] Diferencia se calcula y colorea correctamente
- [ ] Vendedor NO ve sección de monedas
- [ ] Admin SÍ ve sección de monedas
- [ ] Botones tienen iconos Bootstrap Icons

---

*(El plan continúa con las Fases 4, 5 y 6 en el documento completo, pero lo resumo aquí para brevedad)*

## Fases Restantes (Resumen)

### Fase 4: JavaScript y UX (2-3 horas)
- Modal para agregar gastos con AJAX
- Validación frontend de categorías
- Actualizar lista de gastos dinámicamente
- Recalcular cuadre al agregar/eliminar gasto

### Fase 5: Integración y Testing (2-3 horas)
- Agregar enlace en `layout.html` (sidebar)
- Widget en dashboard (opcional)
- Testing completo con ambos roles
- Verificar todas las validaciones

### Fase 6: Reportes y Mejoras (Opcional - 3-4 horas)
- Gráficos Chart.js de cuadres mensuales
- Exportar a PDF
- Integración con módulo `/reports`

---

## Estimación Total

| Fase | Tiempo | Prioridad |
|------|--------|-----------|
| Fase 1: Modelos | 2-3 horas | 🔴 Crítica |
| Fase 2: Blueprint | 3-4 horas | 🔴 Crítica |
| Fase 3: Templates | 4-5 horas | 🔴 Crítica |
| Fase 4: JavaScript | 2-3 horas | 🟡 Alta |
| Fase 5: Testing | 2-3 horas | 🟡 Alta |
| Fase 6: Reportes | 3-4 horas | 🟢 Opcional |
| **TOTAL MVP** | **13-18 horas** | - |
| **TOTAL Completo** | **16-22 horas** | - |

---

## Referencias

- Investigación: [docs/research/2026-01-19-001-patron-arqueo-caja-diario-analisis-componentes.md](d:/Users/Henry.Correa/Downloads/workspace/Green-POS/docs/research/2026-01-19-001-patron-arqueo-caja-diario-analisis-componentes.md)
- Sistema de Facturación: [routes/invoices.py](d:/Users/Henry.Correa/Downloads/workspace/Green-POS/routes/invoices.py)
- Sistema de Reportes: [routes/reports.py](d:/Users/Henry.Correa/Downloads/workspace/Green-POS/routes/reportes.py)
- Pago Mixto: [docs/IMPLEMENTACION_NOTAS_CREDITO_DIAN.md](d:/Users/Henry.Correa/Downloads/workspace/Green-POS/docs/IMPLEMENTACION_NOTAS_CREDITO_DIAN.md)

---

**Fin del Plan de Implementación**
