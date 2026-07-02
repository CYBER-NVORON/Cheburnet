from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy, QStyle, QStyleOption, QWidget


class FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 10) -> None:
        super().__init__(parent)
        self._items: list[QLayout.Item] = []  # type: ignore[name-defined]
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item) -> None:  # type: ignore[override]
        self._items.append(item)

    def count(self) -> int:  # type: ignore[override]
        return len(self._items)

    def itemAt(self, index: int):  # type: ignore[override]
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:  # type: ignore[override]
        return Qt.Orientations()

    def hasHeightForWidth(self) -> bool:  # type: ignore[override]
        return True

    def heightForWidth(self, width: int) -> int:  # type: ignore[override]
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # type: ignore[override]
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # type: ignore[override]
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0
        for item in self._items:
            widget = item.widget()
            space_x = self.spacing()
            space_y = self.spacing()
            if widget:
                style = widget.style()
                option = QStyleOption()
                option.initFrom(widget)
                space_x = style.layoutSpacing(QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton, Qt.Orientation.Horizontal, option, widget)
                space_y = style.layoutSpacing(QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton, Qt.Orientation.Vertical, option, widget)
                if space_x < 0:
                    space_x = self.spacing()
                if space_y < 0:
                    space_y = self.spacing()
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y() + margins.bottom()
