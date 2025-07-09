import unittest

from jupyter_deploy import transform_utils
from jupyter_deploy.enum import TransformType


class TestTransformFunctions(unittest.TestCase):
    """Tests for transform_utils module."""

    def test_no_transform_fn_returns_input_unchanged(self) -> None:
        """Test that _no_transform_fn returns the input value unchanged."""
        # Test with various input types
        test_cases = ["string value", 123, 1.23, True, None, ["item1", "item2"], {"key": "value"}]

        for value in test_cases:
            with self.subTest(value=value):
                result = transform_utils._no_transform_fn(value)
                self.assertEqual(result, value)
                self.assertIs(result, value, "Should return the exact same object instance")

    def test_comma_sep_str_to_list_str_handles_empty_string(self) -> None:
        """Test _comma_sep_str_to_list_str with empty input."""
        result = transform_utils._comma_sep_str_to_list_str("")
        self.assertEqual(result, [])

    def test_comma_sep_str_to_list_str_handles_single_value(self) -> None:
        """Test _comma_sep_str_to_list_str with single value."""
        result = transform_utils._comma_sep_str_to_list_str("value")
        self.assertEqual(result, ["value"])

    def test_comma_sep_str_to_list_str_handles_multiple_values(self) -> None:
        """Test _comma_sep_str_to_list_str with multiple values."""
        result = transform_utils._comma_sep_str_to_list_str("value1,value2,value3")
        self.assertEqual(result, ["value1", "value2", "value3"])

    def test_comma_sep_str_to_list_str_preserves_whitespace(self) -> None:
        """Test _comma_sep_str_to_list_str preserves whitespace."""
        result = transform_utils._comma_sep_str_to_list_str("value1, value2 , value3")
        self.assertEqual(result, ["value1", " value2 ", " value3"])

    def test_comma_sep_str_to_list_str_handles_empty_elements(self) -> None:
        """Test _comma_sep_str_to_list_str handles empty elements."""
        result = transform_utils._comma_sep_str_to_list_str("value1,,value3")
        self.assertEqual(result, ["value1", "", "value3"])

    def test_get_transform_fn_returns_correct_function(self) -> None:
        """Test get_transform_fn returns the correct function for each TransformType."""
        # Test for NO_TRANSFORM
        no_transform_fn = transform_utils.get_transform_fn(TransformType.NO_TRANSFORM)
        self.assertIs(no_transform_fn, transform_utils._no_transform_fn)

        # Test for COMMA_SEPARATED_STR_TO_LIST_STR
        comma_sep_fn = transform_utils.get_transform_fn(TransformType.COMMA_SEPARATED_STR_TO_LIST_STR)
        self.assertIs(comma_sep_fn, transform_utils._comma_sep_str_to_list_str)

    def test_all_transform_types_have_corresponding_functions(self) -> None:
        """Test that all TransformType enum values have a corresponding function in _TRANSFORM_FN_MAP."""
        for transform_type in TransformType:
            with self.subTest(transform_type=transform_type):
                self.assertIn(transform_type, transform_utils._TRANSFORM_FN_MAP)
                self.assertIsNotNone(transform_utils._TRANSFORM_FN_MAP[transform_type])
                self.assertTrue(callable(transform_utils._TRANSFORM_FN_MAP[transform_type]))
