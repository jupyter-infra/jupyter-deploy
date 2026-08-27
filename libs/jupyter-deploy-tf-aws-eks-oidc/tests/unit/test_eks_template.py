"""Tests for the template module."""

import re
from pathlib import Path

import yaml

from jupyter_deploy_tf_aws_eks_oidc.template import TEMPLATE_PATH

MANDATORY_TEMPLATE_STRPATHS: list[str] = [
    "manifest.yaml",
    "variables.yaml",
    "AGENT.md.template",
    "TROUBLESHOOT.md.template",
    "engine/presets/defaults-all.tfvars",
    "engine/presets/destroy.tfvars",
    "engine/main.tf",
    "engine/outputs.tf",
    "engine/variables.tf",
    "engine/waiter.tf",
    "engine/local-await-router.sh.tftpl",
    "engine/local-destroy-workspaces.sh.tftpl",
    "charts/workspace-defaults/Chart.yaml",
    "charts/github-rbac/Chart.yaml",
    # Existence only — its version is deliberately decoupled from the template
    # version (see CHART_DIRS), so it does not belong there.
    "charts/karpenter-nodepools/Chart.yaml",
]

CHART_DIRS: list[str] = [
    "charts/workspace-defaults",
    "charts/github-rbac",
]


def test_template_path_exists() -> None:
    assert TEMPLATE_PATH.exists()
    assert TEMPLATE_PATH.is_dir()


def test_mandatory_template_files_exist() -> None:
    for file_str_path in MANDATORY_TEMPLATE_STRPATHS:
        relative_path = Path(*file_str_path.split("/"))
        full_path = TEMPLATE_PATH / relative_path

        assert full_path.exists(), f"missing file: {relative_path}"
        assert full_path.is_file(), f"not a file: {relative_path}"


def test_chart_versions_match_template_version() -> None:
    manifest_path = TEMPLATE_PATH / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    template_version = manifest["template"]["version"]

    for chart_dir in CHART_DIRS:
        chart_yaml_path = TEMPLATE_PATH / chart_dir / "Chart.yaml"
        chart = yaml.safe_load(chart_yaml_path.read_text())
        chart_version = chart["version"]

        assert chart_version == template_version, (
            f"{chart_dir}/Chart.yaml version ({chart_version}) does not match manifest version ({template_version})"
        )


def _extract_depends_on_names(block: str, resource_type: str) -> set[str]:
    """Return the set of `<resource_type>` names referenced in a depends_on list."""
    match = re.search(r"depends_on\s*=\s*\[(.*?)\]", block, re.DOTALL)
    assert match is not None, "no depends_on block found"
    refs = re.findall(rf"{re.escape(resource_type)}\.(\w+)", match.group(1))
    return set(refs)


def _extract_resource_block(content: str, resource_type: str, resource_name: str) -> str:
    """Return the body of a `resource "<type>" "<name>" {{ ... }}` block."""
    start = re.search(
        rf'resource\s+"{re.escape(resource_type)}"\s+"{re.escape(resource_name)}"\s*\{{',
        content,
    )
    assert start is not None, f"resource {resource_type}.{resource_name} not found"

    depth = 1
    idx = start.end()
    while idx < len(content) and depth > 0:
        if content[idx] == "{":
            depth += 1
        elif content[idx] == "}":
            depth -= 1
        idx += 1
    return content[start.end() : idx - 1]


def test_all_eks_addons_gated_by_cluster_addons() -> None:
    """Every aws_eks_addon MUST appear in null_resource.cluster_addons.depends_on.

    This is the barrier that keeps all cluster addons alive until every Helm chart
    has uninstalled (see eks_addons.tf comments). If a new addon is added but not
    wired into this aggregator, the Helm destroy ordering silently regresses and
    `jd down` can leave undeletable resources in etcd. Guard against that drift.
    """
    addons_tf = TEMPLATE_PATH / "engine" / "eks_addons.tf"
    content = addons_tf.read_text()

    declared_addons = set(re.findall(r'resource\s+"aws_eks_addon"\s+"(\w+)"', content))
    assert declared_addons, "no aws_eks_addon resources found in eks_addons.tf"

    cluster_addons_block = _extract_resource_block(content, "null_resource", "cluster_addons")
    gated_addons = _extract_depends_on_names(cluster_addons_block, "aws_eks_addon")

    missing = declared_addons - gated_addons
    assert not missing, (
        f"aws_eks_addon(s) {sorted(missing)} are not listed in "
        "null_resource.cluster_addons.depends_on — Helm chart destroy ordering will "
        "silently regress. Add them to the aggregator in eks_addons.tf."
    )


def test_karpenter_can_read_generated_instance_profiles() -> None:
    """Karpenter's termination reconciler probes generated <cluster>_* profile
    names with GetInstanceProfile; a 403 there blocks EC2NodeClass deletion (#349).
    """
    iam_tf = (TEMPLATE_PATH / "engine" / "iam.tf").read_text()
    statement = re.search(r'sid\s*=\s*"AllowInstanceProfileGet"(.*?)(?=\n  statement|\n\})', iam_tf, re.DOTALL)
    assert statement is not None, "AllowInstanceProfileGet statement not found in iam.tf"
    assert "instance-profile/${module.eks_cluster.cluster_name}_*" in statement.group(1), (
        "iam:GetInstanceProfile no longer covers Karpenter's generated <cluster>_* "
        "instance profiles; deleting an EC2NodeClass will hang on a 403 probe (#349)."
    )


def _iter_resource_blocks(content: str) -> list[tuple[str, str, str]]:
    """Yield (resource_type, resource_name, body) for every resource block in content."""
    blocks: list[tuple[str, str, str]] = []
    for m in re.finditer(r'resource\s+"([\w-]+)"\s+"([\w-]+)"\s*\{', content):
        depth = 1
        idx = m.end()
        while idx < len(content) and depth > 0:
            if content[idx] == "{":
                depth += 1
            elif content[idx] == "}":
                depth -= 1
            idx += 1
        blocks.append((m.group(1), m.group(2), content[m.end() : idx - 1]))
    return blocks


def _depends_on_refs(body: str) -> set[str]:
    """Return the set of `<type>.<name>` refs in a block's depends_on list (empty if none)."""
    m = re.search(r"depends_on\s*=\s*\[(.*?)\]", body, re.DOTALL)
    if not m:
        return set()
    return {f"{t}.{n}" for t, n in re.findall(r"([\w-]+)\.(\w+)", m.group(1))}


# Resources whose destroy needs the cluster to still be usable — they run against the
# cluster API (K8s provider) or evict pods/finalizers (Helm uninstall). Each MUST keep
# both the admin authorization AND the node groups alive until it is deleted.
_AUTH_AT_DESTROY_TYPES = ("kubernetes_", "helm_release")

# The only access-policy associations that grant a caller (human/CI, i.e. the identity
# Terraform's kubernetes/helm provider authenticates as) cluster API authorization.
_ADMIN_AUTH_NODES = frozenset(
    {
        "aws_eks_access_policy_association.admin_role",
        "aws_eks_access_policy_association.admin_user",
    }
)

# Node groups must outlive every K8s/Helm resource on destroy: Helm uninstall evicts
# pods and runs finalizers, which need nodes to schedule on (see CLAUDE.md destroy order).
_NODE_GROUP_NODES = frozenset({"aws_eks_node_group.platform"})


def _build_depends_on_graph() -> tuple[dict[str, set[str]], list[str]]:
    """Return (graph, k8s_nodes): the depends_on graph across engine/*.tf and the list
    of kubernetes_*/helm_release resource nodes within it."""
    engine_dir = TEMPLATE_PATH / "engine"
    graph: dict[str, set[str]] = {}
    k8s_nodes: list[str] = []
    for tf_file in sorted(engine_dir.glob("*.tf")):
        for rtype, rname, body in _iter_resource_blocks(tf_file.read_text()):
            node = f"{rtype}.{rname}"
            graph[node] = _depends_on_refs(body)
            if rtype.startswith(_AUTH_AT_DESTROY_TYPES):
                k8s_nodes.append(node)
    return graph, k8s_nodes


def _reaches(graph: dict[str, set[str]], start: str, targets: frozenset[str]) -> bool:
    """True if any target is reachable from start by following depends_on edges."""
    seen: set[str] = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if cur in targets:
            return True
        stack.extend(graph.get(cur, set()))
    return False


def test_k8s_resources_guard_admin_auth_through_destroy() -> None:
    """Every kubernetes_*/helm_release resource MUST reach an admin access-policy
    association via its depends_on chain, so admin authorization outlives it on destroy.

    The chain may be transitive: e.g. helm_release.jupyter_k8s depends on
    kubernetes_namespace_v1.shared, which depends on the associations directly. This is
    the invariant that broke when the fluent-bit SA and cluster-autoscaler lacked the
    guard — a concurrent/interrupted destroy tore down the access entry first and the
    provider lost authorization. Guard against that drift for any newly-added resource.
    """
    graph, k8s_nodes = _build_depends_on_graph()
    assert k8s_nodes, "no kubernetes_*/helm_release resources found in engine/*.tf"

    unguarded = sorted(n for n in k8s_nodes if not _reaches(graph, n, _ADMIN_AUTH_NODES))
    assert not unguarded, (
        f"resource(s) {unguarded} do not reach an admin access-policy association "
        f"({sorted(_ADMIN_AUTH_NODES)}) via depends_on — the K8s/Helm provider can lose "
        "authorization mid-destroy and `jd down` fails with 'Unauthorized'. Add the "
        "associations to the resource's depends_on (directly or via an already-guarded "
        "resource like kubernetes_namespace_v1.shared)."
    )


def test_k8s_resources_guard_node_group_through_destroy() -> None:
    """Every kubernetes_*/helm_release resource MUST reach a node group via its
    depends_on chain, so the nodes outlive it on destroy.

    Helm uninstall evicts pods and runs finalizers, which need a node to schedule on;
    if the node groups are torn down first the uninstall hangs and `jd down` stalls
    (see the load-bearing destroy order in CLAUDE.md). The chain may be transitive.
    """
    graph, k8s_nodes = _build_depends_on_graph()
    assert k8s_nodes, "no kubernetes_*/helm_release resources found in engine/*.tf"

    unguarded = sorted(n for n in k8s_nodes if not _reaches(graph, n, _NODE_GROUP_NODES))
    assert not unguarded, (
        f"resource(s) {unguarded} do not reach a node group ({sorted(_NODE_GROUP_NODES)}) "
        "via depends_on — the nodes can be torn down mid-destroy and the Helm uninstall "
        "hangs (pods/finalizers have nowhere to run). Add the node group to the "
        "resource's depends_on (directly or via an already-guarded resource)."
    )


def test_main_tf_version_matches_template_version() -> None:
    manifest_path = TEMPLATE_PATH / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    template_version = manifest["template"]["version"]

    main_tf_path = TEMPLATE_PATH / "engine" / "main.tf"
    main_tf_content = main_tf_path.read_text()
    match = re.search(r'template_version\s*=\s*"([^"]+)"', main_tf_content)

    assert match is not None, "template_version not found in main.tf"
    assert match.group(1) == template_version, (
        f"main.tf template_version ({match.group(1)}) does not match manifest version ({template_version})"
    )
