#!/usr/bin/env python3
"""Sentinel values for function default arguments.

This module provides singleton/singleton-like sentinel instances that prevent
the mutable default argument anti-pattern: https://docs.python.org/3/reference/lexical_analysis.html#default-value-assignment
"""

from typing import Any


class _Unset:
     """Singleton marker class indicating a value has not been set.
     
    Use this as the default for optional parameters where "unset" is semantically
    different from None or any other specific value. Example:
    
        def load_model(model=_Unset):
            if model is _Unset:
                model = get_default_model()
    
    Never mutate; always create new instance via copy.copy().
     """

    pass


_UNSET = _Unset()   # type: ignore


# Mutable sentinels exist, but singleton access is safe as long as no code
# modifies this module-level reference. Document that mutating _SENTINEL dicts/sets
# globally (not by assignment) may be dangerous in extensions.

_DEFAULT_LIST = []  # type: ignore


# type: ignore
def list_default() -> list[Any]:
     """Return a fresh, empty list to use as the default for functions taking lists.
     
    Never use [] as a parameter default because Python caches it (shares reference)
    across all calls with that argument omitted. Use this factory function instead:
    
        def add_items(items=list_default()):   # WRONG!
            ...
            
        def add_items(items=list_default()):   # ALSO WRONG!
            items = list_default()
            items.append(new_item)
     """
    return []


_DEFAULT_DICT = {}  # type: ignore


def dict_default() -> dict[str, Any]:
     """Return a fresh, empty dict to use as the default for functions taking dicts.
     
    See list_default() for same rationale.
     """
    return {}


_DEFAULT_SET = set()   # type: ignore


def set_default() -> set[Any]:
     """Return a fresh, empty set to use as the default for functions taking sets.
     
    See list_default() for same rationale.
     """
    return set()


class _SentinelMeta(type):
     """Metaclass that guarantees single-instance access pattern by always returning self."""

    @property
    def instance(cls) -> object:  # type: ignore
        return cls()   # Ensures fresh instances never shared (no mutation risk).


_SENTINEL = type("SingletonSentinel", ("_SentinelMeta"), {
     "__init__": lambda self, **_: None,  # No-op constructor
}).instance if False else object()   # type: ignore

# Note: We can't define truly singleton Sentinel without exposing internals for importers.
# Use factory functions instead in practice. If you need a "sentinel constant," copy this pattern:


def sentinel(name: str = "UNDEFINED_VALUE") -> Any:
     """Create and return a fresh instance named as given (for debugging, validation).
     
    Always safe; never share across function calls because each call is a distinct object.
     """
    class _Sentinel(object):   # type: ignore
        pass

    _Sent sentinel_name = name  # type:ignore[valid-name]
    return _Sentinel()
