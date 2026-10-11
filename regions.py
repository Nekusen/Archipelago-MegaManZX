"""Archipelago regions, entrances, locations and events, from the generated logic module."""

from BaseClasses import Region
from rule_builder.rules import Has

from .locations import MMZXLocation, active_locations
from .logic import bosses as B
from .logic import document as F
from .logic import rules as R
from .logic.builder import boss_requirements


def progression_overrides(world) -> set:
    """Useful items that the logic or the player's boss YAML turn into progression."""
    return set(R.COUNTED_ITEMS) | B.items_used(boss_requirements(world))


def create_regions(world) -> None:
    """Creates the regions, entrances, locations and events of one player from logic/rules.py.

    An entrance whose rule resolves to False for this slot's options is not created: the boss rush
    teleporters with skip_boss_rush, the connections drawn as never. Nor is an event that could
    never hold with them: the ones that stand for a story object another mode makes an item, or
    for the seal of a mode not played.
    """
    if R.ERRORS:
        raise ValueError("logic/rules.py was generated from a document with errors; fix them in the logic editor "
                         "(it rewrites the module on save) or run tools/check_logic.py:\n  " + "\n  ".join(R.ERRORS))
    player, mw = world.player, world.multiworld
    regions = {name: Region(name, player, mw) for name in R.REGIONS}
    mw.regions += list(regions.values())
    for name, edge in R.ENTRANCES.items():
        world.create_entrance(regions[edge.src], regions[edge.dst], edge.rule, name,
                              force_creation=name == F.START_ENTRANCE)

    spots = {}
    for name, v in active_locations(world.options).items():
        spots[name] = MMZXLocation(player, name, v["id"], regions[R.LOCATIONS[name].region])
    for name, item in R.EVENTS.items():
        if R.LOCATIONS[name].rule.resolve(world).always_false:
            continue
        spots[name] = MMZXLocation(player, name, None, regions[R.LOCATIONS[name].region])
        spots[name].place_locked_item(world.create_event(item))
    # every location exists before any rule is set: a rule may name another location
    for location in spots.values():
        location.parent_region.locations.append(location)
    for name, location in spots.items():
        world.set_rule(location, R.LOCATIONS[name].rule)
    world.set_completion_rule(Has(F.VICTORY))
