import time

project = "Jupyter Deploy"
copyright = f"2025–{time.localtime().tm_year}, Amazon Web Services"
author = "Amazon Web Services"
html_title = "Jupyter Deploy"

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinx_tabs.tabs",
    "sphinx_copybutton",
]
myst_enable_extensions = ["colon_fence"]

templates_path = ["_templates"]
exclude_patterns = []

html_theme = "shibuya"
html_static_path = ["_static"]

html_css_files = [
    "css/custom.css",
]

html_logo = "_static/img/jupyter_logo.png"

html_theme_options = {
    "accent_color": "orange",
    "github_url": "https://github.com/jupyter-infra/jupyter-deploy",
    "nav_links": [
        {
            "title": "Getting Started",
            "url": "getting-started/index",
        },
        {
            "title": "Templates",
            "url": "templates/index",
        },
        {
            "title": "Contributor Guide",
            "url": "contributor-guide/index",
        },
    ],
}
