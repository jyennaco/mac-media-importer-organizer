# -*- coding: utf-8 -*-

"""
mediamantis.settings
~~~~~~~~~~~~~~~~~~~
This module contains the set of settings for mediamantis
"""


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
Archive size used to determine the maximum size of the zip archive bundles
"""
max_archive_size_bytes = 2000000000
