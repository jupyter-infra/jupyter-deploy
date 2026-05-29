# `up`

Apply the project configuration to the cloud resources.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>. Optionally, you can also pass a --config-file
argument.

Call <jd config> first to set the input variables and
verify the configuration.

**Usage**:

```console
$ jd up [OPTIONS]
```

**Options**:

* `-p, --path PATH`: Directory of the project to bring up.
* `-f, --config-filename TEXT`: Name of a file in the project directory containing the execution configuration.
* `-y, --answer-yes`: Apply changes without confirmation prompt.
* `-v, --verbose`: Show full output without progress bar.
* `--help`: Show this message and exit.
