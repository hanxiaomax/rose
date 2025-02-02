#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "rosbag_io.h"

namespace py = pybind11;

PYBIND11_MODULE(rosbag_io_py, m)
{
     m.doc() = R"pbdoc(
        ROS bag IO module
        ----------------

        A Python binding for the rosbag_io C++ class that provides
        high-performance ROS bag file operations with filtering capabilities.
    )pbdoc";

     py::class_<rosbag_io>(m, "rosbag_io")
         .def(py::init<>(), "Initialize the rosbag_io object")
         .def("load", &rosbag_io::load,
              "Load a ROS bag file for reading",
              py::arg("input_bag"),
              py::arg("topics") = std::vector<std::string>())
         .def("get_connections", &rosbag_io::get_connections,
              "Get all topic-to-datatype mappings from the loaded bag")
         .def("get_topics", &rosbag_io::get_topics,
              "Get list of all topics in the loaded bag")
         .def("get_time_range", &rosbag_io::get_time_range,
              "Get the time range of messages in the bag")
         .def("dump", py::overload_cast<const std::string &, const std::vector<std::string> &, const std::pair<ros::Time, ros::Time> &>(&rosbag_io::dump),
              "Export selected topics to a new bag file with time range filtering",
              py::arg("output_bag"),
              py::arg("topics"),
              py::arg("time_range"));
}
