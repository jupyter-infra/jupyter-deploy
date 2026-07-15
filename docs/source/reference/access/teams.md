# `teams`

Control access to your app at team level.

**Usage**:

```console
$ jd teams [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `add`: Add team(s) to the list authorized to...
* `remove`: Remove team(s) from the list authorized to...
* `set`: Set the list of team(s) authorized to...
* `list`: Show the name(s) of the team(s) authorized...

## `teams add`

Add team(s) to the list authorized to access the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd teams add [OPTIONS] {teams}...
```

**Arguments**:

* `teams...`: Names of the teams to add to the allowlist.  [required]

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.

## `teams remove`

Remove team(s) from the list authorized to access the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd teams remove [OPTIONS] {teams}...
```

**Arguments**:

* `teams...`: Names of the teams to remove from the allowlist.  [required]

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.

## `teams set`

Set the list of team(s) authorized to access the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd teams set [OPTIONS] {teams}...
```

**Arguments**:

* `teams...`: Names of the teams to allowlist.  [required]

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.

## `teams list`

Show the name(s) of the team(s) authorized to access the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd teams list [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.
