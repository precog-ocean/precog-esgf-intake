"""Sphinx configuration for precog-esgf-intake."""

import datetime
from importlib.metadata import PackageNotFoundError, version

project = "precog-esgf-intake"
author = "Leonardo Bertini"
copyright = f"{datetime.date.today().year}, {author}"

try:
    release = version("precog-esgf-intake")
except PackageNotFoundError:
    release = "0.0.0"

version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
    "myst_nb",
    "sphinx_design",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_title = "precog-esgf-intake"
html_static_path = ["_static"]

myst_enable_extensions = [
    "attrs_block",
    "attrs_inline",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_image",
    "linkify",
    "substitution",
]

myst_heading_anchors = 3

autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}
autosummary_generate = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "xarray": ("https://docs.xarray.dev/en/stable/", None),
    "intake": ("https://intake.readthedocs.io/en/latest/", None),
    "intake-esgf": ("https://intake-esgf.readthedocs.io/en/latest/", None),
}

nitpicky = False
