"""
Simple in-memory rate limiter.
"""

import time
from collections import defaultdict, deque
from typing import Dict


class RateLimiter:
    """Simple in-memory rate limiter by IP address"""
    
    def __init__(self, max_requests: int = 5, window_seconds: int = 300):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds (default: 5 minutes)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request from client IP is allowed"""
        now = time.time()
        client_requests = self.requests[client_ip]
        
        # Remove old requests outside the window
        while client_requests and client_requests[0] < now - self.window_seconds:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) >= self.max_requests:
            return False
        
        # Add current request
        client_requests.append(now)
        return True
    
    def get_remaining_requests(self, client_ip: str) -> int:
        """Get remaining requests for client IP"""
        now = time.time()
        client_requests = self.requests[client_ip]
        
        # Remove old requests
        while client_requests and client_requests[0] < now - self.window_seconds:
            client_requests.popleft()
        
        return max(0, self.max_requests - len(client_requests))
    
    def get_reset_time(self, client_ip: str) -> float:
        """Get timestamp when rate limit resets for client IP"""
        client_requests = self.requests[client_ip]
        if not client_requests:
            return time.time()
        
        return client_requests[0] + self.window_seconds
