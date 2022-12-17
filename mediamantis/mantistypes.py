# -*- coding: utf-8 -*-

"""
mediamantis.mantistypes
~~~~~~~~~~~~~~~~~~~
Data types for mediamantis

"""

import enum
import os


class MediaFileType(enum.Enum):
    """ENUM for the media file type"""
    MOVIE = 1
    PICTURE = 2
    AUDIO = 3
    UNKNOWN = 4


class ArchiveStatus(enum.Enum):
    """ENUM for the archive status"""
    COMPLETED = 1
    PENDING = 2


class ImportStatus(enum.Enum):
    """ENUM for import status"""
    COMPLETED = 1
    PENDING = 2
    ALREADY_EXISTS = 3
    DO_NOT_IMPORT = 4
    UNIMPORTED = 5


def chunker(seq, size):
    """Splits a list of threads into chunks

    :param seq: (list) of Threads
    :param size: (int) Maximum simultaneous threads
    :return: (list) Chunk of threads
    :raise: None
    """
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def get_slack_webhook(dirs):
    """Evaluates the local directory structure to find and read the webhook from the slack.txt file

    :param dirs: (directories.Directories)
    :return: (str) Slack webhook URL
    :raises: None
    """
    if not os.path.isfile(dirs.slack_webhook_file):
        return
    with open(dirs.slack_webhook_file, 'r') as f:
        contents = f.read()
    return contents.strip()


def map_import_status(import_status_str):
    """Maps a string to ImportStatus ENUM

    :param import_status_str: (str) Import status
    :return: ImportStatus
    :raises: ValueError
    """
    if import_status_str == 'COMPLETED':
        return ImportStatus.COMPLETED
    elif import_status_str == 'PENDING':
        return ImportStatus.PENDING
    elif import_status_str == 'ALREADY_EXISTS':
        return ImportStatus.ALREADY_EXISTS
    elif import_status_str == 'DO_NOT_IMPORT':
        return ImportStatus.DO_NOT_IMPORT
    elif import_status_str == 'UNIMPORTED':
        return ImportStatus.UNIMPORTED
    else:
        raise ValueError('Unsupported import status: {s}'.format(s=import_status_str))
