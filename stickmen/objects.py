"""Objetos que el usuario coloca y mueve; los stickmen interactúan con ellos.

No se guardan: al cerrar el programa desaparecen.
"""
from .core import *  # noqa: F401,F403
from .i18n import tr
from PySide6.QtGui import QRadialGradient, QPainterPath


class Slot:
    """Un lugar para usar el objeto. Medidas en H (altura del stickman)."""

    def __init__(self, dx, face, actions, seat=None, floor=0.0, hide=False, ride=False,
                 no_climb=False):
        self.dx, self.face = dx, face
        self.actions = actions if isinstance(actions, (list, tuple)) else [actions]
        self.seat, self.floor, self.hide, self.ride = seat, floor, hide, ride
        self.no_climb = no_climb
        self.user = None


ITEM_TYPES = {}


def item_type(cls):
    ITEM_TYPES[cls.key] = cls
    return cls


class Item(QWidget):
    key, label = "item", "Objeto"
    W, HH = 1.0, 1.0          # ancho y alto en H
    throwable = False
    is_room = False
    is_roof = False
    layer = 2                 # orden de apilado: 0 cuartos, 1 techos, 2 objetos

    def __init__(self, crew, x, y):
        flags = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
                 Qt.NoDropShadowWindowHint | Qt.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.crew, self.H = crew, HEIGHT
        self.resize(int((self.W + 1.2) * self.H), int((self.HH + 1.2) * self.H))
        self.ox, self.oy = self.width() / 2, self.height() - self.H * 0.12
        self.x, self.y = float(x), float(y)     # centro abajo, en coordenadas de pantalla
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.t = random.random() * 10
        self.hidden = False
        self.dragging = False
        self.grab = QPointF()
        self.svx = self.svy = 0.0
        self.last_cursor = None
        self.slots = self.make_slots()

    # ---- para subclases
    def make_slots(self):
        return []

    def usable(self):
        return True

    def on_used(self, s, slot):
        pass

    def draw(self, p):
        pass

    def extra_tick(self, dt):
        pass

    def bounds(self):
        return QRectF(-self.W / 2 * self.H, -self.HH * self.H, self.W * self.H, self.HH * self.H)

    def slot_pos(self, slot, s):
        """Dónde se pone el stickman: (x, y de la base) en pantalla."""
        return self.x + slot.dx * self.H, self.y

    def actions_for(self, slot):
        return slot.actions

    def on_land(self, room):
        pass

    def support(self, y_now):
        """La superficie más alta debajo de y_now: el piso o un cuarto (su piso o su techo)."""
        best = ground_at(self.x)
        if best is None:
            best = desktop_bounds()[2] + 5000
        self.support_room = None
        for r in self.crew.items:
            if r is self or not r.is_room or not r.on_ground or r.dragging:
                continue
            half = r.W * self.H / 2
            if abs(self.x - r.x) > half - 0.15 * self.H:
                continue
            surfaces = [r.y - r.HH * self.H]
            if not self.is_room and not self.is_roof:
                surfaces.append(r.y - r.FLOOR * self.H)
            for sy in surfaces:
                if y_now - 2 <= sy < best:
                    best, self.support_room = sy, r
        return best

    # ---- lógica
    def free_slots(self):
        return [s for s in self.slots if s.user is None]

    def release_users(self):
        for sl in self.slots:
            if sl.user is not None:
                sl.user.kick_from_item()

    def tick(self, dt):
        self.t += dt
        if self.dragging:
            cur = QPointF(QCursor.pos())
            nx, ny = cur.x() - self.grab.x(), cur.y() - self.grab.y()
            if dt > 0:
                a = 1 - math.exp(-dt * 12)
                self.svx += ((nx - self.x) / dt - self.svx) * a
                self.svy += ((ny - self.y) / dt - self.svy) * a
            self.x, self.y = nx, ny
        elif not self.on_ground:
            self.physics(dt)
        elif self.crew.has_rooms and self.support(self.y) > self.y + 2:
            self.on_ground = False      # le quitaron lo que tenía abajo
            self.release_users()
        self.extra_tick(dt)

    def physics(self, dt):
        L, Rb, top = desktop_bounds()
        self.vy += GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        m = self.W * self.H / 2
        if self.x < L + m:
            self.x, self.vx = L + m, abs(self.vx) * 0.5
        elif self.x > Rb - m:
            self.x, self.vx = Rb - m, -abs(self.vx) * 0.5
        g = self.support(self.y - self.vy * dt)
        if self.y >= g:
            self.y = g
            self.vx = self.vy = 0.0
            self.on_ground = True
            self.on_land(self.support_room)

    def sync(self):
        self.setVisible(not self.hidden and self.crew.visible)
        if not self.hidden:
            self.move(int(round(self.x - self.ox)), int(round(self.y - self.oy)))
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.ox, self.oy)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 1))       # para poder agarrarlo
        p.drawRect(self.bounds().adjusted(-4, -4, 4, 4))
        self.draw(p)

    # ---- mouse
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.release_users()
            self.dragging = True
            self.on_ground = False
            self.svx = self.svy = 0.0
            self.grab = e.globalPosition() - QPointF(self.x, self.y)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            if self.throwable:
                self.vx, self.vy = clamp(self.svx, -1600, 1600), clamp(self.svy, -1600, 1600)
            else:
                self.vx = self.vy = 0.0
            self.crew.restack()

    def contextMenuEvent(self, e):
        menu = QMenu()
        menu.addAction(f"— {tr(self.label)} —").setEnabled(False)
        self.extra_menu(menu)
        menu.addAction(tr("Quitar")).triggered.connect(lambda: self.crew.remove_item(self))
        menu.exec(e.globalPos())

    def extra_menu(self, menu):
        pass


def wood(p, rect, c="#A0662F", r=3):
    p.setPen(QPen(QColor(c).darker(140), 1.2))
    p.setBrush(QColor(c))
    p.drawRoundedRect(rect, r, r)


# ============================================================================
@item_type
class Sofa(Item):
    key, label, W, HH = "sofa", "Sofá", 2.2, 0.85

    def make_slots(self):
        return [Slot(dx, 0, ["o_sentarse", "o_sentarse", "o_sentarse_cel"], seat=0.42)
                for dx in (-0.6, 0.0, 0.6)]

    def draw(self, p):
        H = self.H
        base = QColor("#B5523B")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#4A3426"))
        for x in (-0.95, 0.88):
            p.drawRect(QRectF(x * H, -0.1 * H, 0.07 * H, 0.1 * H))
        p.setBrush(base.darker(110))
        p.drawRoundedRect(QRectF(-1.0 * H, -0.85 * H, 2.0 * H, 0.55 * H), 0.12 * H, 0.12 * H)
        p.setBrush(base)
        p.drawRoundedRect(QRectF(-1.05 * H, -0.4 * H, 2.1 * H, 0.3 * H), 0.06 * H, 0.06 * H)
        p.setBrush(base.lighter(112))
        for x in (-0.9, -0.3, 0.3):
            p.drawRoundedRect(QRectF(x * H, -0.47 * H, 0.6 * H, 0.12 * H), 0.05 * H, 0.05 * H)
        p.setBrush(base.darker(105))
        for x in (-1.1, 0.88):
            p.drawRoundedRect(QRectF(x * H, -0.6 * H, 0.22 * H, 0.5 * H), 0.08 * H, 0.08 * H)


@item_type
class Picnic(Item):
    key, label, W, HH = "picnic", "Mesa de picnic", 2.6, 0.68

    def make_slots(self):
        return [Slot(-0.98, 1, "o_comer", seat=0.37), Slot(0.98, -1, "o_comer", seat=0.37)]

    def draw(self, p):
        H = self.H
        p.setPen(QPen(QColor("#6E4320"), 0.06 * H, Qt.SolidLine, Qt.RoundCap))
        for sx in (-1, 1):
            p.drawLine(QPointF(sx * 0.45 * H, -0.62 * H), QPointF(sx * 0.95 * H, 0))
            p.drawLine(QPointF(sx * 0.6 * H, -0.62 * H), QPointF(sx * 0.15 * H, 0))
            p.drawLine(QPointF(sx * 1.25 * H, -0.32 * H), QPointF(sx * 1.25 * H, 0))
        wood(p, QRectF(-1.2 * H, -0.68 * H, 2.4 * H, 0.09 * H))
        wood(p, QRectF(-1.32 * H, -0.36 * H, 0.62 * H, 0.07 * H))
        wood(p, QRectF(0.7 * H, -0.36 * H, 0.62 * H, 0.07 * H))
        # mantel y canasta
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E5484D"))
        p.drawRect(QRectF(-0.5 * H, -0.7 * H, 1.0 * H, 0.04 * H))
        p.setBrush(QColor("#D4A35A"))
        p.drawRoundedRect(QRectF(-0.18 * H, -0.86 * H, 0.36 * H, 0.17 * H), 4, 4)


@item_type
class Trampoline(Item):
    key, label, W, HH = "trampolin", "Trampolín", 1.6, 0.32

    def make_slots(self):
        return [Slot(0.0, 0, "o_trampolin", floor=0.3)]

    def draw(self, p):
        H = self.H
        dip = 0.0
        u = self.slots[0].user
        if u is not None and u.state == "act" and u.pose["lift"] < 0.08:
            dip = 0.08 * H
        p.setPen(QPen(QColor("#2563EB"), 0.05 * H, Qt.SolidLine, Qt.RoundCap))
        for sx in (-1, 1):
            p.drawLine(QPointF(sx * 0.7 * H, -0.3 * H), QPointF(sx * 0.55 * H, 0))
            p.drawLine(QPointF(sx * 0.7 * H, -0.3 * H), QPointF(sx * 0.82 * H, 0))
        p.setPen(QPen(QColor("#111"), 0.045 * H, Qt.SolidLine, Qt.RoundCap))
        path = QPainterPath(QPointF(-0.7 * H, -0.3 * H))
        path.quadTo(QPointF(0, -0.3 * H + 2 * dip), QPointF(0.7 * H, -0.3 * H))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(QPen(QColor("#60A5FA"), 0.07 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-0.8 * H, -0.3 * H), QPointF(-0.68 * H, -0.3 * H))
        p.drawLine(QPointF(0.68 * H, -0.3 * H), QPointF(0.8 * H, -0.3 * H))


@item_type
class Campfire(Item):
    key, label, W, HH = "fogata", "Fogata", 0.9, 0.75

    def make_slots(self):
        return [Slot(-0.8, 1, ["o_calentarse", "o_bombon"]), Slot(0.8, -1, ["o_calentarse", "o_bombon"])]

    def draw(self, p):
        H, t = self.H, self.t
        g = QRadialGradient(QPointF(0, -0.2 * H), 0.7 * H)
        g.setColorAt(0, QColor(255, 170, 60, 90))
        g.setColorAt(1, QColor(255, 170, 60, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(0, -0.2 * H), 0.7 * H, 0.55 * H)
        for a in (-18, 18):
            p.save()
            p.rotate(a)
            wood(p, QRectF(-0.4 * H, -0.1 * H, 0.8 * H, 0.1 * H), "#7A4A22", 5)
            p.restore()
        for i, (c, s) in enumerate(((QColor("#F97316"), 1.0), (QColor("#FBBF24"), 0.7), (QColor("#FEF3C7"), 0.4))):
            hgt = (0.65 + 0.08 * math.sin(t * 9 + i)) * s * H
            wdt = 0.28 * s * H
            sway = 0.05 * H * math.sin(t * 6 + i * 2)
            path = QPainterPath(QPointF(-wdt, -0.08 * H))
            path.quadTo(QPointF(-wdt * 0.9, -hgt * 0.6), QPointF(sway, -hgt - 0.08 * H))
            path.quadTo(QPointF(wdt * 0.9, -hgt * 0.6), QPointF(wdt, -0.08 * H))
            path.closeSubpath()
            p.setBrush(c)
            p.drawPath(path)
        p.setBrush(QColor(255, 200, 80))
        for i in range(3):
            k = (t * 0.8 + i / 3) % 1.0
            p.drawEllipse(QPointF(0.15 * H * math.sin(t * 3 + i * 2), -(0.5 + 0.6 * k) * H),
                          0.015 * H * (1 - k), 0.015 * H * (1 - k))


@item_type
class TV(Item):
    key, label, W, HH = "tele", "Tele", 1.1, 1.0

    def make_slots(self):
        return [Slot(-1.35, 1, "o_tele"), Slot(1.35, -1, "o_tele")]

    def draw(self, p):
        H, t = self.H, self.t
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#4B5563"))
        p.drawRect(QRectF(-0.06 * H, -0.36 * H, 0.12 * H, 0.3 * H))
        p.drawRoundedRect(QRectF(-0.3 * H, -0.08 * H, 0.6 * H, 0.08 * H), 3, 3)
        p.setBrush(QColor("#111827"))
        p.drawRoundedRect(QRectF(-0.55 * H, -1.0 * H, 1.1 * H, 0.66 * H), 6, 6)
        scr = QRectF(-0.49 * H, -0.94 * H, 0.98 * H, 0.54 * H)
        on = any(sl.user is not None for sl in self.slots)
        if on:
            p.setBrush(QColor.fromHsvF((t * 0.05) % 1.0, 0.35, 0.95))
            p.drawRect(scr)
            # una caricatura: una pelotita rebotando
            bx = scr.left() + (0.5 + 0.4 * math.sin(t * 1.3)) * scr.width()
            by = scr.bottom() - abs(math.sin(t * 4)) * scr.height() * 0.7 - 0.06 * H
            p.setBrush(QColor("#EF4444"))
            p.drawEllipse(QPointF(bx, by), 0.06 * H, 0.06 * H)
            p.setBrush(QColor("#22C55E"))
            p.drawRect(QRectF(scr.left(), scr.bottom() - 0.05 * H, scr.width(), 0.05 * H))
        else:
            p.setBrush(QColor("#1F2937"))
            p.drawRect(scr)
            p.setBrush(QColor(255, 255, 255, 30))
            p.drawPolygon(QPolygonF([scr.topLeft(), scr.topLeft() + QPointF(0.3 * H, 0),
                                     scr.topLeft() + QPointF(0, 0.3 * H)]))


@item_type
class Bed(Item):
    key, label, W, HH = "cama", "Cama", 2.1, 0.65

    def make_slots(self):
        return [Slot(0.3, 1, "o_acostarse", floor=0.38)]

    def draw(self, p):
        H = self.H
        wood(p, QRectF(-1.05 * H, -0.65 * H, 0.1 * H, 0.65 * H), "#8B5A2B")
        wood(p, QRectF(0.97 * H, -0.42 * H, 0.08 * H, 0.42 * H), "#8B5A2B")
        wood(p, QRectF(-1.0 * H, -0.3 * H, 2.0 * H, 0.16 * H), "#8B5A2B")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#F8FAFC"))
        p.drawRoundedRect(QRectF(-0.97 * H, -0.4 * H, 1.94 * H, 0.12 * H), 5, 5)
        p.setBrush(QColor("#E2E8F0"))
        p.drawRoundedRect(QRectF(-0.92 * H, -0.5 * H, 0.42 * H, 0.13 * H), 8, 8)
        p.setBrush(QColor("#6366F1"))
        p.drawRoundedRect(QRectF(-0.25 * H, -0.42 * H, 1.25 * H, 0.2 * H), 6, 6)


@item_type
class Weights(Item):
    key, label, W, HH = "pesas", "Pesas", 0.8, 0.2

    def make_slots(self):
        return [Slot(0.0, 0, "o_pesas", hide=True)]

    def draw(self, p):
        H = self.H
        for x in (-0.22, 0.22):
            p.setPen(QPen(QColor("#6B7280"), 0.03 * H))
            p.drawLine(QPointF((x - 0.12) * H, -0.08 * H), QPointF((x + 0.12) * H, -0.08 * H))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#1F2937"))
            for dx in (-0.12, 0.12):
                p.drawRoundedRect(QRectF((x + dx - 0.035) * H, -0.16 * H, 0.07 * H, 0.16 * H), 3, 3)


@item_type
class PullUpBar(Item):
    key, label, W, HH = "barra", "Barra de dominadas", 1.2, 1.6
    BAR = 1.5

    def make_slots(self):
        return [Slot(0.0, 0, "o_dominadas", seat=self.BAR - 0.63)]

    def draw(self, p):
        H = self.H
        p.setPen(QPen(QColor("#374151"), 0.06 * H, Qt.SolidLine, Qt.RoundCap))
        for sx in (-1, 1):
            p.drawLine(QPointF(sx * 0.55 * H, 0), QPointF(sx * 0.55 * H, -self.BAR * H))
            p.drawLine(QPointF(sx * 0.4 * H, 0), QPointF(sx * 0.7 * H, 0))
        p.setPen(QPen(QColor("#9CA3AF"), 0.045 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-0.58 * H, -self.BAR * H), QPointF(0.58 * H, -self.BAR * H))


@item_type
class Crate(Item):
    key, label, W, HH = "caja", "Caja", 0.7, 0.6

    def make_slots(self):
        return [Slot(0.0, 0, ["o_sentarse", "o_sentarse_cel"], seat=0.62)]

    def draw(self, p):
        H = self.H
        r = QRectF(-0.35 * H, -0.6 * H, 0.7 * H, 0.6 * H)
        wood(p, r, "#C48A47", 2)
        p.setPen(QPen(QColor("#8B5A2B"), 0.035 * H))
        p.drawLine(r.topLeft(), r.bottomRight())
        p.drawRect(r.adjusted(0.04 * H, 0.04 * H, -0.04 * H, -0.04 * H))


@item_type
class Skateboard(Item):
    key, label, W, HH = "patineta", "Patineta", 0.85, 0.15

    def make_slots(self):
        return [Slot(0.0, 0, "o_patineta", floor=0.12, ride=True)]

    def extra_tick(self, dt):
        u = self.slots[0].user
        if u is not None and u.state == "act" and u.item is self:
            self.x = u.hx
            g = ground_at(self.x) or self.y
            self.y = g - u.pose["lift"] * self.H
            self.on_ground = True

    def draw(self, p):
        H = self.H
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#F59E0B"))
        p.drawRoundedRect(QRectF(-0.42 * H, -0.13 * H, 0.84 * H, 0.05 * H), 0.025 * H, 0.025 * H)
        p.setBrush(QColor("#111"))
        for x in (-0.28, 0.28):
            p.drawEllipse(QPointF(x * H, -0.04 * H), 0.04 * H, 0.04 * H)


@item_type
class Plant(Item):
    key, label, W, HH = "maceta", "Maceta", 0.6, 1.0

    def __init__(self, *a):
        super().__init__(*a)
        self.growth = 0

    def make_slots(self):
        return [Slot(-0.55, 1, "o_regar"), Slot(0.55, -1, "o_regar")]

    def on_used(self, s, slot):
        self.growth = min(5, self.growth + 1)

    def extra_menu(self, menu):
        menu.addAction(tr("Podar (volver a chiquita)")).triggered.connect(lambda: setattr(self, "growth", 0))

    def draw(self, p):
        H, t = self.H, self.t
        top = -(0.25 + 0.15 + 0.11 * self.growth) * H
        sway = math.sin(t * 1.5) * 0.02 * H
        p.setPen(QPen(QColor("#15803D"), 0.03 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(0, -0.25 * H), QPointF(sway, top))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#22C55E"))
        n = 2 + self.growth
        for i in range(n):
            y = -0.3 * H + (top + 0.3 * H) * (i + 1) / (n + 1)
            sx = 1 if i % 2 else -1
            p.save()
            p.translate(sway * (i + 1) / n, y)
            p.rotate(sx * 35)
            p.drawEllipse(QPointF(sx * 0.08 * H, 0), 0.09 * H, 0.04 * H)
            p.restore()
        if self.growth >= 3:
            p.setBrush(QColor("#F472B6"))
            for i in range(6):
                a = i * math.pi / 3
                p.drawEllipse(QPointF(sway + math.cos(a) * 0.05 * H, top + math.sin(a) * 0.05 * H),
                              0.035 * H, 0.035 * H)
            p.setBrush(QColor("#FDE047"))
            p.drawEllipse(QPointF(sway, top), 0.03 * H, 0.03 * H)
        p.setBrush(QColor("#C2410C"))
        p.drawPolygon(QPolygonF([QPointF(-0.2 * H, -0.27 * H), QPointF(0.2 * H, -0.27 * H),
                                 QPointF(0.15 * H, 0), QPointF(-0.15 * H, 0)]))
        p.setBrush(QColor("#9A3412"))
        p.drawRect(QRectF(-0.22 * H, -0.3 * H, 0.44 * H, 0.06 * H))


@item_type
class Pizza(Item):
    key, label, W, HH = "pizza", "Pizza", 0.85, 0.5

    def __init__(self, *a):
        super().__init__(*a)
        self.slices = 8

    def make_slots(self):
        return [Slot(-0.62, 1, "o_comer_piso"), Slot(0.62, -1, "o_comer_piso")]

    def usable(self):
        return self.slices > 0

    def on_used(self, s, slot):
        self.slices = max(0, self.slices - 1)

    def extra_menu(self, menu):
        menu.addAction(tr("Pedir otra pizza")).triggered.connect(lambda: setattr(self, "slices", 8))

    def draw(self, p):
        H = self.H
        p.setPen(QPen(QColor("#A16207"), 1))
        p.setBrush(QColor("#D6B37A"))
        p.drawPolygon(QPolygonF([QPointF(-0.4 * H, -0.05 * H), QPointF(0.4 * H, -0.05 * H),
                                 QPointF(0.33 * H, -0.48 * H), QPointF(-0.33 * H, -0.48 * H)]))
        p.drawRect(QRectF(-0.42 * H, -0.05 * H, 0.84 * H, 0.05 * H))
        r = QRectF(-0.34 * H, -0.14 * H, 0.68 * H, 0.14 * H)
        if self.slices:
            p.setBrush(QColor("#F59E0B"))
            p.drawPie(r, 90 * 16, int(self.slices * 45 * 16))
            p.setBrush(QColor("#B91C1C"))
            p.setPen(Qt.NoPen)
            for i in range(self.slices):
                a = math.radians(90 + 45 * i + 22)
                p.drawEllipse(QPointF(math.cos(a) * 0.18 * H, -0.07 * H - math.sin(a) * 0.035 * H),
                              0.03 * H, 0.012 * H)


@item_type
class Book(Item):
    key, label, W, HH = "libro", "Libro", 0.4, 0.1

    def make_slots(self):
        return [Slot(0.0, 0, "o_leer", hide=True)]

    def draw(self, p):
        H = self.H
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FAFAF5"))
        p.drawRect(QRectF(-0.17 * H, -0.08 * H, 0.34 * H, 0.06 * H))
        p.setBrush(QColor("#7C3AED"))
        p.drawRoundedRect(QRectF(-0.19 * H, -0.03 * H, 0.38 * H, 0.03 * H), 2, 2)
        p.drawRoundedRect(QRectF(-0.19 * H, -0.1 * H, 0.38 * H, 0.025 * H), 2, 2)


@item_type
class Guitar(Item):
    key, label, W, HH = "guitarra", "Guitarra", 0.95, 0.25

    def make_slots(self):
        return [Slot(0.0, 0, "o_guitarra", hide=True)]

    def draw(self, p):
        H = self.H
        p.setPen(QPen(QColor("#5B3714"), 0.035 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-0.1 * H, -0.1 * H), QPointF(0.45 * H, -0.1 * H))
        p.setPen(QPen(QColor("#6B3A12"), 1.2))
        p.setBrush(QColor("#CD7832"))
        p.drawEllipse(QPointF(-0.22 * H, -0.1 * H), 0.2 * H, 0.1 * H)
        p.setBrush(QColor("#3B1F0A"))
        p.drawEllipse(QPointF(-0.17 * H, -0.1 * H), 0.035 * H, 0.035 * H)


@item_type
class Speaker(Item):
    key, label, W, HH = "bocina", "Bocina", 0.6, 0.85

    def make_slots(self):
        dances = ["bailar", "disco", "robot", "guitarra", "moonwalk"]
        return [Slot(-0.95, 1, dances), Slot(0.95, -1, dances)]

    def draw(self, p):
        H, t = self.H, self.t
        on = any(sl.user is not None for sl in self.slots)
        pulse = (0.5 + 0.5 * abs(math.sin(t * 8))) if on else 0.0
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1F2937"))
        p.drawRoundedRect(QRectF(-0.28 * H, -0.85 * H, 0.56 * H, 0.85 * H), 6, 6)
        for y, r in ((-0.62, 0.1), (-0.27, 0.17)):
            p.setBrush(QColor("#4B5563"))
            p.drawEllipse(QPointF(0, y * H), (r + 0.02 * pulse) * H, (r + 0.02 * pulse) * H)
            p.setBrush(QColor("#111827"))
            p.drawEllipse(QPointF(0, y * H), r * 0.45 * H, r * 0.45 * H)
        if on:
            f = QFont()
            f.setPixelSize(int(0.2 * H))
            f.setBold(True)
            p.setFont(f)
            for i in range(3):
                k = (t * 0.6 + i / 3) % 1.0
                c = QColor.fromHsvF((i * 0.3 + t * 0.1) % 1.0, 0.7, 0.9)
                c.setAlphaF(1 - k)
                p.setPen(c)
                p.drawText(QPointF((0.25 * math.sin(t * 2 + i * 2)) * H - 0.05 * H, -(0.9 + 0.5 * k) * H), "♪")


@item_type
class Ball(Item):
    key, label, W, HH = "pelota", "Pelota", 0.22, 0.22
    throwable = True
    RADIUS = 0.1

    def __init__(self, *a):
        super().__init__(*a)
        self.held_by = None
        self.spin = 0.0

    def make_slots(self):
        return [Slot(0.0, 0, "o_patear")]

    def bounds(self):
        r = self.RADIUS * self.H
        return QRectF(-r, -2 * r, 2 * r, 2 * r)

    def center(self):
        return QPointF(self.x, self.y - self.RADIUS * self.H)

    def set_center(self, c):
        self.x, self.y = c.x(), c.y() + self.RADIUS * self.H

    def tick(self, dt):
        if self.held_by is not None and not self.dragging:
            s = self.held_by
            hand = QPointF(s.hx, s.hy) + (s.joints["haF"] + s.joints["haB"]) * 0.5
            self.set_center(hand + QPointF(s.facing * self.RADIUS * self.H * 0.6, 0))
            self.vx = self.vy = 0.0
            self.on_ground = False
            self.t += dt
            return
        x0 = self.x
        super().tick(dt)
        self.spin += (self.x - x0) / (self.RADIUS * self.H)

    def physics(self, dt):
        L, Rb, top = desktop_bounds()
        self.vy += GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        r = self.RADIUS * self.H
        if self.x < L + r:
            self.x, self.vx = L + r, abs(self.vx) * 0.7
        elif self.x > Rb - r:
            self.x, self.vx = Rb - r, -abs(self.vx) * 0.7
        if self.y < top + 2 * r and self.vy < 0:
            self.vy = abs(self.vy) * 0.5
        g = self.support(self.y - self.vy * dt)
        if self.y >= g:
            self.y = g
            if self.vy > 160:
                self.vy = -self.vy * 0.55
            else:
                self.vy = 0.0
                self.vx *= math.exp(-dt * 2.5)
                if abs(self.vx) < 8:
                    self.vx = 0.0
                    self.on_ground = True

    def mousePressEvent(self, e):
        self.held_by = None
        super().mousePressEvent(e)

    def draw(self, p):
        H = self.H
        r = self.RADIUS * H
        c = QPointF(0, -r)
        p.setPen(QPen(QColor("#1F2937"), 1.2))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(c, r, r)
        p.save()
        p.translate(c)
        p.rotate(math.degrees(self.spin))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#EF4444"))
        p.drawPie(QRectF(-r, -r, 2 * r, 2 * r), 0, 60 * 16)
        p.drawPie(QRectF(-r, -r, 2 * r, 2 * r), 180 * 16, 60 * 16)
        p.setBrush(QColor("#3B82F6"))
        p.drawPie(QRectF(-r, -r, 2 * r, 2 * r), 90 * 16, 45 * 16)
        p.drawPie(QRectF(-r, -r, 2 * r, 2 * r), 270 * 16, 45 * 16)
        p.restore()





# ============================================================================
# Instrumentos
@item_type
class Piano(Item):
    key, label, W, HH = "piano", "Piano", 1.7, 1.15

    def make_slots(self):
        return [Slot(-0.55, 1, "o_piano", seat=0.44)]

    def draw(self, p):
        H = self.H
        wood(p, QRectF(-0.25 * H, -1.15 * H, 1.05 * H, 1.15 * H), "#1F1A17", 5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#F8FAFC"))
        p.drawRect(QRectF(-0.42 * H, -0.76 * H, 0.2 * H, 0.06 * H))
        p.setBrush(QColor("#111"))
        for i in range(4):
            p.drawRect(QRectF((-0.41 + i * 0.05) * H, -0.76 * H, 0.025 * H, 0.03 * H))
        p.setBrush(QColor("#2A221D"))
        p.drawRect(QRectF(-0.45 * H, -0.7 * H, 0.25 * H, 0.05 * H))
        wood(p, QRectF(-0.72 * H, -0.44 * H, 0.34 * H, 0.06 * H), "#5B3A1E")
        p.setPen(QPen(QColor("#5B3A1E"), 0.04 * H))
        p.drawLine(QPointF(-0.68 * H, -0.4 * H), QPointF(-0.68 * H, 0))
        p.drawLine(QPointF(-0.42 * H, -0.4 * H), QPointF(-0.42 * H, 0))


@item_type
class Drums(Item):
    key, label, W, HH = "bateria", "Batería", 1.7, 1.05

    def make_slots(self):
        return [Slot(-0.6, 1, "o_bateria", seat=0.44)]

    def draw(self, p):
        H, t = self.H, self.t
        hit = 0.03 * H * abs(math.sin(t * 14)) if self.slots[0].user is not None else 0.0
        wood(p, QRectF(-0.82 * H, -0.44 * H, 0.32 * H, 0.06 * H), "#374151")
        p.setPen(QPen(QColor("#374151"), 0.035 * H))
        p.drawLine(QPointF(-0.66 * H, -0.4 * H), QPointF(-0.66 * H, 0))
        p.setPen(QPen(QColor("#7F1D1D"), 2))
        p.setBrush(QColor("#DC2626"))
        p.drawEllipse(QPointF(0.35 * H, -0.32 * H), 0.32 * H, 0.32 * H)
        p.setBrush(QColor("#FEE2E2"))
        p.drawEllipse(QPointF(0.35 * H, -0.32 * H), 0.2 * H, 0.2 * H)
        p.setBrush(QColor("#DC2626"))
        p.drawRoundedRect(QRectF(-0.25 * H, -0.62 * H, 0.38 * H, 0.16 * H), 4, 4)
        p.setPen(QPen(QColor("#6B7280"), 0.02 * H))
        p.drawLine(QPointF(0.85 * H, 0), QPointF(0.85 * H, -0.95 * H))
        p.setPen(QPen(QColor("#CA8A04"), 0.035 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(0.62 * H, -0.95 * H - hit), QPointF(1.08 * H, -0.95 * H + hit))


@item_type
class Trumpet(Item):
    key, label, W, HH = "trompeta", "Trompeta", 0.6, 0.16

    def make_slots(self):
        return [Slot(0.0, 0, "o_trompeta", hide=True)]

    def draw(self, p):
        H = self.H
        p.setPen(QPen(QColor("#EAB308"), 0.03 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-0.25 * H, -0.07 * H), QPointF(0.15 * H, -0.07 * H))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#EAB308"))
        p.drawPolygon(QPolygonF([QPointF(0.12 * H, -0.09 * H), QPointF(0.28 * H, -0.15 * H),
                                 QPointF(0.28 * H, 0.0), QPointF(0.12 * H, -0.05 * H)]))


@item_type
class Violin(Item):
    key, label, W, HH = "violin", "Violín", 0.7, 0.16

    def make_slots(self):
        return [Slot(0.0, 0, "o_violin", hide=True)]

    def draw(self, p):
        H = self.H
        p.setPen(QPen(QColor("#5B2C0A"), 1))
        p.setBrush(QColor("#B45309"))
        p.drawEllipse(QPointF(-0.12 * H, -0.07 * H), 0.16 * H, 0.07 * H)
        p.setPen(QPen(QColor("#3B1F0A"), 0.025 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(0.04 * H, -0.07 * H), QPointF(0.3 * H, -0.07 * H))


@item_type
class Mic(Item):
    key, label, W, HH = "microfono", "Micrófono", 0.5, 1.15

    def make_slots(self):
        return [Slot(-0.38, 1, "o_cantar")]

    def draw(self, p):
        H, t = self.H, self.t
        p.setPen(QPen(QColor("#374151"), 0.03 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(0, 0), QPointF(0, -0.95 * H))
        p.drawLine(QPointF(-0.18 * H, 0), QPointF(0.18 * H, 0))
        p.drawLine(QPointF(0, -0.95 * H), QPointF(-0.12 * H, -1.03 * H))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#9CA3AF"))
        p.drawEllipse(QPointF(-0.14 * H, -1.05 * H), 0.05 * H, 0.05 * H)
        if self.slots[0].user is not None:
            f = QFont()
            f.setPixelSize(int(0.18 * H))
            p.setFont(f)
            for i in range(2):
                k = (t * 0.7 + i / 2) % 1.0
                c = QColor.fromHsvF((t * 0.1 + i * 0.4) % 1.0, 0.7, 0.9)
                c.setAlphaF(1 - k)
                p.setPen(c)
                p.drawText(QPointF(0.1 * H + 0.15 * H * math.sin(t * 2 + i), -(1.1 + 0.4 * k) * H), "♪")


# ============================================================================
# Más objetos
@item_type
class TableChairs(Item):
    key, label, W, HH = "mesa", "Mesa con sillas", 2.4, 0.95

    def make_slots(self):
        return [Slot(-0.85, 1, ["o_comer", "o_cartas"], seat=0.44),
                Slot(0.85, -1, ["o_comer", "o_cartas"], seat=0.44)]

    def draw(self, p):
        H = self.H
        for sx in (-1, 1):
            wood(p, QRectF(sx * 0.85 * H - 0.18 * H, -0.44 * H, 0.36 * H, 0.06 * H), "#92400E")
            p.setPen(QPen(QColor("#78350F"), 0.04 * H, Qt.SolidLine, Qt.RoundCap))
            back = sx * 1.05 * H
            p.drawLine(QPointF(back, 0), QPointF(back, -0.95 * H))
            p.drawLine(QPointF(sx * 0.68 * H, -0.4 * H), QPointF(sx * 0.68 * H, 0))
        p.setPen(QPen(QColor("#78350F"), 0.05 * H, Qt.SolidLine, Qt.RoundCap))
        for x in (-0.45, 0.45):
            p.drawLine(QPointF(x * H, -0.7 * H), QPointF(x * H, 0))
        wood(p, QRectF(-0.6 * H, -0.76 * H, 1.2 * H, 0.08 * H), "#B45309")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#F8FAFC"))
        p.drawEllipse(QPointF(0, -0.79 * H), 0.12 * H, 0.03 * H)


@item_type
class Swing(Item):
    key, label, W, HH = "columpio", "Columpio", 1.9, 1.95
    PIVOT, ROPE = 1.88, 1.42

    def __init__(self, *a):
        super().__init__(*a)
        self.swing = 0.0
        self.amp = 0.0

    def make_slots(self):
        return [Slot(0.0, 0, "o_columpio", seat=0.0)]

    def angle(self):
        return self.amp * math.sin(self.t * 2.4)

    def extra_tick(self, dt):
        used = self.slots[0].user is not None and self.slots[0].user.state == "act"
        self.amp += ((0.6 if used else 0.0) - self.amp) * min(1.0, dt * (0.5 if used else 0.8))
        self.swing = self.angle()

    def seat_point(self):
        a = self.angle()
        return QPointF(math.sin(a) * self.ROPE * self.H, (-self.PIVOT + math.cos(a) * self.ROPE) * self.H)

    def slot_pos(self, slot, s):
        sp = self.seat_point()
        return self.x + sp.x(), self.y + sp.y() + 0.02 * self.H

    def draw(self, p):
        H = self.H
        p.setPen(QPen(QColor("#2563EB"), 0.05 * H, Qt.SolidLine, Qt.RoundCap))
        for sx in (-1, 1):
            p.drawLine(QPointF(sx * 0.9 * H, 0), QPointF(sx * 0.7 * H, -self.PIVOT * H))
        p.drawLine(QPointF(-0.75 * H, -self.PIVOT * H), QPointF(0.75 * H, -self.PIVOT * H))
        sp = self.seat_point()
        p.setPen(QPen(QColor("#6B7280"), 0.015 * H))
        p.drawLine(QPointF(0, -self.PIVOT * H), sp)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#F59E0B"))
        p.save()
        p.translate(sp)
        p.rotate(math.degrees(-self.angle()))
        p.drawRoundedRect(QRectF(-0.16 * H, 0, 0.32 * H, 0.05 * H), 3, 3)
        p.restore()


@item_type
class Slide(Item):
    key, label, W, HH = "resbaladilla", "Resbaladilla", 2.4, 1.45

    def make_slots(self):
        return [Slot(-0.95, 1, "o_resbaladilla", seat=0.0, no_climb=True)]

    def slot_pos(self, slot, s):
        H = self.H
        u = max(0.0, s.act_u) if s.state == "act" and s.item is self else 0.0
        if u < 0.4:
            k = smooth(u / 0.4)
            return self.x - 0.95 * H, self.y - (0.47 + 0.85 * k) * H
        if u < 0.45:
            return self.x - 0.78 * H, self.y - 1.33 * H
        if u < 0.88:
            k = ((u - 0.45) / 0.43) ** 1.6
            return self.x + (-0.78 + 1.95 * k) * H, self.y - (1.33 - 1.0 * k) * H
        return self.x + 1.3 * H, self.y - 0.4 * H

    def draw(self, p):
        H = self.H
        p.setPen(QPen(QColor("#475569"), 0.04 * H, Qt.SolidLine, Qt.RoundCap))
        for x in (-1.05, -0.85):
            p.drawLine(QPointF(x * H, 0), QPointF(x * H, -1.35 * H))
        for i in range(6):
            y = -0.2 * H - i * 0.2 * H
            p.drawLine(QPointF(-1.05 * H, y), QPointF(-0.85 * H, y))
        p.setPen(QPen(QColor("#EF4444"), 0.08 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-0.8 * H, -1.32 * H), QPointF(1.15 * H, -0.12 * H))
        p.setPen(QPen(QColor("#475569"), 0.035 * H))
        p.drawLine(QPointF(0.2 * H, -0.7 * H), QPointF(0.2 * H, 0))


@item_type
class Pool(Item):
    key, label, W, HH = "alberca", "Alberca inflable", 1.8, 0.42
    layer = 3          # se dibuja enfrente: el que está adentro queda "en el agua"

    def make_slots(self):
        return [Slot(-0.35, 1, "o_alberca", floor=0.04), Slot(0.4, -1, "o_alberca", floor=0.04)]

    def draw(self, p):
        H, t = self.H, self.t
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(56, 189, 248, 170))
        p.drawRoundedRect(QRectF(-0.85 * H, -0.36 * H, 1.7 * H, 0.32 * H), 0.1 * H, 0.1 * H)
        p.setBrush(QColor("#38BDF8"))
        wave = [QPointF((-0.85 + 0.1 * i) * H, -0.34 * H + 0.015 * H * math.sin(t * 3 + i)) for i in range(18)]
        p.setPen(QPen(QColor("#E0F2FE"), 0.02 * H))
        p.drawPolyline(QPolygonF(wave))
        p.setPen(Qt.NoPen)
        for i, c in enumerate(("#F472B6", "#FDE047", "#60A5FA")):
            p.setBrush(QColor(c))
            p.drawRoundedRect(QRectF(-0.9 * H, -0.12 * H * (i + 1), 1.8 * H, 0.12 * H), 0.06 * H, 0.06 * H)
        if any(sl.user is not None for sl in self.slots):
            p.setBrush(QColor(186, 230, 253, 220))
            for i in range(6):
                k = (t * 1.6 + i / 6) % 1.0
                x = (-0.5 + (i % 3) * 0.4) * H + 0.2 * H * k * (1 if i % 2 else -1)
                p.drawEllipse(QPointF(x, -0.4 * H - 0.5 * H * math.sin(k * math.pi)), 0.025 * H, 0.025 * H)


@item_type
class Easel(Item):
    key, label, W, HH = "caballete", "Caballete de pintura", 0.9, 1.45

    def __init__(self, *a):
        super().__init__(*a)
        self.strokes = []
        self.st_t = 0.0

    def make_slots(self):
        return [Slot(-0.62, 1, "o_pintar")]

    def extra_tick(self, dt):
        u = self.slots[0].user
        if u is not None and u.state == "act" and len(self.strokes) < 45:
            self.st_t -= dt
            if self.st_t <= 0:
                self.st_t = 0.25
                c = QColor.fromHsvF(random.random(), random.uniform(0.5, 1), random.uniform(0.6, 1))
                x0, y0 = random.uniform(-0.2, 0.2), random.uniform(-1.3, -0.82)
                self.strokes.append((c, x0, y0, x0 + random.uniform(-0.12, 0.12), y0 + random.uniform(-0.1, 0.1)))

    def extra_menu(self, menu):
        menu.addAction(tr("Lienzo nuevo")).triggered.connect(lambda: self.strokes.clear())

    def draw(self, p):
        H = self.H
        p.setPen(QPen(QColor("#92400E"), 0.035 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-0.3 * H, 0), QPointF(0, -1.4 * H))
        p.drawLine(QPointF(0.3 * H, 0), QPointF(0, -1.4 * H))
        p.drawLine(QPointF(0, -1.0 * H), QPointF(0.15 * H, 0))
        p.setPen(QPen(QColor("#D6D3D1"), 1))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(QRectF(-0.27 * H, -1.36 * H, 0.54 * H, 0.6 * H))
        for c, x0, y0, x1, y1 in self.strokes:
            p.setPen(QPen(c, 0.03 * H, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x0 * H, y0 * H), QPointF(x1 * H, y1 * H))
        wood(p, QRectF(-0.3 * H, -0.78 * H, 0.6 * H, 0.04 * H), "#92400E")


@item_type
class Desk(Item):
    key, label, W, HH = "escritorio", "Escritorio con compu", 1.6, 1.2

    def make_slots(self):
        return [Slot(-0.45, 1, "o_compu", seat=0.44)]

    def draw(self, p):
        H, t = self.H, self.t
        wood(p, QRectF(-0.62 * H, -0.44 * H, 0.32 * H, 0.06 * H), "#334155")
        p.setPen(QPen(QColor("#334155"), 0.035 * H))
        p.drawLine(QPointF(-0.46 * H, -0.4 * H), QPointF(-0.46 * H, 0))
        p.drawLine(QPointF(-0.62 * H, -0.44 * H), QPointF(-0.64 * H, -0.82 * H))
        p.setPen(QPen(QColor("#78350F"), 0.05 * H))
        for x in (-0.1, 0.72):
            p.drawLine(QPointF(x * H, -0.68 * H), QPointF(x * H, 0))
        wood(p, QRectF(-0.2 * H, -0.74 * H, 1.0 * H, 0.07 * H), "#A16207")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#111827"))
        p.drawRect(QRectF(0.3 * H, -1.2 * H, 0.42 * H, 0.32 * H))
        p.drawRect(QRectF(0.48 * H, -0.88 * H, 0.06 * H, 0.14 * H))
        on = self.slots[0].user is not None
        p.setBrush(QColor("#1E3A8A") if on else QColor("#1F2937"))
        p.drawRect(QRectF(0.33 * H, -1.17 * H, 0.36 * H, 0.26 * H))
        if on:
            for i in range(5):
                w = (0.08 + 0.2 * abs(math.sin(i * 1.7 + int(t * 3) * 0.5))) * H
                p.setBrush(QColor("#93C5FD") if i % 2 else QColor("#86EFAC"))
                p.drawRect(QRectF(0.36 * H, (-1.14 + i * 0.045) * H, w, 0.02 * H))
        p.setBrush(QColor("#E5E7EB"))
        p.drawRect(QRectF(0.05 * H, -0.77 * H, 0.22 * H, 0.03 * H))


@item_type
class Hammock(Item):
    key, label, W, HH = "hamaca", "Hamaca", 2.3, 1.05

    def make_slots(self):
        return [Slot(0.0, 1, "o_hamaca", seat=0.0)]

    def slot_pos(self, slot, s):
        return self.x + 0.05 * self.H * math.sin(self.t * 1.2), self.y - 0.48 * self.H

    def draw(self, p):
        H = self.H
        sway = 0.05 * H * math.sin(self.t * 1.2)
        p.setPen(QPen(QColor("#78350F"), 0.07 * H, Qt.SolidLine, Qt.RoundCap))
        for sx in (-1, 1):
            p.drawLine(QPointF(sx * 1.08 * H, 0), QPointF(sx * 1.08 * H, -1.0 * H))
        path = QPainterPath(QPointF(-1.05 * H, -0.85 * H))
        path.quadTo(QPointF(sway, -0.1 * H), QPointF(1.05 * H, -0.85 * H))
        p.setPen(QPen(QColor("#F97316"), 0.06 * H, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(QPen(QColor("#FDE047"), 0.02 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)


@item_type
class Grill(Item):
    key, label, W, HH = "asador", "Asador", 0.9, 0.9

    def make_slots(self):
        return [Slot(-0.62, 1, "o_asar")]

    def draw(self, p):
        H, t = self.H, self.t
        p.setPen(QPen(QColor("#111827"), 0.035 * H, Qt.SolidLine, Qt.RoundCap))
        for x in (-0.3, 0.3):
            p.drawLine(QPointF(x * 0.6 * H, -0.5 * H), QPointF(x * H, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1F2937"))
        p.drawChord(QRectF(-0.35 * H, -0.85 * H, 0.7 * H, 0.7 * H), 180 * 16, 180 * 16)
        p.setBrush(QColor("#B45309"))
        for x in (-0.15, 0.05, 0.2):
            p.drawRoundedRect(QRectF(x * H, -0.56 * H, 0.12 * H, 0.04 * H), 3, 3)
        if self.slots[0].user is not None:
            for i in range(3):
                k = (t * 0.5 + i / 3) % 1.0
                c = QColor(200, 200, 200, int(150 * (1 - k)))
                p.setBrush(c)
                p.drawEllipse(QPointF((0.05 * math.sin(t + i * 2)) * H + (i - 1) * 0.1 * H, -(0.65 + 0.6 * k) * H),
                              (0.05 + 0.06 * k) * H, (0.05 + 0.06 * k) * H)


@item_type
class Tree(Item):
    key, label, W, HH = "arbol", "Árbol", 1.7, 2.4

    def make_slots(self):
        return [Slot(0.28, 1, "o_arbol", seat=0.07), Slot(-0.28, -1, "o_arbol", seat=0.07)]

    def draw(self, p):
        H, t = self.H, self.t
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#78350F"))
        p.drawPolygon(QPolygonF([QPointF(-0.14 * H, 0), QPointF(0.14 * H, 0), QPointF(0.09 * H, -1.4 * H),
                                 QPointF(-0.09 * H, -1.4 * H)]))
        for i, (x, y, r) in enumerate(((0, -1.75, 0.62), (-0.42, -1.45, 0.42), (0.45, -1.5, 0.45),
                                       (0.1, -2.05, 0.38))):
            sway = 0.03 * H * math.sin(t * 1.3 + i)
            p.setBrush(QColor("#16A34A") if i % 2 else QColor("#22C55E"))
            p.drawEllipse(QPointF(x * H + sway, y * H), r * H, r * H * 0.85)
        p.setBrush(QColor("#EF4444"))
        for x, y in ((-0.3, -1.5), (0.35, -1.65), (0.05, -1.95)):
            p.drawEllipse(QPointF(x * H, y * H), 0.05 * H, 0.05 * H)
