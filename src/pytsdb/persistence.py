"""Save and load a TimeSeriesDB to/from JSON files.

Think of this like saving your video-game progress.  When you close
the game, your save file keeps everything.  Next time you open it,
you pick up right where you left off.

We use JSON because it's human-readable -- you can open the file in a
text editor and actually *see* your data!
"""

import json
from pathlib import Path

from pytsdb.database import TimeSeriesDB


def save(db: TimeSeriesDB, path: Path | str) -> None:
    """Write the entire database to a JSON file.

    Args:
        db: The database to persist.
        path: Where to write the file.

    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    data = db.to_dict()
    file_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load(path: Path | str) -> TimeSeriesDB:
    """Read a database from a JSON file.

    Args:
        path: The file to read.

    Returns:
        A fully-loaded :class:`~pytsdb.database.TimeSeriesDB`.

    Raises:
        FileNotFoundError: If the file doesn't exist.

    """
    file_path = Path(path)
    raw = file_path.read_text(encoding="utf-8")
    data: object = json.loads(raw)
    if not isinstance(data, dict):
        msg = "Top-level JSON must be an object"
        raise TypeError(msg)
    db_data: dict[str, object] = {str(k): v for k, v in data.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return TimeSeriesDB.from_dict(db_data)
