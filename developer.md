# SCHOOL ERP – DEVELOPER LEVEL AUDIT & IMPLEMENTATION SPEC

## Purpose

This document is a **developer-focused audit + execution blueprint**. It defines:

* Exact features
* Required input fields
* RBAC (Role-Based Access Control)
* Missing logic
* Implementation expectations

This is intended so a developer can **directly build missing features without ambiguity**.

---

# 1. CORE ARCHITECTURE EXPECTATION

## Apps (Expected Structure)

* accounts
* students
* admissions
* academics
* attendance
* fees
* exams
* timetable
* communication
* reports
* frontoffice
* transport (missing)
* hostel (missing)
* library (missing)

---

# 2. RBAC MATRIX (DEVELOPER LEVEL)

## Roles

* Super Admin
* School Admin
* Teacher
* Accountant
* Parent
* Student

## Permission Types

* view
* create
* edit
* delete
* approve
* export

### Example RBAC Mapping

#### Student Module

| Role    | Permissions          |
| ------- | -------------------- |
| Admin   | full                 |
| Teacher | view, edit (limited) |
| Parent  | view own child       |
| Student | view self            |

#### Fees Module

| Role       | Permissions |
| ---------- | ----------- |
| Admin      | full        |
| Accountant | full        |
| Parent     | view + pay  |
| Student    | view        |

---

# 3. MODULE-WISE DEVELOPER SPEC

---

## 3.1 STUDENT MANAGEMENT (90%)

### Required Fields (Model)

* admission_no (unique)
* first_name
* last_name
* gender
* dob
* blood_group
* category
* religion
* phone
* email
* address
* city
* state
* pincode
* father_name
* mother_name
* guardian_phone
* admission_date
* class_id (FK)
* section_id (FK)
* status

### Missing / Improve

* Validation rules (required + formats)
* Parent linking (multi-child)
* Document upload structure normalization

---

## 3.2 ADMISSIONS (80%)

### Fields

* application_no
* student_name
* parent_name
* phone
* email
* previous_school
* documents
* status (applied/review/approved/rejected)

### Missing

* Entrance test module
* Interview scheduling
* Admission fee workflow

---

## 3.3 ATTENDANCE (CRITICAL - 30%)

### Required Models

#### AttendanceSession

* date
* class
* section
* teacher

#### Attendance

* student (FK)
* status (present/absent/late/leave)
* remarks

### Missing Logic

* Bulk marking UI
* Monthly summary
* Parent notification
* Leave request approval

---

## 3.4 FEES MODULE (CRITICAL - 35%)

### Models Required

#### FeeStructure

* class
* fee_type (tuition, transport, etc.)
* amount

#### FeeInvoice

* student
* total_amount
* due_date
* status

#### Payment

* invoice
* amount
* mode (cash/online)
* transaction_id

### Missing

* Receipt generation
* Partial payment
* Late fine
* Discount/concession
* Payment gateway integration

---

## 3.5 EXAMS MODULE (30%)

### Models

* Exam
* Subject
* Marks

### Required Fields

* exam_name
* class
* subject
* max_marks
* obtained_marks

### Missing

* Grade calculation
* Result publish
* Report card PDF
* Ranking system

---

## 3.6 TIMETABLE (NOT BUILT - 5%)

### Required Model

* class
* section
* day
* period
* subject
* teacher

### Features

* Clash detection
* Teacher availability
* Auto scheduler (optional)

---

## 3.7 COMMUNICATION (65%)

### Models

* Notification
* Template
* Campaign

### Missing

* WhatsApp API integration
* Delivery tracking
* Segmentation filters

---

## 3.8 REPORTS (55%)

### Required

* Fee report
* Attendance report
* Exam report

### Missing

* Charts/graphs
* Dashboard KPIs

---

# 4. API REQUIREMENTS (IMPORTANT)

System must expose APIs:

* /api/students/
* /api/attendance/
* /api/fees/
* /api/exams/
* /api/reports/

Use Django REST Framework properly:

* serializers
* viewsets
* permissions

---

# 5. VALIDATION RULES

* Email must be unique
* Phone must be numeric
* Admission number must be unique
* DOB cannot be future
* Fees cannot be negative

---

# 6. CRITICAL DEV ISSUES

* Remove all: `except: pass`
* Add logging
* Add transaction.atomic where needed
* Normalize database where possible

---

# 7. UI/UX DEV REQUIREMENTS

* Use component-based frontend
* Mobile responsive
* Table filters + pagination
* Inline editing where possible

---

# 8. PRIORITY IMPLEMENTATION ORDER

1. Fees system
2. Attendance system
3. Exams result
4. Timetable
5. Parent portal
6. Communication upgrade

---

# FINAL NOTE

This ERP is structurally strong but **workflow incomplete**.

Developer focus should be:
➡️ Workflow completion
➡️ Data validation
➡️ RBAC enforcement
➡️ UI usability

Once these are done, product becomes **market ready SaaS ERP**.
