#!/usr/bin/env python3
"""
Desk Stickmen — stickmen animados que viven sobre tu barra de tareas.

Cada stickman es una ventanita transparente, siempre encima, que camina por el
"piso" (el borde superior de la barra de tareas). Por su cuenta caminan, corren,
se sientan, saltan, se saludan, se pelean entre ellos y de repente notan el
cursor y lo persiguen. Los puedes agarrar con el mouse y lanzarlos, hacer clic
para que reaccionen o clic derecho para darles órdenes. Se controlan desde el
ícono de la bandeja del sistema.

Requisitos:  pip install PySide6
Ejecutar:    python desk_stickmen.py
"""
import math
import random
import sys

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QElapsedTimer
from PySide6.QtGui import (QPainter, QPen, QColor, QGuiApplication, QPixmap,
                           QIcon, QAction, QCursor, QPolygonF, QFont)
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon

# ----------------------------------------------------------------------------
# Ajustes
# ----------------------------------------------------------------------------
HEIGHT = 90            # altura del stickman en píxeles
GRAVITY = 2400.0       # px/s²
WALK_SPEED = 70.0      # px/s
RUN_SPEED = 190.0      # px/s
FPS = 60

# Probabilidades cuando dos se encuentran
P_GREET = 0.40
P_FIGHT = 0.30

# Elenco original. acc: bufanda | moño | gorra | audifonos
ROSTER = [
    dict(name="Uva",    color="#8B5CF6", accent="#22D3EE", acc="bufanda",   eyes="#1F1147"),
    dict(name="Chicle", color="#EC4899", accent="#7C3AED", acc="moño",      eyes="#3B0A24"),
    dict(name="Ola",    color="#14B8A6", accent="#1E293B", acc="gorra",     eyes="#06302B"),
    dict(name="Tinta",  color="#2B2B2B", accent="#EF4444", acc="audifonos", eyes="#FFFFFF"),
]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def sign(v):
    return 1 if v >= 0 else -1


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
# Poses. Ángulos en grados: 0 = hacia abajo, positivo = hacia donde mira.
# B = extremidad de atrás, F = extremidad de enfrente.
# ----------------------------------------------------------------------------
KEYS = ("lean", "tilt", "thB", "shB", "thF", "shF", "uaB", "faB", "uaF", "faF")


def P(**k):
    d = dict.fromkeys(KEYS, 0.0)
    d.update(k)
    return d


def lerp_pose(a, b, k):
    return {key: a[key] + (b[key] - a[key]) * k for key in KEYS}


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
    p = pose_stand(t)
    p.update(uaF=150, faF=165 + 25 * math.sin(t * 11), uaB=-8, faB=-2, tilt=-6)
    return p


def pose_watch(t, look):
    p = pose_stand(t)
    p.update(tilt=-look * 28, lean=2 - look * 6)
    return p


def pose_sit(t):
    return P(lean=-12 + 1.5 * math.sin(t * 1.5), tilt=-4 + 4 * math.sin(t * 0.6),
             thB=135, shB=45, thF=92, shF=88,
             uaB=60, faB=100, uaF=-35, faF=-35)


def pose_crouch():
    return P(lean=22, thB=50, shB=-25, thF=58, shF=-18,
             uaB=-40, faB=-15, uaF=-30, faF=-5)


def pose_tuck():
    return P(lean=8, thB=75, shB=-5, thF=85, shF=5,
             uaB=150, faB=165, uaF=160, faF=175)


def pose_reach():
    """Saltando para atrapar el cursor."""
    return P(lean=-4, tilt=-20, thB=-15, shB=-30, thF=30, shF=5,
             uaB=150, faB=160, uaF=172, faF=178)


def pose_fall():
    return P(lean=4, thB=-10, shB=-14, thF=20, shF=8,
             uaB=110, faB=130, uaF=120, faF=140)


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


# --- pelea ---
def pose_guard(t, shuffle=0.0):
    s = 3 * math.sin(t * 8) + shuffle
    return P(lean=10, tilt=-4, thB=-20 + s, shB=-20 + s, thF=22 - s, shF=10 - s,
             uaB=40, faB=145, uaF=55, faF=150)


def pose_punch():
    return P(lean=18, tilt=4, thB=-24, shB=-24, thF=26, shF=12,
             uaB=45, faB=140, uaF=88, faF=90)


def pose_kick():
    return P(lean=-18, tilt=10, thB=-8, shB=-8, thF=98, shF=92,
             uaB=-55, faB=-30, uaF=60, faF=140)


def pose_block():
    return P(lean=-10, tilt=8, thB=-26, shB=-26, thF=18, shF=8,
             uaB=70, faB=175, uaF=80, faF=175)


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
    return j


# ----------------------------------------------------------------------------
# Dibujo
# ----------------------------------------------------------------------------
def draw_stickman(p, j, H, spec, f, t, blink=False, look=0.0):
    col = QColor(spec["color"])
    back = col.lighter(170) if col.lightness() < 70 else col.darker(125)
    acc = QColor(spec["accent"])
    w = H * 0.075
    R = 0.13 * H

    def seg(c, *pts, width=w):
        p.setPen(QPen(c, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF(list(pts)))

    c = j["head"]
    kind = spec["acc"]

    # Extremidades de atrás (tono distinto para dar profundidad)
    seg(back, j["sh"], j["elB"], j["haB"])
    seg(back, j["hip"], j["knB"], j["ftB"])

    # Cola de la bufanda (detrás del cuerpo)
    if kind == "bufanda":
        n = j["neck"]
        tail_end = n + QPointF(-f * R * 1.6, R * 0.5 + R * 0.35 * math.sin(t * 9))
        tail_mid = n + QPointF(-f * R * 0.8, R * 0.15 + R * 0.2 * math.sin(t * 9 + 1))
        seg(acc, n, tail_mid, tail_end, width=w * 0.8)

    # Torso y pierna de enfrente
    seg(col, j["hip"], j["neck"])
    seg(col, j["hip"], j["knF"], j["ftF"])

    # Cabeza
    p.setPen(Qt.NoPen)
    p.setBrush(col)
    p.drawEllipse(c, R, R)

    # Ojos (de perfil, hacia donde mira; suben si ve algo arriba)
    p.setBrush(QColor(spec["eyes"]))
    eh = R * 0.04 if blink else R * 0.2
    ey = -R * 0.08 - look * R * 0.22
    for dx in (0.18, 0.58):
        p.drawEllipse(c + QPointF(f * R * dx, ey), R * 0.12, eh)

    # Accesorios
    if kind == "gorra":
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawChord(QRectF(c.x() - R * 1.06, c.y() - R * 1.12, R * 2.12, R * 2.12),
                    0, 180 * 16)
        seg(acc, c + QPointF(f * R * 0.3, -R * 0.06),
            c + QPointF(f * R * 1.55, -R * 0.06), width=w * 0.75)
    elif kind == "moño":
        b = c + QPointF(-f * R * 0.65, -R * 0.8)
        s = R * 0.55
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawPolygon(QPolygonF([b, b + QPointF(-s, -s * 0.7), b + QPointF(-s, s * 0.7)]))
        p.drawPolygon(QPolygonF([b, b + QPointF(s, -s * 0.7), b + QPointF(s, s * 0.7)]))
        p.drawEllipse(b, s * 0.3, s * 0.3)
    elif kind == "audifonos":
        p.setPen(QPen(acc, w * 0.55, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(c.x() - R * 1.2, c.y() - R * 1.25, R * 2.4, R * 2.4),
                  15 * 16, 150 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawEllipse(c + QPointF(-f * R * 0.15, R * 0.05), R * 0.42, R * 0.58)
    elif kind == "bufanda":
        n = j["neck"]
        seg(acc, n + QPointF(-R * 0.55, -R * 0.05), n + QPointF(R * 0.55, -R * 0.05),
            width=w * 1.1)

    # Brazo de enfrente al final (queda sobre todo lo demás)
    seg(col, j["sh"], j["elF"], j["haF"])


def draw_impact(p, c, H, k):
    """Destello de golpe. k va de 1 a 0 mientras se desvanece."""
    r1, r2 = H * (0.10 + 0.08 * (1 - k)), H * 0.05
    pts = []
    for i in range(16):
        a = i * math.pi / 8
        r = r1 if i % 2 == 0 else r2
        pts.append(c + QPointF(math.cos(a) * r, math.sin(a) * r))
    p.setPen(QPen(QColor(40, 40, 40, int(220 * k)), H * 0.02))
    p.setBrush(QColor(255, 230, 90, int(255 * k)))
    p.drawPolygon(QPolygonF(pts))


def draw_bubble(p, c, H, text):
    r = H * 0.11
    p.setPen(QPen(QColor(30, 30, 30), H * 0.022))
    p.setBrush(QColor(255, 255, 255))
    p.drawEllipse(c, r, r)
    f = QFont()
    f.setBold(True)
    f.setPixelSize(int(H * 0.17))
    p.setFont(f)
    p.setPen(QColor(220, 40, 40))
    p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignCenter, text)


# ----------------------------------------------------------------------------
# Un stickman = una ventanita transparente que se mueve por la pantalla
# ----------------------------------------------------------------------------
class Stickman(QWidget):
    GROUNDED = ("walk", "run", "idle", "wave", "sit", "greet", "crouch", "land",
                "watch", "chase", "fight", "punch", "kick", "block")
    TIMERLESS = ("fight", "chase")

    def __init__(self, crew, spec, x, y):
        flags = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
                 Qt.NoDropShadowWindowHint | Qt.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)

        self.crew, self.spec, self.H = crew, spec, HEIGHT
        self.resize(int(self.H * 1.8), int(self.H * 1.55))
        self.ox, self.oy = self.H * 0.9, self.H * 0.97   # cadera dentro de la ventana

        self.hx, self.hy = float(x), float(y)
        self.vx = self.vy = 0.0
        self.facing = random.choice((-1, 1))
        self.t = random.random() * 10
        self.phase = 0.0
        self.pose = pose_fall()
        self.joints = solve(self.pose, self.H, self.facing)
        self.state, self.timer = "air", 0.0
        self.thrown = False
        self.reaching = False
        self.meet_cd = 3.0
        self.blink_in = random.uniform(2, 5)
        self.blink_t = 0.0
        self.last_ground = ground_at(x) or y
        self.look = 0.0
        self.notice_cd = random.uniform(4, 10)

        # persecución del cursor
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
        self.hit_done = False
        self.moving = False
        self.fx_t = 0.0
        self.fx_pt = QPointF()

        # arrastre
        self.dragging = False
        self.grab = QPointF()
        self.press_pos = None
        self.drag_dist = 0.0
        self.svx = self.svy = 0.0

    # ---------------- utilidades ----------------
    def set_state(self, s, dur=0.0):
        self.state, self.timer = s, dur

    def cursor_rel(self):
        """Cursor relativo a la cabeza: (dx, dy) con dy positivo = arriba."""
        cur = QPointF(QCursor.pos())
        head = QPointF(self.hx, self.hy) + self.joints["head"]
        return cur.x() - head.x(), head.y() - cur.y()

    def step(self, speed, dt):
        """Avanza hacia donde mira. Devuelve False si hay pared o vacío."""
        L, Rb, _ = desktop_bounds()
        m = self.H * 0.35
        nx = self.hx + self.facing * speed * dt
        if nx < L + m or nx > Rb - m or ground_at(nx) is None:
            return False
        self.hx = nx
        self.phase = (self.phase + dt * speed / (self.H * 1.05)) % 1.0
        return True

    # ---------------- comportamiento ----------------
    def decide(self):
        opts = [("walk", 42), ("idle", 14), ("run", 9), ("wave", 6), ("sit", 10),
                ("jump", 7), ("watch", 9)]
        s = random.choices([o[0] for o in opts], [o[1] for o in opts])[0]
        if s == "walk":
            if random.random() < 0.35:
                self.facing *= -1
            self.set_state("walk", random.uniform(2, 7))
        elif s == "run":
            self.set_state("run", random.uniform(1.2, 3))
        elif s == "idle":
            self.set_state("idle", random.uniform(1.5, 4))
        elif s == "wave":
            self.set_state("wave", random.uniform(1.2, 2.2))
        elif s == "sit":
            self.set_state("sit", random.uniform(4, 10))
        elif s == "watch":
            self.notice_cursor()
        else:
            self.jump()

    def resume(self):
        """Qué hacer al terminar una acción o al aterrizar."""
        if self.fight_t > 0 and self.opponent in self.crew.members:
            self.set_state("fight")
        elif self.chase_t > 0:
            self.set_state("chase")
        else:
            self.end_fight()
            self.decide()

    def notice_cursor(self):
        """¡De la nada ve el cursor!"""
        self.alert_t = 0.8
        self.notice_cd = random.uniform(8, 18)
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

    def start_fight(self, other):
        dur = random.uniform(5, 9)
        for a, b in ((self, other), (other, self)):
            a.opponent, a.fight_t = b, dur
            a.attack_cd = random.uniform(0.2, 0.9)
            a.chase_t = 0
            a.set_state("fight")

    def end_fight(self):
        self.opponent = None
        self.fight_t = 0.0

    def attack(self):
        self.hit_done = False
        if random.random() < 0.6:
            self.set_state("punch", 0.32)
        else:
            self.set_state("kick", 0.40)

    def do_hit(self):
        self.hit_done = True
        o = self.opponent
        if o not in self.crew.members:
            return
        kick = self.state == "kick"
        reach = self.H * (0.66 if kick else 0.6)
        if (o.state in self.GROUNDED and abs(o.hx - self.hx) < reach
                and abs(o.hy - self.hy) < self.H * 0.4):
            limb = self.joints["ftF" if kick else "haF"]
            self.fx_t, self.fx_pt = 0.18, QPointF(limb)
            if o.state == "fight" and random.random() < 0.3:
                o.hx += self.facing * self.H * 0.12   # lo bloqueó
                o.set_state("block", 0.3)
            else:
                o.vx = self.facing * random.uniform(280, 480) * (1.3 if kick else 1.0)
                o.vy = -random.uniform(450, 750)
                o.thrown = True
                o.set_state("air")

    # ---------------- pose objetivo ----------------
    def target_pose(self):
        s, t = self.state, self.t
        if s == "walk":
            return pose_walk(self.phase)
        if s == "run":
            return pose_walk(self.phase, amp=1.45, lean=15)
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
            return pose_crouch()
        if s == "fight":
            sh = 12 * math.sin(self.phase * 2 * math.pi) if self.moving else 0.0
            return pose_guard(t, sh)
        if s == "punch":
            return pose_punch() if self.timer < 0.24 else pose_guard(t)
        if s == "kick":
            return pose_kick() if self.timer < 0.30 else pose_guard(t)
        if s == "block":
            return pose_block()
        if s == "drag":
            return pose_dangle(t, clamp(-self.svx * self.facing * 0.04, -45, 45))
        if s == "air":
            if self.thrown:
                return pose_flail(t)
            if self.reaching:
                return pose_reach()
            return pose_tuck() if self.vy < 0 else pose_fall()
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
            dx, dy = self.cursor_rel()
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
                # si el cursor pasa cerca, a veces lo nota
                dx, dy = self.cursor_rel()
                if (self.notice_cd <= 0 and abs(dx) < self.H * 1.8 and -self.H < dy < self.H * 3
                        and random.random() < dt * 0.8):
                    self.notice_cursor()
            elif s == "watch":
                dx, _ = self.cursor_rel()
                if abs(dx) > self.H * 0.1:
                    self.facing = sign(dx)
            elif s == "chase":
                self.update_chase(dt)
            elif s == "fight":
                self.update_fight(dt)
            elif s in ("punch", "kick"):
                hit_at = 0.22 if s == "punch" else 0.28
                if not self.hit_done and self.timer < hit_at:
                    self.do_hit()

            if self.state not in self.TIMERLESS and self.timer <= 0:
                self.on_timer_end()

        # suavizado de pose -> transiciones fluidas entre estados
        speed = 45 if self.state in ("punch", "kick", "block") else 22
        k = 1 - math.exp(-dt * speed)
        self.pose = lerp_pose(self.pose, self.target_pose(), k)
        self.joints = solve(self.pose, self.H, self.facing)

        # pegar al piso
        if self.state in self.GROUNDED:
            g = ground_at(self.hx) or self.last_ground
            self.last_ground = g
            cy = max(self.joints["ftB"].y(), self.joints["ftF"].y(), 0.0)
            if g > self.hy + cy + 3 and self.state in ("walk", "run", "chase", "fight"):
                self.thrown = False
                self.vx, self.vy = self.facing * 40, 0.0
                self.set_state("air")       # se acabó el piso: a caer
            else:
                self.hy = g - cy

    def on_timer_end(self):
        s = self.state
        if s == "crouch":
            self.launch()
        elif s in ("punch", "kick", "block"):
            self.attack_cd = random.uniform(0.35, 1.0)
            self.resume()
        elif s == "watch":
            if random.random() < 0.6:
                self.chase_t = random.uniform(4, 9)
                self.set_state("chase")
            else:
                self.decide()
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
            # está justo arriba y al alcance: ¡a saltar para atraparlo!
            self.jump_cd = random.uniform(0.6, 1.4)
            self.jump(vx=clamp(dx * 4, -200, 200))

    def update_fight(self, dt):
        o = self.opponent
        if self.fight_t <= 0 or o not in self.crew.members:
            self.end_fight()
            self.set_state("wave", 1.0) if random.random() < 0.5 else self.decide()
            return
        dx = o.hx - self.hx
        if abs(dx) > 2:
            self.facing = sign(dx)
        self.moving = False
        if o.state not in self.GROUNDED:      # el otro va volando: esperar en guardia
            return
        if abs(dx) > self.H * 0.52:
            self.moving = self.step(110, dt)
        elif abs(dx) < self.H * 0.3:
            self.facing *= -1                  # demasiado cerca: un pasito atrás
            self.step(80, dt)
            self.facing *= -1
        self.attack_cd -= dt
        if self.attack_cd <= 0 and abs(dx) < self.H * 0.62:
            self.attack()

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
        cy = max(self.joints["ftB"].y(), self.joints["ftF"].y(), 0.0)
        if self.vy >= 0 and self.hy + cy >= g:
            impact = self.vy
            self.hy = g - cy
            self.vx = self.vy = 0.0
            self.reaching = False
            if impact > 1700:
                self.set_state("sit", 1.4)     # aterrizaje duro: se queda sentado
            else:
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
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.ox, self.oy)
        j = self.joints
        xs = [pt.x() for pt in j.values()]
        ys = [pt.y() for pt in j.values()]
        pad = self.H * 0.14
        # Área casi invisible (alpha 1) para poder agarrarlo con el mouse;
        # el resto de la ventana es 100% transparente y deja pasar los clics.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 1))
        p.drawRoundedRect(QRectF(min(xs) - pad, min(ys) - pad,
                                 max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad),
                          12, 12)
        draw_stickman(p, j, self.H, self.spec, self.facing, self.t,
                      self.blink_t > 0, self.look)
        if self.fx_t > 0:
            draw_impact(p, self.fx_pt, self.H, self.fx_t / 0.18)
        if self.alert_t > 0:
            pop = min(1.0, (0.8 - self.alert_t) * 8)
            c = j["head"] + QPointF(0, -self.H * (0.18 + 0.12 * pop))
            draw_bubble(p, c, self.H, "!")

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
        elif self.state in self.GROUNDED and self.opponent is None:
            if random.random() < 0.5:
                self.set_state("wave", 1.5)
            else:
                self.jump()

    def contextMenuEvent(self, e):
        menu = QMenu()
        menu.addAction(f"— {self.spec['name']} —").setEnabled(False)
        grounded = self.state in self.GROUNDED and self.opponent is None

        def order(fn):
            def run():
                self.chase_t = 0.0
                fn()
            return run

        acts = [("Saludar", lambda: self.set_state("wave", 2)),
                ("Saltar", self.jump),
                ("Sentarse", lambda: self.set_state("sit", 10)),
                ("Correr", lambda: self.set_state("run", 3)),
                ("Caminar", lambda: self.set_state("walk", 5)),
                ("Perseguir el cursor", self.notice_cursor)]
        for name, fn in acts:
            a = menu.addAction(name)
            a.setEnabled(grounded)
            a.triggered.connect(order(fn))

        rivals = [m for m in self.crew.members
                  if m is not self and m.opponent is None and m.state in self.GROUNDED]
        if rivals and grounded:
            sub = menu.addMenu("Pelear con…")
            for r in rivals:
                sub.addAction(r.spec["name"]).triggered.connect(
                    lambda _=False, r=r: self.start_fight(r))
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
        s.close()
        s.deleteLater()

    def tick(self):
        dt = min(self.clock.restart() / 1000.0, 0.05)
        if self.paused:
            return
        for m in self.members:
            m.update_logic(dt)
        self.check_encounters()
        for m in self.members:
            m.sync()

    def check_encounters(self):
        ok = ("walk", "idle", "run")
        ms = self.members
        for i in range(len(ms)):
            for k in range(i + 1, len(ms)):
                a, b = ms[i], ms[k]
                if (a.state in ok and b.state in ok and a.meet_cd <= 0 and b.meet_cd <= 0
                        and abs(a.hx - b.hx) < HEIGHT * 0.7 and abs(a.hy - b.hy) < HEIGHT * 0.3):
                    r = random.random()
                    if r < P_GREET:
                        a.facing = sign(b.hx - a.hx)
                        b.facing = -a.facing
                        a.set_state("greet", 1.6)
                        b.set_state("greet", 1.6)
                        a.meet_cd = b.meet_cd = 12
                    elif r < P_GREET + P_FIGHT:
                        a.start_fight(b)
                        a.meet_cd = b.meet_cd = 20
                    else:
                        a.meet_cd = b.meet_cd = 4

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
