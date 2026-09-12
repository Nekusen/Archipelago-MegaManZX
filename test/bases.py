from BaseClasses import CollectionState
from test.bases import WorldTestBase


class MMZXTestBase(WorldTestBase):
    game = "Mega Man ZX"


# Logic-level mixins: list one FIRST in the bases of a test class so that its
# options win over WorldTestBase's empty default.
class NormalLogic:
    options = {"logic_difficulty": "normal"}


class ExpertLogic:
    options = {"logic_difficulty": "expert"}


WITNESS = "Absorber Chip"   # a useful item that no rule of the document asks for


def reach(multiworld, without=()):
    """Regions, locations and victory in logic with the whole pool but the items in `without`."""
    player = 1
    state = CollectionState(multiworld)
    for item in multiworld.itempool:
        if item.name not in without:
            state.collect(item, prevent_sweep=True)
    state.sweep_for_advancements()
    state.update_reachable_regions(player)
    return {
        "regions": {region.name for region in state.reachable_regions[player]},
        "locs": {loc.name for loc in multiworld.get_locations(player)
                 if loc.address is not None and loc.can_reach(state)},
        "victory": bool(multiworld.completion_condition[player](state)),
    }
