#include "rosbag_io.h"
#include <ros/ros.h>
#include <rosbag/view.h>
#include <iostream>
#include <ctime>

rosbag_io::rosbag_io() {}

rosbag_io::~rosbag_io()
{
    if (_bag.isOpen())
    {
        _bag.close();
    }
}

void rosbag_io::load(const std::string &input_bag, const std::vector<std::string> &topics)
{
    _input_bag = input_bag;
    try
    {
        _bag.open(_input_bag, rosbag::bagmode::Read);
    }
    catch (const rosbag::BagException &e)
    {
        std::cerr << "Error opening input bag file: " << e.what() << std::endl;
        throw;
    }

    if (topics.empty())
    {
        _view = std::make_shared<rosbag::View>(_bag);
    }
    else
    {
        _view = std::make_shared<rosbag::View>(_bag, rosbag::TopicQuery(topics));
    }

    _connections.clear();
    for (const auto &connection : _view->getConnections())
    {
        _connections[connection->topic] = connection->datatype;
    }
}

rosbag_io::ConnectionsMap rosbag_io::get_connections() const
{
    return _connections;
}

std::vector<std::string> rosbag_io::get_topics() const
{
    std::vector<std::string> topics;
    for (const auto &connection : _connections)
    {
        topics.push_back(connection.first);
    }
    return topics;
}

std::pair<ros::Time, ros::Time> rosbag_io::get_time_range()
{
    if (_view->size() == 0)
    {
        return {ros::Time(0), ros::Time(0)};
    }

    ros::Time start_time = _view->getBeginTime();
    ros::Time end_time = _view->getEndTime();

    return {start_time, end_time};
}

void rosbag_io::dump(const std::string &output_bag,
                     const std::vector<std::string> &topics,
                     const std::pair<ros::Time, ros::Time> &time_range)
{
    rosbag::Bag out_bag;
    try
    {
        out_bag.open(output_bag, rosbag::bagmode::Write);
    }
    catch (const rosbag::BagException &e)
    {
        std::cerr << "Error opening output bag file: " << e.what() << std::endl;
        throw;
    }

    std::shared_ptr<rosbag::View> dump_view;
    if (topics.empty())
    {
        dump_view = std::make_shared<rosbag::View>(_bag);
    }
    else
    {
        dump_view = std::make_shared<rosbag::View>(_bag, rosbag::TopicQuery(topics));
    }

    // Apply time range if specified
    if (time_range.first != ros::Time(0) || time_range.second != ros::Time(0))
    {
        dump_view = std::make_shared<rosbag::View>(_bag,
                                                   rosbag::TopicQuery(topics),
                                                   time_range.first,
                                                   time_range.second);
    }

    for (const rosbag::MessageInstance &msg : *dump_view)
    {
        out_bag.write(msg.getTopic(), msg.getTime(), msg, msg.getConnectionHeader());
    }

    out_bag.close();
}
