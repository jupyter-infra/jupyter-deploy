import unittest

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import InstructionNotFoundError, InvalidInstructionArgumentError
from jupyter_deploy.provider.core.core_runner import CoreInstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    ListStrResolvedInstructionArgument,
    StrResolvedInstructionArgument,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ListStrResolvedInstructionResult,
    StrResolvedInstructionResult,
)


class TestConcatListsOfStr(unittest.TestCase):
    def _runner(self) -> CoreInstructionRunner:
        return CoreInstructionRunner(NullDisplay())

    def test_concatenates_two_liststr_operands_in_order(self) -> None:
        result = self._runner().execute_instruction(
            "core.concat-lists-of-str",
            {
                "list_1": ListStrResolvedInstructionArgument(argument_name="list_1", value=["a", "b"]),
                "list_2": ListStrResolvedInstructionArgument(argument_name="list_2", value=["c"]),
            },
        )
        self.assertIsInstance(result["Names"], ListStrResolvedInstructionResult)
        self.assertEqual(result["Names"].value, ["a", "b", "c"])

    def test_preserves_order_and_does_not_dedup(self) -> None:
        result = self._runner().execute_instruction(
            "core.concat-lists-of-str",
            {
                "list_1": ListStrResolvedInstructionArgument(argument_name="list_1", value=["x", "dup"]),
                "list_2": ListStrResolvedInstructionArgument(argument_name="list_2", value=["dup", "y"]),
            },
        )
        self.assertEqual(result["Names"].value, ["x", "dup", "dup", "y"])

    def test_one_operand_absent_returns_other_list(self) -> None:
        result = self._runner().execute_instruction(
            "core.concat-lists-of-str",
            {
                "list_2": ListStrResolvedInstructionArgument(argument_name="list_2", value=["only"]),
            },
        )
        self.assertEqual(result["Names"].value, ["only"])

    def test_both_operands_absent_returns_empty(self) -> None:
        result = self._runner().execute_instruction("core.concat-lists-of-str", {})
        self.assertEqual(result["Names"].value, [])

    def test_non_liststr_operand_raises(self) -> None:
        with self.assertRaises(InvalidInstructionArgumentError):
            self._runner().execute_instruction(
                "core.concat-lists-of-str",
                {
                    "list_1": StrResolvedInstructionArgument(argument_name="list_1", value='["a"]'),
                },
            )

    def test_three_operands_sorted_numerically(self) -> None:
        result = self._runner().execute_instruction(
            "core.concat-lists-of-str",
            {
                "list_2": ListStrResolvedInstructionArgument(argument_name="list_2", value=["b"]),
                "list_1": ListStrResolvedInstructionArgument(argument_name="list_1", value=["a"]),
                "list_3": ListStrResolvedInstructionArgument(argument_name="list_3", value=["c"]),
            },
        )
        self.assertEqual(result["Names"].value, ["a", "b", "c"])


class TestCoalesce(unittest.TestCase):
    def _runner(self) -> CoreInstructionRunner:
        return CoreInstructionRunner(NullDisplay())

    def test_first_operand_present_wins(self) -> None:
        result = self._runner().execute_instruction(
            "core.coalesce-str",
            {
                "value_1": StrResolvedInstructionArgument(argument_name="value_1", value="first"),
                "value_2": StrResolvedInstructionArgument(argument_name="value_2", value="second"),
            },
        )
        self.assertIsInstance(result["Value"], StrResolvedInstructionResult)
        self.assertEqual(result["Value"].value, "first")

    def test_first_operand_absent_second_present(self) -> None:
        result = self._runner().execute_instruction(
            "core.coalesce-str",
            {
                "value_2": StrResolvedInstructionArgument(argument_name="value_2", value="second"),
            },
        )
        self.assertEqual(result["Value"].value, "second")

    def test_first_operand_ran_but_empty_is_skipped_past(self) -> None:
        result = self._runner().execute_instruction(
            "core.coalesce-str",
            {
                "value_1": StrResolvedInstructionArgument(argument_name="value_1", value=""),
                "value_2": StrResolvedInstructionArgument(argument_name="value_2", value="second"),
            },
        )
        self.assertEqual(result["Value"].value, "second")

    def test_all_operands_empty_or_absent_returns_empty_value(self) -> None:
        result = self._runner().execute_instruction(
            "core.coalesce-str",
            {
                "value_1": StrResolvedInstructionArgument(argument_name="value_1", value=""),
            },
        )
        self.assertEqual(result["Value"].value, "")

    def test_non_str_operand_raises(self) -> None:
        with self.assertRaises(InvalidInstructionArgumentError):
            self._runner().execute_instruction(
                "core.coalesce-str",
                {
                    "value_1": ListStrResolvedInstructionArgument(argument_name="value_1", value=["a"]),
                },
            )


class TestCoreRunnerDispatch(unittest.TestCase):
    def test_unknown_instruction_raises(self) -> None:
        with self.assertRaises(InstructionNotFoundError):
            CoreInstructionRunner(NullDisplay()).execute_instruction("core.unknown", {})
