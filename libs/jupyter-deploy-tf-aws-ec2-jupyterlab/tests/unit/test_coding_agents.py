"""Static checks for the coding agents (Claude Code, Codex) and their Bedrock access.

The image build, the IAM grants and the instance metadata settings only meet on a live deployment;
these tests pin each side to what the others expect.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from jupyter_deploy.engine.terraform.tf_varfiles import parse_dot_tfvars_to_dict

from jupyter_deploy_tf_aws_ec2_jupyterlab.template import TEMPLATE_PATH

SERVICES_PATH: Path = TEMPLATE_PATH / "services"
DOCS_DIR: Path = Path(__file__).resolve().parents[4] / "docs" / "source" / "templates" / "aws-ec2-jupyterlab-template"
ENGINE_PATH: Path = TEMPLATE_PATH / "engine"
DOCKERFILES: list[Path] = [
    SERVICES_PATH / "jupyter" / "dockerfile.jupyter",
    SERVICES_PATH / "jupyter-pixi" / "dockerfile.jupyter.pixi",
]


def _instructions(dockerfile: Path) -> list[str]:
    """Return the dockerfile's instructions, comments dropped and continuation lines joined."""
    lines = [line for line in dockerfile.read_text().splitlines() if not line.lstrip().startswith("#")]
    return [" ".join(i.split()) for i in re.split(r"(?<!\\)\n", "\n".join(lines)) if i.strip()]


def _list_keys(block: str, key: str) -> set[str]:
    """Return the variable names of a compose ``- NAME=value`` list under ``key`` in ``block``."""
    match = re.search(rf"^(\s+){key}:\n((?:\1\s+- .*\n)+)", block, re.M)
    assert match is not None, f"no {key} list"
    return set(re.findall(r"- (\w+)=", match.group(2)))


def _hcl(path: Path) -> dict[str, Any]:
    return parse_dot_tfvars_to_dict(path.read_text())


class TestCodingAgentsImage(unittest.TestCase):
    def test_both_dockerfiles_install_clis_outside_home(self) -> None:
        for dockerfile in DOCKERFILES:
            with self.subTest(dockerfile=dockerfile.name):
                instructions = _instructions(dockerfile)
                text = "\n".join(instructions)

                self.assertIn("FROM node:22-trixie-slim AS ai-clis", text)
                install = next(i for i in instructions if "npm install" in i)
                self.assertIn("--prefix /opt/ai-clis", install)
                self.assertIn('"@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"', install)
                self.assertIn('"@openai/codex@${CODEX_VERSION}"', install)
                self.assertIn("COPY --from=ai-clis /opt/ai-clis /opt/ai-clis", text)
                self.assertIn("ln -s /opt/ai-clis/bin/claude /usr/local/bin/claude", text)
                self.assertIn("ln -s /opt/ai-clis/bin/codex /usr/local/bin/codex", text)

                # The data volume mounts over /home/jovyan at runtime and hides anything built there.
                for instruction in instructions:
                    if instruction.startswith(("COPY ", "ADD ")):
                        self.assertFalse(instruction.split()[-1].startswith("/home/jovyan"), instruction)
                    elif instruction.startswith("RUN ") and "/home/jovyan" in instruction:
                        self.assertEqual(instruction, "RUN chown -R jovyan:jovyan /home/jovyan")

    def test_compose_passes_cli_build_args_and_bedrock_env(self) -> None:
        compose = (SERVICES_PATH / "docker-compose.yml.tftpl").read_text()
        match = re.search(r"^  jupyter:\n(.*?)^  \S", compose, re.M | re.S)
        self.assertIsNotNone(match, "no jupyter service in docker-compose")
        assert match is not None  # for mypy
        jupyter = match.group(1)

        self.assertTrue(
            {"CLAUDE_CODE_VERSION", "CODEX_VERSION", "CODEX_PROFILE_PREFIX", "CODEX_MODEL_PATTERNS"}
            <= _list_keys(jupyter, "args")
        )
        self.assertTrue({"AWS_REGION", "ANTHROPIC_BEDROCK_REGION_PREFIX"} <= _list_keys(jupyter, "environment"))


class TestCodingAgentsDefaults(unittest.TestCase):
    def test_bedrock_is_on_by_default_and_codex_supports_bedrock(self) -> None:
        defaults = _hcl(ENGINE_PATH / "presets" / "defaults-all.tfvars")

        self.assertIs(defaults["bedrock_enabled"], True)
        # Codex reaches Bedrock through its amazon-bedrock-runtime provider from 0.128.0.
        codex_version = tuple(int(part) for part in defaults["codex_version"].split("."))
        self.assertGreaterEqual(codex_version, (0, 128, 0))

    def test_variable_descriptions_do_not_mention_imds(self) -> None:
        # The jupyter container cannot reach IMDS: a description that still says so is stale.
        variables_tf = (ENGINE_PATH / "variables.tf").read_text()
        for stale in ("metadata service", "IMDS", "instance role credentials"):
            self.assertNotIn(stale, variables_tf)


class TestPickCodexModel(unittest.TestCase):
    SCRIPT: Path = SERVICES_PATH / "jupyter" / "pick-codex-model.py"
    CATALOG = {
        "models": [
            {"slug": "global.openai.gpt-oss-120b", "priority": 0},
            {"slug": "us.anthropic.claude-sonnet-4", "priority": 0},
            {"slug": "us.openai.gpt-unranked"},
            {"slug": "us.openai.gpt-nullprio", "priority": None},
            {"slug": "us.openai.gpt-5", "priority": 3},
            {"slug": "us.openai.gpt-5-codex", "priority": 1},
        ]
    }

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.config = self.tmp / "config.toml"
        self.called = self.tmp / "codex-called"
        # The fake codex records the call and only answers `debug models`, as the real one is invoked.
        fake = self.tmp / "codex"
        fake.write_text(
            f'#!/bin/sh\ntouch "{self.called}"\n[ "$1 $2" = "debug models" ] || exit 2\n'
            f"cat <<'EOF'\n{json.dumps(self.CATALOG)}\nEOF\n"
        )
        fake.chmod(0o755)

    def _run(self, prefix: str, patterns: str, reset: bool = True, **env: str) -> tuple[int, str, str]:
        if reset:
            self.config.write_text('model_provider = "amazon-bedrock-runtime"\nmodel = "@CODEX_MODEL@"\n')
        result = subprocess.run(
            [sys.executable, "-I", str(self.SCRIPT), prefix, patterns, str(self.config)],
            env={**os.environ, "PATH": f"{self.tmp}{os.pathsep}{os.environ['PATH']}", **env},
            capture_output=True,
            text=True,
        )
        return result.returncode, self.config.read_text(), result.stderr

    def codex_called(self) -> bool:
        return self.called.exists()

    def test_empty_patterns_leave_model_unset_with_reason(self) -> None:
        rc, cfg, _ = self._run("us", "")
        self.assertEqual(rc, 0)
        self.assertIn(
            'model = "unset: bedrock_enabled is false or no openai model allowed by bedrock_model_patterns"', cfg
        )
        self.assertFalse(self.codex_called())

    def test_non_us_prefix_leaves_model_unset_with_reason(self) -> None:
        rc, cfg, _ = self._run("eu", "openai.gpt-*")
        self.assertEqual(rc, 0)
        self.assertIn('model = "unset: no eu OpenAI inference profiles, set bedrock_inference_scope to global"', cfg)
        self.assertFalse(self.codex_called())

    def test_empty_prefix_names_geographic(self) -> None:
        rc, cfg, _ = self._run("", "openai.gpt-*")
        self.assertEqual(rc, 0)
        self.assertIn("unset: no geographic OpenAI", cfg)
        self.assertFalse(self.codex_called())

    def test_usable_prefix_picks_lowest_priority(self) -> None:
        rc, cfg, _ = self._run("us", "openai.gpt-*")
        self.assertEqual(rc, 0)
        self.assertIn('model = "us.openai.gpt-5-codex"', cfg)
        self.assertTrue(self.codex_called())
        _, cfg, _ = self._run("global", "openai.gpt-*")
        self.assertIn('model = "global.openai.gpt-oss-120b"', cfg)

    def test_null_priority_ranks_last(self) -> None:
        _, cfg, _ = self._run("us", "openai.gpt-nullprio,openai.gpt-unranked,openai.gpt-5")
        self.assertIn('model = "us.openai.gpt-5"', cfg)
        _, cfg, _ = self._run("us", "openai.gpt-nullprio")
        self.assertIn('model = "us.openai.gpt-nullprio"', cfg)

    def test_codex_bin_overrides_path(self) -> None:
        pinned = self.tmp / "codex-pinned"
        (self.tmp / "codex").rename(pinned)
        rc, cfg, _ = self._run("us", "openai.gpt-*", CODEX_BIN=str(pinned))
        self.assertEqual(rc, 0)
        self.assertIn('model = "us.openai.gpt-5-codex"', cfg)
        self.assertTrue(self.codex_called())

    def test_no_matching_model_fails_the_build(self) -> None:
        rc, cfg, err = self._run("us", "openai.o3-*")
        self.assertEqual(rc, 1)
        self.assertIn("codex debug models lists no us. model allowed by openai.o3-*", err)
        self.assertIn("@CODEX_MODEL@", cfg)

    def test_missing_placeholder_fails_the_build(self) -> None:
        self._run("us", "openai.gpt-*")
        rc, cfg, err = self._run("us", "openai.gpt-*", reset=False)
        self.assertEqual(rc, 1)
        self.assertIn("has no @CODEX_MODEL@ placeholder", err)
        self.assertIn('model = "us.openai.gpt-5-codex"', cfg)


class TestBedrockIam(unittest.TestCase):
    def test_policy_is_gated_and_scoped_to_profiles(self) -> None:
        bedrock_tf = _hcl(ENGINE_PATH / "bedrock.tf")
        resources = {
            (t, n): body for r in bedrock_tf["resource"] for t, named in r.items() for n, body in named.items()
        }
        policy = resources[("aws_iam_policy", "bedrock_inference")]
        attachment = resources[("aws_iam_role_policy_attachment", "bedrock_inference")]

        self.assertEqual(policy["count"], "${var.bedrock_enabled ? 1 : 0}")
        self.assertEqual(attachment["count"], "${var.bedrock_enabled ? 1 : 0}")

        locals_ = {k: v for block in bedrock_tf["locals"] for k, v in block.items()}
        self.assertIn(
            ":bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/",
            locals_["bedrock_profile_arns"],
        )

        document = next(
            d["aws_iam_policy_document"]["bedrock_inference"]
            for d in bedrock_tf["data"]
            if "bedrock_inference" in d.get("aws_iam_policy_document", {})
        )
        invokes_foundation_models = [
            s
            for s in document["statement"]
            if "foundation_model" in str(s["resources"]) and any(a.startswith("bedrock:Invoke") for a in s["actions"])
        ]
        self.assertTrue(invokes_foundation_models, "expected a statement invoking foundation models")
        for statement in invokes_foundation_models:
            conditions = {c["variable"]: c for c in statement.get("condition", [])}
            self.assertIn("bedrock:InferenceProfileArn", conditions, statement["sid"])
            self.assertEqual(conditions["bedrock:InferenceProfileArn"]["values"], "${local.bedrock_profile_arns}")

    def test_app_role_is_gated_and_trusts_the_instance_role(self) -> None:
        tf = _hcl(ENGINE_PATH / "bedrock.tf")
        resources = {(t, n): body for r in tf["resource"] for t, named in r.items() for n, body in named.items()}
        role = resources[("aws_iam_role", "bedrock_app")]
        self.assertEqual(role["count"], "${var.bedrock_enabled ? 1 : 0}")
        self.assertEqual(role["name_prefix"], "bedrock-app-")
        self.assertEqual(role["max_session_duration"], 3600)
        self.assertEqual(
            resources[("aws_iam_role_policy_attachment", "bedrock_inference")]["role"],
            "${aws_iam_role.bedrock_app[0].name}",
        )
        self.assertEqual(
            resources[("aws_iam_role_policy_attachment", "assume_bedrock_app")]["role"],
            "${module.ec2_iam_role.execution_role_name}",
        )
        self.assertEqual(resources[("aws_iam_policy", "assume_bedrock_app")]["name_prefix"], "assume-bedrock-app-")
        data = {(t, n): body for d in tf["data"] for t, named in d.items() for n, body in named.items()}
        trust = data[("aws_iam_policy_document", "bedrock_app_trust")]
        self.assertEqual(
            trust["statement"][0]["principals"][0]["identifiers"], ["${module.ec2_iam_role.execution_role_arn}"]
        )
        self.assertEqual(
            data[("aws_iam_policy_document", "assume_bedrock_app")]["statement"][0]["actions"], ["sts:AssumeRole"]
        )

    def test_instance_role_module_exports_its_arn(self) -> None:
        outputs = _hcl(ENGINE_PATH / "modules" / "ec2_iam_role" / "outputs.tf")["output"]
        self.assertIn("execution_role_arn", {k for o in outputs for k in o})


class TestBedrockPrefix(unittest.TestCase):
    def test_region_table(self) -> None:
        locals_ = {k: v for block in _hcl(ENGINE_PATH / "bedrock.tf")["locals"] for k, v in block.items()}
        self.assertEqual(
            locals_["bedrock_region_prefixes"],
            {"ap-northeast-1": "jp", "ap-northeast-3": "jp", "ap-southeast-2": "au", "ca-central-1": "us"},
        )
        expr = locals_["bedrock_geo_prefix"]
        self.assertIn("lookup(local.bedrock_region_prefixes, var.region", expr)
        self.assertNotIn("apac", expr)

    def test_other_ap_regions_have_no_geo_prefix(self) -> None:
        text = (ENGINE_PATH / "bedrock.tf").read_text()
        self.assertNotIn('startswith(var.region, "ap-")', text)

    def test_regions_without_geo_prefix_fall_back_to_global(self) -> None:
        hcl = _hcl(ENGINE_PATH / "bedrock.tf")
        locals_ = {k: v for block in hcl["locals"] for k, v in block.items()}
        # A commercial region with no geo prefix must plan, not fail; isolated partitions still fail closed.
        self.assertIn('partition == "aws" ? "global" : ""', locals_["bedrock_profile_prefix"])
        checks = {k: v for block in hcl["check"] for k, v in block.items()}
        (assertion,) = checks["bedrock_geo_fallback"]["assert"]
        self.assertTrue(assertion["condition"].startswith("${!var.bedrock_enabled || "))
        self.assertIn('local.bedrock_geo_prefix != ""', assertion["condition"])


class TestInstanceMetadata(unittest.TestCase):
    def test_imds_hop_limit_allows_containers(self) -> None:
        main_tf = _hcl(ENGINE_PATH / "modules" / "ec2_instance" / "main.tf")
        instance = next(r["aws_instance"]["ec2_jupyter_server"] for r in main_tf["resource"] if "aws_instance" in r)
        (metadata_options,) = instance["metadata_options"]

        self.assertEqual(metadata_options["http_tokens"], "required")
        self.assertEqual(metadata_options["http_put_response_hop_limit"], 2)


class TestBedrockSidecarWiring(unittest.TestCase):
    """The credential sidecar only exists when Bedrock is enabled, and every consumer knows its name."""

    AWS_CONFIG = "[default]\ncredential_process = /bin/cat /run/bedrock-creds/credentials.json\n"

    def test_compose_sidecar_block_is_gated_and_mounts_credentials(self) -> None:
        text = (SERVICES_PATH / "docker-compose.yml.tftpl").read_text()
        self.assertIn("%{ if bedrock_enabled ~}", text)
        sidecar = re.search(r"^  bedrock-sidecar:\n(.*?)^  \S", text, re.S | re.M)
        assert sidecar is not None, "no bedrock-sidecar service in docker-compose"
        for snippet in (
            "build:\n      context: ./bedrock-sidecar",
            "container_name: bedrock-sidecar",
            "BEDROCK_APP_ROLE_ARN=${bedrock_app_role_arn}",
            "- bedrock-creds:/creds",
            'test: ["CMD", "/refresh.sh", "-healthcheck"]',
            'tag: "docker.bedrock-sidecar"',
        ):
            self.assertIn(snippet, sidecar.group(1))
        jupyter = re.search(r"^  jupyter:\n(.*?)^  \S", text, re.S | re.M)
        assert jupyter is not None
        self.assertIn("- bedrock-creds:/run/bedrock-creds:ro", jupyter.group(1))
        self.assertIn("AWS_CONFIG_FILE=/etc/aws/config", jupyter.group(1))
        self.assertIn("volumes:\n  bedrock-creds:", text)

    def test_dockerfiles_bake_the_aws_config(self) -> None:
        for dockerfile in DOCKERFILES:
            with self.subTest(dockerfile=dockerfile.name):
                self.assertIn("COPY aws-config /etc/aws/config", _instructions(dockerfile))
        self.assertEqual((SERVICES_PATH / "jupyter" / "aws-config").read_text(), self.AWS_CONFIG)

    def test_services_tf_passes_sidecar_inputs(self) -> None:
        text = (ENGINE_PATH / "services.tf").read_text()
        for snippet in (
            "bedrock_enabled      = var.bedrock_enabled",
            'bedrock_app_role_arn = var.bedrock_enabled ? aws_iam_role.bedrock_app[0].arn : ""',
            '"deployment-docker/bedrock-sidecar/Dockerfile"',
            '"deployment-docker/bedrock-sidecar/refresh.sh"',
            "deployment-docker/aws-config",
        ):
            self.assertIn(snippet, text)

    def test_image_build_inputs_cover_versions_model_selection_and_sidecar(self) -> None:
        match = re.search(r"build_affecting_files = \[(.*?)\n  \]", (ENGINE_PATH / "services.tf").read_text(), re.S)
        assert match is not None, "no build_affecting_files list in services.tf"
        for snippet in (
            "var.claude_code_version",
            "var.codex_version",
            "local.bedrock_profile_prefix",
            "local.codex_model_patterns",
            "bedrock_sidecar_dockerfile.content",
            "bedrock_sidecar_refresh.content",
            "aws_config.content",
        ):
            self.assertIn(snippet, match.group(1))

    def test_status_requires_sidecar_only_when_enabled(self) -> None:
        text = (SERVICES_PATH / "commands" / "check-status-internal.sh").read_text()
        self.assertIn('REQUIRED_CONTAINERS+=("bedrock-sidecar")', text)
        self.assertIn("BEDROCK_ENABLED", text)

    def test_commands_and_manifest_know_the_sidecar(self) -> None:
        commands = (ENGINE_PATH / "commands.tf").read_text()
        for document in ("ssm_server_update", "ssm_server_logs"):
            with self.subTest(document=document):
                body = re.search(rf"{document}\s*=\s*<<DOC\n(.*?)\nDOC", commands, re.S)
                assert body is not None, f"no {document} heredoc"
                self.assertIn("      - bedrock-sidecar\n", body.group(1))
        self.assertIn("- bedrock-sidecar", (TEMPLATE_PATH / "manifest.yaml").read_text())
        self.assertIn(
            "Match               docker.bedrock-sidecar", (SERVICES_PATH / "fluent-bit" / "fluent-bit.conf").read_text()
        )


class TestJupyterNetworkIsolation(unittest.TestCase):
    """User code in the jupyter container must not be able to borrow the instance role from IMDS."""

    SUBNET = "172.30.250.0/24"
    ADDRESS = "172.30.250.10"

    def setUp(self) -> None:
        self.compose = (SERVICES_PATH / "docker-compose.yml.tftpl").read_text()
        self.jupyter = self._service("jupyter")
        self.traefik = self._service("traefik")

    def _service(self, name: str) -> str:
        match = re.search(rf"^  {name}:\n(.*?)^  \S", self.compose, re.S | re.M)
        assert match is not None, f"no {name} service"
        return match.group(1)

    def test_jupyter_is_isolated_on_its_own_network(self) -> None:
        self.assertIn(f"networks:\n      jupyter:\n        ipv4_address: {self.ADDRESS}\n", self.jupyter)
        self.assertNotIn("- web", self.jupyter)
        self.assertIn("AWS_EC2_METADATA_DISABLED=true", self.jupyter)
        network = "  jupyter:\n    name: jupyter\n    driver: bridge\n    ipam:\n      config:\n"
        network += f"        - subnet: {self.SUBNET}"
        self.assertIn(network, self.compose)

    def test_traefik_bridges_both_networks(self) -> None:
        self.assertIn("network: web", (SERVICES_PATH / "traefik" / "traefik.yml").read_text())
        self.assertIn("traefik.docker.network=jupyter", self.jupyter)
        self.assertIn("networks:\n      - web\n      - jupyter\n", self.traefik)

    def test_imds_rule_is_idempotent(self) -> None:
        text = (SERVICES_PATH / "docker-startup.sh").read_text()
        drop = f"-s {self.ADDRESS}/32 -d 169.254.169.254 -j DROP"
        insert = f"iptables -C DOCKER-USER {drop} 2>/dev/null || iptables -I DOCKER-USER 1 {drop}"
        raw = f"iptables -t raw -C PREROUTING {drop} 2>/dev/null || iptables -t raw -I PREROUTING 1 {drop}"
        self.assertIn(insert, text)
        self.assertIn(raw, text)
        # Stale subnet-wide rule from an earlier revision must be removed before the scoped one is added.
        stale = f"iptables -D DOCKER-USER -s {self.SUBNET} -d 169.254.169.254 -j DROP 2>/dev/null || true"
        self.assertIn(stale, text)
        self.assertLess(text.index(stale), text.index(insert))
        self.assertLess(text.index(insert), text.index("docker compose up"))
        self.assertLess(text.index(raw), text.index("docker compose up"))

    def test_compose_up_removes_orphans(self) -> None:
        # Flipping bedrock_enabled off re-renders the compose file without the sidecar; without this
        # flag the old container keeps running (and keeps the app role's credentials) across the update.
        ups = [
            line
            for line in (SERVICES_PATH / "docker-startup.sh").read_text().splitlines()
            if "docker compose up" in line
        ]
        self.assertEqual(len(ups), 3)
        for line in ups:
            self.assertIn("--remove-orphans", line)

    def test_imds_rule_survives_reboot(self) -> None:
        cloudinit = (SERVICES_PATH / "cloudinit.sh.tftpl").read_text()
        startup = (SERVICES_PATH / "docker-startup.sh").read_text()
        rule = re.compile(r"iptables -C DOCKER-USER .*? \|\| iptables -I DOCKER-USER 1 .*?-j DROP")
        raw = re.compile(r"iptables -t raw -C PREROUTING .*? \|\| iptables -t raw -I PREROUTING 1 .*?-j DROP")
        self.assertIn("/etc/systemd/system/docker.service.d/imds-block.conf", cloudinit)
        self.assertIn("systemctl daemon-reload", cloudinit)
        in_cloudinit, in_startup = rule.findall(cloudinit), rule.findall(startup)
        self.assertEqual(in_cloudinit, in_startup)
        self.assertEqual(len(in_cloudinit), 1)
        post = f"ExecStartPost=/bin/sh -c '{in_cloudinit[0]}'"
        self.assertIn(post, cloudinit)
        raw_cloudinit, raw_startup = raw.findall(cloudinit), raw.findall(startup)
        self.assertEqual(raw_cloudinit, raw_startup)
        self.assertEqual(len(raw_cloudinit), 1)
        # dockerd restarts the containers before ExecStartPost runs: the raw rule must already hold by then.
        pre = f"ExecStartPre=/bin/sh -c '{raw_cloudinit[0]}'"
        self.assertIn(pre, cloudinit)
        self.assertLess(cloudinit.index(pre), cloudinit.index(post))


class TestBedrockDocs(unittest.TestCase):
    def test_bedrock_page_in_toctree(self) -> None:
        toctree = re.search(r"```\{toctree\}\n(.*?)```", (DOCS_DIR / "index.md").read_text(), re.S)
        assert toctree is not None, "no toctree in index.md"
        self.assertIn("\nbedrock-integration\n", toctree.group(1))
        self.assertTrue((DOCS_DIR / "bedrock-integration.md").exists())
        # Everything Bedrock lives on its own page; the user guide stays install/deploy/open.
        self.assertNotIn("Use the coding agents", (DOCS_DIR / "user-guide.md").read_text())
        self.assertIn("bedrock-app", (DOCS_DIR / "details.md").read_text())
