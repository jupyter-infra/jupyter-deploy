import unittest

from jupyter_deploy import type_utils


class TestTypeUtils(unittest.TestCase):
    """Tests for type_utils module."""

    def test_is_list_str_repr_with_valid_inputs(self) -> None:
        """Test is_list_str_repr() with valid inputs representing list of strings."""
        # Test with 'list' and 'string' - this is the most common case in practice
        self.assertTrue(type_utils.is_list_str_repr(["list", "string"]))

        # Test with 'list' and 'str' - another valid representation
        self.assertTrue(type_utils.is_list_str_repr(["list", "str"]))

        # Test with 'list' and 'dynamic' - empty array case
        self.assertTrue(type_utils.is_list_str_repr(["list", "dynamic"]))

        # Test with additional elements in the list
        self.assertTrue(type_utils.is_list_str_repr(["list", "string", "additional", "elements"]))
        self.assertTrue(type_utils.is_list_str_repr(["list", "str", True]))

    def test_is_list_str_repr_with_invalid_inputs(self) -> None:
        """Test is_list_str_repr() with invalid inputs that should return False."""
        # Test with non-list inputs
        self.assertFalse(type_utils.is_list_str_repr("list"))
        self.assertFalse(type_utils.is_list_str_repr(123))
        self.assertFalse(type_utils.is_list_str_repr(None))
        self.assertFalse(type_utils.is_list_str_repr({}))

        # Test with wrong first element
        self.assertFalse(type_utils.is_list_str_repr(["tuple", "string"]))
        self.assertFalse(type_utils.is_list_str_repr(["LIST", "string"]))  # Case sensitive check

        # Test with wrong second element
        self.assertFalse(type_utils.is_list_str_repr(["list", "int"]))
        self.assertFalse(type_utils.is_list_str_repr(["list", "number"]))
        self.assertFalse(type_utils.is_list_str_repr(["list", "bool"]))

        # Test with too short list
        self.assertFalse(type_utils.is_list_str_repr(["list"]))
        self.assertFalse(type_utils.is_list_str_repr([]))

        # Test with correct elements but in wrong order
        self.assertFalse(type_utils.is_list_str_repr(["string", "list"]))

        # Test with Python types instead of strings
        self.assertFalse(type_utils.is_list_str_repr(list))
        self.assertFalse(type_utils.is_list_str_repr(dict))
        self.assertFalse(type_utils.is_list_str_repr(set))
        self.assertFalse(type_utils.is_list_str_repr(int))

    def test_is_list_str_repr_with_real_terraform_output_format(self) -> None:
        """Test is_list_str_repr() with the exact format that Terraform would output."""
        # This is what we'd typically get from Terraform's output command
        terraform_output_type = ["list", "string"]
        self.assertTrue(type_utils.is_list_str_repr(terraform_output_type))

        # Sometimes Terraform might use 'str' instead
        terraform_output_type_alt = ["list", "str"]
        self.assertTrue(type_utils.is_list_str_repr(terraform_output_type_alt))

    def test_is_list_str_repr_with_edge_cases(self) -> None:
        """Test is_list_str_repr() with edge cases."""
        # Test with nested lists - these should fail
        self.assertFalse(type_utils.is_list_str_repr([["list"], "string"]))
        self.assertFalse(type_utils.is_list_str_repr(["list", ["string"]]))

        # Test with tuple instead of list
        self.assertFalse(type_utils.is_list_str_repr(("list", "string")))

        # Test with non-string elements but correct structure
        self.assertFalse(type_utils.is_list_str_repr([list, "string"]))
        self.assertFalse(type_utils.is_list_str_repr(["list", str]))
