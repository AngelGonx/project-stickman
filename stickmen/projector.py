"""Proyector con pantalla de tela: pasa fotos y GIFs de tu compu como presentación."""
import os
import threading

from .core import *  # noqa: F401,F403
from .i18n import tr
from .objects import Item, Slot, item_type, wood
from .games import Game, game, GAME_ORDER, art_strokes, draw_art, ART_THEMES
from .actions import S, W, P, pose_stand, pose_walk
from PySide6.QtCore import QSize, QStandardPaths, QStorageInfo
from PySide6.QtGui import QImageReader, QMovie, QImage

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}
SKIP_DIRS = {"windows", "program files", "program files (x86)", "programdata", "appdata", "$recycle.bin",
             "system volume information", "node_modules", ".git", "__pycache__", "site-packages",
             "steamapps", "cache", "caches", "temp", "tmp", "winsxs", "drivers", ".gradle", ".android",
             "library", "msocache", "recovery", "perflogs", "intel", "amd", "nvidia"}
MAX_FILES = 4000


class PhotoLibrary:
    """Busca archivos (fotos o música) en segundo plano en las carpetas que elijas."""

    def __init__(self, exts=None, locs=None, min_size=25000, small_ok=(".gif",)):
        self.exts = exts or IMG_EXT
        self.locs = locs or (QStandardPaths.PicturesLocation, QStandardPaths.DesktopLocation,
                             QStandardPaths.DownloadLocation)
        self.min_size, self.small_ok = min_size, small_ok
        self.files = []
        self.scanning = False
        self.dirs = []
        self.whole = False
        self._gen = 0

    def default_dirs(self):
        out = []
        for loc in self.locs:
            for d in QStandardPaths.standardLocations(loc):
                if d and os.path.isdir(d) and d not in out:
                    out.append(d)
        return out

    def roots(self):
        if self.whole:
            out = []
            for v in QStorageInfo.mountedVolumes():
                if v.isValid() and v.isReady() and not v.isReadOnly():
                    out.append(v.rootPath())
            return out or ["/"]
        return self.dirs or self.default_dirs()

    def rescan(self):
        self._gen += 1
        gen = self._gen
        roots = self.roots()
        self.scanning = True

        def work():
            found = []
            for root in roots:
                for dp, dns, fns in os.walk(root, onerror=lambda e: None):
                    if gen != self._gen:
                        return
                    dns[:] = [d for d in dns if not d.startswith(".") and d.lower() not in SKIP_DIRS]
                    for fn in fns:
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in self.exts:
                            path = os.path.join(dp, fn)
                            try:
                                if ext not in self.small_ok and os.path.getsize(path) < self.min_size:
                                    continue        # íconos y miniaturas: no
                            except OSError:
                                continue
                            found.append(path)
                            if len(found) >= MAX_FILES:
                                break
                    if len(found) >= MAX_FILES:
                        break
            if gen == self._gen:
                self.files = found
                self.scanning = False

        threading.Thread(target=work, daemon=True).start()

    def pick(self, n):
        if not self.files:
            return []
        return random.sample(self.files, min(n, len(self.files)))


LIBRARY = PhotoLibrary()


@item_type
class Projector(Item):
    key, label, W, HH = "proyector", "Proyector y pantalla", 4.8, 2.6
    SCR = (-1.05, -2.45, 2.7, 1.6)     # x, y, ancho, alto de la pantalla (en H, relativo a la base)

    def __init__(self, *a):
        super().__init__(*a)
        self.showing = False
        self.slides = []        # rutas o ("arte", trazos)
        self.idx = -1
        self.img = None
        self.movie = None
        self.fade = 0.0
        self.slide_t = 0.0
        self.auto = False

    def make_slots(self):
        return [Slot(-0.4, 1, "o_tele"), Slot(0.9, -1, "o_tele")]

    def screen_rect(self):
        x, y, w, h = self.SCR
        return QRectF(x * self.H, y * self.H, w * self.H, h * self.H)

    # ---- presentación
    def start_show(self, n=8):
        self.slides = LIBRARY.pick(n)
        if not self.slides:     # sin fotos: presenta "obras de arte"
            self.slides = [("arte", art_strokes(random.choice(ART_THEMES),
                                                QColor.fromHsvF(random.random(), 0.7, 0.8), random.random()))
                           for _ in range(n)]
        self.idx = -1
        self.showing = True
        self.next_slide()

    def stop_show(self):
        self.showing = False
        self.set_movie(None)
        self.img = None
        self.idx = -1

    def set_movie(self, mv):
        if self.movie is not None:
            self.movie.stop()
            self.movie.deleteLater()
        self.movie = mv

    def next_slide(self):
        if not self.slides:
            return
        self.idx = (self.idx + 1) % len(self.slides)
        self.fade = 0.0
        self.slide_t = 0.0
        self.set_movie(None)
        self.img = None
        sl = self.slides[self.idx]
        if isinstance(sl, tuple):
            return
        r = self.screen_rect()
        try:
            if sl.lower().endswith(".gif"):
                mv = QMovie(sl)
                if mv.isValid() and mv.frameCount() != 1:
                    mv.setCacheMode(QMovie.CacheAll)
                    mv.jumpToFrame(0)
                    sz = mv.currentImage().size()
                    if sz.width() > 0:
                        sz.scale(QSize(int(r.width() * 2), int(r.height() * 2)), Qt.KeepAspectRatio)
                        mv.setScaledSize(sz)
                    mv.start()
                    self.set_movie(mv)
                    return
            rd = QImageReader(sl)
            rd.setAutoTransform(True)
            sz = rd.size()
            if sz.isValid() and sz.width() > 0:
                sz.scale(QSize(int(r.width() * 2), int(r.height() * 2)), Qt.KeepAspectRatio)
                rd.setScaledSize(sz)
            im = rd.read()
            self.img = im if not im.isNull() else None
        except Exception:
            self.img = None

    def extra_tick(self, dt):
        self.fade = min(1.0, self.fade + dt * 2.5)
        watching = any(sl.user is not None for sl in self.slots)
        if watching and not self.showing:
            self.start_show(12)
            self.auto = True
        elif self.auto and not watching and self.showing:
            self.stop_show()
            self.auto = False
        if self.showing and self.auto:
            self.slide_t += dt
            if self.slide_t > 5.0:
                self.next_slide()

    def extra_menu(self, menu):
        menu.addAction(tr("Siguiente foto")).triggered.connect(self.next_slide)

    # ---- dibujo
    def draw(self, p):
        H = self.H
        r = self.screen_rect()
        # tripié de la pantalla
        p.setPen(QPen(QColor("#374151"), 0.04 * H, Qt.SolidLine, Qt.RoundCap))
        cx = r.center().x()
        p.drawLine(QPointF(cx, r.bottom()), QPointF(cx, 0))
        p.drawLine(QPointF(cx, -0.25 * H), QPointF(cx - 0.4 * H, 0))
        p.drawLine(QPointF(cx, -0.25 * H), QPointF(cx + 0.4 * H, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1F2937"))
        p.drawRoundedRect(QRectF(r.left() - 0.08 * H, r.top() - 0.08 * H, r.width() + 0.16 * H, 0.1 * H), 4, 4)
        # tela
        p.setBrush(QColor("#F8FAFC"))
        p.drawRect(r)
        p.setPen(QPen(QColor(0, 0, 0, 25), 1))
        for i in range(1, 6):
            x = r.left() + r.width() * i / 6
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
        if self.showing:
            self.draw_slide(p, r)
        # proyector en su mesita
        px, py = -1.85 * H, -0.62 * H
        wood(p, QRectF(px - 0.3 * H, -0.5 * H, 0.6 * H, 0.06 * H), "#78350F")
        p.setPen(QPen(QColor("#78350F"), 0.04 * H))
        p.drawLine(QPointF(px - 0.22 * H, -0.46 * H), QPointF(px - 0.25 * H, 0))
        p.drawLine(QPointF(px + 0.22 * H, -0.46 * H), QPointF(px + 0.25 * H, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E5E7EB"))
        p.drawRoundedRect(QRectF(px - 0.22 * H, py - 0.06 * H, 0.44 * H, 0.18 * H), 5, 5)
        p.setBrush(QColor("#111827"))
        p.drawEllipse(QPointF(px + 0.2 * H, py + 0.03 * H), 0.06 * H, 0.06 * H)
        if self.showing:
            lens = QPointF(px + 0.22 * H, py + 0.03 * H)
            c = QColor(255, 255, 220, 38)
            p.setBrush(c)
            p.drawPolygon(QPolygonF([lens, r.topLeft(), r.bottomLeft()]))
            p.drawPolygon(QPolygonF([lens, r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]))

    def draw_slide(self, p, r):
        p.save()
        p.setClipRect(r)
        p.setOpacity(self.fade)
        sl = self.slides[self.idx] if 0 <= self.idx < len(self.slides) else None
        if isinstance(sl, tuple):
            m = r.height() * 0.1
            ar = QRectF(0, 0, r.height() * 1.25 - 2 * m, r.height() - 2 * m)
            ar.moveCenter(r.center())
            draw_art(p, ar, sl[1], 1.0)
        else:
            im = self.movie.currentImage() if self.movie is not None else self.img
            if im is not None and not im.isNull():
                sz = im.size().scaled(r.size().toSize(), Qt.KeepAspectRatio)
                tr_ = QRectF(0, 0, sz.width(), sz.height())
                tr_.moveCenter(r.center())
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                p.drawImage(tr_, im)
            else:
                p.fillRect(r, QColor("#E2E8F0"))
                p.setPen(QColor("#64748B"))
                p.drawText(r, Qt.AlignCenter, "…")
        p.restore()


# ============================================================================
REACT = ["¡Ooh!", "¡Wow!", "jaja", "¡Qué bonito!", "¡Otra!", "¿Quién es?", "¡Jajaja!", "¡Oh!", "♥"]
TALK = ["Y aquí…", "¡Miren esto!", "Siguiente…", "Esta es de mis favoritas", "¿Se acuerdan?",
        "Esta me encanta", "Y ahora…"]


@game
class Presentation(Game):
    key, label = "presentacion", "Presentación con proyector"
    min_p, max_p, span = 2, 6, 6.0
    weight = 8

    @classmethod
    def available(cls, crew):
        return any(it.key == "proyector" and not it.dragging and not it.hidden for it in crew.items)

    def setup(self):
        projs = [it for it in self.crew.items if it.key == "proyector"]
        self.proj = min(projs, key=lambda it: abs(it.x - self.cx)) if projs else None
        if self.proj is None:
            return
        self.proj.release_users()
        H = self.H
        r = self.proj.screen_rect()
        self.presenter = self.players[0]
        self.audience = self.players[1:]
        sx = self.proj.x + r.right() + 0.35 * H
        self.spot[self.presenter] = (sx, -1)
        n = len(self.audience)
        for i, s in enumerate(self.audience):
            x = self.proj.x + r.left() + r.width() * (i + 0.5) / max(n, 1)
            self.spot[s] = (x, 1 if x < self.proj.x + r.center().x() else -1)
        self.ground = self.proj.y

    def begin(self):
        if self.proj is None:
            self.end()
            return
        self.n = random.randint(6, 10)
        self.proj.auto = False
        self.proj.start_show(self.n)
        self.count = 0
        self.slide_t = 0.0
        self.presenter.prop_override = "pointer"
        self.presenter.say("¡Bienvenidos a mi presentación!", 2.2)

    def play(self, s, dt):
        s.moving = False
        if s in self.spot:
            s.facing = self.spot[s][1]

    def play_pose(self, s):
        if s is self.presenter:
            k = math.sin(s.t * 1.5)
            return S(uaF=125 + 15 * k, faF=135 + 10 * k, uaB=-20, faB=20, tilt=-6, lean=-2)
        clap = self.count >= self.n
        if clap:
            o = 18 * math.sin(s.t * 16)
            return W(P(lean=-2, thB=85, shB=-80, thF=95, shF=-95), uaF=70, faF=110 + o, uaB=60, faB=95 - o)
        return P(lean=-4, tilt=-14, thB=85, shB=-80, thF=95, shF=-95, uaB=20, faB=80, uaF=25, faF=85)

    def update(self, dt):
        if self.proj is None or self.proj not in self.crew.items or self.proj.dragging:
            self.end()
            return
        if self.count >= self.n:
            if self.t - self.end_t > 3.5:
                self.proj.stop_show()
                self.end(winners=self.players)
            return
        self.slide_t += dt
        dur = 6.5 if self.proj.movie is not None else 5.0
        if self.slide_t > 1.2 and self.slide_t - dt <= 1.2 and random.random() < 0.6:
            self.presenter.say(random.choice(TALK), 1.6)
        if self.slide_t > 2.6 and self.slide_t - dt <= 2.6 and self.audience:
            for s in random.sample(self.audience, min(len(self.audience), random.randint(1, 2))):
                s.say(random.choice(REACT), 1.4)
        if self.slide_t > dur:
            self.slide_t = 0.0
            self.count += 1
            if self.count >= self.n:
                self.end_t = self.t
                self.presenter.say("¡Gracias!", 2.0)
                for s in self.audience:
                    s.say(random.choice(["¡Bravo!", "clap clap", "¡Otra!"]), 2.0)
            else:
                self.proj.next_slide()

    def end(self, winners=(), losers=()):
        if getattr(self, "proj", None) is not None and self.proj.showing and not self.proj.auto:
            self.proj.stop_show()
        super().end(winners, losers)


GAME_ORDER.append("presentacion")


def load_photo_settings(storage):
    d = storage._read("proyector.json", {})
    if isinstance(d, dict):
        LIBRARY.dirs = [x for x in d.get("dirs", []) if isinstance(x, str) and os.path.isdir(x)]
        LIBRARY.whole = bool(d.get("whole", False))


def save_photo_settings(storage):
    storage._write("proyector.json", {"dirs": LIBRARY.dirs, "whole": LIBRARY.whole})
