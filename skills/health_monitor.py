import time
import psutil
import subprocess
from datetime import datetime
from threading import Thread
import os
import json


class HealthMonitor:
    """
    Monitors the health of all watchers and services, checking every 5 minutes
    """
    
    def __init__(self, log_path="logs/health_monitor.log"):
        self.log_path = log_path
        self.running = False
        self.check_interval = 300  # 5 minutes in seconds
        self.services_to_monitor = [
            "filesystem_watcher",
            "gmail_watcher",
            "whatsapp_watcher",
            "odoo_watcher",
            "task_processor",
            "execution_engine"
        ]
        
        # Ensure logs directory exists
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    def log_message(self, message):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    
    def check_process_health(self):
        """Check if required processes are running"""
        running_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if any of our services are running
                process_cmdline = ' '.join(proc.info['cmdline']).lower() if proc.info['cmdline'] else ''
                process_name = proc.info['name'].lower()
                
                for service in self.services_to_monitor:
                    if service.lower() in process_cmdline or service.lower() in process_name:
                        running_processes.append({
                            'name': service,
                            'pid': proc.info['pid'],
                            'status': 'running'
                        })
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # Check for missing services
        missing_services = []
        for service in self.services_to_monitor:
            if not any(service.lower() in rp['name'].lower() for rp in running_processes):
                missing_services.append({
                    'name': service,
                    'status': 'not_running'
                })
        
        return running_processes, missing_services
    
    def check_system_resources(self):
        """Check system resource usage"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'disk_usage': disk_usage,
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_health_report(self):
        """Generate a comprehensive health report"""
        running_processes, missing_services = self.check_process_health()
        system_resources = self.check_system_resources()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'processes': {
                'running': running_processes,
                'missing': missing_services
            },
            'system_resources': system_resources,
            'overall_status': 'healthy' if not missing_services else 'degraded'
        }
        
        return report
    
    def log_health_check(self):
        """Perform a health check and log the results"""
        report = self.generate_health_report()
        
        message = f"Health Check - Overall: {report['overall_status']}"
        message += f" | Running: {len(report['processes']['running'])}"
        message += f" | Missing: {len(report['processes']['missing'])}"
        message += f" | CPU: {report['system_resources']['cpu_percent']}%"
        message += f" | Memory: {report['system_resources']['memory_percent']}%"
        
        self.log_message(message)
        
        # Also log detailed info
        if report['processes']['missing']:
            missing_names = [s['name'] for s in report['processes']['missing']]
            self.log_message(f"WARNING: Missing services - {', '.join(missing_names)}")
        
        return report
    
    def start_monitoring(self):
        """Start the health monitoring loop"""
        self.running = True
        self.log_message("Health Monitor started")
        
        while self.running:
            try:
                self.log_health_check()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                self.log_message("Health Monitor stopped by user")
                break
            except Exception as e:
                self.log_message(f"Error in health monitor: {str(e)}")
                time.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """Stop the health monitoring"""
        self.running = False
        self.log_message("Health Monitor stopped")
    
    def run_once(self):
        """Run a single health check and return the report"""
        return self.generate_health_report()


def main():
    """Example usage of the health monitor"""
    monitor = HealthMonitor()
    report = monitor.run_once()
    
    print("System Health Report:")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()