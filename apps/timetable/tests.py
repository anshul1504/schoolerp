from django.test import SimpleTestCase


class TimetableSmokeTests(SimpleTestCase):
    def test_urls_module_imports(self):
        from . import urls  # noqa: F401

        self.assertIsNotNone(urls)
