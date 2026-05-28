from __future__ import annotations

import sys

from cheburnet.app.core.system import IS_WINDOWS, is_admin, relaunch_as_admin


def _request_admin_at_startup() -> None:
    if not IS_WINDOWS or is_admin() or "--no-admin" in sys.argv:
        return
    try:
        relaunch_as_admin()
    except RuntimeError:
        return
    raise SystemExit(0)


def main() -> None:
    _request_admin_at_startup()

    from PySide6.QtWidgets import QApplication

    from cheburnet.app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    font = app.font()
    if font.pointSize() <= 0:
        font.setPointSize(10)
        app.setFont(font)
    app.setApplicationName("CheburNet")
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())


__all__ = ["main"]
