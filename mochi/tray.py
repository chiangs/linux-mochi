# the little goo in the system tray (Waybar, KDE, …), so Mochi is always findable: a StatusNotifierItem with a dbusmenu menu,
# spoken directly over D-Bus with Gio (no extra libraries). If no tray is running, nothing happens.
#
# items() is called each time the menu opens, so the to-do count and Show/Hide are current. Each item is
# (label, callback) or (label, callback, checked) or None for a separator.
import os

from gi.repository import Gio, GLib

SNI_XML = """
<node><interface name="org.kde.StatusNotifierItem">
  <property name="Category" type="s" access="read"/><property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/><property name="Status" type="s" access="read"/>
  <property name="IconName" type="s" access="read"/><property name="IconPixmap" type="a(iiay)" access="read"/>
  <property name="ToolTip" type="(sa(iiay)ss)" access="read"/><property name="ItemIsMenu" type="b" access="read"/>
  <property name="Menu" type="o" access="read"/>
  <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
  <signal name="NewIcon"/><signal name="NewToolTip"/><signal name="NewStatus"><arg type="s"/></signal>
</interface></node>"""

MENU_XML = """
<node><interface name="com.canonical.dbusmenu">
  <property name="Version" type="u" access="read"/><property name="TextDirection" type="s" access="read"/>
  <property name="Status" type="s" access="read"/><property name="IconThemePath" type="as" access="read"/>
  <method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
    <arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method>
  <method name="GetGroupProperties"><arg type="ai" direction="in"/><arg type="as" direction="in"/><arg type="a(ia{sv})" direction="out"/></method>
  <method name="GetProperty"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
  <method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/></method>
  <method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>
  <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
  <method name="AboutToShowGroup"><arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/></method>
  <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
  <signal name="ItemsPropertiesUpdated"><arg type="a(ia{sv})"/><arg type="a(ias)"/></signal>
</interface></node>"""

# a 9×8 pixel goo
SHAPE = ["..XXXXX..", ".XXXXXXX.", "XXXXXXXXX", "XX.XXX.XX", "XX.XXX.XX", "XXXXXXXXX", "XXXXXXXXX", "XXXXXXXXX"]


def pixmap(color, size=22):
    """ARGB32 (network byte order) pixels of the goo in her colour, scaled into a size×size square"""
    cell = size // 10
    ox, oy = (size - 9 * cell) // 2, (size - 8 * cell) // 2 + cell // 2
    r, g, b = (int(c * 255) for c in color[:3])
    er, eg, eb = int(r * 0.62), int(g * 0.62), int(b * 0.62)
    buf = bytearray(size * size * 4)
    for row, line in enumerate(SHAPE):
        for col, ch in enumerate(line):
            px = (255, r, g, b) if ch == "X" else (255, 8, 30, 60) if row in (3, 4) else None
            if row == 0 or (ch == "X" and (col in (0, 8) or line[col - 1] != "X" or col + 1 >= 9 or line[col + 1] != "X")):
                px = (255, er, eg, eb) if ch == "X" else px
            if not px: continue
            for y in range(cell):
                for x in range(cell):
                    i = ((oy + row * cell + y) * size + ox + col * cell + x) * 4
                    buf[i:i + 4] = bytes(px)
    return [(size, size, bytes(buf))]


class Tray:
    def __init__(self, items, on_activate, color):
        self.items, self.on_activate, self.color = items, on_activate, color
        self.revision, self.current = 1, []
        self.bus = None
        self.name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        Gio.bus_get(Gio.BusType.SESSION, None, self._got_bus)

    def _got_bus(self, _src, res):
        try:
            self.bus = Gio.bus_get_finish(res)
        except GLib.Error:
            return
        sni = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
        menu = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self.bus.register_object("/StatusNotifierItem", sni, self._sni_call, self._sni_get, None)
        self.bus.register_object("/MenuBar", menu, self._menu_call, self._menu_get, None)
        Gio.bus_own_name_on_connection(self.bus, self.name, Gio.BusNameOwnerFlags.NONE, self._register, None)

    def _register(self, *_):
        # tell the tray we're here (and again whenever a tray starts later)
        def reg(*_a):
            self.bus.call("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher",
                          "RegisterStatusNotifierItem", GLib.Variant("(s)", (self.name,)), None, Gio.DBusCallFlags.NONE, -1, None, None)
        reg()
        Gio.bus_watch_name_on_connection(self.bus, "org.kde.StatusNotifierWatcher", Gio.BusNameWatcherFlags.NONE, reg, None)

    def set_color(self, color):
        self.color = color
        if self.bus: self.bus.emit_signal(None, "/StatusNotifierItem", "org.kde.StatusNotifierItem", "NewIcon", None)

    # -- StatusNotifierItem --
    def _sni_get(self, _c, _s, _p, _i, prop):
        return {"Category": GLib.Variant("s", "ApplicationStatus"), "Id": GLib.Variant("s", "mochi"),
                "Title": GLib.Variant("s", "Mochi"), "Status": GLib.Variant("s", "Active"),
                "IconName": GLib.Variant("s", ""), "IconPixmap": GLib.Variant("a(iiay)", pixmap(self.color)),
                "ToolTip": GLib.Variant("(sa(iiay)ss)", ("", [], "Mochi", "")), "ItemIsMenu": GLib.Variant("b", False),
                "Menu": GLib.Variant("o", "/MenuBar")}.get(prop)

    def _sni_call(self, _c, _s, _p, _i, method, _params, inv):
        if method in ("Activate", "SecondaryActivate"): GLib.idle_add(lambda: (self.on_activate(), False)[1])
        inv.return_value(None)

    # -- dbusmenu --
    def _menu_get(self, _c, _s, _p, _i, prop):
        return {"Version": GLib.Variant("u", 3), "TextDirection": GLib.Variant("s", "ltr"),
                "Status": GLib.Variant("s", "normal"), "IconThemePath": GLib.Variant("as", [])}.get(prop)

    def _props(self, i):
        it = self.current[i - 1]
        if it is None: return {"type": GLib.Variant("s", "separator")}
        p = {"label": GLib.Variant("s", it[0].replace("_", "__")), "enabled": GLib.Variant("b", True), "visible": GLib.Variant("b", True)}
        if len(it) > 2:
            p["toggle-type"] = GLib.Variant("s", "checkmark"); p["toggle-state"] = GLib.Variant("i", 1 if it[2] else 0)
        return p

    def _layout(self):
        self.current = list(self.items())
        kids = [GLib.Variant("(ia{sv}av)", (i, self._props(i), [])) for i in range(1, len(self.current) + 1)]
        return (0, {"children-display": GLib.Variant("s", "submenu")}, kids)

    def _menu_call(self, _c, _s, _p, _i, method, params, inv):
        if method == "GetLayout":
            inv.return_value(GLib.Variant("(u(ia{sv}av))", (self.revision, self._layout())))
        elif method == "GetGroupProperties":
            ids = params.unpack()[0] or range(1, len(self.current) + 1)
            inv.return_value(GLib.Variant("(a(ia{sv}))", ([(i, self._props(i)) for i in ids if 0 < i <= len(self.current)],)))
        elif method == "GetProperty":
            i, name = params.unpack()
            p = self._props(i) if 0 < i <= len(self.current) else {}
            inv.return_value(GLib.Variant("(v)", (p.get(name, GLib.Variant("s", "")),)))
        elif method == "Event":
            i, ev, _d, _t = params.unpack()
            if ev == "clicked" and 0 < i <= len(self.current) and self.current[i - 1]:
                cb = self.current[i - 1][1]
                GLib.idle_add(lambda: (cb(), False)[1])
            inv.return_value(None)
        elif method == "EventGroup":
            for i, ev, _d, _t in params.unpack()[0]:
                if ev == "clicked" and 0 < i <= len(self.current) and self.current[i - 1]:
                    cb = self.current[i - 1][1]
                    GLib.idle_add(lambda cb=cb: (cb(), False)[1])
            inv.return_value(GLib.Variant("(ai)", ([],)))
        elif method == "AboutToShow":
            # rebuild so the counts are current
            self.revision += 1
            self._layout()
            self.bus.emit_signal(None, "/MenuBar", "com.canonical.dbusmenu", "LayoutUpdated", GLib.Variant("(ui)", (self.revision, 0)))
            inv.return_value(GLib.Variant("(b)", (True,)))
        elif method == "AboutToShowGroup":
            inv.return_value(GLib.Variant("(aiai)", ([], [])))
        else:
            inv.return_value(None)
