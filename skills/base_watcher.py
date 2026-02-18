from abc import ABC, abstractmethod
import os


class BaseWatcher(ABC):
    """
    Abstract Base Class for all watchers.
    Defines the interface that all concrete watcher implementations must follow.
    """
    
    def __init__(self, monitored_path: str):
        self.monitored_path = monitored_path
        self.is_running = False
    
    @abstractmethod
    def start_monitoring(self):
        """Start the monitoring process"""
        pass
    
    @abstractmethod
    def stop_monitoring(self):
        """Stop the monitoring process"""
        pass
    
    @abstractmethod
    def handle_new_file(self, file_path: str):
        """Handle a newly detected file"""
        pass
    
    def ensure_directory_exists(self, path: str):
        """Ensure that a directory exists, creating it if necessary"""
        os.makedirs(path, exist_ok=True)