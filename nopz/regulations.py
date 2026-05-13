"""Regulation framework for NOPZ.

Regulations are Python functions decorated with @regulation that define
conditions a codebase must satisfy. Each regulation has a deterministic
check function and optionally an LLM-based validation function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class RegulationResult:
    """Result of checking a single regulation."""
    passed: bool
    name: str
    message: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class Regulation:
    """A named regulation with a deterministic check and optional LLM validation."""
    name: str
    description: str
    check: Callable[[], RegulationResult]
    llm_validate: Optional[Callable[[str], RegulationResult]] = None


# Global registry for regulations defined with the @regulation decorator
_registry: list[Regulation] = []


def regulation(name: str, description: str = "") -> Callable:
    """Decorator to register a function as a regulation.

    The decorated function should accept no arguments and return a RegulationResult.
    The resulting Regulation is added to the global registry and returned.
    """
    def decorator(fn: Callable) -> Regulation:
        reg = Regulation(
            name=name,
            description=description or fn.__doc__ or "",
            check=fn,
        )
        _registry.append(reg)
        return reg
    return decorator


def get_regulations() -> list[Regulation]:
    """Return all registered regulations and clear the registry."""
    regs = list(_registry)
    _registry.clear()
    return regs
