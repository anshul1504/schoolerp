import os
from datetime import date
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.research.models import EthicsReview, Grant, ResearchPaper, ResearchProject  # noqa: E402
from apps.schools.models import School  # noqa: E402
from apps.staff.models import StaffMember  # noqa: E402


def test_research_flow():
    print("Starting Research Coordinator Backend Test...")

    # Get or create a test school
    school, _ = School.objects.get_or_create(
        name="Test University", defaults={"currency": "USD", "established_year": 2000}
    )

    # Get or create a PI (Staff Member)
    pi, _ = StaffMember.objects.get_or_create(
        full_name="Dr. Test PI",
        school=school,
        defaults={"designation": "Head of Research", "employee_id": "ST-001"},
    )

    # 1. Create a Project
    project = ResearchProject.objects.create(
        school=school,
        title="Quantum Ethics Study 2026",
        description="Analyzing the ethical implications of quantum computing in academia.",
        pi=pi,
        budget=Decimal("75000.00"),
        start_date=date(2026, 1, 1),
        status="ONGOING",
    )
    print(f"✅ Project Created: {project.title}")

    # 2. Add a Grant
    grant = Grant.objects.create(
        project=project,
        grant_id="GR-QT-2026",
        agency="Global Tech Foundation",
        amount=Decimal("50000.00"),
        received_date=date(2026, 2, 1),
    )
    print(f"✅ Grant Added: {grant.grant_id} - {grant.amount}")

    # 3. Add a Publication
    paper = ResearchPaper.objects.create(
        project=project,
        title="Ethical Bounds of Quantum Supremacy",
        journal="Journal of Future Tech",
        publication_date=date(2026, 3, 15),
        doi="10.1234/qtech.2026.001",
    )
    print(f"✅ Publication Added: {paper.title}")

    # 4. Verify Ethics Review
    ethics, created = EthicsReview.objects.get_or_create(project=project)
    ethics.status = "APPROVED"
    ethics.comments = "Protocol reviewed and approved by IRB."
    ethics.save()
    print(f"✅ Ethics Review Verified/Updated: {ethics.status}")

    # Final check
    assert project.grants.count() >= 1
    assert project.papers.count() >= 1
    assert project.ethics_review.status == "APPROVED"

    print("\n🚀 All Backend Research Flows Verified Successfully!")


if __name__ == "__main__":
    test_research_flow()
