"""
Redis client for session management and counters
"""
import redis
import json
import os
from typing import Optional

class RedisClient:
    """Redis connection manager"""
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            redis_host = os.getenv('REDIS_HOST', 'redis')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            self._client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=0,
                decode_responses=True
            )
    
    def get_client(self):
        """Get Redis client instance"""
        return self._client
    
    # Onsite counter methods
    def get_onsite_count(self) -> int:
        """Get current number of people onsite"""
        count = self._client.get('attendance:onsite_count')
        return int(count) if count else 0
    
    def increment_onsite(self) -> int:
        """Increment onsite count"""
        return self._client.incr('attendance:onsite_count')
    
    def decrement_onsite(self) -> int:
        """Decrement onsite count"""
        count = self._client.decr('attendance:onsite_count')
        # Don't go below 0
        if count < 0:
            self._client.set('attendance:onsite_count', 0)
            return 0
        return count
    
    def set_onsite_count(self, count: int):
        """Set onsite count directly"""
        self._client.set('attendance:onsite_count', max(0, count))
    
    # Cooldown tracking (anti-spam)
    def is_in_cooldown(self, camera_id: str, gate_id: str) -> bool:
        """Check if a crossing is in cooldown period"""
        key = f'attendance:cooldown:{camera_id}:{gate_id}'
        return self._client.exists(key) > 0
    
    def set_cooldown(self, camera_id: str, gate_id: str, seconds: int):
        """Set cooldown period for a gate"""
        key = f'attendance:cooldown:{camera_id}:{gate_id}'
        self._client.setex(key, seconds, '1')
    
    # Trajectory tracking
    def store_detection_position(self, camera_id: str, detection_id: str, x: float, y: float, timestamp: float):
        """Store detection position for trajectory analysis"""
        key = f'attendance:trajectory:{camera_id}:{detection_id}'
        data = json.dumps({'x': x, 'y': y, 'timestamp': timestamp})
        self._client.lpush(key, data)
        self._client.ltrim(key, 0, 9)  # Keep last 10 positions
        self._client.expire(key, 10)  # Expire after 10 seconds
    
    def get_detection_trajectory(self, camera_id: str, detection_id: str) -> list:
        """Get stored trajectory for a detection"""
        key = f'attendance:trajectory:{camera_id}:{detection_id}'
        positions = self._client.lrange(key, 0, -1)
        return [json.loads(p) for p in positions]


# Global instance
redis_client = RedisClient()