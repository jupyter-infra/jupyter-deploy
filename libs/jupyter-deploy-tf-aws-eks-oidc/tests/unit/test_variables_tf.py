import re
import unittest

from jupyter_deploy_tf_aws_eks_oidc.template import TEMPLATE_PATH

VARIABLES_TF = TEMPLATE_PATH / "engine" / "variables.tf"

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
