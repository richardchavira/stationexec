# Minimal makefile for Sphinx documentation
#

ifndef VERBOSE
MAKEFLAGS += --no-print-directory
endif

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = StationExecutive
SOURCEDIR     = .
BUILDDIR      = build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

clean:
	/bin/rm -rf build

pdf:
	@$(MAKE) html
	@echo "  "
	@$(MAKE) latexpdf
	@echo "  "
	@echo "Please see build/latex/StationExec.pdf"

html2:
	@$(MAKE) html
	xdg-open build/html/index.html
