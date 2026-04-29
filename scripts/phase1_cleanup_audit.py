from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
APPS_DIR = ROOT / "apps"
OUTPUT = ROOT / "PHASE1_SAFE_CLEANUP_REPORT.md"

RE_RENDER = re.compile(r'render\(\s*request\s*,\s*["\']([^"\']+)["\']')
RE_EXTENDS = re.compile(r'\{\%\s*extends\s+["\']([^"\']+)["\']\s*\%\}')
RE_INCLUDE = re.compile(r'\{\%\s*include\s+["\']([^"\']+)["\']\s*\%\}')


def all_templates() -> set[str]:
    out = set()
    for p in TEMPLATES_DIR.rglob("*.html"):
        out.add(str(p.relative_to(TEMPLATES_DIR)).replace("\\", "/"))
    for p in TEMPLATES_DIR.rglob("*.txt"):
        out.add(str(p.relative_to(TEMPLATES_DIR)).replace("\\", "/"))
    return out


def referenced_templates() -> set[str]:
    refs = set()
    for py in APPS_DIR.rglob("*.py"):
        txt = py.read_text(encoding="utf-8", errors="ignore")
        refs.update(RE_RENDER.findall(txt))
    for t in TEMPLATES_DIR.rglob("*.html"):
        txt = t.read_text(encoding="utf-8", errors="ignore")
        refs.update(RE_EXTENDS.findall(txt))
        refs.update(RE_INCLUDE.findall(txt))
    return {r.replace("\\", "/") for r in refs}


def main() -> None:
    existing = all_templates()
    refs = referenced_templates()

    missing = sorted(r for r in refs if r not in existing and not r.startswith("admin/"))
    unreferenced = sorted(p for p in existing if p not in refs)

    demo_unreferenced = [p for p in unreferenced if p.startswith("demo/")]
    non_demo_unreferenced = [p for p in unreferenced if not p.startswith("demo/")]

    OUTPUT.write_text(
        "\n".join(
            [
                "# Phase 1 Safe Cleanup Report",
                "",
                "This report is static-analysis only and makes no runtime behavior changes.",
                "",
                f"- Total templates discovered: {len(existing)}",
                f"- Total template references discovered: {len(refs)}",
                f"- Missing referenced templates: {len(missing)}",
                f"- Unreferenced templates: {len(unreferenced)}",
                f"- Unreferenced demo templates: {len(demo_unreferenced)}",
                f"- Unreferenced non-demo templates: {len(non_demo_unreferenced)}",
                "",
                "## Missing Referenced Templates",
                "",
                *(missing or ["- None"]),
                "",
                "## Unreferenced Non-Demo Templates (Review Before Deletion)",
                "",
                *([f"- {p}" for p in non_demo_unreferenced] or ["- None"]),
                "",
                "## Unreferenced Demo Templates",
                "",
                *([f"- {p}" for p in demo_unreferenced] or ["- None"]),
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
