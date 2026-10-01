from __future__ import annotations

from copy import copy
from typing import Any


def clone_with_updates(value: Any, **updates: Any) -> Any:
    """Clone a framework value without mutating the application-owned object."""

    if isinstance(value, dict):
        cloned = dict(value)
        cloned.update(updates)
        return cloned

    model_copy = getattr(value, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=updates)

    legacy_copy = getattr(value, "copy", None)
    if callable(legacy_copy):
        try:
            return legacy_copy(update=updates)
        except TypeError:
            pass

    try:
        cloned = copy(value)
        for key, item in updates.items():
            setattr(cloned, key, item)
    except (AttributeError, TypeError) as exc:
        raise TypeError(
            "Could not clone %s with evidence-lineage metadata." % type(value).__name__
        ) from exc
    return cloned
