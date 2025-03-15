# Standard library imports
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

# Third-party imports
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.fuzzy import FuzzySearch
from textual.widgets import Input, Tree

# Local application imports
from roseApp.tui.components.BagExplorer import BagExplorer
from roseApp.core.BagManager import BagManager
from roseApp.core.util import get_logger

logger = get_logger("TopicPanel")



class TopicTree(Tree):
    """A tree widget for displaying ROS bag topics with multi-selection capability"""
    
    def __init__(self):
        super().__init__("Topics")
        self.border_subtitle = "Selected: 0"
        self.fuzzy_searcher = FuzzySearch(case_sensitive=False)
        self.multi_select_mode = False
        self.show_root = False
        self._search_input = None


    def on_mount(self) -> None:
        """Initialize when mounted"""
        super().on_mount()
        self.root.expand()
        self._search_input = self.parent.query_one(TopicSearchInput)
        self.watch(self.app.query_one(BagExplorer), "bags", self.handle_bags_change)
        self.watch(self.app.query_one(BagExplorer), "multi_select_mode", 
                                self.handle_multi_select_mode_change)

    @property
    def bags(self) -> BagManager:
        return self.app.query_one(BagExplorer).bags
    

    def handle_bags_change(self, bags: BagManager) -> None:
        """Handle changes in BagManager and update topics accordingly"""        
        self.render_topics()

    def handle_multi_select_mode_change(self, multi_select_mode: bool) -> None:
        """Handle multi select mode change"""
        self.multi_select_mode = multi_select_mode

    def get_node_label(self, topic: str, selected: bool = False) -> Text:
        """
        Get the label for a topic node based on mode and selection state.
        
        Args:
            topic: The topic name
            selected: Whether the topic is selected
        """
        if self.multi_select_mode:
            # Get count from bag manager
            count = self.bags.get_topic_summary().get(topic, 0)
            label = f"{topic} [{count}]"
        else:
            label = topic
            
        if selected:
            return Text("√ ") + Text(label)
        return Text(label)

    def filter_topics(self,topics,search_text: str) -> None:
        """Filter topics based on search text using fuzzy search.
        Do not change data in bag manager, only for display
        """
        self.root.remove_children()
        
        if not search_text:
            filtered_topics = topics
        else:
            scored_topics = [
                (topic, self.fuzzy_searcher.match(search_text, topic)[0])
                for topic in topics
            ]
            filtered_topics = [
                topic for topic, score in sorted(
                    scored_topics,
                    key=lambda x: x[1],
                    reverse=True
                ) if score > 0
            ]
        
        return filtered_topics
        

    def render_topics(self) -> None:
        """Set topics based on BagManager's state"""


        topics = list(self.bags.get_topic_summary().keys())
        search_text = self._search_input.value
        
        filtered_topics = self.filter_topics(topics,search_text)
        
        
        
        self.root.remove_children()
        for topic in filtered_topics:
            is_selected = topic in self.bags.get_selected_topics()
            self.root.add(
                self.get_node_label(topic,is_selected),
                data={"topic": topic, "selected": is_selected},
                allow_expand=False
            )
        
        self.update_border_subtitle()
        self.update_border_title()

    def update_border_subtitle(self):
        """Update subtitle with selected topics count"""
        self.app.query_one(TopicTreePanel).border_subtitle = f"Topic selected: {len(self.bags.get_selected_topics())}"
    
    def update_border_title(self):
        if self.multi_select_mode:
            self.app.query_one(TopicTreePanel).border_title = "Topics(Show Common Topics)"
        else:
            self.app.query_one(TopicTreePanel).border_title = "Topics"

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle topic selection toggle"""
        if event.node.allow_expand:
            return
            
        data = event.node.data
        if data:
            data["selected"] = not data["selected"]
            topic = data["topic"]
            
            if data["selected"]:
                self.bags.select_topic(topic)
            else:
                self.bags.deselect_topic(topic)
            
            print(self.bags.get_selected_topics())
            event.node.label = self.get_node_label(topic, data["selected"])
            self.update_border_subtitle()



    def toggle_select_all(self) -> 'tuple[bool, int]':
        """
        Toggle selection state of all topics.
        
        Returns:
            tuple[bool, int]: (is_all_deselected, count_of_selected)
        """
        if not self.root.children:
            return False, 0
            
        # Check if all topics are already selected
        all_selected = all(node.data["selected"] for node in self.root.children)
        
        # Toggle selection state
        for node in self.root.children:
            node.data["selected"] = not all_selected
            topic = node.data.get("topic")
            if node.data["selected"]:
                self.bags.select_topic(topic)
                node.label = self.get_node_label(topic, True)
            else:
                self.bags.deselect_topic(topic)
                node.label = self.get_node_label(topic, False)
        
        print(self.bags)
        self.update_border_subtitle()
        return all_selected, len(self.bags.get_selected_topics())

class TopicSearchInput(Input):
    """Input widget for searching topics"""
    
    def __init__(self):
        super().__init__(placeholder="Search topics...", id="topic-search")
        self._topic_tree = None

    def on_mount(self) -> None:
        """Get reference to topic tree when mounted"""
        self._topic_tree = self.parent.query_one(TopicTree)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes"""
        self._topic_tree.render_topics()
            

class TopicTreePanel(Container):
    """A wrapper component that contains a search input and a topic tree"""
    
    def __init__(self):
        super().__init__()

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield TopicSearchInput()
        yield TopicTree()

    def on_mount(self) -> None:
        """Initialize when mounted"""
        self.border_title = "Topics"

    def get_topic_tree(self) -> TopicTree:
        """Get the topic tree"""
        return self.query_one(TopicTree)
    

