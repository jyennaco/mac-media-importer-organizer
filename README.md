mac-media-importer-organizer
============================

Simple Python3 program that automatically imports and organizes pictures and 
videos from attached volumes on your Mac.

(There is also a deprecated Ruby version with less features)

Sample usage:

```
# Import media from a local directory into your media library

mantis import --dir=~/Pictures/20200704_iPhone_import

# Import media from removable medis on a Mac

mantis import --dir=/Volumes/KING4GB

# Un-import media that was mistakenly imported from a local direcory:

mantis unimport --dir=~/Pictures/20201212_iPhone_import

# Import media from an AWS S3 bucket using filename filters:

mantis import --s3bucket=bucket-name --filters=squamella,disyllabizing

# Import media from all zip files in an AWS S3 bucket as a background task:
#   This will not attempt to re-import zip archives found in the 
#   compelted_imports.txt file

nohup mantis import --s3bucket=bucket-name --filters=zip &

# Un-import media from archives in an S3 bucket:

nohup mantis unimport --s3bucket=bucket-name --filters=asparagyl &

# Archive media to an AWS S3 bucket
#   This creates zip files up to about 2 GB in size, named by a keyword
#   and uploads the resulting zip archives to an AWS S3 bucket

mantis archive --s3bucket bucket-name --dir ~/Pictures/20200325_Pics

# Provide the "--keyword" arg to specify a keyword to be used in the archive 
# files, instead of a randomly selected keyword

mantis archive --s3bucket bucket-name --dir ~/Pictures/20200325_Pics --keyword joeiphone

# Re-Archive an S3Bucket, this will reorganize an S3 bucket with media files
# into a proper mediamantis archive, where zip files do not exceed 2 GBs

mantis rearchive --s3bucket bucket-name

# Use the "--library NAME" arg to import/archive files under a separate 
# sub-library.  For example, a family member's pics/videos that should be 
# in a separate library:

mantis import --dir ~/Pictures/20201128_Joys_Pics --library JOY
mantis import --s3bucket bucket-name \
    --filters YYYYMMDD-YYYYMMDD_keyword.zip \
    --library FRED
    
# Note: The --library can be saved in the archive in archive.txt.  If mantis 
# finds a library in archive.txt at import time, it will be used in the import.

```

mediamantis creates a directory structure under:

* `~/Desktop/Media_Inbox` (if a ~/Desktop directory exists)
* `~/Media_Inbox`         (if no ~/Desktop directory exists)

Under `Media_Inbox`:

```
Media_Inbox/
    archive_files/
        # mantis archive command creates archive directories and zips here
        # This directory needs to be periodically cleaned up
        YYYYMMDD-YYYYMMDD_keyword.zip
        YYYYMMDD-YYYYMMDD_keyword/
            archive.txt -- Contains info about the archive
            image.jpg
            movie.mp4
        rearchive.txt -- (optional) List files that need to be rearchived
    auto_import/
        # Downloaded archives or files from S3, staged for import
        # This directory should be automatically cleaned up
    My_Directory_Of_Media/
        # This is a good location to stage media before import/archiving
        # For example, media imported from an iPhone
    slack.txt -- (optional) Contains a Slack webhook
```

# Installation

Clone the git repo

```
git clone git@github.com:jyennaco/mac-media-importer-organizer.git
#                  or
git clone https://github.com/jyennaco/mac-media-importer-organizer.git
```

### Windows

* [Install python3](https://www.python.org/downloads/windows/)

* [Install git](https://git-scm.com/downloads)

* Edit the `PATH` environment variable to includw:
    * `C:\Python39\`
    * `C:\Python39\Scripts`

* Install pip

```
python3 -m install --upgrade pip
```

* Install virtual environments

```
pip install virtualenv
```

...continue below...  

### MacOS

* [Install Homebrew](https://brew.sh/)

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

* Install python3 and git

```
brew install python3
brew install git
```

* Install virtualenv

```
python -m pip install virtualenv --user
```

### Install mediamantis

* Clone the git repo and change into it

```
git clone https://github.com/jyennaco/mac-media-importer-organizer.git
cd mac-media-importer-organizer
```

* Create a virtual environment in the repo directory

```
# MacOS:
~/Library/Python/2.7/bin/virtualenv -p python3 venv

# Windows:
virtualenv -p python3 venv
```

* Activate the virtual environment

```
source ./venv/bin/activate
```

* Verify the python3 version, and pip location are in the venv

```
python --version
which pip
```

* Install dependencies and install mediamantis

```
pip install -r cfg/requirements.txt
python setup.py install
```

* Test the installation

```
mantis version
```
