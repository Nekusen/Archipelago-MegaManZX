#!/usr/bin/env python3
"""normalize_names.py - normalizes the region NAMES (and rids) of
logic/logic.json to a fixed standard WITHOUT changing the logic:
polygons, connections, requirements, checks and placements stay the same;
only `regions[rid].name`, the `rid` (slug of the new name) and the rid
references (conns from/to, members) change. User decision (2026-09-04):
"I prefer a fixed standard even if I am a mess with names". Standard
(docs/logic_editor.md, Names section):

  <Room> Entrance      region whose doors to OTHER rooms all lead to the
                       same room (e.g. "E-5 Entrance"); if two regions of
                       the room lead to the same one, the original name is
                       kept in parentheses: "E-4 Entrance (Bottom Area)"
  Hub Entrance         region with the Transerver pad (warp to the hub)
  Save Pad             region with a save-only pad (no Transport)
  Boss Room / Mini-Boss Room / Before Boss Room / After Boss Room
  Middle Area          passage zone between entrances ("Middle Part")
  Upper/Lower/Left/Right Area (and combinations: "Upper Right Area")
  Nth Floor / Nth Floor Room / Nth Floor Room (Outside) / Basement Room
  Descriptive names: Title Case, room codes with a hyphen ("A-2")

Usage: python tools/logic_editor/normalize_names.py [--dry-run] [--json path]
Prints the rename table. With --dry-run nothing is written.
"""
import argparse
import importlib.util
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))
import logic_format as F  # noqa: E402

DIRECTIONAL = re.compile(r"^(Left|Right|West|East|North|South|Top|Bottom|Upper|Lower)\s+Entrance$", re.I)
ZONE_MAP = OrderedDict([
    (r"^Upper Side$", "Upper Area"), (r"^Top Area$", "Upper Area"), (r"^Top Part$", "Upper Area"),
    (r"^Top$", "Upper Area"), (r"^Bottom Area$", "Lower Area"), (r"^Bottom$", "Lower Area"),
    (r"^Bottom Part$", "Lower Area"), (r"^Left Side$", "Left Area"), (r"^Right Side$", "Right Area"),
    (r"^Top Right Side$", "Upper Right Area"), (r"^Top Right Area$", "Upper Right Area"),
    (r"^Bottom Right Side$", "Lower Right Area"), (r"^Bottom Left Side$", "Lower Left Area"),
    (r"^Middle Part$", "Middle Area"), (r"^Boss Area$", "Boss Room"), (r"^Boss Arena$", "Boss Room"),
    (r"^Final Boss Room$", "Boss Room"), (r"^Mini-Boss$", "Mini-Boss Room"), (r"^Mini Boss Room$", "Mini-Boss Room"),
    (r"^Before Boss$", "Before Boss Room"), (r"^After Boss$", "After Boss Room"),
    (r"^After Mini-Boss$", "After Mini-Boss Room"),
    (r"^Basement - Room$", "Basement Room"), (r"^(\d+(?:st|nd|rd|th) Floor Room) - Outside$", r"\1 (Outside)"),
    (r"^Hub Area$", "Hub Entrance"), (r"^Hub Door$", "Hub Entrance"), (r"^Save Room Area$", "Hub Entrance"),
    (r"^Save Point Entrance$", "Hub Entrance"),
    (r"^Left Side Cave$", "Left Area Cave"), (r"^Upper Side Cave$", "Upper Area Cave"),
    (r"^Right Side \(Before Boss\)$", "Right Area (Before Boss)"), (r"^Right Side \(After Boss\)$", "Right Area (After Boss)"),
    (r"^Left Side of Door Switch$", "Left Area (Door Switch)"),
    (r"^F3- Entrance$", "F-3 Entrance"),
])
ROOM_CODE = re.compile(r"\b([A-OX])(\d)\b")          # "A2" -> "A-2"


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "region"


def door_targets(world, doc, members, room, rid):
    """Destination rooms of the doors/warps that LEAVE the region (no internal ones)."""
    out, hub_warp, save_pad = set(), False, False
    hubish = lambda e: e["kind"] in ("warp", "save") or "corridor" in e["name"]   # pad + floor corridors
    for e in world["edges"]:
        if e["src"] != room or members[room].get(e["name"], "main") != rid:
            continue
        if e["dst"] == room:
            continue
        if hubish(e):
            hub_warp = hub_warp or e["kind"] == "warp" or "corridor" in e["name"]
            save_pad = save_pad or e["kind"] == "save"
        else:
            out.add(e["dst"])
    for e in world["edges"]:   # arrivals from other rooms (for arrival-only lobbies)
        if e["dst"] != room or e["src"] == room:
            continue
        if members[room].get(e["name"] + "@in", "main") == rid:
            if hubish(e):
                hub_warp = hub_warp or e["kind"] == "warp" or "corridor" in e["name"]
                save_pad = save_pad or e["kind"] == "save"
            else:
                out.add(e["src"])
    return out, hub_warp, save_pad


def region_has_checks(world, doc, members, room, rid):
    edges = {e["name"] for e in world["edges"]}
    return any(not n.endswith("@in") and n not in edges and m == rid for n, m in members[room].items())


def normalize(world, doc):
    members = F.resolve_members(world, doc)
    changes = []
    for room in world["rooms"]:
        rl = doc["rooms"][room]
        regs = rl["regions"]
        new_names = {}
        for rid, reg in regs.items():
            if rid == "main":
                continue
            name = (reg.get("name") or rid).strip()
            name = re.sub(r"\s+", " ", name)
            name = ROOM_CODE.sub(lambda m: "%s-%s" % (m.group(1), m.group(2)), name)
            for pat, rep_ in ZONE_MAP.items():
                if re.match(pat, name, re.I):
                    name = re.sub(pat, rep_, name, flags=re.I)
                    break
            targets, hub_warp, save_pad = door_targets(world, doc, members, room, rid)
            # entrance: by name, or by structure (no checks and only doors to one room / to the hub)
            is_entrance_like = bool(DIRECTIONAL.match(name)) or name.endswith("Entrance") or name in ("Hub Entrance", "Save Pad")
            if name == "I-5" and room == "i02":
                is_entrance_like = True
            series = bool(re.match(r"^(\d+(st|nd|rd|th) Floor|Basement)", name))   # series names: kept as they are
            only_doors = (not series and not region_has_checks(world, doc, members, room, rid)
                          and (targets or hub_warp or save_pad))
            if is_entrance_like or only_doors:
                if len(targets) == 1 and not (hub_warp or save_pad):
                    dst = next(iter(targets))
                    name = "%s Entrance" % world["room_label"][dst]
                elif not targets and (hub_warp or save_pad):
                    name = "Hub Entrance"
            new_names[rid] = name
        # collisions inside the room: keep the original name in parentheses
        # collisions by BASE name (without the trailing parenthesis): "A-2 Entrance" and
        # "A-2 Entrance (Top Part)" form a group -> all of them get a tag
        base_of = lambda n: re.sub(r"\s*\([^()]*\)$", "", n).strip()
        seen = {}
        for rid, name in new_names.items():
            seen.setdefault(base_of(name), []).append(rid)
        for base, rids in seen.items():
            if len(rids) > 1:
                for rid in rids:
                    cur = new_names[rid]
                    orig = ROOM_CODE.sub(lambda m: "%s-%s" % (m.group(1), m.group(2)), (regs[rid].get("name") or rid).strip())
                    tag = cur[len(base):].strip(" ()") if cur.startswith(base) and len(cur) > len(base) else ""
                    if not tag:
                        tag = orig[len(base):].strip(" ()") if orig.startswith(base) else orig
                        tag = re.sub(r"\s*Entrance$", "", tag).strip()   # "After Mini-Boss Entrance" -> "After Mini-Boss"
                    new_names[rid] = "%s (%s)" % (base, tag) if tag and tag != base else "%s (%s)" % (base, rid)
        # new unique rids
        rid_map = {}
        used = {"main"}
        for rid in regs:
            if rid == "main":
                continue
            base = slugify(new_names[rid])
            cand, k = base, 2
            while cand in used:
                cand = "%s-%d" % (base, k)
                k += 1
            used.add(cand)
            rid_map[rid] = cand
        # apply
        new_regs = OrderedDict()
        for rid, reg in regs.items():
            if rid == "main":
                new_regs["main"] = reg
                continue
            nr = dict(reg)
            if nr.get("name") != new_names[rid] or rid != rid_map[rid]:
                changes.append((room, rid, reg.get("name"), rid_map[rid], new_names[rid]))
            nr["name"] = new_names[rid]
            new_regs[rid_map[rid]] = nr
        rl["regions"] = dict(new_regs)
        for c in rl.get("conns", []):
            c["from"] = rid_map.get(c["from"], c["from"])
            c["to"] = rid_map.get(c["to"], c["to"])
        rl["members"] = {n: rid_map.get(r, r) for n, r in rl.get("members", {}).items()}
    return changes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=str(ROOT / "logic" / "logic.json"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location("mmzx_data_norm", ROOT / "data.py")
    D = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(D)  # type: ignore[union-attr]
    W = F.build_world(D)
    doc = F.load_logic(a.json, W)
    before = F.resolve_members(W, doc)
    changes = normalize(W, doc)
    after = F.resolve_members(W, doc)
    # check: the (translated) membership does not change
    for room in W["rooms"]:
        names_b = {n: doc["rooms"][room]["regions"].get(r, {}).get("name", r) for n, r in after[room].items()}
        if set(before[room]) != set(after[room]):
            print("!! %s: the node set changed" % room)
    print("%d regions renamed:" % len(changes))
    for room, rid, old, nrid, new in changes:
        print("  %-4s %-34s -> %-34s  [%s -> %s]" % (room, old, new, rid, nrid))
    rep = F.validate(W, doc, D.HUB_ROOM, F.unavailable_atoms(D))
    print("validation: %d errors, %d warnings" % (len(rep["errors"]), len(rep["warnings"])))
    if not a.dry_run and not rep["errors"]:
        F.save_logic(a.json, doc)
        Path(a.json).with_suffix(".txt").write_text(F.export_txt(W, doc, D.HUB_ROOM), encoding="utf-8", newline="\n")
        print("saved", a.json)


if __name__ == "__main__":
    main()
