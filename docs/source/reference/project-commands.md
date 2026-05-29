# Project Commands

Project commands manage the full lifecycle of a deployment project: initialization, configuration, provisioning, teardown, and inspection.

| Command | Description |
|---------|-------------|
| [init](project/init) | Initialize a project from a template in the target directory. |
| [config](project/config) | Verify the system configuration, prompt inputs and prepare for deployment. |
| [up](project/up) | Apply the project configuration to the cloud resources. |
| [down](project/down) | Destroy the cloud resources defined in the project configuration. |
| [open](project/open) | Open the app in your web browser. |
| [show](project/show) | Display information about the project. |
| [health](project/health) | Check the health of the full deployment stack. |
| [history](project/history) | View and manage logs emitted by the infrastructure-as-code engine. |

```{toctree}
:hidden:

project/init
project/config
project/up
project/down
project/open
project/show
project/health
project/history
```
