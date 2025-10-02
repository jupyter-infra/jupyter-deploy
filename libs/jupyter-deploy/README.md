# JupyterDeploy

Jupyter deploy is an open-source command line interface tool (CLI) to deploy and manage
JupyterLab applications to remote compute instances provided by a Cloud provider.
Once deployed, you can access your application directly from your webbrowser,
and share its dedicated URL with collaborators.

## Templates
The `jupyter-deploy` CLI interacts with templates: infrastructure-as-code packages
that you can use to create your own project and deploy resources in your own cloud provider account.

Templates are nominally python packages distributed on `pypi`. You can install and manage templates in your virtual
environment with `pip` or `uv`. The CLI automatically finds the templates installed in your environment.

The CLI ships with a default template: [jupyter-deploy-tf-aws-ec2-base](https://pypi.org/project/jupyter-deploy-tf-aws-ec2-base/).
It which uses:
- `terraform` as infrastructure-as-code engine
- `aws` as cloud provider
- `ec2` as compute
- `github` as oauth provider

## Installation
### Using pip

First, consider creating or activating a virtual environment.

```bash
pip install jupyter-deploy
```

## The CLI

### Entry points
From a terminal, run:

```bash
jupyter-deploy --help

# or use the alias
jd --help

# or use the jupyter CLI
jupyter deploy --help
```


### Start a project
First create a new project directory:
```bash
mkdir my-jupyter-deployment
cd my-jupyter-deployment
```

In the rest of this page, we will use the default template.

Run the `init` command:
```bash
jupyter-deploy init .

# select another template that you installed in your virtual environment thanks to the init flags
jupyter-deploy init --help
```

### Configure your project
There are two ways to configure your project:

---
**File based:**
Edit the `variables.yaml` file:
- add required variable values in the `required` and `required_sensitive` section
- optionally override default values in the `overrides` section 

Then run:
```bash
jupyter-deploy config
```

---
**Interactive experience:**
Alternatively, fill in the variable values from your terminal with:
```bash
jupyter-deploy config

# optionally save sensitive values
jupyter-deploy config -s

# Update a variable value afterwards (variable names depends on the template you use).
jupyter-deploy config --instance-type t3.small

# Discover the variables available for this template
jupyter-deploy config --help
```


### Deploy your project
The next step is to actually create your infrastructure
```bash
jupyter-deploy up
```

### Access your application
Once the project was successfully deployed, open your application in your webbrowser with:

```bash
jupyter-deploy open
```

You will be prompted to authenticate.
You can share this URL with collaborators, they will prompted to authenticate on their own webbrowser.

### Turn on and off your compute instance
The default template supports turning off your instance to reduce your cloud bill.

```bash
# stop an instance
jupyter-deploy host stop

# restart it with
jupyter-deploy host start

# and possibly
jupyter-deploy server start
```


### Winddown your resources
To delete all the resources, run:
```bash
jupyter-deploy down
```

## License

The `jupyter-deploy` CLI is licensed under the [MIT License](LICENSE).