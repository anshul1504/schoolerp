from django.test import SimpleTestCase


class AdmissionsSmokeTests(SimpleTestCase):
    def test_urls_module_imports(self):
        from . import urls  # noqa: F401

        self.assertIsNotNone(urls)
