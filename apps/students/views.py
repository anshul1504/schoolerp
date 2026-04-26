import csv
from datetime import date as dt_date
from io import StringIO
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils import timezone
from urllib.parse import urlencode
from django.conf import settings

from apps.core.permissions import has_permission, role_required
from apps.core.ui import build_layout_context
from apps.attendance.models import StudentAttendance
from apps.communication.models import Notice
from apps.exams.models import ExamMark
from apps.fees.models import StudentFeeLedger
from apps.schools.models import School
from apps.schools.limits import active_student_limit_for_school
from apps.academics.models import AcademicYear, ClassMaster, SectionMaster

from .models import (
    AdmissionWorkflowEvent,
    Guardian,
    Student,
    StudentClassChangeHistory,
    StudentCommunicationLog,
    StudentComplianceReminder,
    StudentDisciplineIncident,
    StudentDocument,
    StudentGuardian,
    StudentHealthRecord,
    StudentHistoryEvent,
    StudentProfileEditHistory,
    StudentPromotion,
    TransferCertificate,
    TransferCertificateRequest,
)
from apps.frontoffice.models import Enquiry
from .documents import completeness_score, missing_documents
from apps.core.upload_validation import DEFAULT_DOCUMENT_POLICY, DEFAULT_IMAGE_POLICY, UploadPolicy, antivirus_scan, validate_upload


CLASS_OPTIONS = [
    "Pre-Nursery",
    "Nursery",
    "LKG",
    "UKG",
    *[f"Class {number}" for number in range(1, 13)],
]
SECTION_OPTIONS = ["A", "B", "C", "D"]
BLOOD_GROUP_OPTIONS = [choice[0] for choice in Student.BLOOD_GROUP_CHOICES]
GENDER_OPTIONS = [choice[0] for choice in Student.GENDER_CHOICES]
CATEGORY_OPTIONS = ["General", "OBC", "SC", "ST", "EWS", "Minority", "Other"]
RELIGION_OPTIONS = ["Hindu", "Muslim", "Sikh", "Christian", "Buddhist", "Jain", "Other"]
PREVIOUS_CLASS_OPTIONS = [
    "Pre-Nursery",
    "Nursery",
    "LKG",
    "UKG",
    *[f"Class {number}" for number in range(1, 13)],
]
STREAM_OPTIONS = ["Science", "Commerce", "Arts", "Vocational"]
ADMISSION_STATUS_OPTIONS = ["Pending", "Under Review", "Confirmed", "Active", "On Hold"]
PAGE_SIZE_OPTIONS = [10, 25, 50, 100]
EXPORT_COLUMNS = [
    "admission_no",
    "first_name",
    "middle_name",
    "last_name",
    "gender",
    "date_of_birth",
    "blood_group",
    "class_name",
    "section",
    "roll_number",
    "student_phone",
    "email",
    "aadhar_number",
    "religion",
    "category",
    "mother_tongue",
    "previous_school",
    "play_school_name",
    "medical_conditions",
    "father_name",
    "father_phone",
    "father_email",
    "father_occupation",
    "mother_name",
    "mother_phone",
    "mother_email",
    "mother_occupation",
    "guardian_name",
    "guardian_phone",
    "guardian_email",
    "guardian_occupation",
    "relation_with_student",
    "admission_date",
    "leaving_date",
    "current_address",
    "permanent_address",
    "is_active",
]
SAMPLE_IMPORT_ROWS = [
    {
        "admission_no": "ADM/2026-27/04/0001",
        "first_name": "Aarav",
        "middle_name": "",
        "last_name": "Sharma",
        "gender": "MALE",
        "date_of_birth": "2015-05-12",
        "blood_group": "B+",
        "class_name": "Class 5",
        "section": "A",
        "roll_number": "12",
        "student_phone": "9876543210",
        "email": "aarav@example.com",
        "aadhar_number": "123412341234",
        "religion": "Hindu",
        "category": "General",
        "mother_tongue": "Hindi",
        "previous_school": "Sunrise Public School",
        "play_school_name": "",
        "medical_conditions": "",
        "father_name": "Rakesh Sharma",
        "father_phone": "9876543201",
        "father_email": "rakesh@example.com",
        "father_occupation": "Business",
        "mother_name": "Neha Sharma",
        "mother_phone": "9876543202",
        "mother_email": "neha@example.com",
        "mother_occupation": "Teacher",
        "guardian_name": "Rakesh Sharma",
        "guardian_phone": "9876543201",
        "guardian_email": "rakesh@example.com",
        "guardian_occupation": "Business",
        "relation_with_student": "Father",
        "admission_date": "2026-04-20",
        "leaving_date": "",
        "current_address": "Bhopal, Madhya Pradesh",
        "permanent_address": "Bhopal, Madhya Pradesh",
        "is_active": "True",
    }
]


def _current_academic_year():
    today = timezone.now().date()
    start_year = today.year if today.month >= 4 else today.year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{end_year:02d}"


def _academic_year_code(academic_year):
    value = (academic_year or _current_academic_year()).strip()
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) >= 6:
        return f"{digits[:4]}{digits[-2:]}"
    if len(digits) >= 4:
        return digits[:4]
    today = timezone.now().date()
    return f"{today.year}{(today.year + 1) % 100:02d}"


def _generate_admission_number(academic_year=None, *, school=None):
    month = timezone.now().strftime("%m")
    academic_year_value = (academic_year or _current_academic_year()).strip()
    prefix = f"ADM/{academic_year_value}/{month}/"
    qs = Student.objects.filter(admission_no__startswith=prefix)
    if school is not None:
        qs = qs.filter(school=school)
    last_student = qs.order_by("-id").first()
    next_number = 1

    if last_student:
        try:
            next_number = int(last_student.admission_no.split("/")[-1]) + 1
        except ValueError:
            next_number = last_student.id + 1

    return f"{prefix}{next_number:04d}"


def _student_form_master_options(*, school=None):
    """
    Prefer Academics masters when configured; fall back to hardcoded lists.
    Keeps templates simple (list of strings).
    """
    if school is None:
        return {
            "academic_year_options": [],
            "class_options": CLASS_OPTIONS,
            "section_options": SECTION_OPTIONS,
        }

    years = list(
        AcademicYear.objects.filter(school=school).order_by("-start_date", "-id").values_list("name", flat=True)
    )
    class_names = list(ClassMaster.objects.filter(school=school).order_by("name").values_list("name", flat=True))
    section_names = list(
        SectionMaster.objects.filter(school=school).order_by("name").values_list("name", flat=True)
    )
    return {
        "academic_year_options": years,
        "class_options": class_names or CLASS_OPTIONS,
        "section_options": section_names or SECTION_OPTIONS,
    }


def _next_class_name(current_class):
    current_class = (current_class or "").strip()
    if current_class == "Pre-Nursery":
        return "Nursery"
    if current_class == "Nursery":
        return "LKG"
    if current_class == "LKG":
        return "UKG"
    if current_class == "UKG":
        return "Class 1"
    if current_class.startswith("Class "):
        try:
            class_number = int(current_class.split(" ", 1)[1])
        except (IndexError, ValueError):
            return current_class
        return f"Class {min(class_number + 1, 12)}"
    return current_class


def _generate_tc_number(student):
    year_code = _academic_year_code(getattr(student, "academic_year", ""))
    school_code = getattr(getattr(student, "school", None), "code", "") or "SCH"
    prefix = f"TC/{school_code}/{year_code}/"
    last_certificate = (
        TransferCertificate.objects.select_related("student", "student__school")
        .filter(student__school=student.school, certificate_no__startswith=prefix)
        .order_by("-id")
        .first()
    )
    next_number = 1

    if last_certificate:
        try:
            next_number = int(last_certificate.certificate_no.split("/")[-1]) + 1
        except ValueError:
            next_number = last_certificate.id + 1

    return f"{prefix}{next_number:04d}"


def _phone_with_india_code(value):
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("+"):
        return value
    digits = value.replace(" ", "")
    if digits.startswith("91") and len(digits) >= 12:
        return f"+{digits}"
    return f"+91 {value}"


def _checkbox_value(post_data, key):
    return post_data.get(key) == "on"


def _parse_date_iso(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return dt_date.fromisoformat(value)
    except Exception:
        return None


def _validate_student_minimum(payload):
    required_fields = {
        "first_name": "First name is required.",
        "gender": "Gender is required.",
        "class_name": "Class is required.",
        "section": "Section is required.",
        "guardian_name": "Guardian name is required.",
        "guardian_phone": "Guardian phone is required.",
        "admission_date": "Admission date is required.",
        "admission_no": "Admission number is required.",
    }
    errors = []
    for field, message in required_fields.items():
        if not str(payload.get(field, "")).strip():
            errors.append(message)
    return errors


def _student_payload_from_request(request, *, is_update=False, school=None):
    academic_year = request.POST.get("academic_year", "").strip() or _current_academic_year()
    admission_no = request.POST.get("admission_no", "").strip() or _generate_admission_number(academic_year, school=school)
    guardian_phone = _phone_with_india_code(request.POST["guardian_phone"])
    admission_date_raw = request.POST.get("admission_date", "")
    admission_date = _parse_date_iso(admission_date_raw) or admission_date_raw
    payload = {
        "admission_no": admission_no,
        "academic_year": academic_year,
        "first_name": request.POST["first_name"],
        "middle_name": request.POST.get("middle_name", "").strip(),
        "last_name": request.POST.get("last_name", "").strip(),
        "gender": request.POST["gender"],
        "date_of_birth": _parse_date_iso(request.POST.get("date_of_birth")) or (request.POST.get("date_of_birth") or None),
        "blood_group": request.POST.get("blood_group", "").strip(),
        "class_name": request.POST["class_name"],
        "section": request.POST["section"],
        "roll_number": request.POST.get("roll_number", "").strip(),
        "stream": request.POST.get("stream", "").strip(),
        "house": request.POST.get("house", "").strip(),
        "student_phone": _phone_with_india_code(request.POST.get("student_phone", "")),
        "alternate_mobile": _phone_with_india_code(request.POST.get("alternate_mobile", "")),
        "email": request.POST.get("email", "").strip(),
        "emergency_contact": _phone_with_india_code(request.POST.get("emergency_contact", "")),
        "aadhar_number": request.POST.get("aadhar_number", "").strip(),
        "samagra_id": request.POST.get("samagra_id", "").strip(),
        "pen_number": request.POST.get("pen_number", "").strip(),
        "udise_id": request.POST.get("udise_id", "").strip(),
        "religion": request.POST.get("religion", "").strip(),
        "nationality": request.POST.get("nationality", "").strip(),
        "category": request.POST.get("category", "").strip(),
        "mother_tongue": request.POST.get("mother_tongue", "").strip(),
        "identification_mark_1": request.POST.get("identification_mark_1", "").strip(),
        "identification_mark_2": request.POST.get("identification_mark_2", "").strip(),
        "previous_school": request.POST.get("previous_school", "").strip(),
        "previous_class": request.POST.get("previous_class", "").strip(),
        "play_school_name": request.POST.get("play_school_name", "").strip(),
        "transfer_certificate_number": request.POST.get("transfer_certificate_number", "").strip(),
        "migration_certificate": request.POST.get("migration_certificate", "").strip(),
        "admission_status": request.POST.get("admission_status", "").strip(),
        "medical_conditions": request.POST.get("medical_conditions", "").strip(),
        "father_name": request.POST.get("father_name", "").strip(),
        "father_phone": _phone_with_india_code(request.POST.get("father_phone", "")),
        "father_email": request.POST.get("father_email", "").strip(),
        "father_occupation": request.POST.get("father_occupation", "").strip(),
        "father_income": request.POST.get("father_income", "").strip(),
        "father_aadhar": request.POST.get("father_aadhar", "").strip(),
        "mother_name": request.POST.get("mother_name", "").strip(),
        "mother_phone": _phone_with_india_code(request.POST.get("mother_phone", "")),
        "mother_email": request.POST.get("mother_email", "").strip(),
        "mother_occupation": request.POST.get("mother_occupation", "").strip(),
        "mother_income": request.POST.get("mother_income", "").strip(),
        "mother_aadhar": request.POST.get("mother_aadhar", "").strip(),
        "guardian_name": request.POST["guardian_name"],
        "guardian_phone": guardian_phone,
        "guardian_email": request.POST.get("guardian_email", "").strip(),
        "guardian_occupation": request.POST.get("guardian_occupation", "").strip(),
        "relation_with_student": request.POST.get("relation_with_student", "").strip(),
        "guardian_address": request.POST.get("guardian_address", "").strip(),
        "admission_date": admission_date,
        "leaving_date": _parse_date_iso(request.POST.get("leaving_date")) or (request.POST.get("leaving_date") or None),
        "current_address": request.POST.get("current_address", "").strip(),
        "current_address_line1": request.POST.get("current_address_line1", "").strip(),
        "current_address_line2": request.POST.get("current_address_line2", "").strip(),
        "current_city": request.POST.get("current_city", "").strip(),
        "current_state": request.POST.get("current_state", "").strip(),
        "current_pincode": request.POST.get("current_pincode", "").strip(),
        "permanent_same_as_current": _checkbox_value(request.POST, "permanent_same_as_current"),
        "permanent_address": request.POST.get("permanent_address", "").strip(),
        "permanent_address_line1": request.POST.get("permanent_address_line1", "").strip(),
        "permanent_address_line2": request.POST.get("permanent_address_line2", "").strip(),
        "permanent_city": request.POST.get("permanent_city", "").strip(),
        "permanent_state": request.POST.get("permanent_state", "").strip(),
        "permanent_pincode": request.POST.get("permanent_pincode", "").strip(),
        "disability": _checkbox_value(request.POST, "disability"),
        "disability_details": request.POST.get("disability_details", "").strip(),
        "allergies": request.POST.get("allergies", "").strip(),
        "chronic_disease": request.POST.get("chronic_disease", "").strip(),
        "doctor_name": request.POST.get("doctor_name", "").strip(),
        "emergency_medical_notes": request.POST.get("emergency_medical_notes", "").strip(),
        "subjects": request.POST.get("subjects", "").strip(),
        "previous_percentage": request.POST.get("previous_percentage", "").strip(),
        "previous_grade": request.POST.get("previous_grade", "").strip(),
        "fee_category": request.POST.get("fee_category", "").strip(),
        "scholarship": request.POST.get("scholarship", "").strip(),
        "bank_account_number": request.POST.get("bank_account_number", "").strip(),
        "ifsc_code": request.POST.get("ifsc_code", "").strip(),
        "transport_required": _checkbox_value(request.POST, "transport_required"),
        "route_number": request.POST.get("route_number", "").strip(),
        "bus_number": request.POST.get("bus_number", "").strip(),
        "pickup_point": request.POST.get("pickup_point", "").strip(),
        "driver_contact": _phone_with_india_code(request.POST.get("driver_contact", "")),
        "hostel_required": _checkbox_value(request.POST, "hostel_required"),
        "room_number": request.POST.get("room_number", "").strip(),
        "warden_name": request.POST.get("warden_name", "").strip(),
        "mess_plan": request.POST.get("mess_plan", "").strip(),
        "student_username": admission_no,
        "student_password": "",
        "parent_username": "".join(character for character in guardian_phone if character.isdigit())[-10:] or admission_no,
        "parent_password": "",
    }

    file_fields = {
        "photo": request.FILES.get("photo"),
        "birth_certificate": request.FILES.get("birth_certificate"),
        "aadhar_card": request.FILES.get("aadhar_card"),
        "previous_marksheet": request.FILES.get("previous_marksheet"),
        "transfer_certificate_file": request.FILES.get("transfer_certificate_file"),
        "caste_certificate": request.FILES.get("caste_certificate"),
        "income_certificate": request.FILES.get("income_certificate"),
        "passport_photo": request.FILES.get("passport_photo"),
    }

    if is_update:
        payload["is_active"] = _checkbox_value(request.POST, "is_active")
        payload.update({key: value for key, value in file_fields.items() if value})
    else:
        payload.update(file_fields)

    return payload


def _format_date(value):
    return value.isoformat() if value else ""


def _prefill_student_form(request):
    enquiry = None
    enquiry_id = (request.GET.get("enquiry_id") or "").strip()
    if enquiry_id.isdigit():
        enquiry = Enquiry.objects.filter(id=int(enquiry_id)).first()

    return {
        "enquiry": enquiry,
        "admission_no": _generate_admission_number(_current_academic_year()),
        "first_name": (request.GET.get("first_name") or "").strip(),
        "last_name": (request.GET.get("last_name") or "").strip(),
        "guardian_name": (request.GET.get("guardian_name") or "").strip(),
        "guardian_phone": (request.GET.get("guardian_phone") or "").strip(),
        "guardian_email": (request.GET.get("guardian_email") or "").strip(),
        "class_name": (request.GET.get("class_name") or "").strip(),
        "source_enquiry": (request.GET.get("source_enquiry") or "").strip(),
    }


def _sample_import_dataset():
    return [[row.get(column, "") for column in EXPORT_COLUMNS] for row in SAMPLE_IMPORT_ROWS]


def _export_sample_students_csv():
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="student-import-sample.csv"'
    writer = csv.writer(response)
    writer.writerow(EXPORT_COLUMNS)
    for row in _sample_import_dataset():
        writer.writerow(row)
    return response


def _export_sample_students_excel():
    response = HttpResponse(content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="student-import-sample.xls"'
    header_cells = "".join(f"<th>{column}</th>" for column in EXPORT_COLUMNS)
    rows = []
    for row in _sample_import_dataset():
        rows.append("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>")
    response.write(f"<table><thead><tr>{header_cells}</tr></thead><tbody>{''.join(rows)}</tbody></table>")
    return response


def _build_student_payload(row):
    academic_year = row.get("academic_year", "").strip() or _current_academic_year()
    admission_no = row.get("admission_no", "").strip() or _generate_admission_number(academic_year)
    admission_date = _parse_date_iso(row.get("admission_date")) or (row.get("admission_date", "").strip() or timezone.now().date())
    return {
        "admission_no": admission_no,
        "academic_year": academic_year,
        "first_name": row.get("first_name", "").strip(),
        "middle_name": row.get("middle_name", "").strip(),
        "last_name": row.get("last_name", "").strip(),
        "gender": (row.get("gender", "MALE").strip().upper() or "MALE"),
        "date_of_birth": _parse_date_iso(row.get("date_of_birth")) or (row.get("date_of_birth", "").strip() or None),
        "blood_group": row.get("blood_group", "").strip(),
        "class_name": row.get("class_name", "").strip(),
        "section": row.get("section", "").strip() or "A",
        "roll_number": row.get("roll_number", "").strip(),
        "student_phone": _phone_with_india_code(row.get("student_phone", "")),
        "email": row.get("email", "").strip(),
        "aadhar_number": row.get("aadhar_number", "").strip(),
        "religion": row.get("religion", "").strip(),
        "category": row.get("category", "").strip(),
        "mother_tongue": row.get("mother_tongue", "").strip(),
        "previous_school": row.get("previous_school", "").strip(),
        "play_school_name": row.get("play_school_name", "").strip(),
        "medical_conditions": row.get("medical_conditions", "").strip(),
        "father_name": row.get("father_name", "").strip(),
        "father_phone": _phone_with_india_code(row.get("father_phone", "")),
        "father_email": row.get("father_email", "").strip(),
        "father_occupation": row.get("father_occupation", "").strip(),
        "mother_name": row.get("mother_name", "").strip(),
        "mother_phone": _phone_with_india_code(row.get("mother_phone", "")),
        "mother_email": row.get("mother_email", "").strip(),
        "mother_occupation": row.get("mother_occupation", "").strip(),
        "guardian_name": row.get("guardian_name", "").strip(),
        "guardian_phone": _phone_with_india_code(row.get("guardian_phone", "")),
        "guardian_email": row.get("guardian_email", "").strip(),
        "guardian_occupation": row.get("guardian_occupation", "").strip(),
        "relation_with_student": row.get("relation_with_student", "").strip(),
        "admission_date": admission_date,
        "leaving_date": _parse_date_iso(row.get("leaving_date")) or (row.get("leaving_date", "").strip() or None),
        "current_address": row.get("current_address", "").strip(),
        "permanent_address": row.get("permanent_address", "").strip(),
        "is_active": str(row.get("is_active", "True")).strip().lower() not in {"false", "0", "no"},
    }


def _parse_csv_file(uploaded_file):
    decoded = uploaded_file.read().decode("utf-8-sig")
    return list(csv.DictReader(StringIO(decoded)))


def _parse_xlsx_file(uploaded_file):
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []
    with ZipFile(uploaded_file) as workbook:
        shared_strings = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            shared_strings = [
                "".join(node.itertext()) for node in root.findall("main:si", ns)
            ]
        sheet_root = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        parsed_rows = []
        for row in sheet_root.findall(".//main:sheetData/main:row", ns):
            values = []
            for cell in row.findall("main:c", ns):
                value = cell.find("main:v", ns)
                cell_value = value.text if value is not None else ""
                if cell.get("t") == "s" and cell_value:
                    cell_value = shared_strings[int(cell_value)]
                values.append(cell_value)
            parsed_rows.append(values)
        if not parsed_rows:
            return rows
        headers = [header.strip() for header in parsed_rows[0]]
        for values in parsed_rows[1:]:
            padded = values + [""] * (len(headers) - len(values))
            rows.append(dict(zip(headers, padded)))
    return rows


def _get_school_for_write(request):
    if request.user.role == "SUPER_ADMIN":
        school_id = request.POST.get("school") or request.GET.get("school")
        return School.objects.filter(id=school_id, is_active=True).first()
    return request.user.school


def _remaining_active_student_slots(school):
    limit = active_student_limit_for_school(school.id)
    if not limit:
        return None
    active_count = Student.objects.filter(school=school, is_active=True).count()
    return max(limit - active_count, 0)


def _can_add_active_students(school, count):
    remaining = _remaining_active_student_slots(school)
    if remaining is None:
        return True
    return remaining >= int(count)


def _log_student_history(student, *, actor, action, message="", meta=None):
    StudentHistoryEvent.objects.create(
        student=student,
        school=student.school,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        message=message or "",
        meta=meta or {},
    )


def _log_admission_workflow(student, *, actor, stage, status="DONE", note=""):
    AdmissionWorkflowEvent.objects.create(
        student=student,
        school=student.school,
        stage=stage,
        status=status,
        note=note or "",
        actor=actor if getattr(actor, "is_authenticated", False) else None,
    )


def _capture_profile_edit_history(student, *, actor, old_values, new_values):
    changed_fields = []
    for field, old_value in old_values.items():
        if old_value != new_values.get(field):
            changed_fields.append(field)
    if not changed_fields:
        return
    StudentProfileEditHistory.objects.create(
        student=student,
        school=student.school,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        changed_fields=changed_fields,
        summary=f"Updated {len(changed_fields)} field(s).",
    )


def _log_class_change(student, *, actor, from_class, from_section, to_class, to_section, source="MANUAL", reason="", changed_on=None):
    if from_class == to_class and from_section == to_section:
        return
    StudentClassChangeHistory.objects.create(
        student=student,
        school=student.school,
        from_class=from_class or "",
        from_section=from_section or "",
        to_class=to_class or "",
        to_section=to_section or "",
        reason=reason or "",
        source=source,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        changed_on=changed_on or timezone.now().date(),
    )


def _export_students_csv(students):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="students_export.csv"'
    writer = csv.writer(response)
    writer.writerow(["school_name", *EXPORT_COLUMNS])
    for student in students:
        writer.writerow([
            student.school.name,
            student.admission_no,
            student.first_name,
            student.middle_name,
            student.last_name,
            student.gender,
            _format_date(student.date_of_birth),
            student.blood_group,
            student.class_name,
            student.section,
            student.roll_number,
            student.student_phone,
            student.email,
            student.aadhar_number,
            student.religion,
            student.category,
            student.mother_tongue,
            student.previous_school,
            student.play_school_name,
            student.medical_conditions,
            student.father_name,
            student.father_phone,
            student.father_email,
            student.father_occupation,
            student.mother_name,
            student.mother_phone,
            student.mother_email,
            student.mother_occupation,
            student.guardian_name,
            student.guardian_phone,
            student.guardian_email,
            student.guardian_occupation,
            student.relation_with_student,
            _format_date(student.admission_date),
            _format_date(student.leaving_date),
            student.current_address,
            student.permanent_address,
            "True" if student.is_active else "False",
        ])
    return response


def _export_students_excel(students):
    response = HttpResponse(content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="students_export.xls"'
    header_cells = "".join(f"<th>{column.replace('_', ' ').title()}</th>" for column in ["school_name", *EXPORT_COLUMNS])
    rows = []
    for student in students:
        values = [
            student.school.name,
            student.admission_no,
            student.first_name,
            student.middle_name,
            student.last_name,
            student.gender,
            _format_date(student.date_of_birth),
            student.blood_group,
            student.class_name,
            student.section,
            student.roll_number,
            student.student_phone,
            student.email,
            student.aadhar_number,
            student.religion,
            student.category,
            student.mother_tongue,
            student.previous_school,
            student.play_school_name,
            student.medical_conditions,
            student.father_name,
            student.father_phone,
            student.father_email,
            student.father_occupation,
            student.mother_name,
            student.mother_phone,
            student.mother_email,
            student.mother_occupation,
            student.guardian_name,
            student.guardian_phone,
            student.guardian_email,
            student.guardian_occupation,
            student.relation_with_student,
            _format_date(student.admission_date),
            _format_date(student.leaving_date),
            student.current_address,
            student.permanent_address,
            "True" if student.is_active else "False",
        ]
        rows.append("<tr>" + "".join(f"<td>{value}</td>" for value in values) + "</tr>")
    response.write(f"<table><thead><tr>{header_cells}</tr></thead><tbody>{''.join(rows)}</tbody></table>")
    return response


def _student_queryset_for_user(user):
    if user.role == "SUPER_ADMIN":
        return Student.objects.select_related("school").prefetch_related("documents", "promotions").all()

    if user.school_id:
        return Student.objects.select_related("school").prefetch_related("documents", "promotions").filter(school_id=user.school_id)

    return Student.objects.none()


def _student_permission_flags(user):
    role = getattr(user, "role", "")
    can_manage_students = has_permission(user, "students.manage")
    can_promote_students = role in {"SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "VICE_PRINCIPAL", "ACADEMIC_COORDINATOR", "HOD"}
    return {
        "can_manage_students": can_manage_students,
        "can_promote_students": can_promote_students,
        "can_delete_students": role in {"SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL"},
    }


def _student_full_name(student):
    return f"{student.first_name} {student.middle_name} {student.last_name}".replace("  ", " ").strip()


def _student_operations_summary(student):
    document_count = student.documents.count()
    required_docs_uploaded = completeness_score(student, required="all")["present"]
    needs_attention = []
    if not student.is_active:
        needs_attention.append("Inactive record")
    if not student.emergency_contact:
        needs_attention.append("Emergency contact missing")
    if missing_documents(student, required="basic"):
        needs_attention.append("Admission documents pending")
    if not student.photo:
        needs_attention.append("Profile photo pending")
    if student.medical_conditions or student.allergies or student.chronic_disease or student.disability:
        needs_attention.append("Medical support noted")
    return {
        "document_count": document_count,
        "required_docs_uploaded": required_docs_uploaded,
        "transport_enabled": bool(student.transport_required),
        "hostel_enabled": bool(student.hostel_required),
        "medical_flag": bool(student.medical_conditions or student.allergies or student.chronic_disease or student.disability),
        "account_ready": bool(student.student_username and student.parent_username),
        "needs_attention": needs_attention,
    }


def _student_erp_summary(student):
    attendance_entries = StudentAttendance.objects.filter(student=student).select_related("session")
    fee_ledgers = StudentFeeLedger.objects.filter(student=student).select_related("fee_structure")
    exam_marks = ExamMark.objects.filter(student=student).select_related("exam", "subject")
    notices = Notice.objects.filter(
        school=student.school,
        is_published=True,
        audience__in={"ALL", "STUDENTS"},
    )
    present_count = attendance_entries.filter(status="PRESENT").count()
    attendance_rate = int((present_count / attendance_entries.count()) * 100) if attendance_entries.exists() else 0
    total_due = sum(max((ledger.amount_due - ledger.amount_paid), 0) for ledger in fee_ledgers)
    total_marks = sum(mark.marks_obtained for mark in exam_marks)
    average_marks = round(total_marks / exam_marks.count(), 2) if exam_marks.exists() else 0
    return {
        "attendance_entries": attendance_entries.count(),
        "attendance_rate": attendance_rate,
        "fee_ledger_count": fee_ledgers.count(),
        "outstanding_due": total_due,
        "paid_ledgers": fee_ledgers.filter(status="PAID").count(),
        "exam_marks_count": exam_marks.count(),
        "average_marks": average_marks,
        "notice_count": notices.count(),
        "latest_notice": notices.first(),
    }


def _student_workflow_summary(student):
    docs_basic = completeness_score(student, required="basic")
    return [
        {
            "label": "Admission Profile",
            "status": "Done" if student.admission_no and student.first_name and student.class_name else "Pending",
            "complete": bool(student.admission_no and student.first_name and student.class_name),
            "description": "Student admission, class placement, and base profile are saved.",
            "url": f"/students/{student.id}/edit/",
            "action": "Update",
        },
        {
            "label": "Documents",
            "status": "Done" if docs_basic["percent"] == 100 else "Pending",
            "complete": docs_basic["percent"] == 100,
            "description": "Upload the required admission documents and keep the file complete.",
            "url": f"/students/{student.id}/documents/",
            "action": "Manage",
        },
        {
            "label": "Print Sheet",
            "status": "Ready",
            "complete": True,
            "description": "Open a simple print list with student photos and core details for the printing vendor.",
            "url": f"/students/id-cards/designer/?student_ids={student.id}",
            "action": "Open",
        },
        {
            "label": "Promotion",
            "status": "Done" if student.promotions.exists() else "Pending",
            "complete": student.promotions.exists(),
            "description": "Promote the student to the next class when needed.",
            "url": f"/students/{student.id}/promotion/",
            "action": "Promote",
        },
        {
            "label": "Transfer Certificate",
            "status": "Done" if hasattr(student, "transfer_certificate") else "Pending",
            "complete": hasattr(student, "transfer_certificate"),
            "description": "Generate TC when the student exits the school.",
            "url": f"/students/{student.id}/tc/",
            "action": "Open",
        },
    ]


def _student_completion_status(student):
    operations = _student_operations_summary(student)
    basic_score = completeness_score(student, required="basic")
    checks = {
        "profile": bool(student.first_name and student.admission_no and student.class_name and student.section),
        "guardian": bool(student.guardian_name and student.guardian_phone and student.relation_with_student),
        "contact": bool(student.current_city and student.current_state and student.current_pincode and student.emergency_contact),
        "documents": basic_score["present"] == basic_score["total"],
        "id_ready": bool(student.first_name and student.admission_no and student.class_name),
    }
    completed = sum(1 for value in checks.values() if value)
    total = len(checks)
    missing = []
    if not checks["profile"]:
        missing.append("profile")
    if not checks["guardian"]:
        missing.append("guardian")
    if not checks["contact"]:
        missing.append("contact")
    if not checks["documents"]:
        missing.append("documents")
    if hasattr(student, "transfer_certificate"):
        label = "Transferred"
        tone = "danger"
    elif completed == total:
        label = "Complete"
        tone = "success"
    else:
        label = "In Progress"
        tone = "warning"
    next_step = "Ready for regular school operations"
    if "documents" in missing:
        next_step = "Upload required admission documents"
    elif "contact" in missing:
        next_step = "Complete contact and emergency details"
    elif "guardian" in missing:
        next_step = "Complete guardian authority details"
    elif "profile" in missing:
        next_step = "Complete admission profile"
    elif operations["medical_flag"]:
        next_step = "Review medical support notes"
    return {
        "completed": completed,
        "total": total,
        "percent": int((completed / total) * 100),
        "missing": missing,
        "label": label,
        "tone": tone,
        "next_step": next_step,
        "attention_count": len(operations["needs_attention"]),
        "documents_score": basic_score,
    }


def _truthy_setting(source, key, default=False):
    value = source.get(key)
    if value is None:
        return default
    return value in {"on", "true", "1", "yes"}


ID_CARD_SIZE_OPTIONS = {
    "CR79": {"label": 'CR79 (2.051" x 3.303")', "width": "2.051in", "height": "3.303in"},
    "CR80": {"label": 'CR80 (2.125" x 3.375")', "width": "2.125in", "height": "3.375in"},
    "CR100": {"label": 'CR100 (2.63" x 3.88")', "width": "2.63in", "height": "3.88in"},
}

ID_CARD_PRESETS = {
    "classic-blue": {
        "label": "Classic Blue",
        "front_primary": "#0f172a",
        "front_secondary": "#2563eb",
        "accent_color": "#f97316",
        "text_color": "#0f172a",
        "back_background": "#111827",
        "back_text_color": "#f8fafc",
        "card_title": "Student Identity Card",
        "footer_text": "If found, please return to school office.",
    },
    "emerald-modern": {
        "label": "Emerald Modern",
        "front_primary": "#064e3b",
        "front_secondary": "#10b981",
        "accent_color": "#f59e0b",
        "text_color": "#052e2b",
        "back_background": "#022c22",
        "back_text_color": "#ecfdf5",
        "card_title": "Academic Identity Card",
        "footer_text": "Valid only for current academic session.",
    },
    "sunset-bold": {
        "label": "Sunset Bold",
        "front_primary": "#7c2d12",
        "front_secondary": "#ea580c",
        "accent_color": "#7c3aed",
        "text_color": "#431407",
        "back_background": "#431407",
        "back_text_color": "#fff7ed",
        "card_title": "School Access Card",
        "footer_text": "Carry this card daily while on campus.",
    },
    "royal-purple": {
        "label": "Royal Purple",
        "front_primary": "#312e81",
        "front_secondary": "#7c3aed",
        "accent_color": "#06b6d4",
        "text_color": "#1e1b4b",
        "back_background": "#1e1b4b",
        "back_text_color": "#eef2ff",
        "card_title": "Official Student Card",
        "footer_text": "Unauthorized use of this card is prohibited.",
    },
}


def _id_card_settings_from_request(request):
    source = request.POST if request.method == "POST" else request.GET
    card_size = source.get("card_size", "CR80")
    if card_size not in ID_CARD_SIZE_OPTIONS:
        card_size = "CR80"
    preset = source.get("preset", "classic-blue")
    if preset not in ID_CARD_PRESETS:
        preset = "classic-blue"
    preset_values = ID_CARD_PRESETS[preset]
    return {
        "preset": preset,
        "card_size": card_size,
        "size": ID_CARD_SIZE_OPTIONS[card_size],
        "front_primary": source.get("front_primary", preset_values["front_primary"]),
        "front_secondary": source.get("front_secondary", preset_values["front_secondary"]),
        "accent_color": source.get("accent_color", preset_values["accent_color"]),
        "text_color": source.get("text_color", preset_values["text_color"]),
        "back_background": source.get("back_background", preset_values["back_background"]),
        "back_text_color": source.get("back_text_color", preset_values["back_text_color"]),
        "card_title": source.get("card_title", preset_values["card_title"]).strip() or preset_values["card_title"],
        "footer_text": source.get("footer_text", preset_values["footer_text"]).strip() or preset_values["footer_text"],
        "show_guardian": _truthy_setting(source, "show_guardian", default=True),
        "show_address": _truthy_setting(source, "show_address", default=False),
        "show_dob": _truthy_setting(source, "show_dob", default=True),
        "show_academic_year": _truthy_setting(source, "show_academic_year", default=True),
        "show_student_phone": _truthy_setting(source, "show_student_phone", default=False),
        "show_school_contact": _truthy_setting(source, "show_school_contact", default=True),
        "highlight_name": _truthy_setting(source, "highlight_name", default=True),
    }


def _selected_student_ids_from_request(request, *, source=None):
    source = source or (request.POST if request.method == "POST" else request.GET)
    raw_values = list(source.getlist("student_ids"))
    if not raw_values and source.get("student_ids"):
        raw_values = [source.get("student_ids")]

    ids = []
    for value in raw_values:
        for part in str(value).split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
    return sorted(set(ids))


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER", "RECEPTIONIST")
def student_list(request):
    if not has_permission(request.user, "students.view"):
        messages.error(request, "You do not have permission to view students.")
        return redirect("dashboard")
    students = _student_queryset_for_user(request.user)
    query = request.GET.get("q", "").strip()
    admission_number = request.GET.get("admission_no", "").strip()
    selected_year = request.GET.get("academic_year", "").strip()
    first_name = request.GET.get("first_name", "").strip()
    last_name = request.GET.get("last_name", "").strip()
    selected_class = request.GET.get("class_name", "").strip()
    selected_section = request.GET.get("section", "").strip()
    selected_status = request.GET.get("status", "").strip()
    selected_workflow = request.GET.get("workflow", "").strip()
    requested_view_mode = (request.GET.get("view") or "list").strip().lower()
    selected_sort = request.GET.get("sort", "name").strip()
    selected_direction = request.GET.get("direction", "asc").strip()
    try:
        page_size = int(request.GET.get("page_size", 10))
    except ValueError:
        page_size = 10
    if page_size not in PAGE_SIZE_OPTIONS:
        page_size = 10

    if query:
        students = students.filter(
            Q(admission_no__icontains=query)
            | Q(first_name__icontains=query)
            | Q(middle_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(guardian_name__icontains=query)
        )
    if admission_number:
        students = students.filter(admission_no__icontains=admission_number)
    if selected_year:
        students = students.filter(academic_year=selected_year)
    if first_name:
        students = students.filter(first_name__icontains=first_name)
    if last_name:
        students = students.filter(last_name__icontains=last_name)

    if selected_class:
        students = students.filter(class_name=selected_class)
    if selected_section:
        students = students.filter(section=selected_section)
    if selected_status == "active":
        students = students.filter(is_active=True)
    elif selected_status == "inactive":
        students = students.filter(is_active=False)

    sort_map = {
        "name": ["first_name", "last_name", "id"],
        "admission_no": ["admission_no", "id"],
        "class": ["class_name", "section", "roll_number", "id"],
        "roll_no": ["roll_number", "id"],
        "gender": ["gender", "first_name", "id"],
        "dob": ["date_of_birth", "id"],
        "guardian": ["guardian_name", "first_name", "id"],
    }
    sort_fields = sort_map.get(selected_sort, sort_map["name"])
    if selected_direction == "desc":
        sort_fields = [f"-{field}" for field in sort_fields]
    else:
        selected_direction = "asc"
    students = students.order_by(*sort_fields)

    export_format = request.GET.get("export", "").strip().lower()
    filtered_students = students.distinct()
    if selected_workflow:
        workflow_filtered = []
        for student in filtered_students:
            completion = _student_completion_status(student)
            if selected_workflow == "complete" and completion["label"] == "Complete":
                workflow_filtered.append(student.id)
            elif selected_workflow == "in_progress" and completion["label"] == "In Progress":
                workflow_filtered.append(student.id)
            elif selected_workflow == "transferred" and completion["label"] == "Transferred":
                workflow_filtered.append(student.id)
            elif selected_workflow == "missing_documents" and "documents" in completion["missing"]:
                workflow_filtered.append(student.id)
        filtered_students = filtered_students.filter(id__in=workflow_filtered)

    selected_ids = _selected_student_ids_from_request(request)
    if selected_ids:
        filtered_students = filtered_students.filter(id__in=selected_ids)
    if export_format == "csv":
        return _export_students_csv(filtered_students)
    if export_format == "excel":
        return _export_students_excel(filtered_students)

    view_mode = "classwise" if requested_view_mode == "classwise" else "list"
    if request.user.role == "SCHOOL_OWNER":
        view_mode = "list"

    context = build_layout_context(request.user, current_section="students")
    paginator = Paginator(filtered_students, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    students_with_completion = []
    for student in page_obj.object_list:
        student.workflow = _student_completion_status(student)
        student.operations = _student_operations_summary(student)
        students_with_completion.append(student)
    context["students"] = students_with_completion
    context["page_obj"] = page_obj
    selected_school = request.user.school if request.user.role != "SUPER_ADMIN" else None
    if selected_school:
        master = _student_form_master_options(school=selected_school)
        context["academic_year_options"] = master["academic_year_options"]
        context["class_options"] = master["class_options"]
        context["section_options"] = master["section_options"]
    else:
        context["academic_year_options"] = sorted(
            [year for year in filtered_students.values_list("academic_year", flat=True).distinct() if year],
            reverse=True,
        )
        context["class_options"] = CLASS_OPTIONS
        context["section_options"] = SECTION_OPTIONS
    context["page_size_options"] = PAGE_SIZE_OPTIONS
    context["filters"] = {
        "q": query,
        "admission_no": admission_number,
        "academic_year": selected_year,
        "first_name": first_name,
        "last_name": last_name,
        "class_name": selected_class,
        "section": selected_section,
        "status": selected_status,
        "workflow": selected_workflow,
        "page_size": page_size,
        "sort": selected_sort,
        "direction": selected_direction,
    }
    context["sort_query_base"] = urlencode(
        {
            "q": query,
            "admission_no": admission_number,
            "academic_year": selected_year,
            "first_name": first_name,
            "last_name": last_name,
            "class_name": selected_class,
            "section": selected_section,
            "status": selected_status,
            "workflow": selected_workflow,
            "page_size": page_size,
        }
    )
    context["view_mode"] = view_mode
    context["student_stats"] = {
        "total": filtered_students.count(),
        "active": filtered_students.filter(is_active=True).count(),
        "inactive": filtered_students.filter(is_active=False).count(),
        "classes": filtered_students.values("class_name").distinct().count(),
    }
    workflow_all_students = list(filtered_students)
    context["student_stats"]["complete"] = sum(1 for student in workflow_all_students if _student_completion_status(student)["label"] == "Complete")
    context["student_stats"]["in_progress"] = sum(1 for student in workflow_all_students if _student_completion_status(student)["label"] == "In Progress")
    context["student_stats"]["documents_ready"] = sum(
        1 for student in workflow_all_students if completeness_score(student, required="basic")["percent"] == 100
    )
    context["student_stats"]["support_needed"] = sum(
        1 for student in workflow_all_students if _student_operations_summary(student)["medical_flag"] or _student_operations_summary(student)["transport_enabled"] or _student_operations_summary(student)["hostel_enabled"]
    )
    context.update(_student_permission_flags(request.user))
    return render(request, "students/list.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER", "RECEPTIONIST")
def student_detail(request, slug):
    if not has_permission(request.user, "students.view"):
        messages.error(request, "You do not have permission to view students.")
        return redirect("dashboard")
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)
    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    context["documents_score_basic"] = completeness_score(student, required="basic")
    context["missing_basic_documents"] = missing_documents(student, required="basic")
    context["workflow_steps"] = _student_workflow_summary(student)
    context["student_operations"] = _student_operations_summary(student)
    context["student_workflow"] = _student_completion_status(student)
    context["student_erp_summary"] = _student_erp_summary(student)
    context["student_history"] = StudentHistoryEvent.objects.select_related("actor").filter(student=student)[:20]
    context["admission_workflow_events"] = student.admission_workflow_events.select_related("actor").all()[:10]
    context["profile_edit_events"] = student.profile_edit_history.select_related("actor").all()[:10]
    context["class_change_events"] = student.class_change_history.select_related("actor").all()[:10]
    context["pending_tc_requests_count"] = student.tc_requests.filter(status="PENDING").count()
    context["discipline_open_count"] = student.discipline_incidents.filter(status="OPEN").count()
    context["health_record_count"] = student.health_records.count()
    context["compliance_pending_count"] = student.compliance_reminders.filter(status="PENDING").count()
    context["communication_log_count"] = student.communication_logs.count()
    context.update(_student_permission_flags(request.user))
    return render(request, "students/detail.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER", "RECEPTIONIST")
def student_detail_pdf(request, slug):
    if not has_permission(request.user, "students.view"):
        messages.error(request, "You do not have permission to view students.")
        return redirect("dashboard")
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)
    try:
        from weasyprint import HTML
    except ModuleNotFoundError:
        messages.error(request, "WeasyPrint is not installed in the active project environment yet.")
        return redirect(f"/students/{student.slug}/")

    template = get_template("students/detail_pdf.html")
    context = {
        "student": student,
        "generated_on": timezone.localtime(),
    }
    html = template.render(context)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="student-{student.admission_no.replace("/", "-")}.pdf"'
    base_url = request.build_absolute_uri("/")

    try:
        pdf_bytes = HTML(string=html, base_url=base_url).write_pdf()
    except Exception:
        messages.error(request, "Student PDF could not be generated right now.")
        return redirect(f"/students/{student.slug}/")

    response.write(pdf_bytes)
    return response


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_id_card_designer(request):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    selected_ids = _selected_student_ids_from_request(request, source=request.GET)
    students = _student_queryset_for_user(request.user).filter(id__in=selected_ids).order_by("class_name", "section", "first_name")

    if not students.exists():
        messages.error(request, "Select at least one student to design ID cards.")
        return redirect("/students/")

    school_ids = sorted(set(students.values_list("school_id", flat=True)))
    if len(school_ids) != 1:
        messages.error(request, "Select students from a single school to generate a print sheet.")
        return redirect("/students/")

    context = build_layout_context(request.user, current_section="students")
    context["selected_students"] = students
    context["preview_student"] = students.first()
    context["selected_ids"] = [str(student.id) for student in students]
    context["selected_school"] = students.first().school
    context["id_card_settings"] = _id_card_settings_from_request(request)
    context["id_card_size_options"] = ID_CARD_SIZE_OPTIONS
    context["id_card_presets"] = ID_CARD_PRESETS
    return render(request, "students/id_card_designer.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_id_cards_pdf(request):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    source = request.POST if request.method == "POST" else request.GET
    selected_ids = _selected_student_ids_from_request(request, source=source)
    students = _student_queryset_for_user(request.user).filter(id__in=selected_ids).order_by("class_name", "section", "first_name")

    if not students.exists():
        messages.error(request, "Select at least one student to generate ID cards.")
        return redirect("/students/")

    school_ids = sorted(set(students.values_list("school_id", flat=True)))
    if len(school_ids) != 1:
        messages.error(request, "Select students from a single school to generate a print sheet.")
        return redirect("/students/")

    try:
        from weasyprint import HTML
    except ModuleNotFoundError:
        messages.error(request, "WeasyPrint is not installed in the active project environment yet.")
        return redirect("/students/")

    template = get_template("students/id_cards_pdf.html")
    selected_school = students.first().school
    context = {
        "students": students,
        "generated_on": timezone.localtime(),
        "school": selected_school,
        "id_card_settings": _id_card_settings_from_request(request),
    }
    html = template.render(context)
    response = HttpResponse(content_type="application/pdf")
    school_code = getattr(selected_school, "code", "") or "school"
    date_str = timezone.localdate().isoformat()
    response["Content-Disposition"] = f'attachment; filename="{school_code}-student-print-sheet-{date_str}.pdf"'

    try:
        pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    except Exception:
        messages.error(request, "ID cards PDF could not be generated right now.")
        return redirect("/students/")

    response.write(pdf_bytes)
    return response


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_create(request):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    if request.method == "POST":
        school = request.user.school if request.user.role != "SUPER_ADMIN" else None

        if request.user.role == "SUPER_ADMIN":
            school_id_raw = (request.POST.get("school") or "").strip()
            if school_id_raw.isdigit():
                school = School.objects.filter(id=int(school_id_raw), is_active=True).first()
            else:
                school = None

        if school is None:
            messages.error(request, "Select a valid school before creating a student.")
        else:
            upload_errors: list[str] = []
            upload_errors.extend(
                validate_upload(
                    request.FILES.get("photo"),
                    policy=UploadPolicy(
                        max_bytes=int(getattr(settings, "MAX_STUDENT_PHOTO_BYTES", DEFAULT_IMAGE_POLICY.max_bytes)),
                        allowed_extensions={".png", ".jpg", ".jpeg", ".webp"},
                        allowed_image_formats={"PNG", "JPEG", "WEBP"},
                    ),
                    kind="Photo",
                )
            )
            doc_policy = UploadPolicy(
                max_bytes=int(getattr(settings, "MAX_STUDENT_DOCUMENT_BYTES", DEFAULT_DOCUMENT_POLICY.max_bytes)),
                allowed_extensions=DEFAULT_DOCUMENT_POLICY.allowed_extensions,
                allowed_image_formats=DEFAULT_DOCUMENT_POLICY.allowed_image_formats,
            )
            for field, label in [
                ("birth_certificate", "Birth certificate"),
                ("aadhar_card", "Aadhar card"),
                ("previous_marksheet", "Previous marksheet"),
                ("transfer_certificate_file", "Transfer certificate"),
                ("caste_certificate", "Caste certificate"),
                ("income_certificate", "Income certificate"),
                ("passport_photo", "Passport photo"),
            ]:
                upload_errors.extend(validate_upload(request.FILES.get(field), policy=doc_policy, kind=label))
                if request.FILES.get(field):
                    upload_errors.extend(antivirus_scan(request.FILES.get(field), kind=label))

            if upload_errors:
                for error in upload_errors[:3]:
                    messages.error(request, error)
                return redirect("/students/create/")

            payload = _student_payload_from_request(request, school=school)
            # Enforce per-school admission number uniqueness at UI level (DB constraint exists too).
            if Student.objects.filter(school=school, admission_no=payload.get("admission_no", "")).exists():
                messages.error(request, "Admission number already exists for this school.")
                return redirect("/students/create/")
            errors = _validate_student_minimum(payload)
            if errors:
                for error in errors[:3]:
                    messages.error(request, error)
                return redirect("/students/create/")

            if request.user.role != "SUPER_ADMIN":
                if not _can_add_active_students(school, 1):
                    messages.error(request, "Student limit reached for your current subscription plan.")
                    return redirect("/students/")
            student = Student.objects.create(school=school, **payload)
            source_enquiry_id = (request.POST.get("source_enquiry") or "").strip()
            if source_enquiry_id.isdigit():
                enquiry = Enquiry.objects.filter(id=int(source_enquiry_id), school=school).first()
                if enquiry:
                    enquiry.converted_student = student
                    enquiry.status = "CLOSED"
                    enquiry.save(update_fields=["converted_student", "status", "updated_at"])
            _log_student_history(
                student,
                actor=request.user,
                action="CREATED",
                message="Student admission created.",
            )
            _log_admission_workflow(
                student,
                actor=request.user,
                stage="FORM_SUBMITTED",
                status="DONE",
                note="Student admission form submitted and student created.",
            )
            _log_admission_workflow(
                student,
                actor=request.user,
                stage="ENROLLED",
                status="DONE",
                note="Student enrolled in class and section.",
            )
            messages.success(request, "Student admission created successfully.")
            return redirect(f"/students/{student.slug}/")

    context = build_layout_context(request.user, current_section="students")
    context["school_options"] = [request.user.school] if request.user.school_id else []
    if request.user.role == "SUPER_ADMIN":
        context["school_options"] = School.objects.filter(is_active=True).order_by("name")

    # Use masters for the selected school (or user's school). Create form is school-scoped for non-super-admin.
    selected_school = request.user.school
    if request.user.role == "SUPER_ADMIN":
        # For super admin, allow optional preselect via ?school=<id>
        school_qs_raw = (request.GET.get("school") or "").strip()
        if school_qs_raw.isdigit():
            selected_school = School.objects.filter(id=int(school_qs_raw), is_active=True).first() or selected_school
    master = _student_form_master_options(school=selected_school)
    context["academic_year_options"] = master["academic_year_options"]
    context["class_options"] = master["class_options"]
    context["section_options"] = master["section_options"]
    context["blood_group_options"] = BLOOD_GROUP_OPTIONS
    context["gender_options"] = GENDER_OPTIONS
    context["category_options"] = CATEGORY_OPTIONS
    context["religion_options"] = RELIGION_OPTIONS
    context["previous_class_options"] = PREVIOUS_CLASS_OPTIONS
    context["stream_options"] = STREAM_OPTIONS
    context["admission_status_options"] = ADMISSION_STATUS_OPTIONS
    context["default_academic_year"] = _current_academic_year()
    context["next_admission_no"] = _generate_admission_number(context["default_academic_year"], school=selected_school)
    context["today"] = timezone.now().date()
    context["prefill"] = _prefill_student_form(request)
    return render(request, "students/create.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_import(request):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    if request.method == "POST":
        school = _get_school_for_write(request)
        import_file = request.FILES.get("import_file")
        if school is None:
            messages.error(request, "Select a valid school before importing students.")
        elif not import_file:
            messages.error(request, "Choose a CSV or XLSX file to import.")
        else:
            extension = import_file.name.lower().rsplit(".", 1)[-1]
            try:
                if extension == "csv":
                    rows = _parse_csv_file(import_file)
                elif extension == "xlsx":
                    rows = _parse_xlsx_file(import_file)
                else:
                    rows = []
                    messages.error(request, "Only CSV and XLSX files are supported right now.")
                created_count = 0
                updated_count = 0
                skipped_limit = 0
                remaining_slots = None
                if request.user.role != "SUPER_ADMIN":
                    remaining_slots = _remaining_active_student_slots(school)
                for row in rows:
                    payload = _build_student_payload(row)
                    if not payload["first_name"] or not payload["class_name"] or not payload["guardian_name"]:
                        continue
                    existing = Student.objects.filter(school=school, admission_no=payload["admission_no"]).only("id", "is_active").first()
                    is_new = existing is None
                    will_be_active = bool(payload.get("is_active", True))
                    activating_existing = bool(existing and (not existing.is_active) and will_be_active)
                    consuming_slot = bool(will_be_active and (is_new or activating_existing))

                    if remaining_slots is not None and consuming_slot:
                        if remaining_slots <= 0:
                            skipped_limit += 1
                            continue
                        remaining_slots -= 1

                    _, created = Student.objects.update_or_create(
                        school=school,
                        admission_no=payload["admission_no"],
                        defaults=payload,
                    )
                    if created:
                        created_count += 1
                        created_student = Student.objects.filter(school=school, admission_no=payload["admission_no"]).only("id", "school_id").first()
                        if created_student:
                            _log_student_history(
                                created_student,
                                actor=request.user,
                                action="CREATED",
                                message="Student created via import.",
                                meta={"source": "import"},
                            )
                    else:
                        updated_count += 1
                        updated_student = Student.objects.filter(school=school, admission_no=payload["admission_no"]).only("id", "school_id").first()
                        if updated_student:
                            _log_student_history(
                                updated_student,
                                actor=request.user,
                                action="UPDATED",
                                message="Student updated via import.",
                                meta={"source": "import"},
                            )

                if created_count or updated_count:
                    parts = []
                    if created_count:
                        parts.append(f"{created_count} created")
                    if updated_count:
                        parts.append(f"{updated_count} updated")
                    messages.success(request, "Students imported successfully: " + ", ".join(parts) + ".")
                if skipped_limit:
                    messages.error(request, f"{skipped_limit} rows skipped because your student limit is reached.")
            except Exception:
                messages.error(request, "We could not import that file. Please use the export headers and try again.")
        return redirect("/students/")

    context = build_layout_context(request.user, current_section="students")
    context["school_options"] = [request.user.school] if request.user.school_id else []
    if request.user.role == "SUPER_ADMIN":
        context["school_options"] = School.objects.filter(is_active=True).order_by("name")
    context["sample_headers"] = EXPORT_COLUMNS
    return render(request, "students/import.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_import_sample(request, file_type):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    if file_type == "csv":
        return _export_sample_students_csv()
    if file_type == "excel":
        return _export_sample_students_excel()
    messages.error(request, "Unsupported sample file type.")
    return redirect("/students/import/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_update(request, slug):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)

    if request.method == "POST":
        upload_errors: list[str] = []
        upload_errors.extend(
            validate_upload(
                request.FILES.get("photo"),
                policy=UploadPolicy(
                    max_bytes=int(getattr(settings, "MAX_STUDENT_PHOTO_BYTES", DEFAULT_IMAGE_POLICY.max_bytes)),
                    allowed_extensions={".png", ".jpg", ".jpeg", ".webp"},
                    allowed_image_formats={"PNG", "JPEG", "WEBP"},
                ),
                kind="Photo",
            )
        )
        doc_policy = UploadPolicy(
            max_bytes=int(getattr(settings, "MAX_STUDENT_DOCUMENT_BYTES", DEFAULT_DOCUMENT_POLICY.max_bytes)),
            allowed_extensions=DEFAULT_DOCUMENT_POLICY.allowed_extensions,
            allowed_image_formats=DEFAULT_DOCUMENT_POLICY.allowed_image_formats,
        )
        for field, label in [
            ("birth_certificate", "Birth certificate"),
            ("aadhar_card", "Aadhar card"),
            ("previous_marksheet", "Previous marksheet"),
            ("transfer_certificate_file", "Transfer certificate"),
            ("caste_certificate", "Caste certificate"),
            ("income_certificate", "Income certificate"),
            ("passport_photo", "Passport photo"),
        ]:
            upload_errors.extend(validate_upload(request.FILES.get(field), policy=doc_policy, kind=label))
            if request.FILES.get(field):
                upload_errors.extend(antivirus_scan(request.FILES.get(field), kind=label))

        if upload_errors:
            for error in upload_errors[:3]:
                messages.error(request, error)
            return redirect(f"/students/{student.slug}/edit/")

        payload = _student_payload_from_request(request, is_update=True)
        # Admission number updates are allowed via edit form; keep per-school uniqueness enforced.
        if payload.get("admission_no") and payload["admission_no"] != student.admission_no:
            if Student.objects.filter(school=student.school, admission_no=payload["admission_no"]).exclude(id=student.id).exists():
                messages.error(request, "Admission number already exists for this school.")
                return redirect(f"/students/{student.slug}/edit/")
        errors = _validate_student_minimum(payload)
        if errors:
            for error in errors[:3]:
                messages.error(request, error)
            return redirect(f"/students/{student.slug}/edit/")
        if request.user.role != "SUPER_ADMIN":
            wants_active = payload.get("is_active", student.is_active)
            if wants_active and not student.is_active:
                if not _can_add_active_students(student.school, 1):
                    messages.error(request, "Student limit reached for your current subscription plan.")
                    return redirect(f"/students/{student.id}/edit/")

        tracked_fields = {
            "admission_no": student.admission_no,
            "academic_year": student.academic_year,
            "class_name": student.class_name,
            "section": student.section,
            "roll_number": student.roll_number,
            "guardian_name": student.guardian_name,
            "guardian_phone": student.guardian_phone,
            "admission_status": student.admission_status,
            "is_active": student.is_active,
        }
        from_class = student.class_name
        from_section = student.section
        for field, value in payload.items():
            setattr(student, field, value)
        student.save()
        _capture_profile_edit_history(student, actor=request.user, old_values=tracked_fields, new_values=payload)
        _log_class_change(
            student,
            actor=request.user,
            from_class=from_class,
            from_section=from_section,
            to_class=student.class_name,
            to_section=student.section,
            source="MANUAL",
            reason="Updated from profile edit form.",
        )
        _log_student_history(
            student,
            actor=request.user,
            action="UPDATED",
            message="Student profile updated.",
        )
        messages.success(request, "Student record updated successfully.")
        return redirect(f"/students/{student.slug}/")

    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    master = _student_form_master_options(school=student.school)
    context["academic_year_options"] = master["academic_year_options"]
    context["class_options"] = master["class_options"]
    context["section_options"] = master["section_options"]
    context["blood_group_options"] = BLOOD_GROUP_OPTIONS
    context["gender_options"] = GENDER_OPTIONS
    context["category_options"] = CATEGORY_OPTIONS
    context["religion_options"] = RELIGION_OPTIONS
    context["previous_class_options"] = PREVIOUS_CLASS_OPTIONS
    context["stream_options"] = STREAM_OPTIONS
    context["admission_status_options"] = ADMISSION_STATUS_OPTIONS
    context.update(_student_permission_flags(request.user))
    return render(request, "students/edit.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_documents(request, slug):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        document = request.FILES.get("document")
        if not title or not document:
            messages.error(request, "Document title and file are both required.")
        else:
            doc_policy = UploadPolicy(
                max_bytes=int(getattr(settings, "MAX_STUDENT_DOCUMENT_BYTES", DEFAULT_DOCUMENT_POLICY.max_bytes)),
                allowed_extensions=DEFAULT_DOCUMENT_POLICY.allowed_extensions,
                allowed_image_formats=DEFAULT_DOCUMENT_POLICY.allowed_image_formats,
            )
            errors = validate_upload(document, policy=doc_policy, kind="Document")
            errors.extend(antivirus_scan(document, kind="Document"))
            if errors:
                for error in errors[:2]:
                    messages.error(request, error)
                return redirect(f"/students/{student.slug}/documents/")
            StudentDocument.objects.create(student=student, title=title, document=document)
            _log_student_history(
                student,
                actor=request.user,
                action="DOCUMENT_UPLOADED",
                message=f"Document uploaded: {title}",
            )
            messages.success(request, "Student document uploaded successfully.")
            return redirect(f"/students/{student.slug}/documents/")

    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    return render(request, "students/documents.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_guardians(request, slug):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)

    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        email = (request.POST.get("email") or "").strip()
        relation_text = (request.POST.get("relation_text") or "").strip()
        is_primary = request.POST.get("is_primary") == "on"

        if not full_name:
            messages.error(request, "Guardian name is required.")
            return redirect(f"/students/{student.slug}/guardians/")

        guardian, _ = Guardian.objects.get_or_create(
            school=student.school,
            full_name=full_name,
            phone=phone,
            defaults={"email": email},
        )

        link, created = StudentGuardian.objects.get_or_create(
            student=student,
            guardian=guardian,
            defaults={
                "relation": "OTHER",
                "relation_text": relation_text,
                "is_primary": False,
            },
        )
        if not created:
            if relation_text:
                link.relation_text = relation_text
            if email and not guardian.email:
                guardian.email = email
                guardian.save(update_fields=["email"])

        if is_primary:
            StudentGuardian.objects.filter(student=student, is_primary=True).exclude(id=link.id).update(is_primary=False)
            link.is_primary = True

        link.save()
        _log_student_history(student, actor=request.user, action="UPDATED", message="Guardian saved.")
        messages.success(request, "Guardian saved.")
        return redirect(f"/students/{student.slug}/guardians/")

    guardian_links = StudentGuardian.objects.select_related("guardian").filter(student=student).order_by("-is_primary", "id")
    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    context["guardian_links"] = guardian_links
    return render(request, "students/guardians.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def student_promotion(request, slug):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)

    if hasattr(student, "transfer_certificate") or (getattr(student, "admission_status", "") or "").strip().lower() == "transferred":
        messages.error(request, "This student is already transferred. Promotion is not allowed.")
        return redirect(f"/students/{student.slug}/")

    if request.method == "POST":
        promoted_on = _parse_date_iso(request.POST.get("promoted_on"))
        to_class = (request.POST.get("to_class") or "").strip()
        to_section = (request.POST.get("to_section") or "").strip()
        if not to_class or not to_section or not promoted_on:
            messages.error(request, "To class, section, and promoted date are required.")
            return redirect(f"/students/{student.slug}/promotion/")
        if to_class == student.class_name and to_section == student.section:
            messages.error(request, "Promotion target must be different from the current class/section.")
            return redirect(f"/students/{student.slug}/promotion/")

        if student.admission_date and promoted_on < student.admission_date:
            messages.error(request, "Promotion date cannot be before admission date.")
            return redirect(f"/students/{student.slug}/promotion/")

        if StudentPromotion.objects.filter(student=student, promoted_on=promoted_on, to_class=to_class, to_section=to_section).exists():
            messages.error(request, "A promotion with the same target and date already exists.")
            return redirect(f"/students/{student.slug}/promotion/")

        promotion = StudentPromotion.objects.create(
            student=student,
            from_class=student.class_name,
            from_section=student.section,
            to_class=to_class,
            to_section=to_section,
            promoted_on=promoted_on,
            note=request.POST.get("note", ""),
        )
        student.class_name = promotion.to_class
        student.section = promotion.to_section
        student.save(update_fields=["class_name", "section"])
        _log_class_change(
            student,
            actor=request.user,
            from_class=promotion.from_class,
            from_section=promotion.from_section,
            to_class=promotion.to_class,
            to_section=promotion.to_section,
            source="PROMOTION",
            reason=(promotion.note or "Promoted via promotion workflow."),
            changed_on=promotion.promoted_on,
        )
        _log_student_history(
            student,
            actor=request.user,
            action="PROMOTED",
            message=f"Promoted to {promotion.to_class} - {promotion.to_section}.",
            meta={
                "from_class": promotion.from_class,
                "from_section": promotion.from_section,
                "to_class": promotion.to_class,
                "to_section": promotion.to_section,
                "promoted_on": str(promotion.promoted_on),
            },
        )
        messages.success(request, "Student promoted successfully.")
        return redirect(f"/students/{student.slug}/")

    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    master = _student_form_master_options(school=student.school)
    context["class_options"] = master["class_options"]
    context["section_options"] = master["section_options"]
    context["suggested_next_class"] = _next_class_name(student.class_name)
    context["today"] = timezone.now().date()
    return render(request, "students/promotion.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def student_transfer_certificate(request, slug):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)

    if request.method == "POST":
        action = (request.POST.get("action") or "issue").strip().lower()
        if action == "request":
            reason = (request.POST.get("reason") or "").strip()
            destination_school = (request.POST.get("destination_school") or "").strip()
            tc_request = TransferCertificateRequest.objects.create(
                student=student,
                school=student.school,
                requested_by=request.user if request.user.is_authenticated else None,
                reason=reason,
                destination_school=destination_school,
                status="PENDING",
            )
            _log_student_history(
                student,
                actor=request.user,
                action="UPDATED",
                message="Transfer certificate requested.",
                meta={"tc_request_id": tc_request.id, "status": tc_request.status},
            )
            messages.success(request, "TC request submitted successfully.")
            return redirect(f"/students/{student.slug}/tc/requests/")

        certificate_no = (request.POST.get("certificate_no") or "").strip() or _generate_tc_number(student)
        issue_date = _parse_date_iso(request.POST.get("issue_date"))
        if not certificate_no or not issue_date:
            messages.error(request, "Certificate number and issue date are required.")
            return redirect(f"/students/{student.slug}/tc/")
        tc, created = TransferCertificate.objects.update_or_create(
            student=student,
            defaults={
                "certificate_no": certificate_no,
                "issue_date": issue_date,
                "reason": request.POST.get("reason", ""),
                "destination_school": request.POST.get("destination_school", ""),
                "is_issued": True,
            },
        )
        student.is_active = False
        student.admission_status = "Transferred"
        student.leaving_date = issue_date
        student.transfer_certificate_number = tc.certificate_no
        student.save(update_fields=["is_active", "admission_status", "leaving_date", "transfer_certificate_number"])
        TransferCertificateRequest.objects.filter(student=student, status="PENDING").update(
            status="APPROVED",
            reviewed_by=request.user if request.user.is_authenticated else None,
            review_note="Auto-approved during TC issuance.",
            reviewed_at=timezone.now(),
        )
        _log_student_history(
            student,
            actor=request.user,
            action="TC_ISSUED",
            message=f"Transfer certificate issued: {tc.certificate_no}.",
            meta={"certificate_no": tc.certificate_no, "issue_date": str(tc.issue_date)},
        )
        messages.success(request, "Transfer Certificate generated successfully.")
        return redirect(f"/students/{student.slug}/")

    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    context["suggested_tc_number"] = student.transfer_certificate.certificate_no if hasattr(student, "transfer_certificate") else _generate_tc_number(student)
    context["today"] = timezone.now().date()
    context["pending_tc_requests_count"] = student.tc_requests.filter(status="PENDING").count()
    return render(request, "students/tc.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_admission_workflow(request, slug):
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)
    if request.method == "POST" and has_permission(request.user, "students.manage"):
        stage = (request.POST.get("stage") or "").strip()
        status = (request.POST.get("status") or "").strip() or "IN_PROGRESS"
        note = (request.POST.get("note") or "").strip()
        if stage:
            _log_admission_workflow(student, actor=request.user, stage=stage, status=status, note=note)
            _log_student_history(
                student,
                actor=request.user,
                action="UPDATED",
                message=f"Admission workflow updated: {stage}.",
                meta={"stage": stage, "status": status},
            )
            messages.success(request, "Admission workflow step saved.")
        return redirect(f"/students/{student.slug}/workflow/")

    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    context["workflow_events"] = student.admission_workflow_events.all()[:40]
    context["stage_choices"] = AdmissionWorkflowEvent.STAGE_CHOICES
    context["status_choices"] = AdmissionWorkflowEvent.STATUS_CHOICES
    context.update(_student_permission_flags(request.user))
    return render(request, "students/workflow.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_history_timeline(request, slug):
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)
    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    context["profile_edits"] = student.profile_edit_history.select_related("actor").all()[:100]
    context["class_changes"] = student.class_change_history.select_related("actor").all()[:100]
    context["history_events"] = student.history_events.select_related("actor").all()[:100]
    context.update(_student_permission_flags(request.user))
    return render(request, "students/history_timeline.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_tc_requests(request, slug):
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)
    if request.method == "POST" and has_permission(request.user, "students.manage"):
        request_id = (request.POST.get("request_id") or "").strip()
        action = (request.POST.get("decision") or "").strip().upper()
        if request_id.isdigit() and action in {"APPROVED", "REJECTED", "CLOSED"}:
            tc_request = get_object_or_404(TransferCertificateRequest, id=int(request_id), student=student)
            tc_request.status = action
            tc_request.review_note = (request.POST.get("review_note") or "").strip()
            tc_request.reviewed_by = request.user if request.user.is_authenticated else None
            tc_request.reviewed_at = timezone.now()
            tc_request.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at"])
            _log_student_history(
                student,
                actor=request.user,
                action="UPDATED",
                message=f"TC request marked as {action.title()}.",
                meta={"tc_request_id": tc_request.id, "status": tc_request.status},
            )
            messages.success(request, "TC request updated.")
        return redirect(f"/students/{student.slug}/tc/requests/")

    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    context["tc_requests"] = student.tc_requests.select_related("requested_by", "reviewed_by").all()
    context.update(_student_permission_flags(request.user))
    return render(request, "students/tc_requests.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST", "TEACHER")
def student_discipline(request, slug):
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)
    can_manage = has_permission(request.user, "students.manage")
    if request.method == "POST" and can_manage:
        title = (request.POST.get("title") or "").strip()
        if title:
            incident = StudentDisciplineIncident.objects.create(
                student=student,
                school=student.school,
                title=title,
                description=(request.POST.get("description") or "").strip(),
                severity=(request.POST.get("severity") or "LOW").strip() or "LOW",
                status=(request.POST.get("status") or "OPEN").strip() or "OPEN",
                incident_date=_parse_date_iso(request.POST.get("incident_date")),
                reported_by=request.user if request.user.is_authenticated else None,
            )
            _log_student_history(
                student,
                actor=request.user,
                action="UPDATED",
                message=f"Discipline incident logged: {incident.title}.",
            )
            messages.success(request, "Discipline incident saved.")
        else:
            messages.error(request, "Incident title is required.")
        return redirect(f"/students/{student.slug}/discipline/")

    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    context["incidents"] = student.discipline_incidents.select_related("reported_by").all()[:100]
    context["discipline_severity_choices"] = StudentDisciplineIncident.SEVERITY_CHOICES
    context["discipline_status_choices"] = StudentDisciplineIncident.STATUS_CHOICES
    context["today"] = timezone.localdate()
    context.update(_student_permission_flags(request.user))
    return render(request, "students/discipline.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST", "TEACHER")
def student_health(request, slug):
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)
    can_manage = has_permission(request.user, "students.manage")
    if request.method == "POST" and can_manage:
        title = (request.POST.get("title") or "").strip()
        if title:
            record = StudentHealthRecord.objects.create(
                student=student,
                school=student.school,
                record_type=(request.POST.get("record_type") or "CHECKUP").strip() or "CHECKUP",
                title=title,
                notes=(request.POST.get("notes") or "").strip(),
                record_date=_parse_date_iso(request.POST.get("record_date")),
                next_due_date=_parse_date_iso(request.POST.get("next_due_date")),
                created_by=request.user if request.user.is_authenticated else None,
            )
            _log_student_history(
                student,
                actor=request.user,
                action="UPDATED",
                message=f"Health record added: {record.title}.",
            )
            messages.success(request, "Health record saved.")
        else:
            messages.error(request, "Record title is required.")
        return redirect(f"/students/{student.slug}/health/")

    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    context["health_records"] = student.health_records.select_related("created_by").all()[:100]
    context["health_type_choices"] = StudentHealthRecord.TYPE_CHOICES
    context["today"] = timezone.localdate()
    context.update(_student_permission_flags(request.user))
    return render(request, "students/health.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST", "TEACHER")
def student_compliance(request, slug):
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)
    can_manage = has_permission(request.user, "students.manage")
    if request.method == "POST" and can_manage:
        reminder_type = (request.POST.get("reminder_type") or "").strip()
        if reminder_type:
            reminder = StudentComplianceReminder.objects.create(
                student=student,
                school=student.school,
                reminder_type=reminder_type,
                due_date=_parse_date_iso(request.POST.get("due_date")),
                status=(request.POST.get("status") or "PENDING").strip() or "PENDING",
                note=(request.POST.get("note") or "").strip(),
                created_by=request.user if request.user.is_authenticated else None,
            )
            _log_student_history(
                student,
                actor=request.user,
                action="UPDATED",
                message=f"Compliance reminder added: {reminder.reminder_type}.",
            )
            messages.success(request, "Compliance reminder saved.")
        else:
            messages.error(request, "Reminder type is required.")
        return redirect(f"/students/{student.slug}/compliance/")

    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    context["reminders"] = student.compliance_reminders.select_related("created_by").all()[:100]
    context["compliance_status_choices"] = StudentComplianceReminder.STATUS_CHOICES
    context["today"] = timezone.localdate()
    context.update(_student_permission_flags(request.user))
    return render(request, "students/compliance.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST", "TEACHER")
def student_communication_logs(request, slug):
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)
    can_manage = has_permission(request.user, "students.manage")
    if request.method == "POST" and can_manage:
        message_text = (request.POST.get("message") or "").strip()
        if message_text:
            log = StudentCommunicationLog.objects.create(
                student=student,
                school=student.school,
                channel=(request.POST.get("channel") or "NOTE").strip() or "NOTE",
                subject=(request.POST.get("subject") or "").strip(),
                message=message_text,
                logged_at=timezone.now(),
                created_by=request.user if request.user.is_authenticated else None,
            )
            _log_student_history(
                student,
                actor=request.user,
                action="UPDATED",
                message=f"Communication log added ({log.channel}).",
            )
            messages.success(request, "Communication log saved.")
        else:
            messages.error(request, "Message is required.")
        return redirect(f"/students/{student.slug}/communication-logs/")

    context = build_layout_context(request.user, current_section="students")
    context["student"] = student
    context["communication_logs"] = student.communication_logs.select_related("created_by").all()[:100]
    context["communication_channel_choices"] = StudentCommunicationLog.CHANNEL_CHOICES
    context.update(_student_permission_flags(request.user))
    return render(request, "students/communication_logs.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def student_transfer_certificate_pdf(request, slug):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)

    if not hasattr(student, "transfer_certificate"):
        messages.error(request, "Generate the transfer certificate first.")
        return redirect(f"/students/{student.slug}/tc/")

    try:
        from weasyprint import HTML
    except ModuleNotFoundError:
        messages.error(request, "WeasyPrint is not installed in the active project environment yet.")
        return redirect(f"/students/{student.slug}/tc/")

    template = get_template("students/tc_pdf.html")
    context = {
        "student": student,
        "tc": student.transfer_certificate,
        "generated_on": timezone.localtime(),
    }
    html = template.render(context)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="tc-{student.transfer_certificate.certificate_no.replace("/", "-")}.pdf"'

    try:
        pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    except Exception:
        messages.error(request, "Transfer certificate PDF could not be generated right now.")
        return redirect(f"/students/{student.slug}/tc/")

    response.write(pdf_bytes)
    return response


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def student_delete(request, slug):
    if not has_permission(request.user, "students.manage"):
        messages.error(request, "You do not have permission to manage students.")
        return redirect("/students/")
    student = get_object_or_404(_student_queryset_for_user(request.user), slug=slug)

    if request.method == "POST":
        student_name = str(student)
        _log_student_history(
            student,
            actor=request.user,
            action="DELETED",
            message=f"Student record deleted: {student_name}.",
        )
        student.delete()
        messages.success(request, f"{student_name} deleted successfully.")
        return redirect("/students/")

    messages.error(request, "Invalid delete request.")
    return redirect(f"/students/{student.slug}/")
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER", "RECEPTIONIST")
def student_detail_by_id(request, id):
    student = get_object_or_404(_student_queryset_for_user(request.user), id=id)
    return redirect(f"/students/{student.slug}/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER", "RECEPTIONIST")
def student_detail_pdf_by_id(request, id):
    student = get_object_or_404(_student_queryset_for_user(request.user), id=id)
    return redirect(f"/students/{student.slug}/pdf/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_update_by_id(request, id):
    student = get_object_or_404(_student_queryset_for_user(request.user), id=id)
    if request.method == "POST":
        return student_update(request, student.slug)
    return redirect(f"/students/{student.slug}/edit/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "RECEPTIONIST")
def student_documents_by_id(request, id):
    student = get_object_or_404(_student_queryset_for_user(request.user), id=id)
    if request.method == "POST":
        return student_documents(request, student.slug)
    return redirect(f"/students/{student.slug}/documents/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def student_promotion_by_id(request, id):
    student = get_object_or_404(_student_queryset_for_user(request.user), id=id)
    if request.method == "POST":
        return student_promotion(request, student.slug)
    return redirect(f"/students/{student.slug}/promotion/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def student_transfer_certificate_by_id(request, id):
    student = get_object_or_404(_student_queryset_for_user(request.user), id=id)
    if request.method == "POST":
        return student_transfer_certificate(request, student.slug)
    return redirect(f"/students/{student.slug}/tc/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def student_transfer_certificate_pdf_by_id(request, id):
    student = get_object_or_404(_student_queryset_for_user(request.user), id=id)
    return redirect(f"/students/{student.slug}/tc/pdf/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def student_delete_by_id(request, id):
    student = get_object_or_404(_student_queryset_for_user(request.user), id=id)
    if request.method == "POST":
        return student_delete(request, student.slug)
    return redirect(f"/students/{student.slug}/delete/")
