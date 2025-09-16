"""Tests for version consistency across the project."""

import re
import tomllib
from pathlib import Path

import yaml


def test_version_consistency() -> None:
    """
    Test that version numbers are consistent across the project.

    Verifies that the version is the same in:
    1. pyproject.toml
    2. __init__.py
    3. template/manifest.yaml
    4. template/engine/main.tf for template_version
    5. template/services/jupyter/pyproject.jupyter.toml.tftpl
    6. template/services/jupyter-pixi/pixi.jupyter.toml.tftpl
    7. template/services/jupyter/pyproject.kernel.toml.tftpl
    8. template/services/jupyter-pixi/pyproject.kernel.toml.tftpl
    """
    # Base path to the project
    project_path = Path(__file__).parent.parent.parent

    # Read version from pyproject.toml
    with open(project_path / "pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)
    pyproject_version = pyproject_data["project"]["version"]

    # Read version from __init__.py
    init_path = project_path / "jupyter_deploy_tf_aws_ec2_base" / "__init__.py"
    init_content = init_path.read_text()
    init_version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_content)
    assert init_version_match is not None, "Could not find __version__ in __init__.py"
    init_version = init_version_match.group(1)

    # Read version from template/manifest.yaml
    manifest_path = project_path / "jupyter_deploy_tf_aws_ec2_base" / "template" / "manifest.yaml"
    with open(manifest_path) as f:
        manifest_data = yaml.safe_load(f)
    manifest_version = manifest_data["template"]["version"]

    # Read version from template/engine/main.tf for template_version
    main_tf_path = project_path / "jupyter_deploy_tf_aws_ec2_base" / "template" / "engine" / "main.tf"
    main_tf_content = main_tf_path.read_text()
    main_tf_version_match = re.search(r'template_version\s*=\s*["\']([^"\']+)["\']', main_tf_content)
    assert main_tf_version_match is not None, "Could not find template_version in main.tf"
    main_tf_version = main_tf_version_match.group(1)

    # Read version from template/services/jupyter/pyproject.jupyter.toml.tftpl
    jupyter_pyproject_path = (
        project_path
        / "jupyter_deploy_tf_aws_ec2_base"
        / "template"
        / "services"
        / "jupyter"
        / "pyproject.jupyter.toml.tftpl"
    )
    # Extract version directly using regex for template files instead of parsing as TOML
    jupyter_pyproject_content = jupyter_pyproject_path.read_text()
    jupyter_pyproject_version_match = re.search(r'version\s*=\s*["\']([\d\.]+)["\']', jupyter_pyproject_content)
    assert jupyter_pyproject_version_match is not None, "Could not find version in pyproject.jupyter.toml.tftpl"
    jupyter_pyproject_version = jupyter_pyproject_version_match.group(1)

    # Read version from template/services/jupyter-pixi/pixi.jupyter.toml.tftpl
    jupyter_pixi_path = (
        project_path
        / "jupyter_deploy_tf_aws_ec2_base"
        / "template"
        / "services"
        / "jupyter-pixi"
        / "pixi.jupyter.toml.tftpl"
    )
    # Extract version directly using regex for template files instead of parsing as TOML
    jupyter_pixi_content = jupyter_pixi_path.read_text()
    jupyter_pixi_version_match = re.search(r'version\s*=\s*["\']([\d\.]+)["\']', jupyter_pixi_content)
    assert jupyter_pixi_version_match is not None, "Could not find version in pixi.jupyter.toml.tftpl"
    jupyter_pixi_version = jupyter_pixi_version_match.group(1)

    # Read version from template/services/jupyter/pyproject.kernel.toml.tftpl
    jupyter_kernel_path = (
        project_path
        / "jupyter_deploy_tf_aws_ec2_base"
        / "template"
        / "services"
        / "jupyter"
        / "pyproject.kernel.toml.tftpl"
    )
    jupyter_kernel_content = jupyter_kernel_path.read_text()
    jupyter_kernel_version_match = re.search(r'version\s*=\s*["\']([\d\.]+)["\']', jupyter_kernel_content)
    assert jupyter_kernel_version_match is not None, "Could not find version in jupyter/pyproject.kernel.toml.tftpl"
    jupyter_kernel_version = jupyter_kernel_version_match.group(1)

    # Read version from template/services/jupyter-pixi/pyproject.kernel.toml.tftpl
    jupyter_pixi_kernel_path = (
        project_path
        / "jupyter_deploy_tf_aws_ec2_base"
        / "template"
        / "services"
        / "jupyter-pixi"
        / "pyproject.kernel.toml.tftpl"
    )
    jupyter_pixi_kernel_content = jupyter_pixi_kernel_path.read_text()
    jupyter_pixi_kernel_version_match = re.search(r'version\s*=\s*["\']([\d\.]+)["\']', jupyter_pixi_kernel_content)
    assert jupyter_pixi_kernel_version_match is not None, (
        "Could not find version in jupyter-pixi/pyproject.kernel.toml.tftpl"
    )
    jupyter_pixi_kernel_version = jupyter_pixi_kernel_version_match.group(1)

    # Compare all versions
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
        f"jupyter/pyproject.jupyter.toml.tftpl ({jupyter_pyproject_version})"
    )

    assert pyproject_version == jupyter_pixi_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != "
        f"jupyter-pixi/pixi.jupyter.toml.tftpl ({jupyter_pixi_version})"
    )

    assert pyproject_version == jupyter_kernel_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != "
        f"jupyter/pyproject.kernel.toml.tftpl ({jupyter_kernel_version})"
    )

    assert pyproject_version == jupyter_pixi_kernel_version, (
        f"Version mismatch: pyproject.toml ({pyproject_version}) != "
        f"jupyter-pixi/pyproject.kernel.toml.tftpl ({jupyter_pixi_kernel_version})"
    )
