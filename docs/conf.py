import os

project = "flask-githubkit"
author = "LJFCoding"
release = "0.1.6"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
]

# Read the Docs sets this to the default version's URL, giving every page
# a canonical link so latest/ and stable/ are not indexed as duplicates.
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")

root_doc = "index"
myst_heading_anchors = 3
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
