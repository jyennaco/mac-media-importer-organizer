# -*- coding: utf-8 -*-

"""
mediamantis.mantisreader
~~~~~~~~~~~~~~~~~~~
Reads import files from a MEDIA_IMPORT_ROOT/.mantis directory

Sample:

{
  "import_timestamp": "20220925_174532",
  "source_directory": "/Users/my_user/Desktop/Media_Inbox/20220925_iPhone_import",
  "source_directory_name": "20220925_iPhone_import",
  "s3_bucket": "None",
  "s3_key": "None",
  "s3_downloaded_file": "None",
  "media_inbox": "/Users/my_user/Desktop/Media_Inbox",
  "auto_import_dir": "/Users/my_user/Desktop/Media_Inbox/auto_import",
  "archive_files_dir": "/Users/my_user/Desktop/Media_Inbox/archive_files",
  "library": "None",
  "media_import_root_directory": "/Volumes/BACKUP21/my-media-folder",
  "unimport": "False",
  "imports": [
    {
      "file_path": "/Users/my_user/Desktop/Media_Inbox/20220925_iPhone_import/IMG_7941.HEIC",
      "file_name": "IMG_7941.HEIC",
      "creation_time": "20220417-184805",
      "size_bytes": 1379353,
      "file_type": "PICTURE",
      "archive_status": "PENDING",
      "import_status": "COMPLETED",
      "destination_path": "None",
      "import_path": "/Volumes/BACKUP21/my-media-folder/Pictures/2022/2022-04/2022-04-17_184805_IMG_7941.HEIC"
    }
  ],
  "results": {
    "total_import_count": 280,
    "picture_import_count": 248,
    "movie_import_count": 32,
    "audio_import_count": 0,
    "already_imported_count": 0,
    "not_imported_count": 0,
    "un_imported_count": 0
  }
}
"""

import json
import logging
import os

from pycons3rt3.logify import Logify

from .exceptions import MantisError
from .mantistypes import ImportStatus, map_import_status


mod_logger = Logify.get_name() + '.mantisreader'


class MantisReader(object):
    """Handles reading mantis files given a media root directory
    """

    def __init__(self, media_import_root):
        self.cls_logger = mod_logger + '.MantisReader'
        self.media_import_root = media_import_root
        self.completed_import_paths = []
        self.mantis_file_content_list = []
        self.completed_reading_mantis_import_files = False

    def get_completed_imports(self):
        """Returns a list of completed imports by import path

        :return: (list) of string import paths
        :raises: MantisError
        """
        log = logging.getLogger(self.cls_logger + '.get_completed_imports')
        if not self.completed_reading_mantis_import_files:
            self.read_mantis_imports()

        log.info('Scanning mantis data for completed imports...')

        # Store the completed imports that have paths that exist locally
        completed_import_paths = []

        # Import paths not found locally, likely imported on another machine
        not_found_imports = []

        # Count of total imports found
        import_count = 0

        for mantis_data in self.mantis_file_content_list:
            if 'imports' not in mantis_data.keys():
                log.warning('imports data not found in mantis data: {d}'.format(d=str(mantis_data)))
                continue
            if not isinstance(mantis_data['imports'], list):
                log.warning('Found imports data but it is not a list: {d}'.format(d=str(mantis_data['imports'])))
                continue
            for mantis_import in mantis_data['imports']:
                if 'import_status' not in mantis_import.keys():
                    log.warning('import_status not found in import data: {d}'.format(d=str(mantis_import)))
                    continue
                if 'import_path' not in mantis_import.keys():
                    log.warning('import_path not found in import data: {d}'.format(d=str(mantis_import)))
                    continue
                import_status = map_import_status(import_status_str=mantis_import['import_status'])
                import_path = mantis_import['import_path']
                import_count += 1
                if import_status == ImportStatus.COMPLETED:
                    if os.path.isfile(import_path):
                        log.debug('Found import marked as completed: {f}'.format(f=import_path))
                        completed_import_paths.append(import_path)
                    else:
                        log.debug('Import marked completed but file not found, not adding to the list of potential '
                                  'imports: {f}'.format(f=import_path))
                        not_found_imports.append(import_path)

        # Eliminate duplicates
        completed_import_paths = list(set(completed_import_paths))
        self.completed_import_paths = completed_import_paths

        # Log results
        log.info('Found {n} total imports in {f} import files'.format(
            n=str(import_count), f=str(len(self.mantis_file_content_list))))
        log.info('Found {n} imports that were not found locally, likely imported from another machine'.format(
            n=str(len(not_found_imports))))
        log.info('Found {n} completed imports that exist locally'.format(n=str(len(completed_import_paths))))
        return completed_import_paths

    def read_mantis_import_file(self, import_file_path):
        """Reads the import JSON file at the provided path, and returns a list of completed imports

        :param import_file_path: (str) Path to the JSON import file
        :return: (dict) Containing the loaded contents of the file
        :raises: MantisError
        """
        log = logging.getLogger(self.cls_logger + '.read_mantis_import_file')

        # Ensure the import file exists
        if not os.path.isfile(import_file_path):
            msg = 'Import file not found: {d}'.format(d=import_file_path)
            raise MantisError(msg)

        # Load the JSON content
        log.debug('Reading mantis import file: {f}'.format(f=import_file_path))
        try:
            with open(import_file_path, 'r') as f:
                json_content = f.read()
            import_file_contents = json.loads(json_content)
        except Exception as exc:
            msg = 'Problem loading JSON from file: {f}\n{e}'.format(f=import_file_path, e=str(exc))
            raise MantisError(msg) from exc
        return import_file_contents

    def read_mantis_imports(self):
        """Reads the imports files from the .mantis directory and compiles a list of completed import paths

        :return: (list) of str file paths, one for each completed import
        :raises: MantisError
        """
        log = logging.getLogger(self.cls_logger + '.read_mantis_imports')

        import_paths = []

        # Exit if the media import root directory was not found
        if not os.path.isdir(self.media_import_root):
            msg = 'Media import root directory not found: {d}'.format(d=self.media_import_root)
            raise MantisError(msg)

        log.info('Reading mantis import from media import root: {d}'.format(d=self.media_import_root))

        # Ensure the .mantis directory exists, if not assume no imports have been done and return
        mantis_dir = os.path.join(self.media_import_root, '.mantis')
        if not os.path.isdir(mantis_dir):
            log.info('.mantis directory not found [{d}] no imports done on to this media import root'.format(
                d=mantis_dir))
            return import_paths
        
        # Get a list of import files (starting with import and ending with .json)
        log.info('Getting a list of mantis import files...')
        mantis_file_paths = []
        mantis_dir_files = os.listdir(mantis_dir)
        for mantis_dir_file in mantis_dir_files:
            if mantis_dir_file.startswith('import_') and mantis_dir_file.endswith('.json'):
                mantis_file_paths.append(os.path.join(mantis_dir, mantis_dir_file))
        log.info('Found {n} import files in mantis dir: {d}'.format(n=str(len(mantis_file_paths)), d=mantis_dir))

        # Try to JSON import content from each mantis import file
        mantis_file_content_list = []
        mantis_file_fail_list = []
        for mantis_file_path in mantis_file_paths:
            try:
                mantis_file_content = self.read_mantis_import_file(import_file_path=mantis_file_path)
            except MantisError as exc:
                log.warning('Unable to load content from mantis import file: {f}\n{e}'.format(
                    f=mantis_file_path, e=str(exc)))
                mantis_file_fail_list.append(mantis_file_path)
                continue
            mantis_file_content_list.append(mantis_file_content)
        log.info('Loaded mantis file content from {n} mantis files'.format(n=str(len(mantis_file_content_list))))
        if len(mantis_file_fail_list) > 0:
            log.info('Failed to load content from {n} mantis files'.format(n=str(len(mantis_file_fail_list))))
        self.mantis_file_content_list = mantis_file_content_list
        self.completed_reading_mantis_import_files = True
        return mantis_file_content_list
