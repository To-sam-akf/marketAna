from data_proccessing.cli import _isolation_violations


def test_standalone_package_has_no_legacy_imports() -> None:
    assert _isolation_violations() == []


def test_project_has_no_legacy_pn_imports() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    offenders = []
    for path in root.rglob("*.py"):
        if any(part.startswith(".") for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        legacy_imports = ("from " + "pn", "import " + "pn")
        if any(token in text for token in legacy_imports):
            offenders.append(str(path.relative_to(root)))
    assert offenders == []
