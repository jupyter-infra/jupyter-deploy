# `down`

Destroy the cloud resources defined in the project configuration.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

No-op if you have not already created the infrastructure with <jd up>, or if you
already ran <jd down>.

**Usage**:

```console
$ jd down [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project to bring down.
* `-y, --answer-yes`: Destroy resources without confirmation prompt.
* `-v, --verbose`: Show full output without progress bar.
* `--help`: Show this message and exit.
