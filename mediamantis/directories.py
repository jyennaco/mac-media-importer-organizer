# -*- coding: utf-8 -*-

"""
mediamantis.directories
~~~~~~~~~~~~~~~~~~~
This module contains a class for managing directories
"""

import os
import platform

from .mantistypes import mantis_import_shell_script_contents, mantis_mega_upload_shell_script_contents

# Default directory name for the media inbox
media_inbox_dir_name = 'Media_Inbox'

# File names for the media import and upload scripts
script_mantis_import_name = 'mantis_importer.sh'
script_mantis_upload_name = 'mega_uploader.sh'


class Directories(object):

    def __init__(self, media_root=None, media_inbox=None, library=None):
        """Initialize the Directories object

        :param media_root: (str) Full path to the media room to import to
        media_root is the root directory for importing under: Pictures, Movies, etc.
        The default if not provided is the user home directory.  This can be used to
        import and organize media file onto an external drive.

        :param media_inbox: (str) Full path to the mantis media inbox
        media_inbox is the main mantis directory.  This directory is used for staging
        files to archive, import, and other reasons.  mantis will read its configuration
        from here, output log files, look for files to import, etc. under the media_inbox.

        :param library: (str)
        library is not required but will be used when provided as a subdirectory
        of the media_root.  It was originally more useful but overcome by better
        core functionality.  This may be deprecated at some point.

        """
        # Determine media root, default is the home dir, otherwise use the provided media root
        self.media_root = os.path.expanduser('~')
        if media_root:
            self.media_root = media_root

        # If a library was provided, append its path to the media root to become the actual media root
        if library:
            self.media_root += os.sep + library

        # Determine the .mantis directory under media root
        self.mantis_dir = self.media_root + os.sep + '.mantis'

        # Determine the top media inbox directory
        if os.path.isdir(os.path.join(os.path.expanduser('~'), 'Desktop')):
            self.media_inbox = os.path.join(os.path.expanduser('~'), 'Desktop', media_inbox_dir_name)
        else:
            self.media_inbox = os.path.join(os.path.expanduser('~'), media_inbox_dir_name)
        if media_inbox:
            self.media_inbox = media_inbox

        # Media root paths
        self.picture_dir = None
        self.music_dir = None
        self.movie_dir = None
        self.set_media_root_dirs()

        # Media inbox paths
        self.auto_import_dir = None
        self.archive_files_dir = None
        self.conf_dir = None
        self.failed_imports_file = None
        self.failed_re_archive_file = None
        self.import_complete_file = None
        self.imports_dir = None
        self.log_dir = None
        self.re_archive_file = None
        self.re_archive_complete_file = None
        self.scripts_dir = None
        self.slack_webhook_file = None
        self.import_dirs_file = None

        # Set the media inbox directory values
        self.set_media_inbox_dirs()

    def __str__(self):
        return str(self.get_local_dirs())

    def create_mantis_dirs(self):
        """Creates the basic mantis directories

        :return: None
        """
        os.makedirs(self.media_inbox, exist_ok=True)
        os.makedirs(self.conf_dir, exist_ok=True)
        os.makedirs(self.imports_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.scripts_dir, exist_ok=True)

    def create_mantis_scripts(self):
        """Creates the mantis scripts in the scripts directory

        :return: None
        """
        # Create the import script
        script_mantis_import_path = os.path.join(self.scripts_dir, script_mantis_import_name)
        script_mantis_upload_path = os.path.join(self.scripts_dir, script_mantis_upload_name)

        # Delete existing scripts
        if os.path.exists(script_mantis_import_path):
            os.remove(script_mantis_import_path)
        if os.path.exists(script_mantis_upload_path):
            os.remove(script_mantis_upload_path)

        # Create the import script
        with open(script_mantis_import_path, 'w') as f:
            f.write(mantis_import_shell_script_contents)

        # Create the upload script
        with open(script_mantis_upload_path, 'w') as f:
            f.write(mantis_mega_upload_shell_script_contents)

        # Set permissions
        os.chmod(script_mantis_import_path, 0o755)
        os.chmod(script_mantis_upload_path, 0o755)

    def get_local_dirs(self):
        return {
            'archive_files_dir': self.archive_files_dir,
            'auto_import_dir': self.auto_import_dir,
            'conf_dir': self.conf_dir,
            'imports_dir': self.imports_dir,
            'log_dir': self.log_dir,
            'mantis_dir': self.mantis_dir,
            'media_inbox': self.media_inbox,
            'media_root': self.media_root,
            'movie_dir': self.movie_dir,
            'music_dir': self.music_dir,
            'picture_dir': self.picture_dir,
            'scripts_dir': self.scripts_dir
        }

    def get_mantis_dir(self):
        return self.mantis_dir

    def set_library(self, library):
        self.media_root += os.sep + library
        self.set_media_root_dirs()

    def set_media_inbox_dirs(self):
        self.scripts_dir = os.path.join(self.media_inbox, 'scripts')
        self.log_dir = os.path.join(self.media_inbox, 'log')
        self.conf_dir = os.path.join(self.media_inbox, 'conf')
        self.imports_dir = os.path.join(self.media_inbox, 'imports')
        self.auto_import_dir = self.media_inbox + os.sep + 'auto_import'
        self.archive_files_dir = self.media_inbox + os.sep + 'archive_files'
        self.import_complete_file = os.path.join(self.auto_import_dir, 'completed_imports.txt')
        self.failed_imports_file = os.path.join(self.auto_import_dir, 'failed_imports.txt')
        self.re_archive_file = os.path.join(self.archive_files_dir, 'rearchive.txt')
        self.re_archive_complete_file = os.path.join(self.archive_files_dir, 'rearchive_complete.txt')
        self.failed_re_archive_file = os.path.join(self.archive_files_dir, 'rearchive_failed.txt')
        self.slack_webhook_file = os.path.join(self.conf_dir, 'slack.txt')
        self.import_dirs_file = os.path.join(self.conf_dir, 'import_dirs.txt')

    def set_media_root_dirs(self):
        self.picture_dir = self.media_root + os.sep + 'Pictures'
        self.music_dir = self.media_root + os.sep + 'Music'
        if platform.system() != 'Windows':
            self.movie_dir = self.media_root + os.sep + 'Movies'
        else:
            self.movie_dir = self.media_root + os.sep + 'Videos'
