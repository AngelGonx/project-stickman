"""Creador de stickmen personalizados: círculo cromático, cosméticos, nombre y tipo de cuerpo."""
from .core import *  # noqa: F401,F403
from .actions import pose_wave, pose_walk, pose_stand
from .draw import draw_stickman, COSMETICS, bubble_top, draw_bubble
from .storage import new_id, normalize
from .i18n import tr
from PySide6.QtCore import Signal
from PySide6.QtGui import QConicalGradient, QRadialGradient
from PySide6.QtWidgets import (QDialog, QLineEdit, QRadioButton, QButtonGroup, QListWidget,
                               QListWidgetItem, QSlider, QPushButton, QLabel, QHBoxLayout,
                               QVBoxLayout, QGroupBox)


class ColorWheel(QWidget):
    """Círculo cromático: el ángulo es el tono y la distancia al centro la saturación."""
    changed = Signal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.h, self.s, self.v = 0.0, 1.0, 1.0
        self.setCursor(Qt.CrossCursor)

    def color(self):
        return QColor.fromHsvF(self.h % 1.0, clamp(self.s, 0, 1), clamp(self.v, 0, 1))

    def set_color(self, c):
        h, s, v, _ = QColor(c).getHsvF()
        self.h = h if h >= 0 else self.h
        self.s, self.v = s, v
        self.update()

    def set_value(self, v):
        self.v = v
        self.update()
        self.changed.emit(self.color())

    def geom(self):
        r = min(self.width(), self.height()) / 2 - 6
        return QPointF(self.width() / 2, self.height() / 2), r

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c, r = self.geom()
        g = QConicalGradient(c, 0)
        for i in range(13):
            g.setColorAt(i / 12, QColor.fromHsvF((i / 12) % 1.0, 1, 1))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, r, r)
        rg = QRadialGradient(c, r)
        rg.setColorAt(0, QColor(255, 255, 255, 255))
        rg.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(rg)
        p.drawEllipse(c, r, r)
        p.setBrush(QColor(0, 0, 0, int(255 * (1 - self.v))))
        p.drawEllipse(c, r, r)
        a = self.h * 2 * math.pi
        m = c + QPointF(math.cos(a) * r * self.s, -math.sin(a) * r * self.s)
        p.setPen(QPen(QColor(255, 255, 255), 2.5))
        p.setBrush(self.color())
        p.drawEllipse(m, 8, 8)
        p.setPen(QPen(QColor(0, 0, 0), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(m, 9.5, 9.5)

    def pick(self, pos):
        c, r = self.geom()
        d = pos - c
        self.h = (math.atan2(-d.y(), d.x()) / (2 * math.pi)) % 1.0
        self.s = clamp(math.hypot(d.x(), d.y()) / r, 0, 1)
        self.update()
        self.changed.emit(self.color())

    def mousePressEvent(self, e):
        self.pick(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self.pick(e.position())


class Preview(QWidget):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dlg = dialog
        self.setMinimumSize(240, 300)
        self.t = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def tick(self):
        self.t += 0.033
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#EEF1F5"))
        spec = self.dlg.spec()
        H = min(self.height() * 0.42, 130)
        R = head_radius(spec, H)
        k = int(self.t / 3) % 3
        pose = [pose_wave(self.t), pose_stand(self.t), pose_walk((self.t * 0.8) % 1.0)][k]
        f = 1 if int(self.t / 9) % 2 == 0 else -1
        j = solve(pose, H, f, R)
        cy = contact(j, H, R)
        gy = self.height() - 30
        p.setPen(QPen(QColor("#9CA3AF"), 3))
        p.drawLine(20, int(gy), self.width() - 20, int(gy))
        p.translate(self.width() / 2, gy - cy)
        draw_stickman(p, j, H, spec, f, self.t, False, 0.0, None, R)
        name = spec.get("name") or "?"
        draw_bubble(p, QPointF(j["head"].x(), bubble_top(j, H, spec, R)), H, name)


class CreatorDialog(QDialog):
    def __init__(self, spec=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Crear stickman") if spec is None else tr("Editar stickman"))
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        base = normalize(spec) if spec else dict(id=new_id(), name="", color="#F97316",
                                                 accent="#FFFFFF", eyes="#111111", accs=[],
                                                 body="normal")
        self.data = dict(base)
        self.editing = "color"

        self.name = QLineEdit(self.data["name"])
        self.name.setPlaceholderText(tr("Ponle un nombre"))
        self.name.setMaxLength(24)

        self.body_normal = QRadioButton(tr("Normal"))
        self.body_big = QRadioButton(tr("Cabeza grande hueca"))
        (self.body_big if self.data["body"] == "cabezon" else self.body_normal).setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self.body_normal)
        bg.addButton(self.body_big)
        self.body_big.toggled.connect(lambda on: self.data.update(body="cabezon" if on else "normal"))

        # qué color se está editando
        self.mode_btns = {}
        mg = QButtonGroup(self)
        mode_row = QHBoxLayout()
        for key, label in (("color", "Cuerpo"), ("accent", "Accesorios"), ("eyes", "Ojos")):
            b = QRadioButton(tr(label))
            mg.addButton(b)
            mode_row.addWidget(b)
            b.toggled.connect(lambda on, k=key: on and self.set_mode(k))
            self.mode_btns[key] = b
        self.wheel = ColorWheel()
        self.wheel.changed.connect(self.on_color)
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(0, 100)
        self.bright.valueChanged.connect(lambda v: self.wheel.set_value(v / 100))
        self.hex = QLineEdit()
        self.hex.setMaxLength(7)
        self.hex.editingFinished.connect(self.on_hex)
        self.mode_btns["color"].setChecked(True)

        self.cos = QListWidget()
        for key, label in COSMETICS:
            it = QListWidgetItem(tr(label))
            it.setData(Qt.UserRole, key)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if key in self.data["accs"] else Qt.Unchecked)
            self.cos.addItem(it)
        self.cos.itemChanged.connect(self.on_cos)

        rnd = QPushButton(tr("🎲 Aleatorio"))
        rnd.clicked.connect(self.randomize)
        ok = QPushButton(tr("Guardar"))
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QPushButton(tr("Cancelar"))
        cancel.clicked.connect(self.reject)

        self.preview = Preview(self)

        left = QVBoxLayout()
        left.addWidget(QLabel(tr("Nombre:")))
        left.addWidget(self.name)
        body = QGroupBox(tr("Tipo de stickman"))
        bl = QVBoxLayout(body)
        bl.addWidget(self.body_normal)
        bl.addWidget(self.body_big)
        left.addWidget(body)
        left.addWidget(self.preview, 1)

        mid = QVBoxLayout()
        colors = QGroupBox(tr("Colores"))
        cl = QVBoxLayout(colors)
        cl.addLayout(mode_row)
        cl.addWidget(self.wheel, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Brillo")))
        row.addWidget(self.bright, 1)
        row.addWidget(self.hex)
        cl.addLayout(row)
        mid.addWidget(colors)

        right = QVBoxLayout()
        cg = QGroupBox(tr("Cosméticos (puedes elegir varios)"))
        cgl = QVBoxLayout(cg)
        cgl.addWidget(self.cos)
        right.addWidget(cg, 1)

        top = QHBoxLayout()
        top.addLayout(left, 3)
        top.addLayout(mid, 3)
        top.addLayout(right, 2)
        buttons = QHBoxLayout()
        buttons.addWidget(rnd)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        root = QVBoxLayout(self)
        root.addLayout(top, 1)
        root.addLayout(buttons)
        self.resize(860, 520)

    def set_mode(self, key):
        self.editing = key
        c = QColor(self.data[key])
        self.wheel.blockSignals(True)
        self.wheel.set_color(c)
        self.wheel.blockSignals(False)
        self.bright.blockSignals(True)
        self.bright.setValue(int(round(c.valueF() * 100)))
        self.bright.blockSignals(False)
        self.hex.setText(c.name().upper())

    def on_color(self, c):
        self.data[self.editing] = c.name()
        self.hex.setText(c.name().upper())

    def on_hex(self):
        c = QColor(self.hex.text().strip())
        if c.isValid():
            self.data[self.editing] = c.name()
            self.set_mode(self.editing)

    def on_cos(self, _):
        self.data["accs"] = [self.cos.item(i).data(Qt.UserRole) for i in range(self.cos.count())
                             if self.cos.item(i).checkState() == Qt.Checked]

    def randomize(self):
        h = random.random()
        self.data["color"] = QColor.fromHsvF(h, random.uniform(0.5, 1), random.uniform(0.55, 1)).name()
        self.data["accent"] = QColor.fromHsvF((h + random.uniform(0.3, 0.7)) % 1, random.uniform(0.3, 1),
                                              random.uniform(0.6, 1)).name()
        dark = QColor(self.data["color"]).lightness() < 90
        self.data["eyes"] = "#FFFFFF" if dark else "#111111"
        picks = random.sample([k for k, _ in COSMETICS], random.randint(1, 3))
        self.cos.blockSignals(True)
        for i in range(self.cos.count()):
            it = self.cos.item(i)
            it.setCheckState(Qt.Checked if it.data(Qt.UserRole) in picks else Qt.Unchecked)
        self.cos.blockSignals(False)
        self.on_cos(None)
        if random.random() < 0.3:
            self.body_big.setChecked(True)
        else:
            self.body_normal.setChecked(True)
        self.set_mode(self.editing)

    def spec(self):
        d = dict(self.data)
        d["name"] = self.name.text().strip() or tr("Sin nombre")
        return d

    @staticmethod
    def ask(spec=None, parent=None):
        dlg = CreatorDialog(spec, parent)
        if dlg.exec() == QDialog.Accepted:
            return normalize(dlg.spec())
        return None
