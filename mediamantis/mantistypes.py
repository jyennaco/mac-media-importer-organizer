# -*- coding: utf-8 -*-

"""
mediamantis.mantistypes
~~~~~~~~~~~~~~~~~~~
Data types for mediamantis

"""

import enum
import os


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
    UNIMPORTED = 5


def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def get_slack_webhook(dirs):
    if not os.path.isfile(dirs.slack_webhook_file):
        return
    with open(dirs.slack_webhook_file, 'r') as f:
        contents = f.read()
    return contents.strip()
