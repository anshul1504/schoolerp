from django.test import SimpleTestCase


class HostelSmokeTests(SimpleTestCase):
    def test_urls_module_imports(self):
        from . import urls  # noqa: F401

        self.assertIsNotNone(urls)
