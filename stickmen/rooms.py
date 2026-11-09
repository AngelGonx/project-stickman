"""Cuartos modulares: cajitas que se pegan de lado, se apilan y llevan techo."""
from .core import *  # noqa: F401,F403
from .i18n import tr
from .objects import Item, Slot, item_type, wood, ITEM_TYPES

WALL_COLORS = ["#FDE68A", "#BFDBFE", "#FBCFE8", "#BBF7D0", "#E9D5FF", "#FED7AA", "#E5E7EB", "#FECACA"]
ROOF_COLORS = ["#B91C1C", "#1D4ED8", "#15803D", "#78350F", "#334155", "#7C3AED"]


class Room(Item):
    """Una caja-cuarto. Piso abajo, techo plano arriba y paredes con puerta a los lados."""
    is_room = True
    layer = 0
    W, HH = 3.2, 2.3
    FLOOR = 0.08          # grosor del piso (en H)
    DOOR = 1.35           # alto de la puerta
    walls = True
    wall_i = 0

    def __init__(self, *a):
        super().__init__(*a)
        self.wall = WALL_COLORS[self.wall_i % len(WALL_COLORS)]

    def save_state(self):
        d = {"wall": self.wall}
        if hasattr(self, "flip"):
            d["flip"] = self.flip
        return d

    def load_state(self, d):
        self.wall = d.get("wall", self.wall)
        if "flip" in d:
            self.flip = bool(d["flip"])

    def F(self, h):
        """Altura sobre el piso del cuarto, en H, para los slots."""
        return self.FLOOR + h

    def on_land(self, room):
        H = self.H
        if room is not None and abs(room.x - self.x) < (room.W + self.W) * H / 4:
            self.x = room.x                     # apilado: alinear con el de abajo
        for r in self.crew.items:               # pegar de lado al vecino
            if r is self or not r.is_room or not r.on_ground or abs(r.y - self.y) > 4:
                continue
            gap = abs(r.x - self.x) - (r.W + self.W) * H / 2
            if gap < 0.6 * H:      # pegado o encimado: lo acomoda junto al vecino
                self.x = r.x + sign(self.x - r.x) * (r.W + self.W) * H / 2

    def extra_menu(self, menu):
        def cycle():
            i = WALL_COLORS.index(self.wall) if self.wall in WALL_COLORS else -1
            self.wall = WALL_COLORS[(i + 1) % len(WALL_COLORS)]
        menu.addAction(tr("Cambiar color de pared")).triggered.connect(cycle)

    def draw(self, p):
        H = self.H
        w2, h = self.W / 2 * H, self.HH * H
        fl = self.FLOOR * H
        if self.walls:
            p.setPen(Qt.NoPen)
            c = QColor(self.wall)
            p.setBrush(c)
            p.drawRect(QRectF(-w2, -h, 2 * w2, h - fl))
            p.setBrush(c.darker(106))
            for i in range(int(self.W * 3)):
                if i % 2:
                    p.drawRect(QRectF(-w2 + i * H / 3, -h, H / 3, h - fl))
            p.setBrush(QColor(0, 0, 0, 22))
            p.drawRect(QRectF(-w2, -fl - 0.12 * H, 2 * w2, 0.12 * H))
        self.draw_inside(p)
        # piso, techo y paredes con puerta
        wood(p, QRectF(-w2, -fl, 2 * w2, fl), "#8B5A2B", 1)
        if self.walls:
            wall = QColor(self.wall).darker(150)
            p.setPen(Qt.NoPen)
            p.setBrush(wall)
            p.drawRect(QRectF(-w2, -h, 2 * w2, 0.08 * H))
            door_top = -fl - self.DOOR * H
            for x in (-w2, w2 - 0.08 * H):
                p.drawRect(QRectF(x, -h, 0.08 * H, h + door_top))

    def draw_inside(self, p):
        pass

    def window(self, p, x, y, w=0.6, hh=0.55):
        H = self.H
        r = QRectF(x * H, y * H, w * H, hh * H)
        p.setPen(QPen(QColor("#FFFFFF"), 0.04 * H))
        p.setBrush(QColor("#7DD3FC"))
        p.drawRect(r)
        p.drawLine(r.center().x(), r.top(), r.center().x(), r.bottom())
        p.drawLine(r.left(), r.center().y(), r.right(), r.center().y())


@item_type
class EmptyRoom(Room):
    key, label = "cuarto", "Cuarto vacío"

    def draw_inside(self, p):
        self.window(p, -0.3, -1.7)


@item_type
class Bedroom(Room):
    key, label, wall_i = "recamara", "Recámara", 4

    def make_slots(self):
        return [Slot(-0.45, 1, ["o_acostarse"], floor=self.F(0.38))]

    def draw_inside(self, p):
        H = self.H
        fl = self.FLOOR * H
        self.window(p, 0.5, -1.75)
        p.save()
        p.translate(0, -fl)
        wood(p, QRectF(-1.5 * H, -0.65 * H, 0.1 * H, 0.65 * H), "#8B5A2B")
        wood(p, QRectF(-1.45 * H, -0.3 * H, 1.75 * H, 0.16 * H), "#8B5A2B")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#F8FAFC"))
        p.drawRoundedRect(QRectF(-1.42 * H, -0.4 * H, 1.7 * H, 0.12 * H), 5, 5)
        p.setBrush(QColor("#E2E8F0"))
        p.drawRoundedRect(QRectF(-1.38 * H, -0.5 * H, 0.38 * H, 0.13 * H), 8, 8)
        p.setBrush(QColor("#EC4899"))
        p.drawRoundedRect(QRectF(-0.8 * H, -0.42 * H, 1.1 * H, 0.2 * H), 6, 6)
        wood(p, QRectF(0.75 * H, -0.45 * H, 0.4 * H, 0.45 * H), "#A16207")
        p.setBrush(QColor("#FDE68A"))
        p.drawPolygon(QPolygonF([QPointF(0.85 * H, -0.62 * H), QPointF(1.05 * H, -0.62 * H),
                                 QPointF(1.0 * H, -0.78 * H), QPointF(0.9 * H, -0.78 * H)]))
        p.setPen(QPen(QColor("#374151"), 0.02 * H))
        p.drawLine(QPointF(0.95 * H, -0.62 * H), QPointF(0.95 * H, -0.45 * H))
        p.restore()


@item_type
class DiningRoom(Room):
    key, label, wall_i = "comedor", "Comedor", 0

    def make_slots(self):
        return [Slot(-0.85, 1, ["o_comer", "o_cartas"], seat=self.F(0.44)),
                Slot(0.85, -1, ["o_comer", "o_cartas"], seat=self.F(0.44))]

    def draw_inside(self, p):
        H = self.H
        fl = self.FLOOR * H
        p.setPen(QPen(QColor("#374151"), 0.02 * H))
        p.drawLine(QPointF(0, -self.HH * H + 0.08 * H), QPointF(0, -1.8 * H))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FBBF24"))
        p.drawChord(QRectF(-0.25 * H, -1.95 * H, 0.5 * H, 0.35 * H), 180 * 16, 180 * 16)
        p.save()
        p.translate(0, -fl)
        for sx in (-1, 1):
            wood(p, QRectF(sx * 0.85 * H - 0.18 * H, -0.44 * H, 0.36 * H, 0.06 * H), "#92400E")
            p.setPen(QPen(QColor("#78350F"), 0.04 * H, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(sx * 1.05 * H, 0), QPointF(sx * 1.05 * H, -0.95 * H))
            p.drawLine(QPointF(sx * 0.68 * H, -0.4 * H), QPointF(sx * 0.68 * H, 0))
        p.setPen(QPen(QColor("#78350F"), 0.05 * H, Qt.SolidLine, Qt.RoundCap))
        for x in (-0.45, 0.45):
            p.drawLine(QPointF(x * H, -0.7 * H), QPointF(x * H, 0))
        wood(p, QRectF(-0.62 * H, -0.76 * H, 1.24 * H, 0.08 * H), "#B45309")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(QRectF(-0.5 * H, -0.79 * H, 1.0 * H, 0.03 * H))
        p.setBrush(QColor("#EF4444"))
        p.drawEllipse(QPointF(0, -0.84 * H), 0.08 * H, 0.05 * H)
        p.restore()


@item_type
class Kitchen(Room):
    key, label, W, wall_i = "cocina", "Cocina", 3.6, 3

    def make_slots(self):
        return [Slot(-0.95, -1, "o_refri", floor=self.FLOOR),
                Slot(-0.25, -1, "o_lavar", floor=self.FLOOR),
                Slot(1.35, -1, "o_cocinar", floor=self.FLOOR)]

    def draw_inside(self, p):
        H, t = self.H, self.t
        fl = self.FLOOR * H
        self.window(p, -0.85, -1.8, 0.6, 0.5)
        p.save()
        p.translate(0, -fl)
        p.setPen(QPen(QColor("#94A3B8"), 1.5))
        p.setBrush(QColor("#F1F5F9"))
        p.drawRoundedRect(QRectF(-1.72 * H, -1.45 * H, 0.52 * H, 1.45 * H), 6, 6)
        p.drawLine(QPointF(-1.72 * H, -0.95 * H), QPointF(-1.2 * H, -0.95 * H))
        p.setPen(QPen(QColor("#64748B"), 0.03 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-1.28 * H, -1.3 * H), QPointF(-1.28 * H, -1.05 * H))
        wood(p, QRectF(-0.95 * H, -0.68 * H, 0.75 * H, 0.68 * H), "#D6D3D1", 3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#94A3B8"))
        p.drawRect(QRectF(-0.8 * H, -0.7 * H, 0.45 * H, 0.06 * H))
        p.setPen(QPen(QColor("#94A3B8"), 0.03 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-0.58 * H, -0.7 * H), QPointF(-0.58 * H, -0.88 * H))
        p.drawLine(QPointF(-0.58 * H, -0.88 * H), QPointF(-0.5 * H, -0.85 * H))
        wood(p, QRectF(0.4 * H, -0.68 * H, 0.72 * H, 0.68 * H), "#374151", 3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#111827"))
        p.drawRect(QRectF(0.5 * H, -0.5 * H, 0.52 * H, 0.32 * H))
        cooking = self.slots[2].user is not None
        p.setBrush(QColor("#F97316") if cooking else QColor("#4B5563"))
        for x in (0.52, 0.85):
            p.drawRect(QRectF(x * H, -0.71 * H, 0.2 * H, 0.03 * H))
        if cooking:
            for i in range(3):
                k = (t * 0.6 + i / 3) % 1.0
                p.setBrush(QColor(230, 230, 230, int(140 * (1 - k))))
                p.drawEllipse(QPointF((0.75 + 0.08 * math.sin(t * 2 + i)) * H, -(0.8 + 0.5 * k) * H),
                              (0.04 + 0.05 * k) * H, (0.04 + 0.05 * k) * H)
        p.restore()


@item_type
class Garden(Room):
    key, label, wall_i = "huerto", "Huerto", 3
    walls = False
    CROPS = [("#F97316", "zanahoria"), ("#EF4444", "tomate"), ("#FACC15", "elote")]

    def __init__(self, *a):
        super().__init__(*a)
        self.growth = [random.randint(0, 2) for _ in range(3)]
        self.grow_t = 30.0

    def make_slots(self):
        return [Slot(-0.55, 1, ["o_regar"], floor=self.F(0.05)),
                Slot(0.55, -1, ["o_regar"], floor=self.F(0.05))]

    def actions_for(self, slot):
        if max(self.growth) >= 4 and random.random() < 0.7:
            return ["o_cosechar"]
        return ["o_regar"]

    def save_state(self):
        d = super().save_state()
        d["growth"] = list(self.growth)
        return d

    def load_state(self, d):
        super().load_state(d)
        g = d.get("growth")
        if isinstance(g, list) and len(g) == 3:
            self.growth = [int(v) for v in g]

    def on_used(self, s, slot):
        key = getattr(s, "item_action", "")
        if key == "o_cosechar":
            i = self.growth.index(max(self.growth))
            self.growth[i] = 0
        else:
            i = random.randrange(3)
            self.growth[i] = min(4, self.growth[i] + 1)

    def extra_tick(self, dt):
        self.grow_t -= dt
        if self.grow_t <= 0:
            self.grow_t = random.uniform(30, 60)
            i = random.randrange(3)
            self.growth[i] = min(4, self.growth[i] + 1)

    def draw_inside(self, p):
        H, t = self.H, self.t
        fl = self.FLOOR * H
        p.setPen(QPen(QColor("#A16207"), 0.035 * H, Qt.SolidLine, Qt.RoundCap))
        w2 = self.W / 2 * H
        for i in range(9):
            x = -w2 + 0.1 * H + i * (2 * w2 - 0.2 * H) / 8
            p.drawLine(QPointF(x, -fl), QPointF(x, -fl - 0.45 * H))
        p.drawLine(QPointF(-w2 + 0.1 * H, -fl - 0.35 * H), QPointF(w2 - 0.1 * H, -fl - 0.35 * H))
        p.setPen(Qt.NoPen)
        for i, (c, _) in enumerate(self.CROPS):
            x = (-1.0 + i * 1.0) * H
            p.setBrush(QColor("#713F12"))
            p.drawRoundedRect(QRectF(x - 0.4 * H, -fl - 0.1 * H, 0.8 * H, 0.1 * H), 4, 4)
            g = self.growth[i]
            for k in range(3):
                px = x + (k - 1) * 0.25 * H
                hgt = (0.06 + 0.07 * g) * H
                sway = 0.01 * H * math.sin(t * 2 + k + i)
                p.setPen(QPen(QColor("#16A34A"), 0.025 * H, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(px, -fl - 0.1 * H), QPointF(px + sway, -fl - 0.1 * H - hgt))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#22C55E"))
                p.drawEllipse(QPointF(px + sway - 0.04 * H, -fl - 0.1 * H - hgt * 0.7), 0.05 * H, 0.025 * H)
                p.drawEllipse(QPointF(px + sway + 0.04 * H, -fl - 0.1 * H - hgt * 0.8), 0.05 * H, 0.025 * H)
                if g >= 4:
                    p.setBrush(QColor(c))
                    p.drawEllipse(QPointF(px + sway, -fl - 0.1 * H - hgt), 0.045 * H, 0.045 * H)


@item_type
class LivingRoom(Room):
    key, label, wall_i = "sala", "Sala", 1

    def make_slots(self):
        return [Slot(-1.05, 1, ["o_sentarse", "o_sentarse_cel", "o_sentarse"], seat=self.F(0.42)),
                Slot(-0.45, 1, ["o_sentarse", "o_sentarse_cel", "o_sentarse"], seat=self.F(0.42))]

    def draw_inside(self, p):
        H, t = self.H, self.t
        fl = self.FLOOR * H
        p.save()
        p.translate(0, -fl)
        base = QColor("#0F766E")
        p.setPen(Qt.NoPen)
        p.setBrush(base.darker(110))
        p.drawRoundedRect(QRectF(-1.45 * H, -0.85 * H, 1.35 * H, 0.5 * H), 0.1 * H, 0.1 * H)
        p.setBrush(base)
        p.drawRoundedRect(QRectF(-1.5 * H, -0.42 * H, 1.45 * H, 0.32 * H), 0.06 * H, 0.06 * H)
        p.setBrush(QColor("#4A3426"))
        for x in (-1.4, -0.2):
            p.drawRect(QRectF(x * H, -0.1 * H, 0.06 * H, 0.1 * H))
        wood(p, QRectF(0.55 * H, -0.4 * H, 0.9 * H, 0.4 * H), "#78350F", 3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#111827"))
        p.drawRoundedRect(QRectF(0.55 * H, -1.1 * H, 0.9 * H, 0.62 * H), 5, 5)
        on = any(sl.user is not None for sl in self.slots)
        scr = QRectF(0.6 * H, -1.05 * H, 0.8 * H, 0.52 * H)
        if on:
            p.setBrush(QColor.fromHsvF((t * 0.05) % 1.0, 0.35, 0.95))
            p.drawRect(scr)
            p.setBrush(QColor("#EF4444"))
            p.drawEllipse(QPointF(scr.left() + (0.5 + 0.4 * math.sin(t * 1.3)) * scr.width(),
                                  scr.bottom() - abs(math.sin(t * 4)) * scr.height() * 0.7 - 0.06 * H),
                          0.05 * H, 0.05 * H)
        else:
            p.setBrush(QColor("#1F2937"))
            p.drawRect(scr)
        p.restore()


@item_type
class Study(Room):
    key, label, wall_i = "estudio", "Estudio", 6

    def make_slots(self):
        return [Slot(0.25, 1, "o_compu", seat=self.F(0.44)),
                Slot(-1.0, 0, "o_leer", floor=self.FLOOR)]

    def draw_inside(self, p):
        H, t = self.H, self.t
        fl = self.FLOOR * H
        p.save()
        p.translate(0, -fl)
        wood(p, QRectF(-1.5 * H, -1.6 * H, 0.75 * H, 1.6 * H), "#92400E", 3)
        p.setPen(Qt.NoPen)
        cols = ["#EF4444", "#3B82F6", "#22C55E", "#EAB308", "#A855F7", "#F97316"]
        for row in range(4):
            y = -1.55 * H + row * 0.4 * H
            p.setBrush(QColor("#78350F"))
            p.drawRect(QRectF(-1.48 * H, y + 0.32 * H, 0.71 * H, 0.04 * H))
            for i in range(6):
                p.setBrush(QColor(cols[(i + row) % 6]))
                p.drawRect(QRectF((-1.45 + i * 0.11) * H, y + 0.08 * H, 0.08 * H, 0.24 * H))
        wood(p, QRectF(0.07 * H, -0.44 * H, 0.32 * H, 0.06 * H), "#334155")
        p.setPen(QPen(QColor("#334155"), 0.035 * H))
        p.drawLine(QPointF(0.23 * H, -0.4 * H), QPointF(0.23 * H, 0))
        p.drawLine(QPointF(0.07 * H, -0.44 * H), QPointF(0.05 * H, -0.82 * H))
        p.setPen(QPen(QColor("#78350F"), 0.05 * H))
        for x in (0.55, 1.35):
            p.drawLine(QPointF(x * H, -0.68 * H), QPointF(x * H, 0))
        wood(p, QRectF(0.48 * H, -0.74 * H, 0.95 * H, 0.07 * H), "#A16207")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#111827"))
        p.drawRect(QRectF(0.85 * H, -1.2 * H, 0.42 * H, 0.32 * H))
        p.drawRect(QRectF(1.03 * H, -0.88 * H, 0.06 * H, 0.14 * H))
        on = self.slots[0].user is not None
        p.setBrush(QColor("#1E3A8A") if on else QColor("#1F2937"))
        p.drawRect(QRectF(0.88 * H, -1.17 * H, 0.36 * H, 0.26 * H))
        if on:
            for i in range(5):
                w = (0.08 + 0.2 * abs(math.sin(i * 1.7 + int(t * 3) * 0.5))) * H
                p.setBrush(QColor("#93C5FD") if i % 2 else QColor("#86EFAC"))
                p.drawRect(QRectF(0.91 * H, (-1.14 + i * 0.045) * H, w, 0.02 * H))
        p.restore()


@item_type
class Bathroom(Room):
    key, label, wall_i = "baño", "Baño", 1

    def make_slots(self):
        return [Slot(0.35, 1, "o_baño", floor=self.F(0.2))]

    def draw_inside(self, p):
        H, t = self.H, self.t
        fl = self.FLOOR * H
        p.save()
        p.translate(0, -fl)
        p.setPen(QPen(QColor("#CBD5E1"), 1))
        p.setBrush(QColor("#F1F5F9"))
        for i in range(int(self.W * 3)):
            for j in range(3):
                p.drawRect(QRectF((-1.6 + i / 3) * H, (-1.0 + j / 3) * H, H / 3, H / 3))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(QRectF(-0.4 * H, -0.5 * H, 1.6 * H, 0.5 * H), 0.2 * H, 0.2 * H)
        p.setBrush(QColor(125, 211, 252, 200))
        p.drawRect(QRectF(-0.3 * H, -0.45 * H, 1.4 * H, 0.08 * H))
        if self.slots[0].user is not None:
            p.setBrush(QColor(255, 255, 255, 230))
            for i in range(9):
                p.drawEllipse(QPointF((-0.25 + i * 0.16) * H, -0.5 * H - 0.03 * H * math.sin(t * 2 + i)),
                              0.07 * H, 0.06 * H)
        p.setBrush(QColor("#94A3B8"))
        p.drawRect(QRectF(-0.95 * H, -1.5 * H, 0.5 * H, 0.6 * H))
        p.setBrush(QColor("#BFDBFE"))
        p.drawRect(QRectF(-0.92 * H, -1.47 * H, 0.44 * H, 0.54 * H))
        p.restore()


@item_type
class Roof(Item):
    key, label, W, HH = "techo", "Techo", 3.5, 1.15
    is_roof = True
    layer = 1

    def __init__(self, *a):
        super().__init__(*a)
        self.color = ROOF_COLORS[0]
        self.flat = False

    def on_land(self, room):
        if room is not None:
            self.x = room.x

    def save_state(self):
        return {"color": self.color, "flat": self.flat}

    def load_state(self, d):
        self.color = d.get("color", self.color)
        self.flat = bool(d.get("flat", False))

    def extra_menu(self, menu):
        def cycle():
            i = ROOF_COLORS.index(self.color) if self.color in ROOF_COLORS else -1
            self.color = ROOF_COLORS[(i + 1) % len(ROOF_COLORS)]
        menu.addAction(tr("Cambiar color")).triggered.connect(cycle)
        menu.addAction(tr("Techo plano / de dos aguas")).triggered.connect(
            lambda: setattr(self, "flat", not self.flat))

    def bounds(self):
        if self.flat:
            return QRectF(-self.W / 2 * self.H, -0.3 * self.H, self.W * self.H, 0.3 * self.H)
        return super().bounds()

    def draw(self, p):
        H = self.H
        c = QColor(self.color)
        w2 = self.W / 2 * H
        p.setPen(QPen(c.darker(140), 0.03 * H, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(c)
        if self.flat:
            p.drawRect(QRectF(-w2, -0.25 * H, 2 * w2, 0.25 * H))
            p.setBrush(c.darker(120))
            p.drawRect(QRectF(-w2 + 0.1 * H, -0.32 * H, 2 * w2 - 0.2 * H, 0.08 * H))
            return
        p.drawPolygon(QPolygonF([QPointF(-w2, 0), QPointF(w2, 0), QPointF(0, -self.HH * H)]))
        p.setPen(QPen(c.darker(125), 0.02 * H))
        for i in range(1, 5):
            y = -self.HH * H * i / 5
            half = w2 * (1 - i / 5)
            p.drawLine(QPointF(-half, y), QPointF(half, y))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#7F1D1D"))
        p.drawRect(QRectF(0.75 * H, -0.85 * H, 0.25 * H, 0.45 * H))


ITEM_ORDER = ["sofa", "mesa", "picnic", "pelota", "trampolin", "columpio", "resbaladilla", "alberca",
              "fogata", "asador", "tele", "cama", "hamaca", "escritorio", "caballete", "pesas",
              "barra", "caja", "patineta", "maceta", "arbol", "pizza", "libro", "proyector"]
INSTRUMENT_ORDER = ["piano", "bateria", "guitarra", "trompeta", "violin", "microfono", "bocina"]


# ============================================================================
# Escaleras
class StairMixin:
    """Algo por donde se sube: stair_ends() -> (x_abajo, y_abajo, x_arriba, y_arriba)."""
    flip = False

    def stair_draw(self, p, x0, y0, x1, y1, color="#8B5A2B", rail="#475569"):
        H = self.H
        n = 9
        p.setPen(QPen(QColor(color).darker(140), 1.2))
        p.setBrush(QColor(color))
        for i in range(n):
            ax = x0 + (x1 - x0) * i / n
            ay = y0 + (y1 - y0) * (i + 1) / n
            w = (x1 - x0) / n
            p.drawRect(QRectF(min(ax, ax + w), ay, abs(w), y0 - ay))
        p.setPen(QPen(QColor(rail), 0.03 * H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x0, y0 - 0.55 * H), QPointF(x1, y1 - 0.55 * H))
        for i in range(0, n + 1, 3):
            x = x0 + (x1 - x0) * i / n
            y = y0 + (y1 - y0) * i / n
            p.drawLine(QPointF(x, y), QPointF(x, y - 0.55 * H))

    def extra_menu(self, menu):
        super().extra_menu(menu)
        menu.addAction(tr("Voltear escalera")).triggered.connect(lambda: setattr(self, "flip", not self.flip))


@item_type
class StairRoom(StairMixin, Room):
    key, label, W, wall_i = "escaleras", "Cubo de escaleras", 1.9, 6

    def stair_ends(self):
        H = self.H
        d = -1 if self.flip else 1
        return (self.x - d * 0.68 * H, self.y - self.FLOOR * H,
                self.x + d * 0.68 * H, self.y - (self.HH + self.FLOOR) * H)

    def draw_inside(self, p):
        H = self.H
        d = -1 if self.flip else 1
        x0, x1 = -d * 0.68 * H, d * 0.68 * H
        self.stair_draw(p, x0, -self.FLOOR * H, x1, -(self.HH - 0.08) * H)

    def draw(self, p):
        super().draw(p)
        H = self.H
        d = -1 if self.flip else 1   # hueco en el techo para salir arriba
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.wall))
        p.drawRect(QRectF(d * 0.2 * H if d > 0 else -0.85 * H, -self.HH * H, 0.65 * H, 0.08 * H))


@item_type
class Stairs(StairMixin, Item):
    key, label, W, HH = "escalera", "Escalera exterior", 1.6, 2.38

    def save_state(self):
        return {"flip": self.flip}

    def load_state(self, d):
        self.flip = bool(d.get("flip", False))

    def stair_ends(self):
        H = self.H
        d = -1 if self.flip else 1
        return self.x - d * 0.72 * H, self.y, self.x + d * 0.72 * H, self.y - self.HH * H

    def draw(self, p):
        H = self.H
        d = -1 if self.flip else 1
        self.stair_draw(p, -d * 0.72 * H, 0, d * 0.72 * H, -self.HH * H, "#9CA3AF", "#374151")
        p.setPen(QPen(QColor("#374151"), 0.05 * H))
        p.drawLine(QPointF(d * 0.7 * H, 0), QPointF(d * 0.7 * H, -self.HH * H))


def stairs_in(crew):
    out = []
    for it in crew.items:
        if hasattr(it, "stair_ends") and it.on_ground and not it.dragging:
            out.append((it, it.stair_ends()))
    return out


def find_route(crew, y0, yt, tol):
    """Busca qué escaleras tomar para ir del nivel y0 al nivel yt (BFS por pisos)."""
    if abs(y0 - yt) < tol:
        return []
    st = stairs_in(crew)
    frontier = [(y0, [])]
    seen = [y0]
    while frontier:
        y, path = frontier.pop(0)
        for it, (xb, yb, xt, ytop) in st:
            for (ya, xa, yb2, xb2) in ((yb, xb, ytop, xt), (ytop, xt, yb, xb)):
                if abs(ya - y) < tol:
                    np_ = path + [(it, xa, ya, xb2, yb2)]
                    if abs(yb2 - yt) < tol:
                        return np_
                    if all(abs(yb2 - s) > tol for s in seen):
                        seen.append(yb2)
                        frontier.append((yb2, np_))
    return None


ROOM_ORDER = ["cuarto", "recamara", "comedor", "cocina", "sala", "estudio", "baño", "huerto",
              "escaleras", "escalera", "techo"]
BUILD_KEYS = set(ROOM_ORDER)
