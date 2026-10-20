import json

from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view



# create your views here.

@api_view(['GET']) # Decorator to specify that this view only accepts GET requests
def add_numbers(request):
    """
    A view that adds two numbers and returns the result.
    """
    try:
        # Get the numbers from the request (for example, from query parameters)
        num1 = int(request.query_params["a"])
        num2 = int(request.query_params["b"])

        # Calculate the sum
        result = num1 + num2
    
        # Return the result as a JSON response
        return Response({"message" : "hello world",'sum': result})
    except (KeyError, ValueError):
        return Response({"error": "Invalid input. Please provide valid integers for both parameters."}, status=400)
    
TASK_FILE_PATH = "tasks/files/tasks.json"   
@api_view(['GET'])
def get_all_tasks(request):
    
    with open(TASK_FILE_PATH, 'r') as file:
        tasks = json.load(file)
    return Response(tasks)

@api_view(['GET'])
def get_task_by_id(request, task_id):
    
    with open(TASK_FILE_PATH, 'r') as file:
        tasks = json.load(file)
        
        for task in tasks:
            if task['id'] == task_id:
                return Response(task)
    
    return Response({"error": "Task not found."}, status=404)
    
    