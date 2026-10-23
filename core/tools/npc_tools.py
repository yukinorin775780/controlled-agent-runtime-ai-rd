"""Inventory inspection tool, bound to a scoped inventory by the caller."""
from __future__ import annotations

from typing import Mapping
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Iterator
from langchain_core.tools import tool


def inspect_inventory(inventory: Mapping[str, int], keyword: str, target_id: str = "target") -> str:
    from core.systems.inventory import get_registry
    query = keyword.strip().lower()
    if not query:
        return "An item keyword is required."
    registry = get_registry()
    matches = [f"{target_id} 拥有 {count} 个 {item}。" for item, count in inventory.items()
               if count > 0 and (query in item.lower() or query in registry.get_name(item).lower())]
    return "; ".join(matches) if matches else f"No item matching '{keyword}' in the visible inventory."


_inventories: ContextVar[Mapping[str, Mapping[str, int]] | None] = ContextVar("tool_inventories", default=None)


@contextmanager
def inventory_scope(inventories: Mapping[str, Mapping[str, int]]) -> Iterator[None]:
    token = _inventories.set(inventories)
    try:
        yield
    finally:
        _inventories.reset(token)


@tool
def check_target_inventory(target_id: str, item_keyword: str) -> str:
    """Inspect an authorized target's inventory. Runtime must bind the scoped inventory."""
    inventories = _inventories.get()
    if inventories is None or target_id not in inventories:
        return "Denied: target inventory is outside the runtime-bound scope."
    return inspect_inventory(inventories[target_id], item_keyword, target_id)
