from rest_framework import viewsets

from apps.core.permissions import HasModulePermission

from .models import Author, Book, BookIssue, Category
from .serializers import (
    AuthorSerializer,
    BookIssueSerializer,
    BookSerializer,
    CategorySerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)


class BookIssueViewSet(viewsets.ModelViewSet):
    queryset = BookIssue.objects.all()
    serializer_class = BookIssueSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        return self.queryset.filter(book__school=self.request.user.school)
