#!/bin/bash
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
