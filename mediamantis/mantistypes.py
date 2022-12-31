# -*- coding: utf-8 -*-

"""
mediamantis.mantistypes
~~~~~~~~~~~~~~~~~~~
Data types for mediamantis

"""

import enum
import os


class MediaFileType(enum.Enum):
    """ENUM for the media file type"""
    MOVIE = 1
    PICTURE = 2
    AUDIO = 3
    UNKNOWN = 4


class ArchiveStatus(enum.Enum):
    """ENUM for the archive status"""
    COMPLETED = 1
    PENDING = 2


class ImportStatus(enum.Enum):
    """ENUM for import status"""
    COMPLETED = 1
    PENDING = 2
    ALREADY_EXISTS = 3
    DO_NOT_IMPORT = 4
    UNIMPORTED = 5


def chunker(seq, size):
    """Splits a list of threads into chunks

    :param seq: (list) of Threads
    :param size: (int) Maximum simultaneous threads
    :return: (list) Chunk of threads
    :raise: None
    """
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def get_slack_webhook(dirs):
    """Evaluates the local directory structure to find and read the webhook from the slack.txt file

    :param dirs: (directories.Directories)
    :return: (str) Slack webhook URL
    :raises: None
    """
    if not os.path.isfile(dirs.slack_webhook_file):
        return
    with open(dirs.slack_webhook_file, 'r') as f:
        contents = f.read()
    return contents.strip()


def map_import_status(import_status_str):
    """Maps a string to ImportStatus ENUM

    :param import_status_str: (str) Import status
    :return: ImportStatus
    :raises: ValueError
    """
    if import_status_str == 'COMPLETED':
        return ImportStatus.COMPLETED
    elif import_status_str == 'PENDING':
        return ImportStatus.PENDING
    elif import_status_str == 'ALREADY_EXISTS':
        return ImportStatus.ALREADY_EXISTS
    elif import_status_str == 'DO_NOT_IMPORT':
        return ImportStatus.DO_NOT_IMPORT
    elif import_status_str == 'UNIMPORTED':
        return ImportStatus.UNIMPORTED
    else:
        raise ValueError('Unsupported import status: {s}'.format(s=import_status_str))


# Shell script for running the mantis imports
mantis_import_shell_script_contents = '''#!/bin/bash
#
# mantis_importer.sh
#
# This script queries the user (or takes args) to run mantis imports
#
# Usage:
#     ./mantis_importer.sh <MEDIA_IMPORT_ROOT> <DIRECTORY_TO_IMPORT>
#
# Args (OPTIONAL):
#     1. Full path to the root directory for where to import media files to
#     2. Full path to the directory to import
#     3. The root directory on MEGA under which to upload/sync the imported media files
#
# The args are all optional, but if a 1st arg is provided, its only used if there is also a 2nd arg, and so on.
#

# Process the args
# If both paths are provided, use them
if [ -z "${1}" ]; then
  :
else
  if [ -z "${2}" ]; then
    :
  else
    mediaImportRoot="${1}"
    directoryToImport="${2}"
    if [ -z "${3}" ]; then
      :
    else
      megaRoot="${3}"
    fi
  fi
fi

# Get script and imports directories
scriptDir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
megaUploadScript="${scriptDir}/mega_uploader.sh"
importsDir="${scriptDir}/../imports"
confDir="${scriptDir}/../conf"
importsDirFile="${confDir}/import_dirs.txt"

# If the media import root was not provided, query the user
if [ -z "${mediaImportRoot}" ]; then
  if [ -f ${importsDirFile} ]; then
    echo "----------------------------------"
    echo "Previous imports: "
    cat ${importsDirFile}
    echo "----------------------------------"
  fi
  read -p "Path to your local import media root directory [Type ENTER to use you HOME dir]: " mediaImportRoot
fi

# If the user typed ENTER, set it to $HOME
if [ -z "${mediaImportRoot}" ]; then
  mediaImportRoot="${HOME}"
  echo "Using the user HOME directory as the media import root: ${mediaImportRoot}"
fi

# Ensure the directory was found
if [ ! -d ${mediaImportRoot} ]; then
  echo "ERROR: Media import root directory not found: ${mediaImportRoot}"
  exit 1
fi

# Ask if uploading to mega
doMegaUpload=0
if [ -z "${megaRoot}" ]; then
  read -p "Uploading to mega after import? [y/n]: " megaUploadConfirm
  if [ -z "${megaUploadConfirm}" ]; then
    :
  else
    if [[ "${megaUploadConfirm}" == "y" ]]; then
      doMegaUpload=1
      read -p "Type the remote MEGA root path to upload to: " megaRoot
    fi
  fi
else
  doMegaUpload=1
fi

# Print Mega plan
if [ ${doMegaUpload} -eq 1 ]; then
  echo "Uploading to MEGA at: ${megaRoot}"
else
  echo "Not uploading to MEGA"
fi

# Check if the directory to import was provided
if [ -z "${directoryToImport}" ]; then

  # Check if the imports directory exists
  if [ -d ${importsDir} ]; then
    echo "Found imports directory: ${importsDir}"

    # List all the items in the imports directory
    importDirItems=( $(ls ${importsDir}) )

    # Determine which items are directories to import
    potentialImportDirs=()
    for item in "${importDirItems[@]}"; do
      echo "Checking potential import directory: ${item}"
      itemPath="${importsDir}/${item}"
      if [ -d ${itemPath} ]; then
        potentialImportDirs+=("${item}")
      fi
    done

    echo "---------------------------------------------------"
    echo "Potential import directories: ${potentialImportDirs[@]}"
    read -p "Which directory to import from [type 'other' to enter a full path]? " importDirName

    # If the user typed "other" then query for full path
    if [[ "${importDirName}" == "other" ]]; then
      :
    else
      # Set the full path for the directory to import
      directoryToImport="${importsDir}/${importDirName}"
    fi
  fi

  # If the directory to import is not set yet, query the use for the full path
  if [ -z "${directoryToImport}" ]; then
    read -p "Type the full path to the directory to import: " directoryToImport
  fi
fi

# Ensure the import directory exists
if [ ! -d ${directoryToImport} ]; then
    echo "Import directory not found: ${directoryToImport}"
    exit 2
fi

echo "Importing from directory [${directoryToImport}] to: [${mediaImportRoot}]"

echo "Running media mantis..."
mantis import --dir=${directoryToImport} --rootimportdir=${mediaImportRoot}
if [ $? -ne 0 ]; then
  echo "ERROR: Problem importing from directory [${directoryToImport}] to: ${mediaImportRoot}"
  exit 3
fi

# If the mega uploader script is found, run it
if [ ${doMegaUpload} -eq 1 ]; then
  if [ -f ${megaUploadScript} ]; then
    echo "Running the mega_uploader.sh script uploading [${mediaImportRoot}] to [MEGA:${megaRoot}]..."
    ${megaUploadScript} -force ${mediaImportRoot} ${megaRoot}
    megaRes=$?
  else
    echo "Mega uploader script not found: ${megaUploadScript}"
    megaRes=1
  fi
else
  echo "MEGA upload not requested, skipping"
  megaRes=0
fi

echo "Exiting with code: ${megaRes}"
exit $?


'''


# Shell script for running the mantis uploads
mantis_mega_upload_shell_script_contents = '''#!/bin/bash
#
# mega_uploader.sh
#
# This script handles automatically backing up your imported media to Mega.nz using MEGAcmd
#
# Usage:
#     ./mega_uploader.sh -force <MEDIA_IMPORT_ROOT> <MEGA_UPLOAD_ROOT>
#
# Args (OPTIONAL):
#    1.  -force Set this to skip the prompt about prerequisites
#    2.  The root directory of the mantis media import that needs to be uploaded
#    3.  The root directory on MEGA under which to upload/sync the imported media files
#
# The args are all optional, but if a 2nd arg is provided, its only used if there is also a 3rd arg.
#

# Process the args
force="${1}"

# If both paths are provided, use them
if [ -z "${2}" ]; then
  :
else
  if [ -z "${3}" ]; then
    :
  else
    mediaImportRoot="${2}"
    megaRoot="${3}"
  fi
fi

# If -force was provided, skip this prompt
if [[ "${force}" == "-force" ]]; then
  :
else
  echo "---------------------------------------------------"
  echo "Welcome to the automated MEGAcmd Mantis uploader!!"
  echo "Prerequisites for running MEGAcmd uploads:"
  echo "1. Get an account on https://mega.nz"
  echo "2. Install and start MegaCMD server: https://mega.io/cmd"
  echo "3. Log in via MegaCMD (you should be prompted if skipping this):"
  echo "   https://github.com/meganz/MEGAcmd/blob/master/UserGuide.md#login"
  echo "4. In the MEGAcmd server, run: [update --auto=OFF] to disable auto-updating while mantis is working"
  read -p "When ready, type enter "
  echo "---------------------------------------------------"
fi

# If the media import root was not provided, query the user
if [ -z "${mediaImportRoot}" ]; then
  read -p "Type the full path to your local backup/import media root directory: " mediaImportRoot
fi

# Ensure the directory was found
if [ ! -d ${mediaImportRoot} ]; then
  echo "ERROR: backup/import media root directory not found: ${mediaImportRoot}"
  exit 1
fi

# If the mega root was not provided, query the user
if [ -z "${megaRoot}" ]; then
  read -p "Type the remote MEGA root path to upload to: " megaRoot
fi

echo "Starting mantis mega uploader..."

# This loops under the mantis mega command exits successfully
count=0
while :
do

  echo "Running mantis..."
  mantis mega --rootimportdir ${mediaImportRoot} --megaroot ${megaRoot} --force
  res=$?
  if [ ${res} -eq 0 ]; then
    echo "mantis exited with code 0"
    break
  fi

  echo "mantis exited with code: ${res}, killing the server in 5 seconds..."
  sleep 5
  megaFinder=( $(timeout 5s top -stats pid,command | grep -i mega-cmd | awk '{print $1}') )
  echo "Found PIDs: ${megaFinder[@]}"
  serverPid="${megaFinder[0]}"
  if [ -z "${serverPid}" ]; then
    echo "ERROR: Server PID not found, exiting..."
    exit 1
  fi
  echo "Killing MEGA CMD server PID: ${serverPid}"
  kill -9 "${serverPid}"
  if [ $? -ne 0 ]; then
    echo "ERROR: Problem killing MEGA CMD server PID: ${serverPid}"
    exit 2
  fi
  echo "Killer server PID: ${serverPid}, waiting 5 seconds to re-try..."
  sleep 5

done

echo "Completed running the mantis mega uploader!"
exit 0


'''
