# -*- coding: utf-8 -*-

"""
mediamantis.exceptions
~~~~~~~~~~~~~~~~~~~
This module contains the set of exceptions.
"""


class ArchiverError(Exception):
    """Problem archiving a file"""


class ImporterError(Exception):
    """Problem importing a file"""


class MantisError(Exception):
    """General error with Media Mantis"""


class ZipError(Exception):
    """Excepting during the zipping or unzipping process"""
