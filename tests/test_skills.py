import pytest

from src.agent.skills import SKILLS_DIR, SkillError, Skills

EXPECTED = {"sql-injection", "debug-enabled", "hardcoded-secret", "outdated-dependency",
            "access-control-login", "security-headers", "error-leakage"}


def test_the_seven_skills_load_with_a_name_and_a_description():
    listed = Skills().list()
    assert {s["name"] for s in listed} == EXPECTED
    assert all(s["description"] for s in listed)


def test_no_skill_contains_code_or_a_secret_looking_value():
    # The agent must explain in words, so the skills it learns from must not teach it to write code.
    for path in SKILLS_DIR.glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        assert "`" not in text and "ghp_" not in text, path


def test_reading_an_unknown_skill_is_refused_and_lists_the_real_ones():
    with pytest.raises(SkillError, match="Available: "):
        Skills().read("nope")


def test_a_skill_with_a_wrong_header_is_rejected(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "SKILL.md").write_text("---\nname: other\ndescription: x\n---\nbody")
    with pytest.raises(SkillError, match="must match its folder"):
        Skills(tmp_path).list()
    (tmp_path / "a" / "SKILL.md").write_text("no header")
    with pytest.raises(SkillError, match="header"):
        Skills(tmp_path).list()


def test_adding_a_folder_adds_a_skill_with_no_code_change(tmp_path):
    (tmp_path / "new-one").mkdir()
    (tmp_path / "new-one" / "SKILL.md").write_text("---\nname: new-one\ndescription: d\n---\ntext")
    assert Skills(tmp_path).read("new-one") == "text"
