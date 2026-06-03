import os
from typing import IO
from django.conf import settings
from django.core.files.storage import default_storage

class StorageService:
    """
    Abstraction layer for media and document assets.
    V1: Local File System storage.
    V2/V3 can swap this class with Cloudflare R2 or MinIO S3 drivers.
    """

    def save_file(self, path: str, file_io: IO) -> str:
        """
        Saves file to destination path.
        Returns the absolute URL to access the resource.
        """
        # Save file using Django's default storage engine
        saved_name = default_storage.save(path, file_io)
        # Construct absolute URL
        return settings.MEDIA_URL + saved_name

    def read_file(self, path: str) -> IO:
        """
        Returns a file-like object for the requested path.
        """
        # Strip media URL prefix if present to obtain relative file path
        if path.startswith(settings.MEDIA_URL):
            path = path[len(settings.MEDIA_URL):]
            
        return default_storage.open(path, 'rb')

    def delete_file(self, path: str) -> None:
        """
        Removes file from storage system.
        """
        if path.startswith(settings.MEDIA_URL):
            path = path[len(settings.MEDIA_URL):]
            
        if default_storage.exists(path):
            default_storage.delete(path)
