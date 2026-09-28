MANIFEST_FILENAME = "manifest.yaml"
VARIABLES_FILENAME = "variables.yaml"
VARIABLES_DEFAULTS_FILENAME = "variables-defaults.yaml"
HISTORY_DIR = ".jd-history"
JD_DIR = ".jd"
PROXY_RUNTIME_DIR = ".jd-proxy"
STORE_CONFIG_FILENAME = "store.yaml"
DELETION_MARKER_FILENAME = "deletion.yaml"
MASKED_SECRET_VALUE = "****"
SECRET_REVEAL_COMMAND = "secret.reveal"
SECRET_REVEAL_RESULT_NAME = "secret-value"
SECRET_REVEAL_CLI_PARAM = "secret-id"

# Exit code signalling "this failed, but retrying may succeed" (sysexits EX_TEMPFAIL). Used by
# `jd proxy connect-info`, whose caller is the client proxy: it keeps serving on the last-good
# credential when the token command exits with this code, and treats any other non-zero exit as
# permanent. Must stay in sync with the proxy's own RETRYABLE_EXIT_CODE.
RETRYABLE_EXIT_CODE = 75
