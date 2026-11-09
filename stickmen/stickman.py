"""Un stickman = una ventanita transparente que se mueve por la pantalla."""
from .core import *  # noqa: F401,F403
from .actions import (ACTIONS, SOLO, SOCIAL, FIGHT_CLOSE, FIGHT_FAR, pose_stand, pose_walk,
                      pose_wave, pose_watch, pose_sit, pose_guard, pose_flail, pose_dangle,
                      CROUCH, TUCK, REACH, FALL, lerp_pose)
from .draw import draw_stickman, draw_impact, draw_bubble, draw_speed_lines, bubble_top
from .objects import Ball


class Stickman(QWidget):
    GROUNDED = ("walk", "run", "sprint", "idle", "wave", "sit", "greet", "crouch", "land",
                "watch", "chase", "fight", "act", "tag_it", "tag_run", "approach", "wait",
                "goto", "game")
    TIMERLESS = ("fight", "chase", "act", "tag_it", "tag_run", "approach", "goto", "game")
    MOVING = ("walk", "run", "sprint", "chase", "fight", "act", "tag_it", "tag_run",
              "approach", "goto", "game")
    CALM = ("walk", "idle", "run")
    FREE = ("walk", "idle", "run", "sit", "wave")

    def __init__(self, crew, spec, x, y):
        flags = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
                 Qt.NoDropShadowWindowHint | Qt.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)

        self.crew, self.H = crew, HEIGHT
        self.set_spec(spec)
        self.resize(int(self.H * 2.7), int(self.H * 2.7))
        self.ox = self.oy = self.H * 1.35     # la cadera queda al centro de la ventana

        self.hx, self.hy = float(x), float(y)
        self.vx = self.vy = 0.0
        self.facing = random.choice((-1, 1))
        self.t = random.random() * 10
        self.phase = 0.0
        self.pose = dict(FALL)
        self.joints = solve(self.pose, self.H, self.facing, self.R)
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
        self.act_speed_mul = 1.0
        self.kip = False
        self.leap_h = 0.7
        self.ollie_t = 0.0

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

        # objetos y juegos
        self.item = None
        self.slot = None
        self.goto_t = 0.0
        self.blend_t = 0.0
        self.game = None
        self.prop_override = None

        # arrastre
        self.dragging = False
        self.grab = QPointF()
        self.press_pos = None
        self.drag_dist = 0.0
        self.svx = self.svy = 0.0

    def set_spec(self, spec):
        self.spec = dict(spec)
        self.R = head_radius(self.spec, HEIGHT)

    # ---------------- utilidades ----------------
    def set_state(self, s, dur=0.0):
        if s != "act":
            self.act = None
        self.state, self.timer = s, dur

    def grounded(self):
        return self.state in self.GROUNDED

    def busy(self):
        return (self.partner is not None or self.opponent is not None or self.game is not None
                or self.item is not None)

    def is_free(self):
        return self.state in self.FREE and not self.busy() and not self.dragging

    def say(self, text, dur=1.2):
        self.say_text, self.say_t = text, dur

    @property
    def prop(self):
        if self.prop_override:
            return self.prop_override
        if self.state == "act" and self.act is not None:
            return self.act.prop
        return None

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

    def walk_to(self, x, dt, speed=None):
        """Camina hacia x. True cuando ya llegó."""
        dx = x - self.hx
        if abs(dx) < 4:
            self.moving = False
            return True
        self.facing = sign(dx)
        sp = min(speed or WALK_SPEED, abs(dx) / max(dt, 1e-3))
        self.moving = self.step(sp, dt)
        return not self.moving and abs(dx) < self.H

    # ---------------- acciones ----------------
    def start_action(self, key, then=None):
        a = ACTIONS[key]
        self.set_state("act")
        self.act = a
        self.act_u = -1.0
        self.act_el = 0.0
        self.act_dur = a.duration()
        self.act_next = then
        self.act_speed_mul = 1.0
        self.kip = random.random() < 0.35

    def update_act(self, dt):
        a = self.act
        self.act_el += dt
        u = min(1.0, self.act_el / self.act_dur)
        sp = a.speed_at(u) * self.act_speed_mul
        if self.item is not None and self.slot is not None and not self.slot.ride:
            self.hx = self.item.x + self.slot.dx * self.H     # sigue pegado al objeto
        elif sp:
            if not self.step(sp, dt) and a.kind == "item":
                self.facing *= -1
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

    def back_to_game(self):
        if self.game is not None:
            self.set_state("game")
        else:
            self.resume()

    # ---------------- comportamiento ----------------
    def decide(self):
        a = ACTIVIDAD
        items = [it for it in self.crew.items if it.usable() and it.free_slots()
                 and not it.dragging and not it.hidden]
        opts = [("walk", 40), ("idle", 22), ("sit", 8),
                ("action", 22 * a), ("watch", 3 * a), ("run", 4 * a), ("jump", 2 * a), ("wave", 2 * a),
                ("item", (20 if items else 0) * a)]
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
        elif s == "item":
            ws = [1.0 / (1 + abs(it.x - self.hx) / (6 * self.H)) for it in items]
            self.go_use(random.choices(items, ws)[0])
        else:
            self.start_action(random.choice(SOLO))

    def resume(self):
        """Qué hacer al terminar una acción o al aterrizar."""
        if self.game is not None:
            self.set_state("game")
        elif self.opponent is not None and self.opponent in self.crew.members and self.fight_t > 0:
            self.set_state("fight")
        elif self.chase_t > 0:
            self.set_state("chase")
        else:
            self.opponent = None
            self.fight_t = 0.0
            self.decide()

    def leave_all(self):
        self.leave_partner()
        self.leave_item()
        if self.game is not None:
            self.game.drop(self)
        if self.opponent is not None:
            o = self.opponent
            self.opponent = None
            self.fight_t = 0.0
            if o.opponent is self:
                o.opponent, o.fight_t = None, 0.0
                if o.state == "fight":
                    o.decide()

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

    # ---------------- objetos ----------------
    def go_use(self, item, slot=None):
        free = item.free_slots()
        if not free:
            return
        slot = slot or min(free, key=lambda sl: abs(item.x + sl.dx * self.H - self.hx))
        if isinstance(item, Ball):
            side = sign(self.hx - item.x)
            slot.dx, slot.face = side * 0.32, -side
        slot.user = self
        self.item, self.slot = item, slot
        self.goto_t = 12.0
        self.set_state("goto")

    def update_goto(self, dt):
        it, sl = self.item, self.slot
        if it is None or it not in self.crew.items or it.dragging:
            self.leave_item()
            self.decide()
            return
        self.goto_t -= dt
        tx = it.x + sl.dx * self.H
        far = abs(tx - self.hx) > 5 * self.H
        arrived = self.walk_to(tx, dt, RUN_SPEED if far else WALK_SPEED * 1.3)
        if abs(tx - self.hx) < 4 or arrived or self.goto_t <= 0:
            if abs(tx - self.hx) > self.H:
                self.leave_item()
                self.decide()
                return
            self.hx = tx
            self.facing = sl.face if sl.face else random.choice((-1, 1))
            if sl.hide:
                it.hidden = True
            self.blend_t = 0.35
            self.raise_()
            self.start_action(random.choice(sl.actions), then=self.done_item)

    def done_item(self):
        it, sl = self.item, self.slot
        if it is not None:
            it.on_used(self, sl)
        self.leave_item()
        self.resume()

    def leave_item(self):
        it, sl = self.item, self.slot
        self.item = self.slot = None
        if sl is not None and sl.user is self:
            sl.user = None
        if it is not None:
            if sl is not None and sl.hide:
                it.hidden = False
                it.x = self.hx
                it.on_ground = False
                it.y = min(it.y, self.hy)
            self.blend_t = 0.35

    def kick_from_item(self):
        """El usuario movió el objeto: se cae de él."""
        was_using = self.state == "act" and self.item is not None
        self.leave_item()
        if was_using:
            self.vx, self.vy, self.thrown = 0.0, 0.0, False
            self.set_state("air")
        elif self.state == "goto":
            self.decide()

    def kick_item(self):
        it = self.item
        if it is not None:
            it.vx = self.facing * random.uniform(380, 700)
            it.vy = -random.uniform(250, 650)
            it.on_ground = False
            self.fx_t, self.fx_scale = 0.18, 0.6
            self.fx_pt = QPointF(self.joints["ftF"])

    def ollie(self):
        self.ollie_t = 0.5

    # ---------------- juegos ----------------
    def join_game(self, g):
        self.leave_partner()
        self.leave_item()
        self.chase_t = 0.0
        self.game = g
        self.set_state("game")

    # ---------------- pelea ----------------
    def start_fight(self, other):
        for m in (self, other):
            m.leave_partner()
            m.leave_item()
            if m.game is not None:
                m.game.drop(m)
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
        for m in (self, other):
            m.leave_partner()
            m.leave_item()
            if m.game is not None:
                m.game.drop(m)
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
        for m in (self, other):
            m.leave_partner()
            m.leave_item()
            if m.game is not None:
                m.game.drop(m)
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
        if s == "game" and self.game is not None:
            return self.game.pose(self)
        if s in ("walk", "approach"):
            return pose_walk(self.phase)
        if s == "goto":
            far = self.item is not None and abs(self.item.x - self.hx) > 5 * self.H
            return pose_walk(self.phase, amp=1.45 if far else 1.0, lean=15 if far else 5) \
                if self.moving else pose_stand(t)
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
        self.ollie_t = max(0.0, self.ollie_t - dt)
        self.alert_t = max(0.0, self.alert_t - dt)
        self.fx_t = max(0.0, self.fx_t - dt)
        self.say_t = max(0.0, self.say_t - dt)
        if self.fight_t > 0:
            self.fight_t -= dt
        if self.chase_t > 0:
            self.chase_t -= dt

        self.blink_in -= dt
        if self.blink_in <= 0:
            self.blink_t, self.blink_in = 0.12, random.uniform(2, 6)
        self.blink_t = max(0.0, self.blink_t - dt)

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
            elif s == "goto":
                self.update_goto(dt)
            elif s == "game":
                if self.game is None:
                    self.decide()
                else:
                    self.game.control(self, dt)
            elif s == "wait":
                p = self.partner
                if p is None or p not in self.crew.members:
                    self.partner = None
                    self.decide()
                else:
                    self.facing = sign(p.hx - self.hx)

            if (self.state in ("walk", "idle", "sit") and not self.busy()
                    and random.random() < dt * ACTIVIDAD / SPRINT_CADA):
                self.sprint()

            if self.state not in self.TIMERLESS and self.state in self.GROUNDED and self.timer <= 0:
                self.on_timer_end()

        # suavizado de pose
        if self.state != "act":
            self.pose["rot"] = wrap_deg(self.pose["rot"])
        speed = self.act.snap if (self.state == "act" and self.act) else 22
        k = 1 - math.exp(-dt * speed)
        self.pose = lerp_pose(self.pose, self.target_pose(), k)
        self.joints = solve(self.pose, self.H, self.facing, self.R)

        # pegar al piso (o al objeto)
        if self.state in self.GROUNDED:
            g = ground_at(self.hx) or self.last_ground
            dropped = g > self.last_ground + 3
            self.last_ground = g
            cy = contact(self.joints, self.H, self.R)
            lift = self.pose["lift"] * self.H
            if dropped and self.state in self.MOVING and self.item is None:
                self.thrown = False
                self.vx, self.vy = self.facing * 40, 0.0
                self.set_state("air")
                return
            sl = self.slot if (self.item is not None and self.state == "act") else None
            if sl is not None and sl.seat is not None:
                target = g - sl.seat * self.H - lift
            elif sl is not None:
                target = g - sl.floor * self.H - cy - lift
            else:
                target = g - cy - lift
            if self.blend_t > 0:
                self.blend_t -= dt
                self.hy += (target - self.hy) * min(1.0, dt * 14)
            else:
                self.hy = target

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
            self.set_state("idle", random.uniform(1.0, 2.5))
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
            return
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
            self.facing *= -1
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
        cy = contact(self.joints, self.H, self.R)
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
        self.setVisible(self.crew.visible)
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
                      self.blink_t > 0, self.look, self.prop, self.R)
        if self.fx_t > 0:
            draw_impact(p, self.fx_pt, self.H, self.fx_t / 0.25, self.fx_scale)
        text = self.bubble_text()
        if text:
            c = QPointF(j["head"].x(), bubble_top(j, self.H, self.spec, self.R))
            draw_bubble(p, c, self.H, text)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.ox, self.oy)
        j = self.joints
        xs = [pt.x() for pt in j.values()]
        ys = [pt.y() for pt in j.values()] + [j["head"].y() - self.R]
        pad = self.H * 0.16
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 1))   # área casi invisible para poder agarrarlo
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
                self.leave_item()
                if self.game is not None:
                    self.game.drop(self)
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
        elif self.grounded() and not self.busy():
            r = random.random()
            if r < 0.4:
                self.set_state("wave", 1.5)
            elif r < 0.7:
                self.jump()
            else:
                self.start_action(random.choice(["reir", "rascarse", "celebrar", "mortal_atras"]))

    def contextMenuEvent(self, e):
        self.crew.stickman_menu(self, e.globalPos())
