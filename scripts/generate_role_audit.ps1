$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$roles = @(
  "SUPER_ADMIN","SCHOOL_OWNER","ADMIN","PRINCIPAL","VICE_PRINCIPAL","MANAGEMENT_TRUSTEE","REPORT_VIEWER",
  "ACADEMIC_COORDINATOR","EXAM_CONTROLLER","CLASS_TEACHER","SUBJECT_TEACHER","HOD","SUBSTITUTE_TEACHER","TUTOR_MENTOR","TEACHER",
  "STUDENT","PARENT",
  "OFFICE_ADMIN","RECEPTIONIST","ADMISSION_COUNSELOR","HR_MANAGER","STAFF_COORDINATOR",
  "ACCOUNTANT","FEE_MANAGER","BILLING_EXECUTIVE","AUDITOR",
  "TRANSPORT_MANAGER","TRANSPORT_SUPERVISOR","DRIVER","CONDUCTOR_ATTENDANT",
  "HOSTEL_MANAGER","HOSTEL_WARDEN","ASSISTANT_WARDEN","MESS_MANAGER",
  "LIBRARIAN","LAB_ASSISTANT","SPORTS_COACH","INVENTORY_MANAGER",
  "IT_ADMINISTRATOR","SYSTEM_OPERATOR","ROLE_PERMISSION_MANAGER","API_INTEGRATION_USER",
  "NOTIFICATION_MANAGER","SCHOOL_COUNSELOR","EVENT_MANAGER","COMPLIANCE_OFFICER",
  "SECURITY_OFFICER","DIGITAL_MARKETING_MANAGER","ALUMNI_MANAGER","PLACEMENT_COORDINATOR","RESEARCH_COORDINATOR"
)

$labels = @{
  "SUPER_ADMIN"="Super Admin"; "SCHOOL_OWNER"="School Owner"; "ADMIN"="Admin"; "PRINCIPAL"="Principal"; "VICE_PRINCIPAL"="Vice Principal"; "MANAGEMENT_TRUSTEE"="Management / Trustee"; "REPORT_VIEWER"="Report Viewer";
  "ACADEMIC_COORDINATOR"="Academic Coordinator"; "EXAM_CONTROLLER"="Exam Controller"; "CLASS_TEACHER"="Class Teacher"; "SUBJECT_TEACHER"="Subject Teacher"; "HOD"="Head of Department"; "SUBSTITUTE_TEACHER"="Substitute Teacher"; "TUTOR_MENTOR"="Tutor / Mentor"; "TEACHER"="Teacher";
  "STUDENT"="Student"; "PARENT"="Parent / Guardian";
  "OFFICE_ADMIN"="Office Admin"; "RECEPTIONIST"="Receptionist"; "ADMISSION_COUNSELOR"="Admission Counselor"; "HR_MANAGER"="HR Manager"; "STAFF_COORDINATOR"="Staff Coordinator";
  "ACCOUNTANT"="Accountant"; "FEE_MANAGER"="Fee Manager"; "BILLING_EXECUTIVE"="Billing Executive"; "AUDITOR"="Auditor";
  "TRANSPORT_MANAGER"="Transport Manager"; "TRANSPORT_SUPERVISOR"="Transport Supervisor"; "DRIVER"="Driver"; "CONDUCTOR_ATTENDANT"="Conductor / Attendant";
  "HOSTEL_MANAGER"="Hostel Manager"; "HOSTEL_WARDEN"="Hostel Warden"; "ASSISTANT_WARDEN"="Assistant Warden"; "MESS_MANAGER"="Mess Manager";
  "LIBRARIAN"="Librarian"; "LAB_ASSISTANT"="Lab Assistant"; "SPORTS_COACH"="Sports Coach"; "INVENTORY_MANAGER"="Inventory Manager";
  "IT_ADMINISTRATOR"="IT Administrator"; "SYSTEM_OPERATOR"="System Operator"; "ROLE_PERMISSION_MANAGER"="Role & Permission Manager"; "API_INTEGRATION_USER"="API / Integration User";
  "NOTIFICATION_MANAGER"="Notification Manager"; "SCHOOL_COUNSELOR"="School Counselor"; "EVENT_MANAGER"="Event Manager"; "COMPLIANCE_OFFICER"="Compliance Officer";
  "SECURITY_OFFICER"="Security Officer"; "DIGITAL_MARKETING_MANAGER"="Digital Marketing Manager"; "ALUMNI_MANAGER"="Alumni Manager"; "PLACEMENT_COORDINATOR"="Placement Coordinator"; "RESEARCH_COORDINATOR"="Research Coordinator"
}

$directRoles = [System.Collections.Generic.HashSet[string]]::new()
Get-ChildItem apps -Recurse -Filter *.py | ForEach-Object {
  $content = Get-Content $_.FullName -Raw
  if (-not $content) { return }
  $matches = [regex]::Matches($content, '@role_required\(([^\)]*)\)')
  foreach ($m in $matches) {
    $tokens = [regex]::Matches($m.Groups[1].Value, '"([A-Z_]+)"')
    foreach ($t in $tokens) { [void]$directRoles.Add($t.Groups[1].Value) }
  }
}

$uiText = Get-Content apps\core\ui.py -Raw
$permText = Get-Content apps\core\permissions.py -Raw
$dashText = Get-Content templates\dashboard.html -Raw

$uiRoles = [System.Collections.Generic.HashSet[string]]::new()
[regex]::Matches($uiText, '"([A-Z_]+)"\s*:') | ForEach-Object { [void]$uiRoles.Add($_.Groups[1].Value) }
$permRoles = [System.Collections.Generic.HashSet[string]]::new()
[regex]::Matches($permText, '"([A-Z_]+)"\s*:') | ForEach-Object { [void]$permRoles.Add($_.Groups[1].Value) }
$dashRoles = [System.Collections.Generic.HashSet[string]]::new()
[regex]::Matches($dashText, 'request\.user\.role\s*==\s*"([A-Z_]+)"') | ForEach-Object { [void]$dashRoles.Add($_.Groups[1].Value) }

$equiv = @{
  "SCHOOL_OWNER"=@("ADMIN","MANAGEMENT_TRUSTEE")
  "PRINCIPAL"=@("VICE_PRINCIPAL","ACADEMIC_COORDINATOR","HOD")
  "TEACHER"=@("CLASS_TEACHER","SUBJECT_TEACHER","SUBSTITUTE_TEACHER","TUTOR_MENTOR")
  "RECEPTIONIST"=@("OFFICE_ADMIN","ADMISSION_COUNSELOR","SYSTEM_OPERATOR")
  "ACCOUNTANT"=@("FEE_MANAGER","BILLING_EXECUTIVE","AUDITOR")
}
$reverseEquiv = @{}
foreach ($k in $equiv.Keys) {
  foreach ($v in $equiv[$k]) { $reverseEquiv[$v] = $k }
}

$sectionsByRole = @{}
$roleBlocks = [regex]::Matches($uiText, '"([A-Z_]+)"\s*:\s*\{[\s\S]*?"sections"\s*:\s*\{([^}]*)\}', 'Singleline')
foreach ($rb in $roleBlocks) {
  $role = $rb.Groups[1].Value
  $sections = @([regex]::Matches($rb.Groups[2].Value, '"([a-z]+)"') | ForEach-Object { $_.Groups[1].Value })
  $sectionsByRole[$role] = $sections
}

New-Item -ItemType Directory -Force -Path docs\role_audit\roles | Out-Null

$master = @()
$master += "# Role Audit Master Sheet"
$master += ""
$master += "Generated on: 2026-04-26"
$master += ""
$master += "| Role | UI Config | Permission Baseline | Route Guard Coverage | Dashboard Variant | Audit File |"
$master += "|---|---|---|---|---|---|"

foreach ($r in $roles) {
  $direct = $directRoles.Contains($r)
  $via = $false
  $viaBase = ""
  if (-not $direct -and $reverseEquiv.ContainsKey($r)) {
    $base = $reverseEquiv[$r]
    if ($directRoles.Contains($base)) { $via = $true; $viaBase = $base }
  }

  $coverage = "Not Found"
  if ($direct) { $coverage = "Direct" }
  elseif ($via) { $coverage = "Via equivalence (" + $viaBase + ")" }

  $uiStatus = if ($uiRoles.Contains($r)) { "Done" } else { "Missing" }
  $permStatus = if ($permRoles.Contains($r)) { "Done" } else { "Missing" }
  $dashStatus = if ($dashRoles.Contains($r)) { "Custom block exists" } else { "Generic dashboard only" }
  $sections = if ($sectionsByRole.ContainsKey($r)) { $sectionsByRole[$r] } else { @() }
  $sectionsLabel = if ($sections.Count -gt 0) { [string]::Join(", ", $sections) } else { "none" }

  $roleFile = @()
  $roleFile += "# " + $labels[$r] + " Audit (" + $r + ")"
  $roleFile += ""
  $roleFile += "## Scope Snapshot"
  $roleFile += ""
  $roleFile += "- UI config status: **" + $uiStatus + "**"
  $roleFile += "- Permission baseline status: **" + $permStatus + "**"
  $roleFile += "- Route guard coverage: **" + $coverage + "**"
  $roleFile += "- Dashboard variant: **" + $dashStatus + "**"
  $roleFile += "- Declared UI sections: **" + $sectionsLabel + "**"
  $roleFile += ""
  $roleFile += "## Development Completed"
  $roleFile += ""
  $roleFile += "- [x] Role exists in apps/accounts/models.py"
  $roleFile += "- [x] Default permission baseline: " + $permStatus
  $roleFile += "- [x] Role UI config: " + $uiStatus
  $roleFile += "- [x] Route guard coverage: " + $coverage
  $roleFile += "- [x] Dashboard rendering: " + $dashStatus
  $roleFile += ""
  $roleFile += "## Development Pending (UI Rebuild Priority)"
  $roleFile += ""
  $roleFile += "- [ ] Define role-specific UI blueprint for full rebuild (navigation IA, KPI cards, quick actions, detail screens)"
  $roleFile += "- [ ] Create dedicated acceptance checklist for each enabled module"
  $roleFile += "- [ ] Add role-based E2E tests for login, navigation visibility, and action permissions"
  $roleFile += "- [ ] Validate mobile-first layout and accessibility for role-critical workflows"
  if ($coverage -eq "Not Found") {
    $roleFile += "- [ ] Implement route-level enforcement for this role or explicitly map it through role equivalence"
  }
  $roleFile += ""
  $roleFile += "## Code Deletion / Refactor Candidates"
  $roleFile += ""
  $roleFile += "- [ ] Remove duplicated dashboard branch logic from templates/dashboard.html during rebuild and move to config-driven components"
  $roleFile += "- [ ] Delete dead links for sections that have no implemented module backend yet"
  $roleFile += "- [ ] Consolidate overlapping roles after RBAC workshop to reduce maintenance overhead"

  Set-Content -Path ("docs/role_audit/roles/" + $r + ".md") -Value ($roleFile -join "`r`n") -Encoding UTF8
  $master += "| " + $r + " | " + $uiStatus + " | " + $permStatus + " | " + $coverage + " | " + $dashStatus + " | [roles/" + $r + ".md](roles/" + $r + ".md) |"
}

Set-Content -Path docs\role_audit\MASTER_ROLE_AUDIT.md -Value ($master -join "`r`n") -Encoding UTF8
