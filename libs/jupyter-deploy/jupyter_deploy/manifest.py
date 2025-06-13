from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict

from jupyter_deploy.engine.enum import EngineType


class JupyterDeployTemplateV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    engine: EngineType
    version: str


class JupyterDeployManifestV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: Literal[1]
    template: JupyterDeployTemplateV1

    def get_engine(self) -> EngineType:
        """Return the engine type."""
        return self.template.engine


# Combined type using discriminated union
JupyterDeployManifest = Annotated[JupyterDeployManifestV1, "schema_version"]
