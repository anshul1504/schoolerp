# Multi-System Development Workflow (School ERP)

This SOP is for working on the same project from multiple systems (Laptop/Office PC/Home PC) without losing code or creating avoidable conflicts.

## 1) One-Time Setup Per System

1. Install same Python major/minor version on all systems (example: Python 3.12.x).
2. Clone the same repository directory.
3. Create virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
4. Keep a local `.env` file on each machine (never commit secrets).
5. First sync after clone:
   ```powershell
   git pull origin main
   python manage.py migrate
   ```

## 2) Daily Start Routine (Every Session)

Run these before writing code:

```powershell
.\venv\Scripts\Activate.ps1
git checkout main
git pull origin main
git checkout -b feature/<short-task-name>
python manage.py migrate
```

Example branch names:
- `feature/superadmin-nav`
- `feature/school-owner-permissions`
- `fix/admission-form-validation`

## 3) Daily End Routine (Before Switching System)

```powershell
git add .
git commit -m "<clear message>"
git push -u origin <your-branch>
```

Then either:
1. Open PR to `main`, or
2. Merge only after review/testing.

## 4) Never Work Directly on main

Rules:
1. `main` = stable branch.
2. All work in feature/fix branches.
3. Small, frequent commits are preferred.

## 5) Migration Discipline (Important)

If model changed:

```powershell
python manage.py makemigrations
python manage.py migrate
git add .
git commit -m "Add migrations for <module>"
git push
```

When you pull latest changes on another system:

```powershell
git pull origin main
python manage.py migrate
```

## 6) .env and Secrets Policy

1. Keep `.env` in `.gitignore`.
2. Maintain `.env.example` with placeholder values only.
3. Sync keys manually across systems (same variable names).

Suggested `.env.example` keys:
- `DEBUG=`
- `SECRET_KEY=`
- `ALLOWED_HOSTS=`
- `DATABASE_URL=`
- `EMAIL_HOST=`
- `EMAIL_PORT=`
- `EMAIL_HOST_USER=`
- `EMAIL_HOST_PASSWORD=`

## 7) Database Strategy Across Systems

Choose one:

1. Local DB per system (recommended for normal dev)
- Fast and simple.
- Data differs across systems.

2. Shared dev DB (when exact same dataset needed)
- Use shared Postgres/MySQL endpoint.
- Keep backup + access control.

For your current setup with `db.sqlite3`, prefer local DB per system unless team needs identical live-like data.

## 8) Conflict Avoidance Rules

1. Split ownership by module/file when possible.
2. Rebase/merge frequently from `main`.
3. Avoid long-lived branches.
4. Before editing big files, pull latest first.
5. Keep formatting-only commits separate from functional commits.

## 9) Quick Recovery Commands

### See what changed
```powershell
git status
git diff
```

### Bring latest main into your branch
```powershell
git checkout main
git pull origin main
git checkout <your-branch>
git merge main
```

### After conflict resolution
```powershell
git add .
git commit -m "Resolve merge conflicts"
git push
```

## 10) Practical Team Policy (Use This)

1. Start day: pull + migrate.
2. End day: push all work.
3. No local-only critical work overnight.
4. One feature = one branch.
5. Merge only green-tested branches.

## 11) Minimal Command Template

### Start work
```powershell
.\venv\Scripts\Activate.ps1
git pull origin main
git checkout -b feature/<task>
python manage.py migrate
```

### Finish work
```powershell
git add .
git commit -m "<task summary>"
git push -u origin feature/<task>
```

---

If you want, next step is to add a root `.gitignore` + `.env.example` in this repo with safe defaults so this workflow is fully enforced.
