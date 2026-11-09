"""A QA check is one security expectation written as a function: it raises AssertionError when it is violated."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    name: str
    fn: Callable  # fn(page, base_url); raises AssertionError (or any error) when the expectation fails
    description: str = ""

    @property
    def file(self) -> str:
        # Derived from the module, so the same check always gets the same fingerprint.
        return self.fn.__module__.replace(".", "/") + ".py"
