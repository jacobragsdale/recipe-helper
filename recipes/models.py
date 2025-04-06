from django.db import models
from django.contrib.auth.models import User

class Recipe(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    ingredients = models.TextField(help_text="Enter ingredients, one per line")
    instructions = models.TextField()
    prep_time = models.IntegerField(help_text="Preparation time in minutes")
    cook_time = models.IntegerField(help_text="Cooking time in minutes")
    servings = models.IntegerField(default=4)
    image_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='recipe_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recipes')
    is_ai_generated = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class MealPlan(models.Model):
    DAY_CHOICES = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
        ('SAT', 'Saturday'),
        ('SUN', 'Sunday'),
    ]
    MEAL_CHOICES = [
        ('BREAKFAST', 'Breakfast'),
        ('LUNCH', 'Lunch'),
        ('DINNER', 'Dinner'),
        ('SNACK', 'Snack'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meal_plans')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    meal_type = models.CharField(max_length=10, choices=MEAL_CHOICES)
    date = models.DateField()
    
    class Meta:
        unique_together = ('user', 'day', 'meal_type', 'date')
    
    def __str__(self):
        return f"{self.get_day_display()} {self.get_meal_type_display()}: {self.recipe.title}"

class GroceryItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='grocery_items')
    name = models.CharField(max_length=200)
    quantity = models.CharField(max_length=100)
    is_purchased = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} ({self.quantity})"

class GroceryList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='grocery_lists')
    name = models.CharField(max_length=200, default="Weekly Grocery List")
    created_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField()
    end_date = models.DateField()
    items = models.ManyToManyField(GroceryItem)
    
    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"
