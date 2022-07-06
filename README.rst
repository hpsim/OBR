========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |github-actions| |requires|
        | |codecov|
    * - package
      - | |version| |wheel| |supported-versions| |supported-implementations|
        | |commits-since|
.. |docs| image:: https://readthedocs.org/projects/obr/badge/?style=flat
    :target: https://obr.readthedocs.io/
    :alt: Documentation Status

.. |github-actions| image:: https://github.com/hpsim/obr/actions/workflows/github-actions.yml/badge.svg
    :alt: GitHub Actions Build Status
    :target: https://github.com/hpsim/obr/actions

.. |requires| image:: https://requires.io/github/hpsim/obr/requirements.svg?branch=main
    :alt: Requirements Status
    :target: https://requires.io/github/hpsim/obr/requirements/?branch=main

.. |codecov| image:: https://codecov.io/gh/hpsim/obr/branch/main/graphs/badge.svg?branch=main
    :alt: Coverage Status
    :target: https://codecov.io/github/hpsim/obr

.. |version| image:: https://img.shields.io/pypi/v/obr.svg
    :alt: PyPI Package latest release
    :target: https://pypi.org/project/obr

.. |wheel| image:: https://img.shields.io/pypi/wheel/obr.svg
    :alt: PyPI Wheel
    :target: https://pypi.org/project/obr

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/obr.svg
    :alt: Supported versions
    :target: https://pypi.org/project/obr

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/obr.svg
    :alt: Supported implementations
    :target: https://pypi.org/project/obr

.. |commits-since| image:: https://img.shields.io/github/commits-since/hpsim/obr/v0.0.0.svg
    :alt: Commits since latest release
    :target: https://github.com/hpsim/obr/compare/v0.0.0...main



.. end-badges

A tool to create and run OpenFOAM parameter studies

* Free software: BSD 2-Clause License

Installation
============

::

    pip install obr

You can also install the in-development version with::

    pip install https://github.com/hpsim/obr/archive/main.zip


Documentation
=============


https://obr.readthedocs.io/


Development
===========

To run all the tests run::

    tox

Note, to combine the coverage data from all the tox environments run:

.. list-table::
    :widths: 10 90
    :stub-columns: 1

    - - Windows
      - ::

            set PYTEST_ADDOPTS=--cov-append
            tox

    - - Other
      - ::

            PYTEST_ADDOPTS=--cov-append tox
