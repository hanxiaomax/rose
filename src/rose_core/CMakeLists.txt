cmake_minimum_required(VERSION 2.8.12)
project(rose_core)

# 使用 C++14
add_compile_options(-std=c++14)

find_package(catkin REQUIRED COMPONENTS
  rosbag
  rosbag_storage
  roscpp
  tf2_msgs
  tf
)

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 REQUIRED)

catkin_package(
  CATKIN_DEPENDS rosbag rosbag_storage roscpp tf2_msgs tf
)

include_directories(
    include
    ${catkin_INCLUDE_DIRS}
    ${pybind11_INCLUDE_DIRS}
    ${Python3_INCLUDE_DIRS}
)

add_library(rosbag_io SHARED
    src/rosbag_io.cpp
)

target_link_libraries(rosbag_io
   ${catkin_LIBRARIES}
)

pybind11_add_module(rosbag_io_py src/rosbag_io_py.cpp)
target_link_libraries(rosbag_io_py PRIVATE rosbag_io ${catkin_LIBRARIES})
