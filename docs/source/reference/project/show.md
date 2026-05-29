# `show`

Display information about the project.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

If the project is up, shows the values of the output as defined in
the infrastructure-as-code project.

Pass --variable <variable-name> to display the value of a single variable, or
-v <variable-name> --description to display its description.

Pass --output <output-name> to display the value of a single output, or
-o <output-name> --description to display its description.

Pass --variables --list or --outputs --list to display the list of variable or output names.

**Usage**:

```console
$ jd show [OPTIONS]
```

**Options**:

* `-p, --path PATH`: Directory of the project to show information.
* `--info`: Display core project and template information.
* `--outputs`: Display outputs information.
* `--variables`: Display variables information.
* `-v, --variable TEXT`: Get the value of a specific variable by name.
* `-o, --output TEXT`: Get the value of a specific output by name.
* `--template-name`: Display the template name.
* `--template-version`: Display the template version.
* `--template-engine`: Display the template engine.
* `--store-type`: Display the type of store for this project.
* `--store-id`: Display the ID of the store for this project.
* `--project-id`: Display the full project ID.
* `-d, --description`: Show description instead of value (with --variable or --output).
* `--list`: List names only (with --variables or --outputs).
* `--reveal`: Reveal the actual value of a sensitive variable.
* `--text`: Output plain text without Rich markup.
* `--help`: Show this message and exit.
