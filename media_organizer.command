#!/bin/bash

# get the absolute path of the executable
SELF_PATH=$(cd -P -- "$(dirname -- "$0")" && pwd -P) && SELF_PATH=$SELF_PATH/$(basename -- "$0")

# resolve symlinks
while [ -h $SELF_PATH ]; do
# 1) cd to directory of the symlink
# 2) cd to the directory of where the symlink points
# 3) get the pwd
# 4) append the basename
DIR=$(dirname -- "$SELF_PATH")
SYM=$(readlink $SELF_PATH)
SELF_PATH=$(cd $DIR && cd $(dirname -- "$SYM") && pwd)/$(basename -- "$SYM")
done

RUN_DIR=$(dirname -- "$SELF_PATH")

echo "Running: $SELF_PATH"

ruby ${RUN_DIR}/init.rb