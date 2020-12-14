# -*- coding: utf-8 -*-

"""
mediamantis.archiver
~~~~~~~~~~~~~~~~~~~
Manage media file archives

"""

import datetime
import logging
import random
import os
import platform
import shutil
import threading
import time

from pycons3rt3.exceptions import S3UtilError
from pycons3rt3.logify import Logify
from pycons3rt3.s3util import S3Util
from pycons3rt3.slack import SlackAttachment, SlackMessage
import requests

from .directories import Directories
from .exceptions import ArchiverError, ZipError
from .mantistypes import chunker, get_slack_webhook, ArchiveStatus, MediaFileType
from .mediafile import MediaFile
from .settings import extensions, max_archive_size_bytes, skip_items
from .version import version
from .zip import unzip_archive, zip_dir


mod_logger = Logify.get_name() + '.archiver'

word_file = '/usr/share/dict/words'
word_site = 'https://svnweb.freebsd.org/csrg/share/dict/words?view=co&content-type=text/plain'


class Archiver(threading.Thread):

    def __init__(self, dir_to_archive, media_inbox=None, keyword=None, library=None):
        threading.Thread.__init__(self)
        self.cls_logger = mod_logger + '.Archiver'
        self.dir_to_archive = dir_to_archive
        self.library = library
        self.dirs = Directories(media_inbox=media_inbox, library=library)
        self.archive_files_dir = self.dirs.archive_files_dir
        self.current_archive_size_bytes = 0
        if os.path.isfile(word_file):
            self.words = open(word_file).read().splitlines()
        else:
            response = requests.get(word_site)
            self.words = response.content.splitlines()
        if keyword:
            self.primary_id_word = keyword
        else:
            self.primary_id_word = random.choice(self.words)
        self.archive_files_dir_name = self.primary_id_word + '_initial'
        self.archive_files_path = os.path.join(self.archive_files_dir, self.archive_files_dir_name)
        self.archive_total_size = 0
        self.file_count = 0
        self.picture_count = 0
        self.movie_count = 0
        self.audio_count = 0
        self.unknown_count = 0
        self.earliest_date = 33134676164
        self.latest_date = 0
        self.earliest_timestamp = None
        self.latest_timestamp = None
        self.media_files = []
        self.archive_dir_list = []
        self.archive_zip_list = []
        self.s3bucket = None
        slack_webhook = get_slack_webhook(self.dirs)
        if slack_webhook:
            self.slack_msg = SlackMessage(webhook_url=slack_webhook, text='Archiver: {d}'.format(d=dir_to_archive))
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

    def scan_archive(self):
        """Scans the archive for info about the files

        :return None
        :raises: ArchiverError
        """
        log = logging.getLogger(self.cls_logger + '.scan_archive')
        log.info('Scanning directory to archive: {d}'.format(d=self.dir_to_archive))

        if not os.path.isdir(self.dir_to_archive):
            raise ArchiverError('Provided directory to archive is not a directory: {d}'.format(d=self.dir_to_archive))

        for dir_path, _, filenames in os.walk(self.dir_to_archive):
            for f in filenames:
                file_path = os.path.join(dir_path, f)

                # Skip if it is symbolic link
                if os.path.islink(file_path):
                    log.info('Skipping link: {f}'.format(f=file_path))
                    continue

                # Skip if file matches a skip condition
                skip_file = False
                if f in skip_items['files']:
                    log.debug('File matched skipped item: {f}'.format(f=f))
                    skip_file = True
                for skip_prefix in skip_items['prefixes']:
                    if f.startswith(skip_prefix):
                        log.debug('File matched skipped prefix: {p}'.format(p=skip_prefix))
                        skip_file = True
                for skip_ext in skip_items['extensions']:
                    if f.endswith(skip_ext):
                        log.debug('File matched skipped extension: {x}'.format(x=skip_ext))
                        skip_file = True
                if skip_file:
                    log.info('Skipping file: {f}'.format(f=file_path))
                    continue

                # Get the file size
                file_size = os.path.getsize(file_path)

                # Get the file type
                ext = file_path.split('.')[-1].lower()
                if ext in extensions['pics']:
                    file_type = MediaFileType.PICTURE
                    self.picture_count += 1
                elif ext in extensions['vids']:
                    file_type = MediaFileType.MOVIE
                    self.movie_count += 1
                elif ext in extensions['audio']:
                    file_type = MediaFileType.AUDIO
                    self.audio_count += 1
                else:
                    file_type = MediaFileType.UNKNOWN
                    self.unknown_count += 1

                # Get the creation time
                creation_time = get_file_creation_time(file_path)

                # Add a media file to the list
                self.media_files.append(MediaFile(
                    file_path=file_path,
                    creation_time=creation_time,
                    size_bytes=file_size,
                    file_type=file_type
                ))

                # Set overall stats
                self.archive_total_size += file_size
                self.file_count += 1

                # Determine if this is the oldest/newest file
                if creation_time < self.earliest_date:
                    self.earliest_date = creation_time
                if creation_time > self.latest_date:
                    self.latest_date = creation_time

        self.media_files.sort(key=get_timestamp, reverse=False)
        self.earliest_timestamp = datetime.datetime.fromtimestamp(self.earliest_date).strftime('%Y%m%d-%H%M%S')
        self.latest_timestamp = datetime.datetime.fromtimestamp(self.latest_date).strftime('%Y%m%d-%H%M%S')
        log.info('Found total size of files to archive is: {n} bytes'.format(n=str(self.archive_total_size)))
        log.info('Found {n} files in this archive'.format(n=str(self.file_count)))
        log.info('Found {n} pictures'.format(n=str(self.picture_count)))
        log.info('Found {n} movies'.format(n=str(self.movie_count)))
        log.info('Found {n} audio files'.format(n=str(self.audio_count)))
        log.info('Found {n} unknown files'.format(n=str(self.unknown_count)))
        log.info('Found earliest timestamp: {t}'.format(t=self.earliest_timestamp))
        log.info('Found latest timestamp: {t}'.format(t=self.latest_timestamp))

    def create_archive_dir_name(self, first_timestamp, last_timestamp):
        """Returns a directory name with a specific format

        :param first_timestamp: (str) timestamp format: yyyymmdd-HHMMSS
        :param last_timestamp: (str) timestamp format: yyyymmdd-HHMMSS
        :return: (str) directory name for an archive of format: yyyymmdd-yyyymmdd_uniqueWord
        """
        return first_timestamp.split('-')[0] + '-' + last_timestamp.split('-')[0] + '_' + self.primary_id_word

    def create_archive_info_file(self, archive_path):
        """Creates an archive.txt path

        """
        log = logging.getLogger(self.cls_logger + '.create_archive_info_file')
        archive_info_file = os.path.join(archive_path, 'archive.txt')
        info_txt = 'Created by mediamantis version: {v}\n'.format(v=version())
        info_txt += 'Created on: {t}\n'.format(t=datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        info_txt += 'Created from: {d}\n'.format(d=self.dir_to_archive)
        info_txt += 'Using ID word: {w}\n'.format(w=self.primary_id_word)
        if self.library:
            info_txt += 'Library: {b}\n'.format(b=self.library)
        with open(archive_info_file, 'w') as f:
            f.write(info_txt)
        log.info('Created archive info file: {f}'.format(f=archive_info_file))

    def rename_archive_files_dir(self, first_timestamp, last_timestamp):
        """Renames the archive file directory using a specific name format

        :param first_timestamp: (str) timestamp format: yyyymmdd-HHMMSS
        :param last_timestamp: (str) timestamp format: yyyymmdd-HHMMSS
        :return: None
        :raises: ArchiverError
        """
        log = logging.getLogger(self.cls_logger + '.rename_archive_files_dir')
        new_path = os.path.join(self.archive_files_dir, self.create_archive_dir_name(first_timestamp, last_timestamp))
        log.info('Renaming directory [{s}] to: [{d}]'.format(s=self.archive_files_path, d=new_path))
        try:
            shutil.move(src=self.archive_files_path, dst=new_path)
        except Exception as exc:
            raise ArchiverError('Problem renaming archive directory to: {n}'.format(n=new_path)) from exc
        self.archive_dir_list.append(new_path)
        self.create_archive_info_file(archive_path=new_path)

    def update_archive_files_dir(self):
        """Updates the archive files dir name to be used for archiving

        :return: None
        """
        log = logging.getLogger(self.cls_logger + '.update_archive_files_dir')
        self.archive_files_path = os.path.join(
            self.archive_files_dir,
            self.primary_id_word + '_' + random.choice(self.words)
        )
        log.info('Creating directory for archiving: {d}'.format(d=self.archive_files_path))
        os.makedirs(self.archive_files_path, exist_ok=True)

    def verify_disk_space(self):
        """Ensures the destination disk has enough space

        :return: True is enough disk space is determines, False otherwise
        """
        log = logging.getLogger(self.cls_logger + '.verify_disk_space')
        free_disk_space = shutil.disk_usage(self.archive_files_path).free
        log.info('Found {n} bytes free for destination: {d}'.format(n=str(free_disk_space), d=self.archive_files_path))
        if (self.archive_total_size * 3) < free_disk_space:
            log.info('There appears to be enough disk space to complete this archive')
            return True
        else:
            log.warning('There may not be enough disk space to complete this archive')
            return False

    def print_media_files(self):
        """Prints output media files

        :return: none
        """
        for media_file in self.media_files:
            print('{n}: {t}'.format(n=media_file.file_name, t=media_file.creation_timestamp))

    def archive_file(self, media_file):
        """Archives a media file to the current archive files directory

        :param media_file: (MediaFile) object
        :return: None
        :raises: ArchiverError
        """
        log = logging.getLogger(self.cls_logger + '.archive_file')

        if not isinstance(media_file, MediaFile):
            raise ArchiverError('Expected media_file type MediaFile, found: {t}'.format(
                t=media_file.__class__.__name__))

        # Ensure the file exists
        if not os.path.isfile(media_file.file_path):
            raise ArchiverError('File not found to archive: {f}'.format(f=media_file.file_path))

        # Ensure the archive files directory exists, and create it if not found
        if not os.path.exists(self.archive_files_path):
            log.info('Creating archive files directory: {d}'.format(d=self.archive_files_path))
            os.makedirs(self.archive_files_path, exist_ok=True)

        # Move the file to the archive directory
        log.info('Archiving file: {f}'.format(f=media_file.file_path))
        try:
            shutil.move(media_file.file_path, self.archive_files_path)
        except Exception as exc:
            raise ArchiverError('Problem moving file [{f}] to: {d}'.format(
                f=media_file.file_path, d=self.archive_files_path)) from exc
        media_file.archive_status = ArchiveStatus.COMPLETED
        media_file.destination_path = os.path.join(
            self.archive_files_path,
            media_file.file_name
        )

    def zip_archives(self):
        """Create zip files from the archive directories

        :return: None
        :raises: ArchiverError
        """
        log = logging.getLogger(self.cls_logger + '.zip_archives')
        if len(self.archive_dir_list) < 1:
            log.info('No archive directories to zip')
            return
        log.info('Creating {n} zip archives'.format(n=str(len(self.archive_dir_list))))
        for archive_dir in self.archive_dir_list:
            log.info('Found archive dir to zip: {d}'.format(d=archive_dir))
            zip_path = archive_dir + '.zip'
            try:
                zip_dir(dir_path=archive_dir, zip_file=zip_path)
            except ZipError as exc:
                raise ArchiverError('Problem creating zip file: {z}'.format(z=zip_path)) from exc
            self.archive_zip_list.append(zip_path)
            log.info('Created archive zip: {z}'.format(z=zip_path))
        log.info('Completed creating {n} zip archives'.format(n=str(len(self.archive_dir_list))))

    def upload_to_s3(self, bucket_name):
        """Uploads the zip archives to AWS S3 buckets

        :param bucket_name: (str) name of the S3 bucket to upload to
        :return: None
        :raises: ArchiverError
        """
        log = logging.getLogger(self.cls_logger + '.upload_to_s3')
        try:
            s3 = S3Util(_bucket_name=bucket_name)
        except S3UtilError as exc:
            raise ArchiverError('Problem connecting to S3 bucket: {b}'.format(b=bucket_name)) from exc
        if len(self.archive_zip_list) < 1:
            log.info('No archive zip files to upload')
            return
        log.info('Attempting to upload {n} archive zip files to S3 bucket: {b}'.format(
            n=str(len(self.archive_zip_list)), b=bucket_name))
        for archive_zip in self.archive_zip_list:
            log.info('Uploading zip to S3: {z}'.format(z=archive_zip))
            key = archive_zip.split(os.sep)[-1]
            if not s3.upload_file(filepath=archive_zip, key=key):
                raise ArchiverError('Problem uploading zip [{z}] to bucket {b} with key: {k}'.format(
                    z=archive_zip, b=bucket_name, k=key
                ))
            log.info('Completed uploading key: {k}'.format(k=key))
        log.info('Completed uploading {n} archive zip files to S3'.format(n=str(len(self.archive_zip_list))))

    def process_archive(self):
        """Creates zip archives of media files in a directory with a maximum size

        :return: None
        :raises: ArchiverError
        """
        log = logging.getLogger(self.cls_logger + '.process_archive')

        # Scan the archive
        try:
            self.scan_archive()
        except ArchiverError as exc:
            msg = 'Problem scanning archive: {d}'.format(d=self.dir_to_archive)
            self.slack_failure(msg)
            raise ArchiverError(msg) from exc

        # Exit if no media files are found
        if len(self.media_files) < 1:
            msg = 'No media files found to archive in directory: {d}'.format(d=self.dir_to_archive)
            self.slack_failure(msg)
            log.info(msg)
            return

        # Create the archive directory
        try:
            os.makedirs(self.archive_files_path, exist_ok=True)
        except Exception as exc:
            msg = 'Problem creating directory: {d}'.format(d=self.archive_files_path)
            self.slack_failure(msg)
            raise ArchiverError(msg) from exc

        # Ensure the destination has enough space
        if not self.verify_disk_space():
            msg = 'Insufficient disk space available to create archives in: {d}'.format(d=self.archive_files_path)
            self.slack_failure(msg)
            raise ArchiverError(msg)

        archive_size_bytes = 0
        first_timestamp = self.media_files[0].creation_timestamp
        last_timestamp = None
        count = 0
        for media_file in self.media_files:
            if media_file.archive_status == ArchiveStatus.COMPLETED:
                continue
            # if media_file.file_type == MediaFileType.UNKNOWN:
            #    log.info('Unknown file type will not be archived: {f}'.format(f=media_file.file_name))
            #    continue
            if archive_size_bytes > max_archive_size_bytes:
                log.info('Max archive size reached for: {d}'.format(d=self.archive_files_path))
                if not last_timestamp:
                    msg = 'Last timestamp not found to create archive directory name'
                    self.slack_failure(msg)
                    raise ArchiverError(msg)
                # Rename the directory
                self.rename_archive_files_dir(
                    first_timestamp=first_timestamp,
                    last_timestamp=last_timestamp
                )
                first_timestamp = media_file.creation_timestamp
                self.update_archive_files_dir()
                archive_size_bytes = 0
            try:
                self.archive_file(media_file=media_file)
            except ArchiverError as exc:
                msg = 'Problem archiving media file: {f}'.format(f=str(media_file))
                self.slack_failure(msg)
                raise ArchiverError(msg) from exc
            last_timestamp = media_file.creation_timestamp
            archive_size_bytes += media_file.size_bytes
            count += 1
        log.info('Completed last media file archive to: {d}'.format(d=self.archive_files_path))
        self.rename_archive_files_dir(
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp
        )
        log.info('Completed archiving files from directory: {d}'.format(d=self.dir_to_archive))
        try:
            self.zip_archives()
        except ArchiverError as exc:
            msg = 'Problem creating zip archives'
            self.slack_failure(msg)
            raise ArchiverError(msg) from exc
        msg = 'Completed archiving directory: {d}, to: {a}'.format(d=self.dir_to_archive, a=self.archive_files_path)
        log.info(msg)
        self.slack_success(msg)

    def run(self):
        """Start a thread to process an archive

        return: None
        """
        log = logging.getLogger(self.cls_logger + '.run')
        start_wait_sec = random.randint(1, 10)
        log.info('Waiting {t} seconds to start...'.format(t=str(start_wait_sec)))
        time.sleep(start_wait_sec)
        log.info('Starting thread to archive...')
        self.process_archive()

    def clean(self):
        """Cleans archive zip files and directories

        return: None
        """
        log = logging.getLogger(self.cls_logger + '.clean')
        for archive_zip in self.archive_zip_list:
            if os.path.isfile(archive_zip):
                log.info('Removing archive zip: {z}'.format(z=archive_zip))
                os.remove(archive_zip)
        for archive_dir in self.archive_dir_list:
            if os.path.isdir(archive_dir):
                log.info('Removing archive directory: {d}'.format(d=archive_dir))
                shutil.rmtree(archive_dir)


class ReArchiver(threading.Thread):

    def __init__(self, s3_bucket, media_inbox=None, library=None):
        threading.Thread.__init__(self)
        self.cls_logger = mod_logger + '.ReArchiver'
        self.s3_bucket = s3_bucket
        self.library = library
        self.dirs = Directories(media_inbox=media_inbox, library=library)
        self.re_archive_s3_keys = []
        self.filtered_keys = []
        self.re_archive_complete_s3_keys = []
        self.threads = []
        self.max_simultaneous_threads = 3

    def read_re_archive_file(self):
        """Reads the re-archive file to get the list of files to re-archive

        return: None
        """
        log = logging.getLogger(self.cls_logger + '.read_re_archive_file')

        # Ensure the file is found
        if not os.path.isfile(self.dirs.re_archive_file):
            log.warning('No re-archive file found: {f}'.format(f=self.dirs.re_archive_file))
            return

        # Read the file contents
        with open(self.dirs.re_archive_file, 'r') as f:
            content = f.readlines()
        self.re_archive_s3_keys = [x.strip() for x in content]

    def read_re_archive_complete_file(self):
        """Reads the re-archive complete file to get the list of files already re-archived

        return: None
        """
        log = logging.getLogger(self.cls_logger + '.read_re_archive_complete_file')

        # Ensure the file is found
        if not os.path.isfile(self.dirs.re_archive_complete_file):
            log.warning('No re-archive complete file found: {f}'.format(f=self.dirs.re_archive_complete_file))
            return

        # Read the file contents
        with open(self.dirs.re_archive_complete_file, 'r') as f:
            content = f.readlines()
        self.re_archive_complete_s3_keys = [x.strip() for x in content]

    def process_re_archive(self):
        """Runs through the re-archiving process on the S3 keys listed in the rearchive.txt file

        returns: None
        raises: ArchiverError
        """
        log = logging.getLogger(self.cls_logger + '.process_re_archive')
        self.read_re_archive_file()
        self.read_re_archive_complete_file()
        if len(self.re_archive_s3_keys) < 1:
            raise ArchiverError('So S3 keys found in the reachive.txt file')
        try:
            s3 = S3Util(_bucket_name=self.s3_bucket)
        except S3UtilError as exc:
            raise ArchiverError('Problem connecting to S3 bucket: {b}'.format(b=self.s3_bucket)) from exc
        s3_keys = s3.find_keys(regex='')
        if not s3_keys:
            raise ArchiverError('No keys found in S3 bucket: {b}'.format(b=self.s3_bucket))

        for re_archive_s3_key in self.re_archive_s3_keys:
            if re_archive_s3_key in s3_keys:
                if re_archive_s3_key not in self.re_archive_complete_s3_keys:
                    log.info('Found S3 key, not already re-archived: {k}'.format(k=re_archive_s3_key))
                    self.filtered_keys.append(re_archive_s3_key)
                else:
                    log.info('Found S3 key, already re-archived: {k}'.format(k=re_archive_s3_key))
            else:
                log.warning('Matching S3 key not found for: {k}'.format(k=re_archive_s3_key))

        # Create the archive_files directory
        if not os.path.isdir(self.dirs.archive_files_dir):
            log.info('Creating directory: {d}'.format(d=self.dirs.archive_files_dir))
            os.makedirs(self.dirs.archive_files_dir, exist_ok=True)

        log.info('Creating a list of threads...')
        for filtered_key in self.filtered_keys:
            self.threads.append(ReArchiverHandler(
                s3=s3,
                dirs=self.dirs,
                s3_key=filtered_key,
                s3_bucket=self.s3_bucket
            ))
        log.info('Added {n} threads'.format(n=str(len(self.threads))))

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

        # Cleaning up files
        log.info('Cleaning up files from successful re-archives...')
        for re_archive_handler in self.threads:
            if not re_archive_handler.failed_re_archive:
                re_archive_handler.clean()

        # Check for failures
        successful_re_archives = ''
        failed_re_archives = ''
        for re_archive_handler in self.threads:
            if re_archive_handler.failed_re_archive:
                log.warning('Detected failed re-archive: {a}'.format(a=re_archive_handler.s3_key))
                failed_re_archives += re_archive_handler.s3_key + '\n'
            else:
                successful_re_archives += re_archive_handler.s3_key + '\n'

        if successful_re_archives == '':
            log.warning('No successful re-archives detected!')
        else:
            log.info('Adding successful archives to file: {f}'.format(f=self.dirs.re_archive_complete_file))
            with open(self.dirs.re_archive_complete_file, 'a') as f:
                f.write(successful_re_archives)

        if failed_re_archives == '':
            log.info('No failed re-archives detected!')
        else:
            log.info('Adding failed archives to file: {f}'.format(f=self.dirs.failed_re_archive_file))
            with open(self.dirs.failed_re_archive_file, 'a') as f:
                f.write(failed_re_archives)
        log.info('Completed processing re-archives!')


class ReArchiverHandler(threading.Thread):

    def __init__(self, s3, dirs, s3_key, s3_bucket):
        threading.Thread.__init__(self)
        self.cls_logger = mod_logger + '.ReArchiverHandler'
        self.s3 = s3
        self.dirs = dirs
        self.s3_key = s3_key
        self.s3_bucket = s3_bucket
        self.failed_re_archive = False
        self.downloaded_file = None
        self.dir_to_archive = None

    def re_archive(self):
        """Process re-archiving the S3 key

        return: None
        """
        log = logging.getLogger(self.cls_logger + '.re_archive')
        log.info('Attempting to download: {k}'.format(k=self.s3_key))
        try:
            self.downloaded_file = self.s3.download_file_by_key(key=self.s3_key, dest_dir=self.dirs.archive_files_dir)
        except S3UtilError as exc:
            self.failed_re_archive = True
            raise ArchiverError('Problem downloading key: {k}'.format(k=self.s3_key)) from exc
        if not self.downloaded_file:
            self.failed_re_archive = True
            raise ArchiverError('Downloaded file not found for s3 key: {k}'.format(k=self.s3_key))
        log.info('Attempting to unzip: {f}'.format(f=self.downloaded_file))
        try:
            self.dir_to_archive = unzip_archive(zip_file=self.downloaded_file, output_dir=self.dirs.archive_files_dir)
        except ZipError as exc:
            self.failed_re_archive = True
            raise ArchiverError('Problem extracting zip file: {z} to directory: {d}'.format(
                z=self.downloaded_file, d=self.dirs.auto_import_dir)) from exc
        log.info('Using extracted archive directory: {d}'.format(d=self.dir_to_archive))

        # Process archiving the directory
        a = Archiver(dir_to_archive=self.dir_to_archive, media_inbox=self.dirs.media_inbox)
        try:
            a.process_archive()
        except ArchiverError as exc:
            self.failed_re_archive = True
            raise ArchiverError('Problem creating archive for: {s}'.format(s=self.dir_to_archive)) from exc
        log.info('Archive zip files created')

        log.info('Uploading to S3 bucket: {b}'.format(b=self.s3_bucket))
        try:
            a.upload_to_s3(bucket_name=self.s3_bucket)
        except ArchiverError as exc:
            raise ArchiverError('Problem uploading to S3 bucket: {b}'.format(b=self.s3_bucket)) from exc
        for new_archive in a.archive_zip_list:
            new_archive = new_archive.split(os.sep)[-1]
            log.info('Created and uploaded new archive from {a}: {n}'.format(a=self.s3_key, n=new_archive))
        a.clean()
        log.info('Completed re-archiving: {a}'.format(a=self.s3_key))

    def run(self):
        self.re_archive()

    def clean(self):
        """Removes downloaded files

        return: None
        """
        log = logging.getLogger(self.cls_logger + '.clean')
        if self.downloaded_file:
            log.info('Removing file: {f}'.format(f=self.downloaded_file))
            os.remove(self.downloaded_file)
        if self.dir_to_archive:
            if os.path.isdir(self.dir_to_archive):
                log.info('Removing archive directory: {d}'.format(d=self.dir_to_archive))
                shutil.rmtree(self.dir_to_archive)


def get_file_creation_time(file_path):
    """Returns the creation time of the file depending on the platform

    """
    if platform.system() == 'Windows':
        return os.path.getctime(file_path)
    else:
        stat = os.stat(file_path)
        try:
            return stat.st_birthtime
        except AttributeError:
            # We're probably on Linux. No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return stat.st_mtime


def get_timestamp(elem):
    return elem.creation_time


def read_archive_text(archive_text_path):
    """Reads archive.txt file

    :param archive_text_path: (str) path to the archive.txt file for an archive
    :return: (dict) archive meta data
    :raises: ArchiverError
    """
    if not os.path.isfile(archive_text_path):
        msg = 'archive.txt file not found: {f}'.format(f=archive_text_path)
        raise ArchiverError(msg)
    text_file_name = archive_text_path.split(os.sep)[-1]
    if text_file_name != 'archive.txt':
        msg = 'File name {f} must be archive.txt'.format(f=text_file_name)
        raise ArchiverError(msg)
    archive_data = {}
    with open(archive_text_path, 'r') as f:
        content = f.readlines()
    for line in content:
        if line.startswith('Created by mediamantis version:'):
            archive_data['MantisVersion'] = line.split(':')[-1]
        if line.startswith('Created on:'):
            archive_data['CreatedOn'] = line.split(':')[-1]
        if line.startswith('Created from:'):
            archive_data['CreatedFrom'] = line.split(':')[-1]
        if line.startswith('Using ID word:'):
            archive_data['IdWord'] = line.split(':')[-1]
        if line.startswith('Library:'):
            archive_data['Library'] = line.split(':')[-1]

    # Ensure all the required data was found
    if not all(x in ['MantisVersion', 'CreatedOn', 'CreatedFrom', 'IdWord'] for x in archive_data.keys()):
        msg = 'Data missing from archive.txt file: MantisVersion, CreatedOn, CreatedFrom, or IdWord'
        raise ArchiverError(msg)

    # Ensure library is set (even if none)
    if 'Library' not in archive_data.keys():
        archive_data['Library'] = 'default'
    return archive_data
