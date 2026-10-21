import unittest

from wattleflow.helpers.sanitiser import UrlSanitiser

SECRET = "s3cr3t"


class TestUrlSanitiser(unittest.TestCase):
    def test_mask_hides_the_password_only(self):
        uri = f"postgres://bob:{SECRET}@DbHost:5432/db?sslmode=require"
        masked = UrlSanitiser.mask(uri)
        self.assertEqual(masked, "postgres://bob:***@DbHost:5432/db?sslmode=require")

    def test_mask_leaves_a_uri_without_credentials(self):
        self.assertEqual(UrlSanitiser.mask("https://host/path"), "https://host/path")

    def test_redact_drops_credentials_query_and_fragment(self):
        text = UrlSanitiser.redact(f"https://user:{SECRET}@Host:9200/path?token={SECRET}#frag")
        self.assertEqual(text, "https://Host:9200/path")

    def test_redact_drops_a_user_name_without_password(self):
        self.assertEqual(UrlSanitiser.redact("https://bob@host/p"), "https://host/p")

    def test_redact_lists_dicts_and_other_types(self):
        self.assertEqual(UrlSanitiser.redact([f"http://u:{SECRET}@h:1"]), ["http://h:1"])
        self.assertEqual(UrlSanitiser.redact({"host": "h", "password": SECRET}), {"host": "h"})
        self.assertEqual(UrlSanitiser.redact(object()), "<object>")


if __name__ == "__main__":
    unittest.main()
