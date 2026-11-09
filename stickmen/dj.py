"""Escenario de DJ al aire libre: reproduce música al azar de tu PC y arma concierto."""
import os

from .core import *  # noqa: F401,F403
from .i18n import tr
from .objects import Slot, item_type
from .rooms import Room
from .games import Game, game, GAME_ORDER
from .actions import action, held, S, W, P, pose_walk, pose_stand
from .projector import PhotoLibrary
from PySide6.QtCore import QStandardPaths, QUrl, QFileInfo
from PySide6.QtGui import QLinearGradient

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaMetaData
    HAVE_AUDIO = True
except Exception:          # sin QtMultimedia el escenario funciona, pero en silencio
    HAVE_AUDIO = False

AUDIO_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".opus"}
MUSIC = PhotoLibrary(AUDIO_EXT, (QStandardPaths.MusicLocation, QStandardPaths.DownloadLocation,
                                 QStandardPaths.DesktopLocation), min_size=150000, small_ok=())
BPM = 124.0


_PROBE = None


def audio_probe():
    """Prueba el audio en un proceso aparte: si truena ahí, no tumba al programa."""
    global _PROBE
    if _PROBE is None:
        import subprocess
        import sys as _sys
        code = ("from PySide6.QtCore import QCoreApplication\n"
                "from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer\n"
                "a=QCoreApplication([]); o=QAudioOutput(); m=QMediaPlayer(); m.setAudioOutput(o); print('ok')")
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = 0x08000000      # sin ventana de consola
        try:
            r = subprocess.run([_sys.executable, "-c", code], capture_output=True, text=True, timeout=20, **kw)
            _PROBE = r.returncode == 0 and "ok" in r.stdout
        except Exception:
            _PROBE = False
    return _PROBE


class Player:
    """Un solo reproductor para todo el programa."""

    def __init__(self):
        self.mp = None
        self.out = None
        self.path = None
        self.title = ""
        self.playing = False
        self.volume = 0.6
        self.history = []
        self.fails = 0

    def ensure(self):
        global HAVE_AUDIO
        if not HAVE_AUDIO or self.mp is not None:
            return HAVE_AUDIO
        if not audio_probe():
            HAVE_AUDIO = False
            return False
        self.mp = QMediaPlayer()
        self.out = QAudioOutput()
        self.out.setVolume(self.volume)
        self.mp.setAudioOutput(self.out)
        self.mp.mediaStatusChanged.connect(self.on_status)
        self.mp.errorOccurred.connect(lambda *a: self.on_error())
        self.mp.metaDataChanged.connect(self.on_meta)
        return True

    def on_status(self, st):
        if st == QMediaPlayer.EndOfMedia and self.playing:
            self.next()
        elif st == QMediaPlayer.LoadedMedia:
            self.fails = 0

    def on_error(self):
        if self.playing and self.fails < 5:
            self.fails += 1
            self.next()

    def on_meta(self):
        try:
            md = self.mp.metaData()
            t = md.stringValue(QMediaMetaData.Title)
            a = md.stringValue(QMediaMetaData.ContributingArtist) or md.stringValue(QMediaMetaData.AlbumArtist)
            if t:
                self.title = f"{a} – {t}" if a else t
        except Exception:
            pass

    def play(self):
        if not self.ensure():
            self.title = tr("(sin audio en este equipo)")
            self.playing = True
            return
        if self.path is None:
            self.next()
            return
        self.mp.play()
        self.playing = True

    def pause(self):
        if self.mp is not None:
            self.mp.pause()
        self.playing = False

    def toggle(self):
        self.pause() if self.playing else self.play()

    def stop(self):
        if self.mp is not None:
            self.mp.stop()
        self.playing = False

    def next(self):
        if not self.ensure():
            return
        files = MUSIC.files
        if not files:
            self.title = tr("No encontré música (elige una carpeta)")
            self.playing = False
            return
        choices = [f for f in files if f not in self.history[-10:]] or files
        self.path = random.choice(choices)
        self.history.append(self.path)
        self.title = QFileInfo(self.path).completeBaseName()
        self.mp.setSource(QUrl.fromLocalFile(self.path))
        self.mp.play()
        self.playing = True

    def set_volume(self, v):
        self.volume = clamp(v, 0.0, 1.0)
        v = self.volume
        if self.out is not None:
            self.out.setVolume(v)

    def position(self):
        if self.mp is None:
            return 0, 0
        return self.mp.position() / 1000.0, max(0, self.mp.duration()) / 1000.0


PLAYER = Player()


def beat(t):
    """Pulso de 0 a 1 que cae en cada golpe."""
    ph = (t * BPM / 60.0) % 1.0
    return max(0.0, 1.0 - ph * 3.0)


# ============================================================================
@action("o_dj", "Ser el DJ", (40.0, 70.0), kind="item", say=[(0.1, 0.18, "¡Arriba las manos!"),
                                                           (0.6, 0.66, "¡Eso!")])
def _(u, t, s):
    b = beat(s.crew.time)
    k = math.sin(t * 9)
    if int(t / 4) % 3 == 2:       # mano arriba
        return S(uaF=165, faF=175 + 10 * k, uaB=70, faB=80 + 15 * k, tilt=-8 + 6 * b, lean=4)
    return S(uaF=75 + 6 * k, faF=78 + 12 * k, uaB=70, faB=80 - 10 * k, tilt=8 * b + 4, lean=8,
             thF=10 + 6 * b, thB=-10)


@item_type
class DJStage(Room):
    key, label, W, HH = "escenario", "Escenario de DJ", 5.2, 3.1
    walls = False
    FLOOR = 0.5            # el escenario está elevado
    layer = 0

    def make_slots(self):
        return [Slot(-0.15, 1, "o_dj", floor=self.FLOOR)]

    def extra_tick(self, dt):
        # si suena música y no hay DJ, llama a alguien
        if PLAYER.playing and self.slots[0].user is None and not self.dragging:
            self.recruit_t = getattr(self, "recruit_t", 0.0) - dt
            if self.recruit_t <= 0:
                self.recruit_t = 3.0
                cands = [m for m in self.crew.members if m.grounded() and not m.dragging
                         and (m.game is None or m.game.key == "concierto") and m.item is None]
                if cands:
                    dj_ = min(cands, key=lambda m: abs(m.hx - self.x))
                    dj_.leave_all()
                    dj_.go_use(self, self.slots[0])
        dj_ready = self.slots[0].user is not None or len(self.crew.members) <= 1
        if PLAYER.playing and dj_ready and not any(g.key == "concierto" for g in self.crew.games):
            self.concert_t = getattr(self, "concert_t", 0.0) - dt
            if self.concert_t <= 0:
                self.concert_t = 4.0
                self.crew.start_game("concierto", force=True)

    def save_state(self):
        return {"vol": PLAYER.volume}

    def load_state(self, d):
        PLAYER.set_volume(float(d.get("vol", PLAYER.volume)))

    def extra_menu(self, menu):
        add_music_controls(menu)

    def draw(self, p):
        H, t = self.H, self.crew.time
        w2, top = self.W / 2 * H, self.HH * H
        on = PLAYER.playing
        b = beat(t) if on else 0.0
        # bocinas a los lados (en el piso)
        for sx in (-1, 1):
            x = sx * (w2 - 0.32 * H)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#111827"))
            p.drawRoundedRect(QRectF(x - 0.32 * H, -1.5 * H, 0.64 * H, 1.5 * H), 5, 5)
            for y, r in ((-1.15, 0.16), (-0.5, 0.24)):
                p.setBrush(QColor("#374151"))
                rr = (r + 0.03 * b) * H
                p.drawEllipse(QPointF(x, y * H), rr, rr)
                p.setBrush(QColor("#0B0F19"))
                p.drawEllipse(QPointF(x, y * H), rr * 0.45, rr * 0.45)
        # plataforma
        fl = self.FLOOR * H
        sw = w2 - 0.7 * H
        p.setBrush(QColor("#1F2937"))
        p.drawRect(QRectF(-sw, -fl, 2 * sw, fl))
        p.setBrush(QColor("#4B5563"))
        p.drawRect(QRectF(-sw, -fl, 2 * sw, 0.06 * H))
        # estructura (truss)
        p.setPen(QPen(QColor("#9CA3AF"), 0.05 * H, Qt.SolidLine, Qt.RoundCap))
        for sx in (-1, 1):
            p.drawLine(QPointF(sx * (sw - 0.05 * H), -fl), QPointF(sx * (sw - 0.05 * H), -top))
        p.drawLine(QPointF(-sw, -top), QPointF(sw, -top))
        p.setPen(QPen(QColor("#6B7280"), 0.015 * H))
        for i in range(12):
            x0 = -sw + i * 2 * sw / 12
            p.drawLine(QPointF(x0, -top), QPointF(x0 + sw / 6, -top + 0.12 * H))
        # pantalla LED
        scr = QRectF(-1.25 * H, -2.65 * H, 2.5 * H, 1.15 * H)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#030712"))
        p.drawRoundedRect(scr.adjusted(-4, -4, 4, 4), 4, 4)
        if on:
            g = QLinearGradient(scr.topLeft(), scr.bottomRight())
            g.setColorAt(0, QColor.fromHsvF((t * 0.05) % 1, 0.8, 0.35))
            g.setColorAt(1, QColor.fromHsvF((t * 0.05 + 0.3) % 1, 0.8, 0.25))
            p.setBrush(g)
            p.drawRect(scr)
            n = 18
            bw = scr.width() / n
            for i in range(n):
                hgt = (0.15 + 0.6 * abs(math.sin(t * (2.1 + i * 0.37) + i)) * (0.6 + 0.4 * b)) * scr.height() * 0.55
                c = QColor.fromHsvF((i / n + t * 0.1) % 1.0, 0.8, 1.0)
                p.setBrush(c)
                p.drawRect(QRectF(scr.left() + i * bw + 1, scr.bottom() - hgt - 2, bw - 2, hgt))
            f = QFont()
            f.setBold(True)
            f.setPixelSize(int(0.17 * H))
            p.setFont(f)
            p.setPen(QColor("#FFFFFF"))
            title = "♪ " + (PLAYER.title or "...") + "   "
            fm = QFontMetricsF(f)
            tw = fm.horizontalAdvance(title)
            p.save()
            p.setClipRect(scr.adjusted(6, 0, -6, 0))
            if tw > scr.width() - 12:
                off = (t * 50) % tw
                for k in range(3):
                    p.drawText(QPointF(scr.left() + 6 - off + k * tw, scr.top() + 0.24 * H), title)
            else:
                p.drawText(QRectF(scr.left(), scr.top() + 0.04 * H, scr.width(), 0.25 * H), Qt.AlignCenter, title)
            pos, dur = PLAYER.position()
            if dur > 0:
                f.setPixelSize(int(0.11 * H))
                p.setFont(f)
                p.setPen(QColor(255, 255, 255, 200))
                p.drawText(QRectF(scr.left(), scr.top() + 0.27 * H, scr.width(), 0.16 * H), Qt.AlignCenter,
                           f"{int(pos // 60)}:{int(pos % 60):02d} / {int(dur // 60)}:{int(dur % 60):02d}")
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 255, 255, 60))
                p.drawRect(QRectF(scr.left() + 8, scr.top() + 0.44 * H, scr.width() - 16, 3))
                p.setBrush(QColor("#22D3EE"))
                p.drawRect(QRectF(scr.left() + 8, scr.top() + 0.44 * H, (scr.width() - 16) * pos / dur, 3))
            p.restore()
        else:
            p.setBrush(QColor("#111827"))
            p.drawRect(scr)
            f = QFont()
            f.setBold(True)
            f.setPixelSize(int(0.16 * H))
            p.setFont(f)
            p.setPen(QColor("#4B5563"))
            p.drawText(scr, Qt.AlignCenter, "DJ  ▶")
        # luces colgando de la estructura
        for i in range(6):
            x = -sw + (i + 0.5) * 2 * sw / 6
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#374151"))
            p.drawRoundedRect(QRectF(x - 0.08 * H, -top + 0.05 * H, 0.16 * H, 0.14 * H), 3, 3)
            if on:
                ang = math.sin(t * 1.4 + i * 1.3) * 0.5
                lit = (int(t * BPM / 60.0) + i) % 3 == 0
                c = QColor.fromHsvF((i / 6 + t * 0.08) % 1.0, 0.85, 1.0)
                c.setAlpha(int(70 + 80 * b) if lit else 35)
                p.setBrush(c)
                src = QPointF(x, -top + 0.18 * H)
                L = top * 0.95
                dx = math.sin(ang) * L
                spread = 0.35 * H
                p.drawPolygon(QPolygonF([src, QPointF(x + dx - spread, -top + 0.18 * H + L),
                                         QPointF(x + dx + spread, -top + 0.18 * H + L)]))
                c.setAlpha(255)
                p.setBrush(c)
                p.drawEllipse(src, 0.05 * H, 0.05 * H)
        # cabina del DJ con tornamesas
        bx = 0.35 * H
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#111827"))
        p.drawRect(QRectF(bx - 0.55 * H, -fl - 0.62 * H, 1.1 * H, 0.62 * H))
        p.setBrush(QColor("#22D3EE") if on else QColor("#334155"))
        p.drawRect(QRectF(bx - 0.55 * H, -fl - 0.35 * H, 1.1 * H, 0.04 * H))
        p.setBrush(QColor("#374151"))
        p.drawRect(QRectF(bx - 0.6 * H, -fl - 0.68 * H, 1.2 * H, 0.07 * H))
        for dx in (-0.3, 0.3):
            p.save()
            p.translate(bx + dx * H, -fl - 0.7 * H)
            p.setBrush(QColor("#0B0F19"))
            p.drawEllipse(QPointF(0, 0), 0.2 * H, 0.04 * H)
            if on:
                p.setPen(QPen(QColor("#F59E0B"), 1.5))
                a = t * 8
                p.drawLine(QPointF(0, 0), QPointF(math.cos(a) * 0.18 * H, math.sin(a) * 0.035 * H))
            p.restore()
        # destellos al ritmo
        if on and b > 0.6:
            p.setBrush(QColor(255, 255, 255, int(60 * b)))
            p.drawEllipse(QPointF(0, -top * 0.5), 0.4 * H, 0.4 * H)


# ============================================================================
CHEERS = ["¡Wuuu!", "¡Eso!", "¡Otra!", "♪♪", "¡Arriba!", "¡Esa canción!", "¡Fiesta!"]


@game
class Concert(Game):
    key, label = "concierto", "Concierto de DJ"
    min_p, max_p, span = 1, 14, 6.0
    weight = 0

    @classmethod
    def available(cls, crew):
        return PLAYER.playing and any(it.key == "escenario" for it in crew.items)

    def setup(self):
        stages = [it for it in self.crew.items if it.key == "escenario"]
        self.stage = min(stages, key=lambda it: abs(it.x - self.cx)) if stages else None
        if self.stage is None:
            return
        self.cx = self.stage.x
        n = len(self.players)
        L, Rb, _ = desktop_bounds()
        span = max(4.0, n * 0.7)
        for i, s in enumerate(self.players):
            x = self.cx + (i - (n - 1) / 2) * (span / max(n - 1, 1)) * self.H + random.uniform(-0.15, 0.15) * self.H
            x = clamp(x, L + self.H, Rb - self.H)
            self.spot[s] = (x, random.choice((-1, 1)))
        self.style = {s: random.randrange(3) for s in self.players}
        self.offset = {s: random.uniform(0, 0.15) for s in self.players}
        self.gather_t = 12.0

    def begin(self):
        if self.stage is None:
            self.end()
            return
        self.cheer_t = 2.0

    def play(self, s, dt):
        s.moving = False

    def play_pose(self, s):
        t = self.crew.time + self.offset[s]
        ph = (t * BPM / 60.0) % 1.0
        hop = max(0.0, math.sin(ph * math.pi)) * 0.22
        st = self.style[s]
        if st == 0:      # brinca con los dos brazos arriba
            p = S(uaF=160, faF=170, uaB=160, faB=170, tilt=-10)
        elif st == 1:    # puño al aire al ritmo
            up = ph < 0.5
            p = S(uaF=165 if up else 120, faF=170 if up else 200, uaB=-20, faB=30, tilt=-6)
        else:            # mueve los brazos de lado a lado
            k = math.sin(t * math.pi * BPM / 60.0)
            p = S(uaF=150 + 25 * k, faF=165 + 25 * k, uaB=150 - 25 * k, faB=165 - 25 * k, tilt=-8 + 6 * k)
        knee = 25 * (1 - min(1.0, hop / 0.1))
        return W(p, lift=hop, thF=p["thF"] + knee, shF=p["shF"] - knee, thB=p["thB"] + knee, shB=p["shB"] - knee)

    def update(self, dt):
        if self.stage is None or self.stage not in self.crew.items or not PLAYER.playing:
            self.end()
            return
        self.cheer_t -= dt
        if self.cheer_t <= 0 and self.players:
            self.cheer_t = random.uniform(1.5, 4.0)
            random.choice(self.players).say(random.choice(CHEERS), 1.3)


GAME_ORDER.append("concierto")


# ============================================================================
def add_music_controls(menu):
    if PLAYER.playing:
        menu.addAction(tr("⏸ Pausar música")).triggered.connect(PLAYER.pause)
    else:
        menu.addAction(tr("▶ Reproducir música")).triggered.connect(PLAYER.play)
    menu.addAction(tr("⏭ Siguiente canción")).triggered.connect(PLAYER.next)
    menu.addAction(tr("⏹ Detener")).triggered.connect(PLAYER.stop)
    vol = menu.addMenu(tr("Volumen"))
    for v in (0.1, 0.25, 0.5, 0.75, 1.0):
        a = vol.addAction(("✓ " if abs(PLAYER.volume - v) < 0.01 else "   ") + f"{int(v * 100)}%")
        a.triggered.connect(lambda _=False, v=v: PLAYER.set_volume(v))
    if PLAYER.title:
        menu.addAction("♪ " + PLAYER.title[:50]).setEnabled(False)


def load_music_settings(storage):
    d = storage._read("musica.json", {})
    if isinstance(d, dict):
        MUSIC.dirs = [x for x in d.get("dirs", []) if isinstance(x, str) and os.path.isdir(x)]
        MUSIC.whole = bool(d.get("whole", False))
        PLAYER.set_volume(float(d.get("vol", PLAYER.volume)))


def save_music_settings(storage):
    storage._write("musica.json", {"dirs": MUSIC.dirs, "whole": MUSIC.whole, "vol": PLAYER.volume})
