"""Schema of the user-scoped CLI preferences.

Preferences supply the defaults that a command falls back to when the caller passed no explicit
flag. They live outside every project on purpose: a project records what it *is*, in
`.jd/store.yaml` and `variables.yaml`, whereas a preference records what this user wants when they
say nothing. Reading and writing the file belongs to `handlers/preferences_handler.py`.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from jupyter_deploy.enum import PreferenceName, PreferenceSource, StoreType
from jupyter_deploy.exceptions import InvalidStoreTypeError, InvalidTemplateNameError

PREFERENCES_V1_KEYS_ORDER = [
    "schema_version",
    "default-template",
    "default-store-type",
]

# Number of colon-separated segments in a template name: <provider>:<infrastructure>:<template>
TEMPLATE_NAME_SEGMENTS = 3


class PreferenceEntry(BaseModel):
    """One preference and its effective value, for display purposes."""

    name: PreferenceName
    value: str | None
    source: PreferenceSource


class JupyterDeployPreferencesV1(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Defaulted rather than required, unlike the manifest and variables files: those are always
    # generated, whereas a user may hand-write this one, and a file with no version is a V1 file.
    # A file declaring a LATER version fails to validate, which is the point of the key -- only a
    # breaking change bumps it, since adding a preference is tolerated by `extra="allow"`.
    schema_version: Literal[1] = 1
    default_template: str | None = Field(alias="default-template", default=None)
    default_store_type: str | None = Field(alias="default-store-type", default=None)

    def get_store_type(self) -> StoreType | None:
        """Return the preferred store type as an enum, or None when unset.

        Raises:
            InvalidStoreTypeError: If the store type is not recognized.
        """
        if self.default_store_type is None:
            return None
        try:
            return StoreType.from_string(self.default_store_type)
        except ValueError:
            raise InvalidStoreTypeError(self.default_store_type, [t.value for t in StoreType]) from None


# Combined type using discriminated union
JupyterDeployPreferences = Annotated[JupyterDeployPreferencesV1, "schema_version"]


def validate_template_name(template_name: str) -> None:
    """Verify a full template name has the shape <provider>:<infrastructure>:<template>.

    Checks the shape only, not that the template is installed: a preference may legitimately name a
    template package that the user has not installed yet.

    Raises:
        InvalidTemplateNameError: If the name is not three non-empty segments.
    """
    segments = template_name.split(":")
    if len(segments) != TEMPLATE_NAME_SEGMENTS or not all(segments):
        raise InvalidTemplateNameError(template_name)
