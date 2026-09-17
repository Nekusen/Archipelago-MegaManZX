"""Files shipped with the world: the three Archipelago logos."""

import os
import pkgutil


def read(name: str) -> bytes:
    """Bytes of a file in this folder, from a directory or from a zipped .apworld."""
    try:
        data = pkgutil.get_data(__name__, name)
    except Exception:
        data = None
    if data is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), "rb") as f:
            data = f.read()
    return data
