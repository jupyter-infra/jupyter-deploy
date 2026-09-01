import re
import unittest
from pathlib import Path

from jupyter_deploy_tf_aws_ec2_jupyterlab.template import TEMPLATE_PATH


class TestLoggingConsistency(unittest.TestCase):
    """The fluent-bit outputs and the docker-compose fluentd logging tags must stay in lockstep.

    Each container that logs via the ``fluentd`` driver carries a ``tag: "docker.<name>"``; fluent-bit
    routes each tag to a file with a matching ``Match docker.<name>``. A tag with no matching output
    silently drops that container's logs (the bug caught on PR #353's auth-sidecar); a Match with no
    tag is a dead rule that will drop the next renamed service. This guards both directions.
    """

    COMPOSE_PATH: Path = TEMPLATE_PATH / "services" / "docker-compose.yml.tftpl"
    FLUENT_BIT_PATH: Path = TEMPLATE_PATH / "services" / "fluent-bit" / "fluent-bit.conf"

    def test_compose_tags_match_fluent_bit_outputs(self) -> None:
        compose_tags = set(re.findall(r'tag:\s*"(docker\.[\w-]+)"', self.COMPOSE_PATH.read_text()))
        fluent_bit_matches = set(
            re.findall(r"^\s*Match\s+(docker\.[\w-]+)\s*$", self.FLUENT_BIT_PATH.read_text(), re.M)
        )

        self.assertTrue(compose_tags, "expected at least one fluentd logging tag in docker-compose")
        self.assertEqual(
            compose_tags,
            fluent_bit_matches,
            f"fluentd tags without a fluent-bit output (logs dropped): {compose_tags - fluent_bit_matches}; "
            f"fluent-bit Match rules with no matching container tag (dead rules): {fluent_bit_matches - compose_tags}",
        )
