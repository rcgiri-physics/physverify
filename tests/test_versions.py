"""The version is the same everywhere it is written, so a release cannot ship with a stale one."""

import re
from pathlib import Path

import physverify

ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_versions_agree():
    v = physverify.__version__
    assert re.search(r'^version = "([^"]+)"', _read("pyproject.toml"), re.M).group(1) == v
    assert re.search(r"^version: (\S+)", _read("CITATION.cff"), re.M).group(1) == v
    readme = _read("README.md")
    assert f"(v{v})" in readme and f"physverify@v{v}" in readme, "update the version in README.md"
    assert f"physverify@v{v}" in _read("docs/index.md"), "update the action version in docs/index.md"
    for name in ("docs/ci.md", "packaging/mcp-registry/server.json"):
        assert set(re.findall(r'@v(\d+\.\d+\.\d+)|"version": "(\d+\.\d+\.\d+)"|rev: v(\d+\.\d+\.\d+)', _read(name))) <= {
            (v, "", ""), ("", v, ""), ("", "", v)}, f"update the version in {name}"
    released = re.findall(r"^## (\d+\.\d+\.\d+)", _read("CHANGELOG.md"), re.M)
    assert released[0] == v, "add a CHANGELOG section for this version"
    recipe = re.search(r'^  version: "([^"]+)"', _read("packaging/conda-forge/recipe.yaml"), re.M).group(1)
    # the sha256 is that of the sdist on PyPI, known only after the release is published, so the recipe may
    # lag one release behind until the follow-up update
    assert recipe in (v, released[1]), "update the version and sha256 in packaging/conda-forge/recipe.yaml"
