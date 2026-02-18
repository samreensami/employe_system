import os
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class MarkdownHandler(FileSystemEventHandler):
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            filename = os.path.basename(event.src_path)
            print(f'New Task Detected: {filename}')
            
            # Log the event
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f'[{timestamp}] New Task Detected: {filename}\n'
            
            with open(self.log_file_path, 'a', encoding='utf-8') as log_file:
                log_file.write(log_entry)


def main():
    inbox_path = '../obsidian_vault/inbox'
    log_path = '../logs/agent_log.txt'
    
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    # Create inbox directory if it doesn't exist
    os.makedirs(inbox_path, exist_ok=True)
    
    event_handler = MarkdownHandler(log_path)
    observer = Observer()
    observer.schedule(event_handler, path=inbox_path, recursive=False)
    
    print(f'Starting watcher for {inbox_path}...')
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print('\nWatcher stopped.')
    
    observer.join()


if __name__ == '__main__':
    main()