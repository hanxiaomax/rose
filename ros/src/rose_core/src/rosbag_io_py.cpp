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
         .def("dump", [](rosbag_io &self, const std::string &output_bag, const std::vector<std::string> &topics, const py::tuple &time_range)
              {
            if (time_range.size() != 2) {
                throw py::value_error("time_range must be a tuple of two elements (start_time, end_time)");
            }

            py::tuple start_time = time_range[0].cast<py::tuple>();
            py::tuple end_time = time_range[1].cast<py::tuple>();

            if (start_time.size() != 2 || end_time.size() != 2) {
                throw py::value_error("Each time in time_range must be a tuple of two elements (seconds, nanoseconds)");
            }

            ros::Time start(start_time[0].cast<int32_t>(), start_time[1].cast<int32_t>());
            ros::Time end(end_time[0].cast<int32_t>(), end_time[1].cast<int32_t>());

            self.dump(output_bag, topics, std::make_pair(start, end)); }, "Export selected topics to a new bag file with time range filtering", py::arg("output_bag"), py::arg("topics"), py::arg("time_range"));
}
