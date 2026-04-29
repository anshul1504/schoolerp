from rest_framework import serializers

from .models import Author, Book, BookIssue, Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = "__all__"


class BookSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    author_name = serializers.CharField(source="author.name", read_only=True)

    class Meta:
        model = Book
        fields = "__all__"


class BookIssueSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True)
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    staff_name = serializers.CharField(source="staff.get_full_name", read_only=True)

    class Meta:
        model = BookIssue
        fields = "__all__"
