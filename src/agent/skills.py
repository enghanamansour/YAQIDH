"""Skills: short instruction files the agent can read before it explains a finding.

Each skill is a folder under src/agent/skills/ with a SKILL.md that starts with a small header:

    ---
    name: sql-injection
    description: one line saying when to use it
    ---
    ...the text...

The agent only ever sees names and descriptions first, and picks from them. The code checks that the
name exists, so an invented name is refused. Adding a skill means adding a folder, no code change.
"""

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent / "skills"


class SkillError(Exception):
    pass


def _parse(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SkillError(f"{path}: a skill must start with a --- header")
    _, header, body = text.split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    if not meta.get("name") or not meta.get("description"):
        raise SkillError(f"{path}: the header needs a name and a description")
    if meta["name"] != path.parent.name:
        raise SkillError(f"{path}: the name '{meta['name']}' must match its folder '{path.parent.name}'")
    return meta, body.strip()


class Skills:
    def __init__(self, directory: Path = SKILLS_DIR):
        self.directory = Path(directory)

    def _all(self) -> dict[str, tuple[dict, str]]:
        found = {}
        for path in sorted(self.directory.glob("*/SKILL.md")):
            meta, body = _parse(path)
            found[meta["name"]] = (meta, body)
        return found

    def list(self) -> list[dict]:
        return [{"name": n, "description": m["description"]} for n, (m, _) in self._all().items()]

    def read(self, name: str) -> str:
        skills = self._all()
        if name not in skills:
            raise SkillError(f"no skill called '{name}'. Available: {', '.join(skills) or 'none'}")
        return skills[name][1]
