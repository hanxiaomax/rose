#ifndef ROSBAG_IO_H
#define ROSBAG_IO_H

#include <rosbag/bag.h>
#include <rosbag/view.h>
#include <map>
#include <string>
#include <vector>

class rosbag_io
{
public:
    using ConnectionsMap = std::map<std::string, std::string>;

    rosbag_io();
    ~rosbag_io();

    void load(const std::string& input_bag, const std::vector<std::string>& topics = {});
    ConnectionsMap get_connections() const;
    std::vector<std::string> get_topics() const;
    std::pair<std::time_t, std::time_t> get_time_range();
    void dump(const std::string& output_bag, const std::vector<std::string>& topics = {});

private:
    rosbag::Bag _bag;
    std::string _input_bag;
    std::shared_ptr<rosbag::View> _view; // Use a shared_ptr to manage the view
    ConnectionsMap _connections;
};

#endif // ROSBAG_IO_H
