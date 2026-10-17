"""Save and load a TimeSeriesDB to/from JSON files.

Think of this like saving your video-game progress.  When you close
the game, your save file keeps everything.  Next time you open it,
you pick up right where you left off.

We use JSON because it's human-readable -- you can open the file in a
text editor and actually *see* your data!
"""

import json
from pathlib import Path
from typing import cast

from pytsdb.atomic import atomic_write_text
from pytsdb.database import TimeSeriesDB
from pytsdb.errors import PersistenceError

# Every real save file has these top-level keys; anything else isn't one of ours.
_REQUIRED_KEYS = frozenset({"series"})


def save(db: TimeSeriesDB, path: Path | str) -> None:
    """Write the entire database to a JSON file.

    Args:
        db: The database to persist.
        path: Where to write the file.

    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    data = db.to_dict()
    atomic_write_text(file_path, json.dumps(data, indent=2, default=str))


def load(path: Path | str) -> TimeSeriesDB:
    """Read a database from a JSON file.

    Args:
        path: The file to read.

    Returns:
        A fully-loaded :class:`~pytsdb.database.TimeSeriesDB`.

    Raises:
        PersistenceError: If the file is missing, unreadable, not valid JSON,
            or not a valid save file.

    """
    file_path = Path(path)
    try:
        data: object = json.loads(file_path.read_text(encoding="utf-8"))
    except OSError as exc:
        msg = f"Could not read {file_path}: {exc}"
        raise PersistenceError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in {file_path}: {exc}"
        raise PersistenceError(msg) from exc
    if not isinstance(data, dict):
        msg = f"{file_path} is not a valid save file: the top level must be an object"
        raise PersistenceError(msg)
    saved: dict[str, object] = {str(k): v for k, v in cast("dict[object, object]", data).items()}
    missing = _REQUIRED_KEYS - saved.keys()
    if missing:
        msg = f"{file_path} is not a valid save file: missing {sorted(missing)}"
        raise PersistenceError(msg)
    try:
        return TimeSeriesDB.from_dict(saved)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        msg = f"{file_path} is not a valid save file: {exc}"
        raise PersistenceError(msg) from exc
