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

from pycons3rt3.exceptions import S3UtilError
from pycons3rt3.logify import Logify
from pycons3rt3.s3util import S3Util

from .archiver import Archiver, ReArchiver
from .exceptions import ArchiverError, ImporterError
from .importer import Importer, S3Importer


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
    'import',
    'rearchive',
    'unimport'
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

    media_inbox = None
    if args.mediainbox:
        media_inbox = args.mediainbox
        log.info('Using media inbox: {d}'.format(d=media_inbox))

    keyword = None
    if args.keyword:
        keyword = args.keyword

    library = None
    if args.library:
        library = args.library

    # Validate the S3 bucket provided
    s3bucket = None
    if args.s3bucket:
        s3bucket = args.s3bucket
        try:
            s3 = S3Util(_bucket_name=s3bucket)
        except Exception as exc:
            log.error('Problem validating existence of S3 bucket named: {b}'.format(b=s3bucket))
            traceback.print_exc()
            return 2

    a = Archiver(dir_to_archive=source_dir, media_inbox=media_inbox, keyword=keyword, library=library)
    try:
        a.process_archive()
    except ArchiverError as exc:
        log.error('Problem creating archive for: {s}\n{e}'.format(s=source_dir, e=str(exc)))
        traceback.print_exc()
        return 3
    log.info('Archive zip files created')

    if s3bucket:
        log.info('Uploading to S3 bucket: {b}'.format(b=s3bucket))
        try:
            a.upload_to_s3(bucket_name=s3bucket)
        except ArchiverError as exc:
            log.error('Problem uploading to S3 bucket: {b}\n{e}'.format(b=s3bucket, e=str(exc)))
            traceback.print_exc()
            return 4
        log.info('Completed S3 uploads')
    log.info('Media archiving completed!')
    return 0


def import_media(args):
    log = logging.getLogger(mod_logger + '.import_media')
    if args.dir:
        return import_media_from_local(args)
    elif args.s3bucket:
        return import_media_from_s3(args)
    else:
        log.error('--dir or --s3bucket arg is required')
        return 1


def import_media_from_local(args):
    log = logging.getLogger(mod_logger + '.import_media_from_local')
    if args.dir:
        source_dir = args.dir
    else:
        log.error('--dir arg is required, set to the path of media files to archive')
        return 1

    root_import_dir = None
    if args.rootimportdir:
        root_import_dir = args.rootimportdir

    library = None
    if args.library:
        library = args.library

    imp = Importer(import_dir=source_dir, media_import_root=root_import_dir, library=library)
    try:
        imp.process_import()
    except ImporterError as exc:
        log.error('Problem processing import from directory: {d}\n{e}'.format(d=source_dir, e=str(exc)))
        traceback.print_exc()
        return 2

    log.info('Local media import completed!')
    return 0


def import_media_from_s3(args):
    log = logging.getLogger(mod_logger + '.import_media_from_s3')
    if args.s3bucket:
        s3_bucket = args.s3bucket
    else:
        log.error('--s3bucket arg is required, name of the S3 bucket to import')
        return 1

    root_import_dir = None
    if args.rootimportdir:
        root_import_dir = args.rootimportdir

    filters = None
    if args.filters:
        log.info('Found filters: {f}'.format(f=args.filters))
        filters = args.filters.split(',')

    library = None
    if args.library:
        library = args.library

    s3_imp = S3Importer(s3_bucket=s3_bucket, media_import_root=root_import_dir, library=library)
    log.info('Processing S3 imports...')
    try:
        s3_imp.process_s3_imports(filters=filters)
    except ImporterError as exc:
        log.error('Problem processing import from S3 bucket: {b}\n{e}'.format(b=s3_bucket, e=str(exc)))
        traceback.print_exc()
        return 2

    log.info('S3 media import completed!')
    return 0


def re_archive(args):
    log = logging.getLogger(mod_logger + '.re_archive')

    if args.s3bucket:
        s3bucket = args.s3bucket
        log.info('Uploading to S3 bucket: {b}'.format(b=s3bucket))
    else:
        log.error('--s3bucket arg is required')
        return 1

    media_inbox = None
    if args.mediainbox:
        media_inbox = args.mediainbox
        log.info('Using media inbox: {d}'.format(d=media_inbox))

    library = None
    if args.library:
        library = args.library

    re = ReArchiver(s3_bucket=s3bucket, media_inbox=media_inbox, library=library)
    try:
        re.process_re_archive()
    except ArchiverError as exc:
        log.error('Problem processing re-archiver for S3 bucket: {b}\n{e}'.format(b=s3bucket, e=str(exc)))
        traceback.print_exc()
        return 2

    log.info('Completed re-archiving!')
    return 0


def un_import_media(args):
    log = logging.getLogger(mod_logger + '.un_import_media')
    if args.dir:
        return un_import_media_from_local(args)
    elif args.s3bucket:
        return un_import_media_from_s3(args)
    else:
        log.error('--dir or --s3bucket arg is required')
        return 1


def un_import_media_from_local(args):
    log = logging.getLogger(mod_logger + '.un_import_media_from_local')
    if args.dir:
        source_dir = args.dir
    else:
        log.error('--dir arg is required, set to the path of media files to archive')
        return 1

    root_import_dir = None
    if args.rootimportdir:
        root_import_dir = args.rootimportdir

    library = None
    if args.library:
        library = args.library

    imp = Importer(import_dir=source_dir, media_import_root=root_import_dir, un_import=True, library=library)
    try:
        imp.process_import()
    except ImporterError as exc:
        log.error('Problem processing un-import from directory: {d}\n{e}'.format(d=source_dir, e=str(exc)))
        traceback.print_exc()
        return 2
    log.info('Local media un-import completed!')
    return 0


def un_import_media_from_s3(args):
    log = logging.getLogger(mod_logger + '.un_import_media_from_s3')
    if args.s3bucket:
        s3_bucket = args.s3bucket
    else:
        log.error('--s3bucket arg is required, name of the S3 bucket to un-import')
        return 1

    root_import_dir = None
    if args.rootimportdir:
        root_import_dir = args.rootimportdir

    filters = None
    if args.filters:
        log.info('Found filters: {f}'.format(f=args.filters))
        filters = args.filters.split(',')

    library = None
    if args.library:
        library = args.library

    s3_imp = S3Importer(s3_bucket=s3_bucket, media_import_root=root_import_dir, un_import=True, library=library)
    log.info('Processing S3 imports...')
    try:
        s3_imp.process_s3_imports(filters=filters)
    except ImporterError as exc:
        log.error('Problem processing un-imports from S3 bucket: {b}\n{e}'.format(b=s3_bucket, e=str(exc)))
        traceback.print_exc()
        return 2
    log.info('S3 media un-import completed!')
    return 0


def main():
    parser = argparse.ArgumentParser(description='mediamantis command line interface (CLI)')
    parser.add_argument('command', help='mantis command')
    parser.add_argument('--dir', help='Archive directory to process', required=False)
    parser.add_argument('--filters', help='Comma-separated list of strings to filter on', required=False)
    parser.add_argument('--keyword', help='Keyword to include in archive names instead of a random one', required=False)
    parser.add_argument('--library', help='Name of the library to import, exists under rootimportdir', required=False)
    parser.add_argument('--mediainbox', help='Directory to create archives under and to be used for staging',
                        required=False)
    parser.add_argument('--rootimportdir', help='Root directory to import media files under', required=False)
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
    elif command == 'rearchive':
        res = re_archive(args)
    elif command == 'unimport':
        res = un_import_media(args)
    return res


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
