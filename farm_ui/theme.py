"""Qt stylesheet"""

STYLESHEET = """
QWidget {
    background-color: #12121A;
    color: #E0E0E8;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
/* Disabled state, generic fallback — every widget below that sets its own explicit `color`
   needs its OWN :disabled variant too (a stylesheet color rule always wins over Qt's normal
   automatic disabled-palette dimming, for that exact selector), but this catches anything
   plain (e.g. a bare QLabel with no [class=...] tag) that doesn't have a more specific rule. */
QWidget:disabled { color: #4A4A5A; }
QGroupBox {
    border: 1px solid #2A2A3A;
    border-radius: 5px;
    margin-top: 10px;
    padding-top: 8px;
    font-size: 11px;
    color: #888899;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    color: #888899;
}
QLabel[class="app-title"] {
    font-size: 18px;
    font-weight: bold;
    color: #FF6B1A;
    letter-spacing: 1px;
}
QLabel[class="app-subtitle"] {
    font-size: 10px;
    color: #888899;
    letter-spacing: 2px;
}
QLabel[class="section-label"] {
    font-size: 10px;
    font-weight: bold;
    color: #FF6B1A;
    letter-spacing: 2px;
}
QLabel[class="small-label"] {
    font-size: 11px;
    color: #777788;
}
QLabel[class="small-label"]:disabled { color: #45454F; }
QLabel[class="status-label"] {
    font-size: 11px;
    color: #AAAACC;
    padding: 6px 8px;
    background-color: #1C1C28;
    border-radius: 4px;
}
QFrame[class="separator"] {
    background-color: #2A2A3A;
    max-height: 1px;
    border: none;
}
QPushButton {
    background-color: #2A2A3A;
    color: #C0C0D0;
    border: 1px solid #3A3A4E;
    border-radius: 5px;
    padding: 6px 12px;
    font-size: 12px;
}
QPushButton:hover { background-color: #34344A; color: #E0E0F0; }
QPushButton:pressed { background-color: #202030; }
QPushButton:disabled { color: #444458; background-color: #1A1A26; border-color: #242434; }
QPushButton[class="primary-btn"] {
    background-color: #FF6B1A;
    color: #FFFFFF;
    font-weight: bold;
    border: none;
}
QPushButton[class="primary-btn"]:hover { background-color: #FF7F35; }
QPushButton[class="primary-btn"]:pressed { background-color: #E05510; }
QPushButton[class="primary-btn"]:disabled { background-color: #5A2A10; color: #886655; }
QPushButton[class="danger-btn"] {
    background-color: #3A1A1A;
    color: #FF6666;
    border: 1px solid #5A2A2A;
    font-weight: bold;
}
QPushButton[class="danger-btn"]:hover { background-color: #4A2020; }
QPushButton[class="danger-btn"]:disabled { color: #553333; border-color: #332222; }
QTextEdit {
    background-color: #0E0E18;
    color: #C8C8D8;
    border: 1px solid #2A2A3A;
    border-radius: 4px;
    font-family: Consolas, monospace;
    font-size: 11px;
}
QSpinBox {
    background-color: #1C1C28;
    color: #E0E0E8;
    border: 1px solid #3A3A4E;
    border-radius: 4px;
    padding: 3px 6px;
}
QSpinBox:disabled { background-color: #16161D; color: #4A4A5A; border-color: #24242E; }
QSpinBox::up-button, QSpinBox::down-button { background-color: #2A2A3A; border: none; width: 16px; }
QLineEdit {
    background-color: #1C1C28;
    color: #E0E0E8;
    border: 1px solid #3A3A4E;
    border-radius: 4px;
    padding: 3px 6px;
}
QLineEdit:disabled { background-color: #16161D; color: #4A4A5A; border-color: #24242E; }
QComboBox {
    background-color: #1C1C28;
    color: #E0E0E8;
    border: 1px solid #3A3A4E;
    border-radius: 4px;
    padding: 3px 6px;
}
QComboBox:disabled { background-color: #16161D; color: #4A4A5A; border-color: #24242E; }
QComboBox QAbstractItemView {
    background-color: #1C1C28;
    color: #E0E0E8;
    selection-background-color: #FF6B1A;
}
QTabWidget::pane { border: 1px solid #2A2A3A; border-radius: 5px; top: -1px; }
QTabBar::tab {
    background: #1C1C28;
    color: #888899;
    padding: 6px 18px;
    border: 1px solid #2A2A3A;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}
QTabBar::tab:selected { color: #FF6B1A; background: #12121A; }
QTabBar::tab:hover { color: #E0E0F0; }
QCheckBox { spacing: 7px; color: #C0C0D0; }
QCheckBox:disabled { color: #4A4A5A; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #3A3A4E;
    border-radius: 3px;
    background-color: #1C1C28;
}
QCheckBox::indicator:checked { background-color: #FF6B1A; border-color: #FF6B1A; }
QCheckBox::indicator:hover { border-color: #FF6B1A; }
QCheckBox::indicator:disabled { background-color: #16161D; border-color: #24242E; }
QCheckBox::indicator:checked:disabled { background-color: #5A2A10; border-color: #5A2A10; }
QRadioButton { spacing: 7px; color: #C0C0D0; }
QRadioButton::indicator {
    width: 14px; height: 14px;
    border: 1px solid #3A3A4E;
    border-radius: 7px;
    background-color: #1C1C28;
}
QRadioButton::indicator:checked { background-color: #FF6B1A; border-color: #FF6B1A; }
QRadioButton::indicator:hover { border-color: #FF6B1A; }
QScrollBar:vertical { background: #12121A; width: 8px; border: none; }
QScrollBar::handle:vertical { background: #3A3A4E; border-radius: 4px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #FF6B1A; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""
