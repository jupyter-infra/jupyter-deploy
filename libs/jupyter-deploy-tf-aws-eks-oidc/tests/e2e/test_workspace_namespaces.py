"""E2E tests for team-isolated workspace namespaces (workspace_namespaces, issue #343).

The module fixture applies one base mapping (conftest namespace_base_values) before the
first case and restores the deployment's own values after the last. Cases run in a
pinned order right after test_workspace_single_to_multi_namespace; #409 runs last since
it changes the mapping itself. Only #409 relies on the bot's real membership of
JD_E2E_RBAC_TEAM. All workspaces are CPU-only.
"""

import os
from typing import Any

import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.coding_agents import CANARY, ask_claude_code, ask_codex
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.kubernetes.kubectl import run_kubectl
from pytest_jupyter_deploy.kubernetes.namespace import temporary_namespace
from pytest_jupyter_deploy.kubernetes.rbac import impersonated_user_can
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.kubectl import (
    kubectl_apply_workspace,
    kubectl_delete_workspace,
    kubectl_get_workspace,
    kubectl_patch_workspace,
    kubectl_poll_workspace_status,
)
from pytest_jupyter_deploy.workspaces.network_probe import (
    probe_service_allowed,
    probe_workspace,
    workspace_service_host,
)
from pytest_jupyter_deploy.workspaces.template import list_template_names
from pytest_jupyter_deploy.workspaces.web_app import WebAppNavigator

from .constants import (
    NS_A,
    NS_B,
    NS_ONLY_A_TEAM,
    NS_ONLY_B_TEAM,
    NS_ONLY_DEFAULT_TEAM,
    NS_REQUIRED_VARS,
    NS_RUNNING_TIMEOUT_S,
    NS_SMALL_TEMPLATE,
    NS_SMALL_TEMPLATE_CONFIG,
    ORDER_NAMESPACES,
    ROUTER_NAMESPACE,
    WORKSPACE_STOP_PATCH,
    WORKSPACES_DIR,
)

pytestmark = [
    pytest.mark.usefixtures("kubernetes_cluster_login"),
    pytest.mark.mutating,
]

PROBE_NAMESPACE = "e2e-ns-probe"


def _user() -> str:
    return f"github:{os.environ['JD_E2E_USER']}"


def _team(slug: str) -> str:
    return f"{os.environ['JD_E2E_ORG']}:{slug}"


def _rbac_team() -> str:
    return _team(os.environ["JD_E2E_RBAC_TEAM"])


def _group(team: str) -> list[str]:
    return [f"github:{team}"]


def _entry(name: str, teams: list[str], templates: list[str] | None = None) -> dict[str, str]:
    entry = {"name": name, "teams": ",".join(dict.fromkeys(teams))}
    if templates:
        entry["templates"] = ",".join(templates)
    return entry


@pytest.fixture(scope="module")
def mapped(
    e2e_deployment: EndToEndDeployment, restored_namespace_mapping: None, namespace_base_values: dict[str, Any]
) -> dict[str, Any]:
    """Apply the base mapping once for the module; restored_namespace_mapping restores it after the last case."""
    e2e_deployment.ensure_deployed_with_overrides(namespace_base_values)
    return namespace_base_values


@pytest.mark.order(ORDER_NAMESPACES + 1)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_team_mapped_to_one_namespace(mapped: dict[str, Any]) -> None:
    """A team mapped only to e2e-ns-a works there, is Forbidden in default, and cannot read e2e-ns-b."""
    mine, theirs = "e2e-ns-only-a", "e2e-ns-only-b"
    try:
        kubectl_apply_workspace(mine, WORKSPACES_DIR, as_user=_user(), as_groups=_group(_team(NS_ONLY_A_TEAM)))
        kubectl_poll_workspace_status(mine, "Running", namespace=NS_A, timeout_s=NS_RUNNING_TIMEOUT_S)

        for verb in ("list", "create"):
            assert not impersonated_user_can(
                verb, "workspaces", "default", as_user=_user(), as_groups=_group(_team(NS_ONLY_A_TEAM))
            )

        kubectl_apply_workspace(theirs, WORKSPACES_DIR, as_user=_user(), as_groups=_group(_team(NS_ONLY_B_TEAM)))
        read = kubectl_get_workspace(theirs, namespace=NS_B, as_user=_user(), as_groups=_group(_team(NS_ONLY_A_TEAM)))
        assert read.returncode != 0 and "forbidden" in read.stderr.lower(), (
            f"only-a team should not read a workspace in {NS_B}:\n{read.stdout}{read.stderr}"
        )
    finally:
        kubectl_delete_workspace(mine, namespace=NS_A)
        kubectl_delete_workspace(theirs, namespace=NS_B)


@pytest.mark.order(ORDER_NAMESPACES + 2)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_team_mapped_to_two_namespaces(mapped: dict[str, Any]) -> None:
    """A team mapped to both namespaces creates, lists and stops workspaces in each."""
    names = {NS_A: "e2e-ns-two-a", NS_B: "e2e-ns-two-b"}
    rbac = _rbac_team()
    try:
        for name in names.values():
            kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=_user(), as_groups=_group(rbac))
        for ns, name in names.items():
            kubectl_poll_workspace_status(name, "Running", namespace=ns, timeout_s=NS_RUNNING_TIMEOUT_S)
            listed = run_kubectl("get", "workspaces", "-n", ns, "-o", "name", as_user=_user(), as_groups=_group(rbac))
            assert listed.returncode == 0 and name in listed.stdout, f"cannot list {name} in {ns}:\n{listed.stderr}"
            stopped = kubectl_patch_workspace(
                name, WORKSPACE_STOP_PATCH, namespace=ns, as_user=_user(), as_groups=_group(rbac)
            )
            assert stopped.returncode == 0, f"cannot stop {name} in {ns}:\n{stopped.stderr}"
            kubectl_poll_workspace_status(name, "Stopped", namespace=ns, timeout_s=NS_RUNNING_TIMEOUT_S)
    finally:
        for ns, name in names.items():
            kubectl_delete_workspace(name, namespace=ns)


@pytest.mark.order(ORDER_NAMESPACES + 3)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_team_mapped_to_no_namespace(mapped: dict[str, Any]) -> None:
    """A team of an allowlisted org that no entry lists is Forbidden in every workspace namespace."""
    unmapped = _group(_team("e2e-ns-unmapped"))
    for ns in ("default", NS_A, NS_B):
        for verb in ("list", "create"):
            assert not impersonated_user_can(verb, "workspaces", ns, as_user=_user(), as_groups=unmapped), (
                f"an unmapped team should not {verb} workspaces in {ns}"
            )


@pytest.mark.order(ORDER_NAMESPACES + 4)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_templates_offered_per_namespace(mapped: dict[str, Any]) -> None:
    """e2e-cpu-small is offered and runs in e2e-ns-a only; e2e-ns-b offers just jupyterlab."""
    accepted, rejected_name = "e2e-ns-small-a", "e2e-ns-small-b"
    rbac = _rbac_team()
    try:
        assert list_template_names(NS_A, as_user=_user(), as_groups=_group(rbac)) == {"jupyterlab", NS_SMALL_TEMPLATE}
        assert list_template_names(NS_B, as_user=_user(), as_groups=_group(rbac)) == {"jupyterlab"}

        kubectl_apply_workspace(accepted, WORKSPACES_DIR, as_user=_user(), as_groups=_group(rbac))
        kubectl_poll_workspace_status(accepted, "Running", namespace=NS_A, timeout_s=NS_RUNNING_TIMEOUT_S)

        rejected = run_kubectl(
            "apply", "-f", str(WORKSPACES_DIR / f"{rejected_name}.yaml"), as_user=_user(), as_groups=_group(rbac)
        )
        assert rejected.returncode != 0 and "not found" in rejected.stderr, (
            f"{NS_SMALL_TEMPLATE} should be rejected at admission in {NS_B}:\n{rejected.stdout}{rejected.stderr}"
        )
    finally:
        kubectl_delete_workspace(accepted, namespace=NS_A)
        kubectl_delete_workspace(rejected_name, namespace=NS_B)


@pytest.mark.order(ORDER_NAMESPACES + 5)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_network_policy_in_every_namespace(mapped: dict[str, Any]) -> None:
    """The router reaches workspaces in both namespaces on 8888; an unrelated namespace does not."""
    names = {NS_A: "e2e-ns-netpol-a", NS_B: "e2e-ns-netpol-b"}
    try:
        for name in names.values():
            kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=_user(), as_groups=_group(_rbac_team()))
        for ns, name in names.items():
            kubectl_poll_workspace_status(name, "Running", namespace=ns, timeout_s=NS_RUNNING_TIMEOUT_S)
            assert probe_service_allowed(workspace_service_host(name, ns), 8888, from_namespace=ROUTER_NAMESPACE), (
                f"router should reach the workspace in {ns}"
            )
        with temporary_namespace(PROBE_NAMESPACE):
            for ns, name in names.items():
                assert not probe_workspace(name, from_namespace=PROBE_NAMESPACE, workspace_namespace=ns), (
                    f"an unrelated namespace should be denied the workspace in {ns}"
                )
    finally:
        for ns, name in names.items():
            kubectl_delete_workspace(name, namespace=ns)


@pytest.mark.order(ORDER_NAMESPACES + 6)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_in_use_template_cannot_be_dropped(e2e_deployment: EndToEndDeployment, mapped: dict[str, Any]) -> None:
    """Dropping e2e-cpu-small from e2e-ns-a while a workspace uses it fails `jd config`, naming both."""
    name = "e2e-ns-guard"
    try:
        kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=_user(), as_groups=_group(_rbac_team()))
        kubectl_poll_workspace_status(name, "Running", namespace=NS_A, timeout_s=NS_RUNNING_TIMEOUT_S)

        dropped = [
            _entry(e["name"], e["teams"].split(",")) if e["name"] == NS_A else e for e in mapped["workspace_namespaces"]
        ]
        e2e_deployment.update_override_value("workspace_namespaces", dropped)
        error = e2e_deployment.cli.run_command_expecting_failure(["jupyter-deploy", "config"])
        assert f"{NS_A}/{NS_SMALL_TEMPLATE} used by {NS_A}/{name}" in error, error
        assert NS_SMALL_TEMPLATE in list_template_names(NS_A, as_user=_user(), as_groups=_group(_rbac_team()))
    finally:
        e2e_deployment.update_override_value("workspace_namespaces", mapped["workspace_namespaces"])
        kubectl_delete_workspace(name, namespace=NS_A)


@pytest.mark.order(ORDER_NAMESPACES + 7)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_in_use_namespace_cannot_be_dropped(e2e_deployment: EndToEndDeployment, mapped: dict[str, Any]) -> None:
    """Dropping e2e-ns-b while it holds a workspace fails `jd config`, naming both."""
    name = "e2e-ns-drop-guard"
    try:
        kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=_user(), as_groups=_group(_rbac_team()))

        dropped = [e for e in mapped["workspace_namespaces"] if e["name"] != NS_B]
        e2e_deployment.update_override_value("workspace_namespaces", dropped)
        error = e2e_deployment.cli.run_command_expecting_failure(["jupyter-deploy", "config"])
        assert f"{NS_B} holds {NS_B}/{name}" in error, error
    finally:
        e2e_deployment.update_override_value("workspace_namespaces", mapped["workspace_namespaces"])
        kubectl_delete_workspace(name, namespace=NS_B)


@pytest.mark.order(ORDER_NAMESPACES + 8)
@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda m: [*m, m[1]], "workspace_namespaces names must be unique"),
        (
            lambda m: [*m[:2], {**m[2], "templates": "e2e-ns-no-such-config"}],
            f"{NS_B}/e2e-ns-no-such-config",
        ),
        (lambda m: [*m[:2], {**m[2], "teams": _team("e2e-ns-unlisted")}], "e2e-ns-unlisted"),
        (lambda m: [*m[:2], {"name": NS_B, "teams": ""}], "must list at least one team"),
        (lambda m: [*m[:2], {**m[2], "teams": NS_ONLY_B_TEAM}], "must be in 'org:team' format"),
        (lambda m: [*m, {"name": "kube-e2e", "teams": m[2]["teams"]}], 'must not start with "kube-"'),
        (lambda m: [*m, {"name": "keda", "teams": m[2]["teams"]}], "must not name a namespace a platform component"),
    ],
    ids=[
        "duplicate-name",
        "unknown-template",
        "unlisted-team",
        "no-team",
        "malformed-team",
        "reserved-prefix",
        "platform-namespace",
    ],
)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_plan_time_validation(
    e2e_deployment: EndToEndDeployment, mapped: dict[str, Any], mutate: Any, message: str
) -> None:
    """`jd config` refuses an invalid mapping at plan, naming the culprit."""
    try:
        e2e_deployment.update_override_value("workspace_namespaces", mutate(mapped["workspace_namespaces"]))
        assert message in e2e_deployment.cli.run_command_expecting_failure(["jupyter-deploy", "config"])
    finally:
        e2e_deployment.update_override_value("workspace_namespaces", mapped["workspace_namespaces"])


@pytest.mark.order(ORDER_NAMESPACES + 9)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_coding_agents_answer_only_in_bedrock_enabled_namespaces(
    e2e_deployment: EndToEndDeployment, mapped: dict[str, Any]
) -> None:
    """Claude Code and Codex answer in a Bedrock-enabled namespace, and fail in an opted-out one.

    The base mapping leaves Bedrock on in e2e-ns-a (no bedrock key) and opts e2e-ns-b out with
    bedrock = "false". Both namespaces hold the labeled workspace service account, but only
    e2e-ns-a binds it to an IAM role through EKS Pod Identity, so only its workspaces get
    AWS credentials. The agents are prompted headless; their TUIs are covered by
    test_workspace_coding_agents.
    """
    names = {NS_A: "e2e-ns-bedrock-a", NS_B: "e2e-ns-bedrock-b"}
    try:
        # Created after the mapping is applied: the operator assigns the service account
        # and the template env at creation only.
        for name in names.values():
            kubectl_apply_workspace(name, WORKSPACES_DIR, as_user=_user(), as_groups=_group(_rbac_team()))
        for ns, name in names.items():
            kubectl_poll_workspace_status(name, "Running", namespace=ns, timeout_s=NS_RUNNING_TIMEOUT_S)
            e2e_deployment.cli.wait_for_workspace_pod_exec_ready(name, scope=ns, timeout_s=60)

        for ask in (ask_claude_code, ask_codex):
            # Positive: the Bedrock-enabled namespace's workspace gets the model's answer.
            assert CANARY in ask(e2e_deployment, name=names[NS_A], scope=NS_A)
            # Negative: without credentials the agent exits non-zero. Its error text is not
            # asserted on: it varies across CLI releases.
            with pytest.raises(JDCliError):
                ask(e2e_deployment, name=names[NS_B], scope=NS_B)
    finally:
        for ns, name in names.items():
            kubectl_delete_workspace(name, namespace=ns)


@pytest.mark.order(ORDER_NAMESPACES + 10)
@skip_if_testvars_not_set(NS_REQUIRED_VARS)
def test_web_app_follows_mapping_change(
    e2e_deployment: EndToEndDeployment,
    mapped: dict[str, Any],
    fresh_dex: None,
    dex_oauth_web_app: WebAppNavigator,
) -> None:
    """#409: after `jd up` moves the bot's team from e2e-ns-a to e2e-ns-b, a reload resolves e2e-ns-b alone.

    While e2e-ns-a is the bot's only namespace, it also creates a workspace there from the UI
    and opens it, covering the public access path into a non-default namespace.

    Each mapping lists the namespace the bot may use first, which makes it the web app's
    default; `default` stays listed (to a team the bot is not in) so live workspaces keep
    their templates. Runs last: the module teardown restores the deployment's values.
    """
    rbac, other = _rbac_team(), _team(NS_ONLY_DEFAULT_TEAM)
    navigator = dex_oauth_web_app

    e2e_deployment.ensure_deployed_with_overrides(
        {
            "workspace_namespaces": [
                _entry(NS_A, [rbac], [NS_SMALL_TEMPLATE]),
                _entry(NS_B, [_team(NS_ONLY_B_TEAM)]),
                _entry("default", [other]),
            ]
        },
    )
    assert navigator.resolve_namespaces() == (NS_A, [NS_A])

    # The public access path into a non-default namespace: create from e2e-ns-a's own
    # card, then open it through the router and auth middleware.
    app_page = navigator.page
    name = navigator.create_workspace_from_template(NS_SMALL_TEMPLATE_CONFIG["display_name"])
    try:
        assert kubectl_get_workspace(name, namespace=NS_A).returncode == 0, f"{name} should be created in {NS_A}"
        navigator.wait_for_running(timeout=NS_RUNNING_TIMEOUT_S * 1000)
        navigator.open_workspace_from_details_page()
        navigator.verify_jupyterlab_loaded()
    finally:
        if navigator.page is not app_page:
            navigator.page.close()
            navigator.page = app_page
        kubectl_delete_workspace(name, namespace=NS_A)

    e2e_deployment.ensure_deployed_with_overrides(
        {
            "workspace_namespaces": [
                _entry(NS_B, [rbac]),
                _entry(NS_A, [_team(NS_ONLY_A_TEAM)], [NS_SMALL_TEMPLATE]),
                _entry("default", [other]),
            ]
        },
    )
    navigator.page.reload()
    assert navigator.resolve_namespaces() == (NS_B, [NS_B])
