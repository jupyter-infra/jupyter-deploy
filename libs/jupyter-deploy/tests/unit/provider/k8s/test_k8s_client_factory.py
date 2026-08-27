import base64
import os
import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.provider.k8s.k8s_client_factory import K8sClientFactory


class TestK8sClientFactory(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_client_factory.config")
    def test_from_kubeconfig_with_path(self, mock_config: Mock) -> None:
        mock_api_client: Mock = Mock()
        mock_config.new_client_from_config.return_value = mock_api_client

        result = K8sClientFactory.from_kubeconfig(kubeconfig_path="/home/user/.kube/config")

        self.assertEqual(result, mock_api_client)
        mock_config.new_client_from_config.assert_called_once_with(config_file="/home/user/.kube/config")

    @patch("jupyter_deploy.provider.k8s.k8s_client_factory.config")
    def test_from_kubeconfig_without_path_uses_default(self, mock_config: Mock) -> None:
        mock_api_client: Mock = Mock()
        mock_config.new_client_from_config.return_value = mock_api_client

        result = K8sClientFactory.from_kubeconfig()

        self.assertEqual(result, mock_api_client)
        mock_config.new_client_from_config.assert_called_once_with(config_file=None)


class TestK8sClientFactoryFromEks(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.sts.eks_token.get_eks_bearer_token")
    @patch("jupyter_deploy.provider.k8s.k8s_client_factory.client")
    def test_from_eks_cluster_configures_endpoint_and_auth(self, mock_client_mod: Mock, mock_get_token: Mock) -> None:
        mock_get_token.return_value = "k8s-aws-v1.test-token"
        mock_configuration: Mock = Mock()
        mock_configuration.api_key = {}
        mock_configuration.api_key_prefix = {}
        mock_client_mod.Configuration.return_value = mock_configuration
        mock_api_client: Mock = Mock()
        mock_client_mod.ApiClient.return_value = mock_api_client

        ca_data = base64.b64encode(b"FAKE-CA-CERT").decode()

        result = K8sClientFactory.from_eks_cluster(
            endpoint="https://example.eks.amazonaws.com",
            ca_data_b64=ca_data,
            cluster_name="my-cluster",
            region="us-west-2",
        )

        self.assertEqual(result, mock_api_client)
        self.assertEqual(mock_configuration.host, "https://example.eks.amazonaws.com")
        self.assertEqual(mock_configuration.api_key_prefix["BearerToken"], "Bearer")
        self.assertEqual(mock_configuration.api_key["BearerToken"], "k8s-aws-v1.test-token")
        mock_get_token.assert_called_once_with(binding_id="my-cluster", region="us-west-2")

    @patch("jupyter_deploy.api.aws.sts.eks_token.get_eks_bearer_token")
    @patch("jupyter_deploy.provider.k8s.k8s_client_factory.client")
    def test_from_eks_cluster_writes_ca_cert_to_temp_file(self, mock_client_mod: Mock, mock_get_token: Mock) -> None:
        mock_get_token.return_value = "k8s-aws-v1.test-token"
        mock_configuration: Mock = Mock()
        mock_configuration.api_key = {}
        mock_configuration.api_key_prefix = {}
        mock_client_mod.Configuration.return_value = mock_configuration
        mock_client_mod.ApiClient.return_value = Mock()

        ca_content = b"-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----"
        ca_data = base64.b64encode(ca_content).decode()

        K8sClientFactory.from_eks_cluster(
            endpoint="https://example.eks.amazonaws.com",
            ca_data_b64=ca_data,
            cluster_name="my-cluster",
            region="us-west-2",
        )

        ca_path = mock_configuration.ssl_ca_cert
        self.assertTrue(os.path.exists(ca_path))
        with open(ca_path, "rb") as f:
            self.assertEqual(f.read(), ca_content)
        os.unlink(ca_path)

    @patch("jupyter_deploy.api.aws.sts.eks_token.get_eks_bearer_token")
    @patch("jupyter_deploy.provider.k8s.k8s_client_factory.client")
    def test_from_eks_cluster_sets_refresh_hook(self, mock_client_mod: Mock, mock_get_token: Mock) -> None:
        mock_get_token.return_value = "k8s-aws-v1.initial-token"
        mock_configuration: Mock = Mock()
        mock_configuration.api_key = {}
        mock_configuration.api_key_prefix = {}
        mock_client_mod.Configuration.return_value = mock_configuration
        mock_client_mod.ApiClient.return_value = Mock()

        ca_data = base64.b64encode(b"FAKE").decode()

        K8sClientFactory.from_eks_cluster(
            endpoint="https://example.eks.amazonaws.com",
            ca_data_b64=ca_data,
            cluster_name="my-cluster",
            region="us-west-2",
        )

        self.assertIsNotNone(mock_configuration.refresh_api_key_hook)

        mock_get_token.return_value = "k8s-aws-v1.refreshed-token"
        mock_configuration.refresh_api_key_hook(mock_configuration)
        self.assertEqual(mock_configuration.api_key["BearerToken"], "k8s-aws-v1.refreshed-token")
