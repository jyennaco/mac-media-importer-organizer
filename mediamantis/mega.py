# -*- coding: utf-8 -*-

"""
mediamantis.mega
~~~~~~~~~~~~~~~~~~~
Integrates with privacy-focus E2E encrypted cloud provider MEGA.nz using the MegaCMD CLI tool.

References:
    * https://github.com/meganz/MEGAcmd/blob/master/UserGuide.md
    * https://mega.nz/cmd

"""

import datetime
from .exceptions import MegaError
import logging
import os
import threading

from pycons3rt3.bash import run_command
from pycons3rt3.exceptions import CommandError
from pycons3rt3.logify import Logify
from pycons3rt3.slack import SlackAttachment, SlackMessage


mod_logger = Logify.get_name() + '.mega'


class MegaCmd(object):
    """Handles interactions with the MEGA CMD command line interface

    """
    def __init__(self):
        self.cls_logger = mod_logger + '.MegaCmd'

    def put(self, local_path_list, remote_destination_path=None, queue_command=False):
        """Puts a file onto the remote Mega cloud server

        https://github.com/meganz/MEGAcmd/blob/master/UserGuide.md#put

        :param local_path_list: (List) Of string local files and/or folders to upload
        :param remote_destination_path: (str) Remote path on Mega cloud to upload to. Default is current working
            remote directory.
        :param queue_command: (bool) Set true to enqueue the upload and move on without waiting for a response.
            Translates to the -q option in the docs.
        :return: (bool) True if successful, False if an error occurred
        :raises: MegaError
        """
        log = logging.getLogger(self.cls_logger + '.put')

        # Build the base command
        base_command = 'mega-put'
        command = [base_command, '-c', '--ignore-quota-warn']

        # Add the -q if queue is True
        if queue_command:
            command.append('-q')

        # Ensure local_path_list is a list
        if not isinstance(local_path_list, list):
            raise MegaError('Expected a list for local_path_list, found: {t}'.format(
                t=local_path_list.__class__.__name__))

        # Ensure each local file exists and is a file
        for local_path in local_path_list:
            # Ensure the file or folder exists
            if not os.path.exists(local_path):
                raise MegaError('Nothing exists locally at the provided location: {f}'.format(f=local_path))
            # Add the local file or folder to the command
            command.append(local_path)

        # Add the remote path if provided
        if remote_destination_path:
            command.append(remote_destination_path)

        # Log the command
        command_str = ' '.join(command)
        log.info('Running MEGA CMD command: [{c}]'.format(c=command_str))

        # Run the MegaCMD command
        try:
            result = run_command(command, timeout_sec=600)
        except CommandError as exc:
            raise MegaError('Problem detected running: {c}'.format(c=command_str)) from exc
        if result['code'] != 0:
            msg = 'MegaCMD command [{m}] exited with non-zero code [{c}] and output:\n{o}'.format(
                m=command_str, c=str(result['code']), o=result['output'])
            raise MegaError(msg)


class MegaUploader(threading.Thread):
    """TBD

    Uploads files to MEGA cloud mutli-threaded
    """

    def __init__(self, slack_webhook_url=None, slack_channel=None, slack_text=None):
        threading.Thread.__init__(self)
        self.cls_logger = mod_logger + '.ScriptRunner'
        self.timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.slack_webhook_url = slack_webhook_url
        self.slack_text = slack_text
        if all([slack_webhook_url, slack_channel, slack_text]):
            self.slack_msg = SlackMessage(
                slack_webhook_url,
                channel=slack_channel,
                text=self.timestamp + ': ' + self.slack_text
            )
        else:
            self.slack_msg = None
        self.output = None
