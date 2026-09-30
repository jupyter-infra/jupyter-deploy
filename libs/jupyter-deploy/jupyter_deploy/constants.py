MANIFEST_FILENAME = "manifest.yaml"
VARIABLES_FILENAME = "variables.yaml"
VARIABLES_DEFAULTS_FILENAME = "variables-defaults.yaml"
HISTORY_DIR = ".jd-history"
JD_DIR = ".jd"
JD_HOME_DIR = ".jupyter-deploy"
PREFERENCES_FILENAME = "preferences.yaml"
PROXY_RUNTIME_DIR = ".jd-proxy"
STORE_CONFIG_FILENAME = "store.yaml"
DELETION_MARKER_FILENAME = "deletion.yaml"
MASKED_SECRET_VALUE = "****"

# Template that `jd init` uses when the caller passed no --template and set no default-template
# preference.
DEFAULT_TEMPLATE = "aws:ec2:jupyterlab"

# The value DEFAULT_TEMPLATE replaced, and the release that replaced it, both named in the notice that
# `jd init` prints on the fallthrough so that users who relied on the old default can pin it.
# TRANSITIONAL: at 1.0, retire these along with the one statement in `_notify_default_template` that
# prints them, keeping the rest of the notice -- telling a user which template was picked for them stays
# useful, naming the one it replaced does not.
PREVIOUS_DEFAULT_TEMPLATE = "aws:ec2:base"
PREVIOUS_DEFAULT_TEMPLATE_CHANGED_IN = "v0.8.0"
SECRET_REVEAL_COMMAND = "secret.reveal"
SECRET_REVEAL_RESULT_NAME = "secret-value"
SECRET_REVEAL_CLI_PARAM = "secret-id"

# Exit code signalling "this failed, but retrying may succeed" (sysexits EX_TEMPFAIL). Used by
# `jd proxy connect-info`, whose caller is the client proxy: it keeps serving on the last-good
# credential when the token command exits with this code, and treats any other non-zero exit as
# permanent. Must stay in sync with the proxy's own RETRYABLE_EXIT_CODE.
RETRYABLE_EXIT_CODE = 75
