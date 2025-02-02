#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LIB_PATH="$SCRIPT_DIR/devel/lib"
export PYTHONPATH=$LIB_PATH:$PYTHONPATH
echo "PYTHONPATH has been updated: $PYTHONPATH" 