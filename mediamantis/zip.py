# -*- coding: utf-8 -*-

"""
mediamantis.zip
~~~~~~~~~~~~~~~~~~~
Handles zipping and unzipping archive files while preserving metadata

"""

import contextlib
import logging
import os
import time
import zipfile

from pycons3rt3.logify import Logify

from .exceptions import ZipError
from .settings import skip_items


mod_logger = Logify.get_name() + '.zip'

test_zip = '/Users/yennaco/Desktop/Media_Inbox/auto_import/20190113-20200103_colin.zip'
out_dir = '/Users/yennaco/Desktop/Media_Inbox/auto_import/20190113-20200103_colin'


def unzip_archive(zip_file, output_dir):
    """Unzip an archive while retaining the file modified time

    :param zip_file: (str) full path to the zip file to extract
    :param output_dir: (str)

    return: (str) path to output directory containing the files
    """
    log = logging.getLogger(mod_logger + '.unzip_archive')
    zip_file_name = zip_file.split(os.sep)[-1]
    extracted_dir_name = zip_file_name.split('.')[0]
    extracted_dir_path = os.path.join(output_dir, extracted_dir_name)
    if not os.path.isdir(extracted_dir_path):
        log.info('Creating extraction directory: {d}'.format(d=extracted_dir_path))
        os.makedirs(extracted_dir_path, exist_ok=True)
    log.info('Extracting zip file {z} to directory: {d}'.format(z=zip_file, d=extracted_dir_path))
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        for f in zip_ref.infolist():
            name, date_time = f.filename, f.date_time
            skip = False
            for skip_prefix in skip_items['prefixes']:
                if name.startswith(skip_prefix):
                    skip = True
            if skip:
                log.debug('Skipping item with a skippable prefix: {f}'.format(f=name))
                continue
            name = os.path.join(output_dir, name)
            log.debug('Extracting file: {n}'.format(n=name))
            if os.path.isfile(name):
                try:
                    with open(name, 'wb') as outFile:
                        outFile.write(zip_ref.open(f).read())
                except IsADirectoryError as exc:
                    log.warning('Skipping directory: {d}'.format(d=name))
                    continue
            elif os.path.isdir(name):
                log.debug('Skipping directory: {d}'.format(d=name))
                continue
            else:
                log.debug('Skipping archive item, not sure of type: {i}'.format(i=name))
                continue
            date_time = time.mktime(date_time + (0, 0, -1))
            os.utime(name, (date_time, date_time))
    log.info('Completed extraction to directory: {d}'.format(d=extracted_dir_path))
    return extracted_dir_path


def zip_dir(dir_path, zip_file):
    """Creates a zip file of a directory tree

    This method creates a zip archive using the directory tree dir_path
    and adds to zip_file output.

    :param dir_path: (str) Full path to directory to be zipped
    :param zip_file: (str) Full path to the output zip file
    :return: None
    :raises ZipError
    """
    log = logging.getLogger(mod_logger + '.zip_dir')

    # Validate args
    if not isinstance(dir_path, str):
        msg = 'dir_path argument must be a string'
        log.error(msg)
        raise ZipError(msg)
    if not isinstance(zip_file, str):
        msg = 'zip_file argument must be a string'
        log.error(msg)
        raise ZipError(msg)

    # Ensure the dir_path file exists
    if not os.path.isdir(dir_path):
        msg = 'Directory not found: {f}'.format(f=dir_path)
        log.error(msg)
        raise ZipError(msg)

    try:
        with contextlib.closing(zipfile.ZipFile(zip_file, 'w', allowZip64=True)) as zip_w:
            for root, dirs, files in os.walk(dir_path):
                for f in files:
                    log.debug('Adding file to zip: %s', f)
                    strip = len(dir_path) - len(os.path.split(dir_path)[-1])
                    file_name = os.path.join(root, f)
                    archive_name = os.path.join(root[strip:], f)
                    zip_w.write(file_name, archive_name)
    except Exception as exc:
        raise ZipError('Unable to create zip file: {f}'.format(f=zip_file)) from exc
    log.info('Successfully created zip file: {f}'.format(f=zip_file))
