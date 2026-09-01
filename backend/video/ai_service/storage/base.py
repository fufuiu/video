from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TemporaryObject:
    provider: str
    key: str
    size: int

    def to_dict(self):
        return asdict(self)


class TemporaryStorage(ABC):
    @abstractmethod
    def upload_file(self, local_path, *, purpose='ai-input') -> TemporaryObject:
        raise NotImplementedError

    @abstractmethod
    def signed_download_url(self, key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError
