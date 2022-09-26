# -*- coding: utf-8 -*-

"""
mediamantis.mediafile
~~~~~~~~~~~~~~~~~~~
Data type for media files

"""

import datetime
import os

from .mantistypes import ArchiveStatus, ImportStatus, MediaFileType


class MediaFile(object):

    def __init__(self, file_path, creation_time, size_bytes, file_type):
        self.file_path = file_path
        self.file_name = file_path.split(os.sep)[-1]
        self.creation_time = creation_time
        self.creation_timestamp = datetime.datetime.fromtimestamp(creation_time).strftime('%Y%m%d-%H%M%S')
        self.size_bytes = size_bytes
        self.file_type = file_type
        self.archive_status = ArchiveStatus.PENDING
        self.import_status = ImportStatus.PENDING
        self.destination_path = None
        self.import_path = None

    def __str__(self):
        return self.file_name

    def archive_status_to_str(self):
        return self.archive_status.name

    def import_status_to_str(self):
        return self.import_status.name

    def file_type_to_str(self):
        return self.file_type.name

    def to_record(self):
        return {
            'file_path': self.file_path,
            'file_name': self.file_name,
            'creation_time': self.creation_timestamp,
            'size_bytes': self.size_bytes,
            'file_type': self.file_type_to_str(),
            'archive_status': self.archive_status_to_str(),
            'import_status': self.import_status_to_str(),
            'destination_path': self.destination_path if self.destination_path else 'None',
            'import_path': self.import_path if self.import_path else 'None'
        }
