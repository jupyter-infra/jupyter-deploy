# `image`

Manage application images.

**Usage**:

```console
$ jd image [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `list`: List application images for this project.
* `show`: Show details of an application image.
* `tags`: List available tags for an application image.
* `vulnerabilities`: List vulnerabilities for an application...

## `image list`

List application images for this project.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd image list [OPTIONS]
```

**Options**:

* `-p, --path PATH`: Directory of the project.
* `--json`: Output as JSON.
* `--text`: Output as plain names.
* `--help`: Show this message and exit.

## `image show`

Show details of an application image.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd image show [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the image.
* `-p, --path PATH`: Directory of the project.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.

## `image tags`

List available tags for an application image.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd image tags [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the image.
* `-p, --path PATH`: Directory of the project.
* `--json`: Output as JSON.
* `--text`: Output as plain tag names.
* `--help`: Show this message and exit.

## `image vulnerabilities`

List vulnerabilities for an application image.

Shows HIGH and CRITICAL severity vulnerabilities detected by the image scanner.
If --tag is not specified, uses the current deployed tag.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd image vulnerabilities [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the image.
* `--tag TEXT`: Image tag to check.
* `-p, --path PATH`: Directory of the project.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.
