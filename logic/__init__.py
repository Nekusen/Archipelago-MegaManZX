"""The access logic: the document drawn in the editor (logic.json), compiled to Rule Builder rules."""

import json
import pkgutil

from .. import data as _data
from .. import door_data as _door_data
from . import document as F

TIER = F.TIER
WORLD = F.build_world(_data, _door_data.SITES)
ROOM_NAMES = WORLD["rooms"]

_DOC = None


def load_document():
    """The bundled logic.json, normalized and cached."""
    global _DOC
    if _DOC is None:
        raw = pkgutil.get_data(__name__, "logic.json")
        if raw is None:
            raise FileNotFoundError("logic/logic.json not found: "
                                    "create the logic with tools/logic_editor/")
        _DOC = F.normalize_logic(json.loads(raw.decode("utf-8")), WORLD)
    return _DOC


def starting_point(world) -> dict:
    """Record of the starting_transerver option: spawn, room and pre-granted access item."""
    key = world.options.starting_transerver.current_key
    return _data.STARTING_TRANSERVERS.get(key) or next(iter(_data.STARTING_TRANSERVERS.values()))
