"""Build a source-only GitHub ZIP with screenshots, without local data or environments."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TREES = ("api", "lab", "tests", "scripts", "configs", "frontend/src", "docs", "examples", ".github", ".streamlit")
ROOT_FILES = (
    "README.md", "LICENSE", "CONTRIBUTING.md", ".gitignore", "app.py", "pyproject.toml",
    "Start Lab.cmd", "start.ps1", "setup-web.ps1", "requirements-lock.txt",
    "requirements-web.txt", "requirements-web-lock.txt", "IMPLEMENTATION_PLAN_V3_WALK_FORWARD_SHOWCASE.md",
)
FRONTEND_FILES = ("package.json", "package-lock.json", "index.html", "tsconfig.json", "vite.config.ts")
BLOCKED_PARTS = {".git", ".codex", ".agents", ".aws", ".venv", "venv", ".runtime", "node_modules", "__pycache__", ".pytest_cache", "storage", "dist"}
SKIP_FILES = {"docs/akshare_download_probe.json", "docs/EXECUTION_CHECKLIST.md"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".ts", ".tsx", ".css", ".html", ".ps1", ".cmd", ".csv", ".xml"}
SECRET_PATTERN = re.compile(r"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-proj-[A-Za-z0-9_-]{30,}|AKIA[0-9A-Z]{16})")


def included(path):
    rel = path.relative_to(ROOT)
    return (
        path.is_file() and not path.is_symlink()
        and not set(rel.parts).intersection(BLOCKED_PARTS)
        and rel.as_posix() not in SKIP_FILES
        and path.suffix.lower() not in {".pyc", ".log", ".zip", ".sqlite", ".db", ".tsbuildinfo", ".pem", ".key"}
        and not path.name.startswith(".env")
        and path.name != "secrets.toml"
    )


def main():
    candidates = [ROOT / x for x in ROOT_FILES]
    candidates += [ROOT / "frontend" / x for x in FRONTEND_FILES]
    for name in TREES:
        candidates.extend((ROOT / name).rglob("*"))
    for name in ROOT_FILES:
        if not (ROOT / name).is_file():
            raise FileNotFoundError(name)
    chosen = {p.relative_to(ROOT).as_posix(): p for p in candidates if included(p)}
    hashes = {}
    for name, path in sorted(chosen.items()):
        content = path.read_bytes()
        if len(content) >= 25 * 1024 * 1024:
            raise ValueError(f"File exceeds the browser-upload budget: {name}")
        if path.suffix.lower() in TEXT_SUFFIXES and SECRET_PATTERN.search(content.decode("utf-8", errors="replace")):
            raise ValueError(f"Potential credential material detected; inspect locally: {name}")
        hashes[name] = hashlib.sha256(content).hexdigest()
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    archive_path = output / "Shanghai_Strategy_Lab_GitHub_Source.zip"
    manifest = {"kind": "public-source", "historical_market_data_included": False, "files": hashes}
    prefix = "shanghai-strategy-lab/"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, path in sorted(chosen.items()):
            archive.write(path, prefix + name)
        archive.writestr(prefix + "release-manifest.json", json.dumps(manifest, indent=2))
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity check failed")
        for name, expected in hashes.items():
            if hashlib.sha256(archive.read(prefix + name)).hexdigest() != expected:
                raise ValueError(f"Packaged file differs: {name}")
    summary = {
        "archive": archive_path.name,
        "files": len(hashes) + 1,
        "bytes": archive_path.stat().st_size,
        "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "largest_file": max(chosen, key=lambda name: chosen[name].stat().st_size),
        "excluded": ["historical storage", "Python environments", "web runtime", "node_modules", "compiled frontend", "caches", "credentials"],
    }
    (output / "github-source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "github-package-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
