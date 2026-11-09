"""Acciones animadas por keyframes (solos, pelea, pareja)."""
from .core import *  # noqa: F401,F403

# ----------------------------------------------------------------------------
# Acciones: animaciones por keyframes. pose(u, t, s) con u de 0 a 1.
# ----------------------------------------------------------------------------
class Action:
    def __init__(self, key, label, dur, pose, speed=0.0, events=(), say=(),
                 kind="solo", snap=40.0, lines=False, prop=None):
        self.key, self.label, self.dur, self.pose = key, label, dur, pose
        self.speed, self.events, self.say = speed, list(events), list(say)
        self.kind, self.snap, self.lines, self.prop = kind, snap, lines, prop

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



# ======================== CELULAR ===========================================
PHONE_LOOK = S(uaF=20, faF=150, uaB=10, faB=140, tilt=28, lean=4)
PHONE_EAR = S(uaF=140, faF=222, uaB=-10, faB=20, tilt=-6)


@action("celular", "Ver el celular", (6.0, 12.0), prop="phone",
        say=[(0.45, 0.55, "jaja")])
def _(u, t, s):
    return held(u, W(PHONE_LOOK, faF=150 + 4 * math.sin(t * 9)), 0.08)


@action("caminar_celular", "Caminar viendo el celular", (5.0, 9.0), prop="phone", speed=32)
def _(u, t, s):
    return W(pose_walk(s.phase, amp=0.6, lean=6), uaF=20, faF=150, uaB=10, faB=140, tilt=28)


@action("selfie", "Tomarse una selfie", 3.0, prop="phone",
        say=[(0.55, 0.75, "clic")])
def _(u, t, s):
    p = S(uaF=150, faF=150, uaB=-30, faB=60, tilt=-12, lean=-4)
    p2 = W(p, uaB=150, faB=175, tilt=-18)     # cambia de pose
    return kf(u, [(0, S()), (0.2, p), (0.5, p), (0.65, p2), (0.85, p2), (1, S())])


# ======================== CON OBJETOS =======================================
SEATED = P(lean=-6, thB=86, shB=4, thF=92, shF=-2, uaB=-20, faB=30, uaF=-10, faF=40)
CROSS_LEG = P(lean=-2, thB=85, shB=-80, thF=95, shF=-95, uaB=20, faB=80, uaF=25, faF=85)


@action("o_sentarse", "Sentarse", (8.0, 18.0), kind="item")
def _(u, t, s):
    return W(SEATED, tilt=-4 + 5 * math.sin(t * 0.5), lean=-8 + 2 * math.sin(t * 0.8))


@action("o_sentarse_cel", "Sentarse con el celular", (8.0, 16.0), kind="item", prop="phone",
        say=[(0.5, 0.58, "jaja")])
def _(u, t, s):
    return W(SEATED, uaF=20, faF=150, uaB=10, faB=140, tilt=28, lean=2)


@action("o_acostarse", "Acostarse", (10.0, 20.0), kind="item", say=[(0.15, 0.9, "Zzz")])
def _(u, t, s):
    return W(LIE, lean=2 * math.sin(t * 1.5), uaF=30, faF=60)


@action("o_comer", "Comer", (8.0, 14.0), kind="item", prop="sandwich",
        say=[(0.6, 0.7, "ñam")])
def _(u, t, s):
    bite = (math.sin(t * 1.6) + 1) / 2
    return W(SEATED, uaF=40 + 60 * bite, faF=120 + 70 * bite, tilt=8 - 10 * bite)


@action("o_comer_piso", "Comer pizza", (7.0, 12.0), kind="item", prop="slice",
        say=[(0.6, 0.7, "ñam")])
def _(u, t, s):
    bite = (math.sin(t * 1.6) + 1) / 2
    return W(CROSS_LEG, uaF=40 + 60 * bite, faF=120 + 70 * bite, tilt=8 - 10 * bite)


@action("o_trampolin", "Brincar en el trampolín", (6.0, 10.0), kind="item")
def _(u, t, s):
    ph = (t * 1.1) % 1.0
    n = int(t * 1.1)
    h = 4 * 1.3 * ph * (1 - ph)
    if n % 3 == 2:     # cada tercer brinco, un mortal
        p = W(BALL, rot=360 * smooth((ph - 0.15) / 0.7) * (1 if n % 2 else -1))
    elif ph < 0.12 or ph > 0.88:
        p = CROUCH
    else:
        p = W(STAR, lean=0) if n % 3 == 1 else S(uaB=160, faB=170, uaF=160, faF=170)
    return W(p, lift=h)


@action("o_calentarse", "Calentarse en la fogata", (8.0, 14.0), kind="item")
def _(u, t, s):
    return W(CROUCH, uaF=80, faF=95 + 6 * math.sin(t * 3), uaB=75, faB=90 - 6 * math.sin(t * 3),
             lean=18, tilt=-6)


@action("o_bombon", "Asar bombones", (8.0, 14.0), kind="item", prop="stick",
        say=[(0.85, 0.97, "ñam")])
def _(u, t, s):
    return W(CROSS_LEG, uaF=70, faF=80 + 4 * math.sin(t * 2), tilt=6)


@action("o_tele", "Ver la tele", (10.0, 20.0), kind="item",
        say=[(0.3, 0.36, "jaja"), (0.7, 0.75, "¡No!")])
def _(u, t, s):
    return W(CROSS_LEG, tilt=-4 + 3 * math.sin(t * 0.7))


@action("o_pesas", "Levantar pesas", (5.0, 9.0), kind="item", prop="dumbbells",
        say=[(0.4, 0.55, "¡uff!")])
def _(u, t, s):
    k = (math.sin(t * 3) + 1) / 2
    if int(t / 4) % 2:   # press arriba
        p = S(uaF=110 + 60 * k, faF=190 - 10 * k, uaB=-110 - 60 * k, faB=-190 + 10 * k, thB=-12, thF=12)
    else:                # curl
        p = S(uaF=5, faF=20 + 140 * k, uaB=0, faB=15 + 140 * k, thB=-12, thF=12, lean=-3)
    return held(u, p, 0.08)


@action("o_dominadas", "Hacer dominadas", (5.0, 9.0), kind="item", say=[(0.5, 0.6, "¡uff!")])
def _(u, t, s):
    k = (math.sin(t * 2.6) + 1) / 2
    th = 62 * k
    return P(uaF=180 - th, faF=180 + th, uaB=180 - th, faB=180 + th, thB=-6, shB=-20,
             thF=10, shF=-15, tilt=-10 + 8 * k, lift=0.18 * k)


@action("o_patineta", "Andar en patineta", (6.0, 11.0), kind="item", speed=150,
        events=[(0.3, lambda s: s.ollie()), (0.65, lambda s: s.ollie())])
def _(u, t, s):
    p = P(lean=4, tilt=-4, thB=-20, shB=-25, thF=22, shF=18, uaB=-80, faB=-95, uaF=80, faF=95)
    if s.ollie_t > 0:
        k = s.ollie_t / 0.5
        p = W(CROUCH, uaB=-90, uaF=90, lift=arc(1 - k, 0, 1, 0.45))
    return p


@action("o_regar", "Regar la planta", (4.0, 6.0), kind="item", prop="can")
def _(u, t, s):
    return held(u, S(uaF=75, faF=60, uaB=-10, faB=10, tilt=12, lean=4), 0.12)


@action("o_leer", "Leer", (8.0, 16.0), kind="item", prop="book")
def _(u, t, s):
    return W(CROSS_LEG, uaF=40, faF=130, uaB=35, faB=125, tilt=20 + 3 * math.sin(t * 0.4))


@action("o_guitarra", "Tocar la guitarra", (7.0, 12.0), kind="item", prop="guitar",
        say=[(0.1, 0.9, "♪")])
def _(u, t, s):
    return W(CROSS_LEG, uaF=70, faF=40, uaB=30, faB=80 + 16 * math.sin(t * 20),
             tilt=-6 + 6 * math.sin(t * 4))


@action("o_patear", "Patear la pelota", 0.9, kind="item",
        events=[(0.5, lambda s: s.kick_item())])
def _(u, t, s):
    return kf(u, [(0, S()), (0.35, S(thF=-35, shF=-55, lean=-6, uaB=30, uaF=-30)),
                  (0.5, S(thF=70, shF=75, lean=-12, uaB=50, uaF=-50)), (1, S())])


# ======================== PARA JUEGOS =======================================
def game_event(name):
    return lambda s: s.game and getattr(s.game, name)(s)


@action("g_lanzar", "Lanzar (béisbol)", 1.0, kind="game", events=[(0.62, game_event("on_release"))])
def _(u, t, s):
    wind = P(lean=-10, tilt=-6, thB=-10, shB=-10, thF=95, shF=40, uaB=-120, faB=-150, uaF=60, faF=100)
    rel = P(lean=25, tilt=6, thB=-30, shB=-30, thF=35, shF=15, uaB=-40, faB=-10, uaF=120, faF=95)
    return kf(u, [(0, S()), (0.4, wind), (0.62, rel), (0.85, rel), (1, S())])


BAT_READY = P(lean=4, thB=-22, shB=-22, thF=22, shF=12, uaF=40, faF=200, uaB=50, faB=190, tilt=-4)
BAT_SWING = P(lean=12, tilt=6, thB=-24, shB=-24, thF=26, shF=14, uaF=80, faF=90, uaB=75, faB=88)


@action("g_batear", "Batear", 0.55, kind="game", prop="bat", snap=60,
        events=[(0.4, game_event("on_swing"))])
def _(u, t, s):
    follow = W(BAT_SWING, uaF=130, faF=20, uaB=125, faB=15, lean=6)
    return kf(u, [(0, BAT_READY), (0.4, BAT_SWING), (0.65, follow), (1, BAT_READY)])


@action("g_tirar", "Lanzar la pelota", 0.6, kind="game", events=[(0.5, game_event("on_throw"))])
def _(u, t, s):
    back = S(uaF=-110, faF=-150, lean=-8, thF=20, thB=-15)
    fwd = S(uaF=120, faF=100, lean=12, thF=25, thB=-20)
    return kf(u, [(0, S()), (0.3, back), (0.5, fwd), (0.75, fwd), (1, S())])


@action("g_patear", "Pase con el pie", 0.7, kind="game", events=[(0.5, game_event("on_throw"))])
def _(u, t, s):
    return kf(u, [(0, S()), (0.35, S(thF=-35, shF=-55, lean=-6, uaB=30, uaF=-30)),
                  (0.5, S(thF=55, shF=55, lean=-8, uaB=40, uaF=-40)), (1, S())])


@action("g_salto", "Salto", 0.7, kind="game", lines=True, speed=window_speed(1.0, 0.1, 0.9))
def _(u, t, s):
    p = kf(u, [(0, CROUCH), (0.2, W(TUCK, uaB=150, uaF=160)), (0.8, TUCK), (1, CROUCH)])
    p["lift"] = arc(u, 0.1, 0.92, s.leap_h)
    return p


SOLO += ["celular", "celular", "caminar_celular", "selfie"]
