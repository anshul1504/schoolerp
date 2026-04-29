$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$templateRoot = "templates"
$outputRoot = "docs/ui_rebuild"
$folderOutput = Join-Path $outputRoot "folders"

New-Item -ItemType Directory -Force -Path $folderOutput | Out-Null

$folders = Get-ChildItem $templateRoot -Directory | Sort-Object Name
$allHtml = Get-ChildItem $templateRoot -Recurse -File -Include *.html

$master = @()
$master += "# Folder-wise UI Rebuild Master Plan"
$master += ""
$master += "Generated on: 2026-04-26"
$master += ""
$master += "## Rebuild Rules"
$master += ""
$master += "- Keep backend URLs, forms, and permissions unchanged during UI-only phase."
$master += "- Rebuild module-by-module: base shell first, then high-volume modules."
$master += "- Each folder must pass desktop + mobile + role-visibility checks before moving next."
$master += "- Remove duplicated UI blocks after replacement is live."
$master += ""
$master += "## Global Sequence"
$master += ""
$master += "1. Foundation: tokens, layout shell, navigation, form components"
$master += "2. High-volume modules: platform, frontoffice, students, accounts, billing"
$master += "3. Core school ops: schools, settings, users, academics, reports"
$master += "4. Remaining modules: admissions, staff, communication, attendance, fees, exams, activity, emails"
$master += ""
$master += "## Folder Tracker"
$master += ""
$master += "| Folder | HTML Files | Priority | Target Sprint | Checklist |"
$master += "|---|---:|---|---|---|"

foreach ($folder in $folders) {
  $name = $folder.Name
  $files = Get-ChildItem $folder.FullName -Recurse -File -Include *.html
  $count = @($files).Count

  $priority = "P2"
  if ($name -in @("platform", "frontoffice", "students", "accounts", "billing")) { $priority = "P0" }
  elseif ($name -in @("schools", "settings", "users", "academics", "reports")) { $priority = "P1" }

  $sprint = if ($priority -eq "P0") { "Sprint 1-2" } elseif ($priority -eq "P1") { "Sprint 3-4" } else { "Sprint 5+" }
  $checkPath = "folders/$name.md"
  $master += "| $name | $count | $priority | $sprint | [$name]($checkPath) |"

  $lines = @()
  $lines += "# UI Rebuild Checklist: $name"
  $lines += ""
  $lines += "## Scope"
  $lines += ""
  $lines += ("- Folder: templates/" + $name)
  $lines += "- HTML files: **$count**"
  $lines += "- Priority: **$priority**"
  $lines += "- Target sprint: **$sprint**"
  $lines += ""
  $lines += "## Page Inventory"
  $lines += ""
  if ($count -eq 0) {
    $lines += "- No HTML pages found."
  } else {
    foreach ($f in $files | Sort-Object FullName) {
      $rel = $f.FullName.Replace((Get-Location).Path + "\", "").Replace("\", "/")
      $lines += ("- [ ] " + $rel)
    }
  }
  $lines += ""
  $lines += "## Implementation Checklist"
  $lines += ""
  $lines += "- [ ] Map each page to one of: list, detail, form, dashboard, wizard, settings."
  $lines += "- [ ] Replace legacy spacing/typography with token-based styles."
  $lines += "- [ ] Standardize cards, tables, filters, and action bars."
  $lines += "- [ ] Ensure all forms have consistent labels, errors, and help text."
  $lines += "- [ ] Ensure mobile layout for <= 768px is fully usable."
  $lines += "- [ ] Ensure role-based actions are visible/hidden correctly."
  $lines += "- [ ] Remove obsolete per-page CSS/JS blocks after migration."
  $lines += ""
  $lines += "## QA Checklist"
  $lines += ""
  $lines += "- [ ] Visual QA on desktop (1280+ width)"
  $lines += "- [ ] Visual QA on mobile (360-430 width)"
  $lines += "- [ ] Form submit and validation flow verified"
  $lines += "- [ ] Empty state / no-data state verified"
  $lines += "- [ ] Permissions and action buttons verified by role"

  Set-Content -Path (Join-Path $folderOutput "$name.md") -Value ($lines -join "`r`n") -Encoding UTF8
}

$master += ""
$master += "## Shared Foundation Work"
$master += ""
$master += "- [ ] Finalize design tokens in static/css/tokens.css."
$master += "- [ ] Create reusable UI primitives in templates/base.html sections/includes."
$master += "- [ ] Normalize dashboard patterns from templates/dashboard.html into reusable blocks."
$master += "- [ ] Define migration guideline for removing old utility classes safely."

Set-Content -Path (Join-Path $outputRoot "UI_REBUILD_MASTER.md") -Value ($master -join "`r`n") -Encoding UTF8
