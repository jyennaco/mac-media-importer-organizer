#!/usr/bin/env python3

"""mediamantis -- entry point for CLI

Usage: %s [options]

Options:
setup -- configures

"""

import argparse
import logging
import sys
import traceback

from pycons3rt3.logify import Logify

from .archiver import Archiver
from .exceptions import ArchiverError


mod_logger = Logify.get_name() + '.mediamantis'

# Commands for configuration
setup_command_options = [
    'setup',
    'config',
    'configure'
]

# List of valid CLI commands
valid_commands = setup_command_options + [
    'archive',
    'import'
]

# String representation of valid commands
valid_commands_str = 'Valid commands: {c}'.format(c=', '.join(valid_commands))


def archive(args):
    log = logging.getLogger(mod_logger + '.archive')
    if args.dir:
        source_dir = args.dir
    else:
        log.error('--dir arg is required, set to the path of media files to archive')
        return 1

    a = Archiver(dir_to_archive=source_dir)
    try:
        a.process_archive()
    except ArchiverError as exc:
        log.error('Problem creating archive for: {s}\n{e}'.format(s=source_dir, e=str(exc)))
        traceback.print_exc()
        return 2
    log.info('Archive zip files created')

    if args.s3bucket:
        s3bucket = args.s3bucket
        log.info('Uploading to S3 bucket: {b}'.format(b=s3bucket))
        try:
            a.upload_to_s3(bucket_name=s3bucket)
        except ArchiverError as exc:
            log.error('Problem uploading to S3 bucket {b}\n{e}'.format(b=s3bucket, e=str(exc)))
            traceback.print_exc()
            return 3
        log.info('Completed S3 uploads')
    log.info('Media archiving completed!')
    return 0


def import_media(args):
    log = logging.getLogger(mod_logger + '.import_media')
    if args.dir:
        source_dir = args.dir
    else:
        log.error('--dir arg is required, set to the path of media files to archive')
        return 1

    

    log.info('Media import completed!')
    return 0


def main():
    parser = argparse.ArgumentParser(description='mediamantis command line interface (CLI)')
    parser.add_argument('command', help='mantis command')
    parser.add_argument('--dir', help='Archive directory to process', required=False)
    parser.add_argument('--s3bucket', help='S3 bucket to upload to', required=False)
    parser.add_argument('--s3key', help='S3 bucket key to import', required=False)
    args = parser.parse_args()

    # Get the command
    command = args.command.strip()

    if command not in valid_commands:
        print('Invalid command found [{c}]\n'.format(c=command) + valid_commands_str)

    res = 0
    if command == 'archive':
        res = archive(args)
    elif command == 'import':
        res = import_media(args)
    return res


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
