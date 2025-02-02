#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "rosbag_io.h"

namespace py = pybind11;

PYBIND11_MODULE(rosbag_io_py, m) {
    m.doc() = "ROS bag IO module";

    py::class_<rosbag_io>(m, "rosbag_io")
        .def(py::init<>(), "Initialize the rosbag_io object")
        .def("load", &rosbag_io::load, "Load the ROS bag file",
             py::arg("input_bag"), py::arg("topics") = std::vector<std::string>())
        .def("get_connections", &rosbag_io::get_connections, "Get the connections (topics and types) from the bag")
        .def("get_topics", &rosbag_io::get_topics, "Get the list of topics from the bag")
        .def("get_time_range", &rosbag_io::get_time_range, "Get the time range of messages in the bag")
        .def("dump", &rosbag_io::dump, "Dump specified topics to a new ROS bag file",
             py::arg("output_bag"), py::arg("topics") = std::vector<std::string>());
}
