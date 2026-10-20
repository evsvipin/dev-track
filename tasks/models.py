from django.db import models


# Models are used to define the structure of the database tables and the relationships between them. Each model corresponds to a single table in the database, and each attribute of the model corresponds to a column in that table.

# In generalise backend development, models are used to represent the data that the application will be working with. They provide a way to define the fields and behaviors of the data, as well as the relationships between different pieces of data.

# However in Django, models are used to define the structure of the database tables and the relationships between them. Each model corresponds to a single table in the database, and each attribute of the model corresponds to a column in that table.

# Create your models here.

class Task(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    

    def __str__(self):
        return self.title