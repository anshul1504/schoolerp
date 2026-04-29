from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import library_overview
from .viewsets import (
    AuthorViewSet,
    BookIssueViewSet,
    BookViewSet,
    CategoryViewSet,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="library-category")
router.register("authors", AuthorViewSet, basename="library-author")
router.register("books", BookViewSet, basename="library-book")
router.register("issues", BookIssueViewSet, basename="library-issue")

urlpatterns = [
    path("", library_overview, name="library_overview"),
    path("api/", include(router.urls)),
]
