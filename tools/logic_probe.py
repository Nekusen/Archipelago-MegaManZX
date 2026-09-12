#!/usr/bin/env python3
"""Evaluate the logic of this apworld against an inventory, without generating a seed.

Builds a one-player multiworld from an Archipelago source checkout (--ap or $AP_SRC)
with the given options, collects the items and prints the reachable rooms, the
locations in logic and the frontier: edges out of a reachable region into an
unreachable one, each with the rule that blocks it. --loc explains one location.

Usage (from the apworld root):
  python tools/logic_probe.py --opt starting_model=model_hx --items "Blue Card Key" [--frontier]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ap  # noqa: E402


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap", default=_ap.DEFAULT_AP, help="Archipelago source checkout (0.6.7)")
    ap.add_argument("--opt", action="append", default=[], metavar="KEY=VALUE",
                    help="YAML option (e.g. starting_model=model_hx, hu_in_pool=true)")
    ap.add_argument("--items", nargs="*", default=[], help="received items (exact names)")
    ap.add_argument("--all-keys", action="store_true", help="add all the Card Keys")
    ap.add_argument("--all-models", action="store_true", help="add all the models/biometals")
    ap.add_argument("--all-access", action="store_true", help="add all the Transerver Access items")
    ap.add_argument("--loc", action="append", default=[], help="explain this location")
    ap.add_argument("--rooms", action="store_true")
    ap.add_argument("--locs", action="store_true")
    ap.add_argument("--frontier", action="store_true")
    ap.add_argument("--world", default=None, help="apworld folder to load (by default this very package)")
    ap.add_argument("--json", default=None, help="dump {rooms, locations in logic} as JSON to this file (comparisons)")
    return ap.parse_args()


def parse_value(v: str):
    lv = v.lower()
    if lv in ("true", "yes", "on"):
        return True
    if lv in ("false", "no", "off"):
        return False
    try:
        return int(v)
    except ValueError:
        return v


def main():
    a = parse_args()
    show_all = not (a.rooms or a.locs or a.frontier or a.loc)
    world_type = _ap.load_core(a.ap, a.world)

    opts = {}
    for kv in a.opt:
        k, _, v = kv.partition("=")
        opts[k.strip()] = parse_value(v.strip())
    mw = _ap.solo_multiworld(world_type, opts)
    world = mw.worlds[1]
    player = 1

    # raw data to describe the rules
    mm = sys.modules["worlds.mmzx"]
    data = mm.data
    logic = mm.logic
    F = mm.logic_format
    doc = mm.regions.load_document()
    tier = world.options.logic_difficulty.current_key
    members = F.resolve_members(logic.WORLD, doc)

    def req_txt(req):
        return F.dnf_to_text(F.req_alternatives(req, tier)) if req is not None else "free"

    items = list(a.items)
    if a.all_keys:
        items += [n for n in data.ITEMS if n.endswith("Card Key")]
    if a.all_models:
        for n, v in data.ITEMS.items():
            if "Model " in n:
                items += [n] * int(v.get("count", 1))   # progressive: both halves
    if a.all_access:
        items += [n for n in data.ITEMS if n.startswith("Transerver Access")]

    state, unknown = _ap.collect_state(mw, items)
    for name in unknown:
        print("!! unknown item:", name)
    reach = {r.name for r in state.reachable_regions[player]}

    precollected = [i.name for i in mw.precollected_items[player]]
    print("== options:", {k: getattr(world.options, k).current_key
                          if hasattr(getattr(world.options, k), "current_key") else getattr(world.options, k).value
                          for k in opts} or "(default)")
    print("== inventory:", precollected + items)
    events = sorted(i for i in state.prog_items[player] if i.startswith("Cleared: ") or i == "Victory")
    if events:
        print("== reached events:", events)

    # a room is reachable when any of its regions is
    rooms = sorted(r for r in logic.ROOM_NAMES if r in reach or any(x.startswith(r + "/") for x in reach))
    subs = sorted(r for r in reach if "/" in r)
    if show_all or a.rooms:
        print("\n== reachable rooms (%d/%d):" % (len(rooms), len(logic.ROOM_NAMES)))
        print("   " + " ".join(rooms))
        if subs:
            print("   sub-regions: " + " ".join(subs))
        missing = sorted(set(logic.ROOM_NAMES) - set(rooms))
        print("== rooms NOT reachable (%d): %s" % (len(missing), " ".join(missing)))

    def describe_edge(ent):
        """Rule text of one entrance of the region graph."""
        name = ent.name
        parts = []
        for d in data.DOORS:
            if d["name"] == name:
                if d.get("key"):
                    parts.append("key %s" % d["key"])
                rr = doc["rooms"][d["dst"]].get("req")
                if rr:
                    parts.append("room %s: %s" % (d["dst"], req_txt(rr)))
                ov = doc.get("edges", {}).get(name, {})
                if ov.get("req") and not F.req_is_free(ov["req"], tier):
                    parts.append("edge: %s" % req_txt(ov["req"]))
                if d.get("gate") is not None:
                    g = doc.get("gates", {}).get(str(d["gate"]), {}).get("req")
                    parts.append("event gate %d: %s" % (d["gate"], req_txt(g) if g else "free (the client sets the flag)"))
                if d["kind"] == "warp" and d["src"] == data.HUB_ROOM:
                    if d["dst"] in data.TRANSERVER_ALWAYS:
                        parts.append("free warp")
                    else:
                        it = data.TRANSERVER_ACCESS.get(d["dst"])
                        parts.append("warp: %s" % (it or "NO Transport destination"))
                break
        else:
            # a drawn connection, named "<room>: <from> -> <to>", or "Start"
            if ": " in name and " -> " in name:
                room, rest = name.split(": ", 1)
                a_, b_ = rest.split(" -> ", 1)
                for c in doc["rooms"].get(room, {}).get("conns", []):
                    if c["from"] == a_ and c["to"] == b_:
                        parts.append("connection: %s%s" % (req_txt(c.get("req")), " (?)" if c.get("unsure") else ""))
            if name == "Start":
                parts.append("starting room: %s" % req_txt(doc["rooms"][ent.connected_region.name.split("/")[0]].get("req")))
        return "; ".join(parts) or "(no rule; event?)"

    if show_all or a.frontier:
        print("\n== FRONTIER (reachable edge -> unreachable destination):")
        seen = set()
        for reg in sorted(state.reachable_regions[player], key=lambda r: r.name):
            for ent in reg.exits:
                dst = ent.connected_region
                if dst is None or dst.name in reach:
                    continue
                key = (reg.name, dst.name)
                if key in seen:
                    continue
                seen.add(key)
                print("   %-4s -> %-12s [%s]  %s" % (reg.name, dst.name, ent.name, describe_edge(ent)))

    in_logic = _ap.in_logic(mw, state)
    if show_all or a.locs:
        print("\n== locations IN LOGIC (%d):" % len(in_logic["locs_in"]))
        for name in in_logic["locs_in"]:
            print("   " + name)
        print("\n== locations OUT of logic (%d):" % len(in_logic["locs_out"]))
        for name in in_logic["locs_out"]:
            print("   " + name)

    for name in a.loc:
        loc = next((l for l in mw.get_locations(player) if l.name == name), None)
        if loc is None:
            print("\n?? location not found:", name)
            continue
        v = data.LOCATIONS.get(name, {})
        print("\n== %s: %s" % (name, "IN LOGIC" if loc.can_reach(state) else "OUT"))
        print("   region: %s (%s)" % (loc.parent_region.name,
                                     "reachable" if loc.parent_region.name in reach else "NOT reachable"))
        ch = doc.get("checks", {}).get(name, {})
        print("   curated rule: %s%s" % (req_txt(ch.get("req")) if ch.get("req") else "free",
                                          " (?)" if ch.get("unsure") else ""))
        room, pos = F.check_position(logic.WORLD, doc, name)
        if room:
            rid = members[room].get(name, "main")
            print("   room: %s (%s), region %s (%s)" % (
                room, "reachable" if room in reach else "NOT reachable",
                F.region_name(room, rid), "reachable" if F.region_name(room, rid) in reach else "NOT reachable"))
        else:
            label = v.get("room")
            for g in logic.label_room_groups(label):
                lack = [r for r in g if r not in reach]
                print("   UNPLACED; label %r -> rooms %s; missing: %s" % (label, g, lack or "none"))

    if a.json:
        import json
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"rooms": rooms, "regions": sorted(reach), "locs_in": in_logic["locs_in"],
                       "locs_out": in_logic["locs_out"], "events": events}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
