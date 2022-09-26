# -*- coding: utf-8 -*-

"""
mediamantis.directories
~~~~~~~~~~~~~~~~~~~
This module contains a class for managing directories
"""

import os
import platform

media_inbox_dir_name = 'Media_Inbox'


class Directories(object):

    def __init__(self, media_root=None, media_inbox=None, library=None):
        # Determine the top media root directory

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
        self.import_complete_file = None
        self.failed_imports_file = None
        self.re_archive_file = None
        self.re_archive_complete_file = None
        self.failed_re_archive_file = None
        self.slack_webhook_file = None
        self.set_media_inbox_dirs()

    def __str__(self):
        return str(self.get_local_dirs())

    def get_local_dirs(self):
        return {
            'media_root': self.media_root,
            'mantis_dir': self.mantis_dir,
            'picture_dir': self.picture_dir,
            'music_dir': self.music_dir,
            'movie_dir': self.movie_dir,
            'media_inbox': self.media_inbox,
            'auto_import_dir': self.auto_import_dir,
            'archive_files_dir': self.archive_files_dir
        }

    def get_mantis_dir(self):
        return self.mantis_dir

    def set_library(self, library):
        self.media_root += os.sep + library
        self.set_media_root_dirs()

    def set_media_inbox_dirs(self):
        self.auto_import_dir = self.media_inbox + os.sep + 'auto_import'
        self.archive_files_dir = self.media_inbox + os.sep + 'archive_files'
        self.import_complete_file = os.path.join(self.auto_import_dir, 'completed_imports.txt')
        self.failed_imports_file = os.path.join(self.auto_import_dir, 'failed_imports.txt')
        self.re_archive_file = os.path.join(self.archive_files_dir, 'rearchive.txt')
        self.re_archive_complete_file = os.path.join(self.archive_files_dir, 'rearchive_complete.txt')
        self.failed_re_archive_file = os.path.join(self.archive_files_dir, 'rearchive_failed.txt')
        self.slack_webhook_file = os.path.join(self.media_inbox, 'slack.txt')

    def set_media_root_dirs(self):
        self.picture_dir = self.media_root + os.sep + 'Pictures'
        self.music_dir = self.media_root + os.sep + 'Music'
        if platform.system() != 'Windows':
            self.movie_dir = self.media_root + os.sep + 'Movies'
        else:
            self.movie_dir = self.media_root + os.sep + 'Videos'
