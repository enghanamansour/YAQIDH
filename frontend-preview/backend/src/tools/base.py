from pathlib import Path
from typing import Protocol

from src.schema import Finding


class ToolError(Exception):
    """The tool could not run or its output could not be read. Never swallowed as 'no findings'."""


class Tool(Protocol):
    name: str

    def run(self, target: Path) -> list[Finding]: ...
