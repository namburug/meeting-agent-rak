"""
Minimal integration interface. Slack is implemented; Jira/Linear/GitHub can
plug into the same shape (send(meeting, items) -> external_ref) without
touching the FastAPI layer.
"""
from abc import ABC, abstractmethod


class Integration(ABC):
    name: str

    @abstractmethod
    def post_recap(self, meeting: dict, approved_items: list[dict]) -> str:
        """Send the recap / create the tickets. Returns an external reference string."""
        raise NotImplementedError
