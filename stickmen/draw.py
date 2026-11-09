"""Dibujo de stickmen, cosméticos, objetos en la mano y globos de texto."""
from .core import *  # noqa: F401,F403

# Cosméticos disponibles en el creador: (clave, nombre)
COSMETICS = [
    ("gorra", "Gorra"), ("gorro", "Gorro con pompón"), ("copa", "Sombrero de copa"),
    ("corona", "Corona"), ("moño", "Moño"), ("margarita", "Margarita"),
    ("antenas", "Antenas"), ("cuernos", "Cuernitos"), ("aureola", "Aureola"),
    ("banda", "Banda ninja"), ("audifonos", "Audífonos"), ("lentes", "Lentes"),
    ("lentes_sol", "Lentes de sol"), ("parche", "Parche de pirata"), ("bigote", "Bigote"),
    ("bufanda", "Bufanda"), ("corbata", "Corbata"), ("capa", "Capa"),
]
TALL_ACCS = {"margarita": 1.25, "copa": 0.95, "corona": 0.5, "antenas": 0.95, "aureola": 0.6,
             "gorro": 0.4, "cuernos": 0.45}


def head_angle(a, b):
    d = b - a
    return math.degrees(math.atan2(d.x(), -d.y()))


def draw_stickman(p, j, H, spec, f, t, blink=False, look=0.0, prop=None, R=None):
    col = QColor(spec["color"])
    back = col.lighter(160) if col.lightness() < 90 else col.darker(125)
    acc = QColor(spec.get("accent", "#FFFFFF"))
    accs = spec.get("accs", [])
    hollow = spec.get("body") == "cabezon"
    w = H * 0.075
    R = head_radius(spec, H) if R is None else R
    r0 = 0.13 * H          # tamaño "normal" para escalar detalles finos

    def seg(c, *pts, width=w):
        p.setPen(QPen(c, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF(list(pts)))

    c = j["head"]
    h_ang = head_angle(j["neck"], j["head"])
    t_ang = head_angle(j["hip"], j["neck"])
    tor_len = math.hypot(j["neck"].x() - j["hip"].x(), j["neck"].y() - j["hip"].y())

    def torso_frame():
        p.save()
        p.translate(j["neck"])
        p.rotate(t_ang)

    # ---- capa (detrás de todo)
    if "capa" in accs:
        torso_frame()
        fl = math.sin(t * 6) * H * 0.05
        poly = QPolygonF([QPointF(-r0 * 0.5, 0), QPointF(r0 * 0.5, 0),
                          QPointF(-f * H * 0.12 + r0 * 0.4, tor_len + H * 0.2),
                          QPointF(-f * (H * 0.42 + fl), tor_len + H * 0.12 + fl)])
        p.setPen(Qt.NoPen)
        p.setBrush(acc.darker(115))
        p.drawPolygon(poly)
        p.restore()

    # ---- extremidades de atrás
    if prop == "guitar":
        draw_guitar(p, j, H, f)
    seg(back, j["sh"], j["elB"], j["haB"])
    seg(back, j["hip"], j["knB"], j["ftB"])

    if "bufanda" in accs:
        torso_frame()
        seg(acc, QPointF(0, 0), QPointF(-f * r0 * 0.8, r0 * 0.15 + r0 * 0.2 * math.sin(t * 9 + 1)),
            QPointF(-f * r0 * 1.6, r0 * 0.5 + r0 * 0.35 * math.sin(t * 9)), width=w * 0.8)
        p.restore()

    # ---- torso y pierna de enfrente
    seg(col, j["hip"], j["neck"])
    seg(col, j["hip"], j["knF"], j["ftF"])

    if "corbata" in accs:
        torso_frame()
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        x = f * w * 0.15
        p.drawPolygon(QPolygonF([QPointF(x - w * 0.35, w * 0.3), QPointF(x + w * 0.35, w * 0.3),
                                 QPointF(x + w * 0.5, tor_len * 0.55), QPointF(x, tor_len * 0.68),
                                 QPointF(x - w * 0.5, tor_len * 0.55)]))
        p.restore()

    # ---- cabeza
    if hollow:
        p.setPen(QPen(col, w, Qt.SolidLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, R - w / 2, R - w / 2)
    else:
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(c, R, R)

    p.save()
    p.translate(c)
    p.rotate(h_ang)
    ey = -R * 0.08 - look * R * 0.22
    if not hollow:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(spec.get("eyes", "#111111")))
        eh = R * 0.04 if blink else R * 0.2
        for dx in (0.18, 0.58):
            p.drawEllipse(QPointF(f * R * dx, ey), R * 0.12, eh)
    for kind in accs:
        draw_head_acc(p, kind, R, f, ey, w, t, acc, hollow)
    p.restore()

    if "bufanda" in accs:
        torso_frame()
        seg(acc, QPointF(-r0 * 0.55, -r0 * 0.05), QPointF(r0 * 0.55, -r0 * 0.05), width=w * 1.1)
        p.restore()

    # ---- brazo de enfrente y lo que trae en la mano
    if prop and prop != "guitar":
        draw_prop(p, prop, j, H, f, t)
    seg(col, j["sh"], j["elF"], j["haF"])
    if prop == "dumbbells":
        draw_dumbbell(p, j["haF"], H)


def draw_head_acc(p, kind, R, f, ey, w, t, acc, hollow):
    """Cosméticos en el marco de la cabeza (origen = centro, arriba = -y)."""
    def pen(width, color=None):
        p.setPen(QPen(color or acc, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

    if kind == "gorra":
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawChord(QRectF(-R * 1.06, -R * 1.12, R * 2.12, R * 2.12), 0, 180 * 16)
        pen(w * 0.75)
        p.drawLine(QPointF(f * R * 0.3, -R * 0.06), QPointF(f * R * 1.55, -R * 0.06))
    elif kind == "gorro":
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawChord(QRectF(-R * 1.05, -R * 1.2, R * 2.1, R * 2.2), 0, 180 * 16)
        p.setBrush(acc.darker(120))
        p.drawRoundedRect(QRectF(-R * 1.1, -R * 0.25, R * 2.2, R * 0.32), R * 0.12, R * 0.12)
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(QPointF(0, -R * 1.18), R * 0.24, R * 0.24)
    elif kind == "copa":
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawRoundedRect(QRectF(-R * 0.95, -R * 0.95, R * 1.9, R * 0.16), R * 0.05, R * 0.05)
        p.drawRect(QRectF(-R * 0.6, -R * 1.9, R * 1.2, R * 1.0))
        p.setBrush(acc.darker(150) if acc.lightness() > 60 else acc.lighter(180))
        p.drawRect(QRectF(-R * 0.6, -R * 1.12, R * 1.2, R * 0.18))
    elif kind == "corona":
        p.setPen(QPen(acc.darker(130), max(1.0, w * 0.15)))
        p.setBrush(acc)
        y0, y1 = -R * 0.75, -R * 1.45
        xs = [-0.62, -0.31, 0, 0.31, 0.62]
        pts = [QPointF(-R * 0.62, y0)]
        for i, x in enumerate(xs):
            pts.append(QPointF(R * x, y1 if i % 2 == 0 else y0 - R * 0.28))
        pts.append(QPointF(R * 0.62, y0))
        p.drawPolygon(QPolygonF(pts))
        p.setBrush(QColor("#EF4444"))
        p.drawEllipse(QPointF(0, -R * 0.92), R * 0.09, R * 0.09)
    elif kind == "moño":
        b = QPointF(-f * R * 0.65, -R * 0.8)
        s = R * 0.55
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawPolygon(QPolygonF([b, b + QPointF(-s, -s * 0.7), b + QPointF(-s, s * 0.7)]))
        p.drawPolygon(QPolygonF([b, b + QPointF(s, -s * 0.7), b + QPointF(s, s * 0.7)]))
        p.drawEllipse(b, s * 0.3, s * 0.3)
    elif kind == "margarita":
        sway = R * 0.12 * math.sin(t * 2.5)
        top = QPointF(-f * R * 0.25 + sway, -R * 1.85)
        pen(w * 0.32, QColor("#15803D"))
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(-f * R * 0.1, -R * 0.95), top)
        p.setPen(QPen(QColor(0, 0, 0, 70), 1.0))
        p.setBrush(acc)
        for i in range(8):
            p.save()
            p.translate(top)
            p.rotate(i * 45 + t * 10)
            p.drawEllipse(QPointF(R * 0.33, 0), R * 0.27, R * 0.13)
            p.restore()
        p.setBrush(QColor("#FACC15"))
        p.drawEllipse(top, R * 0.18, R * 0.18)
    elif kind == "antenas":
        for dx, ph in ((-0.35, 0), (0.35, 1.5)):
            tip = QPointF(R * (dx * 1.6) + R * 0.1 * math.sin(t * 3 + ph), -R * 1.75)
            pen(w * 0.3)
            p.drawLine(QPointF(R * dx, -R * 0.9), tip)
            p.setPen(Qt.NoPen)
            p.setBrush(acc)
            p.drawEllipse(tip, R * 0.17, R * 0.17)
    elif kind == "cuernos":
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        for sx in (-1, 1):
            base = QPointF(sx * R * 0.5, -R * 0.82)
            p.drawPolygon(QPolygonF([base + QPointF(-R * 0.2, 0), base + QPointF(R * 0.2, 0),
                                     base + QPointF(sx * R * 0.28, -R * 0.55)]))
    elif kind == "aureola":
        pen(w * 0.4)
        p.setBrush(Qt.NoBrush)
        y = -R * 1.45 + R * 0.05 * math.sin(t * 2)
        p.drawEllipse(QPointF(0, y), R * 0.6, R * 0.16)
    elif kind == "banda":
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawRect(QRectF(-R * 1.0, -R * 0.55, R * 2.0, R * 0.26))
        pen(w * 0.45)
        k = QPointF(-f * R * 0.95, -R * 0.42)
        for ph in (0, 1.2):
            p.drawLine(k, k + QPointF(-f * R * 0.75, R * (0.2 + 0.25 * math.sin(t * 8 + ph))))
    elif kind == "audifonos":
        pen(w * 0.55)
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(-R * 1.2, -R * 1.25, R * 2.4, R * 2.4), 15 * 16, 150 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawEllipse(QPointF(-f * R * 0.15, R * 0.05), R * 0.42, R * 0.58)
    elif kind == "lentes":
        pen(w * 0.28)
        p.setBrush(QColor(255, 255, 255, 45))
        r = R * 0.27
        for dx in (0.14, 0.68):
            p.drawEllipse(QPointF(f * R * dx, ey), r, r)
        p.drawLine(QPointF(f * R * (0.14 - 0.27), ey), QPointF(-f * R * 0.88, ey + R * 0.08))
    elif kind == "lentes_sol":
        pen(w * 0.28)
        p.setBrush(QColor(15, 15, 20))
        p.drawRoundedRect(QRectF(min(f * R * 0.0, f * R * 0.95), ey - R * 0.2, R * 0.95, R * 0.36),
                          R * 0.14, R * 0.14)
        p.drawLine(QPointF(0, ey - R * 0.05), QPointF(-f * R * 0.88, ey + R * 0.05))
        p.setPen(QPen(QColor(255, 255, 255, 150), w * 0.15))
        p.drawLine(QPointF(f * R * 0.2, ey - R * 0.1), QPointF(f * R * 0.35, ey - R * 0.1))
    elif kind == "parche":
        pen(w * 0.22, QColor(20, 20, 20))
        p.drawLine(QPointF(-R * 0.75, -R * 0.65), QPointF(R * 0.85, R * 0.35))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 20, 20))
        p.drawEllipse(QPointF(f * R * 0.5, ey + R * 0.02), R * 0.25, R * 0.22)
    elif kind == "bigote":
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        y = R * 0.32
        for dx in (0.28, 0.62):
            p.drawEllipse(QPointF(f * R * dx, y), R * 0.2, R * 0.1)


# ---------------------------------------------------------------- objetos en la mano
def _forearm(j, side="F"):
    el, ha = j["el" + side], j["ha" + side]
    d = ha - el
    L = math.hypot(d.x(), d.y()) or 1.0
    return ha, QPointF(d.x() / L, d.y() / L)


def draw_prop(p, prop, j, H, f, t):
    ha, d = _forearm(j)
    ang = math.degrees(math.atan2(d.y(), d.x()))
    p.save()
    if prop == "phone":
        p.translate(ha)
        p.rotate(ang + 90)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(25, 25, 35))
        p.drawRoundedRect(QRectF(-H * 0.045, -H * 0.085, H * 0.09, H * 0.15), H * 0.015, H * 0.015)
        p.setBrush(QColor(120, 200, 255))
        p.drawRect(QRectF(-H * 0.033, -H * 0.07, H * 0.066, H * 0.11))
    elif prop == "book":
        p.translate(ha + QPointF(f * H * 0.02, -H * 0.04))
        p.setPen(QPen(QColor(120, 60, 30), H * 0.012))
        p.setBrush(QColor(250, 245, 230))
        p.drawPolygon(QPolygonF([QPointF(0, 0), QPointF(f * H * 0.12, -H * 0.06),
                                 QPointF(f * H * 0.12, H * 0.06), QPointF(0, H * 0.1)]))
        p.drawPolygon(QPolygonF([QPointF(0, 0), QPointF(-f * H * 0.1, -H * 0.05),
                                 QPointF(-f * H * 0.1, H * 0.07), QPointF(0, H * 0.1)]))
    elif prop == "bat":
        tip = ha + d * (H * 0.55)
        p.setPen(QPen(QColor(150, 95, 45), H * 0.04, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(ha - d * (H * 0.04), ha + d * (H * 0.3))
        p.setPen(QPen(QColor(170, 110, 55), H * 0.065, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(ha + d * (H * 0.28), tip)
    elif prop == "sandwich":
        p.translate(ha)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(230, 190, 120))
        p.drawRoundedRect(QRectF(-H * 0.06, -H * 0.04, H * 0.12, H * 0.08), H * 0.02, H * 0.02)
        p.setBrush(QColor(110, 190, 80))
        p.drawRect(QRectF(-H * 0.065, -H * 0.005, H * 0.13, H * 0.015))
    elif prop == "slice":
        p.translate(ha)
        p.rotate(ang)
        p.setPen(QPen(QColor(200, 140, 60), H * 0.015))
        p.setBrush(QColor(250, 200, 70))
        p.drawPolygon(QPolygonF([QPointF(0, -H * 0.04), QPointF(0, H * 0.04), QPointF(H * 0.13, 0)]))
        p.setBrush(QColor(200, 50, 40))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(H * 0.04, 0), H * 0.012, H * 0.012)
    elif prop == "stick":
        tip = ha + QPointF(f * H * 0.55, H * 0.12)
        p.setPen(QPen(QColor(120, 80, 40), H * 0.018, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(ha, tip)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(250, 245, 235) if math.sin(t * 0.7) < 0.5 else QColor(220, 170, 110))
        p.drawRoundedRect(QRectF(tip.x() - H * 0.035, tip.y() - H * 0.025, H * 0.07, H * 0.05),
                          H * 0.015, H * 0.015)
    elif prop == "can":
        p.translate(ha)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(80, 160, 210))
        p.drawRoundedRect(QRectF(-H * 0.05, -H * 0.02, H * 0.1, H * 0.09), H * 0.015, H * 0.015)
        p.setPen(QPen(QColor(80, 160, 210), H * 0.02, Qt.SolidLine, Qt.RoundCap))
        sp = QPointF(f * H * 0.16, H * 0.0)
        p.drawLine(QPointF(f * H * 0.04, H * 0.04), sp)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(110, 180, 255, 200))
        for i in range(4):
            k = (t * 2.5 + i / 4) % 1.0
            p.drawEllipse(sp + QPointF(f * H * 0.05 * k, H * 0.35 * k), H * 0.012, H * 0.018)
    elif prop == "dumbbells":
        draw_dumbbell(p, j["haB"], H)
    p.restore()


def draw_dumbbell(p, c, H):
    p.save()
    p.setPen(QPen(QColor(70, 70, 80), H * 0.02, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(c + QPointF(-H * 0.06, 0), c + QPointF(H * 0.06, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(40, 40, 48))
    for dx in (-0.065, 0.065):
        p.drawRoundedRect(QRectF(c.x() + H * dx - H * 0.02, c.y() - H * 0.04, H * 0.04, H * 0.08),
                          H * 0.01, H * 0.01)
    p.restore()


def draw_guitar(p, j, H, f):
    body = j["hip"] + QPointF(f * H * 0.08, -H * 0.06)
    head = j["haF"] + QPointF(f * H * 0.06, -H * 0.03)
    p.save()
    p.setPen(QPen(QColor(90, 55, 25), H * 0.03, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(body, head)
    p.setPen(QPen(QColor(110, 60, 20), H * 0.012))
    p.setBrush(QColor(205, 120, 50))
    ang = math.degrees(math.atan2(head.y() - body.y(), head.x() - body.x()))
    p.translate(body)
    p.rotate(ang)
    p.drawEllipse(QPointF(-H * 0.02, 0), H * 0.11, H * 0.085)
    p.setBrush(QColor(60, 30, 10))
    p.drawEllipse(QPointF(0, 0), H * 0.025, H * 0.025)
    p.restore()


# ---------------------------------------------------------------- efectos
def draw_impact(p, c, H, k, scale=1.0):
    """Destello de golpe. k va de 1 a 0 mientras se desvanece."""
    r1, r2 = H * (0.10 + 0.08 * (1 - k)) * scale, H * 0.05 * scale
    pts = []
    for i in range(16):
        a = i * math.pi / 8
        r = r1 if i % 2 == 0 else r2
        pts.append(c + QPointF(math.cos(a) * r, math.sin(a) * r))
    p.setPen(QPen(QColor(40, 40, 40, int(220 * k)), H * 0.02))
    p.setBrush(QColor(255, 230, 90, int(255 * k)))
    p.drawPolygon(QPolygonF(pts))


RED_WORDS = ("!", "¡Ven!", "grr", "¡Strike!", "¡Ring! ¡Ring!")


def draw_bubble(p, c, H, text):
    f = QFont()
    f.setBold(True)
    f.setPixelSize(max(9, int(H * 0.15)))
    fm = QFontMetricsF(f)
    tw = fm.horizontalAdvance(text)
    h = H * 0.22
    wd = max(h, tw + H * 0.12)
    rect = QRectF(c.x() - wd / 2, c.y() - h / 2, wd, h)
    p.setPen(QPen(QColor(30, 30, 30), H * 0.02))
    p.setBrush(QColor(255, 255, 255))
    p.drawPolygon(QPolygonF([QPointF(c.x() - h * 0.18, rect.bottom() - 1),
                             QPointF(c.x() + h * 0.18, rect.bottom() - 1),
                             QPointF(c.x(), rect.bottom() + h * 0.3)]))
    p.drawRoundedRect(rect, h / 2, h / 2)
    p.setFont(f)
    p.setPen(QColor(220, 40, 40) if text in RED_WORDS else QColor(35, 35, 45))
    p.drawText(rect, Qt.AlignCenter, text)


def draw_speed_lines(p, H, f, color, t):
    c = QColor(color)
    c.setAlpha(110)
    p.setPen(QPen(c, H * 0.03, Qt.SolidLine, Qt.RoundCap))
    for k in range(3):
        y = -H * (0.05 + 0.14 * k)
        x0 = -f * H * (0.3 + 0.05 * k)
        L = H * (0.3 + 0.1 * math.sin(t * 20 + k * 2))
        p.drawLine(QPointF(x0, y), QPointF(x0 - f * L, y))


def bubble_top(j, H, spec, R=None):
    """Altura (relativa a la cadera) donde va el globo de texto."""
    R = head_radius(spec, H) if R is None else R
    top = min(min(pt.y() for pt in j.values()), j["head"].y() - R)
    extra = max([TALL_ACCS.get(a, 0) for a in spec.get("accs", [])] + [0])
    return top - extra * R - H * 0.24
