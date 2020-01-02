# -*- coding: utf-8 -*-

"""
mediamantis.importer
~~~~~~~~~~~~~~~~~~~
Imports media files from a variety of sources

"""

import datetime
import logging
import os
import shutil
import threading

from pycons3rt3.logify import Logify

from .archiver import Archiver
from .directories import Directories
from .exceptions import ArchiverError, ImporterError
from .mantistypes import ImportStatus, MediaFileType
from .mediafile import MediaFile
from .settings import extensions


mod_logger = Logify.get_name() + '.importer'


class Importer(threading.Thread):

    def __init__(self, import_dir, media_import_root=None):
        threading.Thread.__init__(self)
        self.cls_logger = mod_logger + '.Importer'
        self.import_dir = import_dir
        self.media_import_root = media_import_root
        self.dirs = Directories(media_root=media_import_root)
        self.extensions = extensions
        self.arch = Archiver(dir_to_archive=import_dir)
        self.file_import_count = 0
        self.picture_import_count = 0
        self.movie_import_count = 0
        self.audio_import_count = 0
        self.already_imported_count = 0
        self.not_imported_count = 0

    def import_media_file(self, media_file):
        """Imports a media file

        return: none
        raises: ImporterError
        """
        log = logging.getLogger(self.cls_logger + '.import_media_file')

        if not isinstance(media_file, MediaFile):
            raise ImporterError('Expected media_file type MediaFile, found: {t}'.format(
                t=media_file.__class__.__name__))

        # Ensure the file exists
        if not os.path.isfile(media_file.file_path):
            raise ImporterError('File not found to import: {f}'.format(f=media_file.file_path))

        log.debug('Checking file for import: {f}'.format(f=media_file.file_path))

        # Check the import status

        # Determine the destination import directory based on file type
        if media_file.file_type == MediaFileType.PICTURE:
            import_root_path = self.dirs.picture_dir
        elif media_file.file_type == MediaFileType.MOVIE:
            import_root_path = self.dirs.movie_dir
        elif media_file.file_type == MediaFileType.AUDIO:
            import_root_path = self.dirs.music_dir
        else:
            log.warning('File {f} with type {t} will not be imported'.format(
                f=media_file.file_name, t=media_file.file_type))
            media_file.import_status = ImportStatus.DO_NOT_IMPORT
            self.not_imported_count += 1
            return

        # Ensure the archive files directory exists, and create it if not found
        if not os.path.exists(import_root_path):
            log.info('Creating import root path: {d}'.format(d=import_root_path))
            os.makedirs(import_root_path, exist_ok=True)

        # Determine the import file name prefix
        prefix = datetime.datetime.fromtimestamp(media_file.creation_time).strftime('%Y-%m-%d_%H%M%S_')
        log.debug('Determined import filename prefix: {p}'.format(p=prefix))
        if media_file.file_name.startswith(prefix):
            target_filename = str(media_file.file_name)
        else:
            target_filename = prefix + media_file.file_name
        log.debug('Using target filename: {n}'.format(n=target_filename))

        # Determine the year and month and create directories if they do not exist
        year = datetime.datetime.fromtimestamp(media_file.creation_time).strftime('%Y')
        month = datetime.datetime.fromtimestamp(media_file.creation_time).strftime('%m')
        year_dir = os.path.join(import_root_path, year)
        month_dir = os.path.join(year_dir, '{y}-{m}'.format(y=year, m=month))
        target_path = os.path.join(month_dir, target_filename)

        if os.path.isfile(target_path):
            log.info('Found media file already imported: {f}'.format(f=target_path))
            media_file.import_status = ImportStatus.ALREADY_EXISTS
            self.already_imported_count += 1
            return

        if not os.path.exists(year_dir):
            log.info('Creating year directory: {d}'.format(d=year_dir))
            os.makedirs(year_dir, exist_ok=True)

        if not os.path.exists(month_dir):
            log.info('Creating month directory: {d}'.format(d=month_dir))
            os.makedirs(month_dir, exist_ok=True)

        # Import the media file to the month directory
        log.info('Importing file {f} to: {t}'.format(f=media_file.file_path, t=target_path))
        try:
            shutil.copy2(src=media_file.file_path, dst=target_path)
        except Exception as exc:
            raise ArchiverError('Problem importing file [{f}] to: {t}'.format(
                f=media_file.file_path, t=target_path)) from exc
        media_file.import_status = ImportStatus.COMPLETED
        media_file.import_path = target_path

        # Update counts
        if media_file.file_type == MediaFileType.PICTURE:
            self.picture_import_count += 1
        elif media_file.file_type == MediaFileType.MOVIE:
            self.movie_import_count += 1
        elif media_file.file_type == MediaFileType.AUDIO:
            self.audio_import_count += 1
        self.file_import_count += 1

    def process_import(self):
        """Process the import of media from a directory

        return: none
        raises: ImporterError
        """
        log = logging.getLogger(self.cls_logger + '.process_import')
        log.info('Scanning directory for import: {d}'.format(d=self.import_dir))
        try:
            self.arch.scan_archive()
        except ArchiverError as exc:
            raise ImporterError('Problem scanning directory for import: {d}'.format(d=self.import_dir)) from exc

        for media_file in self.arch.media_files:
            if media_file.import_status == ImportStatus.COMPLETED:
                continue
            elif media_file.import_status == ImportStatus.ALREADY_EXISTS:
                continue
            elif media_file.import_status == ImportStatus.DO_NOT_IMPORT:
                continue
            if media_file.file_type == MediaFileType.UNKNOWN:
                log.info('Unknown file type will not be imported: {f}'.format(f=media_file.file_name))
                continue
            try:
                self.import_media_file(media_file=media_file)
            except ImporterError as exc:
                raise ImporterError('Problem importing media file: {f}'.format(f=str(media_file))) from exc
        log.info('Completed processing media file imports from directory: {d}'.format(d=self.import_dir))
        log.info('Imported a total of {n} media files'.format(n=str(self.file_import_count)))
        log.info('Imported {n} pictures'.format(n=str(self.picture_import_count)))
        log.info('Imported {n} movies'.format(n=str(self.movie_import_count)))
        log.info('Imported {n} audio files'.format(n=str(self.audio_import_count)))
        log.info('{n} media files already imported'.format(n=str(self.already_imported_count)))
        log.info('{n} files were not imported'.format(n=str(self.not_imported_count)))
