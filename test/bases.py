from BaseClasses import CollectionState
from test.bases import WorldTestBase


class MMZXTestBase(WorldTestBase):
    game = "Mega Man ZX"


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


def window_with(bits):
    """A progress window of the client with only these (address, bit) flags set."""
    from ..client.addresses import DETECT_WINDOW
    from ..client.ram import ProgressWindow
    lo, hi = DETECT_WINDOW
    block = bytearray(hi - lo)
    for addr, bit in bits:
        block[addr - lo] |= 1 << bit
    return ProgressWindow(bytes(block), {})
