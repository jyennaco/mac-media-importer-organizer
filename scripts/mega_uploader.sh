#!/bin/bash
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

# Timeout for mantis upload processes
mantisTimeoutSec=3600

# This loops under the mantis mega command exits successfully
count=0
while :
do

  echo "Running mantis..."
  timeout ${mantisTimeoutSec}s mantis mega --rootimportdir ${mediaImportRoot} --megaroot ${megaRoot} --force
  res=$?
  if [ ${res} -eq 0 ]; then
      echo "mantis exited with code 0"
      break
  elif [ ${res} -eq 124 ]; then
      echo "mantis "
  fi

  echo "mantis exited with code: ${res}, killing the server in 5 seconds..."
  sleep 5
  if [ -z "${OSTYPE}" ]; then
      echo "Unable to determine OS type, exiting..."
      exit 1
  else
      if [[ "${OSTYPE}" == "darwin"* ]]; then
          megaFinder=( $(timeout 5s top -stats pid,command | grep -i 'mega-cmd' | awk '{print $1}') )
      elif [[ "${OSTYPE}" == "linux-gnu"* ]]; then
          megaFinder=( $(ps -ef | grep -i 'mega-cmd-server' | grep -v 'grep' | awk '{print $2}') )
      else
          echo "mega uploading in this script if not support for OS: ${OSTYPE}"
      fi
  fi

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
