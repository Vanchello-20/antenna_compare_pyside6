import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen, QBrush, QPolygonF
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
)


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "antennas.json"
ICON_FILE = APP_DIR / "antenna_communication_icon-icons.com_67285.ico"


@dataclass
class Antenna:
    raw: dict

    @property
    def name(self):
        return self.raw.get("name", "Без названия")

    @property
    def category(self):
        return self.raw.get("category", "Без категории")

    @property
    def rating(self):
        return self.raw.get("rating", {})


def load_data():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Не найден файл базы данных: {DATA_FILE}")

    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    antennas = [Antenna(x) for x in data.get("antennas", [])]
    if len(antennas) < 2:
        raise ValueError("В базе должно быть минимум две антенны для сравнения.")
    return data, antennas


def value_text(value):
    if isinstance(value, list):
        return "; ".join(map(str, value))
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


class RadarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.left = None
        self.right = None
        self.setMinimumHeight(264)

    def set_antennas(self, left: Antenna, right: Antenna):
        self.left = left
        self.right = right
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(24, 24, -24, -24)
        center = QPointF(rect.center())
        radius = min(rect.width(), rect.height()) / 2 - 42

        axes = [
            ("Усиление", "gain"),
            ("Полоса", "bandwidth"),
            ("Компактность", "compactness"),
            ("Решётки", "array"),
            ("Спутн. связь", "satcom"),
            ("Сложность", "complexity"),
        ]

        grid_pen = QPen(QColor("#374151"), 1)
        text_pen = QPen(QColor("#E5E7EB"))
        left_pen = QPen(QColor("#60A5FA"), 2)
        right_pen = QPen(QColor("#F59E0B"), 2)

        painter.setPen(grid_pen)

        for level in range(1, 6):
            pts = []
            r = radius * level / 5
            for i in range(len(axes)):
                angle = -math.pi / 2 + 2 * math.pi * i / len(axes)
                pts.append(QPointF(center.x() + r * math.cos(angle), center.y() + r * math.sin(angle)))
            for i in range(len(pts)):
                painter.drawLine(pts[i], pts[(i + 1) % len(pts)])

        for i, (title, key) in enumerate(axes):
            angle = -math.pi / 2 + 2 * math.pi * i / len(axes)
            end = QPointF(center.x() + radius * math.cos(angle), center.y() + radius * math.sin(angle))
            label = QPointF(center.x() + (radius + 22) * math.cos(angle), center.y() + (radius + 22) * math.sin(angle))
            painter.drawLine(center, end)
            painter.setPen(text_pen)
            painter.drawText(QRectF(label.x() - 55, label.y() - 12, 110, 24), Qt.AlignCenter, title)
            painter.setPen(grid_pen)

        def draw_rating(antenna, pen, fill):
            if not antenna:
                return
            pts = []
            for i, (_, key) in enumerate(axes):
                value = max(0, min(5, int(antenna.rating.get(key, 0))))
                r = radius * value / 5
                angle = -math.pi / 2 + 2 * math.pi * i / len(axes)
                pts.append(QPointF(center.x() + r * math.cos(angle), center.y() + r * math.sin(angle)))

            painter.setPen(pen)
            painter.setBrush(fill)
            polygon = pts + [pts[0]]
            for i in range(len(pts)):
                painter.drawLine(polygon[i], polygon[i + 1])

        draw_rating(self.left, left_pen, QBrush(QColor(96, 165, 250, 35)))
        draw_rating(self.right, right_pen, QBrush(QColor(245, 158, 11, 35)))

        painter.setPen(QPen(QColor("#9CA3AF")))
        #painter.drawText(12, self.height() - 30, "Чем больше площадь, тем лучше параметр. Кроме сложности: 5 = сложнее.")
        painter.end()


class RadiationPattern3DWidget(QWidget):
    def __init__(self, color="#60A5FA", parent=None):
        super().__init__(parent)
        self.antenna = None
        self.base_color = QColor(color)
        self.yaw = math.radians(-36)
        self.pitch = math.radians(58)
        self.zoom = 1.0
        self.last_mouse_pos = None
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Левая кнопка мыши: вращение; колесо: масштаб")

    def set_antenna(self, antenna: Antenna):
        self.antenna = antenna
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0B1220"))

        if not self.antenna:
            painter.setPen(QPen(QColor("#94A3B8")))
            painter.drawText(self.rect(), Qt.AlignCenter, "Нет данных")
            painter.end()
            return

        rect = self.rect().adjusted(18, 18, -18, -18)
        center = QPointF(rect.center().x(), rect.center().y() + rect.height() * 0.04)
        scale = min(rect.width(), rect.height()) * 0.34 * self.zoom

        self._draw_axes(painter, center, scale)

        rows = 26
        cols = 42
        projected = []
        for row in range(rows + 1):
            theta = math.pi * row / rows
            line = []
            for col in range(cols + 1):
                phi = 2 * math.pi * col / cols
                r = self._pattern_value(theta, phi)
                x = r * math.sin(theta) * math.cos(phi)
                y = r * math.sin(theta) * math.sin(phi)
                z = r * math.cos(theta)
                point, depth = self._project(x, y, z, center, scale)
                line.append((point, depth, r))
            projected.append(line)

        cells = []
        for row in range(rows):
            for col in range(cols):
                p1 = projected[row][col]
                p2 = projected[row][col + 1]
                p3 = projected[row + 1][col + 1]
                p4 = projected[row + 1][col]
                depth = (p1[1] + p2[1] + p3[1] + p4[1]) / 4
                value = (p1[2] + p2[2] + p3[2] + p4[2]) / 4
                cells.append((depth, value, QPolygonF([p1[0], p2[0], p3[0], p4[0]])))

        cells.sort(key=lambda item: item[0])
        mesh_pen = QPen(QColor(15, 23, 42, 90), 1)
        for depth, value, polygon in cells:
            painter.setPen(mesh_pen)
            painter.setBrush(QBrush(self._surface_color(value, depth)))
            painter.drawPolygon(polygon)

        self._draw_axes(painter, center, scale)
        painter.end()

    def _project(self, x, y, z, center, scale):
        x1 = x * math.cos(self.yaw) - y * math.sin(self.yaw)
        y1 = x * math.sin(self.yaw) + y * math.cos(self.yaw)
        z1 = z

        y2 = y1 * math.cos(self.pitch) - z1 * math.sin(self.pitch)
        z2 = y1 * math.sin(self.pitch) + z1 * math.cos(self.pitch)

        return QPointF(center.x() + x1 * scale, center.y() - y2 * scale), z2

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.last_mouse_pos is None or not event.buttons() & Qt.MouseButton.LeftButton:
            super().mouseMoveEvent(event)
            return

        pos = event.position()
        delta = pos - self.last_mouse_pos
        self.last_mouse_pos = pos

        self.yaw += delta.x() * 0.01
        self.pitch = max(math.radians(-78), min(math.radians(78), self.pitch + delta.y() * 0.01))
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if self.last_mouse_pos is None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().leaveEvent(event)

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120
        if steps:
            self.zoom = max(0.55, min(2.6, self.zoom * (1.12 ** steps)))
            self.update()
            event.accept()
            return
        super().wheelEvent(event)

    def _surface_color(self, value, depth):
        light = max(0.25, min(1.0, 0.48 + value * 0.44 + depth * 0.10))
        color = QColor(
            min(255, int(self.base_color.red() * light + 12)),
            min(255, int(self.base_color.green() * light + 12)),
            min(255, int(self.base_color.blue() * light + 12)),
            205,
        )
        return color

    def _draw_axes(self, painter, center, scale):
        axis_pen = QPen(QColor("#64748B"), 1)
        painter.setPen(axis_pen)
        painter.setBrush(Qt.NoBrush)

        axes = [
            ((1.18, 0, 0), "X"),
            ((0, 1.18, 0), "Y"),
            ((0, 0, 1.18), "Z"),
        ]
        origin, _ = self._project(0, 0, 0, center, scale)
        for (x, y, z), label in axes:
            end, _ = self._project(x, y, z, center, scale)
            painter.drawLine(origin, end)
            painter.drawText(QRectF(end.x() - 10, end.y() - 10, 20, 20), Qt.AlignCenter, label)

    def _pattern_kind(self):
        raw = self.antenna.raw
        params = raw.get("pattern_3d", {})
        if isinstance(params, dict) and params.get("kind"):
            return params.get("kind"), params

        antenna_id = raw.get("id", "")
        category = raw.get("category", "").lower()
        radiation = raw.get("radiation", "").lower()

        if antenna_id in {"half_wave_dipole", "folded_dipole", "slot"}:
            return "dipole", {}
        if antenna_id == "monopole":
            return "monopole", {}
        if antenna_id == "loop":
            return "loop", {}
        if antenna_id in {"biconical", "discone"}:
            return "omni", {}
        if antenna_id in {"microstrip_patch", "planar_phased_array"}:
            return "broadside", {}
        if antenna_id in {"spiral"}:
            return "bidirectional", {}
        if antenna_id in {"hemispherical_conformal_aesa"}:
            return "hemisphere", {}
        if antenna_id in {"cylindrical_conformal_aesa"}:
            return "cylindrical", {}
        if antenna_id in {"sector_panel", "multi_panel_aesa"}:
            return "sector", {}
        if "фазирован" in category or "решёт" in category:
            return "phased", {}
        if "круговая" in radiation or "квазикруговая" in radiation:
            return "omni", {}
        if "двунаправ" in radiation:
            return "bidirectional", {}
        if "широкий broadside" in radiation:
            return "broadside", {}
        if "направ" in radiation or "end-fire" in radiation:
            return "directive", {}
        return "omni", {}

    def _pattern_value(self, theta, phi):
        kind, params = self._pattern_kind()
        power = float(params.get("power", 1.0)) if isinstance(params, dict) else 1.0

        st = math.sin(theta)
        ct = math.cos(theta)
        ux = st * math.cos(phi)
        uy = st * math.sin(phi)

        if kind == "dipole":
            value = abs(st) ** (0.85 * power)
        elif kind == "monopole":
            ground = 1.0 if ct >= -0.05 else 0.22
            value = ground * (abs(st) ** 0.75)
        elif kind == "loop":
            value = 0.70 * (abs(st) ** 1.35) + 0.18 * (abs(math.sin(2 * phi)) * abs(st)) ** 2
        elif kind == "omni":
            value = 0.80 * (abs(st) ** 0.55) + 0.10 * (1 + math.cos(4 * phi)) * abs(st)
        elif kind == "broadside":
            main = max(0.0, ct) ** 3.2
            back = 0.16 * max(0.0, -ct) ** 1.8
            side = 0.10 * (abs(st) ** 2) * (0.5 + 0.5 * math.cos(4 * phi) ** 2)
            value = main + back + side
        elif kind == "bidirectional":
            value = abs(ct) ** 2.2 + 0.12 * abs(st) ** 2
        elif kind == "hemisphere":
            value = max(0.0, ct) ** 0.35 + 0.08 * abs(st) * (1 + 0.3 * math.cos(5 * phi))
        elif kind == "cylindrical":
            value = 0.86 * abs(st) ** 0.45 + 0.10 * (1 + math.cos(6 * phi)) * abs(st)
        elif kind == "sector":
            angle = math.atan2(uy, ux)
            az = max(0.0, math.cos(angle / 1.15)) ** 2.4
            elevation = abs(st) ** 0.65
            value = 0.15 * elevation + 0.85 * az * elevation
        elif kind == "phased":
            scan_x = 0.34
            scan_z = 0.94
            dot = ux * scan_x + ct * scan_z
            main = max(0.0, dot) ** 5.5
            side = 0.13 * (abs(math.sin(4 * phi)) * abs(st)) ** 2
            value = main + side
        else:
            main = max(0.0, ux) ** 7.0
            back = 0.10 * max(0.0, -ux) ** 2.2
            side = 0.16 * (abs(math.sin(2 * phi)) * abs(st)) ** 2
            value = main + back + side

        return max(0.035, min(1.0, value))


class AntennaCard(QFrame):
    def __init__(self, title="Антенна", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")

        self.category = QLabel("—")
        self.category.setObjectName("badge")

        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setObjectName("cardBody")
        self.body.setMinimumHeight(260)

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(self.title)
        top.addStretch(1)
        top.addWidget(self.category)
        layout.addLayout(top)
        layout.addWidget(self.body)

    def set_antenna(self, antenna: Antenna):
        r = antenna.raw
        self.title.setText(antenna.name)
        self.category.setText(antenna.category)
        advantages = "\n".join(f"• {x}" for x in r.get("advantages", []))
        limitations = "\n".join(f"• {x}" for x in r.get("limitations", []))
        applications = "\n".join(f"• {x}" for x in r.get("applications", []))

        html = f"""
        <h3>Основные характеристики</h3>
        <p><b>Усиление:</b> {r.get('gain_dbi', '—')}</p>
        <p><b>Частоты:</b> {r.get('frequency', '—')}</p>
        <p><b>Полоса:</b> {r.get('bandwidth', '—')}</p>
        <p><b>Поляризация:</b> {r.get('polarization', '—')}</p>
        <p><b>Импеданс:</b> {r.get('impedance_ohm', '—')}</p>
        <p><b>КСВН:</b> {r.get('vswr', '—')}</p>
        <p><b>Ширина луча:</b> {r.get('beamwidth_deg', '—')}</p>
        <p><b>Сканирование:</b> {r.get('scan', '—')}</p>
        <h3>Плюсы</h3>
        <p>{advantages}</p>
        <h3>Ограничения</h3>
        <p>{limitations}</p>
        <h3>Применение</h3>
        <p>{applications}</p>
        <h3>Примечание</h3>
        <p>{r.get('notes', '—')}</p>
        """
        self.body.setHtml(html)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data, self.antennas = load_data()
        self.filtered = self.antennas[:]

        self.setWindowTitle("Сравнение антенн")
        if ICON_FILE.exists():
            self.setWindowIcon(QIcon(str(ICON_FILE)))
        self.resize(1420, 860)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по названию, категории, применению...")
        self.search.textChanged.connect(self.refresh_list)

        self.category_filter = QComboBox()
        self.category_filter.addItem("Все категории")
        for cat in sorted({a.category for a in self.antennas}):
            self.category_filter.addItem(cat)
        self.category_filter.currentTextChanged.connect(self.refresh_list)

        self.list_widget = QListWidget()
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setWordWrap(True)
        self.list_widget.itemDoubleClicked.connect(self.pick_from_list)

        self.left_combo = QComboBox()
        self.right_combo = QComboBox()
        for a in self.antennas:
            self.left_combo.addItem(a.name)
            self.right_combo.addItem(a.name)
        self.right_combo.setCurrentIndex(1)
        self.left_combo.currentIndexChanged.connect(self.update_compare)
        self.right_combo.currentIndexChanged.connect(self.update_compare)

        self.left_card = AntennaCard("Антенна 1")
        self.right_card = AntennaCard("Антенна 2")
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Параметр", "Антенна 1", "Антенна 2"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        self.radar = RadarWidget()
        self.left_pattern = RadiationPattern3DWidget("#60A5FA")
        self.right_pattern = RadiationPattern3DWidget("#F59E0B")
        self.conclusion = QTextEdit()
        self.conclusion.setReadOnly(True)
        self.conclusion.setObjectName("conclusion")

        self.build_layout()
        self.apply_style()
        self.refresh_list()
        self.update_compare()

    def build_layout(self):
        root = QWidget()
        main = QHBoxLayout(root)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(360)
        sidebar_layout = QVBoxLayout(sidebar)

        sidebar_layout.addWidget(self.search)
        sidebar_layout.addWidget(self.category_filter)
        sidebar_layout.addWidget(QLabel("База антенн"))
        sidebar_layout.addWidget(self.list_widget, 1)

        radar_group = QGroupBox("Оценочный профиль")
        radar_layout = QVBoxLayout(radar_group)
        radar_layout.addWidget(self.radar)
        sidebar_layout.addWidget(radar_group)

        #hint = QLabel("Двойной щелчок по списку ставит антенну в первый свободный слот сравнения.")
        #hint.setWordWrap(True)
        #hint.setObjectName("hint")
        #sidebar_layout.addWidget(hint)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        header = QFrame()
        header.setObjectName("topbar")
        header_layout = QHBoxLayout(header)
        #title = QLabel("Сравнительная характеристика антенн")
        #title.setObjectName("pageTitle")
        #header_layout.addWidget(title)
        #header_layout.addStretch(1)
        header_layout.addWidget(self.left_combo)
        header_layout.addWidget(self.right_combo)
        content_layout.addWidget(header)

        top = QWidget()
        top_layout = QHBoxLayout(top)

        left_column = QWidget()
        left_column_layout = QVBoxLayout(left_column)
        left_column_layout.addWidget(self.left_card, 2)
        self.left_pattern_group = QGroupBox("Диаграмма направленности 1")
        self.left_pattern_group.setMinimumHeight(340)
        left_pattern_layout = QVBoxLayout(self.left_pattern_group)
        left_pattern_layout.addWidget(self.left_pattern)
        left_column_layout.addWidget(self.left_pattern_group, 1)

        right_column = QWidget()
        right_column_layout = QVBoxLayout(right_column)
        right_column_layout.addWidget(self.right_card, 2)
        self.right_pattern_group = QGroupBox("Диаграмма направленности 2")
        self.right_pattern_group.setMinimumHeight(340)
        right_pattern_layout = QVBoxLayout(self.right_pattern_group)
        right_pattern_layout.addWidget(self.right_pattern)
        right_column_layout.addWidget(self.right_pattern_group, 1)

        top_layout.addWidget(left_column)
        top_layout.addWidget(right_column)
        content_layout.addWidget(top, 1)

        main.addWidget(sidebar)
        main.addWidget(content, 1)
        self.setCentralWidget(root)

    def apply_style(self):
        self.setStyleSheet("""
        QMainWindow, QWidget {
            background: #0F172A;
            color: #E5E7EB;
            font-family: Segoe UI, Arial;
            font-size: 13px;
        }
        #sidebar {
            background: #111827;
            border-right: 1px solid #263244;
        }
        #hint {
            color: #9CA3AF;
            padding: 8px;
        }
        #topbar, #card {
            background: #111827;
            border: 1px solid #263244;
            border-radius: 18px;
        }
        #pageTitle {
            font-size: 22px;
            font-weight: 700;
            color: #F9FAFB;
        }
        #cardTitle {
            font-size: 19px;
            font-weight: 700;
            color: #F9FAFB;
        }
        #badge {
            background: #1E3A8A;
            color: #DBEAFE;
            border-radius: 12px;
            padding: 6px 10px;
            font-weight: 600;
        }
        QTextEdit, QTableWidget, QListWidget, QLineEdit, QComboBox {
            background: #0B1220;
            color: #E5E7EB;
            border: 1px solid #263244;
            border-radius: 12px;
            padding: 8px;
            selection-background-color: #2563EB;
        }
        QComboBox {
            padding: 8px 34px 8px 8px;
        }
        QComboBox::drop-down {
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 34px;
            background: #0B1220;
            border-left: 1px solid #263244;
            border-top-right-radius: 12px;
            border-bottom-right-radius: 12px;
        }
        QComboBox::down-arrow {
            width: 10px;
            height: 10px;
        }
        QScrollBar:vertical {
            background: #0B1220;
            border: 1px solid #263244;
            border-radius: 7px;
            width: 14px;
            margin: 17px 0 17px 0;
        }
        QScrollBar::handle:vertical {
            background: #1F2937;
            border: 1px solid #374151;
            border-radius: 6px;
            min-height: 34px;
        }
        QScrollBar::handle:vertical:hover {
            background: #334155;
        }
        QScrollBar::sub-line:vertical {
            background: #111827;
            border: 1px solid #263244;
            border-top-left-radius: 7px;
            border-top-right-radius: 7px;
            height: 16px;
            subcontrol-origin: margin;
            subcontrol-position: top;
        }
        QScrollBar::add-line:vertical {
            background: #111827;
            border: 1px solid #263244;
            border-bottom-left-radius: 7px;
            border-bottom-right-radius: 7px;
            height: 16px;
            subcontrol-origin: margin;
            subcontrol-position: bottom;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: transparent;
        }
        QScrollBar:horizontal {
            background: #0B1220;
            border: 1px solid #263244;
            border-radius: 7px;
            height: 14px;
            margin: 0 17px 0 17px;
        }
        QScrollBar::handle:horizontal {
            background: #1F2937;
            border: 1px solid #374151;
            border-radius: 6px;
            min-width: 34px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #334155;
        }
        QScrollBar::sub-line:horizontal {
            background: #111827;
            border: 1px solid #263244;
            border-top-left-radius: 7px;
            border-bottom-left-radius: 7px;
            width: 16px;
            subcontrol-origin: margin;
            subcontrol-position: left;
        }
        QScrollBar::add-line:horizontal {
            background: #111827;
            border: 1px solid #263244;
            border-top-right-radius: 7px;
            border-bottom-right-radius: 7px;
            width: 16px;
            subcontrol-origin: margin;
            subcontrol-position: right;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: transparent;
        }
        QTableWidget {
            gridline-color: #263244;
            alternate-background-color: #111827;
        }
        QHeaderView::section {
            background: #1F2937;
            color: #F9FAFB;
            border: 0;
            padding: 8px;
            font-weight: 700;
        }
        QPushButton {
            background: #2563EB;
            color: white;
            border: 0;
            border-radius: 12px;
            padding: 10px 14px;
            font-weight: 700;
        }
        QPushButton:hover {
            background: #1D4ED8;
        }
        QGroupBox {
            border: 1px solid #263244;
            border-radius: 16px;
            margin-top: 16px;
            padding: 12px;
            font-weight: 700;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
            color: #93C5FD;
        }
        QListWidget::item {
            padding: 10px;
            border-radius: 10px;
        }
        QListWidget::item:hover {
            background: #1F2937;
        }
        QListWidget::item:selected {
            background: #2563EB;
        }
        """)

    def refresh_list(self):
        query = self.search.text().lower().strip()
        cat = self.category_filter.currentText()

        self.list_widget.clear()
        self.filtered = []
        for a in self.antennas:
            raw_text = json.dumps(a.raw, ensure_ascii=False).lower()
            if cat != "Все категории" and a.category != cat:
                continue
            if query and query not in raw_text:
                continue
            self.filtered.append(a)
            item = QListWidgetItem(f"{a.name}\n{a.category}")
            item.setData(Qt.UserRole, a.name)
            self.list_widget.addItem(item)

    def pick_from_list(self, item):
        name = item.data(Qt.UserRole)
        left_name = self.left_combo.currentText()
        right_name = self.right_combo.currentText()
        combo = self.right_combo if left_name == name else self.left_combo
        index = combo.findText(name)
        if index >= 0:
            combo.setCurrentIndex(index)

    def by_name(self, name):
        for a in self.antennas:
            if a.name == name:
                return a
        return self.antennas[0]

    def update_compare(self):
        left = self.by_name(self.left_combo.currentText())
        right = self.by_name(self.right_combo.currentText())

        self.left_card.set_antenna(left)
        self.right_card.set_antenna(right)
        self.radar.set_antennas(left, right)
        self.left_pattern.set_antenna(left)
        self.right_pattern.set_antenna(right)
        self.fill_table(left, right)
        self.fill_conclusion(left, right)

    def fill_table(self, left, right):
        fields = [
            ("Категория", "category"),
            ("Усиление", "gain_dbi"),
            ("Рабочий диапазон / частота", "frequency"),
            ("Полоса", "bandwidth"),
            ("Поляризация", "polarization"),
            ("Импеданс", "impedance_ohm"),
            ("КСВН", "vswr"),
            ("Ширина луча", "beamwidth_deg"),
            ("Характер ДН", "radiation"),
            ("Сканирование", "scan"),
            ("Габариты / масштаб", "dimensions"),
            ("Применение", "applications"),
            ("Ограничения", "limitations"),
            ("Примечание", "notes"),
        ]

        self.table.setRowCount(len(fields))
        for row, (label, key) in enumerate(fields):
            values = [
                label,
                value_text(left.raw.get(key, "—")),
                value_text(right.raw.get(key, "—")),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setToolTip(value)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

    def fill_conclusion(self, left, right):
        labels = {
            "gain": "усилению",
            "bandwidth": "полосе",
            "compactness": "компактности",
            "array": "пригодности для решёток",
            "satcom": "пригодности для спутниковой связи",
            "complexity": "сложности",
        }

        lines = []
        score_left = 0
        score_right = 0
        for key, label in labels.items():
            lv = int(left.rating.get(key, 0))
            rv = int(right.rating.get(key, 0))
            if lv > rv:
                winner = left.name
                score_left += 1
            elif rv > lv:
                winner = right.name
                score_right += 1
            else:
                winner = "паритет"
            lines.append(f"• По {label}: {winner} ({lv} / {rv}).")

        if score_left > score_right:
            final = f"Итог: по суммарной экспертной оценке предпочтительнее «{left.name}»."
        elif score_right > score_left:
            final = f"Итог: по суммарной экспертной оценке предпочтительнее «{right.name}»."
        else:
            final = "Итог: варианты близки по суммарной экспертной оценке, выбор зависит от условий установки."

        caution = (
            "Оценки являются типовыми. Для дипломного расчёта их нужно уточнять через частоту, "
            "апертуру, шаг элементов, КПД, диаграмму одиночного излучателя и условия размещения."
        )
        self.conclusion.setPlainText("\n".join(lines) + "\n\n" + final + "\n\n" + caution)

    def export_txt(self):
        left = self.by_name(self.left_combo.currentText())
        right = self.by_name(self.right_combo.currentText())
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт", "antenna_compare_report.txt", "Text files (*.txt)")
        if not path:
            return

        lines = [
            "СРАВНИТЕЛЬНЫЙ ОТЧЁТ ПО АНТЕННАМ",
            "=" * 42,
            f"Антенна 1: {left.name}",
            f"Антенна 2: {right.name}",
            "",
            "Табличное сравнение:",
        ]
        for row in range(self.table.rowCount()):
            p = self.table.item(row, 0).text()
            l = self.table.item(row, 1).text()
            r = self.table.item(row, 2).text()
            lines.append(f"\n{p}\n  {left.name}: {l}\n  {right.name}: {r}")
        lines.append("\nВывод:")
        lines.append(self.conclusion.toPlainText())

        Path(path).write_text("\n".join(lines), encoding="utf-8")
        QMessageBox.information(self, "Готово", "Отчёт сохранён.")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить таблицу", "antenna_compare.csv", "CSV files (*.csv)")
        if not path:
            return

        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Параметр", "Антенна 1", "Антенна 2"])
            for row in range(self.table.rowCount()):
                writer.writerow([
                    self.table.item(row, 0).text(),
                    self.table.item(row, 1).text(),
                    self.table.item(row, 2).text(),
                ])
        QMessageBox.information(self, "Готово", "CSV сохранён.")

    def reload_data(self):
        try:
            self.data, self.antennas = load_data()
            self.left_combo.clear()
            self.right_combo.clear()
            self.category_filter.clear()
            self.category_filter.addItem("Все категории")
            for cat in sorted({a.category for a in self.antennas}):
                self.category_filter.addItem(cat)
            for a in self.antennas:
                self.left_combo.addItem(a.name)
                self.right_combo.addItem(a.name)
            if len(self.antennas) > 1:
                self.right_combo.setCurrentIndex(1)
            self.refresh_list()
            self.update_compare()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Antenna Compare")
    if ICON_FILE.exists():
        app.setWindowIcon(QIcon(str(ICON_FILE)))
    app.setStyle("Fusion")
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
