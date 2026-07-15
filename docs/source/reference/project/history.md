# `history`

View and manage logs emitted by the infrastructure-as-code engine.

**Usage**:

```console
$ jd history [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `list`: Show the list of execution logs available...
* `show`: Display the content of a specific command...
* `clear`: Delete execution logs for a specific...

## `history list`

Show the list of execution logs available in the project for a specific command.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd history list [OPTIONS] {command}:<config|up|down>
```

**Arguments**:

* `command:<config|up|down>`: Command that generated the logs.  [required]

**Options**:

* `-p, --path <path>`: Directory of the project.
* `-n <int range>`: Maximum number of logs to display  [default: 20; x>=1]
* `--text`: Output plain text without Rich markup.
* `--help`: Show this message and exit.

## `history show`

Display the content of a specific command execution log.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

By default, displays the content of the entire log.

Use --lines/-l to show only the last N lines.

Use --skip/-s to offset the first line returned (from the end of the content).

**Usage**:

```console
$ jd history show [OPTIONS] [command]:<config|up|down>
```

**Arguments**:

* `command:<config|up|down>`: Command that generated the log. If omitted, show latest log from any command.

**Options**:

* `-p, --path <path>`: Directory of the project.
* `-n <int range>`: Show Nth most recent log for the command.  [default: 1; x>=1]
* `-l, --lines <int range>`: Show only last L lines of the log content.  [x>=1]
* `-s, --skip <int range>`: Skip S lines from end (for pagination).  [default: 0; x>=0]
* `--help`: Show this message and exit.

## `history clear`

Delete execution logs for a specific command, keeping only the most recent N logs.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd history clear [OPTIONS] {command}:<config|up|down>
```

**Arguments**:

* `command:<config|up|down>`: Command type to clear: config, up, or down.  [required]

**Options**:

* `-p, --path <path>`: Directory of the project.
* `-k, --keep <int range>`: Number of most recent logs to retain.  [default: 20; x>=1]
* `--help`: Show this message and exit.
