# Frontend Cleanup Release Notes

## Scope
This release completes frontend cleanup, style centralization, and template hygiene across rendered app templates while preserving the existing desired UI for `schools`, `alumni`, and `research`.

## Centralized In `static/assets/css/style.css`
- Reusable UI utility classes for icon/avatar sizing, chart heights, truncation, modal layout, and fixed width helpers.
- KPI gradient card variants (`ui-kpi-primary`, `ui-kpi-success`, `ui-kpi-warning`, `ui-kpi-danger`, `ui-kpi-info`).
- Theme swatch classes and logo sizing helpers used by base layout.
- Timetable visual classes migrated from template-local `<style>` blocks.
- Certificate view helper classes and print rules migrated from template-local styles.

## Template Groups Cleaned
- Platform: `templates/platform/*` (selected rendered pages)
- Digital Marketing: list/detail-support pages with repeated inline styling
- Career Counseling: overview cleanup
- Accounts/Students/Activity: inline style reductions and class-based replacements
- Security Office + Compliance Office: KPI cards and detail-page inline style extraction
- Timetable: local style block removed, centralized styles applied
- Base layout: theme picker and logo inline style removal

## Exclusions (Intentional)
- Email templates (`templates/emails/*`, otp/email test mail templates)
- PDF/export-oriented templates where inline/print-specific behavior may be required
- Vendor library files under `static/assets/css/lib/*` and `static/assets/js/*` (left untouched except app-level usage compatibility)

## Validation
- `python manage.py check` passed
- `python -m ruff check apps config scripts --output-format concise` passed
- Targeted template grep confirmed significant inline style reduction and removal from cleaned templates

## Notes
- Golden UI baseline (`schools`, `alumni`, `research`) was preserved; no redesign pass was applied.
- Backend routes/features were not altered in this cleanup; changes are presentation-layer hygiene + consistency.
