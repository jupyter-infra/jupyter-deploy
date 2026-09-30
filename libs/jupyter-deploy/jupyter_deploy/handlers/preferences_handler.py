"""Handler for the user-scoped CLI preferences."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from jupyter_deploy import constants, fs_utils, preferences, template_utils
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.enum import PreferenceName, PreferenceSource, StoreType, TemplateSource
from jupyter_deploy.exceptions import ReadPreferencesError
from jupyter_deploy.preferences import PreferenceEntry


class PreferencesHandler:
    """Read and write the preferences that supply the defaults of other commands."""

    def __init__(self, display_manager: DisplayManager) -> None:
        """Create the preferences handler."""
        self.display_manager = display_manager
        self.preferences_path = get_preferences_path()

    def list_preferences(self) -> list[PreferenceEntry]:
        """Return every settable preference with its effective value and where that value came from.

        Raises:
            ReadPreferencesError: If the preferences file cannot be read or parsed.
        """
        prefs = retrieve_preferences()

        if prefs.default_template:
            template_entry = PreferenceEntry(
                name=PreferenceName.DEFAULT_TEMPLATE,
                value=prefs.default_template,
                source=PreferenceSource.PREFERENCES,
            )
        else:
            template_entry = PreferenceEntry(
                name=PreferenceName.DEFAULT_TEMPLATE,
                value=constants.DEFAULT_TEMPLATE,
                source=PreferenceSource.BUILT_IN,
            )

        if prefs.default_store_type:
            store_type_entry = PreferenceEntry(
                name=PreferenceName.DEFAULT_STORE_TYPE,
                value=prefs.default_store_type,
                source=PreferenceSource.PREFERENCES,
            )
        else:
            # There is no built-in store type: unset means every store command needs --store-type,
            # and every project keeps the store type its own template manifest declares.
            store_type_entry = PreferenceEntry(
                name=PreferenceName.DEFAULT_STORE_TYPE,
                value=None,
                source=PreferenceSource.UNSET,
            )

        return [template_entry, store_type_entry]

    def set_preferences(
        self,
        default_template: str | None = None,
        default_store_type: StoreType | None = None,
    ) -> Path:
        """Persist the given preferences, leaving the ones passed as None untouched.

        Returns:
            Path: the preferences file written to.

        Raises:
            InvalidTemplateNameError: If the template name is not <provider>:<infrastructure>:<template>.
            ReadPreferencesError: If the existing preferences file cannot be read or parsed.
        """
        prefs = retrieve_preferences()

        if default_template is not None:
            preferences.validate_template_name(default_template)
            self._warn_if_template_not_installed(default_template)
            prefs.default_template = default_template

        if default_store_type is not None:
            prefs.default_store_type = default_store_type.value

        return write_preferences(prefs)

    def unset_preferences(self, names: list[PreferenceName]) -> Path:
        """Clear the given preferences, reverting them to the built-in defaults.

        Returns:
            Path: the preferences file written to.

        Raises:
            ReadPreferencesError: If the existing preferences file cannot be read or parsed.
        """
        prefs = retrieve_preferences()

        if PreferenceName.DEFAULT_TEMPLATE in names:
            prefs.default_template = None
        if PreferenceName.DEFAULT_STORE_TYPE in names:
            prefs.default_store_type = None

        return write_preferences(prefs)

    def unset_all_preferences(self) -> bool:
        """Delete the preferences file entirely.

        Returns:
            bool: True if a file was deleted, False if there was nothing to delete.
        """
        return fs_utils.delete_file_if_exists(self.preferences_path)

    def resolve_template(
        self,
        template: str | None,
        provider: str,
        infrastructure: str,
    ) -> tuple[str, TemplateSource]:
        """Resolve the full template name that <jd init> should use.

        Precedence: the --template argument, then the default-template preference, then the built-in
        default. A --template that already contains ':' is a full name and is taken as-is; a base
        name is composed with the provider and infrastructure arguments, as it always was.

        The name is scoped to an engine rather than absolute: templates are registered per engine, so
        the caller resolves the name WITHIN its own engine. There is one engine today, which is why
        no preference records one; a second engine needs a default-engine preference of its own,
        mirroring the fact that --engine is a separate argument from --template.

        Returns:
            tuple: the full template name, and what decided it. Callers report the template back
                whenever an argument did NOT decide it, since a template resolved from a preference
                or from the built-in default is one the user never typed.

        Raises:
            InvalidTemplateNameError: If an explicit or preferred full name is malformed.
            ReadPreferencesError: If the preferences file cannot be read or parsed.
        """
        if template:
            if ":" in template:
                preferences.validate_template_name(template)
                return template.lower(), TemplateSource.ARGUMENT
            composed = f"{provider.lower()}:{infrastructure.lower()}:{template.lower()}"
            return composed, TemplateSource.ARGUMENT

        prefs = retrieve_preferences()
        if prefs.default_template:
            preferences.validate_template_name(prefs.default_template)
            return prefs.default_template.lower(), TemplateSource.PREFERENCES

        return constants.DEFAULT_TEMPLATE, TemplateSource.BUILT_IN

    def resolve_store_type(self, store_type: StoreType | None) -> StoreType | None:
        """Return the explicit store type when given, else the preferred one, else None.

        Raises:
            InvalidStoreTypeError: If the preferred store type is not recognized.
            ReadPreferencesError: If the preferences file cannot be read or parsed.
        """
        if store_type is not None:
            return store_type

        return retrieve_preferences().get_store_type()

    def _warn_if_template_not_installed(self, template_name: str) -> None:
        """Warn when no installed package provides the template, without refusing to record it.

        Setting a preference for a template package the user has yet to install is legitimate --
        resolving the template is where a missing one becomes an error, and it names what is available.

        Looks across the templates of EVERY engine, deliberately: the preference records no engine, so
        scoping to one would warn about a name that some other engine does provide. Erring towards
        staying quiet suits a warning that never blocks the write.
        """
        installed = [name for templates in template_utils.TEMPLATES.values() for name in templates]
        if template_name in installed:
            return

        self.display_manager.warning(f"No installed template matches '{template_name}', recording it anyway.")
        if installed:
            self.display_manager.hint(f"Installed templates: {', '.join(sorted(installed))}")


def get_preferences_dir() -> Path:
    """Return the directory holding the preferences file."""
    return Path.home() / constants.JD_HOME_DIR


def get_preferences_path() -> Path:
    """Return the path of the preferences file, whether or not it exists."""
    return get_preferences_dir() / constants.PREFERENCES_FILENAME


def retrieve_preferences() -> preferences.JupyterDeployPreferences:
    """Read the preferences file and return it parsed, or empty preferences if there is no file.

    Raises:
        ReadPreferencesError: If the file exists but cannot be read or parsed.
    """
    preferences_path = get_preferences_path()
    if not fs_utils.file_exists(preferences_path):
        return preferences.JupyterDeployPreferencesV1()

    try:
        content: Any = yaml.safe_load(fs_utils.read_short_file(preferences_path))
    except (OSError, RuntimeError, yaml.YAMLError) as e:
        raise ReadPreferencesError(str(preferences_path), str(e)) from None

    # An empty file parses to None; treat it the same as no file at all.
    if content is None:
        return preferences.JupyterDeployPreferencesV1()

    if not isinstance(content, dict):
        raise ReadPreferencesError(str(preferences_path), "expected a mapping of preference names to values")

    # The file is hand-editable, so a preference can carry the wrong type. Every field is optional,
    # which keeps a file written by an older version valid; what lands here is a bad value.
    try:
        return preferences.JupyterDeployPreferencesV1(**content)
    except ValidationError as e:
        errors = "; ".join([f"{err['loc']}: {err['msg']}" for err in e.errors()])
        raise ReadPreferencesError(str(preferences_path), errors) from None


def write_preferences(prefs: preferences.JupyterDeployPreferences) -> Path:
    """Write the preferences file with the given values. Creates the directory if needed.

    Returns:
        Path: the path written to.
    """
    preferences_dir = get_preferences_dir()
    preferences_dir.mkdir(parents=True, exist_ok=True)

    preferences_path = preferences_dir / constants.PREFERENCES_FILENAME
    content = prefs.model_dump(by_alias=True, exclude_none=True)

    fs_utils.write_yaml_file_with_comments(
        preferences_path,
        content,
        key_order=preferences.PREFERENCES_V1_KEYS_ORDER,
    )
    return preferences_path
