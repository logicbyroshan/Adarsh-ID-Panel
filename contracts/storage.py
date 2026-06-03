from typing import Protocol
from typing import BinaryIO

class StorageContract(Protocol):
    def save(self, name: str, content: BinaryIO) -> str:
        ...
        
    def url(self, name: str) -> str:
        ...
        
    def delete(self, name: str) -> None:
        ...
        
    def exists(self, name: str) -> bool:
        ...\n