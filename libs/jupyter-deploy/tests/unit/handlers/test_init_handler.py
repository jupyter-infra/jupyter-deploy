import unittest
from pathlib import Path
from unittest.mock import ANY, MagicMock, Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.enum import StoreType, TemplateSource
from jupyter_deploy.exceptions import (
    InvalidTemplateNameError,
    StoreTypeNotSpecifiedError,
    TemplateNotFoundError,
)
from jupyter_deploy.handlers.init_handler import InitHandler, _suggest_template_package
from jupyter_deploy.infrastructure.enum import AWSInfrastructureType
from jupyter_deploy.preferences import JupyterDeployPreferencesV1
from jupyter_deploy.provider.enum import ProviderType

_RETRIEVE_PREFERENCES = "jupyter_deploy.handlers.preferences_handler.retrieve_preferences"
_TEMPLATES = "jupyter_deploy.handlers.init_handler.TEMPLATES"


class TestInitHandler(unittest.TestCase):
    """Test class for InitHandler."""

    def setUp(self) -> None:
        # Every construction below omits the template, so the handler reads the preferences file.
        # Neutralize it for the whole class: patched here rather than per test, because these tests
        # are about project paths and template lookup, not about resolution, and a decorator would
        # add an unused argument to each of their signatures.
        patcher = patch(_RETRIEVE_PREFERENCES, return_value=JupyterDeployPreferencesV1())
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch("jupyter_deploy.fs_utils.get_default_project_path")
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_init_with_project_dir(
        self, mock_find_template_path: MagicMock, mock_get_default_project_path: MagicMock
    ) -> None:
        """Test initialization with project_dir provided."""
        # Setup
        project_dir = Path("/test/project/dir")
        mock_template_path = Path("/mock/template/path")
        mock_find_template_path.return_value = mock_template_path

        # Execute
        handler = InitHandler(project_dir=project_dir)

        # Assert
        self.assertEqual(handler.project_path, Path(project_dir))
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        mock_find_template_path.assert_called_once_with("aws:ec2:jupyterlab")
        mock_get_default_project_path.assert_not_called()

    @patch("jupyter_deploy.fs_utils.get_default_project_path")
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_init_without_project_dir(
        self, mock_find_template_path: MagicMock, mock_get_default_project_path: MagicMock
    ) -> None:
        """Test initialization without project_dir provided."""
        # Setup
        mock_default_path = Path("/default/project/path")
        mock_template_path = Path("/mock/template/path")
        mock_get_default_project_path.return_value = mock_default_path
        mock_find_template_path.return_value = mock_template_path

        # Execute
        handler = InitHandler(project_dir=None)

        # Assert
        self.assertEqual(handler.project_path, mock_default_path)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        mock_find_template_path.assert_called_once_with("aws:ec2:jupyterlab")
        mock_get_default_project_path.assert_called_once()

    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_init_with_enum_parameters(self, mock_find_template_path: MagicMock) -> None:
        """Test initialization with enum types for provider and infrastructure."""
        # Setup
        project_dir = Path("/test/project/dir")
        mock_template_path = Path("/mock/template/path")
        mock_find_template_path.return_value = mock_template_path

        # Execute
        handler = InitHandler(
            project_dir=project_dir,
            engine=EngineType.TERRAFORM,
            provider=ProviderType.AWS,
            infrastructure=AWSInfrastructureType.EC2,
            template="custom-template",
        )

        # Assert
        self.assertEqual(handler.project_path, Path(project_dir))
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        mock_find_template_path.assert_called_once_with("aws:ec2:custom-template")

    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_init_with_full_template_name_ignores_provider_and_infrastructure(
        self, mock_find_template_path: MagicMock
    ) -> None:
        """A template that already names its provider and infrastructure is used as-is."""
        mock_find_template_path.return_value = Path("/mock/template/path")

        InitHandler(
            project_dir=Path("/test/project/dir"),
            provider=ProviderType.AWS,
            infrastructure=AWSInfrastructureType.EC2,
            template="AWS:EKS:oidc",
        )

        mock_find_template_path.assert_called_once_with("aws:eks:oidc")

    @patch("jupyter_deploy.fs_utils.is_empty_dir")
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_may_export_to_project_path_not_exists(
        self, mock_find_template_path: MagicMock, mock_is_empty_dir: MagicMock
    ) -> None:
        """Test may_export_to_project_path when project path doesn't exist."""
        # Setup
        mock_path = MagicMock()
        mock_exists = MagicMock(return_value=False)
        mock_path.exists = mock_exists
        mock_find_template_path.return_value = Path("/mock/template/path")

        handler = InitHandler(project_dir=Path("/test/project/dir"))
        handler.project_path = mock_path

        # Execute
        result = handler.may_export_to_project_path()

        # Assert
        self.assertTrue(result)
        mock_exists.assert_called_once()
        mock_is_empty_dir.assert_not_called()

    @patch("jupyter_deploy.fs_utils.is_empty_dir")
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_may_export_to_project_path_exists_empty(
        self, mock_find_template_path: MagicMock, mock_is_empty_dir: MagicMock
    ) -> None:
        """Test may_export_to_project_path when project path exists and is empty."""
        # Setup
        mock_path = MagicMock()
        mock_exists = MagicMock(return_value=True)
        mock_path.exists = mock_exists
        mock_is_empty_dir.return_value = True
        mock_find_template_path.return_value = Path("/mock/template/path")

        handler = InitHandler(project_dir=Path("/test/project/dir"))
        handler.project_path = mock_path

        # Execute
        result = handler.may_export_to_project_path()

        # Assert
        self.assertTrue(result)
        mock_exists.assert_called_once()
        mock_is_empty_dir.assert_called_once_with(mock_path)

    @patch("jupyter_deploy.fs_utils.is_empty_dir")
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_may_export_to_project_path_exists_not_empty(
        self, mock_find_template_path: MagicMock, mock_is_empty_dir: MagicMock
    ) -> None:
        """Test may_export_to_project_path when project path exists and is not empty."""
        # Setup
        mock_path = MagicMock()
        mock_exists = MagicMock(return_value=True)
        mock_path.exists = mock_exists
        mock_is_empty_dir.return_value = False
        mock_find_template_path.return_value = Path("/mock/template/path")

        handler = InitHandler(project_dir=Path("/test/project/dir"))
        handler.project_path = mock_path

        # Execute
        result = handler.may_export_to_project_path()

        # Assert
        self.assertFalse(result)
        mock_exists.assert_called_once()
        mock_is_empty_dir.assert_called_once_with(mock_path)

    @patch("jupyter_deploy.fs_utils.safe_clean_directory")
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_clear_project_path(self, mock_find_template_path: MagicMock, mock_safe_clean_directory: MagicMock) -> None:
        """Test clear_project_path calls fs_utils.safe_clean_directory with correct path."""
        # Setup
        mock_path = Path("/test/project/dir")
        mock_find_template_path.return_value = Path("/mock/template/path")

        handler = InitHandler(project_dir=Path("/test/project/dir"))
        handler.project_path = mock_path

        # Execute
        handler.clear_project_path()

        # Assert
        mock_safe_clean_directory.assert_called_once_with(mock_path)

    @patch("jupyter_deploy.handlers.init_handler.DocsGenerator")
    @patch("jupyter_deploy.fs_utils.safe_copy_tree")
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_setup(
        self,
        mock_find_template_path: MagicMock,
        mock_safe_copy_tree: MagicMock,
        mock_docs_generator_class: MagicMock,
    ) -> None:
        """Test setup calls fs_utils.safe_copy_tree and generates docs."""
        # Setup
        mock_project_path = Path("/test/project/dir")
        mock_source_path = Path("/mock/template/path")
        mock_find_template_path.return_value = mock_source_path

        mock_docs_generator = MagicMock()
        mock_docs_generator_class.return_value = mock_docs_generator

        handler = InitHandler(project_dir=Path("/test/project/dir"))
        handler.project_path = mock_project_path

        # Execute
        handler.setup()

        # Assert
        mock_safe_copy_tree.assert_called_once_with(mock_source_path, mock_project_path)
        mock_docs_generator_class.assert_called_once_with(
            project_path=mock_project_path,
            engine=EngineType.TERRAFORM.value,
        )
        mock_docs_generator.generate_gitignore.assert_called_once()
        mock_docs_generator.generate_agent_md.assert_called_once()


class TestInitHandlerRestore(unittest.TestCase):
    @patch("jupyter_deploy.handlers.init_handler.write_store_config")
    @patch("jupyter_deploy.handlers.init_handler.StoreManagerFactory")
    def test_restore_pulls_from_store(self, mock_factory: Mock, mock_write_store_config: Mock) -> None:
        mock_store_manager = Mock()
        mock_store_manager.resolve_store.return_value = Mock(store_id="discovered-bucket")
        mock_factory.get_manager.return_value = mock_store_manager

        result = InitHandler.restore(
            project_dir=Path("/tmp/restored"),
            project_id="tpl-abc123",
            store_type=StoreType.S3_ONLY,
            display_manager=NullDisplay(),
        )

        mock_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_ONLY, store_id=None)
        mock_store_manager.pull.assert_called_once_with("tpl-abc123", Path("/tmp/restored"), ANY)
        self.assertEqual(result, Path("/tmp/restored").resolve())

    @patch("jupyter_deploy.handlers.init_handler.write_store_config")
    @patch("jupyter_deploy.handlers.init_handler.StoreManagerFactory")
    def test_restore_passes_store_id(self, mock_factory: Mock, mock_write_store_config: Mock) -> None:
        mock_store_manager = Mock()
        mock_store_manager.resolve_store.return_value = Mock(store_id="my-bucket")
        mock_factory.get_manager.return_value = mock_store_manager

        InitHandler.restore(
            project_dir=Path("/tmp/restored"),
            project_id="tpl-abc123",
            store_type=StoreType.S3_ONLY,
            display_manager=NullDisplay(),
            store_id="my-bucket",
        )

        mock_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_ONLY, store_id="my-bucket")

    @patch("jupyter_deploy.handlers.init_handler.write_store_config")
    @patch("jupyter_deploy.handlers.init_handler.StoreManagerFactory")
    def test_restore_writes_store_config(self, mock_factory: Mock, mock_write_store_config: Mock) -> None:
        mock_store_manager = Mock()
        mock_store_manager.resolve_store.return_value = Mock(store_id="discovered-bucket")
        mock_factory.get_manager.return_value = mock_store_manager

        InitHandler.restore(
            project_dir=Path("/tmp/restored"),
            project_id="tpl-abc123",
            store_type=StoreType.S3_ONLY,
            display_manager=NullDisplay(),
        )

        mock_write_store_config.assert_called_once_with(
            Path("/tmp/restored"),
            store_type="s3-only",
            store_id="discovered-bucket",
            project_id="tpl-abc123",
        )

    @patch("jupyter_deploy.handlers.init_handler.write_store_config")
    @patch("jupyter_deploy.handlers.init_handler.StoreManagerFactory")
    def test_restore_writes_store_config_with_explicit_store_id(
        self, mock_factory: Mock, mock_write_store_config: Mock
    ) -> None:
        mock_store_manager = Mock()
        mock_store_manager.resolve_store.return_value = Mock(store_id="my-bucket")
        mock_factory.get_manager.return_value = mock_store_manager

        InitHandler.restore(
            project_dir=Path("/tmp/restored"),
            project_id="tpl-abc123",
            store_type=StoreType.S3_ONLY,
            display_manager=NullDisplay(),
            store_id="my-bucket",
        )

        mock_write_store_config.assert_called_once_with(
            Path("/tmp/restored"),
            store_type="s3-only",
            store_id="my-bucket",
            project_id="tpl-abc123",
        )


class TestInitHandlerTemplateResolution(unittest.TestCase):
    """The handler resolves the template so that every consumer gets the same precedence."""

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_falls_back_to_the_preference(self, mock_find_template_path: MagicMock, mock_prefs: Mock) -> None:
        mock_prefs.return_value = JupyterDeployPreferencesV1(default_template="aws:ec2:base")

        handler = InitHandler(project_dir=Path("/test/dir"), template=None)

        self.assertEqual(handler.template_name, "aws:ec2:base")
        self.assertEqual(handler.template_source, TemplateSource.PREFERENCES)
        mock_find_template_path.assert_called_once_with("aws:ec2:base")

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_falls_back_to_the_built_in_default_and_records_it(
        self, mock_find_template_path: MagicMock, mock_prefs: Mock
    ) -> None:
        mock_prefs.return_value = JupyterDeployPreferencesV1()

        handler = InitHandler(project_dir=Path("/test/dir"), template=None)

        self.assertEqual(handler.template_name, "aws:ec2:jupyterlab")
        self.assertEqual(handler.template_source, TemplateSource.BUILT_IN)

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_explicit_template_beats_the_preference(self, mock_find_template_path: MagicMock, mock_prefs: Mock) -> None:
        mock_prefs.return_value = JupyterDeployPreferencesV1(default_template="aws:ec2:base")

        handler = InitHandler(project_dir=Path("/test/dir"), template="aws:eks:oidc")

        self.assertEqual(handler.template_name, "aws:eks:oidc")
        self.assertEqual(handler.template_source, TemplateSource.ARGUMENT)
        mock_prefs.assert_not_called()

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_raises_on_a_malformed_preference(self, mock_find_template_path: MagicMock, mock_prefs: Mock) -> None:
        mock_prefs.return_value = JupyterDeployPreferencesV1(default_template="ec2:base")

        with self.assertRaises(InvalidTemplateNameError):
            InitHandler(project_dir=Path("/test/dir"), template=None)

        mock_find_template_path.assert_not_called()

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.init_handler.InitHandler._find_template_path")
    def test_raises_on_a_malformed_argument(self, mock_find_template_path: MagicMock, mock_prefs: Mock) -> None:
        with self.assertRaises(InvalidTemplateNameError):
            InitHandler(project_dir=Path("/test/dir"), template="aws::base")

        mock_find_template_path.assert_not_called()


class TestInitHandlerRestoreStoreTypeResolution(unittest.TestCase):
    """Restoring reaches a store, so it falls back to the preference like every other store command."""

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.init_handler.write_store_config")
    @patch("jupyter_deploy.handlers.init_handler.StoreManagerFactory")
    def test_uses_the_given_store_type(
        self, mock_factory: Mock, mock_write_store_config: Mock, mock_prefs: Mock
    ) -> None:
        mock_factory.get_manager.return_value = Mock(resolve_store=Mock(return_value=Mock(store_id="a-bucket")))

        InitHandler.restore(
            project_dir=Path("/tmp/restored"),
            project_id="tpl-abc123",
            store_type=StoreType.S3_ONLY,
            display_manager=NullDisplay(),
        )

        mock_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_ONLY, store_id=None)
        mock_prefs.assert_not_called()

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.init_handler.write_store_config")
    @patch("jupyter_deploy.handlers.init_handler.StoreManagerFactory")
    def test_falls_back_to_the_preferred_store_type(
        self, mock_factory: Mock, mock_write_store_config: Mock, mock_prefs: Mock
    ) -> None:
        mock_factory.get_manager.return_value = Mock(resolve_store=Mock(return_value=Mock(store_id="a-bucket")))
        mock_prefs.return_value = JupyterDeployPreferencesV1(default_store_type="s3-ddb")

        InitHandler.restore(
            project_dir=Path("/tmp/restored"),
            project_id="tpl-abc123",
            display_manager=NullDisplay(),
        )

        mock_factory.get_manager.assert_called_once_with(store_type=StoreType.S3_DDB, store_id=None)
        self.assertEqual(mock_write_store_config.call_args.kwargs["store_type"], "s3-ddb")

    @patch(_RETRIEVE_PREFERENCES)
    @patch("jupyter_deploy.handlers.init_handler.write_store_config")
    @patch("jupyter_deploy.handlers.init_handler.StoreManagerFactory")
    def test_raises_when_neither_is_available(
        self, mock_factory: Mock, mock_write_store_config: Mock, mock_prefs: Mock
    ) -> None:
        mock_prefs.return_value = JupyterDeployPreferencesV1()

        with self.assertRaises(StoreTypeNotSpecifiedError):
            InitHandler.restore(
                project_dir=Path("/tmp/restored"),
                project_id="tpl-abc123",
                display_manager=NullDisplay(),
            )

        mock_factory.get_manager.assert_not_called()


class TestFindTemplatePath(unittest.TestCase):
    """Exercises the real lookup: `init_handler` imports TEMPLATES directly, so patch it there."""

    def setUp(self) -> None:
        patcher = patch(_RETRIEVE_PREFERENCES, return_value=JupyterDeployPreferencesV1())
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch(_TEMPLATES, {"terraform": {"aws:ec2:base": Path("/installed/base")}})
    def test_returns_the_path_of_an_installed_template(self) -> None:
        handler = InitHandler(project_dir=Path("/test/dir"), template="aws:ec2:base")

        self.assertEqual(handler.source_path, Path("/installed/base"))

    @patch(_TEMPLATES, {"terraform": {"aws:ec2:base": Path("/installed/base")}})
    def test_names_what_is_installed_when_the_template_is_missing(self) -> None:
        with self.assertRaises(TemplateNotFoundError) as ctx:
            InitHandler(project_dir=Path("/test/dir"), template="aws:ec2:jupyterlab")

        self.assertEqual(ctx.exception.template_name, "aws:ec2:jupyterlab")
        self.assertEqual(ctx.exception.engine, "terraform")
        self.assertEqual(ctx.exception.installed, ["aws:ec2:base"])
        self.assertEqual(ctx.exception.suggested_package, "jupyter-deploy-tf-aws-ec2-jupyterlab")

    @patch(_TEMPLATES, {"terraform": {}})
    def test_reports_an_empty_installed_list(self) -> None:
        with self.assertRaises(TemplateNotFoundError) as ctx:
            InitHandler(project_dir=Path("/test/dir"), template="aws:ec2:jupyterlab")

        self.assertEqual(ctx.exception.installed, [])

    @patch(_TEMPLATES, {"terraform": {"aws:eks:oidc": Path("/x"), "aws:ec2:base": Path("/y")}})
    def test_sorts_the_installed_list(self) -> None:
        with self.assertRaises(TemplateNotFoundError) as ctx:
            InitHandler(project_dir=Path("/test/dir"), template="aws:ec2:jupyterlab")

        self.assertEqual(ctx.exception.installed, ["aws:ec2:base", "aws:eks:oidc"])

    @patch(_TEMPLATES, {"terraform": {"aws:ec2:base": Path("/installed/base")}})
    def test_refuses_an_empty_template_name(self) -> None:
        """Unreachable through the CLI, since resolving a template never yields an empty name."""
        handler = InitHandler(project_dir=Path("/test/dir"), template="aws:ec2:base")

        with self.assertRaisesRegex(ValueError, "Template name cannot be empty"):
            handler._find_template_path("")

    @patch(_TEMPLATES, {})
    def test_refuses_an_engine_that_registers_no_templates(self) -> None:
        """Unreachable through the CLI, since --engine only accepts the EngineType values."""
        with self.assertRaisesRegex(ValueError, "Engine 'terraform' is not supported"):
            InitHandler(project_dir=Path("/test/dir"), template="aws:ec2:base")


class TestSuggestTemplatePackage(unittest.TestCase):
    def test_composes_the_conventional_distribution_name(self) -> None:
        self.assertEqual(
            _suggest_template_package("terraform", "aws:ec2:jupyterlab"),
            "jupyter-deploy-tf-aws-ec2-jupyterlab",
        )

    def test_returns_none_for_an_engine_with_no_known_abbreviation(self) -> None:
        self.assertIsNone(_suggest_template_package("pulumi", "aws:ec2:jupyterlab"))

    def test_returns_none_for_a_name_that_is_not_three_segments(self) -> None:
        self.assertIsNone(_suggest_template_package("terraform", "jupyterlab"))
