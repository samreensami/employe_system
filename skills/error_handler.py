import time
import random
import logging
from functools import wraps
from typing import Callable, Any, Optional


class ErrorHandler:
    """
    Handles transient errors with exponential backoff retry mechanism
    """
    
    def __init__(self, max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 60.0, jitter: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay with exponential backoff and optional jitter
        """
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        
        if self.jitter:
            # Add jitter to prevent thundering herd problem
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay
    
    def retry_on_failure(self, exceptions: tuple = (Exception,), condition: Optional[Callable[[Exception], bool]] = None):
        """
        Decorator to retry function calls on failure with exponential backoff
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                last_exception = None
                
                for attempt in range(self.max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        
                        # Check if this exception should trigger a retry
                        should_retry = True
                        if condition:
                            should_retry = condition(e)
                        
                        if not should_retry or attempt >= self.max_retries:
                            self.logger.error(f"Function {func.__name__} failed after {attempt} retries: {str(e)}")
                            raise e
                        
                        if attempt < self.max_retries:
                            delay = self.calculate_delay(attempt)
                            self.logger.warning(
                                f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. "
                                f"Retrying in {delay:.2f}s..."
                            )
                            time.sleep(delay)
                
                # This should never be reached due to the raise in the loop
                raise last_exception
            
            return wrapper
        return decorator
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic
        """
        # Default to retrying on common network/IO errors
        network_errors = (
            ConnectionError,
            TimeoutError,
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
            OSError
        )
        
        decorated_func = self.retry_on_failure(network_errors)(func)
        return decorated_func(*args, **kwargs)
    
    def handle_transient_error(self, error: Exception, context: str = "") -> bool:
        """
        Determine if an error is transient and should be retried
        """
        error_str = str(error).lower()
        
        # Common indicators of transient errors
        transient_indicators = [
            'timeout', 'connection', 'network', 'temporary', 'retry', 
            'reset', 'broken pipe', 'refused', 'unavailable', 'congestion'
        ]
        
        is_transient = any(indicator in error_str for indicator in transient_indicators)
        
        if is_transient:
            self.logger.info(f"Identified transient error in {context}: {error}")
        else:
            self.logger.warning(f"Non-transient error in {context}: {error}")
        
        return is_transient


def main():
    """Example usage of the error handler"""
    handler = ErrorHandler(max_retries=3, base_delay=0.5)
    
    # Example 1: Using the decorator
    @handler.retry_on_failure((ConnectionError, TimeoutError))
    def unreliable_network_call():
        # Simulate a network call that sometimes fails
        if random.random() < 0.7:  # 70% chance of failure
            raise ConnectionError("Network connection failed")
        return "Success!"
    
    # Example 2: Using execute_with_retry
    def another_unreliable_function():
        if random.random() < 0.6:  # 60% chance of failure
            raise TimeoutError("Request timed out")
        return "Another success!"
    
    try:
        result = handler.execute_with_retry(another_unreliable_function)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Final failure after retries: {e}")
    
    print("Error handler initialized successfully")


if __name__ == "__main__":
    main()