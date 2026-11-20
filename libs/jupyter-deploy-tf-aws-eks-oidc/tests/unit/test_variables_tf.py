import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

from jupyter_deploy_tf_aws_eks_oidc.template import TEMPLATE_PATH

VARIABLES_TF = TEMPLATE_PATH / "engine" / "variables.tf"
CHART_FLOOR_MODULE = TEMPLATE_PATH / "engine" / "modules" / "chart_floor"

_VARIABLE_BLOCK = re.compile(r'^variable "(?P<name>[^"]+)" \{\n(?P<body>.*?)^\}', re.MULTILINE | re.DOTALL)
_HEREDOC_FIRST_LINE = re.compile(r"description\s*=\s*<<-EOT\n\s*(?P<line>[^\n]*)\n")
_TYPE = re.compile(r"^\s*type\s*=\s*(?P<type>\S+)", re.MULTILINE)
_KEY_LINE = re.compile(r"^\s{6}(?P<key>[a-z_]+)\s+- ", re.MULTILINE)


def _list_of_map_variables() -> dict[str, str]:
    content = VARIABLES_TF.read_text()
    return {
        m["name"]: m["body"]
        for m in _VARIABLE_BLOCK.finditer(content)
        if (t := _TYPE.search(m["body"])) and t["type"].startswith("list(map(")
    }


class TestListOfMapVariableDescriptions(unittest.TestCase):
    """A list(map(...)) variable names its keys on the first description line, where they read at a glance."""

    def test_list_of_map_variables_found(self) -> None:
        self.assertIn("workspace_namespaces", _list_of_map_variables())

    def test_first_line_lists_keys(self) -> None:
        for name, body in _list_of_map_variables().items():
            with self.subTest(variable=name):
                first = _HEREDOC_FIRST_LINE.search(body)
                self.assertIsNotNone(first, f"{name} must use a <<-EOT description")
                assert first is not None
                self.assertIn("Keys: ", first["line"], f"{name}: first description line must list its keys")

    def test_keys_line_matches_documented_keys(self) -> None:
        for name, body in _list_of_map_variables().items():
            with self.subTest(variable=name):
                first = _HEREDOC_FIRST_LINE.search(body)
                assert first is not None
                listed = [k.strip() for k in first["line"].split("Keys: ", 1)[1].rstrip(".").split(",")]
                documented = [m["key"] for m in _KEY_LINE.finditer(body)]
                self.assertEqual(sorted(listed), sorted(documented))


# `jd config --help` shows only the first description line, cut at this many characters
# (str_utils.get_trimmed_header).
_CLI_HELP_MAX_LENGTH = 120


class TestVariableDescriptionHeaders(unittest.TestCase):
    """The first description line is the variable's `jd config --help` text, so it must read on its own."""

    def setUp(self) -> None:
        self.variables = {m["name"]: m["body"] for m in _VARIABLE_BLOCK.finditer(VARIABLES_TF.read_text())}

    def test_variables_found(self) -> None:
        self.assertIn("workspace_bedrock_enabled", self.variables)

    def test_first_line_is_a_complete_sentence(self) -> None:
        for name, body in self.variables.items():
            with self.subTest(variable=name):
                first = _HEREDOC_FIRST_LINE.search(body)
                self.assertIsNotNone(first, f"{name} must use a <<-EOT description")
                assert first is not None
                line = first["line"].strip()
                self.assertTrue(line.endswith("."), f"{name}: first description line must end a sentence: {line!r}")
                self.assertLessEqual(
                    len(line), _CLI_HELP_MAX_LENGTH, f"{name}: first description line exceeds the CLI help length"
                )


_TERRAFORM = shutil.which("terraform")

# CI must never skip these silently; laptops without terraform may.
_SKIP_WITHOUT_TERRAFORM = unittest.skipIf(_TERRAFORM is None and not os.environ.get("CI"), "terraform not installed")


def _variable_block(name: str) -> str:
    match = next(m for m in _VARIABLE_BLOCK.finditer(VARIABLES_TF.read_text()) if m["name"] == name)
    return match.group(0) + "\n"


def _terraform(cwd: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["terraform", *args, "-no-color"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "TF_IN_AUTOMATION": "1"},
    )


def _diagnostic_text(result: subprocess.CompletedProcess[str]) -> str:
    """Terraform wraps and boxes its diagnostics; one line of plain text matches a message whole."""
    return re.sub(r"\s+", " ", result.stderr.replace("│", ""))


@_SKIP_WITHOUT_TERRAFORM
class TestWorkspaceTemplatesValidation(unittest.TestCase):
    """The workspace_templates validation rules, evaluated by terraform.

    The block's conditions reference only the variable itself, so a root module made of that
    one block plans with no provider and no credentials.
    """

    root: ClassVar[tempfile.TemporaryDirectory[str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = tempfile.TemporaryDirectory()
        (Path(cls.root.name) / "variables.tf").write_text(_variable_block("workspace_templates"))
        init = _terraform(cls.root.name, "init", "-backend=false", "-input=false")
        assert init.returncode == 0, init.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.cleanup()

    def _plan(self, templates: str) -> subprocess.CompletedProcess[str]:
        return _terraform(
            self.root.name, "plan", "-refresh=false", "-input=false", f"-var=workspace_templates={templates}"
        )

    def test_vscode_config_without_idle_minutes_is_accepted(self) -> None:
        result = self._plan('[{name = "vscode-p", app = "vscode", gpus = "1", cpu = "8", memory = "32Gi"}]')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_jupyterlab_config_accepts_idle_minutes(self) -> None:
        result = self._plan('[{name = "jupyterlab-p", idle_minutes = "30"}]')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_vscode_config_refuses_idle_minutes(self) -> None:
        result = self._plan('[{name = "vscode-p", app = "vscode", idle_minutes = "30"}]')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            'workspace_templates configs with app = "vscode" cannot set idle_minutes: '
            "VS Code workspaces have no idle shutdown yet.",
            _diagnostic_text(result),
        )

    def test_unknown_app_is_refused(self) -> None:
        result = self._plan('[{name = "rstudio", app = "rstudio"}]')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            'Each workspace_templates app, when set, must be "jupyterlab" or "vscode".', _diagnostic_text(result)
        )

    def test_built_in_card_names_are_reserved(self) -> None:
        for name in ("jupyterlab", "vscode"):
            with self.subTest(name=name):
                result = self._plan(f'[{{name = "{name}"}}]')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    '"jupyterlab" and "vscode" are reserved for the built-in cards.', _diagnostic_text(result)
                )


@_SKIP_WITHOUT_TERRAFORM
class TestRemoteAccessChartFloors(unittest.TestCase):
    """The chart-version floors remote access needs, compared by terraform on the release core.

    The root module instantiates the chart_floor module with a version and a floor and outputs
    the result, so a plan needs no provider.
    """

    root: ClassVar[tempfile.TemporaryDirectory[str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = tempfile.TemporaryDirectory()
        (Path(cls.root.name) / "main.tf").write_text(
            'variable "chart_version" {\n  type = string\n}\n'
            'variable "floor" {\n  type = list(number)\n}\n'
            f'module "floor" {{\n  source        = "{CHART_FLOOR_MODULE}"\n'
            "  chart_version = var.chart_version\n  floor         = var.floor\n}\n"
            'output "at_floor" {\n  value = module.floor.at_floor\n}\n'
        )
        init = _terraform(cls.root.name, "init", "-backend=false", "-input=false")
        assert init.returncode == 0, init.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.cleanup()

    def _at_floor(self, chart_version: str, floor: list[int]) -> bool:
        plan = _terraform(
            self.root.name,
            "plan",
            "-refresh=false",
            "-input=false",
            "-out=plan.out",
            f"-var=chart_version={chart_version}",
            f"-var=floor={json.dumps(floor)}",
        )
        self.assertEqual(plan.returncode, 0, plan.stderr)
        shown = _terraform(self.root.name, "show", "-json", "plan.out")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        at_floor: bool = json.loads(shown.stdout)["planned_values"]["outputs"]["at_floor"]["value"]
        return at_floor

    def test_router_floor_is_the_first_chart_with_the_websocket_strategy(self) -> None:
        for pin, expected in (("0.2.0", False), ("0.2.1", True), ("0.3.2", True)):
            with self.subTest(pin=pin):
                self.assertIs(self._at_floor(pin, [0, 2, 1]), expected)

    def test_operator_floor_is_the_first_chart_with_the_websocket_connection_type(self) -> None:
        for pin, expected in (("0.2.9", False), ("0.3.0", True), ("0.4.1", True)):
            with self.subTest(pin=pin):
                self.assertIs(self._at_floor(pin, [0, 3, 0]), expected)

    def test_release_core_compares_numerically_and_keeps_a_prerelease_suffix_out(self) -> None:
        # Compared as strings, "0.10.0" sorts below "0.2.1".
        self.assertIs(self._at_floor("0.10.0", [0, 2, 1]), True)
        self.assertIs(self._at_floor("1.0.0-rc1", [0, 3, 0]), True)

    def test_a_pin_that_is_not_a_version_counts_as_below_the_floor(self) -> None:
        self.assertIs(self._at_floor("latest", [0, 2, 1]), False)

    def test_the_preset_pins_both_charts_at_or_above_their_floors(self) -> None:
        remote_access_tf = (TEMPLATE_PATH / "engine" / "workspace_remote_access.tf").read_text()
        preset = (TEMPLATE_PATH / "engine" / "presets" / "defaults-all.tfvars").read_text()
        for chart, variable in (
            ("router", "workspace_router_chart_version"),
            ("operator", "workspace_operator_chart_version"),
        ):
            with self.subTest(chart=chart):
                floor = re.search(
                    rf'module "{chart}_chart_floor" \{{.*?floor\s*=\s*\[([0-9, ]+)\]', remote_access_tf, re.S
                )
                pinned = re.search(rf'^{variable}\s*=\s*"([^"]+)"', preset, re.M)
                assert floor is not None and pinned is not None
                self.assertIs(self._at_floor(pinned.group(1), [int(n) for n in floor.group(1).split(",")]), True)
