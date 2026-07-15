# `organization`

Control access to your app at the organization level.

**Usage**:

```console
$ jd organization [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `set`: Allowlist an organization to access the app.
* `unset`: Remove organization-based access from the...
* `get`: Show the name of the organization...

## `organization set`

Allowlist an organization to access the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd organization set [OPTIONS] {organization}
```

**Arguments**:

* `organization`: Name of the organization to allowlist.  [required]

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.

## `organization unset`

Remove organization-based access from the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd organization unset [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.

## `organization get`

Show the name of the organization authorized to access the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd organization get [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.
