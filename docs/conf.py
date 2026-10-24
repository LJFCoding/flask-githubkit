project = "flask-githubkit"
author = "LJFCoding"
release = "0.1.3"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
]

root_doc = "index"
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
