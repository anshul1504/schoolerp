import random
import string
import uuid
from datetime import timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.schools.models import School
from apps.students.models import Student

FIRST_NAMES = [
    "Aarav",
    "Vivaan",
    "Aditya",
    "Vihaan",
    "Arjun",
    "Reyansh",
    "Muhammad",
    "Sai",
    "Ayaan",
    "Krishna",
    "Ishaan",
    "Shaurya",
    "Atharv",
    "Dhruv",
    "Kabir",
    "Rohan",
    "Anaya",
    "Diya",
    "Ira",
    "Myra",
    "Aadhya",
    "Aarohi",
    "Sara",
    "Kiara",
    "Nisha",
    "Pooja",
    "Riya",
    "Sanya",
    "Naina",
    "Meera",
]

LAST_NAMES = [
    "Sharma",
    "Verma",
    "Gupta",
    "Singh",
    "Kumar",
    "Patel",
    "Mehta",
    "Jain",
    "Shah",
    "Khan",
    "Yadav",
    "Chauhan",
    "Mishra",
    "Das",
    "Roy",
    "Nair",
    "Iyer",
    "Reddy",
    "Joshi",
    "Bose",
]

SECTIONS = ["A", "B", "C", "D"]

CLASS_NAMES = [
    "Pre-Nursery",
    "Nursery",
    "LKG",
    "UKG",
    "Class 1",
    "Class 2",
    "Class 3",
    "Class 4",
    "Class 5",
    "Class 6",
    "Class 7",
    "Class 8",
    "Class 9",
    "Class 10",
    "Class 11",
    "Class 12",
]

GUARDIAN_RELATIONS = ["Father", "Mother", "Guardian", "Uncle", "Aunt"]
OCCUPATIONS = [
    "Teacher",
    "Business",
    "Service",
    "Self-employed",
    "Farmer",
    "Doctor",
    "Engineer",
    "Homemaker",
]


def _rand_phone():
    return "9" + "".join(random.choice(string.digits) for _ in range(9))


def _academic_years(now_year=None):
    year = now_year or timezone.now().year
    # Example: 2025-26, 2024-25, 2023-24
    return [
        f"{year - 1}-{str(year % 100).zfill(2)}",
        f"{year - 2}-{str((year - 1) % 100).zfill(2)}",
        f"{year - 3}-{str((year - 2) % 100).zfill(2)}",
    ]


def _slugify_email_part(value: str) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _maybe_email(first, last, domain="schoolflow.test"):
    if random.random() < 0.62:
        user = f"{_slugify_email_part(first)}.{_slugify_email_part(last)}"
        user = user.strip(".") or _slugify_email_part(first) or "student"
        suffix = str(random.randint(10, 999))
        return f"{user}{suffix}@{domain}"
    return ""


def _xlsx_cell_ref(col_idx: int, row_idx: int) -> str:
    # col_idx: 0 => A, 25 => Z, 26 => AA
    col = ""
    n = col_idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        col = chr(65 + rem) + col
    return f"{col}{row_idx}"


def _write_simple_xlsx(path: Path, headers, rows):
    # Minimal XLSX with sharedStrings + sheet1.xml (enough for our importer in apps.students.views)
    strings = []
    string_index = {}

    def s(value):
        value = "" if value is None else str(value)
        if value not in string_index:
            string_index[value] = len(strings)
            strings.append(value)
        return string_index[value]

    sheet_rows = [headers] + rows

    def xml_escape(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    shared_strings_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{0}" uniqueCount="{0}">'.format(
            len(strings)
        ),
    ]
    # Build after we’ve seen all values

    # Build sheet xml referencing shared strings
    sheet_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for r_idx, row in enumerate(sheet_rows, start=1):
        sheet_xml.append(f'<row r="{r_idx}">')
        for c_idx, value in enumerate(row):
            idx = s(value)
            ref = _xlsx_cell_ref(c_idx, r_idx)
            sheet_xml.append(f'<c r="{ref}" t="s"><v>{idx}</v></c>')
        sheet_xml.append("</row>")
    sheet_xml.extend(["</sheetData>", "</worksheet>"])

    # Now finalize sharedStrings.xml
    for value in strings:
        shared_strings_xml.append(f"<si><t>{xml_escape(value)}</t></si>")
    shared_strings_xml.append("</sst>")

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        z.writestr("xl/worksheets/sheet1.xml", "\n".join(sheet_xml))
        z.writestr("xl/sharedStrings.xml", "\n".join(shared_strings_xml))


class Command(BaseCommand):
    help = "Seed demo students for testing (safe, role-agnostic)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=1000, help="Number of students to create (default: 1000)"
        )
        parser.add_argument(
            "--school-id", type=int, default=None, help="Seed only for a specific School ID"
        )
        parser.add_argument(
            "--per-school",
            type=int,
            default=None,
            help="Seed N students per active school (overrides --count)",
        )
        parser.add_argument(
            "--prefix", type=str, default="SEED", help="Admission number prefix (default: SEED)"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without writing to DB",
        )
        parser.add_argument(
            "--purge",
            action="store_true",
            help="Delete previously seeded students for the target school(s)",
        )
        parser.add_argument(
            "--make-import-samples",
            action="store_true",
            help="Generate sample import CSV + XLSX files in --out-dir",
        )
        parser.add_argument(
            "--out-dir",
            type=str,
            default=".",
            help="Output directory for sample files (default: current dir)",
        )
        parser.add_argument(
            "--sample-rows",
            type=int,
            default=50,
            help="Rows to write in sample import files (default: 50)",
        )

    def handle(self, *args, **options):
        count = max(1, int(options["count"] or 1))
        school_id = options["school_id"]
        per_school = options["per_school"]
        prefix = (options["prefix"] or "SEED").strip().upper()
        dry_run = bool(options["dry_run"])
        purge = bool(options["purge"])
        make_samples = bool(options["make_import_samples"])
        out_dir = Path(options["out_dir"] or ".")
        sample_rows = max(5, min(5000, int(options["sample_rows"] or 50)))

        schools = School.objects.filter(is_active=True).order_by("id")
        if school_id:
            schools = schools.filter(id=school_id)

        schools = list(schools)
        if not schools:
            self.stderr.write("No active schools found for seeding.")
            return

        if purge and not dry_run:
            deleted = Student.objects.filter(
                school_id__in=[s.id for s in schools], admission_no__startswith=f"{prefix}/"
            ).delete()[0]
            self.stdout.write(f"Purged {deleted} seeded students (prefix {prefix}/).")

        if per_school is not None:
            per_school = max(1, int(per_school))
            targets = [(school, per_school) for school in schools]
        else:
            # Spread across schools if multiple.
            base = count // len(schools)
            rem = count % len(schools)
            targets = []
            for idx, school in enumerate(schools):
                targets.append((school, base + (1 if idx < rem else 0)))

        total_to_create = sum(n for _, n in targets)
        years = _academic_years()

        self.stdout.write(
            f"Seeding {total_to_create} students across {len(schools)} school(s). dry_run={dry_run}"
        )

        students_to_create = []
        today = timezone.now().date()

        roll_counters = {}
        for school, n in targets:
            # Month buckets to simulate "new admissions" vs "old"
            for i in range(n):
                academic_year = random.choice(years)
                class_name = random.choice(CLASS_NAMES)
                section = random.choice(SECTIONS)

                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                middle = random.choice(["", "", "", random.choice(FIRST_NAMES)])

                gender = random.choice(["MALE", "FEMALE"])
                # 15% inactive/left
                is_active = random.random() > 0.15

                # Admission dates: mix of recent and older
                if random.random() < 0.35:
                    admission_date = today - timedelta(days=random.randint(0, 45))
                else:
                    admission_date = today - timedelta(days=random.randint(46, 520))

                leaving_date = None
                if not is_active:
                    leaving_date = admission_date + timedelta(days=random.randint(30, 480))
                    if leaving_date > today:
                        leaving_date = today - timedelta(days=random.randint(1, 30))

                # Unique admission number per school:
                # e.g. SEED/2025-26/04/000123
                month = str(admission_date.month).zfill(2)
                serial = str(i + 1).zfill(6)
                admission_no = f"{prefix}/{academic_year}/{month}/{serial}"

                slug = f"seed-{school.id}-{uuid.uuid4().hex[:10]}"

                guardian_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                guardian_phone = _rand_phone()
                guardian_email = _maybe_email(
                    guardian_name.split(" ", 1)[0], guardian_name.split(" ", 1)[1]
                )
                relation = random.choice(GUARDIAN_RELATIONS)

                # Roll numbers: sequential per (school, year, class, section)
                roll_key = (school.id, academic_year, class_name, section)
                roll_counters[roll_key] = roll_counters.get(roll_key, 0) + 1
                roll_number = str(roll_counters[roll_key])

                student_email = _maybe_email(first, last)
                father_name = f"{random.choice(FIRST_NAMES)} {last}"
                mother_name = f"{random.choice(FIRST_NAMES)} {last}"
                father_phone = _rand_phone() if random.random() < 0.75 else ""
                mother_phone = _rand_phone() if random.random() < 0.75 else ""

                is_new = (today - admission_date).days <= 45
                admission_status = "NEW_ADMISSION" if is_new else "OLD_STUDENT"

                students_to_create.append(
                    Student(
                        school=school,
                        slug=slug,
                        admission_no=admission_no,
                        academic_year=academic_year,
                        first_name=first,
                        middle_name=middle,
                        last_name=last,
                        gender=gender,
                        class_name=class_name,
                        section=section,
                        roll_number=roll_number,
                        email=student_email,
                        guardian_name=guardian_name,
                        guardian_phone=guardian_phone,
                        guardian_email=guardian_email,
                        relation_with_student=relation,
                        guardian_occupation=random.choice(OCCUPATIONS),
                        father_name=father_name,
                        father_phone=father_phone,
                        father_email=_maybe_email(
                            father_name.split(" ", 1)[0],
                            father_name.split(" ", 1)[1],
                            domain="guardian.test",
                        ),
                        father_occupation=random.choice(OCCUPATIONS),
                        mother_name=mother_name,
                        mother_phone=mother_phone,
                        mother_email=_maybe_email(
                            mother_name.split(" ", 1)[0],
                            mother_name.split(" ", 1)[1],
                            domain="guardian.test",
                        ),
                        mother_occupation=random.choice(OCCUPATIONS),
                        admission_date=admission_date,
                        leaving_date=leaving_date,
                        is_active=is_active,
                        admission_status=admission_status,
                    )
                )

        if dry_run:
            self.stdout.write(f"Dry run: would create {len(students_to_create)} students.")
            if not make_samples:
                return

        if make_samples:
            headers = [
                "academic_year",
                "admission_no",
                "admission_date",
                "first_name",
                "middle_name",
                "last_name",
                "gender",
                "class_name",
                "section",
                "roll_number",
                "student_phone",
                "email",
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
                "current_address",
                "permanent_address",
                "is_active",
            ]

            def rand_addr():
                return f"House {random.randint(1, 220)}, Sector {random.randint(1, 60)}, City"

            sample = []
            for idx in range(sample_rows):
                academic_year = random.choice(years)
                class_name = random.choice(CLASS_NAMES)
                section = random.choice(SECTIONS)
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                admission_date = today - timedelta(days=random.randint(0, 520))
                month = str(admission_date.month).zfill(2)
                admission_no = f"{prefix}/{academic_year}/{month}/{str(idx + 1).zfill(6)}"
                guardian_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                sample.append(
                    [
                        academic_year,
                        admission_no,
                        admission_date.isoformat(),
                        first,
                        "",
                        last,
                        random.choice(["MALE", "FEMALE"]),
                        class_name,
                        section,
                        str(random.randint(1, 60)),
                        _rand_phone(),
                        _maybe_email(first, last),
                        f"{random.choice(FIRST_NAMES)} {last}",
                        _rand_phone(),
                        _maybe_email("father", last, domain="guardian.test"),
                        random.choice(OCCUPATIONS),
                        f"{random.choice(FIRST_NAMES)} {last}",
                        _rand_phone(),
                        _maybe_email("mother", last, domain="guardian.test"),
                        random.choice(OCCUPATIONS),
                        guardian_name,
                        _rand_phone(),
                        _maybe_email(
                            guardian_name.split(" ", 1)[0],
                            guardian_name.split(" ", 1)[1],
                            domain="guardian.test",
                        ),
                        random.choice(OCCUPATIONS),
                        random.choice(GUARDIAN_RELATIONS),
                        rand_addr(),
                        rand_addr(),
                        "True" if random.random() > 0.12 else "False",
                    ]
                )

            out_dir.mkdir(parents=True, exist_ok=True)
            csv_path = out_dir / "student-import-sample.csv"
            xlsx_path = out_dir / "student-import-sample.xlsx"

            # CSV
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                f.write(",".join(headers) + "\n")
                for row in sample:
                    f.write(",".join('"{}"'.format(str(v).replace('"', '""')) for v in row) + "\n")

            # XLSX (minimal zip)
            _write_simple_xlsx(xlsx_path, headers, sample)

            self.stdout.write(self.style.SUCCESS(f"Wrote sample files: {csv_path} and {xlsx_path}"))

            if dry_run:
                return

        with transaction.atomic():
            Student.objects.bulk_create(students_to_create, batch_size=500)

        self.stdout.write(self.style.SUCCESS(f"Created {len(students_to_create)} students."))
