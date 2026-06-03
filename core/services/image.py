import io
import uuid
from typing import IO
from PIL import Image
from core.services.storage import StorageService

class ImageService:
    """
    Handles image compression, cropping, and thumbnail scaling.
    """

    def __init__(self, storage_service: StorageService = None):
        self.storage = storage_service or StorageService()

    def process_and_upload(self, file_data: io.BytesIO, table_id: str, field_key: str) -> dict:
        """
        Compresses input image, scales size, creates a thumbnail, and uploads both.
        Returns metadata: {'original_url': '...', 'thumbnail_url': '...', ...}
        """
        # Open source image
        img = Image.open(file_data)
        
        # Convert RGBA/P to RGB if JPEG format
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            # Create a white background instead of dropping transparency to black
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 1. Generate Compressed Original (max width 800px)
        orig_img = img.copy()
        orig_img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        orig_io = io.BytesIO()
        orig_img.save(orig_io, format='JPEG', quality=85)
        orig_io.seek(0)
        
        # 2. Generate Thumbnail (max width 200px)
        thumb_img = img.copy()
        thumb_img.thumbnail((200, 200), Image.Resampling.LANCZOS)
        thumb_io = io.BytesIO()
        thumb_img.save(thumb_io, format='JPEG', quality=75)
        thumb_io.seek(0)
        
        # Define directory keys
        uuid_str = uuid.uuid4().hex
        orig_path = f"cards/{table_id}/{field_key}/{uuid_str}_original.jpg"
        thumb_path = f"cards/{table_id}/{field_key}/{uuid_str}_thumb.jpg"
        
        # Upload using Storage Service
        original_url = self.storage.save_file(orig_path, orig_io)
        thumbnail_url = self.storage.save_file(thumb_path, thumb_io)
        
        return {
            'original_path': orig_path,
            'original_url': original_url,
            'thumbnail_path': thumb_path,
            'thumbnail_url': thumbnail_url
        }

    def delete_images(self, metadata: dict) -> None:
        """
        Cleans up image files from the storage backend.
        """
        orig_path = metadata.get('original_path')
        thumb_path = metadata.get('thumbnail_path')
        
        if orig_path:
            self.storage.delete_file(orig_path)
        if thumb_path:
            self.storage.delete_file(thumb_path)
