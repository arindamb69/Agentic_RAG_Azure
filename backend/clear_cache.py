import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))

from backend.services.cache import CacheService
try:
    cache = CacheService()
    if cache.client:
        print("Clearing Redis cache...")
        cache.client.flushdb()
        print("Cache cleared successfully.")
    else:
        print("Using in-memory dictionary or failed to connect to Redis.")
except Exception as e:
    print(f"Failed to clear cache: {e}")
