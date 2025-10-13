# Jupyter Deploy

Jupyter deploy is an open-source command line interface tool (CLI) to deploy and manage
JupyterLab applications to remote compute instances provided by a Cloud provider.
Once deployed, you can access your application directly from your web browser,
and share its dedicated URL with collaborators. Collaborators may then work together
in real time on the same JupyterLab application.

## Templates
The `jupyter-deploy` CLI interacts with templates: infrastructure-as-code packages
that you can use to create your own project and deploy resources in your own cloud provider account.

Templates are nominally python packages distributed on `PyPI`. You can install and manage templates in your virtual
environment with `pip` or `uv`. The CLI automatically finds the templates installed in your Python environment.

The CLI ships with a default template: [jupyter-deploy-tf-aws-ec2-base](https://pypi.org/project/jupyter-deploy-tf-aws-ec2-base/).
Refer to `jupyter-deploy-tf-aws-ec2-base` on PyPI for instructions on setting up the AWS infrastructure needed for your deployment.

## Installation

Consider creating or activating a virtual environment.

### Install with pip

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

```bash
# Get started with the default template
jupyter-deploy init .

# Or use the init flags to select another template that you installed in your virtual environment
jupyter-deploy init --help

# For example, the AWS EC2 base template
jupyter-deploy init -E terraform -P aws -I ec2 -T base . 
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
# Discover the variables available for your specific template
jupyter-deploy config --help

# Run the interactive configuration and set the variables values as prompted
jupyter-deploy config

# Optionally save sensitive values to your project files
# Sensitive values are passwords, secret keys or API tokens that your applications
# need to access at runtime.
jupyter-deploy config -s

# Update a variable value afterwards (variable names depends on the template you use).
jupyter-deploy config --instance-type t3.small
```

### Deploy your project
The next step is to actually create your infrastructure
```bash
jupyter-deploy up
```

### Access your application
Once the project was successfully deployed, open your application in your web browser with:

```bash
jupyter-deploy open
```

You will be prompted to authenticate.
You can share this URL with collaborators, they will prompted to authenticate on their own web browser.

### Turn on and off your compute instance
The default template supports temporarily turning off your instance to reduce your cloud bill.

```bash
# Retrieve the current status of your compute instance
jupyter-deploy host status

# Stop an instance
jupyter-deploy host stop

# Restart it
jupyter-deploy host start

# You may also need to start the containers that run your application
jupyter-deploy server start
```

### Winddown your resources
To delete all the resources, run:

```bash
jupyter-deploy down
```

## License

The `jupyter-deploy` CLI is licensed under the [MIT License](LICENSE).