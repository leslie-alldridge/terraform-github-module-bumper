import unittest
from bot import add_subscriptions, get_module_version_from_code


class Page:
    def __init__(self, byte_string) -> None:
        super().__init__()
        self.decoded_content = byte_string


class TestBot(unittest.TestCase):
    one_module = b'module "vpc" {\n  source = "git::https://github.com/week-2-notes.git?ref=v1.0.0"\n}\n'
    two_modules_with_same_name = b'module "vpc" {\n  source = "git::https://github.com/week-3-notes.git?ref=v1.0.0"\n}\nvar "junk_code" {}\n module "vpc2" {\n  source = "git::https://github.com/week-3-notes.git?ref=v1.1.0"\n}\n'

    def test_can_parse_subscriptions_json(self):
        expected_keys = ["week-2-notes", "week-3-notes"]

        result = add_subscriptions("test_subscriptions.json")

        self.assertTrue(expected_keys[0] in result)
        self.assertTrue(expected_keys[1] in result)

    def test_get_singular_module_version_from_code(self):
        expected_version = ['v1.0.0']
        expected_string_content = self.one_module.decode("utf-8")

        actual_version, actual_string_content = get_module_version_from_code(
            Page(self.one_module), "week-2-notes")

        self.assertEqual(expected_version, actual_version)
        self.assertEqual(expected_string_content, actual_string_content)

    def test_get_multiple_module_version_from_code(self):
        """
        Multiple module calls are supported     
        """
        expected_version = ['v1.0.0', 'v1.1.0']
        expected_string_content = self.two_modules_with_same_name.decode(
            "utf-8")

        actual_version, actual_string_content = get_module_version_from_code(
            Page(self.two_modules_with_same_name), "week-3-notes")

        self.assertEqual(expected_version, actual_version)
        self.assertEqual(expected_string_content, actual_string_content)

    def test_non_matching_modules_are_ignored(self):
        expected_version = []
        expected_string_content = self.two_modules_with_same_name.decode(
            "utf-8")

        actual_version, actual_string_content = get_module_version_from_code(
            Page(self.two_modules_with_same_name), "week-4-notes")

        self.assertEqual(expected_version, actual_version)
        self.assertEqual(expected_string_content, actual_string_content)

        # Since we use `if not current_version:` in bot.py
        self.assertFalse(actual_version)


if __name__ == '__main__':
    unittest.main()
