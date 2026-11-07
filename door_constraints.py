"""Door constraints: the doors that ask for a Card Key in one seed, drawn from the catalogue of sites."""

from collections import Counter

from BaseClasses import CollectionState

from .door_data import SITES

KEYS = ("Red Card Key", "Blue Card Key", "Purple Card Key", "Yellow Card Key", "Green Card Key")
# The Yellow Card Key already opens most of the keyed doors of the original game.
KEY_WEIGHTS = {"Red Card Key": 10, "Blue Card Key": 10, "Purple Card Key": 10, "Yellow Card Key": 5,
               "Green Card Key": 10}
MAX_PER_KEY = 3                 # so no single key opens half of the map
MAX_SITES = MAX_PER_KEY * len(KEYS)
MIN_SPHERE_ZERO = 10            # locations a new game must reach before its first item
MAX_DRAWS = 40                  # redraws before settling for one door less
SLOT_DATA_KEY = "door_constraints"


def site_doors() -> dict[str, str]:
    """{door name: site name} for the two faces of every site of the catalogue."""
    return {door: name for name, site in SITES.items() for door in site["doors"]}


def door_keys(chosen: dict[str, str]) -> dict[str, str]:
    """{door name: key item} for both faces of the chosen sites."""
    return {door: key for name, key in chosen.items() for door in SITES[name]["doors"]}


def draw(random, count: int, pickups: bool) -> dict[str, str]:
    """Weighted draw of `count` sites and a key for each: {site name: key item}."""
    weight = "weight_pickups" if pickups else "weight"
    pool = sorted(SITES)        # sorted so a seed draws the same sites on every machine
    chosen: dict[str, str] = {}
    per_key: Counter = Counter()
    while len(chosen) < count and pool:
        name = random.choices(pool, [SITES[n][weight] for n in pool])[0]
        pool.remove(name)
        keys = [k for k in KEYS if per_key[k] < MAX_PER_KEY and k != SITES[name]["key"]]
        if not keys:
            continue
        key = random.choices(keys, [KEY_WEIGHTS[k] for k in keys])[0]
        chosen[name] = key
        per_key[key] += 1
    return chosen


def sphere_zero(world) -> int:
    """Locations a new game reaches with only what it starts with, under the current door keys."""
    player = world.player
    state = CollectionState(world.multiworld)
    for name in world.fixed_items()[1]:
        state.collect(world.create_item(name), True)
    locations = list(world.get_locations())
    state.sweep_for_advancements(locations)
    return sum(1 for loc in locations if loc.address is not None and loc.can_reach(state))


def choose(world) -> None:
    """Draws the sites of this seed into world.door_sites and world.door_keys.

    A draw that leaves a new game with too little to do is thrown away; after MAX_DRAWS
    of those the seed takes one door less.
    """
    lo = world.options.door_constraints_min.value
    hi = max(lo, world.options.door_constraints_max.value)
    count = min(world.random.randint(lo, hi), len(SITES), MAX_SITES)
    world.door_sites, world.door_keys = {}, {}
    if count == 0:
        return
    pickups = any(getattr(world.options, name).value for name in (
        "pickup_checks_1up", "pickup_checks_energy", "pickup_checks_weapon", "pickup_checks_crystals"))
    floor = min(MIN_SPHERE_ZERO, sphere_zero(world))
    while count:
        for _ in range(MAX_DRAWS):
            chosen = draw(world.random, count, pickups)
            world.door_keys = door_keys(chosen)
            if sphere_zero(world) >= floor:
                world.door_sites = chosen
                return
        count -= 1
    world.door_keys = {}


def describe(chosen: dict[str, str]) -> str:
    """One line for the spoiler: the sites and their keys."""
    return "; ".join("%s: %s" % (name, key) for name, key in sorted(chosen.items())) or "none"
