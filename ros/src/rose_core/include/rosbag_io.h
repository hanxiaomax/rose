#ifndef ROSBAG_IO_H
#define ROSBAG_IO_H

#include <rosbag/bag.h>
#include <rosbag/view.h>
#include <map>
#include <string>
#include <vector>
/**
 * @brief A class for reading and writing ROS bag files with filtering capabilities
 *
 * This class provides functionality to:
 * - Load and read ROS bag files
 * - Get information about topics and message types
 * - Filter and export messages based on topics and time ranges
 */
class rosbag_io
{
public:
  /** Type alias for storing topic to message type mappings */
  using ConnectionsMap = std::map<std::string, std::string>;

  /** @brief Default constructor */
  rosbag_io();

  /** @brief Destructor that ensures bag file is properly closed */
  ~rosbag_io();

  /**
   * @brief Load a ROS bag file for reading
   *
   * @param input_bag Path to the input bag file
   * @param topics List of topics to load (empty for all topics)
   * @throw rosbag::BagException if bag file cannot be opened
   */
  void load(const std::string &input_bag, const std::vector<std::string> &topics);

  /**
   * @brief Get all topic-to-datatype mappings from the loaded bag
   *
   * @return ConnectionsMap Map of topic names to their message types
   */
  ConnectionsMap get_connections() const;

  /**
   * @brief Get list of all topics in the loaded bag
   *
   * @return std::vector<std::string> List of topic names
   */
  std::vector<std::string> get_topics() const;

  /**
   * @brief Get the time range of messages in the loaded bag
   *
   * @return std::pair<std::time_t, std::time_t> Pair of (start_time, end_time) in Unix timestamp
   */
  std::pair<std::time_t, std::time_t> get_time_range();

  /**
   * @brief Export selected topics to a new bag file with optional time range filtering
   *
   * @param output_bag Path to the output bag file
   * @param topics List of topics to export (empty for all topics)
   * @param time_range Pair of (start_time, end_time) for filtering messages
   * @throw rosbag::BagException if output file cannot be created
   */
  void dump(const std::string &output_bag,
            const std::vector<std::string> &topics,
            const std::pair<ros::Time, ros::Time> &time_range);

  /**
   * @brief Export selected topics to a new bag file
   *
   * This is a convenience overload that exports all messages without time filtering
   *
   * @param output_bag Path to the output bag file
   * @param topics List of topics to export (empty for all topics)
   * @throw rosbag::BagException if output file cannot be created
   */
  void dump(const std::string &output_bag, const std::vector<std::string> &topics);

private:
  std::string _input_bag;
  rosbag::Bag _bag;
  std::shared_ptr<rosbag::View> _view;
  ConnectionsMap _connections;
};

#endif // ROSBAG_IO_H