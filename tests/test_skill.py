"""The agent skill (skills/physverify/SKILL.md) is well formed and names only things that exist."""

import re
from pathlib import Path

import physverify
from physverify import butcher, studies
from physverify.cli import build_parser

SKILL = Path(__file__).resolve().parents[1] / "skills" / "physverify" / "SKILL.md"


def _parts():
    _, front, body = SKILL.read_text(encoding="utf-8").split("---\n", 2)
    return dict(line.split(": ", 1) for line in front.splitlines()), body


def test_front_matter_follows_the_agent_skills_format():
    front, _ = _parts()
    assert front["name"] == SKILL.parent.name  # the format requires the folder's name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", front["name"])
    assert 0 < len(front["description"]) <= 1024
    # an unquoted YAML value may not contain ": " or " #"
    assert not any(": " in v or " #" in v for v in front.values())


def test_every_command_named_in_the_skill_exists():
    _, body = _parts()
    subs = next(a for a in build_parser()._actions if a.dest == "command").choices
    named = set(re.findall(r"`physverify ([a-z]+)", body))
    assert named and named <= set(subs)
    assert "--run" in subs["scan"].format_help()


def test_every_function_named_in_the_skill_exists():
    _, body = _parts()
    assert "check_order(" in body and callable(physverify.check_order)
    assert "check_tableau(" in body and callable(butcher.check_tableau)
    assert "`ode_checks`" in body and callable(physverify.ode_checks)
    assert "`physverify.studies.balance_check`" in body and callable(studies.balance_check)
