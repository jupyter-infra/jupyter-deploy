"""Unit tests for the kubernetes.nodes helpers."""

import unittest

from pytest_jupyter_deploy.kubernetes.nodes import parse_cpu_to_millicores


class TestParseCpuToMillicores(unittest.TestCase):
    def test_whole_cores(self) -> None:
        self.assertEqual(parse_cpu_to_millicores("2"), 2000)

    def test_millicores(self) -> None:
        self.assertEqual(parse_cpu_to_millicores("1930m"), 1930)

    def test_fractional_cores(self) -> None:
        self.assertEqual(parse_cpu_to_millicores("3.5"), 3500)

    def test_strips_whitespace(self) -> None:
        self.assertEqual(parse_cpu_to_millicores("  4  "), 4000)
