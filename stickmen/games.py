"""Juegos de grupo: parkour, cuerda, limbo, béisbol, pasar la pelota y más."""
from .core import *  # noqa: F401,F403
from .actions import (pose_walk, pose_stand, S, W, P, CROUCH, REACH, PHONE_EAR, PHONE_LOOK,
                      BAT_READY, lerp_pose, kf)
from PySide6.QtGui import QPainterPath

GAMES = {}


def game(cls):
    GAMES[cls.key] = cls
    return cls


class Overlay(QWidget):
    """Ventana transparente que no recibe clics, para dibujar cuerdas, varas y pelotas."""

    def __init__(self, game, x0, x1, ground):
        flags = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
                 Qt.NoDropShadowWindowHint | Qt.WindowDoesNotAcceptFocus |
                 Qt.WindowTransparentForInput)
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.game = game
        H = HEIGHT
        self.x0, self.y0 = int(x0), int(ground - 6.5 * H)
        self.setGeometry(self.x0, self.y0, int(x1 - x0), int(6.6 * H))
        self.show()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(-self.x0, -self.y0)
        self.game.draw_overlay(p)


class Game:
    key, label = "game", "Juego"
    min_p, max_p = 2, 4
    span = 6.0          # ancho aproximado en H
    overlay = False
    gather = True
    weight = 10

    def __init__(self, crew, players):
        self.crew, self.H = crew, HEIGHT
        self.players = list(players)
        self.t = 0.0
        self.phase = "gather" if self.gather else "play"
        self.gather_t = 9.0
        self.done = False
        self.spot = {}
        self.ov = None
        for s in self.players:
            s.join_game(self)
        self.cx = self.center()
        self.ground = ground_at(self.cx) or self.players[0].last_ground
        self.setup()
        if self.overlay:
            L, Rb, _ = desktop_bounds()
            m = (self.span / 2 + 3) * self.H
            self.ov = Overlay(self, max(L, self.cx - m), min(Rb, self.cx + m), self.ground)
        if self.phase == "play":
            self.begin()

    # ---- utilidades
    @classmethod
    def available(cls, crew):
        return True

    def center(self):
        L, Rb, _ = desktop_bounds()
        cx = sum(s.hx for s in self.players) / len(self.players)
        m = (self.span / 2 + 1) * self.H
        return clamp(cx, L + m, Rb - m) if Rb - L > 2 * m else (L + Rb) / 2

    def gx(self, k):
        return self.cx + k * self.H

    def run(self, s, key, mul=1.0):
        s.start_action(key, then=s.back_to_game)
        s.act_speed_mul = mul

    def active(self, s):
        return s.game is self and s.state == "game"

    # ---- ciclo
    def control(self, s, dt):
        if self.phase == "gather":
            if s in self.spot:
                x, f = self.spot[s]
                if s.walk_to(x, dt, RUN_SPEED if abs(x - s.hx) > 4 * self.H else WALK_SPEED * 1.4):
                    s.facing = f
        else:
            self.play(s, dt)

    def pose(self, s):
        if self.phase == "gather":
            if s.moving:
                return pose_walk(s.phase, amp=1.3 if abs(self.spot.get(s, (s.hx,))[0] - s.hx) > 4 * self.H else 1.0)
            return pose_stand(s.t)
        return self.play_pose(s)

    def tick(self, dt):
        if self.done:
            return
        self.t += dt
        if self.phase == "gather":
            self.gather_t -= dt
            ready = all(abs(s.hx - self.spot[s][0]) < 6 for s in self.players
                        if s in self.spot and s.state == "game")
            if ready or self.gather_t <= 0:
                for s in self.players:
                    if s in self.spot:
                        s.facing = self.spot[s][1]
                self.phase, self.t = "play", 0.0
                self.begin()
        else:
            self.update(dt)
        if self.ov is not None:
            self.ov.update()

    def relayout(self):
        self.setup()
        self.phase, self.gather_t = "gather", 6.0

    def end(self, winners=(), losers=()):
        if self.done:
            return
        self.done = True
        for s in list(self.players):
            s.game = None
            s.prop_override = None
            if s.state == "game" or (s.state == "act" and s.act is not None and s.act.kind == "game"):
                if s in winners:
                    s.start_action(random.choice(["celebrar", "victoria"]))
                elif s in losers:
                    s.start_action(random.choice(["frustrado", "reir", "rascarse"]))
                else:
                    s.decide()
        if self.ov is not None:
            self.ov.close()
            self.ov.deleteLater()
            self.ov = None
        if self in self.crew.games:
            self.crew.games.remove(self)

    def drop(self, s):
        if s in self.players:
            self.players.remove(s)
            s.game = None
            s.prop_override = None
            self.spot.pop(s, None)
            self.on_drop(s)
            if len(self.players) < self.min_p and not self.done:
                self.end()

    # ---- para subclases
    def setup(self):
        pass

    def begin(self):
        pass

    def play(self, s, dt):
        pass

    def play_pose(self, s):
        return pose_stand(s.t)

    def update(self, dt):
        pass

    def on_drop(self, s):
        pass

    def draw_overlay(self, p):
        pass


# ============================================================================
@game
class Parkour(Game):
    key, label = "parkour", "Parkour"
    min_p, max_p, span = 2, 4, 12.0
    TRICKS = [("mortal_adelante", 3), ("voltereta", 3), ("rueda", 2), ("superheroe", 1),
              ("barrida", 2), ("salto", 3)]

    def setup(self):
        L, Rb, _ = desktop_bounds()
        self.d = 1 if (Rb - self.cx) > (self.cx - L) else -1
        self.cx = clamp(self.cx, L + 2 * self.H, Rb - 2 * self.H)
        x0 = self.cx - self.d * 2 * self.H
        for i, s in enumerate(self.players):
            self.spot[s] = (x0 - self.d * i * 1.1 * self.H, self.d)
        self.leader = self.players[0]
        self.queue = []
        self.seen = {}
        self.trick_t = 1.2
        self.vaulted = {}

    def begin(self):
        self.dur = random.uniform(9, 14)

    def do_trick(self, s, key):
        if key == "salto":
            s.leap_h = 0.7
            self.run(s, "g_salto", 230)
        else:
            self.run(s, key)

    def play(self, s, dt):
        s.facing = self.d
        s.moving = s.step(210, dt)
        if not s.moving and s is self.leader:
            self.end(winners=self.players)
            return
        # cajas en el camino: ¡saltarlas!
        for it in self.crew.items:
            if it.key == "caja" and not it.dragging and 0 < (it.x - s.hx) * self.d < 0.9 * self.H \
                    and self.vaulted.get((s, it)) != int(self.t / 3):
                self.vaulted[(s, it)] = int(self.t / 3)
                s.leap_h = it.HH + 0.35
                self.run(s, "g_salto", 260)
                return
        if s is not self.leader:
            i = self.seen.get(s, 0)
            while i < len(self.queue) and (self.queue[i][0] - s.hx) * self.d <= 0:
                key = self.queue[i][1]
                i += 1
                self.seen[s] = i
                self.do_trick(s, key)
                return
            self.seen[s] = i

    def play_pose(self, s):
        return pose_walk(s.phase, amp=1.45, lean=15)

    def update(self, dt):
        if self.t > self.dur:
            self.end(winners=self.players)
            return
        self.trick_t -= dt
        ld = self.leader
        if self.trick_t <= 0 and self.active(ld):
            k, w = zip(*self.TRICKS)
            key = random.choices(k, w)[0]
            self.queue.append((ld.hx, key))
            self.do_trick(ld, key)
            self.trick_t = random.uniform(1.4, 2.4)

    def on_drop(self, s):
        if s is self.leader and self.players:
            self.leader = self.players[0]


# ============================================================================
def rope_path(a, b, mid_y):
    m = (a + b) * 0.5
    c = QPointF(m.x(), 2 * mid_y - m.y())
    path = QPainterPath(a)
    path.quadTo(c, b)
    return path


@game
class JumpRope(Game):
    key, label = "cuerda", "Saltar la cuerda"
    min_p, max_p, span, overlay = 3, 5, 4.0, True

    def setup(self):
        self.h1, self.h2 = self.players[0], self.players[1]
        self.jumpers = self.players[2:]
        self.spot = {self.h1: (self.gx(-1.4), 1), self.h2: (self.gx(1.4), -1)}
        n = len(self.jumpers)
        for i, s in enumerate(self.jumpers):
            self.spot[s] = (self.gx((i - (n - 1) / 2) * 0.45), random.choice((-1, 1)))
        self.phi = math.pi
        self.stopped = False

    def begin(self):
        self.dur = getattr(self, "dur", random.uniform(16, 24))
        self.stopped = False
        self.count = 0

    def play(self, s, dt):
        pass

    def play_pose(self, s):
        m = math.cos(self.phi)
        if s in (self.h1, self.h2):
            a = 75 + 35 * math.sin(self.phi) * (0 if self.stopped else 1)
            return S(uaF=a, faF=a + 10, lean=-4, thB=-14, thF=14)
        lift = 0.0 if self.stopped else 0.3 * max(0.0, m) ** 1.2
        k = lift / 0.3
        p = lerp_pose(S(uaB=-25, faB=10, uaF=25, faF=40), S(thB=25, shB=-20, thF=30, shF=-15,
                                                          uaB=-35, faB=20, uaF=35, faF=60), k)
        return W(p, lift=lift)

    def update(self, dt):
        if self.t > self.dur:
            self.end(winners=self.jumpers, losers=())
            return
        if self.stopped:
            return
        prev = self.phi
        self.phi += dt * 2 * math.pi * 0.85
        if int(prev / (2 * math.pi)) != int(self.phi / (2 * math.pi)):
            self.count += 1
            if self.count > 3 and self.jumpers and random.random() < 0.08:
                trip = random.choice(self.jumpers)
                self.stopped = True
                trip.say("¡Ay!", 1.0)
                trip.start_action("derribado", then=lambda s=trip: self.after_trip(s))

    def after_trip(self, s):
        if self.done or s.game is not self:
            s.resume()
            return
        s.set_state("game")
        old = self.h1
        self.players.remove(s)
        self.players.insert(0, s)
        if old in self.players:
            self.players.remove(old)
            self.players.append(old)
        self.relayout()

    def draw_overlay(self, p):
        if not (self.h1 in self.players and self.h2 in self.players):
            return
        a = QPointF(self.h1.hx, self.h1.hy) + self.h1.joints["haF"]
        b = QPointF(self.h2.hx, self.h2.hy) + self.h2.joints["haF"]
        g = self.ground
        if self.stopped or self.phase == "gather":
            mid = g - 0.03 * self.H
        else:
            m = (math.cos(self.phi) + 1) / 2
            mid = (g - 1.9 * self.H) + (g - 0.02 * self.H - (g - 1.9 * self.H)) * m
        p.setPen(QPen(QColor("#B91C1C"), 0.03 * self.H, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawPath(rope_path(a, b, mid))


# ============================================================================
def _measure_table(fn, steps=21):
    """Mide alturas de una familia de poses (en unidades de H)."""
    out = []
    for i in range(steps):
        k = i / (steps - 1)
        j = solve(fn(k), 1.0, 1)
        cy = contact(j, 1.0)
        top = min(min(pt.y() for pt in j.values()), j["head"].y() - 0.13)
        out.append((k, cy - top, j, cy))
    return out


LIMBO_DEEP = P(lean=-80, tilt=28, thB=88, shB=-35, thF=100, shF=-25, uaB=-140, faB=-150,
               uaF=-125, faF=-135)
LIMBO_UP = S(uaB=-30, faB=-20, uaF=30, faF=40)


def limbo_pose(k):
    return lerp_pose(LIMBO_UP, LIMBO_DEEP, k)


LIMBO_TABLE = [(k, h) for k, h, _, _ in _measure_table(limbo_pose)]


def hold_height(a):
    """Altura sobre el piso de la mano de enfrente con el brazo estirado a 'a' grados."""
    j = solve(S(uaF=a, faF=a), 1.0, 1)
    return contact(j, 1.0) - j["haF"].y()


HOLD_TABLE = [(a, hold_height(a)) for a in range(0, 181, 3)]


def angle_for_height(h):
    best = min(HOLD_TABLE, key=lambda e: abs(e[1] - h))
    return best[0]


@game
class Limbo(Game):
    key, label = "limbo", "Limbo"
    min_p, max_p, span, overlay = 3, 5, 7.0, True

    def setup(self):
        self.h1, self.h2 = self.players[0], self.players[1]
        if not hasattr(self, "dancers"):
            self.dancers = self.players[2:]
            self.start_dancers = len(self.dancers)
            self.flex = {s: random.uniform(0.6, 1.0) for s in self.dancers}
            self.bar = LIMBO_TABLE[7][1] + 0.02
            self.step_h = (self.bar - LIMBO_TABLE[-1][1]) / 4.0
            self.d = 1
            self.round = 1
        self.spot = {self.h1: (self.gx(-1.1), 1), self.h2: (self.gx(1.1), -1)}
        for i, s in enumerate(self.dancers):
            self.spot[s] = (self.gx(-self.d * (2.1 + i * 0.6)), self.d)
        self.st = {s: "queue" for s in self.dancers}
        self.wobble = 0.0

    def rel(self, s):
        return (s.hx - self.cx) * self.d / self.H

    def needed_k(self):
        for k, h in LIMBO_TABLE:
            if h <= self.bar - 0.04:
                return k
        return 1.01

    def play(self, s, dt):
        if s not in self.dancers:
            s.moving = False
            return
        st = self.st.get(s, "queue")
        if st == "queue":
            q = [x for x in self.dancers if self.st.get(x) == "queue"]
            i = q.index(s)
            going = [x for x in self.dancers if self.st.get(x) == "go"]
            if i == 0 and all(self.rel(x) > 0.2 for x in going) and abs(self.rel(s) + 2.1) < 0.3:
                self.st[s] = "go"
                return
            s.walk_to(self.gx(-self.d * (2.1 + i * 0.6)), dt, WALK_SPEED * 1.3)
            if not s.moving:
                s.facing = self.d
        elif st == "go":
            s.facing = self.d
            s.moving = s.step(75, dt)
            r = self.rel(s)
            if -0.35 < r < 0.1 and self.needed_k() > self.flex[s]:
                self.wobble = 1.0
                self.dancers.remove(s)
                self.st.pop(s, None)
                s.say("¡Ups!", 1.0)
                s.start_action("derribado", then=lambda s=s: self.out(s))
                return
            if r > 0.9:
                self.st[s] = "done"
        else:
            done = [x for x in self.dancers if self.st.get(x) == "done"]
            i = done.index(s)
            if s.walk_to(self.gx(self.d * (2.1 + i * 0.6)), dt, WALK_SPEED * 1.2) or not s.moving:
                s.facing = -self.d

    def out(self, s):
        if s in self.players:
            self.drop(s)
        s.start_action(random.choice(["reir", "frustrado"]))

    def play_pose(self, s):
        if s in (self.h1, self.h2):
            a = angle_for_height(self.bar)
            return S(uaF=a, faF=a, uaB=-10, faB=0, lean=-2)
        if self.st.get(s) == "go":
            r = self.rel(s) + 0.15
            ramp = 1.0 if abs(r) < 0.5 else smooth(1 - (abs(r) - 0.5) / 0.6)
            k = min(self.needed_k(), self.flex[s]) * ramp
            p = limbo_pose(k)
            sh = 8 * math.sin(s.t * 8)
            return W(p, thB=p["thB"] + sh, thF=p["thF"] - sh)
        if s.moving:
            return pose_walk(s.phase)
        return W(pose_stand(s.t), uaF=60 + 30 * math.sin(s.t * 6), faF=160, uaB=-60, faB=160)

    def update(self, dt):
        self.wobble = max(0.0, self.wobble - dt * 1.5)
        if not self.dancers or self.t > 75:
            self.end(winners=self.dancers)
            return
        if self.start_dancers > 1 and len(self.dancers) == 1:
            self.end(winners=self.dancers, losers=[])
            return
        if all(self.st.get(x) == "done" for x in self.dancers):
            done = [x for x in self.dancers]
            if all(not x.moving for x in done):
                self.round += 1
                if self.round > 6:
                    self.end(winners=self.dancers)
                    return
                self.bar -= self.step_h
                self.d *= -1
                for x in self.dancers:
                    self.st[x] = "queue"

    def on_drop(self, s):
        if s in (self.h1, self.h2):
            self.end()
        elif s in self.dancers:
            self.dancers.remove(s)
            self.st.pop(s, None)

    def draw_overlay(self, p):
        if self.done or self.h1 not in self.players or self.h2 not in self.players:
            return
        a = QPointF(self.h1.hx, self.h1.hy) + self.h1.joints["haF"]
        b = QPointF(self.h2.hx, self.h2.hy) + self.h2.joints["haF"]
        wob = math.sin(self.t * 30) * self.wobble * 0.08 * self.H
        p.setPen(QPen(QColor("#F59E0B"), 0.045 * self.H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(a + QPointF(-0.1 * self.H, wob), b + QPointF(0.1 * self.H, -wob))


# ============================================================================
class GBall:
    """Pelota de juego (béisbol), dibujada en la capa del juego."""

    def __init__(self, x, y):
        self.p = QPointF(x, y)
        self.v = QPointF(0, 0)
        self.held = None
        self.alive = True
        self.rest = False
        self.fade = 1.0

    def tick(self, dt, ground, x0, x1):
        if self.held is not None:
            s = self.held
            self.p = QPointF(s.hx, s.hy) + s.joints["haF"]
            return
        if self.rest:
            return
        self.v = QPointF(self.v.x(), self.v.y() + GRAVITY * dt)
        self.p = self.p + self.v * dt
        r = 0.05 * HEIGHT
        if self.p.x() < x0 + r or self.p.x() > x1 - r:
            self.v = QPointF(-self.v.x() * 0.5, self.v.y())
            self.p = QPointF(clamp(self.p.x(), x0 + r, x1 - r), self.p.y())
        if self.p.y() > ground - r:
            self.p = QPointF(self.p.x(), ground - r)
            if self.v.y() > 200:
                self.v = QPointF(self.v.x() * 0.7, -self.v.y() * 0.45)
            else:
                self.v = QPointF(self.v.x() * math.exp(-dt * 3), 0)
                if abs(self.v.x()) < 10:
                    self.rest = True

    def landing_x(self, ground):
        """Dónde va a caer (aprox.)."""
        x, y, vx, vy = self.p.x(), self.p.y(), self.v.x(), self.v.y()
        a = 0.5 * GRAVITY
        b, c = vy, y - ground
        disc = b * b - 4 * a * c
        if disc < 0:
            return x
        t = (-b + math.sqrt(disc)) / (2 * a)
        return x + vx * t


def ballistic(a, b, T):
    """Velocidad para ir de a a b en T segundos."""
    vx = (b.x() - a.x()) / T
    vy = (b.y() - a.y() - 0.5 * GRAVITY * T * T) / T
    return QPointF(vx, vy)


@game
class Baseball(Game):
    key, label = "beisbol", "Béisbol"
    min_p, max_p, span, overlay = 2, 4, 12.0, True

    def setup(self):
        if not hasattr(self, "d"):
            self.d = random.choice((-1, 1))
        self.batter, self.pitcher = self.players[0], self.players[1]
        self.fielders = self.players[2:]
        self.spot = {self.batter: (self.gx(-self.d * 3.5), self.d),
                     self.pitcher: (self.gx(-self.d * 0.5), -self.d)}
        for i, s in enumerate(self.fielders):
            self.spot[s] = (self.gx(self.d * (2.5 + 2.0 * i)), -self.d)
        self.batter.prop_override = "bat"
        for s in self.players[1:]:
            s.prop_override = None
        self.ball = None
        self.mode = "ready"
        self.wait = 1.5
        self.strikes = 0
        self.chaser = None
        self.swung = False

    def begin(self):
        self.dur = getattr(self, "dur", random.uniform(35, 50))
        self.ball = GBall(self.pitcher.hx, self.pitcher.hy)
        self.ball.held = self.pitcher
        self.mode, self.wait = "ready", 1.2

    def bounds(self):
        if self.ov is not None:
            return self.ov.x0, self.ov.x0 + self.ov.width()
        L, Rb, _ = desktop_bounds()
        return L, Rb

    # eventos de acciones
    def on_release(self, s):
        if self.ball is None or s is not self.pitcher:
            return
        self.ball.held = None
        b = self.batter
        target = QPointF(b.hx + self.d * 0.3 * self.H, b.hy - 0.15 * self.H)
        T = 0.75
        self.ball.v = ballistic(self.ball.p, target, T)
        self.ball.v = QPointF(self.ball.v.x(), self.ball.v.y() + random.uniform(-60, 60))
        self.mode = "pitch"
        self.swung = False

    def on_swing(self, s):
        if self.ball is None or self.mode != "pitch":
            return
        hand = QPointF(s.hx, s.hy) + s.joints["haF"]
        dist = math.hypot(self.ball.p.x() - hand.x() - self.d * 0.25 * self.H,
                          self.ball.p.y() - hand.y()) / self.H
        r = random.random()
        if dist < 0.7 and r < 0.55:
            self.ball.v = QPointF(self.d * random.uniform(450, 1000), -random.uniform(400, 950))
            self.mode = "hit"
            far = self.ball.landing_x(self.ground)
            last = max([abs(f.hx - s.hx) for f in self.fielders] + [abs(self.pitcher.hx - s.hx)])
            if abs(far - s.hx) > last + 3 * self.H:
                s.say("¡Jonrón!", 1.6)
            else:
                s.say("¡Toma!", 1.0)
            self.choose_chaser()
        elif dist < 0.7 and r < 0.7:
            self.ball.v = QPointF(-self.d * random.uniform(150, 300), -random.uniform(500, 700))
            self.mode = "dead"
            s.say("foul", 1.0)

    def on_throw(self, s):
        if self.ball is None or self.ball.held is not s:
            return
        self.ball.held = None
        tgt = QPointF(self.pitcher.hx, self.pitcher.hy) + self.pitcher.joints["haF"]
        T = clamp(abs(tgt.x() - self.ball.p.x()) / 650, 0.5, 1.2)
        self.ball.v = ballistic(self.ball.p, tgt, T)
        self.mode = "return"

    def choose_chaser(self):
        land = self.ball.landing_x(self.ground)
        cands = self.fielders or [self.pitcher]
        self.chaser = min(cands, key=lambda f: abs(f.hx - land))

    def play(self, s, dt):
        b = self.ball
        if b is None:
            return
        if s is self.chaser and self.mode in ("hit", "fetch"):
            tx = b.p.x() if b.rest or self.mode == "fetch" else b.landing_x(self.ground)
            x0, x1 = self.bounds()
            tx = clamp(tx, x0 + 0.5 * self.H, x1 - 0.5 * self.H)
            s.walk_to(tx, dt, RUN_SPEED * 1.1)
            hand = QPointF(s.hx, s.hy) + s.joints["haF"]
            near_hand = math.hypot(b.p.x() - hand.x(), b.p.y() - hand.y()) < 0.45 * self.H
            on_floor = b.p.y() > self.ground - 0.35 * self.H and abs(b.p.x() - s.hx) < 0.45 * self.H
            if near_hand or on_floor:
                in_air = b.p.y() < self.ground - 0.4 * self.H and not b.rest
                b.held, b.rest = s, False
                if in_air and self.mode == "hit":
                    s.say("¡Fuera!", 1.4)
                    self.out_or_strike(out=True)
                self.mode = "carry"
                self.chaser = None
                s.facing = sign(self.pitcher.hx - s.hx)
                self.run(s, "g_tirar")
            return
        if self.mode in ("ready", "pitch", "return", "dead") and s in self.spot and s is not self.batter:
            x, f = self.spot[s]
            if abs(x - s.hx) > 6:
                s.walk_to(x, dt, WALK_SPEED * 1.6)
            else:
                s.moving = False
                s.facing = f
        if s is self.batter:
            s.facing = self.d
            s.moving = False
            if self.mode == "pitch" and not self.swung and b.held is None:
                hand_x = s.hx + self.d * 0.3 * self.H
                if b.v.x() != 0:
                    tta = (hand_x - b.p.x()) / b.v.x()
                    if 0 < tta < 0.24:
                        self.swung = True
                        self.run(s, "g_batear")

    def out_or_strike(self, out=False):
        self.strikes = 3 if out else self.strikes + 1
        if self.strikes >= 3:
            self.strikes = 0
            self.pending_rotate = True

    def rotate(self):
        self.pending_rotate = False
        self.batter.prop_override = None
        old = self.players.pop(0)
        self.players.append(old)
        self.relayout()

    def play_pose(self, s):
        if s is self.batter:
            return W(BAT_READY, tilt=-4 + 2 * math.sin(s.t * 2))
        if s.moving:
            return pose_walk(s.phase, amp=1.4, lean=14)
        if s is self.pitcher and self.mode in ("return",):
            return W(REACH, lift=0)
        if s is self.chaser:
            return W(REACH, lift=0)
        return P(lean=30, thB=40, shB=-30, thF=50, shF=-20, uaB=40, faB=10, uaF=45, faF=15)

    def new_ball(self):
        self.ball = GBall(self.pitcher.hx, self.pitcher.hy)
        self.ball.held = self.pitcher
        self.chaser = None
        self.mode, self.wait = "ready", random.uniform(1.0, 2.0)

    def update(self, dt):
        b = self.ball
        if b is None:
            return
        x0, x1 = self.bounds()
        b.tick(dt, self.ground, x0, x1)
        # seguro anti-congelados: si una jugada se atora, pelota nueva al lanzador
        if self.mode != getattr(self, "_last_mode", None):
            self._last_mode, self.mode_t = self.mode, 0.0
        self.mode_t = getattr(self, "mode_t", 0.0) + dt
        if self.mode != "ready" and self.mode_t > 9.0:
            self.new_ball()
            return
        if self.mode == "carry" and b.held is not None and b.held.state == "game":
            self.run(b.held, "g_tirar")     # la iba a lanzar pero se interrumpió
        if self.t > self.dur and self.mode == "ready":
            self.end(winners=self.players)
            return
        if self.mode == "ready":
            if b.held is not self.pitcher:
                b.held = self.pitcher
            if getattr(self, "pending_rotate", False):
                self.rotate()
                return
            self.wait -= dt
            if self.wait <= 0 and self.active(self.pitcher) and self.active(self.batter):
                self.run(self.pitcher, "g_lanzar")
                self.wait = 99
        elif self.mode == "pitch":
            past = (b.p.x() - self.batter.hx) * self.d < -0.6 * self.H
            if past or b.rest:
                self.pitcher.say("¡Strike!", 1.2)
                self.out_or_strike()
                self.mode = "dead"
        elif self.mode == "dead":
            b.fade -= dt * 0.8
            if b.fade <= 0 or b.rest:
                self.new_ball()
        elif self.mode == "hit":
            if b.rest or (b.v.y() == 0 and b.p.y() >= self.ground - 0.1 * self.H):
                self.mode = "fetch"
            if self.chaser is None:
                self.choose_chaser()
        elif self.mode == "return":
            hand = QPointF(self.pitcher.hx, self.pitcher.hy) + self.pitcher.joints["haF"]
            if math.hypot(b.p.x() - hand.x(), b.p.y() - hand.y()) < 0.5 * self.H or b.rest:
                if b.rest:   # se le cayó: va por ella
                    self.chaser = self.pitcher
                    self.mode = "fetch"
                    return
                b.held = self.pitcher
                self.mode, self.wait = "ready", random.uniform(1.0, 2.0)
        elif self.mode == "fetch" and self.chaser is None:
            self.chaser = self.pitcher

    def play_fetch_pitcher(self):
        pass

    def on_drop(self, s):
        if s in (self.batter, self.pitcher) and len(self.players) >= 2:
            self.relayout()
            self.begin()
        if s is self.chaser:
            self.chaser = None

    def draw_overlay(self, p):
        b = self.ball
        if b is None:
            return
        r = 0.05 * self.H
        c = QColor(255, 255, 255, int(255 * clamp(b.fade, 0, 1)))
        p.setPen(QPen(QColor(60, 60, 60, c.alpha()), 1.2))
        p.setBrush(c)
        p.drawEllipse(b.p, r, r)
        p.setPen(QPen(QColor(220, 40, 40, c.alpha()), 1.0))
        p.drawArc(QRectF(b.p.x() - r * 1.6, b.p.y() - r, r * 1.2, r * 2), -60 * 16, 120 * 16)


# ============================================================================
@game
class PassBall(Game):
    key, label = "pelota", "Pasarse la pelota"
    min_p, max_p, span = 2, 4, 7.0
    weight = 14

    @classmethod
    def available(cls, crew):
        return any(it.key == "pelota" and not it.dragging for it in crew.items)

    def setup(self):
        balls = [it for it in self.crew.items if it.key == "pelota"]
        self.ball = min(balls, key=lambda b: abs(b.x - self.cx)) if balls else None
        if self.ball is None:
            return
        self.ball.release_users()
        n = len(self.players)
        L, Rb, _ = desktop_bounds()
        span = (n - 1) * 2.3
        cx = clamp(self.ball.x, L + (span / 2 + 1) * self.H, Rb - (span / 2 + 1) * self.H)
        self.cx = cx
        for i, s in enumerate(sorted(self.players, key=lambda s: s.hx)):
            x = cx + (i - (n - 1) / 2) * 2.3 * self.H
            self.spot[s] = (x, 1 if x < cx else -1)
        self.holder = None
        self.target = None
        self.fetcher = None
        self.hold_t = 0.0
        self.kick = False

    def begin(self):
        self.dur = random.uniform(16, 26)

    def play(self, s, dt):
        b = self.ball
        if b is None or b.dragging:
            return
        if s is self.fetcher:
            s.walk_to(b.x, dt, RUN_SPEED)
            if abs(b.x - s.hx) < 0.3 * self.H and b.y > self.ground - 0.4 * self.H:
                b.held_by = s
                self.holder, self.fetcher = s, None
                self.hold_t = random.uniform(0.6, 1.4)
            return
        if s is self.holder:
            s.moving = False
            if self.target is not None:
                s.facing = sign(self.target.hx - s.hx)
            return
        if s in self.spot and s is not self.target:
            x, f = self.spot[s]
            if abs(x - s.hx) > 6:
                s.walk_to(x, dt, WALK_SPEED * 1.5)
            else:
                s.moving = False
                s.facing = sign(b.x - s.hx) if abs(b.x - s.hx) > 5 else f
        if s is self.target:
            s.moving = False
            s.facing = sign(b.x - s.hx) if abs(b.x - s.hx) > 3 else s.facing
            if b.held_by is None:
                if self.kick:
                    near = abs(b.x - s.hx) < 0.35 * self.H
                else:
                    hand = QPointF(s.hx, s.hy) + (s.joints["haF"] + s.joints["haB"]) * 0.5
                    near = math.hypot(b.center().x() - hand.x(), b.center().y() - hand.y()) < 0.5 * self.H
                if near:
                    if random.random() < 0.85:
                        b.held_by = s
                        self.holder, self.target = s, None
                        self.hold_t = random.uniform(0.6, 1.5)
                    else:
                        s.say("¡Ups!", 1.0)
                        self.target = None
                        self.fetcher = s

    def play_pose(self, s):
        if s.moving:
            return pose_walk(s.phase, amp=1.3, lean=10)
        if s is self.holder:
            return S(uaF=70, faF=110, uaB=60, faB=100)
        if s is self.target and not self.kick:
            return S(uaF=110, faF=120, uaB=100, faB=115, lean=-4)
        return pose_stand(s.t)

    def on_throw(self, s):
        b = self.ball
        if b is None or b.held_by is not s or self.target is None:
            return
        b.held_by = None
        r = self.target
        if self.kick:
            T = clamp(abs(r.hx - b.x) / 380, 0.6, 1.6)
            b.vx = (r.hx - b.x) / T
            b.vy = -120
        else:
            tgt = QPointF(r.hx, r.hy) + (r.joints["haF"] + r.joints["haB"]) * 0.5
            T = clamp(abs(tgt.x() - b.x) / 520, 0.55, 1.3)
            v = ballistic(b.center(), tgt + QPointF(0, -0.1 * self.H), T)
            b.vx, b.vy = v.x(), v.y()
        b.on_ground = False
        self.holder = None

    def update(self, dt):
        b = self.ball
        if b is None or b not in self.crew.items or b.dragging:
            self.end()
            return
        if self.t > self.dur and self.holder is not None:
            b.held_by = None
            self.end(winners=self.players)
            return
        if self.holder is None and self.target is None and self.fetcher is None:
            self.fetcher = min(self.players, key=lambda s: abs(s.hx - b.x))
        if self.holder is not None and self.active(self.holder):
            self.hold_t -= dt
            if self.hold_t <= 0:
                others = [o for o in self.players if o is not self.holder]
                if others:
                    self.target = random.choice(others)
                    self.kick = random.random() < 0.3
                    self.holder.facing = sign(self.target.hx - self.holder.hx)
                    if self.kick:
                        b.held_by = None
                        b.set_center(QPointF(self.holder.hx + self.holder.facing * 0.25 * self.H,
                                             self.ground - b.RADIUS * self.H))
                        b.held_by = self.holder
                    self.run(self.holder, "g_patear" if self.kick else "g_tirar")
                    self.hold_t = 99
        # si la pelota quedó quieta y nadie la tiene, alguien va por ella
        if self.target is not None and b.held_by is None and b.on_ground:
            self.fetcher = self.target
            self.target = None

    def end(self, winners=(), losers=()):
        if self.ball is not None and self.ball.held_by in self.players:
            self.ball.held_by = None
        super().end(winners, losers)

    def on_drop(self, s):
        if self.ball is not None and self.ball.held_by is s:
            self.ball.held_by = None
        for attr in ("holder", "target", "fetcher"):
            if getattr(self, attr) is s:
                setattr(self, attr, None)


# ============================================================================
@game
class Race(Game):
    key, label = "carreras", "Carreras"
    min_p, max_p, span = 2, 4, 9.0

    def setup(self):
        L, Rb, _ = desktop_bounds()
        self.d = random.choice((-1, 1))
        for i, s in enumerate(self.players):
            self.spot[s] = (self.gx(-self.d * 4.0) - self.d * i * 0.12 * self.H, self.d)
        self.finish = self.gx(self.d * 4.0)
        self.speed = {s: random.uniform(320, 420) for s in self.players}
        self.order = []

    def begin(self):
        self.go = 2.8
        lead = self.players[0]
        for i, txt in enumerate(("3", "2", "1")):
            QTimer.singleShot(int((0.5 + i * 0.7) * 1000), lambda t=txt, s=lead: s.say(t, 0.6))
        QTimer.singleShot(int(2.6 * 1000), lambda s=lead: s.say("¡Ya!", 0.8))

    def play(self, s, dt):
        if self.t < self.go:
            s.moving = False
            return
        if s in self.order:
            s.moving = s.step(60, dt) if self.t - self.go < 0 else False
            return
        sp = self.speed[s] * (1 + 0.12 * math.sin(self.t * 2.3 + id(s) % 7))
        s.moving = s.step(sp, dt)
        if (s.hx - self.finish) * self.d >= 0 or not s.moving:
            self.order.append(s)

    def play_pose(self, s):
        if self.t < self.go:
            return P(lean=45, tilt=-20, thB=-30, shB=-70, thF=70, shF=-30, uaB=-20, faB=-10,
                     uaF=10, faF=0)
        if s.moving:
            return pose_walk(s.phase, amp=1.6, lean=24)
        return pose_stand(s.t)

    def update(self, dt):
        if len(self.order) >= len(self.players) or self.t > 14:
            win = self.order[:1]
            self.end(winners=win, losers=[s for s in self.players if s not in win])


# ============================================================================
RPS = ["Piedra", "Papel", "Tijera"]


@game
class RockPaperScissors(Game):
    key, label = "piedra", "Piedra, papel o tijera"
    min_p, max_p, span = 2, 2, 2.0

    def setup(self):
        a, b = self.players
        self.spot = {a: (self.gx(-0.45), 1), b: (self.gx(0.45), -1)}
        self.rounds = 0

    def begin(self):
        self.t0 = self.t
        self.shown = None
        self.rounds += 1
        for i, w in enumerate(("piedra…", "papel…", "¡tijera!")):
            for s in self.players:
                QTimer.singleShot(int((0.2 + 0.6 * i) * 1000), lambda s=s, w=w: s.say(w, 0.5))

    def play_pose(self, s):
        dt = self.t - self.t0
        if dt < 1.9:
            a = 100 + 35 * math.sin(dt * math.pi / 0.3)
            return S(uaF=a, faF=a + 20, lean=4)
        return S(uaF=88, faF=90, lean=6)

    def update(self, dt):
        el = self.t - self.t0
        if el > 2.0 and self.shown is None:
            self.shown = {s: random.randrange(3) for s in self.players}
            for s in self.players:
                s.say(RPS[self.shown[s]], 1.6)
        if el > 3.7 and self.shown is not None:
            a, b = self.players
            x, y = self.shown[a], self.shown[b]
            if x == y and self.rounds < 3:
                self.begin()
                return
            if x == y:
                self.end()
            elif (x - y) % 3 == 1:
                self.end(winners=[a], losers=[b])
            else:
                self.end(winners=[b], losers=[a])


# ============================================================================
@game
class TugOfWar(Game):
    key, label = "tira", "Tira y afloja"
    min_p, max_p, span, overlay = 2, 4, 5.0, True

    def setup(self):
        self.left = self.players[0::2]
        self.right = self.players[1::2]
        for i, s in enumerate(self.left):
            self.spot[s] = (self.gx(-0.8 - i * 0.7), 1)
        for i, s in enumerate(self.right):
            self.spot[s] = (self.gx(0.8 + i * 0.7), -1)
        self.pos = 0.0
        self.v = 0.0

    def begin(self):
        self.dur = random.uniform(9, 15)
        self.str = {s: random.uniform(0.8, 1.2) for s in self.players}

    def play(self, s, dt):
        s.moving = False

    def play_pose(self, s):
        j = 4 * math.sin(s.t * 13 + id(s) % 5)
        return P(lean=-28 + j, tilt=-10, thB=-14, shB=-14, thF=34, shF=22,
                 uaB=82, faB=86, uaF=86, faF=90)

    def update(self, dt):
        if self.phase != "play":
            return
        pull = sum(self.str[s] for s in self.right) - sum(self.str[s] for s in self.left)
        self.v += (pull * 0.15 + random.uniform(-1, 1) * 1.6) * dt
        self.v *= math.exp(-dt * 1.5)
        shift = self.v * dt * self.H
        self.pos += self.v * dt
        for s in self.players:
            if self.active(s):
                s.hx += shift
        if abs(self.pos) > 1.0 or self.t > self.dur:
            if abs(self.pos) <= 1.0:
                self.end()
                return
            win, lose = (self.right, self.left) if self.pos > 0 else (self.left, self.right)
            for s in lose:
                s.say("¡Waa!", 1.0)
            self.end(winners=win, losers=[])
            for s in lose:
                if s.grounded():
                    s.start_action("tropezar")

    def draw_overlay(self, p):
        if self.phase != "play" or self.done:
            return
        ps = sorted(self.players, key=lambda s: s.hx)
        if len(ps) < 2:
            return
        pts = [QPointF(s.hx, s.hy) + s.joints["haF"] for s in ps]
        p.setPen(QPen(QColor("#A16207"), 0.035 * self.H, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(pts[0] + QPointF(-0.4 * self.H, 0.05 * self.H), pts[-1] + QPointF(0.4 * self.H, 0.05 * self.H))
        mid = (pts[0] + pts[-1]) * 0.5
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#EF4444"))
        p.drawPolygon(QPolygonF([mid, mid + QPointF(0.06 * self.H, 0.22 * self.H),
                                 mid + QPointF(-0.06 * self.H, 0.22 * self.H)]))


# ============================================================================
LEAP_CROUCH = P(lean=55, tilt=-10, thB=60, shB=-50, thF=70, shF=-40, uaB=40, faB=10, uaF=45, faF=15)


@game
class Leapfrog(Game):
    key, label = "rana", "Salto de rana"
    min_p, max_p, span = 2, 4, 10.0

    def setup(self):
        L, Rb, _ = desktop_bounds()
        self.d = 1 if (Rb - self.cx) > (self.cx - L) else -1
        n = len(self.players)
        x0 = self.cx - self.d * 3 * self.H
        for i, s in enumerate(self.players):     # players[0] = el de hasta atrás
            self.spot[s] = (x0 + self.d * i * 1.3 * self.H, self.d)
        self.jumper = None

    def begin(self):
        self.dur = random.uniform(12, 18)
        self.next_jumper()

    def order(self):
        return sorted(self.players, key=lambda s: s.hx * self.d)

    def next_jumper(self):
        self.jumper = self.order()[0]
        self.hop()

    def hop(self):
        j = self.jumper
        if j is None or not self.active(j):
            return
        ahead = [s for s in self.order() if (s.hx - j.hx) * self.d > 0.2 * self.H and s is not j]
        if not ahead:
            self.jumper = None
            return
        o = ahead[0]
        tgt = o.hx + self.d * (0.65 if len(ahead) > 1 else 1.3) * self.H
        dist = abs(tgt - j.hx)
        j.facing = self.d
        j.leap_h = 0.8
        self.run(j, "g_salto", dist / 0.56)

    def play(self, s, dt):
        s.moving = False
        L, Rb, _ = desktop_bounds()
        if not (L + 1.5 * self.H < s.hx < Rb - 1.5 * self.H):
            self.end(winners=self.players)
            return
        if s is self.jumper:
            self.hop()
        elif self.jumper is None:
            self.next_jumper()

    def play_pose(self, s):
        if s is self.jumper:
            return CROUCH
        return LEAP_CROUCH

    def update(self, dt):
        if self.t > self.dur:
            self.end(winners=self.players)


# ============================================================================
@game
class Conga(Game):
    key, label = "conga", "Conga"
    min_p, max_p, span = 3, 6, 6.0

    def setup(self):
        self.leader = self.players[0]
        self.d = random.choice((-1, 1))
        for i, s in enumerate(self.players):
            self.spot[s] = (self.gx(-self.d * i * 0.6), self.d)
        self.trail = []

    def begin(self):
        self.dur = random.uniform(12, 18)
        self.turn_t = random.uniform(4, 7)

    def play(self, s, dt):
        if s is self.leader:
            s.moving = s.step(55, dt)
            if not s.moving:
                s.facing *= -1
            self.trail.append((self.t, s.hx, s.facing))
            if len(self.trail) > 2000:
                self.trail = self.trail[-1500:]
            return
        i = self.players.index(s)
        tt = self.t - i * 0.95
        if not self.trail or tt < self.trail[0][0]:
            s.moving = False
            return
        for k in range(len(self.trail) - 1, -1, -1):
            if self.trail[k][0] <= tt:
                _, x, f = self.trail[k]
                break
        s.moving = abs(x - s.hx) > 0.3
        s.phase = (s.phase + abs(x - s.hx) / (self.H * 1.05)) % 1.0
        s.hx, s.facing = x, f

    def play_pose(self, s):
        p = pose_walk(s.phase, amp=0.7, lean=4)
        beat = int(self.t * 2.2) % 4
        if beat == 3:
            p = W(p, thF=55, shF=45)
        if s is self.leader:
            return W(p, uaF=150 + 20 * math.sin(self.t * 9), faF=170, uaB=-20, faB=0)
        return W(p, uaF=80, faF=95, uaB=75, faB=92)

    def update(self, dt):
        if self.t > self.dur:
            self.end(winners=self.players)
            return
        self.turn_t -= dt
        if self.turn_t <= 0:
            self.leader.facing *= -1
            self.turn_t = random.uniform(4, 7)
        if int(self.t * 2.2) % 4 == 0 and self.leader.say_t <= 0:
            self.leader.say("♪", 0.4)

    def on_drop(self, s):
        if s is self.leader and self.players:
            self.leader = self.players[0]


# ============================================================================
CALL_SCRIPTS = [
    [(0, "¡Hola! ¿Qué haces?"), (1, "Nada, aquí en la pantalla"), (0, "jajaja"),
     (1, "¿Vamos a jugar?"), (0, "¡Sale!"), (1, "¡Bye!")],
    [(0, "¿Ya viste el cursor?"), (1, "¡Sí! Se mueve solo"), (0, "qué miedo"), (1, "jaja ¡bye!")],
    [(0, "¿Pedimos pizza?"), (1, "¡Obvio!"), (0, "¿Hawaiana?"), (1, "...no"), (0, "jaja ok, bye")],
    [(0, "Oye, ¿me prestas tu patineta?"), (1, "Mmm..."), (1, "bueno, va"), (0, "¡Gracias!")],
]


@game
class PhoneCall(Game):
    key, label = "llamada", "Llamada por celular"
    min_p, max_p, span, gather = 2, 2, 2.0, False
    weight = 12

    def setup(self):
        self.caller, self.callee = self.players
        self.caller.prop_override = "phone"
        self.script = random.choice(CALL_SCRIPTS)
        self.line = -1
        self.line_t = 0.0

    def begin(self):
        self.caller.say("Ring…", 1.0)

    def play(self, s, dt):
        s.moving = False

    def play_pose(self, s):
        t = self.t
        if s is self.caller:
            return W(PHONE_LOOK if t < 1.0 else PHONE_EAR, tilt=-6 + 3 * math.sin(s.t))
        if t < 1.0:
            return pose_stand(s.t)
        if t < 2.6:
            return W(PHONE_LOOK, tilt=-10, lift=0.04 * abs(math.sin(t * 14)))
        return W(PHONE_EAR, tilt=3 * math.sin(s.t * 1.3))

    def update(self, dt):
        t = self.t
        if t > 1.0 and self.callee.prop_override is None:
            self.callee.prop_override = "phone"
            self.callee.say("¡Ring! ¡Ring!", 1.5)
        if 2.6 <= t < 2.7 and self.line < 0:
            self.callee.say("¿Bueno?", 1.2)
            self.line, self.line_t = 0, 3.9
        if self.line >= 0 and t >= self.line_t:
            if self.line >= len(self.script):
                self.end()
                return
            who, txt = self.script[self.line]
            (self.caller if who == 0 else self.callee).say(txt, 1.6)
            self.line += 1
            self.line_t = t + 1.75


GAME_ORDER = ["parkour", "cuerda", "limbo", "beisbol", "pelota", "carreras", "piedra",
              "tira", "rana", "conga", "llamada"]
