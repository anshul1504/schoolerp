# Frontend Conventions

- Use centralized classes in `static/assets/css/style.css` for layout/spacing/icon-box/chart-height patterns.
- Avoid inline `style="..."` in app templates.
- Exceptions: email templates and PDF print templates may keep inline styles for rendering reliability.
- Role-sensitive actions (create/edit/delete/approve/manage) must be rendered only when backend permissions/role flags allow them.
- Reuse shared utility classes before introducing new one-off classes.
