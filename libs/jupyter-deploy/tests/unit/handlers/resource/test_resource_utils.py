import json
import unittest
from unittest.mock import Mock

from jupyter_deploy.handlers.resource.resource_utils import (
    collect_results,
    evaluate_status_rules,
    render_display_field,
    resolve_node,
    resolve_path,
)
from jupyter_deploy.manifest import (
    JupyterDeployDisplayFieldV1,
    JupyterDeployStatusRuleMatchV1,
    JupyterDeployStatusRuleV1,
)


class TestResolvePath(unittest.TestCase):
    def test_simple_dot_access(self) -> None:
        resource = {"spec": {"desiredStatus": "Running"}}
        self.assertEqual(resolve_path(resource, ".spec.desiredStatus"), "Running")

    def test_array_filter(self) -> None:
        resource = {"status": {"conditions": [{"type": "Available", "status": "True"}]}}
        self.assertEqual(resolve_path(resource, ".status.conditions[type=Available].status"), "True")

    def test_array_filter_no_match(self) -> None:
        resource = {"status": {"conditions": [{"type": "Available", "status": "True"}]}}
        self.assertIsNone(resolve_path(resource, ".status.conditions[type=Degraded].status"))

    def test_missing_key(self) -> None:
        self.assertIsNone(resolve_path({}, ".spec.desiredStatus"))

    def test_non_string_leaf(self) -> None:
        resource = {"spec": {"replicas": 3}}
        self.assertIsNone(resolve_path(resource, ".spec.replicas"))

    def test_non_dict_root(self) -> None:
        self.assertIsNone(resolve_path({"status": "a string"}, ".status.field"))

    def test_map_key_lookup_with_dotted_key(self) -> None:
        resource = {"metadata": {"labels": {"workspace.jupyter.org/default-template": "true"}}}
        self.assertEqual(resolve_path(resource, ".metadata.labels[workspace.jupyter.org/default-template]"), "true")

    def test_map_key_lookup_missing_key(self) -> None:
        resource = {"metadata": {"labels": {"other": "x"}}}
        self.assertIsNone(resolve_path(resource, ".metadata.labels[workspace.jupyter.org/default-template]"))

    def test_map_key_lookup_missing_container(self) -> None:
        self.assertIsNone(resolve_path({"metadata": {}}, ".metadata.labels[some.key]"))


class TestResolveNode(unittest.TestCase):
    def test_list_index(self) -> None:
        resource = {"spec": {"versions": [{"name": "v1alpha1"}, {"name": "v1beta1"}]}}
        self.assertEqual(resolve_node(resource, ".spec.versions[0].name"), "v1alpha1")
        self.assertEqual(resolve_node(resource, ".spec.versions[1].name"), "v1beta1")

    def test_list_index_out_of_range(self) -> None:
        resource = {"spec": {"versions": [{"name": "v1alpha1"}]}}
        self.assertIsNone(resolve_node(resource, ".spec.versions[5].name"))

    def test_returns_raw_list(self) -> None:
        resource = {"spec": {"items": [1, 2, 3]}}
        self.assertEqual(resolve_node(resource, ".spec.items"), [1, 2, 3])


class TestRenderDisplayField(unittest.TestCase):
    def test_path_field_with_label(self) -> None:
        resource = json.dumps({"metadata": {"namespace": "shared"}})
        field = JupyterDeployDisplayFieldV1(label="namespace", path=".metadata.namespace")
        self.assertEqual(render_display_field(resource, field), "namespace: shared")

    def test_count_field(self) -> None:
        resource = json.dumps({"spec": {"accessResourceTemplates": [{"a": 1}, {"b": 2}]}})
        field = JupyterDeployDisplayFieldV1(label="access-resources", count=".spec.accessResourceTemplates")
        self.assertEqual(render_display_field(resource, field), "access-resources: 2")

    def test_join_field(self) -> None:
        resource = json.dumps({"spec": {"group": "workspace.jupyter.org", "versions": [{"name": "v1alpha1"}]}})
        field = JupyterDeployDisplayFieldV1(label="apiVersion", join=[".spec.group", ".spec.versions[0].name"])
        self.assertEqual(render_display_field(resource, field), "apiVersion: workspace.jupyter.org/v1alpha1")

    def test_labeled_absent_field_renders_label_with_dash(self) -> None:
        # A missing or typo'd path keeps the label so the cell stays self-documenting.
        resource = json.dumps({"spec": {}})
        field = JupyterDeployDisplayFieldV1(label="app-type", path=".spec.appType")
        self.assertEqual(render_display_field(resource, field), "app-type: -")

    def test_labeled_absent_count_renders_label_with_dash(self) -> None:
        resource = json.dumps({"spec": {}})
        field = JupyterDeployDisplayFieldV1(label="access-resources", count=".spec.absentList")
        self.assertEqual(render_display_field(resource, field), "access-resources: -")

    def test_unlabeled_absent_field_returns_empty(self) -> None:
        resource = json.dumps({"spec": {}})
        field = JupyterDeployDisplayFieldV1(path=".spec.appType")
        self.assertEqual(render_display_field(resource, field), "")

    def test_unparseable_json_returns_empty(self) -> None:
        field = JupyterDeployDisplayFieldV1(label="x", path=".a")
        self.assertEqual(render_display_field("not-json", field), "")

    def test_field_without_label(self) -> None:
        resource = json.dumps({"metadata": {"namespace": "shared"}})
        field = JupyterDeployDisplayFieldV1(path=".metadata.namespace")
        self.assertEqual(render_display_field(resource, field), "shared")


class TestEvaluateStatusRules(unittest.TestCase):
    RULES = [
        JupyterDeployStatusRuleV1(
            display="Degraded",
            all=[JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Degraded].status", equals="True")],
        ),
        JupyterDeployStatusRuleV1(
            display="Starting",
            all=[
                JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Progressing].status", equals="True"),
                JupyterDeployStatusRuleMatchV1(path=".spec.desiredStatus", equals="Running"),
            ],
        ),
        JupyterDeployStatusRuleV1(
            display="Stopping",
            all=[
                JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Progressing].status", equals="True"),
                JupyterDeployStatusRuleMatchV1(path=".spec.desiredStatus", equals="Stopped"),
            ],
        ),
        JupyterDeployStatusRuleV1(
            display="Stopped",
            all=[JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Stopped].status", equals="True")],
        ),
        JupyterDeployStatusRuleV1(
            display="Running",
            all=[JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Available].status", equals="True")],
        ),
    ]

    def test_running(self) -> None:
        resource = json.dumps(
            {
                "status": {
                    "conditions": [{"type": "Available", "status": "True"}, {"type": "Stopped", "status": "False"}]
                }
            }
        )
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Running")

    def test_stopped(self) -> None:
        resource = json.dumps(
            {
                "status": {
                    "conditions": [{"type": "Available", "status": "False"}, {"type": "Stopped", "status": "True"}]
                }
            }
        )
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Stopped")

    def test_starting(self) -> None:
        resource = json.dumps(
            {
                "spec": {"desiredStatus": "Running"},
                "status": {
                    "conditions": [{"type": "Progressing", "status": "True"}, {"type": "Stopped", "status": "False"}]
                },
            }
        )
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Starting")

    def test_stopping(self) -> None:
        resource = json.dumps(
            {
                "spec": {"desiredStatus": "Stopped"},
                "status": {
                    "conditions": [{"type": "Progressing", "status": "True"}, {"type": "Available", "status": "False"}]
                },
            }
        )
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Stopping")

    def test_degraded(self) -> None:
        resource = json.dumps(
            {
                "status": {
                    "conditions": [{"type": "Available", "status": "True"}, {"type": "Degraded", "status": "True"}]
                }
            }
        )
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Degraded")

    def test_unknown_on_no_match(self) -> None:
        resource = json.dumps({"status": {"conditions": []}})
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Unknown")

    def test_unknown_on_invalid_json(self) -> None:
        self.assertEqual(evaluate_status_rules("not-json", self.RULES), "Unknown")

    def test_unknown_on_empty_string(self) -> None:
        self.assertEqual(evaluate_status_rules("", self.RULES), "Unknown")


class TestCollectResults(unittest.TestCase):
    def test_collects_and_strips_prefix(self) -> None:
        mock_runner = Mock()
        mock_runner.get_result_value_with_fallback.side_effect = ["my-ws", '{"spec": {}}']

        mock_result_def_1 = Mock()
        mock_result_def_1.result_name = "server.show.name"
        mock_result_def_2 = Mock()
        mock_result_def_2.result_name = "server.show.resource"

        mock_command = Mock()
        mock_command.cmd = "server.show"
        mock_command.results = [mock_result_def_1, mock_result_def_2]

        result = collect_results(mock_runner, mock_command)

        self.assertEqual(result["name"], "my-ws")
        self.assertEqual(result["resource"], {"spec": {}})

    def test_returns_empty_dict_when_no_results(self) -> None:
        mock_runner = Mock()
        mock_command = Mock()
        mock_command.cmd = "server.show"
        mock_command.results = None

        result = collect_results(mock_runner, mock_command)

        self.assertEqual(result, {})

    def test_non_json_values_returned_as_strings(self) -> None:
        mock_runner = Mock()
        mock_runner.get_result_value_with_fallback.return_value = "plain-text"

        mock_result_def = Mock()
        mock_result_def.result_name = "host.show.status"

        mock_command = Mock()
        mock_command.cmd = "host.show"
        mock_command.results = [mock_result_def]

        result = collect_results(mock_runner, mock_command)

        self.assertEqual(result["status"], "plain-text")

    def test_json_list_values_are_parsed(self) -> None:
        mock_runner = Mock()
        mock_runner.get_result_value_with_fallback.return_value = '["a", "b"]'

        mock_result_def = Mock()
        mock_result_def.result_name = "host.show.items"

        mock_command = Mock()
        mock_command.cmd = "host.show"
        mock_command.results = [mock_result_def]

        result = collect_results(mock_runner, mock_command)

        self.assertEqual(result["items"], ["a", "b"])
