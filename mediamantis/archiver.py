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

from pycons3rt3.bash import zip_dir, CommandError
from pycons3rt3.logify import Logify
from pycons3rt3.s3util import S3Util
import requests

from .exceptions import ArchiverError
from .mantistypes import ArchiveStatus, MediaFileType
from .mediafile import MediaFile
from .settings import extensions, local_dirs, max_archive_size_bytes, skip_items


mod_logger = Logify.get_name() + '.archiver'

word_file = '/usr/share/dict/words'
word_site = 'https://svnweb.freebsd.org/csrg/share/dict/words?view=co&content-type=text/plain'


class Archiver(threading.Thread):

    def __init__(self, dir_to_archive):
        threading.Thread.__init__(self)
        self.cls_logger = mod_logger + '.Archiver'
        self.dir_to_archive = dir_to_archive
        self.archive_files_dir = local_dirs['archive_files_dir']
        self.current_archive_size_bytes = 0
        if os.path.isfile(word_file):
            self.words = open(word_file).read().splitlines()
        else:
            response = requests.get(word_site)
            self.words = response.content.splitlines()
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
        for archive_dir in self.archive_dir_list:
            log.info('Found archive dir to zip: {d}'.format(d=archive_dir))
            zip_path = archive_dir + '.zip'
            try:
                zip_dir(dir_path=archive_dir, zip_file=zip_path)
            except CommandError as exc:
                raise ArchiverError('Problem creating zip file: {z}'.format(z=zip_path)) from exc
            self.archive_zip_list.append(zip_path)
            log.info('Created archive zip: {z}'.format(z=zip_path))

    def upload_to_s3(self, bucket_name):
        """Uploads the zip archives to AWS S3 buckets

        :param bucket_name: (str) name of the S3 bucket to upload to
        :return: None
        :raises: ArchiverError
        """
        log = logging.getLogger(self.cls_logger + '.upload_to_s3')
        s3 = S3Util(_bucket_name=bucket_name)
        log.info('Attempting to upload archive zip files to S3 bucket: {b}'.format(b=bucket_name))
        for archive_zip in self.archive_zip_list:
            log.info('Uploading zip to S3: {z}'.format(z=archive_zip))
            key = archive_zip.split(os.sep)[-1]
            if not s3.upload_file(filepath=archive_zip, key=key):
                raise ArchiverError('Problem uploading zip [{z}] to bucket {b} with key: {k}'.format(
                    z=archive_zip, b=bucket_name, k=key
                ))
            log.info('Completed uploading key: {k}'.format(k=key))

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
            raise ArchiverError('Problem scanning archive') from exc

        # Exit if no media files are found
        if len(self.media_files) < 1:
            log.info('No media files found to archive')
            return

        # Create the archive directory
        try:
            os.makedirs(self.archive_files_path, exist_ok=True)
        except Exception as exc:
            raise ArchiverError('Problem creating directory: {d}'.format(d=self.archive_files_path)) from exc

        # Ensure the destination has enough space
        if not self.verify_disk_space():
            raise ArchiverError('Insufficient disk space available to create archives')

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
                    raise ArchiverError('Last timestamp not found to create archive directory name')
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
                raise ArchiverError('Problem archiving media file: {f}'.format(f=str(media_file))) from exc
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
            raise ArchiverError('Problem creating zip archives') from exc


def get_timestamp(elem):
    return elem.creation_time


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
