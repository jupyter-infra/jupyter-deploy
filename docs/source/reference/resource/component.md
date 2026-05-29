# `component`

Interact with the platform components supporting your apps.

**Usage**:

```console
$ jd component [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `list`: List components declared in the manifest.
* `status`: Check the status of a particular component.
* `show`: Display detailed information about a...
* `logs`: Print the logs of a component.
* `restart`: Restart a persisting component.
* `trigger`: Trigger an ephemeral job from a...

## `component list`

List components declared in the manifest.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd component list [OPTIONS]
```

**Options**:

* `-p, --path PATH`: Directory of the project.
* `--json`: Output as JSON.
* `--text`: Output as comma-separated names.
* `--help`: Show this message and exit.

## `component status`

Check the status of a particular component.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd component status [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the component to check.  [required]
* `-p, --path PATH`: Directory of the project.
* `--help`: Show this message and exit.

## `component show`

Display detailed information about a specific component.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Pass --description to display the component's description only.

**Usage**:

```console
$ jd component show [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the component to show details for.  [required]
* `-p, --path PATH`: Directory of the project.
* `-d, --description`: Show description instead of full details.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.

## `component logs`

Print the logs of a component.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

You can pass additional arguments after '--'.

**Usage**:

```console
$ jd component logs [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the component whose logs to display.  [required]
* `-p, --path PATH`: Directory of the project.
* `--help`: Show this message and exit.

## `component restart`

Restart a persisting component.

Only supported for persisting components.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd component restart [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the component to restart.  [required]
* `-p, --path PATH`: Directory of the project.
* `--help`: Show this message and exit.

## `component trigger`

Trigger an ephemeral job from a job-generating component.

Only supported for job-generating components.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd component trigger [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the CronJob component to trigger.  [required]
* `-p, --path PATH`: Directory of the project.
* `--help`: Show this message and exit.
