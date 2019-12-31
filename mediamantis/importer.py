# -*- coding: utf-8 -*-

"""
mediamantis.importer
~~~~~~~~~~~~~~~~~~~
Imports media files from a variety of sources

"""

import datetime
import enum
import logging
import random
import os
import platform
import shutil
import threading

from pycons3rt3.logify import Logify
from pycons3rt3.s3util import S3Util, S3UtilError
import requests

from .exceptions import ImporterError
from .settings import extensions, local_dirs


mod_logger = Logify.get_name() + '.importer'


class Importer(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.cls_logger = mod_logger + '.Importer'

