# -*- coding: utf-8 -*-

"""
mediamantis.mantistypes
~~~~~~~~~~~~~~~~~~~
Data types for mediamantis

"""

import enum


class MediaFileType(enum.Enum):
    MOVIE = 1
    PICTURE = 2
    AUDIO = 3
    UNKNOWN = 4


class ArchiveStatus(enum.Enum):
    COMPLETED = 1
    PENDING = 2


class ImportStatus(enum.Enum):
    COMPLETED = 1
    PENDING = 2
    ALREADY_EXISTS = 3
    DO_NOT_IMPORT = 4
