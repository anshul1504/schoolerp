from django.conf import settings
from django.db import models

from apps.schools.models import School
from apps.students.models import Student


class Category(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="library_categories")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Author(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="library_authors")
    name = models.CharField(max_length=150)
    biography = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Book(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="books")
    title = models.CharField(max_length=255)
    isbn = models.CharField(max_length=20, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="books"
    )
    author = models.ForeignKey(
        Author, on_delete=models.SET_NULL, null=True, blank=True, related_name="books"
    )
    publisher = models.CharField(max_length=150, blank=True)
    edition = models.CharField(max_length=50, blank=True)
    shelf_location = models.CharField(max_length=100, blank=True)
    total_copies = models.PositiveIntegerField(default=1)
    available_copies = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class BookIssue(models.Model):
    STATUS_CHOICES = (
        ("ISSUED", "Issued"),
        ("RETURNED", "Returned"),
        ("LOST", "Lost"),
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="issues")
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="book_issues", null=True, blank=True
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="book_issues",
        null=True,
        blank=True,
    )
    issue_date = models.DateField()
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ISSUED")
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.book.title} issued to {self.student or self.staff}"
