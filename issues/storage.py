"""
Storage backends: where reporters and issues are saved.

Views never open the JSON files or query the database themselves. They call
get_storage(), which returns the backend named by settings.STORAGE_BACKEND:

    BaseStorage (abstract)
    ├── JsonStorage       data/reporters.json and data/issues.json
    └── DatabaseStorage   PostgreSQL tables via the ORM models in db_models.py

Both backends take and return plain dicts (the output of to_dict()), so the
views work the same whichever backend is active. `entity` is either
REPORTERS or ISSUES.
"""

import json
from abc import ABC, abstractmethod

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from issues.db_models import IssueModel, ReporterModel

REPORTERS = 'reporters'
ISSUES = 'issues'


class BaseStorage(ABC):
    @abstractmethod
    def find_all(self, entity, **filters):
        """Return every record, or only those whose fields equal `filters`."""

    @abstractmethod
    def find_by_id(self, entity, record_id):
        """Return the record with this id, or None."""

    @abstractmethod
    def create(self, entity, record):
        """Save a new record, give it the next id, and return the saved record."""

    @abstractmethod
    def update(self, entity, record_id, record):
        """Overwrite the record's fields. Return the saved record, or None if it doesn't exist."""

    @abstractmethod
    def delete(self, entity, record_id):
        """Delete the record. Return True if it existed, False otherwise."""


class JsonStorage(BaseStorage):
    """Each entity is a JSON list of records in its own file under DATA_DIR."""

    FILES = {
        REPORTERS: 'reporters.json',
        ISSUES: 'issues.json',
    }

    def get_file_path(self, entity):
        return settings.DATA_DIR / self.FILES[entity]

    def read_records(self, entity):
        """Return the list in the file, or [] if the file is missing or empty."""
        path = self.get_file_path(entity)
        if not path.exists():
            return []
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        if not content.strip():
            return []
        return json.loads(content)

    def write_records(self, entity, records):
        path = self.get_file_path(entity)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=4, ensure_ascii=False)

    def find_all(self, entity, **filters):
        return [
            record for record in self.read_records(entity)
            if all(record.get(field) == value for field, value in filters.items())
        ]

    def find_by_id(self, entity, record_id):
        for record in self.read_records(entity):
            if record['id'] == record_id:
                return record
        return None

    def create(self, entity, record):
        records = self.read_records(entity)
        new_id = max((r['id'] for r in records), default=0) + 1
        saved = {**record, 'id': new_id}
        records.append(saved)
        self.write_records(entity, records)
        return saved

    def update(self, entity, record_id, record):
        records = self.read_records(entity)
        for index, existing in enumerate(records):
            if existing['id'] == record_id:
                records[index] = {**record, 'id': record_id}
                self.write_records(entity, records)
                return records[index]
        return None

    def delete(self, entity, record_id):
        records = self.read_records(entity)
        remaining = [r for r in records if r['id'] != record_id]
        if len(remaining) == len(records):
            return False
        self.write_records(entity, remaining)
        return True


class DatabaseStorage(BaseStorage):
    """Each entity is a PostgreSQL table, accessed through its Django ORM model."""

    MODELS = {
        REPORTERS: ReporterModel,
        ISSUES: IssueModel,
    }
    # The database assigns id and created_at is set once on create
    READ_ONLY_FIELDS = ('id', 'created_at')

    def find_all(self, entity, **filters):
        rows = self.MODELS[entity].objects.filter(**filters)
        return [row.to_dict() for row in rows]

    def find_by_id(self, entity, record_id):
        row = self.MODELS[entity].objects.filter(pk=record_id).first()
        return row.to_dict() if row else None

    def create(self, entity, record):
        fields = {key: value for key, value in record.items() if key != 'id'}
        row = self.MODELS[entity].objects.create(**fields)
        row.refresh_from_db()
        return row.to_dict()

    def update(self, entity, record_id, record):
        fields = {key: value for key, value in record.items() if key not in self.READ_ONLY_FIELDS}
        updated_count = self.MODELS[entity].objects.filter(pk=record_id).update(**fields)
        if updated_count == 0:
            return None
        return self.find_by_id(entity, record_id)

    def delete(self, entity, record_id):
        deleted_count, _ = self.MODELS[entity].objects.filter(pk=record_id).delete()
        return deleted_count > 0


STORAGE_BACKENDS = {
    'json': JsonStorage,
    'database': DatabaseStorage,
}


def get_storage():
    """Return the storage backend selected by settings.STORAGE_BACKEND."""
    try:
        backend_class = STORAGE_BACKENDS[settings.STORAGE_BACKEND]
    except KeyError:
        raise ImproperlyConfigured(
            f"STORAGE_BACKEND must be one of: {', '.join(STORAGE_BACKENDS)}"
        )
    return backend_class()
