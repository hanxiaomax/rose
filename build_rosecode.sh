rm -rf build/ devel/ && catkin_make
echo "Add LIB to PYTHONPATH"

export PYTHONPATH=$(pwd)/devel/lib:$PYTHONPATH
