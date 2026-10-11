"""Compiles the intermediate representation of the logic document into Rule Builder rules, defines the
rules of this world that depend on the player's YAML or on their seed, and the records the generated
logic module is written with."""

import dataclasses
from typing import ClassVar, NamedTuple

from rule_builder.options import OptionFilter
from rule_builder.rules import (And, CanReachLocation, CanReachRegion, False_, Has, HasAll, HasAny, HasFromList,
                                HasFromListUnique, Or, Rule, True_)

from .. import options as O
from ..door_constraints import KEYS
from ..goal import COUNTED_MISSIONS, DISK_ITEM, cleared_event
from ..seal import BIOMETAL_EVENTS, MODE_BIOMETALS, MODE_PASSWORDS, PASSWORD_ITEM
from . import bosses as B
from . import document as F


class Edge(NamedTuple):
    """An entrance of the generated module: from one region to another, under a rule."""
    src: str
    dst: str
    rule: Rule


class Spot(NamedTuple):
    """A location or event of the generated module: its region and its rule."""
    region: str
    rule: Rule

    def also(self, rule: Rule) -> "Spot":
        """The same place, asking for this as well: an event that adds to its anchor's rule."""
        return Spot(self.region, self.rule & rule)


def option_filter(option: str, value, operator: str = "eq") -> OptionFilter:
    """An option filter by the class name of the option, as the document names it."""
    return OptionFilter(getattr(O, option), value, operator)


def boss_requirements(world) -> dict:
    """{boss id: REQ} from the boss_logic option, cached on the world for the other hooks."""
    reqs = getattr(world, "_mmzx_boss_reqs", None)
    if reqs is None:
        reqs = B.parse_boss_logic(world.options.boss_logic.value)
        world._mmzx_boss_reqs = reqs
    return reqs


def _resolved(world) -> dict:
    return {"player": world.player, "caching_enabled": getattr(world, "rule_caching_enabled", False)}


class Wrapped(Rule.Resolved):
    """A resolved rule that evaluates and depends on a child rule, and explains it under its own words."""
    child: Rule.Resolved

    def __post_init__(self) -> None:
        object.__setattr__(self, "force_recalculate", self.force_recalculate or self.child.force_recalculate)
        super().__post_init__()

    def _evaluate(self, state) -> bool:
        return self.child(state)

    def item_dependencies(self) -> dict:
        return {name: {id(self), *rules} for name, rules in self.child.item_dependencies().items()}

    def region_dependencies(self) -> dict:
        return {name: {id(self), *rules} for name, rules in self.child.region_dependencies().items()}

    def location_dependencies(self) -> dict:
        return {name: {id(self), *rules} for name, rules in self.child.location_dependencies().items()}

    def entrance_dependencies(self) -> dict:
        return {name: {id(self), *rules} for name, rules in self.child.entrance_dependencies().items()}

    def label(self) -> str:
        return self.rule_name + ": "

    def explain_json(self, state=None) -> list:
        return [{"type": "text", "text": self.label()}, *self.child.explain_json(state)]

    def explain_str(self, state=None) -> str:
        return self.label() + self.child.explain_str(state)

    def __str__(self) -> str:
        return self.label() + str(self.child)


@dataclasses.dataclass()
class BossRequirement(Rule, game=F.GAME):
    """The player's boss_logic requirement for one boss; nothing when the YAML leaves it out."""

    boss_id: str

    def _instantiate(self, world) -> Rule.Resolved:
        req = boss_requirements(world).get(self.boss_id)
        if req is None:
            return True_().resolve(world)
        child = compile_ir(F.req_ir(req, F.TIER)).resolve(world)
        return self.Resolved(child, F.BOSSES[self.boss_id]["name"], **_resolved(world))

    def __str__(self) -> str:
        return "BossRequirement(%s)" % self.boss_id

    class Resolved(Wrapped):
        boss_name: str

        def label(self) -> str:
            return "Beat %s with " % self.boss_name


@dataclasses.dataclass()
class ModelsOwned(Rule, game=F.GAME):
    """`count` of the models in `needs`, each held with its copies: both halves of a progressive
    biometal when the goal requires full models."""

    needs: tuple
    count: int

    def _instantiate(self, world) -> Rule.Resolved:
        return self.Resolved(tuple(tuple(need) for need in self.needs), self.count, **_resolved(world))

    def __str__(self) -> str:
        return "ModelsOwned(%d, %s)" % (self.count, list(self.needs))

    class Resolved(Rule.Resolved):
        needs: tuple
        count: int

        def _owned(self, state) -> list:
            return [(item, copies) for item, copies in self.needs if state.has(item, self.player, copies)]

        def _evaluate(self, state) -> bool:
            return len(self._owned(state)) >= self.count

        def item_dependencies(self) -> dict:
            return {item: {id(self)} for item, _copies in self.needs}

        def explain_json(self, state=None) -> list:
            owned = self._owned(state) if state else []
            parts = [{"type": "text", "text": "Has "},
                     {"type": "color", "color": "green" if len(owned) >= self.count else "salmon",
                      "text": "%d/%d" % (len(owned), self.count)},
                     {"type": "text", "text": " models from ("}]
            for i, (item, copies) in enumerate(self.needs):
                if i:
                    parts.append({"type": "text", "text": ", "})
                parts.append({"type": "color", "color": "green" if (item, copies) in owned else "salmon", "text": item})
                if copies > 1:
                    parts.append({"type": "text", "text": " x%d" % copies})
            parts.append({"type": "text", "text": ")"})
            return parts

        def explain_str(self, state=None) -> str:
            owned = self._owned(state) if state else []
            return "Has %d/%d models from (%s)" % (len(owned), self.count, ", ".join(
                item + (" x%d" % copies if copies > 1 else "") for item, copies in self.needs))

        def __str__(self) -> str:
            return self.explain_str()


@dataclasses.dataclass()
class GoalRequirement(Rule, game=F.GAME):
    """The goal requirements of the seed, as the world resolved them: the models, the Secret Disks
    and the story missions; nothing when they ask for nothing."""

    def _instantiate(self, world) -> Rule.Resolved:
        goal = world.goal
        parts = []
        if goal.wants_models:
            needs = tuple((item, goal.copies.get(item, 1)) for item in goal.models)
            if all(copies == 1 for _item, copies in needs):
                parts.append(HasFromListUnique(*goal.models, count=goal.models_count))
            else:
                parts.append(ModelsOwned(needs, goal.models_count))
        if goal.wants_disks:
            parts.append(Has(DISK_ITEM, goal.disks_required))
        if goal.wants_missions:
            parts.append(HasFromListUnique(*(cleared_event(m) for m in COUNTED_MISSIONS), count=goal.missions_required))
        if not parts:
            return True_().resolve(world)
        return self.Resolved(And(*parts).resolve(world), **_resolved(world))

    def __str__(self) -> str:
        return "GoalRequirement()"

    class Resolved(Wrapped):
        def label(self) -> str:
            return "Goal: "


@dataclasses.dataclass()
class SealRequirement(Rule, game=F.GAME):
    """The seal of Area M as the world resolved area_m_access: the Passwords, the five biometal
    checks, or nothing when it starts open."""

    def _instantiate(self, world) -> Rule.Resolved:
        seal = world.seal
        if seal.mode == MODE_PASSWORDS:
            child = Has(PASSWORD_ITEM, seal.passwords_required)
        elif seal.mode == MODE_BIOMETALS:
            child = HasAll(*BIOMETAL_EVENTS)
        else:
            return True_().resolve(world)
        return self.Resolved(child.resolve(world), **_resolved(world))

    def __str__(self) -> str:
        return "SealRequirement()"

    class Resolved(Wrapped):
        def label(self) -> str:
            return "Seal of Area M: "


@dataclasses.dataclass()
class DoorKey(Rule, game=F.GAME):
    """The Card Key of a door constraint site in this seed, if the seed locked it."""

    door: str

    def _instantiate(self, world) -> Rule.Resolved:
        return self.Resolved(self.door, **_resolved(world))

    def __str__(self) -> str:
        return "DoorKey(%s)" % self.door

    class Resolved(Rule.Resolved):
        door: str
        # the keys are drawn after the regions exist, against the reach they leave a new game
        force_recalculate: ClassVar[bool] = True

        def _key(self, state):
            return state.multiworld.worlds[self.player].door_keys.get(self.door)

        def _evaluate(self, state) -> bool:
            key = self._key(state)
            return key is None or state.has(key, self.player)

        def item_dependencies(self) -> dict:
            return {key: {id(self)} for key in KEYS}

        def explain_json(self, state=None) -> list:
            if state is None:
                return [{"type": "text", "text": "The key of this door, if the seed locked it"}]
            key = self._key(state)
            if key is None:
                return [{"type": "color", "color": "green", "text": "Door not locked in this seed"}]
            held = state.has(key, self.player)
            return [{"type": "text", "text": "Door locked: %s " % ("Has" if held else "Missing")},
                    {"type": "color", "color": "green" if held else "salmon", "text": key}]

        def explain_str(self, state=None) -> str:
            return "".join(part["text"] for part in self.explain_json(state))

        def __str__(self) -> str:
            return "Key of door %s" % self.door


@dataclasses.dataclass()
class LavaCarriedTo(Rule, game=F.GAME):
    """The slow lava of Area K at `region`, while no item slows it: the control's event, and a
    walk from the control to that region through the regions of the area, since the game forgets
    the setting on leaving it."""

    region: str
    control: str

    def _instantiate(self, world) -> Rule.Resolved:
        area = F.area_of(self.control)
        regions = tuple(sorted(r.name for r in world.multiworld.get_regions(world.player) if F.area_of(r.name) == area))
        return self.Resolved(self.region, self.control, regions, **_resolved(world))

    def __str__(self) -> str:
        return "LavaCarriedTo(%s, %s)" % (self.region, self.control)

    class Resolved(Rule.Resolved):
        region: str
        control: str
        area_regions: tuple
        # follows what the area lets the player walk through, not an item alone
        force_recalculate: ClassVar[bool] = True
        walking: ClassVar[set] = set()

        def _evaluate(self, state) -> bool:
            if self.player in self.walking:
                return True     # an edge of the walk itself: the lava is already slow there
            if not state.has(F.LAVA_EVENT, self.player):
                return False
            control = state.multiworld.get_region(self.control, self.player)
            self.walking.add(self.player)
            try:
                seen, todo = {control}, [control]
                while todo:
                    region = todo.pop()
                    if region.name == self.region:
                        return True
                    for way in region.exits:
                        nxt = way.connected_region
                        inside = nxt is not None and F.area_of(nxt.name) == F.area_of(control.name)
                        if inside and nxt not in seen and way.access_rule(state):
                            seen.add(nxt)
                            todo.append(nxt)
                return False
            finally:
                self.walking.discard(self.player)

        def item_dependencies(self) -> dict:
            return {F.LAVA_EVENT: {id(self)}}

        def region_dependencies(self) -> dict:
            return {name: {id(self)} for name in self.area_regions}

        def explain_json(self, state=None) -> list:
            verb = "Slow lava carried" if state is None else ("Slow lava carried" if self(state) else "Slow lava not carried")
            return [{"type": "text", "text": "%s from its control to " % verb},
                    {"type": "color", "color": "yellow", "text": self.region}]

        def explain_str(self, state=None) -> str:
            return "".join(part["text"] for part in self.explain_json(state))

        def __str__(self) -> str:
            return "Slow lava carried from its control to %s" % self.region


@dataclasses.dataclass()
class ReachedAtLeast(Rule, game=F.GAME):
    """`count` of the `locations` reachable: the story objects the game hands out after some others."""

    count: int
    locations: tuple

    def _instantiate(self, world) -> Rule.Resolved:
        cache = world.multiworld.regions.location_cache[world.player]
        present = tuple((name, cache[name].parent_region.name) for name in self.locations if name in cache)
        return self.Resolved(self.count, present, **_resolved(world))

    def __str__(self) -> str:
        return "ReachedAtLeast(%d, %s)" % (self.count, list(self.locations))

    class Resolved(Rule.Resolved):
        count: int
        locations: tuple

        def _reached(self, state) -> list:
            return [name for name, _region in self.locations if state.can_reach_location(name, self.player)]

        def _evaluate(self, state) -> bool:
            return len(self._reached(state)) >= self.count

        def location_dependencies(self) -> dict:
            return {name: {id(self)} for name, _region in self.locations}

        def region_dependencies(self) -> dict:
            return {region: {id(self)} for _name, region in self.locations}

        def explain_json(self, state=None) -> list:
            reached = self._reached(state) if state else []
            parts = [{"type": "text", "text": "Reached "},
                     {"type": "color", "color": "green" if len(reached) >= self.count else "salmon",
                      "text": "%d/%d" % (len(reached), self.count)},
                     {"type": "text", "text": " of ("}]
            for i, (name, _region) in enumerate(self.locations):
                if i:
                    parts.append({"type": "text", "text": ", "})
                parts.append({"type": "location_name", "text": name, "player": self.player})
            parts.append({"type": "text", "text": ")"})
            return parts

        def explain_str(self, state=None) -> str:
            reached = self._reached(state) if state else []
            return "Reached %d/%d of (%s)" % (len(reached), self.count, ", ".join(name for name, _region in self.locations))

        def __str__(self) -> str:
            return self.explain_str()


def compile_ir(ir, gates=None) -> Rule:
    """The Rule of an IR node; `gates` is the table of the document's event gates it may name."""
    kind = ir[0]
    if kind == "true":
        return True_()
    if kind == "false":
        return False_()
    if kind == "and":
        return And(*(compile_ir(c, gates) for c in ir[1]))
    if kind == "or":
        return Or(*(compile_ir(c, gates) for c in ir[1]))
    if kind == "has":
        return Has(ir[1], ir[2])
    if kind in ("has_if", "needs_if"):
        # a has_if counts for nothing without its option, a needs_if is not asked for at all
        return Has(ir[1], ir[2], options=[option_filter(ir[3], ir[4], ir[5])], filtered_resolution=kind == "needs_if")
    if kind == "has_any":
        return HasAny(*ir[1])
    if kind == "has_from_list":
        return HasFromList(*ir[1], count=ir[2])
    if kind == "reach":
        return CanReachRegion(ir[1])
    if kind == "reach_location":
        return CanReachLocation(ir[1], ir[2])
    if kind == "reached_at_least":
        return ReachedAtLeast(ir[1], tuple(ir[2]))
    if kind == "option_true":
        return True_(options=[option_filter(ir[1], ir[2], ir[3])])
    if kind == "goal":
        return GoalRequirement()
    if kind == "seal":
        return SealRequirement()
    if kind == "boss":
        return BossRequirement(ir[1])
    if kind == "door_key":
        return DoorKey(ir[1])
    if kind == "lava":
        return LavaCarriedTo(ir[1], ir[2], options=[option_filter(F.STORY_OPTION, F.STORY_ITEMS, "ne")])
    if kind == "gate":
        return compile_ir(gates[ir[1]], gates)
    if kind == "macro":
        return compile_ir(F.MACRO_IR[ir[1]], gates)
    raise ValueError("unknown IR node %r" % (ir,))


def compile_req(req, tier=F.TIER) -> Rule:
    """The Rule of a requirement asked at no place in particular, such as a boss requirement."""
    return compile_ir(F.req_ir(req, tier))
