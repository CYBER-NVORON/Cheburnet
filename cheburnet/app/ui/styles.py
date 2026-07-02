from __future__ import annotations

from cheburnet.app.ui.resources import app_asset_path
from cheburnet.app.ui.theme import apply_theme


def build_qss(theme_key: str | None = None) -> str:
    c = apply_theme(theme_key)
    chevron = app_asset_path("icons", "chevron-down.svg").as_posix()
    check = app_asset_path("icons", "check.svg").as_posix()
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
    QScrollArea#pageScroll, QScrollArea#pageScroll > QWidget, QScrollArea#pageScroll > QWidget > QWidget {{
        background: {c["bg"]};
        border: 0;
    }}
    QFrame#sidebar {{
        background: {c["sidebar"]};
        border-right: 1px solid {c["border"]};
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
    QPushButton, QToolButton {{
        background: {c["card_inner"]};
        border: 1px solid {c["border"]};
        border-radius: 15px;
        padding: 11px 16px;
        font-weight: 700;
        min-height: 24px;
    }}
    QPushButton:hover, QToolButton:hover {{
        border-color: {c["accent"]};
        background: {c["hover"]};
    }}
    QPushButton:pressed, QToolButton:pressed {{
        background: {c["border"]};
    }}
    QPushButton:disabled {{
        color: #66718E;
        background: {c["input"]};
        border-color: {c["border"]};
    }}
    QPushButton#primary {{
        background: {c["accent"]};
        border-color: {c["accent"]};
    }}
    QPushButton#primary:hover {{
        background: {c["hover"]};
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
        color: {c["text"]};
    }}
    QPushButton#navButton[active="true"] {{
        background: {c["accent"]};
        border-color: {c["accent"]};
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
        background: {c["input"]};
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
        border-left: 1px solid {c["border"]};
        border-top-right-radius: 12px;
        border-bottom-right-radius: 12px;
        background: {c["card_inner"]};
    }}
    QComboBox::drop-down:hover {{
        background: {c["hover"]};
    }}
    QComboBox::down-arrow {{
        image: url("{chevron}");
        width: 12px;
        height: 8px;
        margin-right: 11px;
    }}
    QTreeWidget, QTableWidget, QListWidget {{
        background: transparent;
        border: 0;
        outline: 0;
        gridline-color: {c["border"]};
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
        background: {c["card_inner"]};
        border: 0;
        border-bottom: 1px solid {c["border"]};
        color: {c["muted"]};
        font-weight: 700;
        padding: 8px;
    }}
    QProgressBar {{
        background: {c["input"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        min-height: 10px;
        max-height: 10px;
    }}
    QProgressBar::chunk {{
        background: {c["accent2"]};
        border-radius: 8px;
    }}
    QScrollBar:vertical {{
        width: 10px;
        background: transparent;
    }}
    QScrollBar::handle:vertical {{
        background: {c["border"]};
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
        background: {c["input"]};
    }}
    QCheckBox::indicator:hover {{
        border-color: {c["accent"]};
        background: {c["hover"]};
    }}
    QCheckBox::indicator:checked {{
        background: {c["accent"]};
        border-color: {c["accent"]};
        image: url("{check}");
    }}
    QCheckBox::indicator:checked:hover {{
        background: {c["hover"]};
    }}
    QLabel#updateIcon {{
        font-size: 34px;
        font-weight: 900;
        min-width: 52px;
        max-width: 52px;
        min-height: 52px;
        max-height: 52px;
        border-radius: 16px;
        qproperty-alignment: AlignCenter;
        background: rgba(94, 240, 170, 0.12);
        border: 1px solid rgba(94, 240, 170, 0.45);
        color: {c["accent2"]};
    }}
    QLabel#updateIcon[status="warn"] {{
        background: rgba(255, 209, 102, 0.13);
        border-color: rgba(255, 209, 102, 0.48);
        color: {c["warning"]};
    }}
    QLabel#updateIcon[status="error"] {{
        background: rgba(255, 85, 115, 0.13);
        border-color: rgba(255, 85, 115, 0.48);
        color: {c["danger"]};
    }}
    QLabel#updateTitle {{
        font-size: 17px;
        font-weight: 900;
    }}
    QLabel#updateVersion {{
        font-size: 22px;
        font-weight: 900;
    }}
    QLabel#miniLabel {{
        color: {c["muted"]};
        font-size: 12px;
        font-weight: 800;
    }}
    """
