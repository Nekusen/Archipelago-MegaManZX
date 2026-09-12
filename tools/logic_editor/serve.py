#!/usr/bin/env python3
"""Local server of the visual logic editor.

Serves the interface in this folder, the room renders, the world data and the
document logic/logic.json; every save regenerates logic.txt and returns the
validation report. Standard library only.

Usage (from the apworld root):
    python tools/logic_editor/serve.py [--port N] [--no-browser] [--renders DIR] [--gimmicks FILE]

API (JSON):
    GET  /api/world      rooms, locations, edges, gimmicks, atoms, boss roster
    GET  /api/logic      current document, or an empty skeleton
    GET  /api/txt        the text twin
    POST /api/logic      save; the response is the validation report
    POST /api/validate   validate without saving
    POST /api/reload     reread data.py and the gimmicks
    GET  /renders/<room>.png
"""

import argparse
import importlib.util
import json
import struct
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # apworld root
STATIC = Path(__file__).resolve().parent
RENDERS = STATIC / "local" / "renders"              # 1:1 renders, not in git; --renders
GIMMICKS = STATIC / "data" / "gimmicks.json"        # named gimmicks; --gimmicks
LOGIC_DIR = ROOT / "logic"
LOGIC_JSON = LOGIC_DIR / "logic.json"
LOGIC_TXT = LOGIC_DIR / "logic.txt"



def _load_logic_format():
    """Load logic/document.py by path.

    Putting the package on sys.path would shadow the venv with its vendored packages.
    """
    spec = importlib.util.spec_from_file_location("mmzx_logic_document", ROOT / "logic" / "document.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


F = _load_logic_format()

def load_data():
    spec = importlib.util.spec_from_file_location("mmzx_data_editor", ROOT / "data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def png_size(path: Path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return [w, h]


def load_gimmicks(rooms):
    """{room: [{name, kind, sub, role, mod, pos, layer}]} from gimmicks.json.

    Doors are not included. Without the file the editor works without the layer.
    """
    out = {r: [] for r in rooms}
    if not GIMMICKS.exists():
        print("[serve] no gimmicks: missing %s" % GIMMICKS)
        return out
    data = json.load(open(GIMMICKS, encoding="utf-8"))
    for room, items in data.items():
        if room in out:
            out[room] = items
    return out


class WorldCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.D = None
        self.world = None
        self.payload = None

    def get(self):
        with self.lock:
            if self.payload is None:
                self.build()
            return self.D, self.world, self.payload

    def build(self):
        D = load_data()
        world = F.build_world(D)
        rooms = {}
        for r in world["rooms"]:
            p = RENDERS / (r + ".png")
            rooms[r] = {"label": world["room_label"][r], "area": r[:1],
                        "size": png_size(p) if p.exists() else None,
                        "sub": D.ROOM_SUBAREA.get(r), "render": p.exists()}
        sub = D.STARTING_TRANSERVERS.get("guardian_hub", (70,))[0]
        start_room = next((r for r, s in D.ROOM_SUBAREA.items() if s == sub), D.HUB_ROOM)
        gate_edges = {}
        for e in world["edges"]:
            if e.get("gate") is not None:
                gate_edges.setdefault(str(e["gate"]), []).append(e["name"])
        unavailable = sorted(F.unavailable_atoms(D))
        self.D, self.world = D, world
        self.payload = {
            "unavailable_atoms": unavailable,
            "unavailable_items": sorted(n for n, v in D.ITEMS.items() if not v.get("pooled", True) and n != "Model Hu"),
            "rooms": rooms,
            "room_order": world["rooms"],
            "locations": world["locations"],
            "edges": world["edges"],
            "gimmicks": load_gimmicks(world["rooms"]),
            "atoms": F.atom_catalog(exclude=unavailable),
            "tiers": F.TIERS,
            "hub": world["hub"],
            "start_room": start_room,
            "hub_floor_y": world["hub_floor_y"],
            "transerver_access": world["transerver_access"],
            "event_gates_open": world["event_gates_open"],
            "gate_edges": gate_edges,
            # boss roster for the arena tag; the requirement comes from the YAML
            "bosses": [{"id": b, "name": v["name"], "room": v["room"],
                        "room_label": F.room_label(v["room"]),
                        "pseudoroid": "index" in v}
                       for b, v in F.BOSSES.items()],
        }


CACHE = WorldCache()
SAVE_LOCK = threading.Lock()


def save_document(doc):
    D, world, payload = CACHE.get()
    doc = F.normalize_logic(doc, world)
    report = F.validate(world, doc, payload["start_room"], payload["unavailable_atoms"])
    with SAVE_LOCK:
        LOGIC_DIR.mkdir(parents=True, exist_ok=True)
        F.save_logic(LOGIC_JSON, doc)
        if not report["errors"]:
            LOGIC_TXT.write_text(F.export_txt(world, doc, payload["start_room"]), encoding="utf-8", newline="\n")
    report["saved"] = True
    report["txt"] = not report["errors"]
    return report


class Handler(BaseHTTPRequestHandler):
    server_version = "mmzx-logic-editor/1"

    def log_message(self, fmt, *args):
        if self.path.startswith("/renders/"):
            return
        sys.stderr.write("[serve] %s\n" % (fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        try:
            if path in ("/", "/index.html"):
                return self._static("index.html", "text/html; charset=utf-8")
            if path == "/style.css":
                return self._static("style.css", "text/css; charset=utf-8")
            if path.startswith("/js/"):
                name = path[len("/js/"):]
                if "/" in name or ".." in name or not name.endswith(".js"):
                    return self._send(404, {"error": "not found"})
                return self._static("js/" + name, "text/javascript; charset=utf-8")
            if path == "/api/world":
                return self._send(200, CACHE.get()[2])
            if path == "/api/logic":
                _, world, _ = CACHE.get()
                return self._send(200, F.load_logic(LOGIC_JSON, world))
            if path == "/api/txt":
                return self._send(200, LOGIC_TXT.read_text(encoding="utf-8") if LOGIC_TXT.exists() else "",
                                  "text/plain; charset=utf-8")
            if path.startswith("/renders/"):
                name = path[len("/renders/"):]
                if "/" in name or ".." in name or not name.endswith(".png"):
                    return self._send(404, {"error": "not found"})
                p = RENDERS / name
                if not p.exists():
                    return self._send(404, {"error": "render not found"})
                return self._send(200, p.read_bytes(), "image/png")
            return self._send(404, {"error": "not found"})
        except Exception as ex:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": str(ex)})

    def _static(self, name, ctype):
        p = STATIC / name
        if not p.exists():
            return self._send(404, "missing %s" % name, "text/plain; charset=utf-8")
        return self._send(200, p.read_bytes(), ctype)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            doc = json.loads(raw.decode("utf-8"))
            if path == "/api/logic":
                return self._send(200, save_document(doc))
            if path == "/api/validate":
                _, world, payload = CACHE.get()
                doc = F.normalize_logic(doc, world)
                return self._send(200, F.validate(world, doc, payload["start_room"], payload["unavailable_atoms"]))
            if path == "/api/reload":
                CACHE.payload = None
                return self._send(200, {"ok": True})
            return self._send(404, {"error": "not found"})
        except Exception as ex:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": str(ex)})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--renders", default=None,
                    help="folder with the 1:1 renders <room>.png (default tools/logic_editor/local/renders)")
    ap.add_argument("--gimmicks", default=None,
                    help="JSON of named gimmicks (default tools/logic_editor/data/gimmicks.json)")
    a = ap.parse_args()
    global RENDERS, GIMMICKS
    if a.renders:
        RENDERS = Path(a.renders).resolve()
    if a.gimmicks:
        GIMMICKS = Path(a.gimmicks).resolve()
    D, world, payload = CACHE.get()
    missing = [r for r, v in payload["rooms"].items() if not v["render"]]
    print("[serve] %d rooms, %d locations, %d edges; missing renders: %s" % (
        len(world["rooms"]), len(world["locations"]), len(world["edges"]), missing or "none"))
    if missing:
        print("[serve] renders in %s (see README: they are generated from YOUR ROM with the Mega Man ZX Editor; not in the repo)"
              % RENDERS)
    print("[serve] document: %s (%s)" % (LOGIC_JSON, "exists" if LOGIC_JSON.exists() else "new"))
    url = "http://127.0.0.1:%d/" % a.port
    print("[serve] " + url + "  (Ctrl+C to stop)")
    httpd = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
