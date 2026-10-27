"""Static checks for the coding agents (Claude Code, Codex) and their Bedrock access.

The image build, the IAM grants and the instance metadata settings only meet on a live deployment;
these tests pin each side to what the others expect.
"""

import re
import unittest
from pathlib import Path
from typing import Any

from jupyter_deploy.engine.terraform.tf_varfiles import parse_dot_tfvars_to_dict

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH

SERVICES_PATH: Path = TEMPLATE_PATH / "services"
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
    def test_bedrock_is_opt_in_and_codex_supports_bedrock(self) -> None:
        defaults = _hcl(ENGINE_PATH / "presets" / "defaults-all.tfvars")

        self.assertIs(defaults["bedrock_enabled"], False)
        # Codex reaches Bedrock through its amazon-bedrock-runtime provider from 0.128.0.
        codex_version = tuple(int(part) for part in defaults["codex_version"].split("."))
        self.assertGreaterEqual(codex_version, (0, 128, 0))


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


class TestInstanceMetadata(unittest.TestCase):
    def test_imds_hop_limit_allows_containers(self) -> None:
        main_tf = _hcl(ENGINE_PATH / "modules" / "ec2_instance" / "main.tf")
        instance = next(r["aws_instance"]["ec2_jupyter_server"] for r in main_tf["resource"] if "aws_instance" in r)
        (metadata_options,) = instance["metadata_options"]

        self.assertEqual(metadata_options["http_tokens"], "required")
        self.assertEqual(metadata_options["http_put_response_hop_limit"], 2)
