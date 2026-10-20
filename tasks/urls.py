from django.urls import path
from .views import add_numbers, get_all_tasks, get_task_by_id


urlpatterns = [
    path("add-numbers/", add_numbers, name="add-numbers"),
    path("get-all-tasks/", get_all_tasks, name="get-all-tasks"),
    path("get-task-by-id/<int:task_id>/", get_task_by_id, name="get-task-by-id"),
]