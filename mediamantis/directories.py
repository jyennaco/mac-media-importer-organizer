# -*- coding: utf-8 -*-

"""
mediamantis.directories
~~~~~~~~~~~~~~~~~~~
This module contains a class for managing directories
"""

import os
import platform


class Directories(object):

    def __init__(self, media_root=None, media_inbox=None):
        if media_root:
            self.media_root = media_root
        else:
            self.media_root = os.path.join(os.path.expanduser('~'))
        self.desktop_dir = self.media_root + os.sep + 'Desktop'

        if media_inbox:
            self.media_inbox = media_inbox
        else:
            if os.path.isdir(self.desktop_dir):
                self.media_inbox = self.desktop_dir + os.sep + 'Media_Inbox'
            else:
                self.media_inbox = self.media_root + os.sep + 'Media_Inbox'

        self.picture_dir = self.media_root + os.sep + 'Pictures'
        self.music_dir = self.media_root + os.sep + 'Music'
        if platform.system() != 'Windows':
            self.movie_dir = self.media_root + os.sep + 'Movies'
        else:
            self.movie_dir = self.media_root + os.sep + 'Videos'

        self.auto_import_dir = self.media_inbox + os.sep + 'auto_import'
        self.archive_files_dir = self.media_inbox + os.sep + 'archive_files'
        self.import_complete_file = os.path.join(self.auto_import_dir, 'completed_imports.txt')
        self.failed_imports_file = os.path.join(self.auto_import_dir, 'failed_imports.txt')
        self.re_archive_file = os.path.join(self.archive_files_dir, 'rearchive.txt')
        self.re_archive_complete_file = os.path.join(self.archive_files_dir, 'rearchive_complete.txt')

        self.local_dirs = {
            'media_root': self.media_root,
            'desktop_dir': self.desktop_dir,
            'picture_dir': self.picture_dir,
            'music_dir': self.music_dir,
            'movie_dir': self.movie_dir,
            'media_inbox': self.media_inbox,
            'auto_import_dir': self.auto_import_dir,
            'archive_files_dir': self.archive_files_dir
        }

    def __str__(self):
        return str(self.local_dirs)

    def get_local_dirs(self):
        return self.local_dirs
