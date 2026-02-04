import redis
from config import settings
import json

class CacheService:
    def __init__(self):
        self.client = None
        if settings.REDIS_HOST:
            try:
                if settings.REDIS_USE_ENTRA_ID:
                    # Use Azure Entra ID (Azure AD) authentication
                    from azure.identity import DefaultAzureCredential
                    
                    try:
                        # Get token for Azure Cache for Redis
                        credential = DefaultAzureCredential()
                        token = credential.get_token("https://redis.azure.com/.default")
                        
                        # For Azure Cache for Redis with Entra ID:
                        # - Username should be the Object ID of the principal
                        # - Password is the access token
                        self.credential = credential
                        redis_user = settings.REDIS_PASSWORD or "default"
                        print(f"Redis Cache: Attempting Entra ID connection for user/ID: {redis_user}")
                        
                        self.client = redis.Redis(
                            host=settings.REDIS_HOST,
                            port=settings.REDIS_PORT,
                            username=redis_user,
                            password=token.token,
                            ssl=settings.REDIS_SSL,
                            decode_responses=True
                        )
                        print(f"Redis Cache: Client initialized for {settings.REDIS_HOST}")
                    except Exception as e:
                        print("---------------------------------------------------------")
                        print("!!! AZURE ID AUTHENTICATION FAILED FOR REDIS !!!")
                        print(f"Error: {e}")
                        print("Please ensure you are authenticated to Azure:")
                        print("1. Run 'az login' in your terminal")
                        print("2. OR set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID in .env")
                        print("Redis caching will be disabled until fixed.")
                        print("---------------------------------------------------------")
                        self.client = None
                else:
                    # Standard password-based authentication
                    self.client = redis.Redis(
                        host=settings.REDIS_HOST,
                        port=settings.REDIS_PORT,
                        password=settings.REDIS_PASSWORD,
                        ssl=settings.REDIS_SSL,
                        decode_responses=True
                    )
                    print(f"Redis Cache: Connected with password to {settings.REDIS_HOST}")
            except Exception as e:
                print(f"Redis connection failed: {e}")
                self.client = None

    def _refresh_token_if_needed(self):
        """Refresh the Entra ID token if using Entra ID authentication."""
        if settings.REDIS_USE_ENTRA_ID and hasattr(self, 'credential') and self.client:
            try:
                from azure.identity import DefaultAzureCredential
                token = self.credential.get_token("https://redis.azure.com/.default")
                # Reconnect with new token
                self.client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    username=settings.REDIS_PASSWORD or "default",
                    password=token.token,
                    ssl=settings.REDIS_SSL,
                    decode_responses=True
                )
            except Exception as e:
                print(f"Redis token refresh failed: {e}")

    def get(self, key):
        if self.client:
            try:
                print("Cache: Checking Redis...")
                val = self.client.get(key)
                print(f"Cache: Result {val}")
                return val
            except redis.AuthenticationError as auth_err:
                print(f"Cache: Authentication failed (WRONGPASS). Check if Username/ID '{settings.REDIS_PASSWORD}' matches the 'Name' in Redis Data Access Configuration.")
                # Token might have expired, try to refresh
                print("Cache: Attempting token refresh...")
                self._refresh_token_if_needed()
                try:
                    val = self.client.get(key)
                    return val
                except Exception as e:
                    print(f"Cache: Error after refresh: {e}")
                    return None
            except Exception as e:
                print(f"Cache: Error getting key: {e}")
                return None
        return None

    def set(self, key, value, ttl=300):
        if self.client:
            try:
                self.client.setex(key, ttl, value)
            except redis.AuthenticationError:
                # Token might have expired, try to refresh
                print("Cache: Token expired, refreshing...")
                self._refresh_token_if_needed()
                try:
                    self.client.setex(key, ttl, value)
                except Exception as e:
                    print(f"Cache: Error setting key after refresh: {e}")
            except Exception as e:
                print(f"Cache: Error setting key: {e}")
