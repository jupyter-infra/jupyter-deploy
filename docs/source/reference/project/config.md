# `config`

Verify the system configuration, prompt inputs and prepare for deployment.

Run from a project directory created with <jd init>.

The config command will remember your variable values so that you do not need to
specify them again next time you run <jd config>.

You can reset these recorded values with --reset or -r.

You can specify where to save the planned change with --output-file or -f.

**Usage**:

```console
$ jd config [OPTIONS]
```

**Options**:

* `-d, --defaults TEXT`: Name of the preset defaults to use: 'all', 'none' or template-specific preset names.  [default: all]
* `-r, --reset`: Delete previously recorded variables and secrets.
* `--skip-verify`: Avoid verifying that the project dependencies are configured.
* `-f, --output-filename TEXT`: Name of the file to store the configuration to.
* `--store-type [s3-only|s3-ddb]`: Override the project store type.
* `--store-id TEXT`: Pin a specific store.
* `--restore-secrets`: Restore all masked secret variable value.
* `--restore-secret TEXT`: Restore the specific variable secret value.
* `--reset-store-id`: Clear the pinned store ID and rediscover the store.
* `--verbose`: Show full output without progress bar.
* `--help`: Show this message and exit.
