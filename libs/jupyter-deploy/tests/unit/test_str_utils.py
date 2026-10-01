import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

from parameterized import parameterized  # type: ignore
from pydantic import BaseModel, ValidationError

from jupyter_deploy import str_utils
from jupyter_deploy.str_utils import (
    format_timestamp,
    get_trimmed_header,
    to_cli_option_name,
    to_list_str,
)


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


class TestToListStr(unittest.TestCase):
    def test_empty_str_returns_empty_list(self) -> None:
        self.assertEqual(to_list_str(""), [])
        self.assertEqual(to_list_str("", sep="|"), [])

    @parameterized.expand(
        [
            ("a,b,c", None, ["a", "b", "c"]),
            ("a,b,c", ",", ["a", "b", "c"]),
            ("a,b,c", ";", ["a,b,c"]),
            ("a,b;c", ";", ["a,b", "c"]),
            ("abc", None, ["abc"]),
            ("abc", ",", ["abc"]),
            ("ab|b", "|", ["ab", "b"]),
        ]
    )
    def test_values(self, input_str: str, sep: str | None, expect_list: list[str]) -> None:
        if sep:
            self.assertEqual(to_list_str(input_str, sep=sep), expect_list)
        else:
            self.assertEqual(to_list_str(input_str), expect_list)


class _ListModel(BaseModel):
    assigned_value: list[str] | None = None


class _ListMapModel(BaseModel):
    assigned_value: list[dict[str, str]] | None = None
    count: int | None = None


def _error_from(model: type[BaseModel], **kwargs: Any) -> ValidationError:
    """Return the error a real pydantic validation raises for these field values."""
    try:
        model(**kwargs)
    except ValidationError as e:
        return e
    raise AssertionError(f"Expected {model.__name__} to reject {kwargs}")


class TestDescribeValidationErrors(unittest.TestCase):
    """Test cases for rendering a pydantic error as lines a user can act on."""

    def test_reports_the_reason_and_the_type_received(self) -> None:
        error = _error_from(_ListModel, assigned_value="org:team")

        lines = str_utils.describe_validation_errors(error, root_field="assigned_value")

        self.assertEqual(["Input should be a valid list, got: str"], lines)

    def test_omits_the_path_when_the_whole_value_is_wrong(self) -> None:
        error = _error_from(_ListModel, assigned_value="org:team")

        lines = str_utils.describe_validation_errors(error, root_field="assigned_value")

        # The error is about the value itself, so there is no part of it to point at.
        self.assertNotIn("at ", lines[0])

    def test_points_at_the_offending_part_of_a_nested_value(self) -> None:
        error = _error_from(_ListMapModel, assigned_value=[{"name": "cpu"}, {"disk_size_gb": 50}])

        lines = str_utils.describe_validation_errors(error, root_field="assigned_value")

        self.assertEqual(["at [1].disk_size_gb: Input should be a valid string, got: int"], lines)

    def test_returns_one_line_per_error(self) -> None:
        error = _error_from(_ListMapModel, assigned_value=[{"a": 1}, {"b": 2}], count="many")

        lines = str_utils.describe_validation_errors(error, root_field="assigned_value")

        self.assertEqual(3, len(lines))
        self.assertIn("at [0].a: ", lines[0])
        self.assertIn("at [1].b: ", lines[1])
        # A sibling field is not under root_field, so it keeps its own name in the path.
        self.assertIn("at count: ", lines[2])

    def test_keeps_the_root_field_in_the_path_when_not_given(self) -> None:
        error = _error_from(_ListMapModel, assigned_value=[{"name": 1}])

        lines = str_utils.describe_validation_errors(error)

        self.assertEqual(["at assigned_value[0].name: Input should be a valid string, got: int"], lines)

    def test_keeps_the_path_when_root_field_does_not_match(self) -> None:
        error = _error_from(_ListMapModel, count="many")

        lines = str_utils.describe_validation_errors(error, root_field="assigned_value")

        self.assertEqual(
            ["at count: Input should be a valid integer, unable to parse string as an integer, got: str"], lines
        )


class TestFormatTimestamp(unittest.TestCase):
    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(format_timestamp(""), "")

    def test_iso_utc_timestamp(self) -> None:
        result = format_timestamp("2026-06-18T15:49:33+00:00")
        self.assertEqual(result, "2026-06-18 15:49 UTC")

    def test_iso_with_timezone_offset(self) -> None:
        result = format_timestamp("2026-06-18T10:30:00-05:00")
        self.assertEqual(result, "2026-06-18 15:30 UTC")

    def test_iso_with_microseconds(self) -> None:
        result = format_timestamp("2026-06-18T16:21:23.542000+00:00")
        self.assertEqual(result, "2026-06-18 16:21 UTC")

    def test_invalid_string_returned_as_is(self) -> None:
        self.assertEqual(format_timestamp("not-a-date"), "not-a-date")


class TestFormatAge(unittest.TestCase):
    def test_returns_empty_for_empty_string(self) -> None:
        self.assertEqual(str_utils.format_age(""), "")

    def test_returns_seconds_ago(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 30, tzinfo=UTC)
        timestamp = (now - timedelta(seconds=45)).isoformat()

        with patch("jupyter_deploy.str_utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = str_utils.format_age(timestamp)

        self.assertEqual(result, "45s ago")

    def test_returns_minutes_ago(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(minutes=15)).isoformat()

        with patch("jupyter_deploy.str_utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = str_utils.format_age(timestamp)

        self.assertEqual(result, "15m ago")

    def test_returns_hours_ago(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(hours=3)).isoformat()

        with patch("jupyter_deploy.str_utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = str_utils.format_age(timestamp)

        self.assertEqual(result, "3h ago")

    def test_returns_days_ago(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(days=5)).isoformat()

        with patch("jupyter_deploy.str_utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = str_utils.format_age(timestamp)

        self.assertEqual(result, "5d ago")

    def test_boundary_59_seconds_shows_seconds(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(seconds=59)).isoformat()

        with patch("jupyter_deploy.str_utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = str_utils.format_age(timestamp)

        self.assertEqual(result, "59s ago")

    def test_boundary_60_seconds_shows_minutes(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(seconds=60)).isoformat()

        with patch("jupyter_deploy.str_utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = str_utils.format_age(timestamp)

        self.assertEqual(result, "1m ago")

    def test_boundary_23_hours_shows_hours(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(hours=23)).isoformat()

        with patch("jupyter_deploy.str_utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = str_utils.format_age(timestamp)

        self.assertEqual(result, "23h ago")

    def test_boundary_24_hours_shows_days(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = (now - timedelta(hours=24)).isoformat()

        with patch("jupyter_deploy.str_utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = str_utils.format_age(timestamp)

        self.assertEqual(result, "1d ago")

    def test_naive_timestamp_treated_as_utc(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = "2025-05-14T10:00:00"

        with patch("jupyter_deploy.str_utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = str_utils.format_age(timestamp)

        self.assertEqual(result, "2h ago")

    def test_invalid_timestamp_returns_original(self) -> None:
        self.assertEqual(str_utils.format_age("not-a-date"), "not-a-date")

    def test_zero_seconds_shows_zero(self) -> None:
        now = datetime(2025, 5, 14, 12, 0, 0, tzinfo=UTC)
        timestamp = now.isoformat()

        with patch("jupyter_deploy.str_utils.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = str_utils.format_age(timestamp)

        self.assertEqual(result, "0s ago")
