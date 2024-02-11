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

###############################################################################
# SCRIPT ARGS
###############################################################################

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

###############################################################################
# GLOBAL VARIABLES
###############################################################################

# Timeout for mantis upload processes
mantisTimeoutSec=43200

###############################################################################
# FUNCTIONS
###############################################################################

function kill_mega() {
    # Kills the MegaCMD server and ever processes
    
    # Exit if OS type is not found
    if [ -z "${OSTYPE}" ]; then
        echo "ERROR: Unable to determine OS type, exiting..."
        return 1
    fi
    
    # Get processes based on the OS type for mega-cmd and mega-exec
    if [[ "${OSTYPE}" == "darwin"* ]]; then
        megaCmdPids=( $(timeout 5s top -stats pid,command | grep -i 'mega-cmd' | awk '{print $1}') )
        megaExecPids=( $(timeout 5s top -stats pid,command | grep -i 'mega-exec' | awk '{print $1}') )
    elif [[ "${OSTYPE}" == "linux-gnu"* ]]; then
        megaCmdPids=( $(ps -ef | grep -i 'mega-cmd-server' | grep -v 'grep' | awk '{print $2}') )
        megaExecPids=( $(ps -ef | grep -i 'mega-exec' | grep -v 'grep' | awk '{print $2}') )
    else
        echo "ERROR: mega uploading in this script is not support for OS: ${OSTYPE}"
        return 1
    fi
    
    # Check for mega-exec processes
    if [ -z ${megaExecPids} ]; then
        echo "INFO: No mega-exec processes to kill"
    else
        echo "INFO: Killing ${#megaExecPids[@]} mega-exec processes: ${megaExecPids[@]}"
        for megaExecPid in "${megaExecPids[@]}"; do
            kill_process_by_pid "${megaExecPid}"
            if [ $? -ne 0 ]; then echo "ERROR: Problem killing mega-exec PID: ${megaExecPid}"; fi
        done
    fi

    # Return if no mega-cmd processes were found
    if [ -z ${megaCmdPids} ]; then
        echo "INFO: No mega-cmd processes to kill"
        return 0
    fi
    echo "INFO: Killing ${#megaCmdPids[@]} mega-cmd server PIDs: ${megaCmdPids[@]}"

    for megaCmdPid in "${megaCmdPids[@]}"; do
        kill_process_by_pid "${megaCmdPid}"
        if [ $? -ne 0 ]; then echo "ERROR: Problem killing mega-cmd PID: ${megaCmdPid}"; fi
    done
    echo "INFO: Completed killed mega-exec and mega-cmd processes"
    return 0
}

function kill_process_by_pid() {
    processPid="${1}"
    if [ -z "${processPid}" ]; then echo "Process PID not provided"; return 1; fi

    kill -9 "${processPid}"
    if [ $? -ne 0 ]; then
        echo "ERROR: Problem killing MEGA CMD PID: ${processPid}"
        return 1
    fi
    echo "INFO: Killer server PID: ${processPid}"

    echo "INFO: Killed process PID: ${processPid}"
    return 0
}

###############################################################################
# MAIN
###############################################################################

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

echo "INFO: Starting mantis mega uploader..."

# This loops under the mantis mega command exits successfully
count=0
while :
do
    echo "INFO: Running mantis with a maximum timeout of ${mantisTimeoutSec} seconds..."
    timeout ${mantisTimeoutSec}s mantis mega upload --rootimportdir ${mediaImportRoot} --megaroot ${megaRoot} --force
    res=$?
    if [ ${res} -eq 0 ]; then
        echo "INFO: mantis completed successfully and exited with code 0, exiting..."
        break
    elif [ ${res} -eq 124 ]; then
        echo "WARN: mantis timeout reached at ${mantisTimeoutSec} seconds, the MEGA CMD server will be killed and restarted..."
    else
        echo "WARN: mantis exited with code ${res}, the MEGA CMD server will be killed and restarted..."
    fi

    # Kill the server
    echo "INFO: mantis exited with code: ${res}, killing the server in 5 seconds..."
    sleep 5
    kill_mega
    if [ $? -ne 0 ]; then echo "ERROR: Problem killing the MegaCMD server"; exit 2; fi

    # Wait and re-try the mantic mega command
    echo "INFO: Waiting 5 seconds to re-try..."
    sleep 5
done

echo "INFO: Completed running the mantis mega uploader!"
exit 0
