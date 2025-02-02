cmake_minimum_required(VERSION 3.0.2)
project(rose_core)

# 使用 C++14
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(catkin REQUIRED COMPONENTS
  roscpp
  rosbag
  rosbag_storage
  tf2_msgs
  tf
)

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 REQUIRED)

catkin_package(
  INCLUDE_DIRS include
  LIBRARIES rosbag_io
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

# 安装规则
install(
  TARGETS rosbag_io
  LIBRARY DESTINATION ${CATKIN_PACKAGE_LIB_DESTINATION}
)

install(
  DIRECTORY include/${PROJECT_NAME}/
  DESTINATION ${CATKIN_PACKAGE_INCLUDE_DESTINATION}
)

add_library(rose_core src/rosbag_io.cpp)
target_link_libraries(rose_core ${catkin_LIBRARIES})
