"""The access logic: the document drawn in the editor (logic.json) and the rules that are not drawn."""

import json
import pkgutil

from . import document as F
from .rules import WORLD

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
