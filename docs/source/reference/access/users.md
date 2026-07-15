# `users`

Control access to your app at user level.

**Usage**:

```console
$ jd users [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `add`: Add user(s) to the list authorized to...
* `remove`: Remove user(s) from the list authorized to...
* `set`: Set the list of username(s) authorized to...
* `list`: Show the name(s) of user(s) authorized to...

## `users add`

Add user(s) to the list authorized to access the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd users add [OPTIONS] {users}...
```

**Arguments**:

* `users...`: Name of the users to add to the allowlist.  [required]

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.

## `users remove`

Remove user(s) from the list authorized to access the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd users remove [OPTIONS] {users}...
```

**Arguments**:

* `users...`: Name of the users to remove from the allowlist.  [required]

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.

## `users set`

Set the list of username(s) authorized to access the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd users set [OPTIONS] {users}...
```

**Arguments**:

* `users...`: Names of the users to allowlist.  [required]

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.

## `users list`

Show the name(s) of user(s) authorized to access the app.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd users list [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.
