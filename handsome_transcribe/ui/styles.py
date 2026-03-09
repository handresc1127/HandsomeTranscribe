"""
QSS stylesheet for HandsomeTranscribe desktop application.

Color scheme:
- Primary: #27ae60 (green) - success, recording
- Secondary: #3498db (blue) - info, interactive
- Warning: #f39c12 (orange) - review, pending
- Danger: #e74c3c (red) - errors, stop
- Neutral: #95a5a6 (gray) - disabled, secondary text
- Dark: #2c3e50 (dark blue-gray) - backgrounds
- Light: #ecf0f1 (light gray) - borders, separators
"""

def get_stylesheet():
    """Return main QSS stylesheet for HandsomeTranscribe."""
    return """
    /* === MAIN WINDOW === */
    QMainWindow {
        background-color: #34495e;
        color: #ecf0f1;
    }
    
    QWidget {
        background-color: #34495e;
        color: #ecf0f1;
    }
    
    /* === MENU BAR === */
    QMenuBar {
        background-color: #2c3e50;
        color: #ecf0f1;
        border-bottom: 1px solid #1a252f;
    }
    
    QMenuBar::item:selected {
        background-color: #3498db;
    }
    
    QMenu {
        background-color: #2c3e50;
        color: #ecf0f1;
        border: 1px solid #1a252f;
    }
    
    QMenu::item:selected {
        background-color: #3498db;
    }
    
    /* === STATUS BAR === */
    QStatusBar {
        background-color: #2c3e50;
        color: #ecf0f1;
        border-top: 1px solid #1a252f;
    }
    
    /* === TABS === */
    QTabWidget::pane {
        border: none;
    }
    
    QTabBar::tab {
        background-color: #2c3e50;
        color: #bdc3c7;
        padding: 8px 20px;
        border: none;
    }
    
    QTabBar::tab:selected {
        background-color: #3498db;
        color: white;
    }
    
    QTabBar::tab:hover {
        background-color: #34495e;
    }
    
    /* === LABELS === */
    QLabel {
        color: #ecf0f1;
    }
    
    /* === LINE EDITS === */
    QLineEdit {
        background-color: #2c3e50;
        color: #ecf0f1;
        border: 1px solid #7f8c8d;
        border-radius: 3px;
        padding: 5px;
    }
    
    QLineEdit:focus {
        border: 2px solid #3498db;
    }
    
    QLineEdit:disabled {
        background-color: #34495e;
        color: #95a5a6;
    }
    
    /* === TEXT EDITS === */
    QTextEdit {
        background-color: #2c3e50;
        color: #ecf0f1;
        border: 1px solid #7f8c8d;
        border-radius: 3px;
        padding: 5px;
    }
    
    QTextEdit:focus {
        border: 2px solid #3498db;
    }
    
    QPlainTextEdit {
        background-color: #2c3e50;
        color: #ecf0f1;
        border: 1px solid #7f8c8d;
        border-radius: 3px;
        padding: 5px;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 10px;
    }
    
    QPlainTextEdit:focus {
        border: 2px solid #3498db;
    }
    
    /* === COMBO BOXES === */
    QComboBox {
        background-color: #2c3e50;
        color: #ecf0f1;
        border: 1px solid #7f8c8d;
        border-radius: 3px;
        padding: 5px;
    }
    
    QComboBox:focus {
        border: 2px solid #3498db;
    }
    
    QComboBox::drop-down {
        border: none;
    }
    
    QComboBox QAbstractItemView {
        background-color: #2c3e50;
        color: #ecf0f1;
        selection-background-color: #3498db;
    }
    
    /* === SPIN BOXES === */
    QSpinBox {
        background-color: #2c3e50;
        color: #ecf0f1;
        border: 1px solid #7f8c8d;
        border-radius: 3px;
        padding: 5px;
    }
    
    /* === CHECKBOXES === */
    QCheckBox {
        color: #ecf0f1;
    }
    
    QCheckBox::indicator:checked {
        background-color: #27ae60;
        border: 1px solid #27ae60;
    }
    
    QCheckBox::indicator:unchecked {
        background-color: #2c3e50;
        border: 1px solid #7f8c8d;
    }
    
    /* === PUSH BUTTONS === */
    QPushButton {
        background-color: #3498db;
        color: white;
        border: none;
        border-radius: 3px;
        padding: 10px 20px;
        font-weight: bold;
    }
    
    QPushButton:hover {
        background-color: #2980b9;
    }
    
    QPushButton:pressed {
        background-color: #1f618d;
    }
    
    QPushButton:disabled {
        background-color: #95a5a6;
        color: #7f8c8d;
    }
    
    /* === BUTTON VARIATIONS === */
    QPushButton[success="true"] {
        background-color: #27ae60;
    }
    
    QPushButton[success="true"]:hover {
        background-color: #229954;
    }
    
    QPushButton[danger="true"] {
        background-color: #e74c3c;
    }
    
    QPushButton[danger="true"]:hover {
        background-color: #c0392b;
    }
    
    QPushButton[warning="true"] {
        background-color: #f39c12;
    }
    
    QPushButton[warning="true"]:hover {
        background-color: #e67e22;
    }
    
    /* === GROUP BOXES === */
    QGroupBox {
        color: #ecf0f1;
        border: 1px solid #7f8c8d;
        border-radius: 3px;
        margin-top: 8px;
        padding-top: 8px;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }
    
    /* === LIST WIDGETS === */
    QListWidget {
        background-color: #2c3e50;
        color: #ecf0f1;
        border: 1px solid #7f8c8d;
        border-radius: 3px;
    }
    
    QListWidget::item {
        padding: 8px;
        border-bottom: 1px solid #34495e;
    }
    
    QListWidget::item:selected {
        background-color: #3498db;
        color: white;
    }
    
    QListWidget::item:hover {
        background-color: #34495e;
    }
    
    /* === TABLE WIDGETS === */
    QTableWidget {
        background-color: #2c3e50;
        color: #ecf0f1;
        border: 1px solid #7f8c8d;
        border-radius: 3px;
        gridline-color: #34495e;
    }
    
    QTableWidget::item {
        padding: 8px;
        border-bottom: 1px solid #34495e;
    }
    
    QTableWidget::item:selected {
        background-color: #3498db;
        color: white;
    }
    
    QHeaderView::section {
        background-color: #2c3e50;
        color: #ecf0f1;
        padding: 5px;
        border: none;
        border-right: 1px solid #7f8c8d;
        border-bottom: 1px solid #7f8c8d;
    }
    
    /* === SCROLL BARS === */
    QScrollBar:vertical {
        background-color: #34495e;
        width: 12px;
        border: none;
    }
    
    QScrollBar::handle:vertical {
        background-color: #7f8c8d;
        border-radius: 6px;
        min-height: 20px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #95a5a6;
    }
    
    QScrollBar:horizontal {
        background-color: #34495e;
        height: 12px;
        border: none;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #7f8c8d;
        border-radius: 6px;
        min-width: 20px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #95a5a6;
    }
    
    /* === PROGRESS BARS === */
    QProgressBar {
        background-color: #2c3e50;
        color: #ecf0f1;
        border: 1px solid #7f8c8d;
        border-radius: 3px;
        text-align: center;
    }
    
    QProgressBar::chunk {
        background-color: #27ae60;
    }
    
    /* === DIALOGS === */
    QDialog {
        background-color: #34495e;
        color: #ecf0f1;
    }
    
    QMessageBox {
        background-color: #34495e;
    }
    
    QMessageBox QLabel {
        color: #ecf0f1;
    }
    """


def apply_stylesheet(app):
    """Apply HandsomeTranscribe stylesheet to QApplication."""
    app.setStyle("Fusion")
    app.setStyleSheet(get_stylesheet())
