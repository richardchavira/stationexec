Generating the Documentation
============================

Install sphinx
--------------
::

    sudo apt/yum install python-sphinx
    pip install Sphinx
    pip install sphinx-rtd-theme
    pip install sphinxcontrib-httpdomain

Generate Docs
-------------
Navigate to 'docs' folder in source and run
::

    make html

to generate a new version of the HTML docs. Launch 'index.html' from docs/build/html

For PDF, make sure LaTeX is installed (potentially painful and error prone - consider yourself warned) and generate html first.
::

    make latexpdf

Find 'StationExecutive.pdf' in docs/build/latex

Install LaTeX for PDF
---------------------
*Linux Only* (Tested on Ubuntu and CENTOS 7)
Instructions derived from those at the `TeX Users Group <https://www.tug.org/texlive/quickinstall.html>`_
Download the ~3GB 'texlive.iso' from the `CTAN Mirror <http://ftp.math.purdue.edu/mirrors/ctan.org/systems/texlive/Images/>`_

Mount the iso, then run 'sudo ./install-tl' from inside the mounted drive, enter option 'i' when prompted, then wait
for completion. Add LaTeX to path - update texlive path, date, and install for your machine as necessary:

Ubuntu
^^^^^^
Append the following to ~/.bashrc

::

    PATH=/usr/local/texlive/2018/bin/x86_64-linux:$PATH; export PATH

Fedora
^^^^^^
Create 'texlive.sh' in /etc/profile.d and add the following:

::

    PATH=/usr/local/texlive/2018/bin/x86_64-linux:$PATH
    export PATH

CENTOS - execute as root
^^^^^^^^^^^^^^^^^^^^^^^^
::

    echo 'pathmunge /usr/local/texlive/2018/bin/x86_64-linux/' /usr/profile.d/texlive.sh
    chmod +x /usr/profile.d/texlive/sh
    . /etc/profile
