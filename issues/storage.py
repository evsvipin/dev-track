"""
Reading and writing the JSON files that hold DevTrack's data.

Each file holds a JSON list of records (dicts). Views call these helpers
instead of opening files themselves, so the file handling lives in one place.
"""

import json

from django.conf import settings

REPORTERS_FILE = 'reporters.json'
ISSUES_FILE = 'issues.json'


def get_file_path(filename):
    return settings.DATA_DIR / filename


def read_records(filename):
    """Return the list of records in the file, or [] if it is missing or empty."""
    path = get_file_path(filename)
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if not content.strip():
        return []
    return json.loads(content)


def write_records(filename, records):
    path = get_file_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=4, ensure_ascii=False)


def find_by_id(records, record_id):
    """Loop through the records and return the one whose id matches, or None."""
    for record in records:
        if record['id'] == record_id:
            return record
    return None


def next_id(records):
    """The id to give a new record when the client does not send one."""
    return max((record['id'] for record in records), default=0) + 1
