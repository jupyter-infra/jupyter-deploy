# `init`

Initialize a project from a template in the target directory.

Template will be selected based on the provided parameters - the matching
template package must have already been installed.

You must specify a project path which must be a directory. If such a directory is not empty,
the command will fail unless you passed --overwrite or -o. --overwrite will prompt
for confirmation before deleting existing content.

Alternatively, use --restore-project to restore a project from a remote store.

**Usage**:

```console
$ jd init [OPTIONS] [PATH]
```

**Arguments**:

* `[PATH]`: Path to the directory where the project files will be created. Pass '.' to use your current working directory.

**Options**:

* `-E, --engine [terraform]`: Infrastructure as code software to manage your resources.  [default: terraform]
* `-P, --provider [aws]`: Cloud provider where your resources will be provisioned.  [default: aws]
* `-I, --infrastructure [ec2|eks|iam]`: Infrastructure service that your cloud provider will use to provision your resources.  [default: ec2]
* `-T, --template TEXT`: Base name of the infrastrucuture as code template (e.g., base)  [default: base]
* `-o, --overwrite`: Overwrite the project directory instead of failing when the directory is not empty.
* `--restore-project TEXT`: Restore a project from the remote store instead of creating a new one. Pass the project ID to restore.
* `--store-type [s3-only|s3-ddb]`: Type of the remote store (required with --restore-project).
* `--store-id TEXT`: ID of a specific store to restore from.
* `--help`: Show this message and exit.
