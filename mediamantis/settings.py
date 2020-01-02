# -*- coding: utf-8 -*-

"""
mediamantis.settings
~~~~~~~~~~~~~~~~~~~
This module contains the set of settings for mediamantis
"""

import os
import platform

from pycons3rt3.dyndict import DynDict


"""
File extension lists are used to determine the type of media file
capitalized versions will be checked so they do not need to be defined 
here.
"""
extensions = {
    'pics': [
        'aae',
        'bmp',
        'gif',
        'heic',
        'jpg',
        'jpeg',
        'png',
        'tif',
        'tiff'
    ],
    'vids': [
        'avi',
        '3gp',
        'mov',
        'm4v',
        'mp4',
        'mpg',
        'wmv'
    ],
    'audio': [
        'aac',
        'flac'
        'm4a',
        'm4p',
        'mp3',
        'wav',
        'webm',
        'wma'
    ]
}

"""
Files to skip archiving
"""
skip_items = {
    'files': [
        '.DS_Store'
    ],
    'extensions': [
        'zip'
    ],
    'prefixes': [
        '._',
        '~'
    ]
}

"""
Directories used to stage files in directories
"""
local_dirs = DynDict({
    'media_root': os.path.join(os.path.expanduser('~')),
    'desktop_dir': lambda self: self['media_root'] + os.sep + 'Desktop',
    'picture_dir': lambda self: self['media_root'] + os.sep + 'Pictures',
    'music_dir': lambda self: self['media_root'] + os.sep + 'Music',
    'movie_dir': lambda self: self['media_root'] + os.sep + 'Movies' if platform.system() != 'Windows' else
    lambda self: self['media_root'] + os.sep + 'Videos',
    'media_inbox': lambda self: self['media_root'] + os.sep + 'Desktop' + os.sep + 'Media_Inbox'
    if os.path.isdir(self['desktop_dir']) else lambda self: self['media_root'] + os.sep + 'Media_Inbox',
    'auto_import_dir': lambda self: self['media_inbox'] + os.sep + 'auto_import',
    'working_dir': lambda self: self['media_root'] + os.sep + '.mediamantis',
    'archive_files_dir': lambda self: self['media_inbox'] + os.sep + 'archive_files'
})

"""
Archive size used to determine the maximum size of the zip archive bundles
"""
max_archive_size_bytes = 2000000000
