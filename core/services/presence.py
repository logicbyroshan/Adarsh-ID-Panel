import time
from typing import List
from django.core.cache import cache

class PresenceService:
    """
    Manages live presence indicator heartbeats and cell lease locks.
    Leverages Django cache (Redis in prod, local-memory fallback in dev).
    """

    @staticmethod
    def enter_table(table_id: str, user_id: str) -> None:
        """
        Registers user activity in a table. Heartbeats refresh presence state.
        """
        key = f"presence:table:{table_id}"
        # Store user presence with active timestamp
        now = time.time()
        active_users = cache.get(key, {})
        
        # Add or update user activity
        active_users[user_id] = now
        
        # Filter out users who haven't sent a heartbeat in the last 15 seconds
        cleaned_users = {
            uid: ts for uid, ts in active_users.items() if now - ts < 15
        }
        
        # Save presence map back with a short expiry (30 seconds)
        cache.set(key, cleaned_users, timeout=30)

    @staticmethod
    def get_table_users(table_id: str) -> List[str]:
        """
        Returns list of active User IDs currently inside a table.
        """
        key = f"presence:table:{table_id}"
        active_users = cache.get(key, {})
        now = time.time()
        
        # Filter and return list
        return [uid for uid, ts in active_users.items() if now - ts < 15]

    @staticmethod
    def acquire_cell_lock(record_id: str, field_key: str, user_id: str) -> bool:
        """
        Attempts to acquire a 5-second cell editing lease lock.
        Returns True if successful, False if blocked by another occupant.
        """
        lock_key = f"lock:cell:{record_id}:{field_key}"
        
        # cache.add only writes if the key does not already exist
        is_acquired = cache.add(lock_key, user_id, timeout=5)
        
        if is_acquired:
            return True
            
        # If write failed, check if the current lock belongs to the same user
        current_owner = cache.get(lock_key)
        return current_owner == user_id

    @staticmethod
    def release_cell_lock(record_id: str, field_key: str, user_id: str) -> None:
        """
        Releases cell editing lease if owned by the calling user.
        """
        lock_key = f"lock:cell:{record_id}:{field_key}"
        current_owner = cache.get(lock_key)
        if current_owner == user_id:
            cache.delete(lock_key)
