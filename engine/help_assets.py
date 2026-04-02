"""Static help-image asset resolver."""

from __future__ import annotations

from pathlib import Path


def resolve_help_image_path(is_admin: bool = False) -> Path | None:
    plugin_root = Path(__file__).resolve().parents[1]
    docs_dir = plugin_root / "docs"

    candidates: list[str] = []
    if is_admin:
        candidates.extend(
            [
                "help_admin.png",
                "help-admin.png",
                "help_admin.jpg",
                "help-admin.jpg",
            ]
        )

    candidates.extend(
        [
            "help.png",
            "help.jpg",
            "help-guide.png",
            "help_guide.png",
        ]
    )

    for name in candidates:
        path = docs_dir / name
        if path.exists() and path.is_file():
            return path
    return None
