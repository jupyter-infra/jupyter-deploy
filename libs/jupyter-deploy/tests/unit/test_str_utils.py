import unittest

from parameterized import parameterized  # type: ignore

from jupyter_deploy.str_utils import get_trimmed_header, to_cli_option_name


class TestToCliOptionName(unittest.TestCase):
    @parameterized.expand(
        [
            ("FullTitleCase", "full-title-case"),
            ("camelCaseName", "camel-case-name"),
            ("python_var_name", "python-var-name"),
            ("SomeMixed-Case", "some-mixed-case"),
            ("XmlHttpRequest", "xml-http-request"),
            ("API_KEY", "api-key"),
            ("already-kebab-case", "already-kebab-case"),
            ("UPPERCASE", "uppercase"),
            ("lowercase", "lowercase"),
            ("snake_case_variable", "snake-case-variable"),
            ("Mixed_snake_Case", "mixed-snake-case"),
            ("With-Existing-Hyphens", "with-existing-hyphens"),
            ("Multiple___Underscores", "multiple-underscores"),
            ("Multiple---dashes", "multiple-dashes"),
            ("CamelCaseWithNUMBER123", "camel-case-with-number123"),
        ]
    )
    def test_valid_values(self, input_str: str, expect_str: str) -> None:
        result = to_cli_option_name(input_str)
        self.assertEqual(result, expect_str)

    def test_empty_string_does_not_raise(self) -> None:
        result = to_cli_option_name("")
        self.assertEqual(result, "")


class TestTrimmedHeader(unittest.TestCase):
    def test_actual_tf_variables_description(self) -> None:
        full_desc = (
            "      Client ID of the OAuth app that will control access to your jupyter notebooks.\n"
            "\n"
            "    You must create an OAuth app first in your Github account.\n"
            "    1. Open GitHub: https://github.com/\n"
            "    2. Select your user icon on the top right\n"
        )

        expected = "Client ID of the OAuth app that will control access to your jupyter notebooks."
        result = get_trimmed_header(full_desc)
        self.assertEqual(result, expected)

    def test_trim_leading_spaces(self) -> None:
        input_text = "    This has leading spaces"
        expected = "This has leading spaces"

        result = get_trimmed_header(input_text)
        self.assertEqual(result, expected)

    def test_keeps_only_first_line(self) -> None:
        input_text = "First line\nSecond line\nThird line"
        expected = "First line"

        result = get_trimmed_header(input_text)
        self.assertEqual(result, expected)

    def test_trim_first_line_if_too_long(self) -> None:
        long_text = (
            "This is a very long line that exceeds the default maximum length of 120 characters. "
            "It should be trimmed to exactly 120 characters when processed by the get_trimmed_header function."
        )
        max_length = 30
        result = get_trimmed_header(long_text, max_length)
        self.assertEqual(len(result), max_length)
        self.assertEqual(result, long_text[:max_length])

    def test_empty_string_does_not_raise(self) -> None:
        result = get_trimmed_header("")
        self.assertEqual(result, "")

    @parameterized.expand(
        [
            ("Simple text", 120, "Simple text"),
            ("  Indented text", 120, "Indented text"),
            ("First line\nSecond line", 120, "First line"),
            ("", 120, ""),
            ("Short text", 5, "Short"),
            ("\n\nEmpty lines before text", 120, "Empty lines before text"),
            ("Text with\ttabs", 120, "Text with\ttabs"),
            ("   Mixed   spaces   ", 120, "Mixed   spaces   "),
            ("Zero max", 0, ""),
            ("Negative max", -10, ""),
        ]
    )
    def test_trimmed_values(self, input_str: str, max_length: int, expect_str: str) -> None:
        result = get_trimmed_header(input_str, max_length)
        self.assertEqual(result, expect_str)
