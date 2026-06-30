from __future__ import annotations

import gzip
import logging.handlers
import os
import shutil
from pathlib import Path


def build_gzip_timed_rotating_handler(
    log_path: str | Path,
    *,
    backup_count: int,
    when: str = "midnight",
    utc: bool = True,
    encoding: str = "utf-8",
) -> logging.handlers.TimedRotatingFileHandler:
    """
    Create a timed rotating file handler that gzips archives after rotation.
    """
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.TimedRotatingFileHandler(
        str(path),
        when=when,
        utc=utc,
        backupCount=backup_count,
        encoding=encoding,
    )
    handler.suffix = "%Y-%m-%d"

    def namer(default_name: str) -> str:
        return f"{default_name}.gz"

    def rotator(source: str, dest: str) -> None:
        with open(source, "rb") as src, gzip.open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.remove(source)

    handler.namer = namer
    handler.rotator = rotator
    return handler
