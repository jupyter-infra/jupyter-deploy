# `preferences`

Personalize the CLI.

**Usage**:

```console
$ jd preferences [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `show`: Display the current preferences.
* `set`: Record one or more preferences.
* `unset`: Clear one or more preferences, reverting...

## `preferences show`

Display the current preferences.

**Usage**:

```console
$ jd preferences show [OPTIONS]
```

**Options**:

* `--json`: Output as JSON.
* `--help`: Show this message and exit.

## `preferences set`

Record one or more preferences.

**Usage**:

```console
$ jd preferences set [OPTIONS]
```

**Options**:

* `--default-template <str>`: Template that <jd init> creates a project from when you pass no --template <template-name>. Pass a full name such as <aws:ec2:jupyterlab>.
* `--default-store-type <s3-only|s3-ddb>`: Store type that commands use when you pass no --store-type <store-type>. Does not change the store of a project you already configured.
* `--help`: Show this message and exit.

## `preferences unset`

Clear one or more preferences, reverting to the built-in defaults.

Pass --all to clear every preference at once.

**Usage**:

```console
$ jd preferences unset [OPTIONS]
```

**Options**:

* `--default-template`: Clear the preferred template.
* `--default-store-type`: Clear the preferred store type.
* `--all`: Clear every preference and delete the preferences file.
* `--help`: Show this message and exit.
