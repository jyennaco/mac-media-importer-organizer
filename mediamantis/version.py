# -*- coding: utf-8 -*-

"""
mediamantis.version
~~~~~~~~~~~~~~~~~~~
Returns the version

"""

import pkg_resources


def version():
    mantis_version = pkg_resources.get_distribution('mediamantis').version
    print('mediamantis version: ' + mantis_version)
    return mantis_version
