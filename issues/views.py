"""
Views for the DevTrack API.

Each URL has one view function that checks the HTTP method and hands off
to a helper:

    /api/reporters/   reporters()  ->  GET: get_reporters()  POST: create_reporter()
    /api/issues/      issues()     ->  GET: get_issues()     POST: create_issue()

Every response is JSON. Errors look like {"error": "<message>"}.
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from issues import storage
from issues.models import ISSUE_STATUSES, CriticalIssue, Issue, LowPriorityIssue, Reporter

REPORTER_FIELDS = ('name', 'email', 'team')
ISSUE_FIELDS = ('title', 'description', 'status', 'priority', 'reporter_id')


# ---------- helpers ----------

def error_response(message, status):
    return JsonResponse({'error': message}, status=status)


def method_not_allowed(request, allowed):
    response = error_response(f'Method {request.method} not allowed', 405)
    response['Allow'] = ', '.join(allowed)
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


def parse_id_param(value):
    try:
        return int(value)
    except ValueError:
        raise ValueError('id must be an integer')


# ---------- reporters ----------

@csrf_exempt
def reporters(request):
    if request.method == 'GET':
        return get_reporters(request)
    if request.method == 'POST':
        return create_reporter(request)
    return method_not_allowed(request, ['GET', 'POST'])


def get_reporters(request):
    """GET /api/reporters/ (all) or GET /api/reporters/?id=1 (one)."""
    all_reporters = storage.read_records(storage.REPORTERS_FILE)

    reporter_id = request.GET.get('id')
    if reporter_id is None:
        return JsonResponse(all_reporters, safe=False, status=200)

    try:
        reporter_id = parse_id_param(reporter_id)
    except ValueError as e:
        return error_response(str(e), 400)

    reporter = storage.find_by_id(all_reporters, reporter_id)
    if reporter is None:
        return error_response('Reporter not found', 404)
    return JsonResponse(reporter, status=200)


def create_reporter(request):
    """POST /api/reporters/ - validate the body with Reporter and save it."""
    all_reporters = storage.read_records(storage.REPORTERS_FILE)

    try:
        data = parse_json_body(request)
        check_required_fields(data, REPORTER_FIELDS)
        reporter = Reporter(
            id=data.get('id', storage.next_id(all_reporters)),
            name=data['name'],
            email=data['email'],
            team=data['team'],
        )
        reporter.validate()
    except ValueError as e:
        return error_response(str(e), 400)

    if storage.find_by_id(all_reporters, reporter.id) is not None:
        return error_response(f'Reporter with id {reporter.id} already exists', 409)

    all_reporters.append(reporter.to_dict())
    storage.write_records(storage.REPORTERS_FILE, all_reporters)
    return JsonResponse(reporter.to_dict(), status=201)


# ---------- issues ----------

@csrf_exempt
def issues(request):
    if request.method == 'GET':
        return get_issues(request)
    if request.method == 'POST':
        return create_issue(request)
    return method_not_allowed(request, ['GET', 'POST'])


def get_issues(request):
    """GET /api/issues/ (all), ?id=1 (one) or ?status=open (filtered)."""
    all_issues = storage.read_records(storage.ISSUES_FILE)

    issue_id = request.GET.get('id')
    if issue_id is not None:
        try:
            issue_id = parse_id_param(issue_id)
        except ValueError as e:
            return error_response(str(e), 400)

        issue = storage.find_by_id(all_issues, issue_id)
        if issue is None:
            return error_response('Issue not found', 404)
        return JsonResponse(issue, status=200)

    status = request.GET.get('status')
    if status is not None:
        if status not in ISSUE_STATUSES:
            return error_response(f"Status must be one of: {', '.join(ISSUE_STATUSES)}", 400)
        matching = [issue for issue in all_issues if issue['status'] == status]
        return JsonResponse(matching, safe=False, status=200)

    return JsonResponse(all_issues, safe=False, status=200)


def create_issue(request):
    """
    POST /api/issues/ - build the right Issue subclass for the priority,
    validate it, save it, and return it with describe() as "message".
    """
    all_issues = storage.read_records(storage.ISSUES_FILE)

    try:
        data = parse_json_body(request)
        check_required_fields(data, ISSUE_FIELDS)

        fields = {
            'id': data.get('id', storage.next_id(all_issues)),
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

    all_reporters = storage.read_records(storage.REPORTERS_FILE)
    if storage.find_by_id(all_reporters, issue.reporter_id) is None:
        return error_response(f'Reporter with id {issue.reporter_id} does not exist', 400)

    if storage.find_by_id(all_issues, issue.id) is not None:
        return error_response(f'Issue with id {issue.id} already exists', 409)

    all_issues.append(issue.to_dict())
    storage.write_records(storage.ISSUES_FILE, all_issues)

    response_data = issue.to_dict()
    response_data['message'] = issue.describe()
    return JsonResponse(response_data, status=201)
