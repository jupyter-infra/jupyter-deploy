# `proxy`

Manage local processes that communicate with your project's host(s).

**Usage**:

```console
$ jd proxy [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `connect-info`: Emit the JSON connection bundle for the...
* `start`: Launch a background local proxy to...
* `open`: Open a browser tab against the local proxy.
* `stop`: Stop the local proxy for this project.
* `status`: Check the status of the local proxy.
* `show`: Display information about the local proxy.

## `proxy connect-info`

Emit the JSON connection bundle for the local proxy to consume.

Resolves the endpoint, reads the cert to pin, and mints a short-lived token. The proxy
calls this command before each credential expiry so the bundle stays fresh.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd proxy connect-info [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project to emit the connect-info bundle for.
* `--help`: Show this message and exit.

## `proxy start`

Launch a background local proxy to communicate with the project's remote host(s).

The proxy process keeps running after the command returns. Stop it with
<jd proxy stop>. Exits non-zero if a proxy is already running for this project
(stop it first, or open a tab against it) — it never replaces a running proxy.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Open a browser tab against it with <jd proxy open>.

Requires the proxy library to be installed in your Python environment.

**Usage**:

```console
$ jd proxy start [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project to launch the proxy for.
* `--help`: Show this message and exit.

## `proxy open`

Open a browser tab against the local proxy.

A proxy process must be running for this project; run <jd proxy start> first.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Requires the proxy library to be installed in your Python environment.

**Usage**:

```console
$ jd proxy open [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project to open.
* `--help`: Show this message and exit.

## `proxy stop`

Stop the local proxy for this project.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Requires the proxy library to be installed in your Python environment.

**Usage**:

```console
$ jd proxy stop [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project whose proxy to stop.
* `--help`: Show this message and exit.

## `proxy status`

Check the status of the local proxy.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Requires the proxy library to be installed in your Python environment.

**Usage**:

```console
$ jd proxy status [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project whose proxy to check.
* `--help`: Show this message and exit.

## `proxy show`

Display information about the local proxy.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Requires the proxy library to be installed in your Python environment.

**Usage**:

```console
$ jd proxy show [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project whose proxy to show details for.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.
