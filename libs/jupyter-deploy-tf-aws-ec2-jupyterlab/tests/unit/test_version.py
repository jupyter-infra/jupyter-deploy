"""Tests for version consistency across the project."""

import re
import tomllib
from pathlib import Path

import yaml

PACKAGE_DIR = "jupyter_deploy_tf_aws_ec2_jupyterlab"


def _extract_version(path: Path, pattern: str) -> str:
    match = re.search(pattern, path.read_text())
    assert match is not None, f"Could not find version in {path}"
    return match.group(1)


def test_version_consistency() -> None:
    """Test that version numbers are consistent across the project.

    Verifies that the version is the same in:
    1. pyproject.toml
    2. __init__.py
    3. template/manifest.yaml
    4. template/engine/main.tf for template_version
    5. template/services/jupyter/pyproject.jupyter.toml
    6. template/services/jupyter-pixi/pixi.jupyter.toml.tftpl
    7. template/services/jupyter/pyproject.kernel.toml
    8. template/services/jupyter-pixi/pyproject.kernel.toml
    """
    project_path = Path(__file__).parent.parent.parent

    with open(project_path / "pyproject.toml", "rb") as f:
        pyproject_version = tomllib.load(f)["project"]["version"]

    init_version = _extract_version(
        project_path / PACKAGE_DIR / "__init__.py",
        r'__version__\s*=\s*["\']([^"\']+)["\']',
    )

    manifest_path = project_path / PACKAGE_DIR / "template" / "manifest.yaml"
    with open(manifest_path) as f:
        manifest_version = yaml.safe_load(f)["template"]["version"]

    main_tf_version = _extract_version(
        project_path / PACKAGE_DIR / "template" / "engine" / "main.tf",
        r'template_version\s*=\s*["\']([^"\']+)["\']',
    )

    services_dir = project_path / PACKAGE_DIR / "template" / "services"
    jupyter_pyproject_version = _extract_version(
        services_dir / "jupyter" / "pyproject.jupyter.toml",
        r'version\s*=\s*["\']([\d\.]+)["\']',
    )
    jupyter_pixi_version = _extract_version(
        services_dir / "jupyter-pixi" / "pixi.jupyter.toml.tftpl",
        r'version\s*=\s*["\']([\d\.]+)["\']',
    )
    jupyter_kernel_version = _extract_version(
        services_dir / "jupyter" / "pyproject.kernel.toml",
        r'version\s*=\s*["\']([\d\.]+)["\']',
    )
    jupyter_pixi_kernel_version = _extract_version(
        services_dir / "jupyter-pixi" / "pyproject.kernel.toml",
        r'version\s*=\s*["\']([\d\.]+)["\']',
    )

    assert pyproject_version == init_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != __init__.py ({init_version})"
    )
    assert pyproject_version == manifest_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != manifest.yaml ({manifest_version})"
    )
    assert pyproject_version == main_tf_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != main.tf template_version ({main_tf_version})"
    )
    assert pyproject_version == jupyter_pyproject_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != "
        f"jupyter/pyproject.jupyter.toml ({jupyter_pyproject_version})"
    )
    assert pyproject_version == jupyter_pixi_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != "
        f"jupyter-pixi/pixi.jupyter.toml.tftpl ({jupyter_pixi_version})"
    )
    assert pyproject_version == jupyter_kernel_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != "
        f"jupyter/pyproject.kernel.toml ({jupyter_kernel_version})"
    )
    assert pyproject_version == jupyter_pixi_kernel_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != "
        f"jupyter-pixi/pyproject.kernel.toml ({jupyter_pixi_kernel_version})"
    )
