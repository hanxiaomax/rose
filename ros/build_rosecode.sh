#!/bin/bash
rm -rf build/ devel/ && catkin_make
echo "Build completed. Please run 'source setup.sh' to set up environment variables"

