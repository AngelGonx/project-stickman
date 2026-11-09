"""El grupo: reloj, encuentros, juegos, objetos, guardado y menús."""
from .core import *  # noqa: F401,F403
from .actions import ACTIONS, SOLO, SOCIAL
from .draw import draw_stickman
from .stickman import Stickman
from .objects import ITEM_TYPES
from .rooms import ITEM_ORDER, INSTRUMENT_ORDER, ROOM_ORDER, BUILD_KEYS
from .games import GAMES, GAME_ORDER
from . import projector, dj
from . import storage, i18n
from .i18n import tr
from .creator import CreatorDialog
from PySide6.QtWidgets import QFileDialog, QMessageBox

JUEGO_CADA = 90.0      # segundos promedio entre juegos de grupo espontáneos


class Crew:
    def __init__(self, app):
        self.app = app
        self.members = []
        self.items = []
        self.games = []
        self.visible = True
        self.has_rooms = False
        self.paused = False
        self.time = 0.0
        self.game_cd = random.uniform(25, 45)
        self.library = storage.load_library()
        self.clock = QElapsedTimer()
        self.clock.start()
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(int(1000 / FPS))
        self.autosave = QTimer()
        self.autosave.timeout.connect(self.save_session)
        self.autosave.start(30000)
        app.aboutToQuit.connect(self.on_quit)
        self.build_tray()

    # ---------------- inicio / guardado ----------------
    def start(self):
        session = storage.load_session()
        specs = session if session is not None else storage.default_specs()
        projector.load_photo_settings(storage)
        projector.LIBRARY.rescan()
        dj.load_music_settings(storage)
        dj.MUSIC.rescan()
        self.load_build()
        for sp in specs:
            self.spawn(sp, save=False)
        self.save_session()

    def save_session(self):
        storage.save_session([m.spec for m in self.members])
        self.save_build()

    # ---------------- construcciones ----------------
    def kept_items(self):
        """Cuartos, techos y escaleras, y lo que está dentro o pegado a ellos."""
        rooms = [it for it in self.items if it.is_room]
        keep = []
        for it in self.items:
            if it.key in BUILD_KEYS or it.hidden:
                keep.append(it) if it.key in BUILD_KEYS else None
                continue
            p, inside = it.parent, False
            while p is not None:
                if p.is_room:
                    inside = True
                    break
                p = p.parent
            if not inside and it.on_ground:
                for r in rooms:     # pegado a un costado, al mismo nivel
                    gap = abs(it.x - r.x) - (r.W + it.W) * HEIGHT / 2
                    if abs(it.y - r.y) < 6 and gap < 0.3 * HEIGHT:
                        inside = True
                        break
            if inside:
                keep.append(it)
        return keep

    def save_build(self):
        data = []
        for it in self.kept_items():
            if it.dragging:
                continue
            data.append({"key": it.key, "x": round(it.x, 1), "y": round(it.y, 1), "state": it.save_state()})
        storage.save_build(data)

    def load_build(self):
        data = [d for d in storage.load_build() if isinstance(d, dict) and d.get("key") in ITEM_TYPES]
        data.sort(key=lambda d: -float(d.get("y", 0)))       # de abajo hacia arriba
        for d in data:
            try:
                it = ITEM_TYPES[d["key"]](self, float(d["x"]), float(d["y"]))
                it.load_state(d.get("state", {}))
            except Exception:
                continue
            it.on_ground = True
            self.items.append(it)
            self.has_rooms = any(i.is_room for i in self.items)
            it.support(it.y)
            if it.support_room is not None and abs(it.support(it.y) - it.y) < 3:
                it.attach(it.support_room)
            elif abs((ground_at(it.x) or it.y) - it.y) > 3:
                it.on_ground = False        # ya no hay en qué apoyarse: que caiga
            it.sync()
            it.show()
        self.restack()

    def on_quit(self):
        dj.save_music_settings(storage)
        dj.PLAYER.stop()
        self.save_session()
        storage.save_library(self.library)

    # ---------------- stickmen ----------------
    def spawn(self, spec, save=True):
        g = QGuiApplication.primaryScreen().availableGeometry()
        x = random.uniform(g.left() + HEIGHT, g.right() - HEIGHT)
        s = Stickman(self, storage.normalize(spec), x, g.top() + HEIGHT * 1.2)
        self.members.append(s)
        s.sync()
        s.show()
        if save:
            self.save_session()
        return s

    def remove(self, s=None):
        if not self.members:
            return
        s = s or self.members[-1]
        s.leave_all()
        self.members.remove(s)
        for m in self.members:
            if m.opponent is s:
                m.opponent, m.fight_t = None, 0.0
                if m.state == "fight":
                    m.decide()
        s.close()
        s.deleteLater()
        self.save_session()

    # ---------------- objetos ----------------
    def add_item(self, key):
        cur = QCursor.pos()
        L, Rb, top = desktop_bounds()
        it = ITEM_TYPES[key](self, clamp(cur.x(), L + HEIGHT, Rb - HEIGHT), cur.y())
        self.items.append(it)
        it.sync()
        it.show()
        self.restack()


    def restack(self):
        """Orden de ventanas: cuartos, techos, objetos, stickmen y capas de juego encima."""
        for it in sorted(self.items, key=lambda i: i.layer):
            if it.layer < 3:
                it.raise_()
        for m in self.members:
            m.raise_()
        for it in self.items:
            if it.layer >= 3:
                it.raise_()
        for g in self.games:
            if g.ov is not None:
                g.ov.raise_()

    def remove_item(self, it):
        it.release_users()
        if getattr(it, "held_by", None) is not None:
            it.held_by = None
        if it in self.items:
            self.items.remove(it)
        for other in self.items:
            if other.parent is it:
                other.parent = None
                other.on_ground = False
        it.close()
        it.deleteLater()

    def clear_items(self, build=False):
        for it in list(self.items):
            if (it.key in BUILD_KEYS) == build:
                self.remove_item(it)
        if build:
            self.save_build()

    # ---------------- reloj ----------------
    def tick(self):
        dt = min(self.clock.restart() / 1000.0, 0.05)
        if self.paused:
            return
        self.step(dt)
        for m in self.members:
            m.sync()
        for it in self.items:
            it.sync()

    def step(self, dt):
        self.time += dt
        self.has_rooms = any(it.is_room for it in self.items)
        for m in list(self.members):
            m.update_logic(dt)
        for it in sorted(self.items, key=lambda i: -i.y):     # de abajo hacia arriba
            it.tick(dt)
        for g in list(self.games):
            g.tick(dt)
        self.check_encounters()
        self.game_cd -= dt
        if self.game_cd <= 0:
            self.game_cd = random.uniform(0.6, 1.4) * JUEGO_CADA / max(ACTIVIDAD, 0.1)
            self.start_random_game()

    # ---------------- juegos ----------------
    def start_random_game(self):
        free = [m for m in self.members if m.is_free()]
        opts = [(k, GAMES[k].weight) for k in GAME_ORDER
                if GAMES[k].min_p <= len(free) and GAMES[k].available(self)]
        if not opts:
            return False
        keys, ws = zip(*opts)
        return self.start_game(random.choices(keys, ws)[0])

    def start_game(self, key, seed=None, force=False):
        cls = GAMES[key]
        if not cls.available(self):
            return False
        if force:
            pool = [m for m in self.members if m.grounded() and m.game is None and not m.dragging
                    and not (m.item is not None and m.item.key == "escenario")]
        else:
            pool = [m for m in self.members if m.is_free()]
        if seed is None:
            if not pool:
                return False
            seed = random.choice(pool)
        elif seed not in pool:
            pool.append(seed)
        others = [m for m in pool if m is not seed and abs(m.hy - seed.hy) < HEIGHT * 0.6]
        if key == "llamada":
            random.shuffle(others)
        else:
            others.sort(key=lambda m: abs(m.hx - seed.hx))
        n = min(cls.max_p, 1 + len(others))
        if n < cls.min_p:
            return False
        players = [seed] + others[:n - 1]
        for m in players:
            m.leave_all()
        self.games.append(cls(self, players))
        return True

    def check_encounters(self):
        ms = self.members
        for i in range(len(ms)):
            for k in range(i + 1, len(ms)):
                a, b = ms[i], ms[k]
                if not (a.state in Stickman.CALM and b.state in Stickman.CALM
                        and a.meet_cd <= 0 and b.meet_cd <= 0
                        and not a.busy() and not b.busy()
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
                    from .actions import SOCIAL_W
                    sk, sw = zip(*SOCIAL_W.items())
                    a.start_social(b, random.choices(sk, sw)[0])
                elif r == "traes":
                    a.start_tag(b)
                elif r == "pelear":
                    a.start_fight(b)
                else:
                    a.meet_cd = b.meet_cd = random.uniform(8, 16)

    # ---------------- biblioteca ----------------
    def lib_index(self, sid):
        for i, sp in enumerate(self.library):
            if sp["id"] == sid:
                return i
        return -1

    def save_to_library(self, s):
        i = self.lib_index(s.spec["id"])
        if i >= 0:
            self.library[i] = storage.normalize(s.spec)
        else:
            self.library.append(storage.normalize(s.spec))
        storage.save_library(self.library)
        s.say("¡Guardado!", 1.5)

    def create_custom(self):
        spec = CreatorDialog.ask()
        if spec:
            self.library.append(spec)
            storage.save_library(self.library)
            self.spawn(spec)

    def edit_stickman(self, s):
        spec = CreatorDialog.ask(s.spec)
        if spec:
            spec["id"] = s.spec["id"]
            self.apply_spec(spec)

    def edit_library(self, sid):
        i = self.lib_index(sid)
        if i < 0:
            return
        spec = CreatorDialog.ask(self.library[i])
        if spec:
            spec["id"] = sid
            self.apply_spec(spec)

    def apply_spec(self, spec):
        for m in self.members:
            if m.spec["id"] == spec["id"]:
                m.set_spec(spec)
        i = self.lib_index(spec["id"])
        if i >= 0:
            self.library[i] = spec
            storage.save_library(self.library)
        self.save_session()

    def delete_library(self, sid):
        i = self.lib_index(sid)
        if i < 0:
            return
        name = self.library[i]["name"]
        r = QMessageBox.question(None, tr("Borrar personaje"),
                                 tr("¿Borrar a «{name}» de la biblioteca?\n(Si está en pantalla, se queda ahí.)").format(name=name))
        if r == QMessageBox.Yes:
            self.library.pop(i)
            storage.save_library(self.library)

    def duplicate(self, s):
        spec = dict(s.spec)
        spec["id"] = storage.new_id()
        spec["name"] = s.spec["name"] + " 2"
        self.spawn(spec)

    def export_backup(self):
        path, _ = QFileDialog.getSaveFileName(None, tr("Exportar respaldo"), "respaldo_stickmen.json",
                                              tr("Respaldo (*.json)"))
        if path:
            storage.export_backup(path, self.library, [m.spec for m in self.members])
            self.tray.showMessage("Desk Stickmen", tr("Respaldo guardado."))

    def import_backup(self):
        path, _ = QFileDialog.getOpenFileName(None, tr("Importar respaldo"), "", tr("Respaldo (*.json)"))
        if not path:
            return
        try:
            lib, _ses = storage.import_backup(path)
        except Exception:
            QMessageBox.warning(None, tr("Importar respaldo"), tr("Ese archivo no es un respaldo válido."))
            return
        for sp in lib:
            i = self.lib_index(sp["id"])
            if i >= 0:
                self.library[i] = sp
            else:
                self.library.append(sp)
        storage.save_library(self.library)
        self.tray.showMessage("Desk Stickmen", tr("Se importaron {n} personajes a la biblioteca.").format(n=len(lib)))

    # ---------------- fotos del proyector ----------------
    def source_menu(self, menu, lib_, kind, scanning_txt, count_txt, default_txt, pick_txt):
        menu.addAction(scanning_txt if lib_.scanning else count_txt.format(n=len(lib_.files))).setEnabled(False)
        menu.addSection(tr("¿De dónde salen?"))
        a = menu.addAction(default_txt)
        a.setCheckable(True)
        a.setChecked(not lib_.whole and not lib_.dirs)
        a.triggered.connect(lambda: self.set_source(kind, [], False))
        for d in lib_.dirs:
            a = menu.addAction("✓ " + d)
            a.setToolTip(tr("Clic para quitar esta carpeta"))
            a.triggered.connect(lambda _=False, d=d: self.set_source(kind, [x for x in lib_.dirs if x != d], False))
        a = menu.addAction(tr("Agregar carpeta…"))
        a.triggered.connect(lambda: self.add_source_dir(kind, pick_txt))
        a = menu.addAction(tr("Toda la computadora"))
        a.setCheckable(True)
        a.setChecked(lib_.whole)
        a.triggered.connect(lambda: self.set_source(kind, lib_.dirs, not lib_.whole))
        menu.addSeparator()
        menu.addAction(tr("Volver a buscar")).triggered.connect(lib_.rescan)

    def set_source(self, kind, dirs, whole):
        lib_ = dj.MUSIC if kind == "music" else projector.LIBRARY
        lib_.dirs, lib_.whole = list(dirs), whole
        if kind == "music":
            dj.save_music_settings(storage)
        else:
            projector.save_photo_settings(storage)
        lib_.rescan()

    def add_source_dir(self, kind, title):
        lib_ = dj.MUSIC if kind == "music" else projector.LIBRARY
        d = QFileDialog.getExistingDirectory(None, title)
        if d:
            self.set_source(kind, lib_.dirs + ([d] if d not in lib_.dirs else []), False)

    # ---------------- bandeja ----------------
    def build_tray(self):
        self.tray = QSystemTrayIcon(self.make_icon())
        self.tray.setToolTip("Desk Stickmen")
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.fill_tray_menu)
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        self.fill_tray_menu()

    def fill_tray_menu(self):
        m = self.menu
        m.clear()
        add = m.addMenu(tr("Agregar stickman"))
        add.addSection(tr("Originales"))
        for sp in storage.default_specs():
            add.addAction(sp["name"]).triggered.connect(lambda _=False, sp=sp: self.spawn(sp))
        if self.library:
            add.addSection(tr("De la biblioteca"))
            for sp in self.library:
                add.addAction(sp["name"]).triggered.connect(lambda _=False, sp=sp: self.spawn(sp))
        m.addAction(tr("Crear stickman personalizado…")).triggered.connect(self.create_custom)

        lib = m.addMenu(tr("Biblioteca de personajes"))
        if not self.library:
            lib.addAction(tr("(vacía: clic derecho a un stickman → Guardar)")).setEnabled(False)
        for sp in self.library:
            sub = lib.addMenu(sp["name"])
            sub.addAction(tr("Poner en pantalla")).triggered.connect(lambda _=False, sp=sp: self.spawn(sp))
            sub.addAction(tr("Editar…")).triggered.connect(lambda _=False, i=sp["id"]: self.edit_library(i))
            sub.addAction(tr("Borrar")).triggered.connect(lambda _=False, i=sp["id"]: self.delete_library(i))
        lib.addSeparator()
        lib.addAction(tr("Guardar a todos los de la pantalla")).triggered.connect(
            lambda: [self.save_to_library(s) for s in self.members])
        lib.addAction(tr("Exportar respaldo…")).triggered.connect(self.export_backup)
        lib.addAction(tr("Importar respaldo…")).triggered.connect(self.import_backup)

        obj = m.addMenu(tr("Objetos"))
        for k in ITEM_ORDER:
            obj.addAction(tr(ITEM_TYPES[k].label)).triggered.connect(lambda _=False, k=k: self.add_item(k))
        ins = m.addMenu(tr("Instrumentos"))
        for k in INSTRUMENT_ORDER:
            ins.addAction(tr(ITEM_TYPES[k].label)).triggered.connect(lambda _=False, k=k: self.add_item(k))
        rooms = m.addMenu(tr("Cuartos y techos"))
        for k in ROOM_ORDER:
            if k in ("escaleras", "techo"):
                rooms.addSeparator()
            rooms.addAction(tr(ITEM_TYPES[k].label)).triggered.connect(lambda _=False, k=k: self.add_item(k))
        m.addAction(tr("Quitar todos los objetos")).triggered.connect(lambda: self.clear_items(False))
        rooms.addSeparator()
        rooms.addAction(tr("Quitar todas las construcciones")).triggered.connect(lambda: self.clear_items(True))

        gm = m.addMenu(tr("Juegos"))
        for k in GAME_ORDER:
            a = gm.addAction(tr(GAMES[k].label))
            a.setEnabled(GAMES[k].available(self) and len(self.members) >= GAMES[k].min_p)
            a.triggered.connect(lambda _=False, k=k: self.start_game(k, force=True))

        m.addSeparator()
        m.addAction(tr("Quitar uno")).triggered.connect(lambda: self.remove())
        m.addAction(tr("Reanudar") if self.paused else "Pausar").triggered.connect(self.toggle_pause)
        m.addAction(tr("Mostrar") if not self.visible else "Ocultar").triggered.connect(self.toggle_visible)
        mus = m.addMenu(tr("Música del DJ"))
        dj.add_music_controls(mus)
        mus.addSeparator()
        self.source_menu(mus, dj.MUSIC, "music", tr("Buscando música…"), tr("{n} canciones encontradas"),
                         tr("Música, Descargas y Escritorio"), tr("Elige una carpeta con música"))
        ph = m.addMenu(tr("Fotos del proyector"))
        self.source_menu(ph, projector.LIBRARY, "photo", tr("Buscando fotos…"), tr("{n} fotos y GIFs encontrados"),
                         tr("Imágenes, Escritorio y Descargas"), tr("Elige una carpeta con fotos"))

        lang = m.addMenu("Idioma / Language")
        for code, name in (("es", "Español"), ("en", "English")):
            a = lang.addAction(("✓ " if i18n.LANG == code else "   ") + name)
            a.triggered.connect(lambda _=False, c=code: i18n.set_lang(c))
        m.addSeparator()
        m.addAction(tr("Salir")).triggered.connect(self.app.quit)

    def toggle_pause(self):
        self.paused = not self.paused

    def toggle_visible(self):
        self.visible = not self.visible
        for g in self.games:
            if g.ov is not None:
                g.ov.setVisible(self.visible)

    # ---------------- menú de cada stickman ----------------
    def stickman_menu(self, s, pos):
        menu = QMenu()
        menu.addAction(f"— {s.spec['name']} —").setEnabled(False)
        free = s.grounded() and s.opponent is None

        def order(fn):
            def run():
                s.chase_t = 0.0
                s.leave_all()
                fn()
            return run

        basics = [("Caminar", lambda: s.set_state("walk", 6)),
                  ("Correr", lambda: s.set_state("run", 3)),
                  ("¡Correr a toda velocidad!", s.sprint),
                  ("Sentarse", lambda: s.set_state("sit", 12)),
                  ("Saltar", s.jump),
                  ("Perseguir el cursor", s.notice_cursor)]
        for name, fn in basics:
            a = menu.addAction(tr(name))
            a.setEnabled(free)
            a.triggered.connect(order(fn))

        sub = menu.addMenu(tr("Acciones"))
        sub.setEnabled(free)
        for key in sorted(set(SOLO) | {"saludar"}, key=lambda k: tr(ACTIONS[k].label)):
            sub.addAction(tr(ACTIONS[key].label)).triggered.connect(
                order(lambda _=False, k=key: s.start_action(k)))

        usable = [it for it in self.items if it.usable() and it.free_slots() and not it.hidden]
        um = menu.addMenu(tr("Usar objeto"))
        um.setEnabled(free and bool(usable))
        for it in usable:
            um.addAction(tr(it.label)).triggered.connect(order(lambda _=False, it=it: s.go_use(it)))

        gm = menu.addMenu(tr("Jugar"))
        gm.setEnabled(free)
        for k in GAME_ORDER:
            a = gm.addAction(tr(GAMES[k].label))
            a.setEnabled(GAMES[k].available(self) and len(self.members) >= GAMES[k].min_p)
            a.triggered.connect(lambda _=False, k=k: self.start_game(k, seed=s, force=True))

        others = [m for m in self.members if m is not s and m.grounded() and m.opponent is None]
        if others and free:
            withm = menu.addMenu(tr("Con otro…"))
            for o in others:
                om = withm.addMenu(o.spec["name"])

                def both(fn, o=o):
                    def run():
                        s.leave_all()
                        o.leave_all()
                        fn()
                    return run
                om.addAction(tr("Pelear")).triggered.connect(both(lambda o=o: s.start_fight(o)))
                om.addAction(tr("Jugar a las traes")).triggered.connect(both(lambda o=o: s.start_tag(o)))
                for k in SOCIAL:
                    om.addAction(tr(ACTIONS[k].label)).triggered.connect(
                        both(lambda o=o, k=k: s.start_social(o, k)))
        menu.addSeparator()
        menu.addAction(tr("Guardar en la biblioteca")).triggered.connect(lambda: self.save_to_library(s))
        menu.addAction(tr("Editar apariencia…")).triggered.connect(lambda: self.edit_stickman(s))
        menu.addAction(tr("Duplicar")).triggered.connect(lambda: self.duplicate(s))
        menu.addAction(tr("Quitar de la pantalla")).triggered.connect(lambda: self.remove(s))
        menu.exec(pos)

    @staticmethod
    def make_icon():
        from .actions import pose_wave
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
    i18n.load_lang()
    crew = Crew(app)
    crew.start()
    sys.exit(app.exec())
