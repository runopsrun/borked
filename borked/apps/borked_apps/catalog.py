"""The optional-app catalog. One pipe-separated line per app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

KINDS = ("dnf", "dnf-repo", "script", "github-rpm", "github-bundle", "virt", "distrobox")


@dataclass(frozen=True)
class App:
    category: str
    id: str
    label: str
    blurb: str
    kind: str
    target: str
    check: str

    def repo_name(self) -> str:
        if self.kind != "dnf-repo":
            raise ValueError(f"{self.id} has no repo")
        return self.target.split()[0]

    def packages(self) -> list[str]:
        if self.kind == "dnf-repo":
            names = self.target.split()[1:]
        elif self.kind in ("dnf", "virt"):
            names = self.target.split()
        else:
            raise ValueError(f"{self.id} is not a dnf app")
        if not names:
            raise ValueError(f"{self.id} lists no packages")
        return names


def root() -> Path:
    here = Path(__file__).resolve().parents[1]
    return here


def load(path: Path | None = None) -> list[App]:
    catalog = path or (root() / "catalog")
    apps: list[App] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(catalog.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) != 7:
            raise SystemExit(f"{catalog}:{lineno}: expected 7 fields, found {len(parts)}")
        app = App(*parts)
        if app.kind not in KINDS:
            raise SystemExit(f"{catalog}:{lineno}: unknown kind {app.kind}")
        if not app.id or app.id in seen:
            raise SystemExit(f"{catalog}:{lineno}: missing or repeated id")
        if app.kind == "dnf-repo" and len(app.target.split()) < 2:
            raise SystemExit(f"{catalog}:{lineno}: dnf-repo needs a repo name and a package")
        if app.kind == "distrobox":
            image, _, name = app.target.partition(" ")
            if not name or " " in name or ":" not in image:
                raise SystemExit(f"{catalog}:{lineno}: distrobox needs an image and a container name")
        if app.kind in ("github-rpm", "github-bundle") and app.target.count("/") < 2:
            raise SystemExit(f"{catalog}:{lineno}: {app.kind} needs owner/repo/glob")
        seen.add(app.id)
        apps.append(app)
    if not apps:
        raise SystemExit(f"{catalog}: no apps")
    return apps


def categories(apps: list[App]) -> list[tuple[str, list[App]]]:
    order: list[str] = []
    grouped: dict[str, list[App]] = {}
    for app in apps:
        if app.category not in grouped:
            order.append(app.category)
            grouped[app.category] = []
        grouped[app.category].append(app)
    return [(name, grouped[name]) for name in order]
