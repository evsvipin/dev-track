"""
OOP classes for DevTrack's two entities: Reporter and Issue.

These are plain Python classes, not Django ORM models. DevTrack stores its
data in JSON files, so each class only needs to validate itself and turn
itself into a dict (to_dict) that can be saved to JSON or returned by a view.

Class hierarchy:

    BaseEntity (abstract)
    ├── Reporter
    └── Issue
        ├── CriticalIssue     (priority == 'critical')
        └── LowPriorityIssue  (priority == 'low')
"""

from abc import ABC, abstractmethod
from datetime import datetime

ISSUE_STATUSES = ('open', 'in_progress', 'resolved', 'closed')
ISSUE_PRIORITIES = ('low', 'medium', 'high', 'critical')


class BaseEntity(ABC):
    """Common parent of every entity. Subclasses must implement validate()."""

    @abstractmethod
    def validate(self):
        pass

    def to_dict(self):
        return {
            key: value
            for key, value in self.__dict__.items()
        }


def validate_positive_int(value, field_name):
    # bool is a subclass of int in Python, so True/False are rejected explicitly
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{field_name} must be a positive integer')


def validate_non_empty_string(value, message):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)


class Reporter(BaseEntity):
    """A person who files issues."""

    def __init__(self, id, name, email, team):
        self.id = id
        self.name = name
        self.email = email
        self.team = team

    def validate(self):
        validate_positive_int(self.id, 'id')
        validate_non_empty_string(self.name, 'Name cannot be empty')
        if not isinstance(self.email, str) or '@' not in self.email:
            raise ValueError('Invalid email')
        validate_non_empty_string(self.team, 'Team cannot be empty')


class Issue(BaseEntity):
    """A bug report or task filed by a Reporter (one Reporter -> many Issues)."""

    def __init__(self, id, title, description, status, priority, reporter_id, created_at=None):
        self.id = id
        self.title = title
        self.description = description
        self.status = status
        self.priority = priority
        self.reporter_id = reporter_id
        self.created_at = created_at or str(datetime.now())

    def validate(self):
        validate_positive_int(self.id, 'id')
        validate_non_empty_string(self.title, 'Title cannot be empty')
        if not isinstance(self.description, str):
            raise ValueError('Description must be a string')
        if self.status not in ISSUE_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(ISSUE_STATUSES)}")
        if self.priority not in ISSUE_PRIORITIES:
            raise ValueError(f"Priority must be one of: {', '.join(ISSUE_PRIORITIES)}")
        validate_positive_int(self.reporter_id, 'reporter_id')

    def describe(self):
        return f"{self.title} [{self.priority}]"


class CriticalIssue(Issue):
    """Issue with priority 'critical'. Overrides describe() to flag urgency."""

    def describe(self):
        return f"[URGENT] {self.title} — needs immediate attention"


class LowPriorityIssue(Issue):
    """Issue with priority 'low'. Overrides describe() to signal it can wait."""

    def describe(self):
        return f"{self.title} — low priority, handle when free"
