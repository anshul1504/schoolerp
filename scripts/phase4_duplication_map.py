import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
APPS = ROOT / "apps"
OUT = ROOT / "PHASE4_DUPLICATION_MAP.md"

form_get = 0
search_q = 0
bootstrap_form_control = 0

for p in TEMPLATES.rglob("*.html"):
    t = p.read_text(encoding="utf-8", errors="ignore")
    form_get += len(re.findall(r'<form[^>]*method=["\']get["\']', t, flags=re.I))
    search_q += len(re.findall(r'name=["\']q["\']', t))
    bootstrap_form_control += len(re.findall(r'class=["\'][^"\']*form-control', t))

render_targets = Counter()
for p in APPS.rglob("*.py"):
    if "migrations" in p.parts:
        continue
    t = p.read_text(encoding="utf-8", errors="ignore")
    for m in re.findall(r'render\(\s*request\s*,\s*["\']([^"\']+)["\']', t):
        render_targets[m] += 1

multi_render = [x for x in render_targets.items() if x[1] > 1]
multi_render.sort(key=lambda x: (-x[1], x[0]))

OUT.write_text(
    "\n".join(
        [
            "# Phase 4 Duplication Map",
            "",
            "Static, non-behavioral analysis for next cleanup/refactor batch.",
            "",
            f"- Templates scanned: {len(list(TEMPLATES.rglob('*.html')))}",
            f"- GET forms detected: {form_get}",
            f'- `name="q"` fields detected: {search_q}',
            f"- `form-control` class usages detected: {bootstrap_form_control}",
            "",
            "## Repeated Render Targets (count > 1)",
            *([f"- {name}: {count}" for name, count in multi_render[:60]] or ["- None"]),
            "",
            "## Recommended Next Refactor Targets",
            "- Shared list-filter partial for `q` search + reset actions across list pages.",
            "- Shared generic modal/form partial for create/edit pages with repeated control classes.",
            "- Consolidate repeated dashboard/list card blocks into `templates/includes/` partials.",
        ]
    )
)
