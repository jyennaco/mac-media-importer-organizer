# -*- coding: utf-8 -*-

"""
mediamantis.importer
~~~~~~~~~~~~~~~~~~~
Imports media files from a variety of sources

"""

import datetime
import logging
import os
import random
import shutil
import threading
import time

from pycons3rt3.exceptions import S3UtilError
from pycons3rt3.logify import Logify
from pycons3rt3.s3util import S3Util
from pycons3rt3.slack import SlackAttachment, SlackMessage

from .archiver import Archiver
from .directories import Directories
from .exceptions import ArchiverError, ImporterError, ZipError
from .mantistypes import chunker, get_slack_webhook, ImportStatus, MediaFileType
from .mediafile import MediaFile
from .settings import extensions
from .zip import unzip_archive


mod_logger = Logify.get_name() + '.importer'


class S3Importer(object):

    def __init__(self, s3_bucket, media_import_root=None):
        self.cls_logger = mod_logger + '.S3Importer'
        self.s3_bucket = s3_bucket
        try:
            self.s3 = S3Util(_bucket_name=self.s3_bucket)
        except S3UtilError as exc:
            self.failed_import = True
            raise ImporterError('Problem connecting to S3 bucket: {b}'.format(b=self.s3_bucket)) from exc
        self.media_import_root = media_import_root
        self.dirs = Directories(media_root=media_import_root)
        self.completed_archives = []
        self.filtered_keys = []
        self.threads = []
        self.max_simultaneous_threads = 3

    def read_completed_imports(self):
        """Reads the completed imports file

        return: None
        """
        log = logging.getLogger(self.cls_logger + '.read_completed_imports')

        # Ensure the file is found
        if not os.path.isfile(self.dirs.import_complete_file):
            log.warning('No archive complete file found: {f}'.format(f=self.dirs.import_complete_file))
            return

        # Read the file contents
        with open(self.dirs.import_complete_file, 'r') as f:
            content = f.readlines()
        self.completed_archives = [x.strip() for x in content]

    def process_s3_imports(self, filters=None):
        """Determine which S3 keys to import

        returns: None
        raises: ImporterError
        """
        log = logging.getLogger(self.cls_logger + '.process_s3_imports')
        s3_keys = self.s3.find_keys(regex='')
        self.read_completed_imports()

        matching_keys = []
        if filters:
            if not isinstance(filters, list):
                raise ImporterError('filters arg must be a list, found: {t}'.format(t=filters.__class__.__name__))
            for s3_key in s3_keys:
                for a_filter in filters:
                    if a_filter in s3_key:
                        log.info('Found S3 matching key: {k}'.format(k=s3_key))
                        matching_keys.append(s3_key)
        else:
            log.info('No filters specified, using all S3 keys...')
            matching_keys = s3_keys

        # Filter archive files already completed
        for matching_key in matching_keys:
            if matching_key not in self.completed_archives:
                log.info('Found S3 key not already imported: {k}'.format(k=matching_key))
                self.filtered_keys.append(matching_key)
            else:
                log.info('S3 key archive found already imported, will not be re-imported: {k}'.format(k=matching_key))

        if len(self.filtered_keys) < 1:
            log.info('No S3 keys found to import')
            return

        for filtered_key in self.filtered_keys:
            imp = Importer(
                media_import_root=self.media_import_root,
                s3_bucket=self.s3_bucket,
                s3_key=filtered_key
            )
            self.threads.append(imp)

        # Start threads in groups
        thread_group_num = 1
        log.info('Starting threads in groups of: {n}'.format(n=str(self.max_simultaneous_threads)))
        for thread_group in chunker(self.threads, self.max_simultaneous_threads):
            log.info('Starting thread group: {n}'.format(n=str(thread_group_num)))
            for thread in thread_group:
                thread.start()

            log.info('Waiting for completion of thread group: {n}'.format(n=str(thread_group_num)))
            for t in thread_group:
                t.join()
            log.info('Completed thread group: {n}'.format(n=str(thread_group_num)))
            thread_group_num += 1
        log.info('Completed processing all thread groups')

        # Log successful or failed imports to the respective files
        successful_imports = ''
        successful_count = 0
        failed_imports = ''
        for imp in self.threads:
            if imp.failed_import:
                failed_imports += imp.s3_key + '\n'
                log.warning('Detected failed import: {k}'.format(k=imp.s3_key))
            else:
                successful_count += 1
                successful_imports += imp.s3_key + '\n'
        if failed_imports == '':
            log.info('No failed imports detected!')
        else:
            with open(self.dirs.failed_imports_file, 'a') as f:
                f.write(failed_imports)
        if successful_imports == '':
            log.warning('No successful imports detected!')
        else:
            with open(self.dirs.import_complete_file, 'a') as f:
                f.write(successful_imports)

        # Clean up downloaded and import files
        log.info('Cleaning up files...')
        for imp in self.threads:
            imp.clean()
        log.info('Completed import of {n} archives:\n{t}'.format(n=str(successful_count), t=successful_imports))


class Importer(threading.Thread):

    def __init__(self, import_dir=None, media_import_root=None, s3_bucket=None, s3_key=None):
        threading.Thread.__init__(self)
        self.cls_logger = mod_logger + '.Importer'
        self.import_dir = import_dir
        self.media_import_root = media_import_root
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.dirs = Directories(media_root=media_import_root)
        self.extensions = extensions
        self.downloaded_file = None
        self.file_import_count = 0
        self.picture_import_count = 0
        self.movie_import_count = 0
        self.audio_import_count = 0
        self.already_imported_count = 0
        self.not_imported_count = 0
        self.failed_import = False
        slack_webhook = get_slack_webhook(self.dirs)
        if slack_webhook:
            slack_text = 'Importer'
            if s3_key:
                slack_text += ': S3 key: {k}'.format(k=s3_key)
            elif import_dir:
                slack_text += ': Local dir: {d}'.format(d=import_dir)
            self.slack_msg = SlackMessage(webhook_url=slack_webhook, text=slack_text)
        else:
            self.slack_msg = None

    def slack_success(self, msg):
        """Send successful Slack message"""
        if not self.slack_msg:
            return
        attachment = SlackAttachment(fallback=msg, text=msg, color='good')
        self.slack_msg.add_attachment(attachment)
        self.slack_msg.send()

    def slack_failure(self, msg):
        """Send failed Slack message"""
        if not self.slack_msg:
            return
        attachment = SlackAttachment(fallback=msg, text=msg, color='danger')
        self.slack_msg.add_attachment(attachment)
        self.slack_msg.send()

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

        if self.s3_key and self.s3_bucket:
            try:
                s3 = S3Util(_bucket_name=self.s3_bucket)
            except S3UtilError as exc:
                self.failed_import = True
                msg = 'Problem connecting to S3 bucket: {b}'.format(b=self.s3_bucket)
                self.slack_failure(msg)
                raise ImporterError(msg) from exc
            if not os.path.isdir(self.dirs.auto_import_dir):
                log.info('Creating directory: {d}'.format(d=self.dirs.auto_import_dir))
                os.makedirs(self.dirs.auto_import_dir, exist_ok=True)
            try:
                self.downloaded_file = s3.download_file_by_key(key=self.s3_key, dest_dir=self.dirs.auto_import_dir)
            except S3UtilError as exc:
                self.failed_import = True
                msg = 'Problem downloading key: {k}'.format(k=self.s3_key)
                self.slack_failure(msg)
                raise ImporterError(msg) from exc
            if not self.downloaded_file:
                self.failed_import = True
                msg = 'Downloaded file not found for s3 key: {k}'.format(k=self.s3_key)
                self.slack_failure(msg)
                raise ImporterError(msg)
            log.info('Attempting to unzip: {f}'.format(f=self.downloaded_file))
            try:
                self.import_dir = unzip_archive(zip_file=self.downloaded_file, output_dir=self.dirs.auto_import_dir)
            except ZipError as exc:
                self.failed_import = True
                msg = 'Problem extracting zip file: {z} to directory: {d}'.format(
                    z=self.downloaded_file, d=self.dirs.auto_import_dir)
                self.slack_failure(msg)
                raise ImporterError(msg) from exc
            log.info('Using extracted import directory: {d}'.format(d=self.import_dir))

        if not self.import_dir:
            self.failed_import = True
            msg = 'Import directory not set, cannot import!'
            self.slack_failure(msg)
            raise ImporterError(msg)

        log.info('Scanning directory for import: {d}'.format(d=self.import_dir))
        arch = Archiver(dir_to_archive=self.import_dir)
        try:
            arch.scan_archive()
        except ArchiverError as exc:
            self.failed_import = True
            msg = 'Problem scanning directory for import: {d}'.format(d=self.import_dir)
            self.slack_failure(msg)
            raise ImporterError(msg) from exc

        for media_file in arch.media_files:
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
                self.failed_import = True
                msg = 'Problem importing media file: {f}'.format(f=str(media_file))
                self.slack_failure(msg)
                raise ImporterError(msg) from exc
        msg = 'Completed processing media file imports from directory: {d}\n'.format(d=self.import_dir)
        msg += 'Imported a total of {n} media files\n'.format(n=str(self.file_import_count))
        msg += 'Imported {n} pictures\n'.format(n=str(self.picture_import_count))
        msg += 'Imported {n} movies\n'.format(n=str(self.movie_import_count))
        msg += 'Imported {n} audio files\n'.format(n=str(self.audio_import_count))
        msg += '{n} media files already imported\n'.format(n=str(self.already_imported_count))
        msg += '{n} files were not imported'.format(n=str(self.not_imported_count))
        log.info(msg)
        self.slack_success(msg)

    def clean(self):
        """Clean files used for import

        return: True if successful, false otherwise
        """
        log = logging.getLogger(self.cls_logger + '.clean')
        if self.downloaded_file:
            log.info('Removing file: {f}'.format(f=self.downloaded_file))
            os.remove(self.downloaded_file)
        if self.import_dir:
            if os.path.isdir(self.import_dir):
                log.info('Removing directory: {d}'.format(d=self.import_dir))
                shutil.rmtree(self.import_dir)

    def run(self):
        """Start a thread to process an import

        return: None
        """
        log = logging.getLogger(self.cls_logger + '.run')
        start_wait_sec = random.randint(1, 10)
        log.info('Waiting {t} seconds to start...'.format(t=str(start_wait_sec)))
        time.sleep(start_wait_sec)
        log.info('Starting thread to import...')
        self.process_import()
