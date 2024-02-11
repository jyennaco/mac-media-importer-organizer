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

import progressbar
import psutil
from pycons3rt3.bash import run_command
from pycons3rt3.exceptions import CommandError
from pycons3rt3.logify import Logify
from pycons3rt3.slack import SlackAttachment, SlackMessage

from .directories import Directories
from .exceptions import MegaError
from .mantisreader import MantisReader
from .mantistypes import get_slack_webhook

mod_logger = Logify.get_name() + '.mega'

# Progress bar widget for Mega uploads
widgets = [
    progressbar.AnimatedMarker(),
    ' MEGA Uploads ',
    progressbar.AnimatedMarker(),
    ' [', progressbar.SimpleProgress(), '] ',
    ' [', progressbar.Timer(), '] ',
    progressbar.Bar(),
    ' (', progressbar.ETA(), ') ',
]


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
        slack_webhook = get_slack_webhook(self.dirs)
        if slack_webhook:
            slack_text = 'Mega Uploader: {d}'.format(d=media_import_root)
            self.slack_msg = SlackMessage(webhook_url=slack_webhook, text=slack_text)
        else:
            self.slack_msg = None

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

    def get_pending_uploads(self, completed_uploads, completed_imports):
        """Given a list of completed uploads and a list of completed imports, return a list the figures out
        which of the completed imports need tobe uploaded

        Completed imports which have a path not found, are skipped.  These are assumed to have been imported
        from another machine and likely synced to Mega from there.

        TODO evaluate if there is a clean way to determine pending uploads from another machine, e.g. the
            ones in import_path_not_found

        :param completed_uploads: (list) of mega paths to uploads that have been completed
        :param completed_imports: (list) of completed import paths
        :return: (tuple)
            (list) of (dict) { "import_path": import_path, "mega_path", mega_path }
            (list) of imports found to be already uploaded
            (list) of imports where the local file path was not found
        :raises: MegaError
        """
        log = logging.getLogger(self.cls_logger + '.get_pending_uploads')

        # List of imports (dict) that need to be uploaded, this gets returned
        # Format: { "import_path": import_path, "mega_path", mega_path }
        pending_uploads = []

        # List of import paths that were not found, potentially imported on another machine where the import
        # path was different e.g. /media/BACKUPS on Linux vs. /Volumes/BACKUPS on macOS
        import_paths_not_found = []

        # List of import paths that were found to be already uploaded via the provided completed uploads
        already_uploaded = []

        # Loop through the completed imports to determine which need to be uploaded
        for completed_import in completed_imports:

            # Skip if the prefix does not match the media import root
            if not completed_import.startswith(self.media_import_root):
                log.info('This import was likely imported from another machine, expected prefix [{p}], '
                         'found [{f}]'.format(p=self.media_import_root, f=completed_import))
                import_paths_not_found.append(completed_import)
                continue

            # Determine the relative path to the import root, this is used as the relative path to the mega root
            # for the upload to Mega
            relative_path = completed_import[len(self.media_import_root)+1:]
            mega_path = os.path.join(self.mega_root, relative_path)

            # Check completed uploads and skip ones already uploaded
            if mega_path in completed_uploads:
                log.debug('Mega upload already found in completed uploads: {p}'.format(p=mega_path))
                already_uploaded.append(completed_import)
                continue

            # Add this import to the intermediate list of uploads, before checking the Mega paths for existence
            pending_uploads.append({
                'import_path': completed_import,
                'mega_path': mega_path
            })

        # Estimate the amount of uploads
        log.info('{n} completed uploads'.format(n=str(len(completed_uploads))))
        log.info('{n} completed imports that most likely need to be uploaded to Mega'.format(
            n=str(len(pending_uploads))))

        # Log the results
        log.info('Out of the {n} completed imports found...'.format(n=str(len(completed_imports))))
        log.info('Number of local file paths not found, likely imported on another machine: {n}'.format(
            n=str(len(import_paths_not_found))))
        log.info('Number of files already uploaded to Mega: {n}'.format(n=str(len(already_uploaded))))
        log.info('Number of files pending upload to Mega: {n}'.format(n=str(len(pending_uploads))))

        # Ensure the computed number of pending uploads is not < 0
        pending_vs_completed = len(completed_imports) - len(pending_uploads)
        if pending_vs_completed < 0:
            msg = 'There are more pending uploads than completed imports, something is not right: {p}'.format(
                p=str(pending_vs_completed))
            raise MegaError(msg)

        return pending_uploads, already_uploaded, import_paths_not_found

    def send_slack_message(self, text, color):
        """Sends a Slack message using the text as and attachment, and the color

        :param text: (str) Text to send in the attachment
        :param color: (str) Color for the attachment
        :return: None
        """
        log = logging.getLogger(self.cls_logger + '.send_slack_message')
        if not self.slack_msg:
            log.debug('Slack is not configured for this mantis')
            return
        log.debug('Sending slack message with text [{t}] and color [{c}]'.format(t=text, c=color))
        attachment = SlackAttachment(fallback=text, text=text, color=color)
        self.slack_msg.add_attachment(attachment)
        self.slack_msg.send()

    def sync_mantis_imports(self):
        """Sync recent mantis imports by uploading to Mega

        :return: (list) of str failed pending upload paths
        :raises: MegaError
        """
        log = logging.getLogger(self.cls_logger + '.sync_mantis_imports')

        # List of failed uploads to be returned
        failed_uploads = []

        # First read mantis imports from the media import root directory
        mantis_reader = MantisReader(media_import_root=self.media_import_root)
        completed_imports = mantis_reader.get_completed_imports()

        # Read completed uploads
        try:
            completed_uploads = self.get_completed_uploads()
        except MegaError as exc:
            raise MegaError from exc

        # Create a diff and find the completed imports that have a valid path on this machine
        pending_uploads, already_uploaded, import_paths_not_found = self.get_pending_uploads(
            completed_uploads=completed_uploads, completed_imports=completed_imports)

        msg = '{n} estimated pending uploads to Mega are needed'.format(n=str(len(pending_uploads)))

        # Or exit if 0
        if len(pending_uploads) == 0:
            log.info(msg)
            return failed_uploads

        # Notify
        log.info(msg)
        self.send_slack_message(text=msg, color='good')

        # Set a progressbar
        bar = progressbar.ProgressBar(max_value=len(pending_uploads), widgets=widgets)

        # List of Mega paths that were found to be already uploaded via a matching enumerated mega path
        found_mega_paths = []

        # Count of uploads completed
        upload_count = 0

        for pending_upload in pending_uploads:

            log.debug('Waiting 1 second...')
            time.sleep(1)

            # Get the completed import path and the mega path
            completed_import = pending_upload['import_path']
            mega_path = pending_upload['mega_path']

            # Bump the upload count
            upload_count += 1

            # Check if the remote path exists
            max_attempts = 10
            retry_sec = 2
            list_count = 1
            failed_list = False
            remote_path_exists = False
            while True:
                if list_count > max_attempts:
                    failed_uploads.append(pending_upload)
                    failed_list = True
                    break
                log.info('Attempting list remote path [{p}] attempt [{n}] of [{m}]'.format(
                    p=mega_path, n=str(list_count), m=str(max_attempts)
                ))
                try:
                    remote_path_exists = self.mega_cmd.remote_path_exists(remote_path=mega_path)
                except MegaError as exc:
                    log.warning('Problem determining existence of remote path: {p}\n{e}'.format(
                        p=mega_path, e=str(exc)))
                    list_count += 1
                    log.warning('Attempting the kill the mega server in {t} sec...'.format(t=str(retry_sec)))
                    time.sleep(2)
                    kill_mega_server()
                else:
                    break

            if failed_list:
                log.info('Failed to list remote path [{p}], skipping...'.format(p=mega_path))
                continue

            # Check if the remote path exists on mega, add to found_paths
            if remote_path_exists:
                log.info('File already exists on Mega: {f}'.format(f=mega_path))
                found_mega_paths.append(mega_path)
            else:
                # This file does not exist in Mega and is a pending upload
                log.debug('Found pending upload that does not exist in Mega: {f}'.format(f=completed_import))

                # Attempt the Mega upload
                log.debug('Uploading file [{f}] to mega path: {m}'.format(f=completed_import, m=mega_path))

                # Check if the remote path exists
                max_attempts = 10
                retry_sec = 2
                upload_attempt_count = 1
                failed_upload = False
                while True:
                    if upload_attempt_count > max_attempts:
                        failed_uploads.append(pending_upload)
                        failed_upload = True
                        break
                    log.info('Attempting upload to remote path [{p}] attempt [{n}] of [{m}]'.format(
                        p=mega_path, n=str(upload_count), m=str(max_attempts)
                    ))
                    try:
                        self.mega_cmd.put(local_path_list=[completed_import], remote_destination_path=mega_path)
                    except MegaError as exc:
                        log.warning('Problem uploading local file [{f}] to remote path: {p}'.format(
                            f=completed_import, p=mega_path, e=str(exc)))
                        upload_attempt_count += 1
                        log.warning('Attempting the kill the mega server in {t} sec...'.format(t=str(retry_sec)))
                        time.sleep(2)
                        kill_mega_server()
                    else:
                        break

                if failed_upload:
                    log.info('Failed to upload remote path [{p}], skipping...'.format(p=mega_path))
                    continue

            # Consider the upload successful and log it
            log.info('Completed [{n}] out of [{m}] uploads'.format(n=str(upload_count), m=str(len(pending_uploads))))

            # Update the progress bar with the index
            bar.update(upload_count)

            # Add the mega path to the completed uploads list, and update the list
            completed_uploads.append(mega_path)
            self.write_completed_uploads(completed_uploads=completed_uploads)

        # Log how many files already existed on Mega
        log.info('Found {n} completed imports already existed on Mega'.format(n=str(len(found_mega_paths))))

        # Eliminate duplicates from completed uploads and update the list
        completed_uploads = list(set(completed_uploads))
        self.write_completed_uploads(completed_uploads=completed_uploads)

        # Log and send a Slack message about completed uploads
        msg = 'Completed uploading [{n}] mantis imports from [{d}] to: {p}'.format(
            n=str(upload_count), d=self.media_import_root, p=self.mega_root)
        log.info(msg)
        self.send_slack_message(text=msg, color='good')

        # Log and send a Slack notification about uncompleted uploads
        if len(failed_uploads) > 0:
            msg = 'Unable to upload [{n}] mantis imports from [{d}] to: {p}'.format(
                n=str(upload_count), d=self.media_import_root, p=self.mega_root)
            log.warning(msg)
            self.send_slack_message(text=msg, color='danger')

        # Return the failed upload list
        return failed_uploads

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
        log.debug('Write mega completion file: {f}'.format(f=self.mega_completion_file))


class MegaCmd(object):
    """Handles interactions with the MEGA CMD command line interface

    """
    def __init__(self):
        self.cls_logger = mod_logger + '.MegaCmd'

    def command_runner(self, command):
        """Runs MegaCMD commands with retry logic

        :param command: (list) Including the mega base command (e.g. mega-put) following by args/options
        :return: (tuple):
            (bool) True if the command succeeded, or False if the command failed
            (int) Exit code from the most recent command attempt
        """

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

    Upload files to MEGA cloud multithreaded
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


def kill_mega_server():
    """Attempts to find and kill the MegaCMD server process

    :return: (bool) True if the process was killed, False otherwise
    :raises: MegaError
    """
    log = logging.getLogger(mod_logger + '.kill_mega_server')

    mega_cmd_processes = []
    mega_exec_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username']):
        if 'mega-cmd' in proc.info['name'].lower():
            mega_cmd_processes.append(proc.info)
        elif 'mega-exec' in proc.info['name'].lower():
            mega_exec_processes.append(proc.info)
    log.info('Found [{n}] mega-cmd processes'.format(n=str(len(mega_cmd_processes))))
    log.info('Found [{n}] mega-exec processes'.format(n=str(len(mega_exec_processes))))

    # Build the list of processes to kill starting with mega-cmd, followed by mega-exec
    kill_processes = mega_cmd_processes + mega_exec_processes

    # Kill the mega-cmd processes
    for process_to_kill in kill_processes:
        pid = process_to_kill['pid']
        process_name = process_to_kill['name']
        if not kill_process(process_name=process_name, pid=pid):
            msg = 'Unable to kill process [{n}] with PID [{p}]'.format(n=process_name, p=pid)
            raise MegaError(msg)


def kill_process(process_name, pid):
    """Kill the process with the provided pid

    :param process_name: (str) Process name
    :param pid: (int) process PID
    :return: (bool) True if successful, False otherwise
    :raises: MegaError
    """
    log = logging.getLogger(mod_logger + '.kill_process')
    terminate_timeout_sec = 5

    # Get the process and ensure it exists
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        log.info('Process not found: [{n}] with PID [{p}]'.format(n=process_name, p=pid))
        return True

    # Attempt to terminate the process
    log.info('Attempting to gracefully terminate the process [{n}] with PID [{p}]'.format(n=process_name, p=str(pid)))
    process.terminate()

    # Wait for the process to gracefully terminate
    kill = False
    try:
        process.wait(timeout=terminate_timeout_sec)  # Wait for graceful termination
    except psutil.TimeoutExpired:
        log.warning('Unable to gracefully terminate process [{n}] with PID [{p}], attempting to kill...'.format(
            n=process_name, p=str(pid)))
        kill = True
    else:
        log.info('Gracefully terminated process [{n}] with PID [{p}]'.format(n=process_name, p=str(pid)))
        return True

    # Kill the process if graceful termination failed
    if kill:
        log.info('Attempting to kill process: [{n}] with PID [{p}]'.format(n=process_name, p=pid))
        try:
            process.kill()
        except psutil.Error as exc:
            log.warning('Problem killing process: [{n}] with PID [{p}]\n{e}'.format(n=process_name, p=pid, e=str(exc)))
            return False
        log.info('Successfully killed process [{n}] with PID [{p}]'.format(n=process_name, p=str(pid)))
    return True
