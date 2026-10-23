# Mochi's pill and everything around it. Type into her to send a message to Claude; she shows Claude's replies,
# questions and progress. A port of the Bar class in macos/Sources/Mochi.swift; the comments there apply here too.
import json
import math
import os
import re
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio, GLib  # noqa: E402

from . import config, paths, text, todos as todolist, terminals, ui  # noqa: E402
from .colors import goo_colors, hex_, to_hex, white, rgb, CYAN_TEXT, PRESETS  # noqa: E402
from .compositor import detect as detect_compositor  # noqa: E402
from .goo import Goo  # noqa: E402
from .layer import Floating, monitor_named, monitors  # noqa: E402
from .parts import Fx, Wave, Visitors, Social, TodoBadge, SOCIAL_SITES  # noqa: E402
from .tray import Tray  # noqa: E402

ENV = os.environ
STATUS_IDLE = "→ Claude"


def later(ms, fn):
    GLib.timeout_add(int(ms), lambda: (fn(), False)[1])


def read_json(p):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def today_start():
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))


class Bar:
    # sizes: a small "Mochi" pill when collapsed, the full bar when open
    W, H = 560, 48
    w, h = 120, 34

    def __init__(self, app):
        self.app = app
        self.cfg = config.load()
        self.state = config.State()
        text.set_families(self.cfg["font"], self.cfg["mono_font"])
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)   # the colour picker, tooltips
        ui.install_css(self.cfg["glass_alpha"], self.cfg["font"], self.cfg["mono_font"])
        self.comp = detect_compositor()
        self.sender = terminals.Sender(self.comp, self.cfg, later)
        self.colors = goo_colors(hex_(self.cfg["color"]))

        self.open = False
        self.sending = False
        self.size = (self.w, self.h)          # current (animated) pill size
        self.anim = None
        self.cx = None                         # the pill's bottom-centre, in the output's coordinates
        self.meter_text = ""
        self.todos = []
        self.todo_mtime = None
        self.q_data, self.q_shown, self.q_index, self.answering_other = None, "", 0, False
        self.progress_seen, self.now_text = "", ""
        self.pages, self.page = [], 0
        self.last_seen = None
        self.social_seen = None
        self.seen_visitors = None
        self.visitor_note = ""
        self.hide_src = None
        self.bubble_hover = False
        self.todo_hover = False
        self.pointer_local = None
        self.recent = []
        self.drag = None
        self.last_move = (0.0, 0.0)

        # where she lives: the focused output (or the one in config.json, or PB_SCREEN=index)
        name = self.cfg.get("monitor") or self.comp.focused_monitor()
        self.monitor = monitor_named(name)
        try:
            i = int(ENV.get("PB_SCREEN", ""))
            if i < len(monitors()): self.monitor = monitors()[i]
        except ValueError:
            pass

        self.goo = Goo(self.colors)
        st = self.state
        self.goo.fed = st.get("fed", 0) if st.get("fedDay") == today_start() else 0
        self.fx = Fx()
        self.mini = Wave("Mochi")
        self.visitors = Visitors()
        self.social = Social()
        self.todo_badge = TodoBadge()
        self.status_text, self.status_color = STATUS_IDLE, white(0.6)

        self.bubble = self.q_panel = self.now_panel = self.todo_panel = self.menu_panel = None
        self.menu_hover = False
        self.build_pill()

        self.lay()
        self.panel.present()
        self.tray = Tray(self.tray_items, self.find_mochi, self.colors.body)

        self.last_seen = paths.mtime(paths.LAST)     # don't pop up an old reply at launch
        p = read_json(paths.PROGRESS)
        if isinstance(p, dict): self.progress_seen = p.get("text", "")
        q = read_json(paths.QUESTION)
        if isinstance(q, dict) and time.time() - q.get("time", 0) > 1800: self.q_shown = q.get("id", "")   # a stale question
        self.reload_todos(announce=False)

        # open at login: switched on once, the first time; after that the menu decides
        if not st.get("loginSet"):
            st.set("loginSet", True); self.set_login(True)

        GLib.timeout_add(83, self.tick)              # 12 frames a second, for a pixel-art feel
        GLib.timeout_add(33, self.tick_wave)
        GLib.timeout_add(700, lambda: (self.check_reply(), True)[1])

        # social notifications: a slot for a source plug-in (see mochi/social.py); PB_DEMO=social shows sample badges
        if "social" in ENV.get("PB_DEMO", ""):
            self.check_social()
        # PB_DEMO=send plays the send animation without sending anything (for checking it)
        if "send" in ENV.get("PB_DEMO", ""):
            later(1500, lambda: self.set_open(True))
            later(2300, self.celebrate_send)

    # ---------------------------------------------------------------- the pill

    def build_pill(self):
        self.panel = Floating(self.app, self.monitor, keyboard=True)
        self.area = Gtk.DrawingArea()
        self.area.set_draw_func(self.draw_pill)
        ov = Gtk.Overlay()
        ov.set_child(self.area)
        self.field = Gtk.Entry()
        self.field.add_css_class("mochi-field")
        self.field.set_placeholder_text("Message Mochi…")
        self.field.set_has_frame(False)
        self.field.set_halign(Gtk.Align.START); self.field.set_valign(Gtk.Align.CENTER)
        self.field.set_margin_start(1 + 46)
        self.field.set_size_request(self.W - 46 - 160, 22)
        self.field.set_visible(False)
        self.field.connect("activate", lambda *_: self.send())
        ov.add_overlay(self.field)
        self.panel.set_child(ov)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.panel.add_controller(keys)

        click = Gtk.GestureClick(button=1)
        click.connect("released", self.on_click)
        self.area.add_controller(click)
        right = Gtk.GestureClick(button=3)
        right.connect("pressed", lambda g, n, x, y: self.show_menu(x, y))
        ov.add_controller(right)
        drag = Gtk.GestureDrag(button=1)
        drag.connect("drag-begin", self.drag_begin)
        drag.connect("drag-update", self.drag_update)
        drag.connect("drag-end", lambda *_: setattr(self, "drag", None))
        self.area.add_controller(drag)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", lambda c, x, y: setattr(self, "pointer_local", (x, y)))
        motion.connect("leave", lambda c: setattr(self, "pointer_local", None))
        ov.add_controller(motion)
        self.panel.connect("notify::is-active", self.on_active)

        sw, sh = self.size
        self.cx = None
        self.panel.resize(sw, sh)
        self.reposition()

    def output(self):
        g = self.monitor.get_geometry() if self.monitor else None
        return (g.x, g.y, g.width, g.height) if g else (0, 0, 1280, 720)

    def reserved(self):
        return self.comp.reserved(self.monitor.get_connector() if self.monitor else "")

    def reposition(self):
        """put the pill at its centre, kept on screen, then the pop-ups above it"""
        _x, _y, mw, _mh = self.output()
        rl, _rt, rr, _rb = self.reserved()
        usable = mw - rl - rr
        if self.cx is None: self.cx = usable / 2
        w, h = self.size
        left = min(max(self.cx - w / 2, 8), usable - w - 8)
        self.panel.place(left, self.cfg["bottom_margin"])
        self.reposition_panels()

    # -- drawing --

    def draw_pill(self, area, cr, W, H):
        cr.translate(0, H); cr.scale(1, -1)           # y up, like AppKit
        r = H / 2
        def rounded(x, y, w, h, rad):
            cr.new_sub_path()
            cr.arc(x + w - rad, y + rad, rad, -math.pi / 2, 0); cr.arc(x + w - rad, y + h - rad, rad, 0, math.pi / 2)
            cr.arc(x + rad, y + h - rad, rad, math.pi / 2, math.pi); cr.arc(x + rad, y + rad, rad, math.pi, 3 * math.pi / 2)
            cr.close_path()
        # smoked glass pill: always dark, with a dark outer ring (reads on light screens) and a light inner ring (reads on dark ones)
        rounded(0.5, 0.5, W - 1, H - 1, r - 0.5)
        cr.set_source_rgba(0.063, 0.063, 0.07, self.cfg["glass_alpha"]); cr.fill_preserve()
        cr.set_source_rgba(0, 0, 0, 0.45); cr.set_line_width(1); cr.stroke()
        rounded(1.5, 1.5, W - 3, H - 3, r - 1.5)
        cr.set_source_rgba(1, 1, 1, 0.28); cr.stroke()

        cr.translate(1, 1)                              # the glass's coordinates, as in the Swift layout
        gh = H - 2
        open_ = self.open
        dx, dy = self.dot_origin(gh)
        self.goo.draw(cr, dx, dy)
        if not open_:
            mw, mh = self.mini.size()
            self.mini.draw(cr, 41, (gh - mh) / 2)
            x = 41 + mw
            if self.meter_text:
                fd = text.font(10, "medium", mono=True)
                tw, th = text.size(self.meter_text, fd)
                text.draw(cr, self.meter_text, x + 8, round((gh - th) / 2), fd, CYAN_TEXT)
                x += 8 + tw
            if self.visitors.tints:
                self.visitors.draw(cr, x + 8, round((gh - 10) / 2)); x += 8 + self.visitors.width
            if self.social.counts:
                self.social_x = x + 10
                self.social.draw(cr, x + 10, round((gh - 14) / 2)); x += 10 + self.social.width
            if self.todo_badge.n:
                self.todo_x = x + 10
                self.todo_badge.draw(cr, x + 10, round((gh - 14) / 2))
        else:
            fd = text.font(10.5, "medium", mono=True)
            tw, th = text.size(self.status_text, fd)
            sx = W - 2 - 152
            text.draw(cr, self.status_text, sx + 132 - tw, (gh - 14) / 2, fd, self.status_color)
        if self.fx.active:
            self.fx.draw(cr)

    def dot_origin(self, gh):
        return (10 if self.open else 7), round((gh - 28) / 2)

    def collapsed_width(self):
        mw, _ = self.mini.size()
        meter = text.size(self.meter_text, text.font(10, "medium", mono=True))[0] if self.meter_text else 0
        return (41 + mw + (8 + meter if self.meter_text else 0) + (8 + self.visitors.width if self.visitors.tints else 0)
                + (10 + self.social.width if self.social.counts else 0) + (10 + self.todo_badge.width if self.todo_badge.n else 0) + 12)

    def fit_collapsed(self):
        if self.open or self.anim: return
        w2 = math.ceil(self.collapsed_width())
        if abs(self.size[0] - w2) > 0.5:
            self.size = (w2, self.h); self.panel.resize(w2, self.h); self.reposition()

    def lay(self):
        self.field.set_visible(self.open)
        self.mini.bobbing = self.mini.string == "Mochi" and not self.goo.sleeping and not self.open
        tip = self.tooltip_text()
        self.area.set_tooltip_text(tip)
        self.area.queue_draw()

    # -- animation --

    def tick(self):
        self.goo.step(self.pointer())
        self.visitors.t += 1 / 12
        self.area.queue_draw()
        return True

    def tick_wave(self):
        if self.mini.bobbing and not self.open:
            self.mini.t += 1 / 30; self.area.queue_draw()
        if self.fx.active: self.area.queue_draw()
        return True

    def pointer(self):
        """(dx, dy) from the goo's face to the pointer, y up; anywhere on screen on Hyprland, otherwise only over the pill"""
        w, h = self.size
        gx, gy = self.dot_origin(h - 2)
        fx, fy = 1 + gx + 16 - 4, 1 + gy + 14          # the face, in pill coordinates (y up)
        c = self.comp.cursor()
        if c is not None and self.monitor:
            ox, oy, _mw, mh = self.output()
            rl, _rt, _rr, rb = self.reserved()
            left = ox + rl + self.panel.left
            bottom = oy + mh - rb - self.panel.bottom        # screen y (down) of the pill's bottom edge
            return (c[0] - (left + fx), (bottom - fy) - c[1])
        if self.pointer_local is not None:
            x, y = self.pointer_local
            return (x - fx, (h - y) - fy)
        return None

    def note(self, s):
        self.recent = (self.recent + [f"{time.time() % 1000:.1f} {s}"])[-12:]

    # -- input --

    def on_key(self, ctl, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            # Esc clears and folds up (and if it's the other-answer prompt, goes back to normal)
            if self.answering_other: self.answering_other = False; self.reset_placeholder()
            self.field.set_text(""); self.set_open(False)
            return True
        if self.bubble and self.bubble.get_visible() and not self.field.get_text():
            if keyval == Gdk.KEY_Left: self.prev_page(); return True
            if keyval == Gdk.KEY_Right: self.next_page(); return True
        return False

    def on_active(self, *_):
        # click away with nothing typed: fold back up
        if not self.panel.is_active() and self.open and not self.field.get_text() and not self.sending:
            self.set_open(False)

    def drag_begin(self, g, x, y):
        c = self.comp.cursor()
        self.drag = {"cx": self.cx, "cursor": c[0] if c else None, "moved": False, "x": x}

    def drag_update(self, g, ox, oy):
        d = self.drag
        if d is None: return
        if not d["moved"] and abs(ox) < 4: return
        d["moved"] = True
        c = self.comp.cursor() if d["cursor"] is not None else None
        before = self.cx
        if c is not None:
            self.cx = d["cx"] + (c[0] - d["cursor"])
        else:
            # the surface moves under the pointer, so each offset is measured from where it now is
            self.cx += ox - (d.get("applied", 0))
            d["applied"] = 0
        _x, _y, mw, _mh = self.output()
        self.cx = min(max(self.cx, self.size[0] / 2 + 8), mw - self.size[0] / 2 - 8)
        self.reposition()
        # flung: the goo stretches behind and jiggles
        now = time.monotonic()
        dt = now - self.last_move[0]
        if 0 < dt < 0.1:
            vx = (self.cx - before) / dt
            if abs(vx) > 250: self.goo.fling(vx)
        self.last_move = (now, self.cx)

    def on_click(self, g, n, x, y):
        if self.drag and self.drag.get("moved"): return
        self.tapped(x, y)

    def tapped(self, x, y):
        if self.menu_panel and self.menu_panel.get_visible(): self.hide_menu(); return
        if self.open: return
        if self.todo_panel and self.todo_panel.get_visible() and self.todo_panel.get_opacity() > 0.5:
            self.hide_todo_list(); return
        gh = self.size[1] - 2
        yy = gh - (y - 1)
        # the checklist badge opens the to-do list
        if self.todo_badge.n and hasattr(self, "todo_x"):
            bx = x - 1 - self.todo_x
            if -5 <= bx <= self.todo_badge.width + 5 and -8 <= yy - round((gh - 14) / 2) <= 22:
                self.toggle_todo_list(); return
        # a click on a social badge jumps to that tab; anywhere else opens the bar
        if self.social.counts and hasattr(self, "social_x"):
            s = self.social.site_at(x - 1 - self.social_x)
            if s: self.open_social(s); return
        self.set_open(True)

    # grow or shrink around the bar's current bottom centre
    def set_open(self, o, grab=False):
        self.note(f"setOpen {o}")
        if o == self.open: return
        self.open = o
        target = (self.W, self.H) if o else (math.ceil(self.collapsed_width()), self.h)
        frm, t0 = self.size, time.monotonic()
        self.anim = True
        if o:
            # show the field now (not after the animation) so it can take typing straight away
            self.lay()
            self.panel.keyboard("exclusive" if grab else "on_demand")
            self.panel.present()
            self.field.grab_focus()
            if grab: later(400, lambda: self.open and self.panel.keyboard("on_demand"))
        else:
            self.field.set_visible(False)
            # hand the keyboard back to whatever you were in
            self.panel.keyboard("none")
            later(150, lambda: self.open or self.panel.keyboard("on_demand"))

        def step():
            k = min(1.0, (time.monotonic() - t0) / 0.22)
            e = k * k * (3 - 2 * k)
            self.size = (frm[0] + (target[0] - frm[0]) * e, frm[1] + (target[1] - frm[1]) * e)
            self.panel.resize(*self.size); self.reposition()
            if k >= 1:
                self.anim = None; self.size = target; self.panel.resize(*target); self.reposition(); self.lay()
                return False
            return True
        GLib.timeout_add(16, step)

    # ---------------------------------------------------------------- menus

    # her right-click menu: one of her own glass pop-ups (GTK's popover menus clip on layer surfaces)
    def install_actions(self):
        q = Gio.SimpleAction.new("quit", None)
        q.connect("activate", lambda *_: self.app.quit())
        self.app.add_action(q)

    def show_menu(self, x=0, y=0):
        if self.menu_panel is None:
            self.menu_panel = Floating(self.app, self.monitor)
            self.menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2); self.menu_box.add_css_class("glass")
            self.menu_box.add_css_class("menu")
            self.menu_panel.set_child(self.menu_box)
            mo = Gtk.EventControllerMotion()
            mo.connect("enter", lambda *_: setattr(self, "menu_hover", True))
            mo.connect("leave", lambda *_: setattr(self, "menu_hover", False))
            self.menu_box.add_controller(mo)
        box = self.menu_box
        while (c := box.get_first_child()) is not None: box.remove(c)

        def item(title, cb, check=None):
            row = Gtk.Box(spacing=8)
            row.append(ui.label("✓" if check else "", 12, classes=("cyan",), xalign=0.5))
            row.get_first_child().set_size_request(12, -1)
            row.append(ui.label(title, 13))
            b = ui.button(row, lambda: (self.hide_menu(), cb()), ("item",)); box.append(b)

        def sep():
            s_ = Gtk.Separator(); s_.add_css_class("sep"); box.append(s_)
        item("Open at Login", lambda: self.set_login(not self.login_enabled()), self.login_enabled())
        sep()
        box.append(ui.label("Mochi's color", 10, "medium", ("cyan",), mono=True))
        box.get_last_child().set_margin_start(10); box.get_last_child().set_margin_top(4)
        swatches = Gtk.Box(spacing=6); swatches.set_margin_start(10); swatches.set_margin_end(10); swatches.set_margin_top(4)
        swatches.set_margin_bottom(4)
        current = to_hex(self.colors.body)
        for name, h in PRESETS:
            sw = ui.button("", lambda h=h: (self.hide_menu(), self.set_color(hex_(h))), ("swatch",) + (("on",) if h == current else ()), tooltip=name)
            prov = Gtk.CssProvider()
            css = f"button {{ background-color: {h}; }}"
            try: prov.load_from_string(css)
            except AttributeError: prov.load_from_data(css, -1)
            sw.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
            swatches.append(sw)
        box.append(swatches)
        item("Custom color…", self.pick_color)
        sep()
        item("Quit Mochi", self.app.quit)
        W = 214
        p = self.menu_panel
        p.resize(W, ui.natural(box, W))
        p.set_opacity(1); self.place_above(p); p.set_visible(True); p.present()
        self.arm_menu_close(6)

    def arm_menu_close(self, secs):
        token = object(); self.menu_close = token
        def fire():
            if getattr(self, "menu_close", None) is not token: return False
            if self.menu_hover: self.arm_menu_close(2)
            else: self.hide_menu()
            return False
        GLib.timeout_add(int(secs * 1000), fire)

    def hide_menu(self):
        self.menu_close = None
        if self.menu_panel and self.menu_panel.get_visible(): self.menu_panel.set_visible(False)

    def tray_items(self):
        n = sum(1 for t in self.todos if t.get("done") is None)
        return [("Find Mochi", self.find_mochi), ("Message Mochi…", self.message_mochi),
                (f"To-do list ({n})" if n else "To-do list", self.open_todo_from_menu),
                ("Hide Mochi" if self.panel.get_visible() else "Show Mochi", self.toggle_shown), None,
                ("Open at Login", lambda: self.set_login(not self.login_enabled()), self.login_enabled()),
                ("Quit Mochi", self.app.quit)]

    # bring the pill to the bottom middle of the screen you're on, and say hi
    def find_mochi(self):
        name = self.comp.focused_monitor()
        if name and (not self.monitor or name != self.monitor.get_connector()):
            self.move_to_monitor(monitor_named(name))
        self.cx = None
        self.panel.set_visible(True); self.panel.present()
        self.reposition()
        self.goo.greet()

    def move_to_monitor(self, m):
        self.monitor = m
        for p in (self.panel, self.bubble, self.q_panel, self.now_panel, self.todo_panel, self.menu_panel):
            if p:
                vis = p.get_visible()
                if vis: p.set_visible(False)
                p.set_monitor(m)
                if vis: p.set_visible(True)

    def message_mochi(self):
        if not self.panel.get_visible(): self.find_mochi()
        self.set_open(True, grab=True)

    def open_todo_from_menu(self):
        if not self.panel.get_visible(): self.find_mochi()
        self.show_todo_list()

    def toggle_shown(self):
        if self.panel.get_visible():
            self.set_open(False); self.hide_bubble(); self.hide_todo_list()
            for p in (self.now_panel, self.q_panel):
                if p: p.set_visible(False)
            self.panel.set_visible(False)
        else:
            self.find_mochi()

    # -- colour --
    def set_color(self, c):
        self.colors = goo_colors(c); self.goo.colors = self.colors
        config.save_key("color", to_hex(c))
        self.tray.set_color(c)

    def pick_color(self):
        try:
            dlg = Gtk.ColorDialog(with_alpha=False, title="Mochi's Color")
        except (AttributeError, TypeError):
            return
        rgba = Gdk.RGBA(); rgba.red, rgba.green, rgba.blue, rgba.alpha = self.colors.body
        def done(d, res):
            try:
                c = d.choose_rgba_finish(res)
            except GLib.Error:
                return
            self.set_color((c.red, c.green, c.blue, 1.0))
        dlg.choose_rgba(None, rgba, None, done)

    # -- open at login: an XDG autostart entry --
    def login_enabled(self):
        return paths.AUTOSTART.exists()

    def set_login(self, on):
        try:
            if on:
                paths.AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
                exe = os.path.expanduser("~/.local/bin/mochi")
                paths.AUTOSTART.write_text("[Desktop Entry]\nType=Application\nName=Mochi\nComment=A little pixel goo that talks to Claude Code\n"
                                           f"Exec={exe if os.path.exists(exe) else 'mochi'}\nIcon=mochi\nX-GNOME-Autostart-enabled=true\n")
            elif paths.AUTOSTART.exists():
                paths.AUTOSTART.unlink()
        except OSError as e:
            paths.log(f"login item: {e}")

    # ---------------------------------------------------------------- what Claude Code tells her (the hook files)

    def check_reply(self):
        # thinking: a prompt went in after the last reply came out (and not too long ago)
        wm, lm = paths.mtime(paths.WORKING), paths.mtime(paths.LAST)
        self.goo.thinking = wm is not None and (lm is None or wm > lm) and time.time() - wm < 1800
        self.mini.bobbing = not self.open and self.mini.string == "Mochi" and not self.goo.sleeping

        # the meter: how long Claude has been at it, and how many tokens it has written this turn
        prog = {}
        if self.goo.thinking:
            p = read_json(paths.PROGRESS)
            if isinstance(p, dict): prog = p
        mt = ""
        if self.goo.thinking:
            secs = max(0, int(time.time() - wm))
            mt = "%d:%02d" % (secs // 60, secs % 60)
            tk = prog.get("tokens")
            if isinstance(tk, int) and tk > 0: mt += " · " + ("%.1fk" % (tk / 1000) if tk >= 1000 else str(tk))
        if mt != self.meter_text:
            self.meter_text = mt
            if not self.open: self.fit_collapsed()
            self.lay()
        # the step Claude is on
        step = ""
        if self.goo.thinking:
            d = read_json(paths.DOING)
            if isinstance(d, dict) and isinstance(d.get("text"), str) and d.get("time", 0) >= wm - 1: step = d["text"]
        if step != self.now_text:
            self.now_text = step; self.show_step(step)
        # what Claude says while it works (not just when it's done)
        said = prog.get("text")
        if isinstance(said, str) and said and said != self.progress_seen:
            self.progress_seen = said
            if not (self.q_panel and self.q_panel.get_visible()):
                self.show_bubble(said, (prog.get("project") or "") + " · working", react=False, full=said); self.goo.hop()

        # a question from Claude
        q = read_json(paths.QUESTION)
        if isinstance(q, dict) and q.get("id"):
            if q["id"] != self.q_shown:
                self.q_shown, self.q_data, self.q_index = q["id"], q, 0; self.show_question()
        elif self.q_panel and self.q_panel.get_visible():
            self.hide_question()

        # the to-do list changed on disk (Claude added something)
        if paths.mtime(paths.TODOS) != self.todo_mtime: self.reload_todos(announce=True)

        # good morning: once a day, how many things are on the list
        n_open = sum(1 for t in self.todos if t.get("done") is None)
        if (6 <= self.goo.hour < 12 and n_open > 0 and not self.goo.sleeping and self.state.get("nudgeDay") != today_start()
                and not (self.bubble and self.bubble.get_visible()) and not (self.q_panel and self.q_panel.get_visible())):
            self.state.set("nudgeDay", today_start())
            self.show_bubble(f"good morning! ☕ {n_open} thing{'' if n_open == 1 else 's'} on your to-do list. Click the checklist to see.",
                             "to-do", react=False); self.goo.hop()

        if lm is None or lm == self.last_seen: return
        self.last_seen = lm
        j = read_json(paths.LAST)
        if not isinstance(j, dict) or not j.get("text"): return
        self.progress_seen = ""
        self.show_bubble(j["text"], j.get("project", ""), full=j.get("full"))

    # ---------------------------------------------------------------- the reply bubble

    def make_bubble(self):
        self.bubble = Floating(self.app, self.monitor)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); box.add_css_class("glass")
        self.bubble.set_child(box)
        self.bubble_box = box
        click = Gtk.GestureClick(button=1)
        click.connect("released", lambda *_: self.hide_bubble())   # click to dismiss (the arrows handle their own clicks)
        box.add_controller(click)
        mo = Gtk.EventControllerMotion()
        mo.connect("enter", lambda *_: setattr(self, "bubble_hover", True))
        mo.connect("leave", lambda *_: setattr(self, "bubble_hover", False))
        box.add_controller(mo)

    def show_bubble(self, text_, project, react=True, full=None):
        self.note("bubble: " + text_[:30])
        # the goo reacts: a proud double hop with sparkles when something went live, otherwise a hop
        if react:
            if re.search(r"\b(live|pushed|deployed|shipped|published)\b", text_, re.I): self.goo.proud()
            else: self.goo.hop()
        if self.bubble is None: self.make_bubble()
        body = full if full and len(full) > len(text_) else text_
        self.bubble_project = "mochi · " + project
        fd = text.font(13)
        self.pages = ui.paginate(body, 352 - 28, 88, fd)
        if len(self.pages) > 1: self.pages = ui.paginate(body, 392 - 68, 88, fd)   # narrower, to make room for the arrows
        self.page = 0
        fresh = not self.bubble.get_visible() or self.bubble.get_opacity() < 1
        self.render_page()
        if fresh:
            self.bubble.set_opacity(0); self.bubble.set_visible(True); self.bubble.present()
            ui.fade(self.bubble, 1, 0.25)
        self.arm_hide(16 if len(self.pages) > 1 else 5 + len(body) / 25)

    def render_page(self):
        multi = len(self.pages) > 1
        W, pad = (392 if multi else 352), 14
        side = 34 if multi else pad
        tw = W - side * 2
        fd = text.font(13)
        def h(t): return math.ceil(text.size(t, fd, width=tw)[1])
        th = h(self.pages[self.page])
        max_th = max(h(p) for p in self.pages) if multi else th    # same height on every page
        box = self.bubble_box
        while (c := box.get_first_child()) is not None: box.remove(c)
        head = Gtk.Box(); head.set_margin_top(pad); head.set_margin_start(side); head.set_margin_end(side)
        head.append(ui.label(self.bubble_project, 10, "medium", ("cyan",), mono=True))
        if multi:
            sp = Gtk.Box(); sp.set_hexpand(True); head.append(sp)
            head.append(ui.label(f"{self.page + 1}/{len(self.pages)}", 10, "medium", ("faint",), mono=True))
        box.append(head)
        row = Gtk.Box(); row.set_margin_top(6); row.set_margin_bottom(pad)
        body = ui.label(self.pages[self.page], 13, wrap=tw); body.set_valign(Gtk.Align.START)
        body.set_size_request(tw, max_th)
        if multi:
            prev = ui.button("‹", self.prev_page, ("arrow",)); nxt = ui.button("›", self.next_page, ("arrow",))
            for b, ok in ((prev, self.page > 0), (nxt, self.page < len(self.pages) - 1)):
                b.set_size_request(26, max_th); b.set_sensitive(ok); b.set_opacity(1 if ok else 0.25)
            prev.set_margin_start(4); prev.set_margin_end(4); nxt.set_margin_start(4); nxt.set_margin_end(4)
            row.append(prev); row.append(body); row.append(nxt)
        else:
            body.set_margin_start(side); body.set_margin_end(side); row.append(body)
        box.append(row)
        H = pad + max_th + 6 + 14 + pad
        self.bubble.resize(W, max(H, ui.natural(box, W)))
        self.place_above(self.bubble)

    def prev_page(self):
        if self.page > 0: self.page -= 1; self.render_page(); self.arm_hide(16)

    def next_page(self):
        if self.page < len(self.pages) - 1: self.page += 1; self.render_page(); self.arm_hide(16)

    # hide after a while, but never while the mouse is resting on it
    def arm_hide(self, secs):
        if self.hide_src: GLib.source_remove(self.hide_src)
        def fire():
            self.hide_src = None
            if self.bubble_hover: self.arm_hide(3)
            else: self.hide_bubble()
            return False
        self.hide_src = GLib.timeout_add(int(secs * 1000), fire)

    def hide_bubble(self):
        if self.hide_src: GLib.source_remove(self.hide_src); self.hide_src = None
        b = self.bubble
        if b and b.get_visible(): ui.fade(b, 0, 0.3, lambda: b.set_visible(False))

    # sits just above the bar, centred on it, kept on screen. A question sits right on the bar; the others stack above it
    def place_above(self, p):
        bar = self.panel
        y = bar.top + 10
        n, q = self.now_panel, self.q_panel
        if p is not n and n and n.get_visible() and n.get_opacity() > 0: y = n.top + 6
        if p is not q and p is not n and q and q.get_visible(): y = q.top + 8
        _x, _y, mw, mh = self.output()
        rl, _rt, rr, _rb = self.reserved()
        mid = bar.left + bar.w / 2
        left = min(max(mid - p.w / 2, 8), mw - rl - rr - p.w - 8)
        p.place(left, y)

    def reposition_panels(self):
        for p in (self.now_panel, self.q_panel, self.bubble, self.todo_panel, self.menu_panel):
            if p and p.get_visible(): self.place_above(p)

    # ---------------------------------------------------------------- the step Claude is on

    def show_step(self, t):
        p = self.now_panel
        if not t:
            if p and p.get_visible():
                ui.fade(p, 0, 0.2, lambda: (p.set_visible(False), self.reposition_panels()))
            return
        if p is None:
            p = self.now_panel = Floating(self.app, self.monitor)
            box = Gtk.Box(); box.add_css_class("glass"); box.add_css_class("step")
            self.now_label = ui.label("", 10.5, "medium", mono=True)
            self.now_label.set_ellipsize(3)       # Pango.EllipsizeMode.END
            self.now_label.set_margin_start(11); self.now_label.set_margin_end(11); self.now_label.set_valign(Gtk.Align.CENTER)
            self.now_label.set_hexpand(True)
            box.append(self.now_label); p.set_child(box)
        self.now_label.set_label("› " + t)
        tw = text.size("› " + t, text.font(10.5, "medium", mono=True))[0]
        fresh = not p.get_visible() or p.get_opacity() < 1
        p.resize(min(420, tw + 24), 24)
        self.place_above(p)
        if fresh:
            p.set_opacity(0); p.set_visible(True); p.present(); ui.fade(p, 1, 0.2)
        self.reposition_panels()

    # ---------------------------------------------------------------- questions from Claude

    def show_question(self):
        self.note("question")
        j = self.q_data or {}
        qs = j.get("questions") or []
        if self.q_index >= len(qs): self.hide_question(); return
        q = qs[self.q_index]
        opts = q.get("options") or []
        multi = bool(q.get("multiSelect"))
        if self.q_panel is None:
            self.q_panel = Floating(self.app, self.monitor)
            self.q_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7); self.q_box.add_css_class("glass")
            self.q_panel.set_child(self.q_box)
        W, pad = 360, 14
        iw = W - 2 - pad * 2
        box = self.q_box
        while (c := box.get_first_child()) is not None: box.remove(c)
        views = [ui.label("mochi · claude is asking" + (f"   {self.q_index + 1} of {len(qs)}" if len(qs) > 1 else ""), 10, "medium", ("cyan",), mono=True),
                 ui.label(q.get("question", ""), 13.5, "semibold", wrap=iw)]
        if multi: views.append(ui.label("This one takes several picks, so answer it in your terminal.", 11.5, classes=("dim",), wrap=iw))
        for i, o in enumerate(opts): views.append(self.option(o.get("label", ""), o.get("description", ""), iw, i, not multi))
        if not multi: views.append(self.option("Other…", "Type your own answer in Mochi", iw, 1000, True))
        go = ui.button("Open in terminal ↗", self.open_question_tab, ("link",), size=11); go.set_halign(Gtk.Align.START)
        views.append(go)
        for v in views:
            v.set_margin_start(pad); v.set_margin_end(pad); box.append(v)
        views[0].set_margin_top(pad); views[-1].set_margin_bottom(pad)
        self.hide_bubble()
        p = self.q_panel
        p.resize(W, ui.natural(box, W))
        if not p.get_visible():
            p.set_opacity(0); self.place_above(p); p.set_visible(True); p.present(); ui.fade(p, 1, 0.25)
        else:
            self.place_above(p)
        self.reposition_panels()
        self.goo.asking = True; self.goo.hop(); self.goo.lookTo = 0; self.goo.lookY = 1

    def option(self, title, desc, width, tag, enabled):
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        inner.append(ui.label(title, 13, "semibold", wrap=width - 20))
        if desc: inner.append(ui.label(desc, 11.5, classes=("dim",), wrap=width - 20))
        if not enabled:
            inner.add_css_class("option"); inner.add_css_class("off"); return inner
        return ui.button(inner, lambda: self.pick_option(tag), ("option",))

    def pick_option(self, tag):
        if tag == 1000:
            self.answering_other = True; self.reset_placeholder("Your answer for Claude…"); self.set_open(True, grab=True); return
        self.answer(tag)

    def question_session(self):
        j = self.q_data or {}
        return terminals.session_for(j.get("pid", 0), j.get("tty", "")) or self.front_session()

    def open_question_tab(self):
        s = self.question_session()
        if s: self.sender.focus(s)

    # answer in Claude's terminal: Claude's question menu is numbered, so typing the option's number picks it
    # ("Other" is the number after the options, then the typed answer)
    def answer(self, i, other=None):
        j = self.q_data or {}
        qs = j.get("questions") or []
        if self.q_index >= len(qs): return
        n = len(qs[self.q_index].get("options") or [])
        s = self.question_session()
        if not s: self.failed("no Claude running"); return

        def done(err):
            if err: self.failed(err); return
            self.q_index += 1
            if self.q_index < len(qs):
                later(600, self.show_question)
            else:
                if len(qs) > 1: later(700, lambda: self.sender.press_return(s, lambda e: e and self.failed(e)))   # the "submit answers" step
                self.hide_question(); self.flash("answered ✓"); self.goo.proud()
        self.sender.answer(s, (n if i is None else i) + 1, other, done)

    def hide_question(self):
        self.goo.asking = False
        p = self.q_panel
        if p and p.get_visible(): ui.fade(p, 0, 0.25, lambda: (p.set_visible(False), self.reposition_panels()))

    # ---------------------------------------------------------------- to-do list

    def handle_todo(self, raw):
        r = todolist.parse(raw)
        if not r: return False
        kind, arg = r
        def done(): self.field.set_text(""); self.set_open(False)
        if kind == "add":
            self.todos.append(todolist.new(arg)); self.save_todos_now()
            done(); self.goo.hop(); self.goo.sparkT = self.goo.t
            self.show_bubble("added ✓  " + arg, "to-do", react=False)
            return True
        if kind == "show":
            done(); self.show_todo_list(); return True
        i = todolist.find_open(self.todos, arg)
        if i is None: return False      # not on the list: it's a message for Claude
        self.todos[i]["done"] = time.time(); self.save_todos_now()
        done(); self.goo.proud()
        self.show_bubble("checked off ✓  " + self.todos[i]["text"], "to-do", react=False)
        return True

    def save_todos_now(self):
        todolist.save(self.todos)
        self.todo_mtime = paths.mtime(paths.TODOS)
        self.todos_changed()

    def reload_todos(self, announce):
        fresh, had = todolist.load(), {t["id"] for t in self.todos}
        self.todo_mtime = paths.mtime(paths.TODOS)
        if announce:
            a = next((t for t in fresh if t["id"] not in had and t.get("done") is None), None)
            if a: self.show_bubble("added to your to-do list: " + a["text"], "to-do", react=False); self.goo.hop()
        self.todos = fresh; self.todos_changed()

    def todos_changed(self):
        self.todo_badge.n = sum(1 for t in self.todos if t.get("done") is None)
        if not self.open: self.fit_collapsed()
        self.lay()
        if self.todo_panel and self.todo_panel.get_visible() and self.todo_panel.get_opacity() > 0: self.show_todo_list()

    def toggle_todo_list(self):
        if self.todo_panel and self.todo_panel.get_visible(): self.hide_todo_list()
        else: self.show_todo_list()

    def show_todo_list(self):
        self.note("todo list")
        if self.todo_panel is None:
            self.todo_panel = Floating(self.app, self.monitor)
            self.todo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); self.todo_box.add_css_class("glass")
            self.todo_panel.set_child(self.todo_box)
            mo = Gtk.EventControllerMotion()
            mo.connect("enter", lambda *_: setattr(self, "todo_hover", True))
            mo.connect("leave", lambda *_: setattr(self, "todo_hover", False))
            self.todo_box.add_controller(mo)
        p, box = self.todo_panel, self.todo_box
        while (c := box.get_first_child()) is not None: box.remove(c)
        W, pad = 300, 14
        iw = W - 2 - pad * 2
        n_open = sum(1 for t in self.todos if t.get("done") is None)
        head = Gtk.Box()
        head.append(ui.label("mochi · to-do" + (f"   {n_open} open" if n_open else ""), 10, "medium", ("cyan",), mono=True))
        sp = Gtk.Box(); sp.set_hexpand(True); head.append(sp)
        head.append(ui.button("×", self.hide_todo_list, ("x",), size=16, tooltip="Close"))
        views = [head]
        items = sorted(self.todos, key=lambda t: (0 if t.get("done") is None else 1, t.get("added", 0)))
        if not items:
            views.append(ui.label("All clear ✨  Tell Mochi “todo: …” to add something.", 12, classes=("dim",), wrap=iw))
            # nothing left (and no badge to click): close on its own in a moment
            later(2200, lambda: not self.todos and self.hide_todo_list())
        for t in items[:14]: views.append(self.todo_row(t, iw))
        if any(t.get("done") is not None for t in items):
            c = ui.button("clear done", self.clear_done, ("link",), size=11); c.set_halign(Gtk.Align.START); views.append(c)
        for v in views:
            v.set_margin_start(pad); v.set_margin_end(pad); box.append(v)
        views[0].set_margin_top(8); views[-1].set_margin_bottom(pad)
        self.hide_bubble()
        p.resize(W, ui.natural(box, W))
        if not p.get_visible() or p.get_opacity() < 1:
            p.set_opacity(0); self.place_above(p); p.set_visible(True); p.present(); ui.fade(p, 1, 0.2)
        else:
            self.place_above(p)
        # Wayland doesn't tell apps about clicks elsewhere, so instead of closing on an outside click
        # the list closes after a while once the pointer isn't on it (or with ×, or a click on Mochi)
        self.arm_todo_close(12)

    def arm_todo_close(self, secs):
        token = object(); self.todo_close = token
        def fire():
            if getattr(self, "todo_close", None) is not token: return False
            if self.todo_hover: self.arm_todo_close(4)
            else: self.hide_todo_list()
            return False
        GLib.timeout_add(int(secs * 1000), fire)

    def todo_row(self, t, width):
        done = t.get("done") is not None
        row = Gtk.Box(spacing=6)
        chk = ui.button("✓" if done else "", lambda: self.toggle_todo(t["id"]), ("check",) + (("on",) if done else ()),
                        size=10, tooltip="Done" if done else "Not done")
        chk.set_valign(Gtk.Align.START); row.append(chk)
        age = ui.label(todolist.ago(t.get("done") or t.get("added", time.time())), 10, classes=("faint",), mono=True)
        aw = text.size(age.get_label(), text.font(10, mono=True))[0]
        tl = ui.label(t["text"], 13, classes=("done",) if done else (), wrap=width - 26 - aw - 6 - 18)
        tl.set_hexpand(True); row.append(tl)
        age.set_valign(Gtk.Align.START); age.set_margin_top(3); row.append(age)
        d = ui.button("×", lambda: self.delete_todo(t["id"]), ("del",), size=14, tooltip="Remove"); d.set_valign(Gtk.Align.START)
        row.append(d)
        return row

    def toggle_todo(self, tid):
        for t in self.todos:
            if t["id"] == tid:
                t["done"] = None if t.get("done") is not None else time.time()
                if t["done"]: self.goo.hop(); self.goo.sparkT = self.goo.t
        self.save_todos_now()

    def delete_todo(self, tid):
        self.todos = [t for t in self.todos if t["id"] != tid]; self.save_todos_now()

    def clear_done(self):
        self.todos = [t for t in self.todos if t.get("done") is None]; self.save_todos_now()

    def hide_todo_list(self):
        self.todo_close = None
        p = self.todo_panel
        if p and p.get_visible(): ui.fade(p, 0, 0.2, lambda: p.set_visible(False))

    # ---------------------------------------------------------------- social (a slot for a source plug-in)

    def check_social(self):
        best = {"ig": 3, "li": 12, "th": 1} if "social" in ENV.get("PB_DEMO", "") else {}   # for checking the look
        self.social.counts = [(s, best[s.key]) for s in SOCIAL_SITES if best.get(s.key, 0) > 0]
        if self.social_seen is not None:
            ups = [f"{best.get(s.key, 0) - self.social_seen.get(s.key, 0)} new on {s.name}" for s in SOCIAL_SITES
                   if best.get(s.key, 0) - self.social_seen.get(s.key, 0) > 0]
            if ups: self.show_bubble(" · ".join(ups), "notifications", react=False); self.goo.hop()
        self.social_seen = best
        if not self.open: self.fit_collapsed()
        self.lay()

    def open_social(self, site):
        pass   # a source plug-in can jump to the site's tab here

    # (the visitors strip is kept for anyone who wants to feed it their own list: call show_visitors with [{"name", "tint", "page", "id"}])
    def show_visitors(self, here):
        tint = {"mint": hex_("#7ad3a3"), "lilac": hex_("#b89bff"), "sky": hex_("#8cc1ff")}
        self.visitors.tints = [tint.get(m.get("tint", ""), hex_("#7ad3a3")) for m in here]
        def place(m):
            p = (m.get("page") or "").replace(".html", "")
            return p[4:] if p.startswith("app#") else "home" if p in ("app", "") else p
        self.visitor_note = "" if not here else "Here now:\n" + "\n".join(f"{m.get('name', 'Someone')} · {place(m)}" for m in here)
        ids = {m.get("id") for m in here}
        if self.seen_visitors is not None:
            m = next((m for m in here if m.get("id") not in self.seen_visitors), None)
            if m: self.goo.greet(); self.show_bubble(f"{m.get('name', 'Someone')} just arrived on {place(m)}", "", react=False)
        self.seen_visitors = ids
        if not self.open: self.fit_collapsed()
        self.lay()

    def tooltip_text(self):
        parts = []
        if self.social.counts: parts.append(" · ".join(f"{s.name}: {n}" for s, n in self.social.counts))
        if self.visitor_note: parts.append(self.visitor_note)
        return "\n\n".join(parts) or None

    # ---------------------------------------------------------------- sending

    def front_session(self, ss=None):
        """the Claude to talk to: the one whose terminal you were in most recently, else the newest"""
        ss = terminals.sessions() if ss is None else ss
        if not ss: return None
        wins = self.comp.windows()
        def recency(s):
            pids = set(s.terminal_pids())
            r = [w.recent for w in wins if w.pid in pids]
            return min(r) if r else 1e9
        return min(ss, key=lambda s: (recency(s), -s.start))

    def send(self):
        t = self.field.get_text().strip()
        if not t or self.sending: return
        if self.answering_other:
            self.answering_other = False; self.reset_placeholder(); self.field.set_text(""); self.set_open(False)
            self.answer(None, other=t); return
        if self.handle_todo(t): return
        self.sending = True
        s = self.front_session()
        if s is None: self.wake(t); return
        self.deliver(s, t)

    def deliver(self, s, t):
        self.note(f"send via {self.sender.route(s)}")
        def done(err):
            if err: self.failed(err); return
            self.field.set_text("")
            self.celebrate_send()
        self.sender.send(s, t, done)

    # no Claude running anywhere: open a terminal running `claude --continue`, wait for it, then send
    def wake(self, t):
        cmd = terminals.wake_command(self.cfg)
        if not cmd: self.failed("no terminal found"); return
        self.status_text, self.status_color = "waking Claude…", CYAN_TEXT
        self.field.set_editable(False)
        self.goo.hop()
        before = {s.pid for s in terminals.sessions()}
        try:
            terminals.spawn(cmd)
        except OSError as e:
            self.field.set_editable(True); self.failed(str(e)); return
        tries = [0]
        def check():
            tries[0] += 1
            new = [s for s in terminals.sessions() if s.pid not in before]
            if new:
                # it's up: give it a moment to draw its prompt, then send
                def go():
                    self.field.set_editable(True); self.status_text, self.status_color = STATUS_IDLE, white(0.6)
                    self.deliver(new[0], t)
                later(3000, go)
            elif tries[0] < 40:
                later(500, check)
            else:
                self.field.set_editable(True); self.sending = False; self.goo.worry(); self.flash("couldn't wake Claude", False)
        later(500, check)

    def reset_placeholder(self, s="Message Mochi…"):
        self.field.set_placeholder_text(s)

    # a short note in whichever label is showing
    def flash(self, s, ok=True):
        c = CYAN_TEXT if ok else rgb(1, 0.55, 0.55, 0.95)
        self.status_text, self.status_color = s, c
        self.mini.string, self.mini.color = s, c
        self.fit_collapsed(); self.lay()
        def back():
            self.status_text, self.status_color = STATUS_IDLE, white(0.6)
            self.mini.string, self.mini.color = "Mochi", white(0.85)
            self.fit_collapsed(); self.lay()
        later(2000, back)

    # say what went wrong, and keep the details in the log
    def failed(self, err):
        self.sending = False
        paths.log(f"send failed: {err} (recent: {' | '.join(self.recent)})")
        self.goo.worry()
        short = err if len(err) <= 22 else err.split(":")[0][:22]
        self.flash(short, False)

    def celebrate_send(self):
        self.flash("sent ✓")
        # a snack for the goo (a little rounder each message, back to normal tomorrow)
        st, today = self.state, today_start()
        if st.get("fedDay") != today: st.set("fedDay", today); st.set("fed", 0)
        st.set("fed", st.get("fed", 0) + 1); self.goo.fed = st.get("fed")
        # the goo springs up and throws a paper plane across the bar to "→ Claude", then lands with a splat
        self.goo.throw_it()
        self.sending = True
        gh = self.H - 2
        dx, dy = self.dot_origin(gh)
        frm = (dx + 16, dy + 14 + 4)
        to = (self.W - 2 - 152 + 30, (gh - 14) / 2 + 7 - 2)
        later(300, lambda: self.fx.launch(frm, to, self.colors.body, self.colors.shine))
        def end(): self.sending = False; self.set_open(False)
        later(1250, end)
