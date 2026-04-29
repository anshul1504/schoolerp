# Phase 2 Needs-Review Decisions

Generated on: 2026-04-29
Source: `PHASE1_SAFE_CLEANUP_REPORT.md`

## Decision Summary

- Reviewed candidates: 22
- Keep (confirmed runtime or indirect usage): 21
- Remove now: 0
- Needs manual business decision: 1 (`demo/index.html` missing reference target)

## File-by-File Decisions

1. `accounts/otp_email.html` -> KEEP
- Used by `apps/accounts/views.py` via `render_to_string("accounts/otp_email.html", ...)`.

2. `accounts/otp_email.txt` -> KEEP
- Used by `apps/accounts/views.py` via `render_to_string("accounts/otp_email.txt", ...)`.

3. `accounts/password_reset_complete.html` -> KEEP
- Used by Django auth view mapping in `apps/accounts/urls.py`.

4. `accounts/password_reset_confirm.html` -> KEEP
- Used by Django auth view mapping in `apps/accounts/urls.py`.

5. `accounts/password_reset_done.html` -> KEEP
- Used by Django auth view mapping in `apps/accounts/urls.py`.

6. `accounts/password_reset_form.html` -> KEEP
- Used by Django auth view mapping in `apps/accounts/urls.py`.

7. `emails/invitation.html` -> KEEP
- Used in `apps/core/views_users.py` and `apps/schools/views.py` via `render_to_string`.

8. `emails/invitation.txt` -> KEEP
- Used in `apps/core/views_users.py` and `apps/schools/views.py` via `render_to_string`.

9. `exams/report_card_pdf.html` -> KEEP
- Used by `apps/exams/views.py` in PDF generation path.

10. `fees/receipt_pdf.html` -> KEEP
- Used by `apps/fees/views.py` in receipt PDF generation path.

11. `includes/dashboard_components.html` -> KEEP (for now)
- Not currently resolved via direct `include` scan; retain to avoid accidental design-system breakage during ongoing UI refactors.

12. `platform/_superadmin_nav.html` -> KEEP (for now)
- Not directly linked in static scan; likely partial for platform pages and should remain until template-component consolidation phase.

13. `platform/communication_logs.html` -> KEEP
- Used by `apps/core/views_platform.py` route `super_admin_communication_logs`.

14. `research/exports/project_detail_pdf.html` -> KEEP
- Used by `apps/research/views.py` export path.

15. `research/exports/project_list_pdf.html` -> KEEP
- Used by `apps/research/views.py` export path.

16. `security_office/incident_form.html` -> KEEP (for now)
- Security office flows mix generic form usage and feature-specific pages; hold until flow normalization.

17. `security_office/visitor_form.html` -> KEEP (for now)
- Same reason as above; retain to avoid regressions while module refactor is pending.

18. `settings/email_test_email.html` -> KEEP
- Used by `apps/core/views_settings.py` via `render_to_string`.

19. `students/_student_nav.html` -> KEEP (for now)
- Shared partial candidate; retain until explicit component usage map and cleanup PR.

20. `students/detail_pdf.html` -> KEEP
- Used by `apps/students/views.py` via `get_template`.

21. `students/id_cards_pdf.html` -> KEEP
- Used by `apps/students/views.py` via `get_template`.

22. `students/tc_pdf.html` -> KEEP
- Used by `apps/students/views.py` via `get_template`.

## Additional Finding

- Missing template reference from phase-1 report: `demo/index.html`
- Source: `apps/core/views.py` demo route rendering logic.
- Decision: no code change in phase 2. Handle in Phase 3 by either:
  1. restoring a minimal `templates/demo/index.html`, or
  2. removing/guarding demo routes when demo pages are disabled.

## Phase 2 Outcome

Phase 2 (`needs-review`) is complete: no safe deletions approved from the phase-1 flagged template list due to confirmed or probable runtime usage.
