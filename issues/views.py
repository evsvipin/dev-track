"""
Views for the DevTrack API.

Each URL has one view function that checks the HTTP method and hands off
to a helper:

    /api/reporters/   reporters()  ->  GET: get_reporters()   POST: create_reporter()
                                       PATCH: update_reporter()   DELETE: delete_reporter()
    /api/issues/      issues()     ->  GET: get_issues()      POST: create_issue()
                                       PATCH: update_issue()      DELETE: delete_issue()

PATCH and DELETE pick the record with ?id=<id>, the same way GET does.
Records are saved through get_storage() (JSON files or PostgreSQL, see
issues/storage.py). Every response is JSON. Errors look like {"error": "<message>"}.
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from issues.models import ISSUE_STATUSES, CriticalIssue, Issue, LowPriorityIssue, Reporter
from issues.storage import ISSUES, REPORTERS, get_storage

REPORTER_FIELDS = ('name', 'email', 'team')
ISSUE_FIELDS = ('title', 'description', 'status', 'priority', 'reporter_id')
ALLOWED_METHODS = ['GET', 'POST', 'PATCH', 'DELETE']


# ---------- helpers ----------

def error_response(message, status):
    return JsonResponse({'error': message}, status=status)


def method_not_allowed(request):
    response = error_response(f'Method {request.method} not allowed', 405)
    response['Allow'] = ', '.join(ALLOWED_METHODS)
    return response


def parse_json_body(request):
    """Return the request body as a dict, or raise ValueError."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError('Request body must be valid JSON')
    if not isinstance(data, dict):
        raise ValueError('Request body must be a JSON object')
    return data


def check_required_fields(data, fields):
    missing = [field for field in fields if field not in data]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")


def check_update_fields(data, fields):
    """A PATCH body may only contain fields that can be changed."""
    if not data:
        raise ValueError('No fields to update')
    not_allowed = [field for field in data if field not in fields]
    if not_allowed:
        raise ValueError(
            f"Cannot update field(s): {', '.join(not_allowed)}. "
            f"Allowed: {', '.join(fields)}"
        )


def parse_id_param(value):
    try:
        return int(value)
    except ValueError:
        raise ValueError('id must be an integer')


def get_required_id(request):
    """Read ?id= for PATCH and DELETE, where it is mandatory."""
    value = request.GET.get('id')
    if value is None:
        raise ValueError('id query parameter is required, e.g. ?id=1')
    return parse_id_param(value)


def build_issue(fields):
    """Create the Issue subclass that matches the priority."""
    if fields['priority'] == 'critical':
        return CriticalIssue(**fields)
    elif fields['priority'] == 'low':
        return LowPriorityIssue(**fields)
    else:
        return Issue(**fields)


def issue_response(issue, status):
    """The issue as JSON, plus describe() as "message"."""
    response_data = issue.to_dict()
    response_data['message'] = issue.describe()
    return JsonResponse(response_data, status=status)


# ---------- reporters ----------

@csrf_exempt
def reporters(request):
    if request.method == 'GET':
        return get_reporters(request)
    if request.method == 'POST':
        return create_reporter(request)
    if request.method == 'PATCH':
        return update_reporter(request)
    if request.method == 'DELETE':
        return delete_reporter(request)
    return method_not_allowed(request)


def get_reporters(request):
    """GET /api/reporters/ (all) or GET /api/reporters/?id=1 (one)."""
    storage = get_storage()

    reporter_id = request.GET.get('id')
    if reporter_id is None:
        return JsonResponse(storage.find_all(REPORTERS), safe=False, status=200)

    try:
        reporter_id = parse_id_param(reporter_id)
    except ValueError as e:
        return error_response(str(e), 400)

    reporter = storage.find_by_id(REPORTERS, reporter_id)
    if reporter is None:
        return error_response('Reporter not found', 404)
    return JsonResponse(reporter, status=200)


def create_reporter(request):
    """POST /api/reporters/ - validate the body with Reporter and save it."""
    try:
        data = parse_json_body(request)
        check_required_fields(data, REPORTER_FIELDS)
        reporter = Reporter(
            id=None,
            name=data['name'],
            email=data['email'],
            team=data['team'],
        )
        reporter.validate()
    except ValueError as e:
        return error_response(str(e), 400)

    saved = get_storage().create(REPORTERS, reporter.to_dict())
    reporter.id = saved['id']
    return JsonResponse(reporter.to_dict(), status=201)


def update_reporter(request):
    """PATCH /api/reporters/?id=1 - change some of name, email, team."""
    storage = get_storage()

    try:
        reporter_id = get_required_id(request)
    except ValueError as e:
        return error_response(str(e), 400)

    existing = storage.find_by_id(REPORTERS, reporter_id)
    if existing is None:
        return error_response('Reporter not found', 404)

    try:
        data = parse_json_body(request)
        check_update_fields(data, REPORTER_FIELDS)
        reporter = Reporter(**{**existing, **data})
        reporter.validate()
    except ValueError as e:
        return error_response(str(e), 400)

    saved = storage.update(REPORTERS, reporter_id, reporter.to_dict())
    return JsonResponse(saved, status=200)


def delete_reporter(request):
    """DELETE /api/reporters/?id=1 - only allowed when the reporter has no issues."""
    storage = get_storage()

    try:
        reporter_id = get_required_id(request)
    except ValueError as e:
        return error_response(str(e), 400)

    if storage.find_by_id(REPORTERS, reporter_id) is None:
        return error_response('Reporter not found', 404)

    issue_count = len(storage.find_all(ISSUES, reporter_id=reporter_id))
    if issue_count:
        return error_response(
            f'Reporter {reporter_id} has {issue_count} issue(s). '
            'Delete them or move them to another reporter first',
            409,
        )

    storage.delete(REPORTERS, reporter_id)
    return JsonResponse({'message': f'Reporter {reporter_id} deleted'}, status=200)


# ---------- issues ----------

@csrf_exempt
def issues(request):
    if request.method == 'GET':
        return get_issues(request)
    if request.method == 'POST':
        return create_issue(request)
    if request.method == 'PATCH':
        return update_issue(request)
    if request.method == 'DELETE':
        return delete_issue(request)
    return method_not_allowed(request)


def get_issues(request):
    """GET /api/issues/ (all), ?id=1 (one) or ?status=open (filtered)."""
    storage = get_storage()

    issue_id = request.GET.get('id')
    if issue_id is not None:
        try:
            issue_id = parse_id_param(issue_id)
        except ValueError as e:
            return error_response(str(e), 400)

        issue = storage.find_by_id(ISSUES, issue_id)
        if issue is None:
            return error_response('Issue not found', 404)
        return JsonResponse(issue, status=200)

    status = request.GET.get('status')
    if status is not None:
        if status not in ISSUE_STATUSES:
            return error_response(f"Status must be one of: {', '.join(ISSUE_STATUSES)}", 400)
        return JsonResponse(storage.find_all(ISSUES, status=status), safe=False, status=200)

    return JsonResponse(storage.find_all(ISSUES), safe=False, status=200)


def create_issue(request):
    """
    POST /api/issues/ - build the right Issue subclass for the priority,
    validate it, save it, and return it with describe() as "message".
    """
    storage = get_storage()

    try:
        data = parse_json_body(request)
        check_required_fields(data, ISSUE_FIELDS)

        fields = {
            'id': None,
            'title': data['title'],
            'description': data['description'],
            'status': data['status'],
            'priority': data['priority'],
            'reporter_id': data['reporter_id'],
        }
        if data['priority'] == 'critical':
            issue = CriticalIssue(**fields)
        elif data['priority'] == 'low':
            issue = LowPriorityIssue(**fields)
        else:
            issue = Issue(**fields)

        issue.validate()
    except ValueError as e:
        return error_response(str(e), 400)

    if storage.find_by_id(REPORTERS, issue.reporter_id) is None:
        return error_response(f'Reporter with id {issue.reporter_id} does not exist', 400)

    saved = storage.create(ISSUES, issue.to_dict())
    issue.id = saved['id']
    issue.created_at = saved['created_at']
    return issue_response(issue, 201)


def update_issue(request):
    """
    PATCH /api/issues/?id=1 - change some of title, description, status,
    priority, reporter_id. A new priority also changes the Issue subclass,
    so the returned message matches it.
    """
    storage = get_storage()

    try:
        issue_id = get_required_id(request)
    except ValueError as e:
        return error_response(str(e), 400)

    existing = storage.find_by_id(ISSUES, issue_id)
    if existing is None:
        return error_response('Issue not found', 404)

    try:
        data = parse_json_body(request)
        check_update_fields(data, ISSUE_FIELDS)
        issue = build_issue({**existing, **data})
        issue.validate()
    except ValueError as e:
        return error_response(str(e), 400)

    if 'reporter_id' in data and storage.find_by_id(REPORTERS, issue.reporter_id) is None:
        return error_response(f'Reporter with id {issue.reporter_id} does not exist', 400)

    saved = storage.update(ISSUES, issue_id, issue.to_dict())
    return issue_response(build_issue(saved), 200)


def delete_issue(request):
    """DELETE /api/issues/?id=1"""
    storage = get_storage()

    try:
        issue_id = get_required_id(request)
    except ValueError as e:
        return error_response(str(e), 400)

    if not storage.delete(ISSUES, issue_id):
        return error_response('Issue not found', 404)
    return JsonResponse({'message': f'Issue {issue_id} deleted'}, status=200)
