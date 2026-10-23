"""Single-machine advisory serialization for full checkpoint transactions (Unix)."""
from __future__ import annotations

import asyncio
import fcntl
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator


@asynccontextmanager
async def checkpoint_lock(db_path: str) -> AsyncIterator[None]:
    # Lock the entire read/modify/write sequence, not only individual SQL writes.
    # Separate file descriptions also serialize independent service instances.
    lock_path = Path(db_path).resolve().with_suffix(Path(db_path).suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as handle:
        acquired = False
        try:
            while not acquired:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    await asyncio.sleep(0.01)
            yield
        finally:
            if acquired:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
