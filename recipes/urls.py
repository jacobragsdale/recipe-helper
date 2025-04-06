from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('recipes/', views.recipe_list, name='recipe_list'),
    path('recipes/<int:recipe_id>/', views.recipe_detail, name='recipe_detail'),
    path('recipes/create/', views.recipe_create, name='recipe_create'),
    path('recipes/<int:recipe_id>/delete/', views.recipe_delete, name='recipe_delete'),
    path('generate-recipe/', views.ai_recipe_generator, name='ai_recipe_generator'),
    path('meal-plan/', views.meal_plan, name='meal_plan'),
    path('meal-plan/add/', views.add_to_meal_plan, name='add_to_meal_plan'),
    path('meal-plan/<int:meal_plan_id>/remove/', views.remove_from_meal_plan, name='remove_from_meal_plan'),
    path('grocery-list/generate/', views.generate_grocery_list, name='generate_grocery_list'),
    path('grocery-list/<int:list_id>/', views.grocery_list_detail, name='grocery_list_detail'),
    path('grocery-item/<int:item_id>/toggle/', views.toggle_grocery_item, name='toggle_grocery_item'),
] 