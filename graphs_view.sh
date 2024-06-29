#!/bin/bash
THIS_FILE=$(readlink -f -- "${0}")
SCRIPT_DIR=$(dirname $THIS_FILE)
$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/graphs_view.py