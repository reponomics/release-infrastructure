"""Release publication must preserve candidate identity and privilege boundaries."""

import ast
import hashlib
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/python-release.yml").read_text())
JOBS = WORKFLOW["jobs"]


def step(job, name):
    return next(item for item in JOBS[job]["steps"] if item["name"] == name)


def python_source(block):
    return block.split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]


VERIFY = python_source(step("attest", "Verify candidate identities and checksums")["run"])


def verification_namespace():
    module = ast.parse(VERIFY)
    module.body = [
        item
        for item in module.body
        if isinstance(item, ast.Import | ast.ImportFrom | ast.FunctionDef)
    ]
    namespace = {}
    exec(compile(module, "release-candidate-verifier", "exec"), namespace)
    return namespace


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    root = tmp_path / "bundle"
    (root / "dist").mkdir(parents=True)
    (root / "reports").mkdir()
    files = {
        "dist/best_practices_mcp-0.2.0b1-py3-none-any.whl": b"wheel",
        "dist/best_practices_mcp-0.2.0b1.tar.gz": b"source",
        "reports/runtime-wheel.cdx.json": b"{}",
    }
    for name, content in files.items():
        (root / name).write_bytes(content)
    manifest = {
        "schema_version": 1,
        "tag": "v0.2.0-beta.1",
        "commit": "a" * 40,
        "version": "0.2.0b1",
        "artifacts": {
            name: {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
            for name, content in files.items()
        },
    }
    (root / "release.json").write_text(json.dumps(manifest))
    sums = "".join(
        hashlib.sha256((root / name).read_bytes()).hexdigest() + "  " + Path(name).name + "\n"
        for name in sorted([*files, "release.json"], key=lambda name: Path(name).name)
    )
    (root / "SHA256SUMS").write_text(sums)
    monkeypatch.setenv("RELEASE_TAG", manifest["tag"])
    monkeypatch.setenv("GITHUB_SHA", manifest["commit"])
    return root


def test_exact_candidate_verifies(candidate):
    wheel, sdist = verification_namespace()["verify"](candidate)
    assert wheel.read_bytes() == b"wheel"
    assert sdist.read_bytes() == b"source"


def test_candidate_mutation_is_rejected(candidate):
    next((candidate / "dist").glob("*.whl")).write_bytes(b"replaced")
    with pytest.raises(ValueError, match="checksum or size"):
        verification_namespace()["verify"](candidate)


@pytest.mark.parametrize("name", ["dist/unexpected.whl", "reports/unexpected.txt"])
def test_extra_files_are_rejected(candidate, name):
    (candidate / name).write_bytes(b"extra")
    with pytest.raises(ValueError, match="Unexpected, missing"):
        verification_namespace()["verify"](candidate)


def test_missing_files_are_rejected(candidate):
    (candidate / "reports/runtime-wheel.cdx.json").unlink()
    with pytest.raises(ValueError, match="regular files"):
        verification_namespace()["verify"](candidate)


@pytest.mark.parametrize("name", ["../outside", "/absolute", "reports/a\n::error::x"])
def test_manifest_paths_are_rejected(candidate, name):
    manifest = json.loads((candidate / "release.json").read_text())
    manifest["artifacts"] = {name: {"sha256": "0" * 64, "bytes": 0}}
    (candidate / "release.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Unsafe candidate path"):
        verification_namespace()["verify"](candidate)


def test_candidate_symlink_is_rejected(candidate):
    path = candidate / "reports/runtime-wheel.cdx.json"
    path.unlink()
    try:
        path.symlink_to("../release.json")
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(ValueError, match="regular files"):
        verification_namespace()["verify"](candidate)


@pytest.mark.parametrize("variable", ["RELEASE_TAG", "GITHUB_SHA"])
def test_candidate_for_another_release_is_rejected(candidate, monkeypatch, variable):
    monkeypatch.setenv(variable, "wrong")
    with pytest.raises(ValueError, match="identity|another commit"):
        verification_namespace()["verify"](candidate)


def test_checksum_manifest_is_checked(candidate):
    (candidate / "SHA256SUMS").write_text("incorrect\n")
    with pytest.raises(ValueError, match="Checksum manifest"):
        verification_namespace()["verify"](candidate)


