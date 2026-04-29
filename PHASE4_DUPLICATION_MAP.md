# Phase 4 Duplication Map

Static, non-behavioral analysis for next cleanup/refactor batch.

- Templates scanned: 244
- GET forms detected: 48
- `name="q"` fields detected: 24
- `form-control` class usages detected: 761

## Repeated Render Targets (count > 1)
- accounts/login.html: 9
- compliance_office/generic_form.html: 6
- security_office/generic_form.html: 5
- accounts/otp_verify.html: 4
- schools/create.html: 3
- schools/edit.html: 3
- academics/entity_edit.html: 2
- academics/year_form.html: 2
- accounts/activate.html: 2
- alumni/alumni_form.html: 2
- alumni/event_form.html: 2
- alumni/story_form.html: 2
- billing/plan_form.html: 2
- career_counseling/application_form.html: 2
- career_counseling/event_form.html: 2
- career_counseling/session_form.html: 2
- career_counseling/university_form.html: 2
- communication/notice_form.html: 2
- frontoffice/call_form.html: 2
- frontoffice/enquiry_form.html: 2
- frontoffice/meeting_form.html: 2
- frontoffice/overview.html: 2
- frontoffice/template_form.html: 2
- frontoffice/visitor_form.html: 2
- platform/announcements_form.html: 2
- platform/domains_form.html: 2
- platform/role_detail.html: 2
- reports/builder_form.html: 2
- reports/scheduled_form.html: 2
- research/project_form.html: 2
- staff/form.html: 2
- users/create.html: 2

## Recommended Next Refactor Targets
- Shared list-filter partial for `q` search + reset actions across list pages.
- Shared generic modal/form partial for create/edit pages with repeated control classes.
- Consolidate repeated dashboard/list card blocks into `templates/includes/` partials.