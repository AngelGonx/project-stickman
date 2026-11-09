#!/usr/bin/env python3
"""
Desk Stickmen — stickmen animados que viven sobre tu barra de tareas.

Cada stickman es una ventanita transparente, siempre encima, que camina por el
"piso" (el borde superior de la barra de tareas). Por su cuenta caminan, se
sientan, hacen decenas de acciones (mortales, lagartijas, bailes, dormir...),
de repente salen corriendo, se saludan, juegan entre ellos, se pelean y notan
el cursor para perseguirlo. Los puedes agarrar y lanzar con el mouse, hacer
clic para que reaccionen o clic derecho para darles órdenes. Se controlan
desde el ícono de la bandeja del sistema.

Requisitos:  pip install PySide6
Ejecutar:    python desk_stickmen.py
"""
import math
import random
import sys

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QElapsedTimer
from PySide6.QtGui import (QPainter, QPen, QColor, QGuiApplication, QPixmap,
                           QIcon, QAction, QCursor, QPolygonF, QFont, QFontMetricsF)
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon

# ----------------------------------------------------------------------------
# Ajustes
# ----------------------------------------------------------------------------
HEIGHT = 90            # altura del stickman en píxeles
GRAVITY = 2400.0       # px/s²
WALK_SPEED = 70.0      # px/s
RUN_SPEED = 190.0      # px/s
SPRINT_SPEED = 420.0   # px/s ("correr de la nada")
FPS = 60

# Qué tan inquietos son: 1 = normal, 0.5 = tranquilos, 2 = hiperactivos
ACTIVIDAD = 1.0
# Cada cuánto, en promedio (segundos), a uno le da por salir corriendo de la nada
SPRINT_CADA = 75.0
# Segundos de espera entre encuentros de una misma pareja
ENCUENTRO_PAUSA = (25.0, 50.0)
# Qué pasa cuando dos se cruzan (pesos relativos)
ENCUENTRO = dict(saludar=24, convivir=24, traes=10, pelear=20, nada=22)

# Elenco original. acc: bufanda | moño | gorra | audifonos | lentes | margarita
ROSTER = [
    dict(name="Uva",    color="#8B5CF6", accent="#22D3EE", acc="bufanda",   eyes="#1F1147"),
    dict(name="Chicle", color="#EC4899", accent="#7C3AED", acc="moño",      eyes="#3B0A24"),
    dict(name="Ola",    color="#14B8A6", accent="#1E293B", acc="gorra",     eyes="#06302B"),
    dict(name="Tinta",  color="#2B2B2B", accent="#EF4444", acc="audifonos", eyes="#FFFFFF"),
    dict(name="Marino", color="#1E3A8A", accent="#FBBF24", acc="lentes",    eyes="#E0E7FF"),
    dict(name="Brote",  color="#22C55E", accent="#FFFFFF", acc="margarita", eyes="#052E16"),
]


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


def pose_walk(phase, amp=1.0, lean=5):
    t = 2 * math.pi * phase

    def leg(a):
        th = 26 * amp * math.sin(a)
        sh = th - (6 + 40 * amp * max(0.0, math.cos(a)))
        return th, sh

    thF, shF = leg(t)
    thB, shB = leg(t + math.pi)
    arm = 24 * amp
    bend = 20 + 80 * (amp - 1)
    uaF = -arm * math.sin(t)
    uaB = arm * math.sin(t)
    return P(lean=lean, tilt=0, thB=thB, shB=shB, thF=thF, shF=shF,
             uaB=uaB, faB=uaB + bend, uaF=uaF, faF=uaF + bend)


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
def solve(pose, H, f):
    T, R = 0.30 * H, 0.13 * H
    TH, SH, UA, FA = 0.22 * H, 0.22 * H, 0.17 * H, 0.17 * H

    def v(a, L):
        r = math.radians(a)
        return QPointF(math.sin(r) * L * f, math.cos(r) * L)

    def up(a, L):
        r = math.radians(a)
        return QPointF(math.sin(r) * L * f, -math.cos(r) * L)

    hip = QPointF(0, 0)
    neck = up(pose["lean"], T)
    head = neck + up(pose["lean"] + pose["tilt"], R * 1.15)
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


def contact(j, H):
    """Qué tan abajo de la cadera queda el punto más bajo del cuerpo."""
    w = H * 0.0375
    m = max(pt.y() + w for k, pt in j.items() if k != "head")
    return max(m, j["head"].y() + 0.13 * H)


# ----------------------------------------------------------------------------
# Acciones: animaciones por keyframes. pose(u, t, s) con u de 0 a 1.
# ----------------------------------------------------------------------------
class Action:
    def __init__(self, key, label, dur, pose, speed=0.0, events=(), say=(),
                 kind="solo", snap=40.0, lines=False):
        self.key, self.label, self.dur, self.pose = key, label, dur, pose
        self.speed, self.events, self.say = speed, list(events), list(say)
        self.kind, self.snap, self.lines = kind, snap, lines

    def duration(self):
        return random.uniform(*self.dur) if isinstance(self.dur, tuple) else self.dur

    def speed_at(self, u):
        return self.speed(u) if callable(self.speed) else self.speed


ACTIONS = {}


def action(key, label, dur, **kw):
    def deco(fn):
        ACTIONS[key] = Action(key, label, dur, fn, **kw)
        return fn
    return deco


def FLIP(s):
    s.facing *= -1


def hit(kind, reach, limb, dy=0.45, power=1.0, high=True):
    return lambda s: s.fight_hit(kind, reach, limb, dy, power, high)


def window_speed(v, a, b):
    return lambda u: v if a < u < b else 0.0


# ======================= ACCIONES EN SOLITARIO ==============================
@action("estirarse", "Estirarse", 2.4)
def _(u, t, s):
    up = S(lean=-6, tilt=-14, uaB=172, faB=178, uaF=176, faF=182, thB=-2, thF=2)
    return kf(u, [(0, S()), (0.3, up), (0.75, W(up, lean=-9, tilt=-18)), (1, S())])


@action("bostezar", "Bostezar", 2.4, say=[(0.3, 0.75, "aah")])
def _(u, t, s):
    y = S(tilt=-22, lean=-4, uaF=35, faF=165, uaB=150, faB=170)
    return kf(u, [(0, S()), (0.25, y), (0.7, W(y, tilt=-26)), (1, S())])


def dance_pose(t):
    b = math.sin(t * 7)
    return S(lean=6 * b, tilt=-6 * b, uaF=110 + 50 * b, faF=150 + 30 * b,
             uaB=110 - 50 * b, faB=150 - 30 * b, thB=-12 + 10 * b, shB=-20 + 10 * b,
             thF=12 + 10 * b, shF=-5 + 10 * b, lift=0.03 * abs(math.sin(t * 7)))


@action("bailar", "Bailar", 4.5, say=[(0.1, 0.9, "♪")],
        speed=lambda u: 50 * math.sin(u * math.pi * 4))
def _(u, t, s):
    return held(u, dance_pose(t), 0.08)


@action("disco", "Paso disco", 3.6, say=[(0.1, 0.9, "♪")])
def _(u, t, s):
    k = int(t * 2.5) % 2
    p = S(lean=4, thF=15, shF=0, thB=-10, uaB=-40, faB=40,
          uaF=150 if k else 25, faF=150 if k else 20, tilt=-10 if k else 8)
    return held(u, p, 0.1)


def pushup(k):
    return P(rot=62 + 10 * k, tilt=-20, thB=0, shB=0, thF=2, shF=2,
             uaF=72 - 50 * k, faF=72 + 50 * k, uaB=70 - 50 * k, faB=74 + 50 * k)


@action("lagartijas", "Hacer lagartijas", 4.5)
def _(u, t, s):
    return held(u, pushup(0.5 - 0.5 * math.cos(t * 5)), 0.12)


@action("sentadillas", "Hacer sentadillas", 3.8)
def _(u, t, s):
    k = 0.5 - 0.5 * math.cos(t * 5)
    top = S(uaB=90, faB=90, uaF=90, faF=90)
    low = P(lean=25, thB=75, shB=-30, thF=80, shF=-25, uaB=95, faB=90, uaF=95, faF=90)
    return held(u, lerp_pose(top, low, k), 0.12)


@action("tijera", "Saltos de tijera", 3.0)
def _(u, t, s):
    ph = t * 6
    k = math.sin(ph) ** 2
    open_ = S(thB=-24, shB=-24, thF=24, shF=24, uaB=-160, faB=-165, uaF=160, faF=165)
    return held(u, W(lerp_pose(S(), open_, k), lift=0.1 * abs(math.sin(ph))), 0.1)


def flip_pose(u, d):
    """Mortal: d = +1 hacia adelante, -1 hacia atrás."""
    p = kf(u, [(0, S()),
               (0.18, P(lean=20, thB=55, shB=-25, thF=60, shF=-20, uaB=-60, faB=-40, uaF=-50, faF=-30)),
               (0.3, P(rot=30 * d, lean=-5, thB=-5, shB=-5, thF=5, shF=5,
                       uaB=175, faB=180, uaF=175, faF=180)),
               (0.55, W(BALL, rot=180 * d)),
               (0.78, W(BALL, rot=300 * d)),
               (0.9, P(rot=345 * d, thB=20, shB=-10, thF=25, shF=-5, uaB=100, faB=100, uaF=110, faF=110)),
               (1.0, W(CROUCH, rot=360 * d))])
    p["lift"] = arc(u, 0.25, 0.92, 1.15)
    return p


@action("mortal_atras", "Mortal hacia atrás", 1.2)
def _(u, t, s):
    return flip_pose(u, -1)


@action("mortal_adelante", "Mortal hacia adelante", 1.2, speed=window_speed(150, 0.25, 0.92))
def _(u, t, s):
    return flip_pose(u, 1)


STAR = P(thB=-35, shB=-35, thF=35, shF=35, uaB=-150, faB=-150, uaF=150, faF=150)


@action("rueda", "Rueda de carro", 1.2, speed=window_speed(170, 0.12, 0.88))
def _(u, t, s):
    p = kf(u, [(0, S()), (0.12, STAR), (0.88, STAR), (1, S(rot=360))])
    if 0.12 <= u <= 0.88:
        p["rot"] = 360 * (u - 0.12) / 0.76
    return p


@action("parado_manos", "Pararse de manos", 3.6)
def _(u, t, s):
    w = math.sin(t * 3)
    hs = P(rot=180, lean=3 * w, thB=-6 + 5 * w, shB=-6 + 5 * w, thF=6 + 5 * w, shF=6 + 5 * w,
           uaB=180, faB=180, uaF=180, faF=180, tilt=-20)
    return kf(u, [(0, S()),
                  (0.12, P(lean=50, thB=30, shB=-10, thF=40, shF=0, uaB=90, faB=90, uaF=95, faF=95)),
                  (0.3, hs), (0.82, hs), (1.0, S(rot=360))])


@action("moonwalk", "Moonwalk", 3.2, speed=-55, say=[(0.1, 0.9, "♪")])
def _(u, t, s):
    return W(pose_walk(s.phase, amp=0.8, lean=-4), uaF=20, faF=30, uaB=-20, faB=-10)


ROBOT = [S(uaF=90, faF=180, uaB=0, faB=90, thF=8, shF=8, thB=-8, shB=-8),
         S(uaF=90, faF=90, uaB=-45, faB=-45, tilt=15, thF=8, shF=8, thB=-8, shB=-8),
         S(uaF=0, faF=90, uaB=90, faB=180, tilt=-15, thF=8, shF=8, thB=-8, shB=-8),
         S(uaF=135, faF=45, uaB=0, faB=0, lean=-3, thF=8, shF=8, thB=-8, shB=-8)]


@action("robot", "Baile robot", 3.6, snap=70, say=[(0.15, 0.3, "bip"), (0.6, 0.75, "bup")])
def _(u, t, s):
    return ROBOT[int(t * 3) % 4]


@action("guitarra", "Guitarra de aire", 3.6, say=[(0.1, 0.9, "♪♪")])
def _(u, t, s):
    p = S(lean=-12, tilt=-10 + 8 * math.sin(t * 8), thB=-25, shB=-25, thF=25, shF=25,
          uaF=75, faF=55, uaB=40, faB=85 + 18 * math.sin(t * 22))
    return held(u, p, 0.1)


@action("sombra", "Boxear al aire", 3.0, speed=lambda u: 30 * math.sin(u * 12))
def _(u, t, s):
    g = W(pose_guard(t), lift=0.02 * abs(math.sin(t * 8)))
    k = int(t * 4) % 3
    if k == 1:
        g = W(g, uaF=88, faF=90, lean=16)
    elif k == 2:
        g = W(g, uaB=86, faB=88, lean=20)
    return held(u, g, 0.1)


@action("meditar", "Meditar (y levitar)", 6.0, say=[(0.25, 0.85, "om")])
def _(u, t, s):
    seat = P(lean=-2, thB=85, shB=-80, thF=95, shF=-95, uaB=20, faB=80, uaF=25, faF=85)
    p = held(u, W(seat, lift=0.18 + 0.04 * math.sin(t * 2)), 0.15)
    return p


@action("dormir", "Dormir", (7.0, 12.0), say=[(0.2, 0.86, "Zzz")])
def _(u, t, s):
    lie = W(LIE, lean=2 * math.sin(t * 1.5), uaF=30, faF=60)
    return kf(u, [(0, S()), (0.06, SITUP), (0.14, lie), (0.88, lie), (0.94, SITUP), (1, S())])


@action("agujeta", "Amarrarse la agujeta", 3.2)
def _(u, t, s):
    kneel = P(lean=35, tilt=10, thB=0, shB=-90, thF=90, shF=0,
              uaF=70 + 8 * math.sin(t * 12), faF=30, uaB=55, faB=20)
    return held(u, kneel, 0.15)


@action("mirar", "Mirar alrededor", 3.0, events=[(0.3, FLIP), (0.62, FLIP)])
def _(u, t, s):
    return S(tilt=-6 + 6 * math.sin(t * 2), lean=0)


@action("rascarse", "Rascarse la cabeza", 2.6, say=[(0.15, 0.85, "?")])
def _(u, t, s):
    return held(u, S(uaF=150, faF=225 + 12 * math.sin(t * 18), tilt=8, lean=3), 0.15)


@action("celebrar", "Celebrar", 2.6, say=[(0.1, 0.9, "¡Yay!")])
def _(u, t, s):
    b = math.sin(t * 12)
    p = S(uaB=165 + 15 * b, faB=175 + 15 * b, uaF=165 - 15 * b, faF=175 - 15 * b,
          tilt=-10, lift=0.12 * abs(math.sin(t * 7)))
    return held(u, p, 0.1)


@action("victoria", "Pose de victoria", 2.4, say=[(0.25, 0.85, "¡Sí!")])
def _(u, t, s):
    v = S(uaF=175 + 6 * math.sin(t * 10), faF=178, uaB=-35, faB=45, lean=-4, tilt=-10,
          thF=10, thB=-10)
    return kf(u, [(0, S()), (0.25, v), (0.8, v), (1, S())])


@action("tropezar", "Tropezar", 3.4, say=[(0.38, 0.6, "¡Ay!")],
        speed=lambda u: 110 * (1 - u / 0.3) if u < 0.3 else 0.0)
def _(u, t, s):
    if u < 0.22:
        return pose_walk(s.phase)
    return kf(u, [(0.22, pose_walk(0.25)), (0.36, FACEDOWN), (0.7, FACEDOWN),
                  (0.84, pushup(0)), (1, S())])


@action("pirueta", "Pirueta", 1.8, events=[(0.15 * i, FLIP) for i in range(1, 7)])
def _(u, t, s):
    p = S(uaB=-95, faB=-95, uaF=95, faF=95, thF=40, shF=-30, lift=0.03)
    return held(u, p, 0.1)


@action("un_pie", "Brincar en un pie", 2.6, speed=60)
def _(u, t, s):
    p = S(thF=55, shF=-35, uaB=-40, faB=-20, uaF=40, faF=60, lean=5,
          lift=0.09 * abs(math.sin(t * 9)))
    return held(u, p, 0.08)


@action("sigiloso", "Caminar sigiloso", 4.0, speed=30, say=[(0.05, 0.3, "shh")])
def _(u, t, s):
    return W(pose_walk(s.phase, amp=0.75, lean=18), uaF=70, faF=150, uaB=55, faB=140, tilt=-8)


STANCE = P(lean=5, thB=-25, shB=-25, thF=25, shF=10, uaB=60, faB=120, uaF=80, faF=130)
HIGHK = P(lean=-25, tilt=10, thB=-5, shB=-5, thF=150, shF=155, uaB=-60, faB=-40, uaF=60, faF=110)


@action("karate", "Patadas de karate", 2.6, say=[(0.28, 0.42, "¡Hya!")])
def _(u, t, s):
    return kf(u, [(0, S()), (0.15, STANCE), (0.3, HIGHK), (0.42, STANCE), (0.6, HIGHK),
                  (0.72, STANCE), (1, S())])


@action("musculos", "Sacar músculo", 2.8)
def _(u, t, s):
    f1 = S(uaF=90, faF=180, uaB=-90, faB=-180, lean=-3, tilt=-8, thB=-12, thF=12)
    f2 = S(uaF=120, faF=210, uaB=-120, faB=-210, lean=-2, tilt=-12, thB=-12, thF=12)
    return kf(u, [(0, S()), (0.2, f1), (0.5, f1), (0.6, f2), (0.85, f2), (1, S())])


@action("reir", "Reírse", 2.4, say=[(0.05, 0.95, "ja ja")])
def _(u, t, s):
    b = math.sin(t * 18)
    return held(u, S(lean=15 + 4 * b, tilt=10 + 6 * b, uaF=60, faF=20, uaB=-20, faB=40), 0.1)


@action("estornudar", "Estornudar", 2.0, say=[(0.5, 0.85, "¡Achú!")])
def _(u, t, s):
    pre = S(lean=-14, tilt=-28, uaF=60, faF=170)
    ach = S(lean=35, tilt=25, uaF=80, faF=150, thB=-15, thF=15)
    return kf(u, [(0, S()), (0.45, pre), (0.55, ach), (0.75, ach), (1, S())])


@action("breakdance", "Breakdance", 3.0, say=[(0.3, 0.7, "♪")],
        events=[(0.3 + 0.05 * i, FLIP) for i in range(8)])
def _(u, t, s):
    spin = P(rot=180, thB=-45, shB=-45, thF=45, shF=45, uaB=165, faB=200, uaF=195, faF=160)
    return kf(u, [(0, S()),
                  (0.15, P(lean=60, thB=50, shB=-20, thF=60, shF=-10, uaB=80, faB=80, uaF=85, faF=85)),
                  (0.28, spin), (0.75, spin), (0.88, W(BALL, rot=300)), (1, S(rot=360))])


SLIDE = P(rot=-55, lean=0, tilt=20, thB=5, shB=-85, thF=25, shF=25, uaB=-95, faB=-95, uaF=85, faF=100)


@action("barrida", "Barrerse", 1.4, lines=True,
        speed=lambda u: 300 * (1 - u / 0.8) if u < 0.8 else 0.0)
def _(u, t, s):
    return kf(u, [(0, pose_walk(0.3, 1.45, 15)), (0.2, SLIDE), (0.75, SLIDE), (1, S())])


BOW = S(lean=70, tilt=15, uaF=45, faF=120, uaB=-30, faB=-60)


@action("reverencia", "Reverencia", 2.2)
def _(u, t, s):
    return kf(u, [(0, S()), (0.35, BOW), (0.65, BOW), (1, S())])


@action("pensar", "Pensar", 3.2, say=[(0.15, 0.75, "..."), (0.8, 0.97, "!")])
def _(u, t, s):
    return held(u, S(uaF=30, faF=160, uaB=40, faB=100, tilt=-12, lean=0), 0.15)


SPLIT = P(tilt=-8, thB=-90, shB=-90, thF=90, shF=90, uaB=-150, faB=-155, uaF=150, faF=155)


@action("split", "Abrirse de piernas", 2.8, say=[(0.5, 0.75, "auch")])
def _(u, t, s):
    return kf(u, [(0, S()), (0.25, SPLIT), (0.75, SPLIT), (1, S())])


@action("voltereta", "Voltereta", 1.1, speed=window_speed(150, 0.12, 0.88))
def _(u, t, s):
    p = kf(u, [(0, S()), (0.15, BALL), (0.85, BALL), (1, S(rot=360))])
    if 0.15 <= u <= 0.85:
        p["rot"] = 360 * (u - 0.15) / 0.7
    return p


@action("dab", "Dab", 1.8)
def _(u, t, s):
    dab = S(lean=8, tilt=32, uaF=125, faF=205, uaB=-135, faB=-135)
    return kf(u, [(0, S()), (0.2, dab), (0.7, dab), (1, S())])


FLY = P(rot=75, tilt=-25, uaF=180, faF=180, uaB=15, faB=10, thB=0, shB=0, thF=8, shF=-10)


@action("superheroe", "Volar como superhéroe", 1.5, lines=True,
        speed=window_speed(260, 0.22, 0.9))
def _(u, t, s):
    p = kf(u, [(0, S()), (0.15, W(CROUCH, uaF=-20, uaB=-30)), (0.3, FLY), (0.78, FLY),
               (0.9, P(rot=15, lean=10, thB=30, shB=-10, thF=40, shF=0, uaB=100, faB=110, uaF=110, faF=120)),
               (1, S())])
    p["lift"] = arc(u, 0.2, 0.95, 0.9)
    return p


@action("aplaudir", "Aplaudir", 2.0, say=[(0.1, 0.9, "clap clap")])
def _(u, t, s):
    o = 18 * math.sin(t * 16)
    return held(u, S(uaF=70, faF=110 + o, uaB=60, faB=95 - o, lean=4), 0.12)


@action("saludar", "Saludar", 2.0)
def _(u, t, s):
    return held(u, pose_wave(t), 0.12)


@action("frustrado", "Hacer berrinche", 2.2, say=[(0.1, 0.9, "grr")])
def _(u, t, s):
    p = S(lean=15, tilt=30, uaF=-10, faF=-5, uaB=-15, faB=-10,
          thF=30 * abs(math.sin(t * 6)), shF=10 * abs(math.sin(t * 6)))
    return held(u, p, 0.1)


@action("estirar_piernas", "Estirar piernas", 3.0)
def _(u, t, s):
    p = P(lean=65, tilt=10, thB=-20, shB=-20, thF=25, shF=25, uaB=70, faB=60, uaF=75, faF=65)
    p2 = W(p, thB=-28, shB=-28, thF=32, shF=32, lean=72)
    return kf(u, [(0, S()), (0.2, p), (0.5, p2), (0.8, p), (1, S())])


@action("patear_piedra", "Patear una piedrita", 2.2)
def _(u, t, s):
    return kf(u, [(0, S()), (0.3, S(thF=-30, shF=-50, lean=-4, uaB=20, uaF=-20)),
                  (0.45, S(thF=65, shF=70, lean=-10, uaB=40, uaF=-40)), (0.7, S(tilt=-20)), (1, S())])


SOLO = [k for k, a in ACTIONS.items() if a.kind == "solo" and k not in ("saludar", "frustrado")]


# =========================== PELEA ==========================================
def G(t):
    return pose_guard(t)


@action("jab", "Jab", 0.32, kind="fight", events=[(0.45, hit("light", 0.6, "haF"))])
def _(u, t, s):
    return kf(u, [(0, G(t)), (0.45, JAB), (0.7, JAB), (1, G(t))])


@action("cruzado", "Golpe cruzado", 0.45, kind="fight", events=[(0.5, hit("heavy", 0.62, "haB"))])
def _(u, t, s):
    return kf(u, [(0, G(t)), (0.5, CROSS), (0.72, CROSS), (1, G(t))])


@action("combo", "Combo", 1.0, kind="fight",
        events=[(0.15, hit("light", 0.6, "haF")), (0.42, hit("light", 0.62, "haB")),
                (0.75, hit("launch", 0.58, "haF"))])
def _(u, t, s):
    return kf(u, [(0, G(t)), (0.15, JAB), (0.28, G(t)), (0.42, CROSS), (0.55, G(t)),
                  (0.75, UPPER), (1, G(t))])


@action("gancho", "Gancho al mentón", 0.6, kind="fight", events=[(0.55, hit("launch", 0.56, "haF"))])
def _(u, t, s):
    low = P(lean=25, thB=40, shB=-20, thF=50, shF=-10, uaF=40, faF=100, uaB=40, faB=140)
    return kf(u, [(0, G(t)), (0.3, low), (0.55, UPPER), (0.8, UPPER), (1, G(t))])


@action("patada", "Patada", 0.45, kind="fight", events=[(0.55, hit("heavy", 0.7, "ftF"))])
def _(u, t, s):
    return kf(u, [(0, G(t)), (0.55, KICK), (0.75, KICK), (1, G(t))])


ROUNDK = P(lean=-30, tilt=15, thB=-5, shB=-5, thF=110, shF=105, uaB=-60, faB=-30, uaF=40, faF=90)


@action("giratoria", "Patada giratoria", 0.7, kind="fight",
        events=[(0.2, FLIP), (0.5, FLIP), (0.5, hit("heavy", 0.72, "ftF", power=1.4))])
def _(u, t, s):
    turn = P(lean=10, thB=10, shB=10, thF=-15, shF=-15, uaB=-60, faB=-40, uaF=60, faF=90)
    return kf(u, [(0, G(t)), (0.2, turn), (0.5, ROUNDK), (0.7, ROUNDK), (1, G(t))])


FLYK = P(rot=-15, lean=-20, thB=60, shB=-40, thF=95, shF=95, uaB=-80, faB=-60, uaF=40, faF=100)


@action("voladora", "Patada voladora", 0.75, kind="fight", lines=True,
        speed=window_speed(280, 0.15, 0.7),
        events=[(0.5, hit("heavy", 0.78, "ftF", dy=1.0, power=1.3))])
def _(u, t, s):
    p = kf(u, [(0, G(t)), (0.15, CROUCH), (0.35, FLYK), (0.75, FLYK), (1, G(t))])
    p["lift"] = arc(u, 0.15, 0.95, 0.6)
    return p


SWEEP = P(lean=30, thB=60, shB=-60, thF=85, shF=88, uaB=60, faB=30, uaF=-40, faF=-20)


@action("barrida_baja", "Barrida", 0.6, kind="fight",
        events=[(0.5, hit("down", 0.74, "ftF", high=False))])
def _(u, t, s):
    return kf(u, [(0, G(t)), (0.45, SWEEP), (0.7, SWEEP), (1, G(t))])


@action("agarre", "Agarrar y lanzar", 0.9, kind="fight", events=[(0.3, hit("throw", 0.56, "haF"))])
def _(u, t, s):
    grab = P(lean=20, thB=-25, shB=-25, thF=25, shF=10, uaF=85, faF=85, uaB=80, faB=80)
    lift = P(lean=-25, tilt=-10, thB=-25, shB=-25, thF=25, shF=10, uaF=170, faF=175, uaB=170, faB=175)
    throw = P(lean=-30, tilt=-15, thB=-30, shB=-30, thF=20, shF=10,
              uaF=-150, faF=-150, uaB=-150, faB=-150)
    return kf(u, [(0, G(t)), (0.25, grab), (0.45, lift), (0.6, throw), (1, G(t))])


@action("embestida", "Embestida", 0.6, kind="fight", lines=True,
        speed=lambda u: 320 if u < 0.5 else 0.0, events=[(0.45, hit("heavy", 0.62, "haF"))])
def _(u, t, s):
    run = P(lean=30, thB=-30, shB=-50, thF=40, shF=0, uaB=-60, faB=-20, uaF=-40, faF=0)
    return kf(u, [(0, G(t)), (0.2, run), (0.45, W(JAB, lean=30)), (0.7, W(JAB, lean=30)), (1, G(t))])


@action("cabezazo", "Cabezazo", 0.5, kind="fight", events=[(0.55, hit("light", 0.5, "head", power=1.5))])
def _(u, t, s):
    back = W(G(t), lean=-15, tilt=-20)
    fwd = W(G(t), lean=35, tilt=25)
    return kf(u, [(0, G(t)), (0.35, back), (0.55, fwd), (0.7, fwd), (1, G(t))])


PUSH = P(lean=20, thB=-25, shB=-25, thF=25, shF=10, uaF=88, faF=95, uaB=85, faB=92)


@action("empujon", "Empujón", 0.5, kind="fight", events=[(0.5, hit("heavy", 0.58, "haF", power=0.8))])
def _(u, t, s):
    return kf(u, [(0, G(t)), (0.5, PUSH), (0.7, PUSH), (1, G(t))])


@action("codazo", "Codazo", 0.4, kind="fight", events=[(0.5, hit("light", 0.46, "elF"))])
def _(u, t, s):
    el = P(lean=18, tilt=5, thB=-24, shB=-24, thF=26, shF=12, uaB=40, faB=140, uaF=95, faF=215)
    return kf(u, [(0, G(t)), (0.5, el), (0.7, el), (1, G(t))])


@action("provocar", "Provocar", 1.4, kind="fight", say=[(0.1, 0.9, "¡Ven!")])
def _(u, t, s):
    return held(u, S(uaF=90, faF=90 + 50 * abs(math.sin(t * 8)), lean=-5, tilt=-10), 0.15, base=G(t))


# defensas
@action("bloqueo", "Bloquear", 0.35, kind="defend", speed=lambda u: -90 * (1 - u))
def _(u, t, s):
    return BLOCK


@action("esquive", "Esquivar", 0.5, kind="defend", speed=lambda u: -230 if u < 0.8 else 0.0)
def _(u, t, s):
    p = P(lean=-15, tilt=-10, thB=10, shB=-30, thF=20, shF=-20, uaB=-60, faB=-20, uaF=60, faF=120)
    p = kf(u, [(0, p), (0.8, p), (1, G(t))])
    p["lift"] = arc(u, 0, 0.85, 0.25)
    return p


@action("esquive_mortal", "Esquivar con mortal", 1.0, kind="defend", speed=window_speed(-170, 0.25, 0.92))
def _(u, t, s):
    return flip_pose(u, -1)


@action("agacharse", "Agacharse", 0.45, kind="defend")
def _(u, t, s):
    duck = P(lean=30, thB=70, shB=-45, thF=80, shF=-35, uaF=140, faF=200, uaB=130, faB=210)
    return kf(u, [(0, duck), (0.7, duck), (1, G(t))])


# reacciones
@action("tambaleo", "Tambalearse", 0.45, kind="react", speed=lambda u: -170 * (1 - u))
def _(u, t, s):
    ow = P(lean=-20, tilt=-25, uaB=120, faB=150, uaF=100, faF=150, thB=-20, shB=-20, thF=20, shF=10)
    return kf(u, [(0, ow), (1, G(t))])


LIE_X = W(LIE, uaB=170, faB=178, uaF=8, faF=18)


def getup(u, start, kip):
    """Levantarse del piso, u de 0 a 1."""
    if kip:   # ¡de un salto!
        p = kf(u, [(0, start),
                   (0.3, P(rot=-90, tilt=20, thB=160, shB=170, thF=165, shF=175,
                           uaB=180, faB=180, uaF=180, faF=180)),
                   (0.65, P(rot=-10, lean=10, thB=40, shB=-20, thF=50, shF=-10,
                            uaB=60, faB=90, uaF=70, faF=100)),
                   (1, S())])
        p["lift"] = arc(u, 0.3, 0.8, 0.35)
        return p
    return kf(u, [(0, start), (0.35, SITUP), (0.7, CROUCH), (1, S())])


@action("derribado", "Caer al piso", 2.6, kind="react")
def _(u, t, s):
    if u < 0.62:
        return kf(u, [(0, S()), (0.12, P(rot=-50, tilt=-20, uaB=120, faB=140, uaF=110, faF=140)),
                      (0.22, LIE_X), (0.62, LIE_X)])
    return getup((u - 0.62) / 0.38, LIE_X, s.kip)


@action("en_suelo", "En el suelo", 2.0, kind="react")
def _(u, t, s):
    if u < 0.5:
        return kf(u, [(0, LIE_X), (0.5, LIE_X)])
    return getup((u - 0.5) / 0.5, LIE_X, s.kip)


FIGHT_CLOSE = [("jab", 16), ("cruzado", 12), ("combo", 8), ("gancho", 6), ("patada", 12),
               ("giratoria", 6), ("barrida_baja", 6), ("agarre", 5), ("cabezazo", 5),
               ("empujon", 6), ("codazo", 6)]
FIGHT_FAR = [("voladora", 3), ("embestida", 3), ("provocar", 2)]


# ======================== CON OTRO (PAREJA) =================================
def pair_fx(s):
    if s.lead:
        s.pair_fx()


@action("chocar5", "Chocar los cinco", 1.4, kind="pair", events=[(0.5, pair_fx)])
def _(u, t, s):
    hi = S(uaF=125, faF=140, lean=-3, tilt=-8)
    return kf(u, [(0, S()), (0.3, S(uaF=165, faF=190, lean=-6)), (0.5, hi), (0.7, hi), (1, S())])


@action("puno", "Chocar puños", 1.5, kind="pair", events=[(0.45, pair_fx)])
def _(u, t, s):
    fist = S(uaF=88, faF=90, lean=6)
    return kf(u, [(0, S()), (0.25, S(uaF=60, faF=120)), (0.45, fist), (0.6, fist),
                  (0.8, S(uaF=120, faF=150, tilt=-10)), (1, S())])


@action("mano", "Saludo de mano", 2.0, kind="pair")
def _(u, t, s):
    k = 1.0 if 0.25 < u < 0.75 else 0.0
    return held(u, S(uaF=70, faF=82 + 12 * k * math.sin(t * 20), lean=4), 0.2)


@action("reverencia_par", "Reverencia", 2.2, kind="pair")
def _(u, t, s):
    return kf(u, [(0, S()), (0.35, BOW), (0.65, BOW), (1, S())])


@action("bailar_par", "Bailar juntos", 4.5, kind="pair", say=[(0.1, 0.9, "♪")])
def _(u, t, s):
    return held(u, dance_pose(s.crew.time), 0.08)


SOCIAL = dict(chocar5=0.5, puno=0.72, mano=0.66, reverencia_par=0.9, bailar_par=0.95)
SOCIAL_W = dict(chocar5=26, puno=22, mano=18, reverencia_par=12, bailar_par=22)


# ----------------------------------------------------------------------------
# Dibujo
# ----------------------------------------------------------------------------
def draw_stickman(p, j, H, spec, f, t, blink=False, look=0.0):
    col = QColor(spec["color"])
    back = col.lighter(160) if col.lightness() < 90 else col.darker(125)
    acc = QColor(spec["accent"])
    w = H * 0.075
    R = 0.13 * H

    def seg(c, *pts, width=w):
        p.setPen(QPen(c, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF(list(pts)))

    def ang(a, b):
        d = b - a
        return math.degrees(math.atan2(d.x(), -d.y()))

    c = j["head"]
    kind = spec["acc"]
    head_ang = ang(j["neck"], j["head"])
    torso_ang = ang(j["hip"], j["neck"])

    # Extremidades de atrás (tono distinto para dar profundidad)
    seg(back, j["sh"], j["elB"], j["haB"])
    seg(back, j["hip"], j["knB"], j["ftB"])

    if kind == "bufanda":   # cola de la bufanda (detrás del cuerpo)
        p.save()
        p.translate(j["neck"])
        p.rotate(torso_ang)
        o = QPointF(0, 0)
        seg(acc, o, QPointF(-f * R * 0.8, R * 0.15 + R * 0.2 * math.sin(t * 9 + 1)),
            QPointF(-f * R * 1.6, R * 0.5 + R * 0.35 * math.sin(t * 9)), width=w * 0.8)
        p.restore()

    # Torso y pierna de enfrente
    seg(col, j["hip"], j["neck"])
    seg(col, j["hip"], j["knF"], j["ftF"])

    # Cabeza
    p.setPen(Qt.NoPen)
    p.setBrush(col)
    p.drawEllipse(c, R, R)

    # Rasgos de la cabeza, en el marco de la cabeza (giran con ella)
    p.save()
    p.translate(c)
    p.rotate(head_ang)
    O = QPointF(0, 0)
    ey = -R * 0.08 - look * R * 0.22
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(spec["eyes"]))
    eh = R * 0.04 if blink else R * 0.2
    for dx in (0.18, 0.58):
        p.drawEllipse(QPointF(f * R * dx, ey), R * 0.12, eh)

    if kind == "gorra":
        p.setBrush(acc)
        p.drawChord(QRectF(-R * 1.06, -R * 1.12, R * 2.12, R * 2.12), 0, 180 * 16)
        seg(acc, QPointF(f * R * 0.3, -R * 0.06), QPointF(f * R * 1.55, -R * 0.06), width=w * 0.75)
    elif kind == "moño":
        b = QPointF(-f * R * 0.65, -R * 0.8)
        s = R * 0.55
        p.setBrush(acc)
        p.drawPolygon(QPolygonF([b, b + QPointF(-s, -s * 0.7), b + QPointF(-s, s * 0.7)]))
        p.drawPolygon(QPolygonF([b, b + QPointF(s, -s * 0.7), b + QPointF(s, s * 0.7)]))
        p.drawEllipse(b, s * 0.3, s * 0.3)
    elif kind == "audifonos":
        p.setPen(QPen(acc, w * 0.55, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(-R * 1.2, -R * 1.25, R * 2.4, R * 2.4), 15 * 16, 150 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawEllipse(QPointF(-f * R * 0.15, R * 0.05), R * 0.42, R * 0.58)
    elif kind == "lentes":
        lw = w * 0.28
        p.setPen(QPen(acc, lw, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(QColor(255, 255, 255, 45))
        r = R * 0.27
        for dx in (0.14, 0.68):
            p.drawEllipse(QPointF(f * R * dx, ey), r, r)
        p.drawLine(QPointF(f * R * (0.14 - 0.27), ey), QPointF(-f * R * 0.88, ey + R * 0.08))
    elif kind == "margarita":
        sway = R * 0.12 * math.sin(t * 2.5)
        top = QPointF(-f * R * 0.25 + sway, -R * 1.85)
        p.setPen(QPen(QColor("#15803D"), w * 0.32, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(-f * R * 0.1, -R * 0.95), top)
        p.setPen(QPen(QColor(0, 0, 0, 70), max(1.0, H * 0.008)))
        p.setBrush(acc)
        for i in range(8):
            p.save()
            p.translate(top)
            p.rotate(i * 45 + t * 10)
            p.drawEllipse(QPointF(R * 0.33, 0), R * 0.27, R * 0.13)
            p.restore()
        p.setBrush(QColor("#FACC15"))
        p.drawEllipse(top, R * 0.18, R * 0.18)
    p.restore()

    if kind == "bufanda":
        p.save()
        p.translate(j["neck"])
        p.rotate(torso_ang)
        seg(acc, QPointF(-R * 0.55, -R * 0.05), QPointF(R * 0.55, -R * 0.05), width=w * 1.1)
        p.restore()

    # Brazo de enfrente al final (queda sobre todo lo demás)
    seg(col, j["sh"], j["elF"], j["haF"])


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
    p.setPen(QColor(220, 40, 40) if text in ("!", "¡Ven!", "grr") else QColor(35, 35, 45))
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


# ----------------------------------------------------------------------------
# Un stickman = una ventanita transparente que se mueve por la pantalla
# ----------------------------------------------------------------------------
class Stickman(QWidget):
    GROUNDED = ("walk", "run", "sprint", "idle", "wave", "sit", "greet", "crouch", "land",
                "watch", "chase", "fight", "act", "tag_it", "tag_run", "approach", "wait")
    TIMERLESS = ("fight", "chase", "act", "tag_it", "tag_run", "approach")
    MOVING = ("walk", "run", "sprint", "chase", "fight", "act", "tag_it", "tag_run", "approach")
    CALM = ("walk", "idle", "run")

    def __init__(self, crew, spec, x, y):
        flags = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
                 Qt.NoDropShadowWindowHint | Qt.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)

        self.crew, self.spec, self.H = crew, spec, HEIGHT
        self.resize(int(self.H * 2.3), int(self.H * 2.3))
        self.ox = self.oy = self.H * 1.15     # la cadera queda al centro de la ventana

        self.hx, self.hy = float(x), float(y)
        self.vx = self.vy = 0.0
        self.facing = random.choice((-1, 1))
        self.t = random.random() * 10
        self.phase = 0.0
        self.pose = dict(FALL)
        self.joints = solve(self.pose, self.H, self.facing)
        self.state, self.timer = "air", 0.0
        self.thrown = False
        self.reaching = False
        self.meet_cd = random.uniform(8, 15)
        self.blink_in = random.uniform(2, 5)
        self.blink_t = 0.0
        self.last_ground = ground_at(x) or y
        self.look = 0.0
        self.notice_cd = random.uniform(20, 40)
        self.say_text, self.say_t = "", 0.0
        self.moving = False

        # acción en curso
        self.act = None
        self.act_u = 0.0
        self.act_el = 0.0
        self.act_dur = 1.0
        self.act_next = None
        self.kip = False

        # cursor
        self.chase_t = 0.0
        self.chase_moving = False
        self.chase_fast = False
        self.jump_cd = 0.0
        self.jump_vx = None
        self.alert_t = 0.0

        # pelea
        self.opponent = None
        self.fight_t = 0.0
        self.attack_cd = 0.0
        self.hits = 0
        self.fx_t = 0.0
        self.fx_pt = QPointF()
        self.fx_scale = 1.0

        # pareja (convivir / las traes)
        self.partner = None
        self.lead = False
        self.social_kind = None
        self.approach_x = 0.0
        self.approach_t = 0.0
        self.tag_t = 0.0
        self.tag_wait = 0.0
        self.flee_turn = 0.0

        # arrastre
        self.dragging = False
        self.grab = QPointF()
        self.press_pos = None
        self.drag_dist = 0.0
        self.svx = self.svy = 0.0

    # ---------------- utilidades ----------------
    def set_state(self, s, dur=0.0):
        if s != "act":
            self.act = None
        self.state, self.timer = s, dur

    def grounded(self):
        return self.state in self.GROUNDED

    def say(self, text, dur=1.2):
        self.say_text, self.say_t = text, dur

    def cursor_rel(self):
        """Cursor relativo a la cabeza: (dx, dy) con dy positivo = arriba."""
        cur = QPointF(QCursor.pos())
        head = QPointF(self.hx, self.hy) + self.joints["head"]
        return cur.x() - head.x(), head.y() - cur.y()

    def step(self, speed, dt):
        """Avanza hacia donde mira (o hacia atrás si speed<0). False si hay pared o vacío."""
        L, Rb, _ = desktop_bounds()
        m = self.H * 0.35
        nx = self.hx + self.facing * speed * dt
        if nx < L + m or nx > Rb - m or ground_at(nx) is None:
            return False
        self.hx = nx
        self.phase = (self.phase + dt * speed / (self.H * 1.05)) % 1.0
        return True

    # ---------------- acciones ----------------
    def start_action(self, key, then=None):
        a = ACTIONS[key]
        self.set_state("act")
        self.act = a
        self.act_u = -1.0
        self.act_el = 0.0
        self.act_dur = a.duration()
        self.act_next = then
        self.kip = random.random() < 0.35

    def update_act(self, dt):
        a = self.act
        self.act_el += dt
        u = min(1.0, self.act_el / self.act_dur)
        sp = a.speed_at(u)
        if sp:
            self.step(sp, dt)
        prev, self.act_u = self.act_u, u
        for eu, fn in a.events:
            if prev < eu <= u:
                fn(self)
                if self.state != "act" or self.act is not a:
                    return
        if u >= 1.0:
            self.finish_action()

    def finish_action(self):
        self.act = None
        self.pose["rot"] = wrap_deg(self.pose["rot"])
        nxt, self.act_next = self.act_next, None
        if nxt:
            nxt()
        else:
            self.resume()

    # ---------------- comportamiento ----------------
    def decide(self):
        a = ACTIVIDAD
        opts = [("walk", 40), ("idle", 22), ("sit", 8),
                ("action", 22 * a), ("watch", 3 * a), ("run", 4 * a), ("jump", 2 * a), ("wave", 2 * a)]
        s = random.choices([o[0] for o in opts], [o[1] for o in opts])[0]
        if s == "walk":
            if random.random() < 0.35:
                self.facing *= -1
            self.set_state("walk", random.uniform(4, 12))
        elif s == "idle":
            self.set_state("idle", random.uniform(3, 8))
        elif s == "sit":
            self.set_state("sit", random.uniform(8, 20))
        elif s == "run":
            self.set_state("run", random.uniform(1.5, 3))
        elif s == "wave":
            self.set_state("wave", random.uniform(1.2, 2.2))
        elif s == "watch":
            self.notice_cursor()
        elif s == "jump":
            self.jump()
        else:
            self.start_action(random.choice(SOLO))

    def resume(self):
        """Qué hacer al terminar una acción o al aterrizar."""
        if self.opponent is not None and self.opponent in self.crew.members and self.fight_t > 0:
            self.set_state("fight")
        elif self.chase_t > 0:
            self.set_state("chase")
        else:
            self.opponent = None
            self.fight_t = 0.0
            self.decide()

    def sprint(self):
        """¡Sale corriendo de la nada!"""
        if random.random() < 0.4:
            self.alert_t = 0.5
        if random.random() < 0.4:
            self.facing *= -1
        self.set_state("sprint", random.uniform(1.5, 3.5))

    def notice_cursor(self):
        self.alert_t = 0.8
        self.notice_cd = random.uniform(25, 60)
        self.set_state("watch", random.uniform(1.2, 2.5))

    def jump(self, vx=None):
        self.jump_vx = vx
        self.set_state("crouch", 0.14)

    def launch(self):
        self.reaching = self.chase_t > 0
        h = self.H * (1.3 if self.reaching else 0.9)
        self.vy = -math.sqrt(2 * GRAVITY * h)
        self.vx = self.jump_vx if self.jump_vx is not None else self.facing * random.uniform(0, 120)
        self.jump_vx = None
        self.thrown = False
        self.set_state("air")

    # ---------------- pelea ----------------
    def start_fight(self, other):
        self.leave_partner()
        other.leave_partner()
        dur = random.uniform(6, 10)
        for a, b in ((self, other), (other, self)):
            a.opponent, a.fight_t, a.hits = b, dur, 0
            a.attack_cd = random.uniform(0.4, 1.2)
            a.chase_t = 0
            if a.grounded():
                a.set_state("fight")

    def finish_fight(self):
        o = self.opponent
        for m in (self, o):
            if m is not None:
                m.opponent = None
                m.fight_t = 0.0
        if o is None or o not in self.crew.members:
            self.decide()
            return
        win = lose = None
        if self.hits - o.hits >= 2:
            win, lose = self, o
        elif o.hits - self.hits >= 2:
            win, lose = o, self
        self.hits = o.hits = 0
        if win is None and self.grounded() and o.grounded():
            self.start_social(o, "mano")
            return
        for m in (self, o):
            if not m.grounded():
                continue
            if m is win:
                m.start_action(random.choice(["victoria", "celebrar", "musculos"]))
            elif m is lose:
                m.start_action(random.choice(["frustrado", "reverencia", "rascarse"]))
            else:
                m.decide()

    def fight_hit(self, kind, reach, limb, dy=0.45, power=1.0, high=True):
        o = self.opponent
        if o is None or o not in self.crew.members:
            return
        dx = o.hx - self.hx
        if not (o.grounded() and abs(dx) < reach * self.H and sign(dx) == self.facing
                and abs(o.hy - self.hy) < dy * self.H):
            return
        if o.state == "act" and o.act is not None and o.act.kind in ("react", "defend"):
            return
        self.fx_t, self.fx_pt, self.fx_scale = 0.18, QPointF(self.joints[limb]), 1.0
        o.facing = -self.facing
        if o.state == "fight" and kind != "throw":
            r = random.random()
            if r < 0.22:
                o.start_action("bloqueo")
                return
            if r < 0.32:
                o.start_action(random.choice(["esquive", "esquive", "esquive_mortal"]))
                return
            if r < 0.38 and high:
                o.start_action("agacharse")
                return
        self.hits += 1
        if kind == "light":
            o.start_action("tambaleo")
            if power > 1.2:
                o.act_dur *= 1.4
        elif kind == "heavy":
            o.vx = self.facing * random.uniform(300, 450) * power
            o.vy = -random.uniform(450, 700) * min(power, 1.2)
            o.thrown = True
            o.set_state("air")
        elif kind == "launch":
            o.vx = self.facing * 150
            o.vy = -1150
            o.thrown = True
            o.set_state("air")
        elif kind == "down":
            o.start_action("derribado")
        elif kind == "throw":
            o.vx = -self.facing * random.uniform(300, 420)
            o.vy = -1000
            o.thrown = True
            o.set_state("air")

    # ---------------- pareja ----------------
    def leave_partner(self):
        p = self.partner
        self.partner = None
        if p is not None and p.partner is self:
            p.partner = None
            if p.state in ("tag_it", "tag_run", "approach", "wait"):
                p.decide()

    def start_social(self, other, kind):
        self.leave_partner()
        other.leave_partner()
        self.partner, other.partner = other, self
        self.social_kind = other.social_kind = kind
        self.lead, other.lead = True, False
        d = other.hx - self.hx
        self.facing = sign(d) if abs(d) > 1 else self.facing
        L, Rb, _ = desktop_bounds()
        m = self.H * 0.35
        tx = self.hx + self.facing * SOCIAL[kind] * self.H
        if not (L + m < tx < Rb - m):
            self.facing *= -1
            tx = self.hx + self.facing * SOCIAL[kind] * self.H
        other.approach_x = tx
        other.approach_t = 4.0
        self.set_state("wait", 6.0)
        other.set_state("approach")

    def end_social(self):
        self.partner = None
        self.resume()

    def update_approach(self, dt):
        p = self.partner
        if p is None or p not in self.crew.members or p.state != "wait":
            self.leave_partner()
            self.decide()
            return
        self.approach_t -= dt
        dx = self.approach_x - self.hx
        self.moving = False
        if abs(dx) < 3 or self.approach_t <= 0:
            self.facing = sign(p.hx - self.hx)
            p.facing = -self.facing
            k = self.social_kind
            for m in (self, p):
                m.start_action(k, then=m.end_social)
            return
        self.facing = sign(dx)
        self.moving = self.step(min(WALK_SPEED * 1.4, abs(dx) / dt), dt)
        if not self.moving:
            self.approach_t = 0

    def pair_fx(self):
        p = self.partner
        if p is None:
            return
        mine = QPointF(self.hx, self.hy) + self.joints["haF"]
        theirs = QPointF(p.hx, p.hy) + p.joints["haF"]
        mid = (mine + theirs) * 0.5
        self.fx_t, self.fx_scale = 0.25, 0.7
        self.fx_pt = mid - QPointF(self.hx, self.hy)

    def start_tag(self, other):
        """Juego de 'las traes': self la trae."""
        self.leave_partner()
        other.leave_partner()
        dur = random.uniform(8, 13)
        self.partner, other.partner = other, self
        self.tag_t = other.tag_t = dur
        self.set_state("tag_it")
        self.tag_wait = 0.8
        self.say("¡Las traes!", 1.0)
        other.set_state("tag_run")
        other.flee_turn = 0.0

    def update_tag(self, dt):
        p = self.partner
        if p is None or p not in self.crew.members:
            self.partner = None
            self.decide()
            return
        self.tag_t -= dt
        if self.tag_t <= 0:
            self.partner = p.partner = None
            for m in (self, p):
                if m.grounded():
                    m.start_action("reir")
            return
        self.moving = False
        if self.state == "tag_it":
            if self.tag_wait > 0:
                self.tag_wait -= dt
                self.facing = sign(p.hx - self.hx)
                return
            if not p.grounded():
                return
            dx = p.hx - self.hx
            self.facing = sign(dx)
            self.moving = self.step(235, dt)
            if abs(dx) < self.H * 0.45:
                self.fx_t, self.fx_scale = 0.2, 0.6
                self.fx_pt = QPointF(self.joints["haF"])
                self.set_state("tag_run")
                self.flee_turn = 0.0
                p.set_state("tag_it")
                p.tag_wait = 0.9
                self.say("¡Te toca!", 1.0)
        else:
            if self.flee_turn > 0:
                self.flee_turn -= dt
            else:
                self.facing = sign(self.hx - p.hx)
            chased = p.state == "tag_it" and p.tag_wait <= 0
            self.moving = self.step(215 if chased else 120, dt)
            if not self.moving:
                self.facing *= -1
                self.flee_turn = 1.2

    # ---------------- pose objetivo ----------------
    def target_pose(self):
        s, t = self.state, self.t
        if s == "act":
            return self.act.pose(max(0.0, self.act_u), t, self)
        if s in ("walk", "approach"):
            return pose_walk(self.phase)
        if s == "run":
            return pose_walk(self.phase, amp=1.45, lean=15)
        if s == "sprint":
            return pose_walk(self.phase, amp=1.6, lean=24)
        if s in ("tag_it", "tag_run"):
            if self.moving:
                return pose_walk(self.phase, amp=1.5, lean=18)
            return pose_stand(t)
        if s in ("wave", "greet"):
            return pose_wave(t)
        if s == "watch":
            return pose_watch(t, self.look)
        if s == "chase":
            if self.chase_moving:
                return pose_walk(self.phase, amp=1.45 if self.chase_fast else 1.15,
                                 lean=15 if self.chase_fast else 8)
            return pose_watch(t, self.look)
        if s == "sit":
            return pose_sit(t)
        if s in ("crouch", "land"):
            return CROUCH
        if s == "fight":
            sh = 12 * math.sin(self.phase * 2 * math.pi) if self.moving else 0.0
            return pose_guard(t, sh)
        if s == "drag":
            return pose_dangle(t, clamp(-self.svx * self.facing * 0.04, -45, 45))
        if s == "air":
            if self.thrown:
                return pose_flail(t)
            if self.reaching:
                return REACH
            return TUCK if self.vy < 0 else FALL
        return pose_stand(t)

    # ---------------- actualización ----------------
    def update_logic(self, dt):
        self.t += dt
        self.timer -= dt
        self.meet_cd -= dt
        self.notice_cd -= dt
        self.jump_cd -= dt
        self.alert_t = max(0.0, self.alert_t - dt)
        self.fx_t = max(0.0, self.fx_t - dt)
        self.say_t = max(0.0, self.say_t - dt)
        if self.fight_t > 0:
            self.fight_t -= dt
        if self.chase_t > 0:
            self.chase_t -= dt

        # parpadeo
        self.blink_in -= dt
        if self.blink_in <= 0:
            self.blink_t, self.blink_in = 0.12, random.uniform(2, 6)
        self.blink_t = max(0.0, self.blink_t - dt)

        # hacia dónde ve (ojos/cabeza)
        look_target = 0.0
        if self.state in ("watch", "chase"):
            _, dy = self.cursor_rel()
            look_target = clamp(dy / (self.H * 3), -0.6, 1.0)
        self.look += (look_target - self.look) * (1 - math.exp(-dt * 8))

        L, Rb, top = desktop_bounds()
        m = self.H * 0.35
        s = self.state

        if s == "drag":
            self.update_drag(dt)
        elif s == "air":
            self.update_air(dt, L, Rb, top, m)
        else:
            if s in ("walk", "run"):
                if not self.step(WALK_SPEED if s == "walk" else RUN_SPEED, dt):
                    self.facing *= -1
                dx, dy = self.cursor_rel()
                if (self.notice_cd <= 0 and abs(dx) < self.H * 1.8 and -self.H < dy < self.H * 3
                        and random.random() < dt * 0.35 * ACTIVIDAD):
                    self.notice_cursor()
            elif s == "sprint":
                if not self.step(SPRINT_SPEED, dt):
                    self.facing *= -1
            elif s == "watch":
                dx, _ = self.cursor_rel()
                if abs(dx) > self.H * 0.1:
                    self.facing = sign(dx)
            elif s == "chase":
                self.update_chase(dt)
            elif s == "fight":
                self.update_fight(dt)
            elif s == "act":
                self.update_act(dt)
            elif s in ("tag_it", "tag_run"):
                self.update_tag(dt)
            elif s == "approach":
                self.update_approach(dt)
            elif s == "wait":
                p = self.partner
                if p is None or p not in self.crew.members:
                    self.partner = None
                    self.decide()
                else:
                    self.facing = sign(p.hx - self.hx)

            # ¡a correr de la nada!
            if (self.state in ("walk", "idle", "sit") and self.partner is None
                    and random.random() < dt * ACTIVIDAD / SPRINT_CADA):
                self.sprint()

            if self.state not in self.TIMERLESS and self.state in self.GROUNDED and self.timer <= 0:
                self.on_timer_end()

        # suavizado de pose -> transiciones fluidas entre estados
        if self.state != "act":
            self.pose["rot"] = wrap_deg(self.pose["rot"])
        speed = self.act.snap if (self.state == "act" and self.act) else 22
        k = 1 - math.exp(-dt * speed)
        self.pose = lerp_pose(self.pose, self.target_pose(), k)
        self.joints = solve(self.pose, self.H, self.facing)

        # pegar al piso
        if self.state in self.GROUNDED:
            g = ground_at(self.hx) or self.last_ground
            dropped = g > self.last_ground + 3      # pasó a un piso más bajo (otro monitor)
            self.last_ground = g
            cy = contact(self.joints, self.H)
            lift = self.pose["lift"] * self.H
            if dropped and self.state in self.MOVING:
                self.thrown = False
                self.vx, self.vy = self.facing * 40, 0.0
                self.set_state("air")       # se acabó el piso: a caer
            else:
                self.hy = g - cy - lift

    def on_timer_end(self):
        s = self.state
        if s == "crouch":
            self.launch()
        elif s == "watch":
            if random.random() < 0.5:
                self.chase_t = random.uniform(4, 9)
                self.set_state("chase")
            else:
                self.decide()
        elif s == "wait":
            self.leave_partner()
            self.decide()
        elif s == "sprint":
            self.set_state("idle", random.uniform(1.0, 2.5))   # a recuperar el aire
        else:
            self.resume()

    def update_chase(self, dt):
        if self.chase_t <= 0:
            self.decide()
            return
        dx, dy = self.cursor_rel()
        self.chase_moving = False
        if abs(dx) > self.H * 0.3:
            self.facing = sign(dx)
            self.chase_fast = abs(dx) > self.H * 3
            sp = RUN_SPEED if self.chase_fast else WALK_SPEED * 1.6
            self.chase_moving = self.step(sp, dt)
        elif self.jump_cd <= 0 and 0 < dy < self.H * 2.2:
            self.jump_cd = random.uniform(0.6, 1.4)
            self.jump(vx=clamp(dx * 4, -200, 200))

    def update_fight(self, dt):
        o = self.opponent
        if self.fight_t <= 0 or o is None or o not in self.crew.members:
            self.finish_fight()
            return
        dx = o.hx - self.hx
        if abs(dx) > 2:
            self.facing = sign(dx)
        self.moving = False
        if not o.grounded() or (o.state == "act" and o.act is not None and o.act.kind == "react"):
            return            # el otro va volando o está en el piso: esperar en guardia
        d = abs(dx) / self.H
        self.attack_cd -= dt
        if d > 0.55:
            if self.attack_cd <= 0 and d < 1.4 and random.random() < 0.5:
                keys, ws = zip(*FIGHT_FAR)
                self.attack_cd = random.uniform(0.6, 1.4)
                self.start_action(random.choices(keys, ws)[0])
                return
            self.moving = self.step(110, dt)
        elif d < 0.3:
            self.facing *= -1                  # demasiado cerca: un pasito atrás
            self.step(80, dt)
            self.facing *= -1
        if self.attack_cd <= 0 and d < 0.64:
            keys, ws = zip(*FIGHT_CLOSE)
            self.attack_cd = random.uniform(0.5, 1.4)
            self.start_action(random.choices(keys, ws)[0])

    def update_air(self, dt, L, Rb, top, m):
        self.vy += GRAVITY * dt
        self.hx += self.vx * dt
        self.hy += self.vy * dt
        self.vx *= 0.995
        if self.hx < L + m:
            self.hx, self.vx = L + m, abs(self.vx) * 0.5
        elif self.hx > Rb - m:
            self.hx, self.vx = Rb - m, -abs(self.vx) * 0.5
        if self.hy < top + self.H * 0.9 and self.vy < 0:
            self.vy = abs(self.vy) * 0.3
        if self.thrown and abs(self.vx) > 60 and self.opponent is None:
            self.facing = sign(self.vx)

        g = ground_at(self.hx) or self.last_ground
        self.last_ground = g
        cy = contact(self.joints, self.H)
        if self.vy >= 0 and self.hy + cy >= g:
            impact = self.vy
            self.hy = g - cy
            self.vx = self.vy = 0.0
            self.reaching = False
            if self.thrown and (impact > 1500 or random.random() < 0.55):
                self.thrown = False
                self.start_action("en_suelo")
            else:
                self.thrown = False
                self.set_state("land", 0.18)

    def update_drag(self, dt):
        cur = QPointF(QCursor.pos())
        head = self.joints["head"]
        nx = cur.x() - self.grab.x() - head.x()
        ny = cur.y() - self.grab.y() - head.y()
        if dt > 0:
            a = 1 - math.exp(-dt * 12)
            self.svx += ((nx - self.hx) / dt - self.svx) * a
            self.svy += ((ny - self.hy) / dt - self.svy) * a
        self.hx, self.hy = nx, ny

    def sync(self):
        self.move(int(round(self.hx - self.ox)), int(round(self.hy - self.oy)))
        self.update()

    # ---------------- dibujo ----------------
    def bubble_text(self):
        if self.alert_t > 0:
            return "!"
        if self.say_t > 0:
            return self.say_text
        if self.state == "act" and self.act is not None:
            for u0, u1, text in self.act.say:
                if u0 <= self.act_u <= u1:
                    return text
        return None

    def paint_on(self, p):
        j = self.joints
        if self.state == "sprint" or (self.state == "act" and self.act and self.act.lines):
            draw_speed_lines(p, self.H, self.facing, self.spec["color"], self.t)
        draw_stickman(p, j, self.H, self.spec, self.facing, self.t,
                      self.blink_t > 0, self.look)
        if self.fx_t > 0:
            draw_impact(p, self.fx_pt, self.H, self.fx_t / 0.25, self.fx_scale)
        text = self.bubble_text()
        if text:
            top = min(pt.y() for pt in j.values()) - 0.13 * self.H
            if self.spec["acc"] == "margarita":
                top -= 0.14 * self.H
            c = QPointF(j["head"].x(), top - self.H * 0.2)
            draw_bubble(p, c, self.H, text)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.ox, self.oy)
        j = self.joints
        xs = [pt.x() for pt in j.values()]
        ys = [pt.y() for pt in j.values()]
        pad = self.H * 0.16
        # Área casi invisible (alpha 1) para poder agarrarlo con el mouse;
        # el resto de la ventana es 100% transparente y deja pasar los clics.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 1))
        p.drawRoundedRect(QRectF(min(xs) - pad, min(ys) - pad,
                                 max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad),
                          12, 12)
        self.paint_on(p)

    # ---------------- mouse ----------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            gp = e.globalPosition()
            self.press_pos = gp
            self.drag_dist = 0.0
            head = QPointF(self.hx, self.hy) + self.joints["head"]
            self.grab = gp - head
            self.dragging = True

    def mouseMoveEvent(self, e):
        if self.dragging and self.press_pos is not None:
            d = e.globalPosition() - self.press_pos
            self.drag_dist = max(self.drag_dist, math.hypot(d.x(), d.y()))
            if self.drag_dist > 5 and self.state != "drag":
                self.svx = self.svy = 0.0
                self.chase_t = 0.0
                self.leave_partner()
                self.set_state("drag")

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.dragging:
            return
        self.dragging = False
        if self.state == "drag":
            self.vx = clamp(self.svx, -1800, 1800)
            self.vy = clamp(self.svy, -1800, 1800)
            self.thrown = True
            self.set_state("air")
        elif self.grounded() and self.opponent is None and self.partner is None:
            r = random.random()
            if r < 0.4:
                self.set_state("wave", 1.5)
            elif r < 0.7:
                self.jump()
            else:
                self.start_action(random.choice(["reir", "rascarse", "celebrar", "mortal_atras"]))

    def contextMenuEvent(self, e):
        menu = QMenu()
        menu.addAction(f"— {self.spec['name']} —").setEnabled(False)
        free = self.grounded() and self.opponent is None

        def order(fn):
            def run():
                self.chase_t = 0.0
                self.leave_partner()
                fn()
            return run

        basics = [("Caminar", lambda: self.set_state("walk", 6)),
                  ("Correr", lambda: self.set_state("run", 3)),
                  ("¡Correr a toda velocidad!", self.sprint),
                  ("Sentarse", lambda: self.set_state("sit", 12)),
                  ("Saltar", self.jump),
                  ("Perseguir el cursor", self.notice_cursor)]
        for name, fn in basics:
            a = menu.addAction(name)
            a.setEnabled(free)
            a.triggered.connect(order(fn))

        sub = menu.addMenu("Acciones")
        sub.setEnabled(free)
        for key in sorted(SOLO + ["saludar"], key=lambda k: ACTIONS[k].label):
            sub.addAction(ACTIONS[key].label).triggered.connect(
                order(lambda _=False, k=key: self.start_action(k)))

        others = [m for m in self.crew.members
                  if m is not self and m.grounded() and m.opponent is None]
        if others and free:
            withm = menu.addMenu("Con otro…")
            for o in others:
                om = withm.addMenu(o.spec["name"])
                om.addAction("Pelear").triggered.connect(lambda _=False, o=o: self.start_fight(o))
                om.addAction("Jugar a las traes").triggered.connect(
                    lambda _=False, o=o: self.start_tag(o))
                for k in SOCIAL:
                    om.addAction(ACTIONS[k].label).triggered.connect(
                        lambda _=False, o=o, k=k: self.start_social(o, k))
        menu.addSeparator()
        menu.addAction("Quitar").triggered.connect(lambda: self.crew.remove(self))
        menu.exec(e.globalPos())


# ----------------------------------------------------------------------------
# El grupo: reloj, encuentros entre ellos y bandeja del sistema
# ----------------------------------------------------------------------------
class Crew:
    def __init__(self, app):
        self.app = app
        self.members = []
        self.next_spec = 0
        self.time = 0.0
        self.clock = QElapsedTimer()
        self.clock.start()
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(int(1000 / FPS))
        self.paused = False
        self.build_tray()

    def spawn(self, spec=None):
        if spec is None:
            spec = ROSTER[self.next_spec % len(ROSTER)]
            self.next_spec += 1
        g = QGuiApplication.primaryScreen().availableGeometry()
        x = random.uniform(g.left() + HEIGHT, g.right() - HEIGHT)
        s = Stickman(self, spec, x, g.top() + HEIGHT * 1.2)   # caen desde arriba
        self.members.append(s)
        s.sync()
        s.show()

    def remove(self, s=None):
        if not self.members:
            return
        s = s or self.members[-1]
        self.members.remove(s)
        s.leave_partner()
        for m in self.members:
            if m.opponent is s:
                m.opponent, m.fight_t = None, 0.0
                if m.state == "fight":
                    m.decide()
        s.close()
        s.deleteLater()

    def tick(self):
        dt = min(self.clock.restart() / 1000.0, 0.05)
        if self.paused:
            return
        self.step(dt)
        for m in self.members:
            m.sync()

    def step(self, dt):
        self.time += dt
        for m in list(self.members):
            m.update_logic(dt)
        self.check_encounters()

    def check_encounters(self):
        ms = self.members
        for i in range(len(ms)):
            for k in range(i + 1, len(ms)):
                a, b = ms[i], ms[k]
                if not (a.state in Stickman.CALM and b.state in Stickman.CALM
                        and a.meet_cd <= 0 and b.meet_cd <= 0
                        and a.partner is None and b.partner is None
                        and a.opponent is None and b.opponent is None
                        and abs(a.hx - b.hx) < HEIGHT * 0.7 and abs(a.hy - b.hy) < HEIGHT * 0.3):
                    continue
                kinds, ws = zip(*ENCUENTRO.items())
                r = random.choices(kinds, ws)[0]
                a.meet_cd = b.meet_cd = random.uniform(*ENCUENTRO_PAUSA)
                if r == "saludar":
                    a.facing = sign(b.hx - a.hx)
                    b.facing = -a.facing
                    a.set_state("greet", 1.6)
                    b.set_state("greet", 1.6)
                elif r == "convivir":
                    sk, sw = zip(*SOCIAL_W.items())
                    a.start_social(b, random.choices(sk, sw)[0])
                elif r == "traes":
                    a.start_tag(b)
                elif r == "pelear":
                    a.start_fight(b)
                else:
                    a.meet_cd = b.meet_cd = random.uniform(8, 16)

    # ---------------- bandeja ----------------
    def build_tray(self):
        self.tray = QSystemTrayIcon(self.make_icon())
        self.tray.setToolTip("Desk Stickmen")
        menu = QMenu()
        menu.addAction("Agregar stickman").triggered.connect(lambda: self.spawn())
        menu.addAction("Quitar uno").triggered.connect(lambda: self.remove())
        self.pause_act = QAction("Pausar")
        self.pause_act.triggered.connect(self.toggle_pause)
        menu.addAction(self.pause_act)
        self.hide_act = QAction("Ocultar")
        self.hide_act.triggered.connect(self.toggle_visible)
        menu.addAction(self.hide_act)
        menu.addSeparator()
        menu.addAction("Salir").triggered.connect(self.app.quit)
        self.menu = menu
        self.tray.setContextMenu(menu)
        self.tray.show()

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_act.setText("Reanudar" if self.paused else "Pausar")

    def toggle_visible(self):
        vis = self.hide_act.text() == "Mostrar"
        for m in self.members:
            m.setVisible(vis)
        self.hide_act.setText("Ocultar" if vis else "Mostrar")

    @staticmethod
    def make_icon():
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(32, 36)
        j = solve(pose_wave(0.3), 58, 1)
        draw_stickman(p, j, 58, ROSTER[0], 1, 0)
        p.end()
        return QIcon(pm)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    crew = Crew(app)
    for spec in ROSTER:
        crew.spawn(spec)
    crew.next_spec = len(ROSTER)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
