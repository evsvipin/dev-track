"""
Tests for the DevTrack API and OOP classes.

Run with:  python manage.py test      (PostgreSQL must be running: docker compose up -d)
           In JSON mode (STORAGE_BACKEND=json) the database tests are skipped.

Every API test runs twice, once per storage backend:
  - Json...Tests      use a temporary folder, so data/*.json is never touched
  - Database...Tests  use a temporary test database that Django creates and drops
"""

import json
import tempfile
from pathlib import Path
from unittest import skipIf

from django.conf import settings
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from issues.models import BaseEntity, CriticalIssue, Issue, LowPriorityIssue, Reporter

STORAGE_BACKEND_IS_JSON = settings.STORAGE_BACKEND == 'json'


class ModelTests(SimpleTestCase):
    def test_base_entity_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            BaseEntity()

    def test_reporter_validation(self):
        Reporter(1, 'Asha Rao', 'asha@example.com', 'backend').validate()
        Reporter(None, 'Asha Rao', 'asha@example.com', 'backend').validate()
        with self.assertRaisesMessage(ValueError, 'Name cannot be empty'):
            Reporter(1, '', 'asha@example.com', 'backend').validate()
        with self.assertRaisesMessage(ValueError, 'Invalid email'):
            Reporter(1, 'Asha Rao', 'asha.example.com', 'backend').validate()
        with self.assertRaisesMessage(ValueError, 'id must be a positive integer'):
            Reporter(0, 'Asha Rao', 'asha@example.com', 'backend').validate()

    def test_issue_validation(self):
        with self.assertRaisesMessage(ValueError, 'Title cannot be empty'):
            Issue(1, '', 'desc', 'open', 'high', 1).validate()
        with self.assertRaisesMessage(ValueError, 'Status must be one of'):
            Issue(1, 'Bug', 'desc', 'done', 'high', 1).validate()
        with self.assertRaisesMessage(ValueError, 'Priority must be one of'):
            Issue(1, 'Bug', 'desc', 'open', 'urgent', 1).validate()
        with self.assertRaisesMessage(ValueError, 'reporter_id must be a positive integer'):
            Issue(1, 'Bug', 'desc', 'open', 'high', '1').validate()

    def test_describe_is_overridden_by_subclasses(self):
        self.assertEqual(Issue(1, 'Bug', '', 'open', 'high', 1).describe(), 'Bug [high]')
        self.assertEqual(
            CriticalIssue(1, 'Bug', '', 'open', 'critical', 1).describe(),
            '[URGENT] Bug — needs immediate attention',
        )
        self.assertEqual(
            LowPriorityIssue(1, 'Bug', '', 'open', 'low', 1).describe(),
            'Bug — low priority, handle when free',
        )

    def test_to_dict_contains_all_fields(self):
        data = Issue(1, 'Bug', 'desc', 'open', 'high', 2, created_at='now').to_dict()
        self.assertEqual(data, {
            'id': 1, 'title': 'Bug', 'description': 'desc', 'status': 'open',
            'priority': 'high', 'reporter_id': 2, 'created_at': 'now',
        })


# ---------- API tests, shared by both backends ----------

class ApiTestMixin:
    def post(self, url, body):
        return self.client.post(url, data=json.dumps(body), content_type='application/json')

    def patch(self, url, body):
        return self.client.patch(url, data=json.dumps(body), content_type='application/json')

    def create_reporter(self, **overrides):
        body = {'name': 'Asha Rao', 'email': 'asha@example.com', 'team': 'backend', **overrides}
        return self.post('/api/reporters/', body)

    def create_issue(self, **overrides):
        body = {
            'title': 'Login button not working on mobile',
            'description': 'Users on iOS 17 cannot tap the login button',
            'status': 'open',
            'priority': 'critical',
            'reporter_id': 1,
            **overrides,
        }
        return self.post('/api/issues/', body)


class ReporterApiTestsMixin(ApiTestMixin):
    def test_create_and_list_reporters(self):
        response = self.create_reporter()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {
            'id': 1, 'name': 'Asha Rao', 'email': 'asha@example.com', 'team': 'backend',
        })

        self.create_reporter(name='Ben Lee', email='ben@example.com', team='frontend')
        response = self.client.get('/api/reporters/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['id'] for r in response.json()], [1, 2])

    def test_id_in_body_is_ignored(self):
        response = self.create_reporter(id=50)
        self.assertEqual(response.json()['id'], 1)

    def test_get_reporter_by_id(self):
        self.create_reporter()
        response = self.client.get('/api/reporters/?id=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Asha Rao')

    def test_get_missing_reporter_returns_404(self):
        response = self.client.get('/api/reporters/?id=99')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'error': 'Reporter not found'})

    def test_invalid_reporter_returns_400(self):
        response = self.create_reporter(email='not-an-email')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Invalid email'})

    def test_missing_fields_return_400(self):
        response = self.post('/api/reporters/', {'name': 'Asha Rao'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Missing required field(s): email, team'})

    def test_non_integer_id_param_returns_400(self):
        response = self.client.get('/api/reporters/?id=abc')
        self.assertEqual(response.status_code, 400)

    def test_update_reporter(self):
        self.create_reporter()
        response = self.patch('/api/reporters/?id=1', {'team': 'devops'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'id': 1, 'name': 'Asha Rao', 'email': 'asha@example.com', 'team': 'devops',
        })
        self.assertEqual(self.client.get('/api/reporters/?id=1').json()['team'], 'devops')

    def test_update_reporter_validation_and_errors(self):
        self.create_reporter()
        self.assertEqual(self.patch('/api/reporters/?id=1', {'email': 'bad'}).status_code, 400)
        self.assertEqual(self.patch('/api/reporters/?id=1', {'id': 7}).status_code, 400)
        self.assertEqual(self.patch('/api/reporters/?id=1', {}).status_code, 400)
        self.assertEqual(self.patch('/api/reporters/', {'team': 'x'}).status_code, 400)
        self.assertEqual(self.patch('/api/reporters/?id=99', {'team': 'x'}).status_code, 404)

    def test_delete_reporter(self):
        self.create_reporter()
        response = self.client.delete('/api/reporters/?id=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Reporter 1 deleted'})
        self.assertEqual(self.client.get('/api/reporters/?id=1').status_code, 404)
        self.assertEqual(self.client.delete('/api/reporters/?id=1').status_code, 404)

    def test_cannot_delete_reporter_with_issues(self):
        self.create_reporter()
        self.create_issue()
        response = self.client.delete('/api/reporters/?id=1')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get('/api/reporters/?id=1').status_code, 200)


class IssueApiTestsMixin(ApiTestMixin):
    def setUp(self):
        super().setUp()
        self.create_reporter()

    def test_create_critical_issue_matches_sample_response(self):
        response = self.create_issue(id=1)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn('created_at', data)
        del data['created_at']
        self.assertEqual(data, {
            'id': 1,
            'title': 'Login button not working on mobile',
            'description': 'Users on iOS 17 cannot tap the login button',
            'status': 'open',
            'priority': 'critical',
            'reporter_id': 1,
            'message': '[URGENT] Login button not working on mobile — needs immediate attention',
        })

    def test_created_at_is_kept_when_reading_back(self):
        created = self.create_issue().json()
        fetched = self.client.get('/api/issues/?id=1').json()
        self.assertEqual(fetched['created_at'], created['created_at'])

    def test_message_depends_on_priority(self):
        low = self.create_issue(title='Typo', priority='low').json()
        medium = self.create_issue(title='Slow page', priority='medium').json()
        self.assertEqual(low['message'], 'Typo — low priority, handle when free')
        self.assertEqual(medium['message'], 'Slow page [medium]')

    def test_message_is_not_stored(self):
        self.create_issue()
        self.assertNotIn('message', self.client.get('/api/issues/?id=1').json())

    def test_empty_title_returns_400(self):
        response = self.create_issue(title='')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Title cannot be empty'})

    def test_invalid_status_returns_400(self):
        response = self.create_issue(status='done')
        self.assertEqual(response.status_code, 400)

    def test_unknown_reporter_returns_400(self):
        response = self.create_issue(reporter_id=42)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Reporter with id 42 does not exist'})

    def test_invalid_json_returns_400(self):
        response = self.client.post('/api/issues/', data='{bad json', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_issue_by_id(self):
        self.create_issue()
        response = self.client.get('/api/issues/?id=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['title'], 'Login button not working on mobile')

    def test_get_missing_issue_returns_404(self):
        response = self.client.get('/api/issues/?id=99')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'error': 'Issue not found'})

    def test_filter_by_status(self):
        self.create_issue(title='A', status='open')
        self.create_issue(title='B', status='closed')
        self.create_issue(title='C', status='open')
        response = self.client.get('/api/issues/?status=open')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([i['title'] for i in response.json()], ['A', 'C'])

    def test_invalid_status_filter_returns_400(self):
        response = self.client.get('/api/issues/?status=done')
        self.assertEqual(response.status_code, 400)

    def test_get_all_issues(self):
        self.create_issue(title='A')
        self.create_issue(title='B')
        response = self.client.get('/api/issues/')
        self.assertEqual([i['title'] for i in response.json()], ['A', 'B'])

    def test_update_issue_status(self):
        created = self.create_issue().json()
        response = self.patch('/api/issues/?id=1', {'status': 'resolved'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'resolved')
        self.assertEqual(data['title'], 'Login button not working on mobile')
        self.assertEqual(data['created_at'], created['created_at'])
        self.assertEqual(self.client.get('/api/issues/?id=1').json()['status'], 'resolved')

    def test_update_priority_changes_message(self):
        self.create_issue(priority='critical')
        response = self.patch('/api/issues/?id=1', {'priority': 'low'})
        self.assertEqual(
            response.json()['message'],
            'Login button not working on mobile — low priority, handle when free',
        )

    def test_update_issue_errors(self):
        self.create_issue()
        self.assertEqual(self.patch('/api/issues/?id=1', {'status': 'done'}).status_code, 400)
        self.assertEqual(self.patch('/api/issues/?id=1', {'title': ''}).status_code, 400)
        self.assertEqual(self.patch('/api/issues/?id=1', {'created_at': 'x'}).status_code, 400)
        self.assertEqual(self.patch('/api/issues/?id=1', {'reporter_id': 42}).status_code, 400)
        self.assertEqual(self.patch('/api/issues/', {'status': 'closed'}).status_code, 400)
        self.assertEqual(self.patch('/api/issues/?id=99', {'status': 'closed'}).status_code, 404)

    def test_move_issue_to_another_reporter(self):
        self.create_reporter(name='Ben Lee', email='ben@example.com', team='frontend')
        self.create_issue()
        response = self.patch('/api/issues/?id=1', {'reporter_id': 2})
        self.assertEqual(response.json()['reporter_id'], 2)

    def test_delete_issue(self):
        self.create_issue()
        response = self.client.delete('/api/issues/?id=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Issue 1 deleted'})
        self.assertEqual(self.client.get('/api/issues/?id=1').status_code, 404)
        self.assertEqual(self.client.delete('/api/issues/?id=1').status_code, 404)
        self.assertEqual(self.client.delete('/api/issues/').status_code, 400)

    def test_unsupported_method_returns_405(self):
        response = self.client.put('/api/issues/')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response['Allow'], 'GET, POST, PATCH, DELETE')


# ---------- run the API tests against each backend ----------

class JsonBackendMixin:
    """Point the JSON backend at an empty temporary folder."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.data_dir = Path(temp_dir.name)
        settings_override = override_settings(STORAGE_BACKEND='json', DATA_DIR=self.data_dir)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        super().setUp()


class DatabaseBackendMixin:
    def setUp(self):
        settings_override = override_settings(STORAGE_BACKEND='database')
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        super().setUp()


@skipIf(STORAGE_BACKEND_IS_JSON, 'STORAGE_BACKEND=json: no database configured')
class DatabaseTestCase(TransactionTestCase):
    """Empties the tables after each test and restarts ids at 1, like a fresh database."""

    reset_sequences = True


# SimpleTestCase fails any database query, which proves the JSON backend never touches the database.
class JsonReporterApiTests(JsonBackendMixin, ReporterApiTestsMixin, SimpleTestCase):
    pass


class JsonIssueApiTests(JsonBackendMixin, IssueApiTestsMixin, SimpleTestCase):
    def test_issues_are_saved_to_file(self):
        self.create_issue()
        saved = json.loads((self.data_dir / 'issues.json').read_text(encoding='utf-8'))
        self.assertEqual(saved[0]['title'], 'Login button not working on mobile')


class DatabaseReporterApiTests(DatabaseBackendMixin, ReporterApiTestsMixin, DatabaseTestCase):
    pass


class DatabaseIssueApiTests(DatabaseBackendMixin, IssueApiTestsMixin, DatabaseTestCase):
    def test_issues_are_saved_to_database(self):
        from issues.db_models import IssueModel

        self.create_issue()
        self.assertEqual(IssueModel.objects.get(pk=1).reporter.name, 'Asha Rao')
