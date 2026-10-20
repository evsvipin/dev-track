"""
Tests for the DevTrack API and OOP classes.

Run with:  python manage.py test

Each test points DATA_DIR at a fresh temporary folder, so the real
data/reporters.json and data/issues.json are never touched.
"""

import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from issues.models import BaseEntity, CriticalIssue, Issue, LowPriorityIssue, Reporter


class ModelTests(SimpleTestCase):
    def test_base_entity_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            BaseEntity()

    def test_reporter_validation(self):
        Reporter(1, 'Asha Rao', 'asha@example.com', 'backend').validate()
        with self.assertRaisesMessage(ValueError, 'Name cannot be empty'):
            Reporter(1, '', 'asha@example.com', 'backend').validate()
        with self.assertRaisesMessage(ValueError, 'Invalid email'):
            Reporter(1, 'Asha Rao', 'asha.example.com', 'backend').validate()

    def test_issue_validation(self):
        with self.assertRaisesMessage(ValueError, 'Title cannot be empty'):
            Issue(1, '', 'desc', 'open', 'high', 1).validate()
        with self.assertRaisesMessage(ValueError, 'Status must be one of'):
            Issue(1, 'Bug', 'desc', 'done', 'high', 1).validate()
        with self.assertRaisesMessage(ValueError, 'Priority must be one of'):
            Issue(1, 'Bug', 'desc', 'open', 'urgent', 1).validate()

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


class ApiTestCase(SimpleTestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.data_dir = Path(temp_dir.name)
        settings_override = override_settings(DATA_DIR=self.data_dir)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def post(self, url, body):
        return self.client.post(url, data=json.dumps(body), content_type='application/json')

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


class ReporterApiTests(ApiTestCase):
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

        saved = json.loads((self.data_dir / 'reporters.json').read_text(encoding='utf-8'))
        self.assertEqual(len(saved), 2)

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

    def test_duplicate_id_returns_409(self):
        self.create_reporter(id=5)
        response = self.create_reporter(id=5)
        self.assertEqual(response.status_code, 409)

    def test_non_integer_id_param_returns_400(self):
        response = self.client.get('/api/reporters/?id=abc')
        self.assertEqual(response.status_code, 400)


class IssueApiTests(ApiTestCase):
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

    def test_message_depends_on_priority(self):
        low = self.create_issue(title='Typo', priority='low').json()
        medium = self.create_issue(title='Slow page', priority='medium').json()
        self.assertEqual(low['message'], 'Typo — low priority, handle when free')
        self.assertEqual(medium['message'], 'Slow page [medium]')

    def test_message_is_not_saved_to_file(self):
        self.create_issue()
        saved = json.loads((self.data_dir / 'issues.json').read_text(encoding='utf-8'))
        self.assertNotIn('message', saved[0])

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
        self.assertEqual(len(response.json()), 2)

    def test_unsupported_method_returns_405(self):
        response = self.client.delete('/api/issues/')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response['Allow'], 'GET, POST')
