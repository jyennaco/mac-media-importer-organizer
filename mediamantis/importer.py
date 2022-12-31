# -*- coding: utf-8 -*-

"""
mediamantis.importer
~~~~~~~~~~~~~~~~~~~
Imports media files from a variety of sources

"""

import datetime
import json
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

from .archiver import Archiver, read_archive_text
from .directories import Directories
from .exceptions import ArchiverError, ImporterError, ZipError
from .mantistypes import chunker, get_slack_webhook, ImportStatus, MediaFileType
from .mediafile import MediaFile
from .settings import extensions
from .zip import unzip_archive


mod_logger = Logify.get_name() + '.importer'


class S3Importer(object):

    def __init__(self, s3_bucket, media_import_root=None, un_import=False, library=None):
        self.cls_logger = mod_logger + '.S3Importer'
        self.s3_bucket = s3_bucket
        try:
            self.s3 = S3Util(_bucket_name=self.s3_bucket)
        except S3UtilError as exc:
            self.failed_import = True
            raise ImporterError('Problem connecting to S3 bucket: {b}'.format(b=self.s3_bucket)) from exc
        self.media_import_root = media_import_root
        self.un_import = un_import
        self.library = library
        self.dirs = Directories(media_root=media_import_root, library=library)
        self.completed_archives = []
        self.filtered_keys = []
        self.threads = []
        self.max_simultaneous_threads = 3

    def filter_completed_s3_keys(self, s3_keys):
        """Filters out a list of S3 keys by ones that have been completed

        :param s3_keys: (str) list of string S3 keys
        :return: (list) filtered list of S3 keys that have not been completed yet
        """
        log = logging.getLogger(self.cls_logger + '.filter_completed_s3_keys')

        # Read the completed imports
        if not self.un_import:
            self.read_completed_imports()

        # Filter archive files already completed
        completed_s3_keys = []
        not_completed_s3_keys = []
        for s3_key in s3_keys:
            if self.un_import:
                log.info('This is an un-import, adding S3 key to the filtered list: {k}'.format(k=s3_key))
                not_completed_s3_keys.append(s3_key)
            elif s3_key not in self.completed_archives:
                log.info('S3 key not already imported: {k}'.format(k=s3_key))
                not_completed_s3_keys.append(s3_key)
            else:
                log.info('S3 key already imported, will not be re-imported: {k}'.format(k=s3_key))
                completed_s3_keys.append(s3_key)
        log.info('Found {n} completed S3 keys that will not be imported'.format(n=str(len(completed_s3_keys))))
        log.info('Found {n} NOT completed S3 keys that will be imported'.format(n=str(len(not_completed_s3_keys))))
        self.filtered_keys = list(not_completed_s3_keys)
        return not_completed_s3_keys

    def list_imports(self, filters=None):
        """Lists the remaining archives to import from the S3 bucket

        :param filters: (list) of string filters
        :return: (list) filtered list of S3 keys that have not been completed yet
        """
        log = logging.getLogger(self.cls_logger + '.list_imports')

        # Get the S3 keys matching the filters
        matching_keys = self.read_s3_keys(filters=filters)

        # Get the list of filtered S3 keys
        self.filter_completed_s3_keys(s3_keys=matching_keys)

        # Exit if none are found to import or un-import
        if len(self.filtered_keys) < 1:
            log.info('No S3 keys found to import/un-import')
            return

        # Log the number of filtered keys found
        log.info('Found {n} filtered, un-imported S3 keys to import/un-import'.format(n=str(len(self.filtered_keys))))
        return self.filtered_keys

    def process_s3_imports(self, filters=None):
        """Determine which S3 keys to import

        :param filters: (list) of string filters
        returns: None
        raises: ImporterError
        """
        log = logging.getLogger(self.cls_logger + '.process_s3_imports')

        # List the imports
        self.list_imports(filters=filters)

        # Create an importer, and append it to the list of threads
        for filtered_key in self.filtered_keys:
            imp = Importer(
                media_import_root=self.media_import_root,
                s3_bucket=self.s3_bucket,
                s3_key=filtered_key,
                un_import=self.un_import,
                library=self.library
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
        successful_count = 0
        failed_count = 0
        successful_imports = ''
        failed_imports = ''
        for imp in self.threads:
            if imp.failed_import:
                failed_count += 1
                if imp.s3_key:
                    # Update the failed import file
                    log.warning('Detected failed import/un-import: {k}'.format(k=imp.s3_key))
                    add_failed_import(dirs=self.dirs, failed_import=imp.s3_key)
                    failed_imports += imp.s3_key + '\n'
            else:
                successful_count += 1
                if imp.s3_key:
                    successful_imports += imp.s3_key + '\n'

        # Print counts and summaries
        if failed_count == 0:
            log.info('No failed imports/un-imports detected!')
        else:
            log.warning('Failed imported archives:\n{t}'.format(t=failed_imports))
        if successful_count == 0:
            log.warning('No successful imports/un-imports detected!')
        else:
            log.info('Completed import/un-import of {n} archives:\n{t}'.format(
                n=str(successful_count), t=successful_imports))

        # Clean up downloaded and import files
        log.info('Cleaning up files and directories...')
        for imp in self.threads:
            imp.clean()

    def read_completed_imports(self):
        """Reads the completed imports file

        return: None
        """
        self.completed_archives = read_completed_imports(dirs=self.dirs)

    def read_s3_keys(self, filters=None):
        """Gets a list of S3 keys from the bucket

        :return:
        """
        log = logging.getLogger(self.cls_logger + '.process_s3_imports')

        # Get a list of keys
        log.info('Getting a list of S3 keys from the target bucket...')
        try:
            s3_keys = self.s3.find_keys(regex='')
        except S3UtilError as exc:
            msg = 'Problem getting S3 keys from the S3 bucket'
            raise ImporterError(msg) from exc

        # Save S3 keys matching the provided filters
        matching_keys = []

        # If filters were provided, find the matching S3 keys
        if filters:
            if not isinstance(filters, list):
                raise ImporterError('filters arg must be a list, found: {t}'.format(t=filters.__class__.__name__))
            log.info('Filtering on keys that match: [{k}]'.format(k=','.join(filters)))
            for s3_key in s3_keys:
                for a_filter in filters:
                    if a_filter in s3_key:
                        log.info('Found S3 matching key: {k}'.format(k=s3_key))
                        matching_keys.append(s3_key)
        else:
            log.info('No filters specified, using all S3 keys...')
            matching_keys = s3_keys

        log.info('Found {n} matching S3 keys'.format(n=str(len(matching_keys))))
        return matching_keys


class Importer(threading.Thread):

    def __init__(self, import_dir=None, media_import_root=None, s3_bucket=None, s3_key=None, un_import=False,
                 library=None):
        threading.Thread.__init__(self)
        self.cls_logger = mod_logger + '.Importer'
        self.import_dir = import_dir
        self.import_dir_name = import_dir.split(os.sep)[-1]
        self.media_import_root = media_import_root
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.un_import = un_import
        self.library = library
        self.dirs = Directories(media_root=media_import_root, library=self.library)
        self.extensions = extensions
        self.downloaded_file = None
        self.file_import_count = 0
        self.picture_import_count = 0
        self.movie_import_count = 0
        self.audio_import_count = 0
        self.already_imported_count = 0
        self.not_imported_count = 0
        self.un_imported_count = 0
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

        # Skip if archive.txt
        if media_file.file_name == 'archive.txt':
            log.debug('Skipping archive.txt file')
            return

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

        # Ensure the import root directory exists, and create it if not found
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
        media_file.import_path = target_path

        if os.path.isfile(target_path) and not self.un_import:
            log.info('Found media file already imported: {f}'.format(f=target_path))
            media_file.import_status = ImportStatus.ALREADY_EXISTS
            self.already_imported_count += 1
            return
        elif os.path.isfile(target_path) and self.un_import:
            log.info('Found media file to un-import: {f}'.format(f=target_path))
            os.remove(target_path)
            media_file.import_status = ImportStatus.UNIMPORTED
            self.un_imported_count += 1
            return
        elif self.un_import:
            log.info('File not found, no need to un-import: {f}'.format(f=target_path))
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

        # Update counts
        if media_file.file_type == MediaFileType.PICTURE:
            self.picture_import_count += 1
        elif media_file.file_type == MediaFileType.MOVIE:
            self.movie_import_count += 1
        elif media_file.file_type == MediaFileType.AUDIO:
            self.audio_import_count += 1
        self.file_import_count += 1

    def process_import(self, delete_import_dir=False, mega=False):
        """Process the import of media from a directory

        :param delete_import_dir: (bool) delete_import_dir: Set True to delete the import directory
        :param mega: (bool) Set True to also import to MegaCMD

        return: none
        raises: ImporterError
        """
        log = logging.getLogger(self.cls_logger + '.process_import')

        # Date/Time of the import
        import_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

        # Create the mantis directory for this import if it does not exist
        if not os.path.isdir(self.dirs.mantis_dir):
            os.makedirs(self.dirs.mantis_dir, exist_ok=True)

        # Import the S3 archive if both a bucket name and S3 key were provided
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

            # Unzip the downloaded zip archive
            log.info('Attempting to unzip: {f}'.format(f=self.downloaded_file))
            try:
                self.import_dir = unzip_archive(zip_file=self.downloaded_file, output_dir=self.dirs.auto_import_dir)
            except ZipError as exc:
                self.failed_import = True
                msg = 'Problem extracting zip file: {z} to directory: {d}'.format(
                    z=self.downloaded_file, d=self.dirs.auto_import_dir)
                self.slack_failure(msg)
                raise ImporterError(msg) from exc

            # Delete the downloaded zip archive
            if os.path.isfile(self.downloaded_file):
                log.info('Removing downloaded archive file: {f}'.format(f=self.downloaded_file))
                os.remove(self.downloaded_file)
            log.info('Using extracted import directory: {d}'.format(d=self.import_dir))
        elif self.s3_key and not self.s3_bucket:
            msg = 'S3 key to a zip archive provided, but s3bucket not provided'
            self.slack_failure(msg)
            raise ImporterError(msg)
        elif self.s3_bucket and not self.s3_key:
            msg = 'S3 bucket provided, but S3 key to a zip archive was not provided not provided'
            self.slack_failure(msg)
            raise ImporterError(msg)

        # Fail out if the import directory is not set
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

        # Check archive data for a library
        if not self.library:
            try:
                archive_data = read_archive_text(archive_text_path=os.path.join(self.import_dir, 'archive.txt'))
            except ArchiverError as exc:
                log.warning('Problem reading archive.txt file from directory: {d}\n{e}'.format(
                    d=self.import_dir, e=str(exc)))
                archive_data = None
            if archive_data:
                log.info('Found archive data')
                if archive_data['Library'] != 'default':
                    self.library = archive_data['Library']
                    log.info('Found library in archive dats set to: {b}'.format(b=self.library))
                    self.dirs.set_library(library=self.library)
                else:
                    log.info('Using the default library for import')
        else:
            log.info('Importing into provided library: {b}'.format(b=self.library))

        # Path to the mantis import file to track imports
        mantis_import_file = self.dirs.mantis_dir + os.sep + 'import_' + import_timestamp
        if self.s3_key:
            mantis_import_file += '_s3'
        mantis_import_file += '_' + self.import_dir_name + '.json'

        # Create the mantis import file contents with header
        mantis_file_content = {
            'import_timestamp': import_timestamp,
            'source_directory': self.import_dir,
            'source_directory_name': self.import_dir_name,
            's3_bucket': self.s3_bucket if self.s3_bucket else 'None',
            's3_key': self.s3_key if self.s3_key else 'None',
            's3_downloaded_file': self.downloaded_file if self.downloaded_file else 'None',
            'media_inbox': self.dirs.media_inbox,
            'auto_import_dir': self.dirs.auto_import_dir,
            'archive_files_dir': self.dirs.archive_files_dir,
            'library': self.library if self.library else 'None',
            'media_import_root_directory': self.media_import_root,
            'unimport': 'True' if self.un_import else 'False',
            'imports': [],
            'results': {
                'total_import_count': self.file_import_count,
                'picture_import_count': self.picture_import_count,
                'movie_import_count': self.movie_import_count,
                'audio_import_count': self.audio_import_count,
                'already_imported_count': self.already_imported_count,
                'not_imported_count': self.not_imported_count,
                'un_imported_count': self.un_imported_count
            }
        }

        # Write the import file with the header
        log.info('Creating import file: {f}'.format(f=mantis_import_file))
        write_mantis_contents(mantis_file=mantis_import_file, mantis_content=mantis_file_content)

        # Add the media import root directory to the import dirs file
        write_imports_dir_file(imports_dir_file_path=self.dirs.import_dirs_file,
                               media_import_root=self.media_import_root)

        # Import each media file in the archive
        for media_file in arch.media_files:
            if media_file.import_status == ImportStatus.COMPLETED:
                continue
            elif media_file.import_status == ImportStatus.ALREADY_EXISTS:
                continue
            elif media_file.import_status == ImportStatus.DO_NOT_IMPORT:
                continue
            elif media_file.import_status == ImportStatus.UNIMPORTED:
                continue
            if media_file.file_type == MediaFileType.UNKNOWN:
                log.info('Unknown file type will not be imported/un-imported: {f}'.format(f=media_file.file_name))
                continue
            try:
                self.import_media_file(media_file=media_file)
            except ImporterError as exc:
                self.failed_import = True
                msg = 'Problem importing/un-importing media file: {f}'.format(f=str(media_file))
                self.slack_failure(msg)
                raise ImporterError(msg) from exc

            # Update the mantis import file results
            mantis_file_content['imports'].append(media_file.to_record())

            # Update the results
            mantis_file_content['results'] = {
                'total_import_count': self.file_import_count,
                'picture_import_count': self.picture_import_count,
                'movie_import_count': self.movie_import_count,
                'audio_import_count': self.audio_import_count,
                'already_imported_count': self.already_imported_count,
                'not_imported_count': self.not_imported_count,
                'un_imported_count': self.un_imported_count
            }

            # Update the mantis file
            write_mantis_contents(mantis_file=mantis_import_file, mantis_content=mantis_file_content)

        # Append the imported archive to the completed imports file
        if self.s3_key:
            add_completed_import(dirs=self.dirs, completed_import=self.s3_key)

        # Delete the import directory after the import completed
        if delete_import_dir:
            self.clean()
        else:
            log.info('delete_import_dir is False, not cleaning up directory: {d}'.format(d=self.import_dir))

        # Print out the summary of the import
        msg = 'Completed processing media files from directory: {d}\n'.format(d=self.import_dir)
        if self.s3_key and not self.un_import:
            msg += 'Imported media files from s3 key: {k}\n'.format(k=self.s3_key)
        if self.s3_key and self.un_import:
            msg += 'Un-imported media files from s3 key: {k}\n'.format(k=self.s3_key)
        if not self.un_import:
            msg += 'Imported a total of {n} media files\n'.format(n=str(self.file_import_count))
            msg += 'Imported {n} pictures\n'.format(n=str(self.picture_import_count))
            msg += 'Imported {n} movies\n'.format(n=str(self.movie_import_count))
            msg += 'Imported {n} audio files\n'.format(n=str(self.audio_import_count))
            msg += '{n} media files already imported\n'.format(n=str(self.already_imported_count))
        if self.not_imported_count > 0:
            msg += '{n} files were not imported'.format(n=str(self.not_imported_count))
        if self.un_import:
            msg += '{n} files were un-imported'.format(n=str(self.un_imported_count))
        log.info(msg)
        self.slack_success(msg)

    def clean(self):
        """Clean files and directories used for import

        return: True if successful, false otherwise
        """
        log = logging.getLogger(self.cls_logger + '.clean')
        if self.downloaded_file:
            if os.path.isfile(self.downloaded_file):
                log.info('Removing file: {f}'.format(f=self.downloaded_file))
                os.remove(self.downloaded_file)
            else:
                log.info('Downloaded file not found, nothing to remove: {f}'.format(f=self.downloaded_file))
        else:
            log.info('No downloaded file, nothing to remove')
        if self.import_dir:
            if os.path.isdir(self.import_dir):
                if '/Volume' not in self.import_dir:
                    if self.import_dir.lower() not in self.media_import_root.lower():
                        log.info('Removing directory: {d}'.format(d=self.import_dir))
                        shutil.rmtree(self.import_dir)
                    else:
                        log.info('Not removing import directory [{d}], it would also delete the media root '
                                 'directory [{m}]'.format(d=self.import_dir, m=self.media_import_root))
                else:
                    log.info('Not removing a mounted volume: {d}'.format(d=self.import_dir))
            else:
                log.info('Import directory not found, nothing to remove: {d}'.format(d=self.import_dir))
        else:
            log.info('No import directory, nothing to remove')

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


def add_completed_import(dirs, completed_import):
    """Adds an imported archive to the completed imports file

    :param: dirs (Directories) object
    :param: completed_import: (str) Name of the completed import archive
    :return: None
    """
    log = logging.getLogger(mod_logger + '.add_completed_import')
    with open(dirs.import_complete_file, 'a') as f:
        f.write(completed_import + '\n')
    log.info('Added [{i}] to file: {f}'.format(i=completed_import, f=dirs.import_complete_file))


def add_failed_import(dirs, failed_import):
    """Adds an imported archive to the completed imports file

    :param: dirs: (Directories) object
    :param: failed_import: (str) Name of the failed import archive
    :return: None
    """
    log = logging.getLogger(mod_logger + '.add_failed_import')
    with open(dirs.failed_imports_file, 'a') as f:
        f.write(failed_import + '\n')
    log.info('Added [{i}] to file: {f}'.format(i=failed_import, f=dirs.failed_imports_file))


def read_completed_imports(dirs):
    """Reads the completed imports file

    :param: (dirs) Directories object
    return: list of completed imports
    """
    log = logging.getLogger(mod_logger + '.read_completed_imports')

    completed_archives = []

    # Ensure the file is found
    if not os.path.isfile(dirs.import_complete_file):
        log.warning('No archive complete file found: {f}'.format(f=dirs.import_complete_file))
        return completed_archives

    # Read the file contents
    log.info('Reading completed imports from file: {f}'.format(f=dirs.import_complete_file))
    with open(dirs.import_complete_file, 'r') as f:
        content = f.readlines()
    completed_archives = [x.strip() for x in content]
    log.info('Found {n} completed archives'.format(n=str(len(completed_archives))))
    return completed_archives


def read_failed_imports(dirs):
    """Reads the failed imports file

    :param: (dirs) Directories object
    return: list of completed imports
    """
    log = logging.getLogger(mod_logger + '.read_failed_imports')

    failed_imports = []

    # Ensure the file is found
    if not os.path.isfile(dirs.failed_imports_file):
        log.warning('No failed imports file found: {f}'.format(f=dirs.failed_imports_file))
        return failed_imports

    # Read the file contents
    log.info('Reading failed imports from file: {f}'.format(f=dirs.failed_imports_file))
    with open(dirs.failed_imports_file, 'r') as f:
        content = f.readlines()
    failed_imports = [x.strip() for x in content]
    log.info('Found {n} failed imports'.format(n=str(len(failed_imports))))
    return failed_imports


def read_imports_dir_file(imports_dir_file_path, media_import_root):
    """Reads the contents of the imports dir file

    :param imports_dir_file_path: (str) Full path to the imports dir file
    :param media_import_root: (str) Full path to the media import root
    :return: (list) Unique list of file paths for import directories
    """
    import_dirs = []
    if not os.path.isfile(imports_dir_file_path):
        return import_dirs
    with open(imports_dir_file_path, 'r') as f:
        file_content = f.readlines()

    # Get a list of import dirs, one per line of the file
    raw_import_dirs = [x.strip() for x in file_content]

    # Ensure the list is unique
    for raw_import_dir in raw_import_dirs:
        if raw_import_dir not in import_dirs:
            import_dirs.append(raw_import_dir)

    # Return the list of unique import dirs
    return import_dirs


def write_imports_dir_file(imports_dir_file_path, media_import_root):
    """Write content to the mantis file for an import

    :param imports_dir_file_path: (str) Full path to the imports dir file
    :param media_import_root: (str) Full path to the media import root
    :return: None
    :raises: ImporterError
    """
    if not isinstance(imports_dir_file_path, str):
        raise ImporterError('imports_dir_file_path arg must be a str, found: {t}'.format(
            t=str(type(imports_dir_file_path))))
    if not isinstance(media_import_root, str):
        raise ImporterError('media_import_root arg must be a str, found: {t}'.format(t=str(type(media_import_root))))

    # Ensure the new media import root exists
    if not os.path.isdir(media_import_root):
        raise ImporterError('Media import root directory not found: {d}'.format(d=media_import_root))

    # Get the current list of unqiue import dirs
    import_dirs = read_imports_dir_file(imports_dir_file_path=imports_dir_file_path,
                                        media_import_root=media_import_root)

    # Add the new media import root
    import_dirs.append(media_import_root)

    # Generate the file content as a string
    file_content = ''
    for import_dir in import_dirs:
        file_content += import_dir + '\n'

    # Overwrite the mantis file
    try:
        with open(imports_dir_file_path, 'w') as f:
            f.write(file_content)
    except (IOError, OSError) as exc:
        msg = 'Problem writing import dirs file: {f}'.format(f=imports_dir_file_path)
        raise ImporterError(msg) from exc


def write_mantis_contents(mantis_file, mantis_content):
    """Write content to the mantis file for an import

    :param mantis_file: (str) Path to mantis file
    :param mantis_content: (dict) Contents to write
    :return:
    """
    if not isinstance(mantis_file, str):
        raise ImporterError('mantis_file arg must be a str, found: {t}'.format(t=mantis_file.__class__.__name__))
    if not isinstance(mantis_content, dict):
        raise ImporterError('mantis_content arg must be a dict, found: {t}'.format(
            t=mantis_file.__class__.__name__))

    # Get JSON content
    mantis_json_content = json.dumps(mantis_content, indent=2, sort_keys=False)

    # Overwrite the mantis file
    try:
        with open(mantis_file, 'w') as f:
            f.write(mantis_json_content)
    except (IOError, OSError) as exc:
        msg = 'Problem writing mantis file: {f}'.format(f=mantis_file)
        raise ImporterError(msg) from exc
