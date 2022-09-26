# -*- coding: utf-8 -*-

"""
mediamantis.mega
~~~~~~~~~~~~~~~~~~~
Integrates with privacy-focus E2E encrypted cloud provider MEGA.nz using the MegaCMD CLI tool.

References:
    * https://github.com/meganz/MEGAcmd/blob/master/UserGuide.md
    * https://mega.nz/cmd

Prerequisites:
    * Account with MEGA
    * MegaCMD App installed
    * MegaCMD server started and active

"""

import datetime
import json
import logging
import os
import threading
import time

from pycons3rt3.bash import run_command
from pycons3rt3.exceptions import CommandError
from pycons3rt3.logify import Logify
from pycons3rt3.slack import SlackAttachment, SlackMessage

from .directories import Directories
from .exceptions import MegaError
from .mantisreader import MantisReader

mod_logger = Logify.get_name() + '.mega'


class MantisMega(object):
    """Handles the integration with MEGAcmd
    """

    def __init__(self, media_import_root, mega_root):
        """Initializes a MantisMega handler

        :param media_import_root: (str) local path to the media import root directory
        :param mega_root: (str) remote path to the corresponding mega import directory "/" is the root of the account
        """
        self.cls_logger = mod_logger + '.MantisMega'
        self.media_import_root = media_import_root
        self.mega_root = mega_root
        self.mega_cmd = MegaCmd()
        self.dirs = Directories(media_root=media_import_root)
        self.mega_completion_file = os.path.join(self.dirs.mantis_dir, 'mega_completed_uploads.json')

    def get_completed_uploads(self):
        """Reads a file containing a list of files already uploaded to Mega

        :return: (list) of remote paths on Mega for files previously uploaded
        :raises: MegaError
        """
        log = logging.getLogger(self.cls_logger + '.get_completed_uploads')

        # Return an empty list if the file does not exist
        if not os.path.isfile(self.mega_completion_file):
            log.info('Mega completed uploads file does not exist for this media root: {f}'.format(
                f=self.mega_completion_file))
            return []

        # Load the JSON content
        log.info('Reading mega completion file: {f}'.format(f=self.mega_completion_file))
        try:
            with open(self.mega_completion_file, 'r') as f:
                json_content = f.read()
            mega_completion_file_contents = json.loads(json_content)
        except Exception as exc:
            msg = 'Problem loading JSON from file: {f}'.format(f=self.mega_completion_file)
            raise MegaError(msg) from exc

        # Ensure completed_uploads is found
        if 'completed_uploads' not in mega_completion_file_contents.keys():
            raise MegaError('completed_uploads data not found in completion file: {f}'.format(
                f=self.mega_completion_file))

        completed_uploads = mega_completion_file_contents['completed_uploads']

        # Ensure completed_uploads is a list
        if not isinstance(completed_uploads, list):
            raise MegaError('Expected type list for completed_uploads in file: {f}, found: {t}'.format(
                f=self.mega_completion_file, t=completed_uploads.__class__.__name__))

        log.info('Found {n} completed uploads'.format(n=str(len(completed_uploads))))
        return mega_completion_file_contents['completed_uploads']

    def sync_mantis_imports(self):
        """Sync recent mantis imports by uploading to Mega

        :return: None
        :raises: MegaError
        """
        log = logging.getLogger(self.cls_logger + '.sync_mantis_imports')

        # First read mantis imports from the media import root directory
        mantis_reader = MantisReader(media_import_root=self.media_import_root)
        completed_imports = mantis_reader.get_completed_imports()

        # Read completed uploads
        try:
            completed_uploads = self.get_completed_uploads()
        except MegaError as exc:
            raise MegaError from exc

        # Compute the mega path for each completed import, and the local/mega paths to a list
        unable_to_upload_imports = []
        upload_count = 0
        for completed_import in completed_imports:
            if not completed_import.startswith(self.media_import_root):
                log.warning('Completed import path should start with [{p}]: {f}'.format(
                    p=self.media_import_root, f=completed_import))
                unable_to_upload_imports.append(completed_import)
                continue
            relative_path = completed_import[len(self.media_import_root)+1:]
            mega_path = os.path.join(self.mega_root, relative_path)

            # Check completed uploads and skip ones already uploaded
            if mega_path in completed_uploads:
                log.debug('Path already found in completed uploads: {p}'.format(p=mega_path))
                continue

            # Check if the mega path already exists
            time.sleep(2)
            try:
                remote_path_exists = self.mega_cmd.remote_path_exists(remote_path=mega_path)
            except MegaError as exc:
                msg = 'Problem determining existence of remote path: {p}'.format(p=mega_path)
                raise MegaError(msg) from exc
            if remote_path_exists:
                log.info('File already exists on Mega: {f}'.format(f=mega_path))
                completed_uploads.append(mega_path)
            else:
                # Get the directory portion of the path
                #mega_dir = os.path.dirname(mega_path)
                time.sleep(2)
                try:
                    self.mega_cmd.put(local_path_list=[completed_import], remote_destination_path=mega_path)
                except MegaError as exc:
                    msg = 'Problem uploading local file [{f}] to remote path: {p}'.format(
                        f=completed_import, p=mega_path)
                    raise MegaError(msg) from exc
                else:
                    upload_count += 1

            # Add the mega path to the completed uploads list, and update the list
            completed_uploads.append(mega_path)
            self.write_completed_uploads(completed_uploads=completed_uploads)
        log.info('Completed syncing [{n}] mantis imports from [{d}] to: {p}'.format(
            n=str(upload_count), d=self.media_import_root, p=self.mega_root))

    def write_completed_uploads(self, completed_uploads):
        """Writes a list of completed uploads

        :param completed_uploads: (list) of str remote paths in Mega
        :return: None
        :raises: MegaError
        """
        log = logging.getLogger(self.cls_logger + '.write_completed_uploads')

        # Timestamp for the update
        update_time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

        if not isinstance(completed_uploads, list):
            raise MegaError('completed_uploads arg must be a list, found: {t}'.format(
                t=completed_uploads.__class__.__name__))

        # build the content
        completed_uploads = list(set(completed_uploads))
        file_content = {
            'update_time': update_time,
            'completed_uploads': completed_uploads
        }

        # Get JSON content
        json_content = json.dumps(file_content, indent=2, sort_keys=False)

        # Overwrite the mega completion file
        try:
            with open(self.mega_completion_file, 'w') as f:
                f.write(json_content)
        except (IOError, OSError) as exc:
            msg = 'Problem writing mega completion file: {f}'.format(f=self.mega_completion_file)
            raise MegaError(msg) from exc


class MegaCmd(object):
    """Handles interactions with the MEGA CMD command line interface

    """
    def __init__(self):
        self.cls_logger = mod_logger + '.MegaCmd'

    def ls(self, remote_path):
        """Lists a remote path

        :param remote_path: (str) remote path to list
        :return: (tuple) True/False for existence, and a list of remote path contents
        """
        log = logging.getLogger(self.cls_logger + '.ls')

        # Ensure remote_path is a list
        if not isinstance(remote_path, str):
            raise MegaError('Expected a str for remote_path, found: {t}'.format(t=remote_path.__class__.__name__))

        # Build the base command
        base_command = 'mega-ls'
        command = [base_command, remote_path]

        # Log the command
        command_str = ' '.join(command)
        log.debug('Running MEGA CMD command: [{c}]'.format(c=command_str))

        # Run the MegaCMD command
        try:
            result = run_command(command, timeout_sec=600)
        except CommandError as exc:
            raise MegaError('Problem detected running: {c}'.format(c=command_str)) from exc
        if result['code'] == 0:
            log.info('Mega list command succeeded')
            list_items = result['output'].split('\n')
            for list_item in list_items:
                print(' >>> Found item: ' + list_item)
            return True, list_items
        elif result['code'] == 53:
            log.info('Remote path does not exist: {p}'.format(p=remote_path))
            return False, []
        else:
            msg = 'MegaCMD command [{m}] exited with non-zero code [{c}] and output:\n{o}'.format(
                m=command_str, c=str(result['code']), o=result['output'])
            raise MegaError(msg)

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
        log.debug('Running MEGA CMD command: [{c}]'.format(c=command_str))

        # Run the MegaCMD command
        try:
            result = run_command(command, timeout_sec=600)
        except CommandError as exc:
            raise MegaError('Problem detected running: {c}'.format(c=command_str)) from exc
        if result['code'] != 0:
            msg = 'MegaCMD command [{m}] exited with non-zero code [{c}] and output:\n{o}'.format(
                m=command_str, c=str(result['code']), o=result['output'])
            raise MegaError(msg)

    def remote_path_exists(self, remote_path):
        """Determine if the remote path exists in Mega

        :param remote_path: (str) remote path
        :return: (bool) True if the path exists, False otherwise
        :raises: MegaError
        """
        try:
            exists, _ = self.ls(remote_path=remote_path)
        except MegaError as exc:
            raise MegaError from exc
        return exists


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



