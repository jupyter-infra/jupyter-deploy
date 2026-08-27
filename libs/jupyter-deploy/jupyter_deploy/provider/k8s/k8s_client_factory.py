from __future__ import annotations

import base64
import tempfile

from kubernetes import client, config


class K8sClientFactory:
    """Build Kubernetes API clients from kubeconfig or in-memory config."""

    @staticmethod
    def from_kubeconfig(kubeconfig_path: str | None = None) -> client.ApiClient:
        api_client: client.ApiClient = config.new_client_from_config(config_file=kubeconfig_path)
        return api_client

    @staticmethod
    def from_eks_cluster(
        endpoint: str,
        ca_data_b64: str,
        cluster_name: str,
        region: str,
    ) -> client.ApiClient:
        """Build an ApiClient in-memory for an EKS cluster.

        Uses STS presigned URL as bearer token, refreshed on each API call.
        """
        from jupyter_deploy.api.aws.sts.eks_token import get_eks_bearer_token  # noqa: PLC0415

        ca_cert_data = base64.b64decode(ca_data_b64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".crt") as ca_cert_file:
            ca_cert_file.write(ca_cert_data)
            ca_cert_path = ca_cert_file.name

        configuration = client.Configuration()
        configuration.host = endpoint
        configuration.ssl_ca_cert = ca_cert_path
        configuration.api_key_prefix["BearerToken"] = "Bearer"
        configuration.api_key["BearerToken"] = get_eks_bearer_token(binding_id=cluster_name, region=region)

        def _refresh_token(cfg: client.Configuration) -> None:
            cfg.api_key["BearerToken"] = get_eks_bearer_token(binding_id=cluster_name, region=region)

        configuration.refresh_api_key_hook = _refresh_token

        return client.ApiClient(configuration=configuration)
