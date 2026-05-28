from __future__ import annotations

from cheburnet.app.core.paths import app_root
from cheburnet.app.ui.theme import COLORS


def build_qss() -> str:
    c = COLORS
    chevron = (app_root() / "cheburnet" / "app" / "assets" / "icons" / "chevron-down.svg").as_posix()
    check = (app_root() / "cheburnet" / "app" / "assets" / "icons" / "check.svg").as_posix()
    return f"""
    * {{
        font-family: "Segoe UI", "Inter", Arial, sans-serif;
        font-size: 14px;
        letter-spacing: 0px;
        color: {c["text"]};
    }}
    QMainWindow, QWidget#root, QWidget#page {{
        background: {c["bg"]};
    }}
    QFrame#sidebar {{
        background: {c["sidebar"]};
        border-right: 1px solid #1C2547;
    }}
    QLabel#brand {{
        font-size: 20px;
        font-weight: 800;
    }}
    QLabel#pageTitle {{
        font-size: 26px;
        font-weight: 800;
    }}
    QLabel#cardTitle {{
        font-size: 18px;
        font-weight: 800;
    }}
    QLabel#muted, QLabel.muted {{
        color: {c["muted"]};
    }}
    QLabel#metric {{
        font-size: 22px;
        font-weight: 800;
    }}
    QLabel#bigStatus {{
        font-size: 24px;
        font-weight: 900;
    }}
    QFrame#glassCard, QFrame#statCard {{
        background: {c["card"]};
        border: 1px solid {c["border"]};
        border-radius: 20px;
    }}
    QFrame#innerPanel {{
        background: {c["card_inner"]};
        border: 1px solid {c["border"]};
        border-radius: 16px;
    }}
    QPushButton {{
        background: {c["card_inner"]};
        border: 1px solid {c["border"]};
        border-radius: 15px;
        padding: 11px 16px;
        font-weight: 700;
        min-height: 24px;
    }}
    QPushButton:hover {{
        border-color: {c["accent"]};
        background: #202A50;
    }}
    QPushButton:pressed {{
        background: #263160;
    }}
    QPushButton:disabled {{
        color: #66718E;
        background: #10172D;
        border-color: #1B2442;
    }}
    QPushButton#primary {{
        background: {c["accent"]};
        border-color: #9B85FF;
    }}
    QPushButton#primary:hover {{
        background: #8D72FF;
    }}
    QPushButton#danger {{
        background: rgba(255, 77, 109, 0.18);
        border-color: {c["danger"]};
        color: #FFD5DD;
    }}
    QPushButton#navButton {{
        text-align: left;
        padding: 14px 18px;
        border-radius: 12px;
        background: transparent;
        border: 1px solid transparent;
        color: #C9D3F5;
    }}
    QPushButton#navButton[active="true"] {{
        background: {c["accent"]};
        border-color: #8E79FF;
        color: #FFFFFF;
    }}
    QLabel#statusPill {{
        border-radius: 14px;
        padding: 6px 12px;
        font-weight: 800;
        background: rgba(124, 92, 255, 0.18);
        border: 1px solid rgba(124, 92, 255, 0.45);
    }}
    QLabel#statusPill[status="ok"] {{
        background: rgba(47, 230, 160, 0.14);
        border-color: rgba(47, 230, 160, 0.55);
        color: {c["accent2"]};
    }}
    QLabel#statusPill[status="error"] {{
        background: rgba(255, 77, 109, 0.14);
        border-color: rgba(255, 77, 109, 0.55);
        color: {c["danger"]};
    }}
    QLabel#statusPill[status="warn"] {{
        background: rgba(255, 200, 87, 0.14);
        border-color: rgba(255, 200, 87, 0.55);
        color: {c["warning"]};
    }}
    QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {{
        background: #0D1430;
        border: 1px solid {c["border"]};
        border-radius: 12px;
        padding: 9px 12px;
        selection-background-color: {c["accent"]};
    }}
    QComboBox {{
        padding-right: 38px;
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 34px;
        border-left: 1px solid #22305D;
        border-top-right-radius: 12px;
        border-bottom-right-radius: 12px;
        background: #111936;
    }}
    QComboBox::drop-down:hover {{
        background: #18213D;
    }}
    QComboBox::down-arrow {{
        image: url("{chevron}");
        width: 12px;
        height: 8px;
    }}
    QTreeWidget, QTableWidget, QListWidget {{
        background: transparent;
        border: 0;
        outline: 0;
        gridline-color: #22305D;
        alternate-background-color: rgba(255, 255, 255, 0.025);
    }}
    QTreeWidget::item, QTableWidget::item, QListWidget::item {{
        min-height: 38px;
        padding: 6px;
        border: 0;
    }}
    QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
        background: rgba(47, 230, 160, 0.14);
        color: #FFFFFF;
    }}
    QHeaderView::section {{
        background: #111936;
        border: 0;
        border-bottom: 1px solid {c["border"]};
        color: {c["muted"]};
        font-weight: 700;
        padding: 8px;
    }}
    QScrollBar:vertical {{
        width: 10px;
        background: transparent;
    }}
    QScrollBar::handle:vertical {{
        background: #2B386A;
        border-radius: 5px;
    }}
    QCheckBox {{
        spacing: 10px;
        color: {c["text"]};
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 6px;
        border: 1px solid {c["border"]};
        background: #0D1430;
    }}
    QCheckBox::indicator:hover {{
        border-color: {c["accent"]};
        background: #172040;
    }}
    QCheckBox::indicator:checked {{
        background: {c["accent"]};
        border-color: #A18EFF;
        image: url("{check}");
    }}
    QCheckBox::indicator:checked:hover {{
        background: #8D72FF;
    }}
    """
