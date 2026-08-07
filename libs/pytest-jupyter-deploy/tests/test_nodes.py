"""Unit tests for the kubernetes.nodes helpers."""

import unittest
from unittest.mock import Mock, patch

from pytest_jupyter_deploy.kubernetes.nodes import get_node_allocatable_gpu_count, parse_cpu_to_millicores


class TestParseCpuToMillicores(unittest.TestCase):
    def test_whole_cores(self) -> None:
        self.assertEqual(parse_cpu_to_millicores("2"), 2000)

    def test_millicores(self) -> None:
        self.assertEqual(parse_cpu_to_millicores("1930m"), 1930)

    def test_fractional_cores(self) -> None:
        self.assertEqual(parse_cpu_to_millicores("3.5"), 3500)

    def test_strips_whitespace(self) -> None:
        self.assertEqual(parse_cpu_to_millicores("  4  "), 4000)


class TestGetNodeAllocatableGpuCount(unittest.TestCase):
    @patch("pytest_jupyter_deploy.kubernetes.nodes.subprocess.run")
    def test_gpu_node(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(stdout="1\n")
        self.assertEqual(get_node_allocatable_gpu_count("node-a"), 1)

    @patch("pytest_jupyter_deploy.kubernetes.nodes.subprocess.run")
    def test_absent_key_reads_zero(self, mock_run: Mock) -> None:
        # A node without the nvidia.com/gpu key (CPU node, or GPU node before the
        # device plugin registers) yields empty output, which must read as 0.
        mock_run.return_value = Mock(stdout="")
        self.assertEqual(get_node_allocatable_gpu_count("node-a"), 0)
