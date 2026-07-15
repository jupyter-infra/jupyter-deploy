# `projects`

Manage projects saved in remote stores.

**Usage**:

```console
$ jd projects [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `list`: List projects in a specific remote store.
* `show`: Show details of a specific project in a...
* `delete`: Delete all the project data from a remote...

## `projects list`

List projects in a specific remote store.

**Usage**:

```console
$ jd projects list [OPTIONS]
```

**Options**:

* `--store-type <s3-only|s3-ddb>`: Type of the remote store.  [required]
* `--store-id <str>`: ID of a specific store to query.
* `-n <int range>`: Maximum number of projects to display.  [default: 20; x>=1]
* `-s, --skip <int range>`: Number of projects to skip.  [default: 0; x>=0]
* `--text`: Output project IDs only, one per line.
* `--help`: Show this message and exit.

## `projects show`

Show details of a specific project in a remote store.

**Usage**:

```console
$ jd projects show [OPTIONS] {project_id}
```

**Arguments**:

* `project_id`: ID of the project to show.  [required]

**Options**:

* `--store-type <s3-only|s3-ddb>`: Type of the remote store.  [required]
* `--store-id <str>`: ID of a specific store to query.
* `--text`: Output plain text without Rich markup.
* `--help`: Show this message and exit.

## `projects delete`

Delete all the project data from a remote store.

**Usage**:

```console
$ jd projects delete [OPTIONS] {project_id}
```

**Arguments**:

* `project_id`: ID of the project to delete.  [required]

**Options**:

* `--store-type <s3-only|s3-ddb>`: Type of the remote store.  [required]
* `--store-id <str>`: ID of a specific store to query.
* `-y, --answer-yes`: Skip confirmation prompt.
* `--help`: Show this message and exit.
