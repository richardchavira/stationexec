# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import os
import sys

sys.path.insert(0, os.path.abspath('..'))

project = u'Station Executive'
copyright = u'2019, Oculus Purple Automation'
author = u'Oculus Purple Automation'

version = {}
# Read in version from stationexec/version.py
with open("../stationexec/version.py") as v:
    exec(v.read(), version)
version = release = version['version']

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinxcontrib.httpdomain',
]

# Add mappings
intersphinx_mapping = {
    'urllib3': ('https://urllib3.readthedocs.io/en/latest', None),
    'python': ('https://docs.python.org/3', None),
    'simplejson': ('https://simplejson.readthedocs.io/en/latest', None),
}

primary_domain = 'py'
default_role = 'py:obj'

autodoc_member_order = "bysource"
autoclass_content = "both"
autodoc_inherit_docstrings = False

# Without this line sphinx includes a copy of object.__init__'s docstring
# on any class that doesn't define __init__.
# https://bitbucket.org/birkenfeld/sphinx/issue/1337/autoclass_content-both-uses-object__init__
autodoc_docstring_signature = False

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'

language = None
exclude_patterns = []

pygments_style = 'sphinx'

latex_elements = {
    'maxlistdepth': '7',
}

latex_documents = [
    (master_doc, 'StationExecutive.tex', u'Station Executive Documentation',
     u'Oculus Purple Automation', 'manual', False),
]

on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

# On RTD we can't import sphinx_rtd_theme, but it will be applied by
# default anyway.  This block will use the same theme when building locally
# as on RTD.
if not on_rtd:
    import sphinx_rtd_theme
    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
