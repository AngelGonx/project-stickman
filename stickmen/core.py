"""Base: ajustes, pantallas, poses y esqueleto."""
import math
import random
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QElapsedTimer
from PySide6.QtGui import (QPainter, QPen, QColor, QGuiApplication, QPixmap,
                           QIcon, QAction, QCursor, QPolygonF, QFont, QFontMetricsF)
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon

# ----------------------------------------------------------------------------
# Ajustes
# ----------------------------------------------------------------------------
HEIGHT = 90            # altura del stickman en píxeles
GRAVITY = 2400.0       # px/s²
WALK_SPEED = 85.0      # px/s
RUN_SPEED = 210.0      # px/s
SPRINT_SPEED = 420.0   # px/s ("correr de la nada")
FPS = 60

# Carpeta donde se guardan sesión y personajes (junto al programa)
DATA_DIR = Path(__file__).resolve().parent.parent / "datos"

# Qué tan inquietos son: 1 = normal, 0.5 = tranquilos, 2 = hiperactivos
ACTIVIDAD = 1.0
# Cada cuánto, en promedio (segundos), a uno le da por salir corriendo de la nada
SPRINT_CADA = 75.0
# Segundos de espera entre encuentros de una misma pareja
ENCUENTRO_PAUSA = (25.0, 50.0)
# Qué pasa cuando dos se cruzan (pesos relativos)
ENCUENTRO = dict(saludar=24, convivir=24, traes=10, pelear=20, nada=22)

# Elenco original (siempre disponible). accs = lista de cosméticos, body = normal | cabezon
ROSTER = [
    dict(id="uva", name="Uva", color="#8B5CF6", accent="#22D3EE", eyes="#1F1147", accs=["bufanda"], body="normal"),
    dict(id="chicle", name="Chicle", color="#EC4899", accent="#7C3AED", eyes="#3B0A24", accs=["moño"], body="normal"),
    dict(id="ola", name="Ola", color="#14B8A6", accent="#1E293B", eyes="#06302B", accs=["gorra"], body="normal"),
    dict(id="tinta", name="Tinta", color="#2B2B2B", accent="#EF4444", eyes="#FFFFFF", accs=["audifonos"], body="normal"),
    dict(id="marino", name="Marino", color="#1E3A8A", accent="#FBBF24", eyes="#E0E7FF", accs=["lentes"], body="normal"),
    dict(id="brote", name="Brote", color="#22C55E", accent="#FFFFFF", eyes="#052E16", accs=["margarita"], body="normal"),
]


def head_radius(spec, H):
    return H * (0.2 if spec.get("body") == "cabezon" else 0.13)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def sign(v):
    return 1 if v >= 0 else -1


def smooth(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def wrap_deg(a):
    return ((a + 180.0) % 360.0) - 180.0


def arc(u, a, b, h):
    """Parábola de altura h entre u=a y u=b (para saltos)."""
    if a < u < b:
        x = (u - a) / (b - a)
        return 4 * h * x * (1 - x)
    return 0.0


# ----------------------------------------------------------------------------
# Pantallas: dónde está el piso
# ----------------------------------------------------------------------------
def desktop_bounds():
    gs = [s.availableGeometry() for s in QGuiApplication.screens()]
    return (min(g.left() for g in gs), max(g.right() for g in gs),
            min(g.top() for g in gs))


def ground_at(x):
    """Y del piso (borde superior de la barra de tareas) en la coordenada x."""
    best = None
    for s in QGuiApplication.screens():
        g = s.availableGeometry()
        if g.left() <= x <= g.right():
            y = g.bottom() + 1
            best = y if best is None else max(best, y)
    return best


# ----------------------------------------------------------------------------
# Poses. Ángulos en grados: 0 = hacia abajo, 90 = hacia donde mira, 180 = arriba.
# B = extremidad de atrás, F = de enfrente.
# rot = giro de todo el cuerpo (+ hacia adelante), lift = altura sobre el piso (en H).
# ----------------------------------------------------------------------------
KEYS = ("lean", "tilt", "thB", "shB", "thF", "shF", "uaB", "faB", "uaF", "faF",
        "rot", "lift")


def P(**k):
    d = dict.fromkeys(KEYS, 0.0)
    d.update(k)
    return d


def W(p, **k):
    d = dict(p)
    d.update(k)
    return d


def lerp_pose(a, b, k):
    return {key: a[key] + (b[key] - a[key]) * k for key in KEYS}


STAND = P(lean=2, thB=-4, shB=-4, thF=4, shF=4, uaB=-6, faB=-2, uaF=8, faF=14)


def S(**k):
    return W(STAND, **k)


def kf(u, frames):
    """Interpola suavemente entre keyframes [(u, pose), ...]."""
    if u <= frames[0][0]:
        return dict(frames[0][1])
    for (u0, p0), (u1, p1) in zip(frames, frames[1:]):
        if u <= u1:
            k = (u - u0) / (u1 - u0) if u1 > u0 else 1.0
            return lerp_pose(p0, p1, smooth(k))
    return dict(frames[-1][1])


def held(u, p, a=0.15, base=None):
    """Entra a la pose p, la sostiene y regresa a estar parado."""
    b = base if base is not None else STAND
    if u < a:
        return lerp_pose(b, p, smooth(u / a))
    if u > 1 - a:
        return lerp_pose(p, b, smooth((u - 1 + a) / a))
    return p


def pose_stand(t):
    b = math.sin(t * 2.2)
    return P(lean=2 + b, tilt=3 * math.sin(t * 0.7),
             thB=-4, shB=-4, thF=4, shF=4,
             uaB=-6 + 2 * b, faB=-2 + 2 * b, uaF=8 - 2 * b, faF=14 - 2 * b)


# Ciclos de pierna (fase 0..1 -> ángulo de muslo, ángulo de espinilla).
# Caminar: contacto, amortiguación, paso, impulso, recogida, alcance.
WALK_LEG = [(0.00, (24, 16)), (0.12, (15, -14)), (0.30, (2, -3)), (0.46, (-20, -16)),
            (0.56, (-22, -40)), (0.70, (-4, -66)), (0.85, (22, -34)), (1.00, (24, 16))]
# Correr: rodillas altas, patada atrás y fase de vuelo.
RUN_LEG = [(0.00, (30, 14)), (0.12, (12, -26)), (0.30, (-26, -22)), (0.42, (-40, -60)),
           (0.58, (-14, -118)), (0.75, (48, -62)), (0.88, (58, -4)), (1.00, (30, 14))]


def _cycle(table, ph):
    ph %= 1.0
    for (u0, (a0, b0)), (u1, (a1, b1)) in zip(table, table[1:]):
        if ph <= u1:
            k = smooth((ph - u0) / (u1 - u0))
            return a0 + (a1 - a0) * k, b0 + (b1 - b0) * k
    return table[-1][1]


def pose_walk(phase, amp=1.0, lean=5):
    """Caminar/correr. amp<1 = pasitos cortos, 1 = caminar, >=1.45 = correr."""
    g = clamp((amp - 1.0) / 0.45, 0.0, 1.0)          # 0 caminar ... 1 correr
    sw = min(amp, 1.0) if g == 0 else 1.0
    sr = max(1.0, amp / 1.45)

    def leg(ph):
        wt, ws = _cycle(WALK_LEG, ph)
        rt, rs = _cycle(RUN_LEG, ph)
        th = wt * sw * (1 - g) + rt * sr * g
        sh = ws * sw * (1 - g) + rs * sr * g
        return th, sh

    thF, shF = leg(phase)
    thB, shB = leg(phase + 0.5)
    c = math.cos(2 * math.pi * (phase - 0.04))       # brazos opuestos a las piernas
    arm = (26 * sw) * (1 - g) + (52 * sr) * g
    uaF, uaB = -arm * c, arm * c
    bendF = (18 + 14 * (1 - c) / 2) * (1 - g) + 95 * g
    bendB = (18 + 14 * (1 + c) / 2) * (1 - g) + 95 * g
    bob = math.cos(4 * math.pi * phase)
    lift = 0.07 * g * max(0.0, math.sin(4 * math.pi * (phase - 0.33))) * sr
    return P(lean=lean + 2.5 * bob * (1 - g * 0.5), tilt=-lean * 0.45 - 2 * bob,
             thB=thB, shB=shB, thF=thF, shF=shF,
             uaB=uaB, faB=uaB + bendB, uaF=uaF, faF=uaF + bendF, lift=lift)


def stride(speed, H):
    """Largo de un ciclo completo (dos pasos) según la velocidad."""
    return H * (0.7 + abs(speed) / 450.0)


def pose_wave(t):
    return W(pose_stand(t), uaF=150, faF=165 + 25 * math.sin(t * 11), uaB=-8, faB=-2, tilt=-6)


def pose_watch(t, look):
    return W(pose_stand(t), tilt=-look * 28, lean=2 - look * 6)


def pose_sit(t):
    return P(lean=-12 + 1.5 * math.sin(t * 1.5), tilt=-4 + 4 * math.sin(t * 0.6),
             thB=135, shB=45, thF=92, shF=88,
             uaB=60, faB=100, uaF=-35, faF=-35)


CROUCH = P(lean=22, thB=50, shB=-25, thF=58, shF=-18, uaB=-40, faB=-15, uaF=-30, faF=-5)
TUCK = P(lean=8, thB=75, shB=-5, thF=85, shF=5, uaB=150, faB=165, uaF=160, faF=175)
BALL = P(lean=30, tilt=20, thB=105, shB=-20, thF=115, shF=-10, uaB=85, faB=20, uaF=95, faF=10)
REACH = P(lean=-4, tilt=-20, thB=-15, shB=-30, thF=30, shF=5, uaB=150, faB=160, uaF=172, faF=178)
FALL = P(lean=4, thB=-10, shB=-14, thF=20, shF=8, uaB=110, faB=130, uaF=120, faF=140)
LIE = P(rot=-90, tilt=25, thB=-3, shB=-6, thF=4, shF=2, uaB=-25, faB=-10, uaF=20, faF=30)
FACEDOWN = P(rot=88, tilt=-25, thB=-5, shB=5, thF=5, shF=10, uaB=160, faB=170, uaF=170, faF=178)
SITUP = P(lean=-15, tilt=5, thB=95, shB=85, thF=90, shF=80, uaB=-40, faB=-30, uaF=-20, faF=-10)


def pose_flail(t):
    s = math.sin(t * 13)
    return P(lean=10 * math.sin(t * 7), tilt=10 * math.sin(t * 9),
             thB=35 * s, shB=35 * s - 30, thF=-35 * s, shF=-35 * s - 30,
             uaB=140 + 45 * math.sin(t * 16), faB=170 + 45 * math.sin(t * 16 + 1),
             uaF=140 + 45 * math.sin(t * 16 + math.pi),
             faF=170 + 45 * math.sin(t * 16 + math.pi + 1))


def pose_dangle(t, sway):
    w = math.sin(t * 4)
    return P(lean=sway * 0.5, tilt=sway * 0.3,
             thB=sway + 5 + 4 * w, shB=sway + 2, thF=sway - 5 - 4 * w, shF=sway - 2,
             uaB=sway + 25 + 6 * math.sin(t * 5), faB=sway + 15,
             uaF=sway - 15 + 6 * math.sin(t * 5 + 2), faF=sway - 5)


def pose_guard(t, shuffle=0.0):
    s = 3 * math.sin(t * 8) + shuffle
    return P(lean=10, tilt=-4, thB=-20 + s, shB=-20 + s, thF=22 - s, shF=10 - s,
             uaB=40, faB=145, uaF=55, faF=150)


JAB = P(lean=18, tilt=4, thB=-24, shB=-24, thF=26, shF=12, uaB=45, faB=140, uaF=88, faF=90)
CROSS = P(lean=24, tilt=4, thB=-30, shB=-30, thF=28, shF=14, uaB=86, faB=90, uaF=50, faF=150)
UPPER = P(lean=-8, tilt=-12, thB=-20, shB=-20, thF=25, shF=10, uaB=40, faB=140,
          uaF=150, faF=175, lift=0.05)
KICK = P(lean=-18, tilt=10, thB=-8, shB=-8, thF=98, shF=92, uaB=-55, faB=-30, uaF=60, faF=140)
BLOCK = P(lean=-10, tilt=8, thB=-26, shB=-26, thF=18, shF=8, uaB=70, faB=175, uaF=80, faF=175)


# ----------------------------------------------------------------------------
# Esqueleto: de pose a puntos (relativos a la cadera)
# ----------------------------------------------------------------------------
def solve(pose, H, f, R=None):
    T = 0.30 * H
    R = 0.13 * H if R is None else R
    TH, SH, UA, FA = 0.22 * H, 0.22 * H, 0.17 * H, 0.17 * H

    def v(a, L):
        r = math.radians(a)
        return QPointF(math.sin(r) * L * f, math.cos(r) * L)

    def up(a, L):
        r = math.radians(a)
        return QPointF(math.sin(r) * L * f, -math.cos(r) * L)

    hip = QPointF(0, 0)
    neck = up(pose["lean"], T)
    head = neck + up(pose["lean"] + pose["tilt"], R * (1.15 if R < 0.16 * H else 1.05))
    sh = neck * 0.9
    j = dict(hip=hip, neck=neck, head=head, sh=sh)
    j["knB"] = hip + v(pose["thB"], TH)
    j["ftB"] = j["knB"] + v(pose["shB"], SH)
    j["knF"] = hip + v(pose["thF"], TH)
    j["ftF"] = j["knF"] + v(pose["shF"], SH)
    j["elB"] = sh + v(pose["uaB"], UA)
    j["haB"] = j["elB"] + v(pose["faB"], FA)
    j["elF"] = sh + v(pose["uaF"], UA)
    j["haF"] = j["elF"] + v(pose["faF"], FA)

    rot = math.radians(pose["rot"]) * f
    if abs(rot) > 1e-6:
        c = QPointF(0, -0.15 * H)
        cs, sn = math.cos(rot), math.sin(rot)
        for k, pt in j.items():
            dx, dy = pt.x() - c.x(), pt.y() - c.y()
            j[k] = QPointF(c.x() + dx * cs - dy * sn, c.y() + dx * sn + dy * cs)
    return j


def contact(j, H, R=None):
    """Qué tan abajo de la cadera queda el punto más bajo del cuerpo."""
    w = H * 0.0375
    R = 0.13 * H if R is None else R
    m = max(pt.y() + w for k, pt in j.items() if k != "head")
    return max(m, j["head"].y() + R)


