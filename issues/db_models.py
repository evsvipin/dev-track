"""
Django ORM models: the PostgreSQL tables behind DatabaseStorage.

These classes only describe how records are stored (columns, types, the
foreign key). The business rules (validation, describe()) stay in the OOP
classes in issues/models.py, which also imports this module so Django
registers these tables.

Tables:
    reporters  id | name | email | team
    issues     id | title | description | status | priority | reporter_id -> reporters.id | created_at
"""

from datetime import datetime

from django.db import models

from issues.models import ISSUE_PRIORITIES, ISSUE_STATUSES


class ReporterModel(models.Model):
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=254)
    team = models.CharField(max_length=50)

    class Meta:
        db_table = 'reporters'
        ordering = ['id']

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'team': self.team,
        }


class IssueModel(models.Model):
    STATUS_CHOICES = [(status, status) for status in ISSUE_STATUSES]
    PRIORITY_CHOICES = [(priority, priority) for priority in ISSUE_PRIORITIES]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    # One Reporter -> many Issues. PROTECT stops a reporter from being
    # deleted while issues still point to them.
    reporter = models.ForeignKey(ReporterModel, on_delete=models.PROTECT, related_name='issues')
    created_at = models.DateTimeField(default=datetime.now)

    class Meta:
        db_table = 'issues'
        ordering = ['id']

    def __str__(self):
        return self.title

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'reporter_id': self.reporter_id,
            'created_at': str(self.created_at),
        }
