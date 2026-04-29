from django.test import SimpleTestCase


class CareerCounselingSmokeTests(SimpleTestCase):
    def test_urls_module_imports(self):
        from . import urls  # noqa: F401

        self.assertIsNotNone(urls)
