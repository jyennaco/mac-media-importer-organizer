#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

logTag="aws_import"
logDir="${SCRIPT_DIR}/log"
logFile="${logDir}/${logTag}-$(date "+%Y%m%d-%H%M%S").log"

function timestamp() { date "+%F %T"; }
function logInfo() { echo -e "$(timestamp) ${logTag} [INFO]: ${1}" >> ${logFile}; }
function logWarn() { echo -e "$(timestamp) ${logTag} [WARN]: ${1}" >> ${logFile}; }
function logErr() { echo -e "$(timestamp) ${logTag} [ERROR]: ${1}" >> ${logFile}; }

s3_bucket_name="your-s3-bucket-name"

photo_inbox="$HOME/Desktop/Photo_Inbox/auto_import"

aws_filenames=( \
archive1.zip \
archive2.tar.gz \
archive3.tar.bz2 \
movie.mp4
)

completed="${SCRIPT_DIR}/completed_imports.txt"

function process_file() {
    import_filename="${1}"
    logInfo "Processing file for import ${import_filename}"
    s3_path="s3://${s3_bucket_name}/${aws_filename}"
    local_path="${photo_inbox}/${import_filename}"
    aws_result=$(aws s3 ls "${s3_path}")
    if [ -z "${aws_result}" ]; then
        logErr "File not found in S3: ${s3_path}"
        return 1
    else
        logInfo "Found file on S3: ${s3_path}"
    fi
    if [ -f ${local_path} ]; then
      logInfo "Removing existing file: $local_path"
      rm -f $local_path >> $logFile 2>&1
    fi
    logInfo "Downloading [${s3_path}] to: ${photo_inbox}"
    aws s3 cp "${s3_path}" "${photo_inbox}/"
    if [ $? -ne 0 ]; then logErr "Problem downloading: ${s3_path} to: ${photo_inbox}"; return 3; fi
    if [ ! -f ${local_path} ]; then
        logErr "Local file not found: ${local_path}"
        return 2
    fi

    cd ${photo_inbox} >> ${logFile} 2>&1
    extension=$(echo $import_filename | awk -F . '{print $NF}')

    # Unzip or untar depending on the extension
    if [ ${extension} == "gz" ]; then
      logInfo "Found bz extension, untarring: $import_filename"
      tar -xvzf $import_filename >> $logFile 2>&1
      if [ $? -ne 0 ]; then logErr "Problem untarring: ${local_path}"; return 3; fi
    elif [ ${extension} == "zip" ]; then
      logInfo "Found zip extension, unzipping: $import_filename"
      unzip ${import_filename} >> ${logFile} 2>&1
      if [ $? -ne 0 ]; then logErr "Problem unzipping: ${local_path}"; return 4; fi
    elif [ ${extension} == "bz2" ]; then
      logInfo "Found bz2 extension, untarring: $import_filename"
      tar -xvjf ${import_filename} >> ${logFile} 2>&1
      if [ $? -ne 0 ]; then logErr "Problem unzipping: ${local_path}"; return 5; fi
    else
      logInfo "Did not find a zip or tar file, nothing to do"
    fi
    cd -

    logInfo "Running import of directory: ${photo_inbox}"
    ruby ${SCRIPT_DIR}/init.rb "${photo_inbox}" >> ${logFile} 2>&1
    if [ $? -ne 0 ]; then logErr "Problem importing from: ${photo_inbox}"; return 6; fi

    logInfo "Completed import from ${photo_inbox}"
    logInfo "Cleaning up: $photo_inbox"
    rm -Rf ${photo_inbox}/* >> $logFile 2>&1
    return 0
}

if [ ! -f ${completed} ]; then
    logInfo "Creating file: ${completed}"
    touch ${completed}
fi

if [ ! -d ${photo_inbox} ]; then
    logInfo "Creating directory: ${photo_inbox}"
    mkdir -p ${photo_inbox}
fi

for aws_filename in "${aws_filenames[@]}"; do
    logInfo "Checking AWS filename: ${aws_filename}"
    completed_result=$(cat ${completed} | grep "${aws_filename}")
    if [ -z "${completed_result}" ]; then
        process_file "${aws_filename}"
        if [ $? -ne 0 ]; then
            logErr "Problem processing import for file: ${aws_filename}"
            exit 1
        else
            logInfo "Completed import for: ${aws_filename}"
            echo "${aws_filename}" >> ${completed}
        fi
    else
        logInfo "Found file already completed: ${aws_filename}"
    fi
done

logInfo "Completed AWS imports"
exit 0
