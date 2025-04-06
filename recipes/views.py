from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import json
import openai
import requests
import os
from django.core.files.base import ContentFile
from django.core.files.temp import NamedTemporaryFile
from .models import Recipe, MealPlan, GroceryItem, GroceryList
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse

def home(request):
    recent_recipes = Recipe.objects.order_by('-created_at')[:6]
    return render(request, 'recipes/home.html', {'recent_recipes': recent_recipes})

@login_required
def recipe_list(request):
    recipes = Recipe.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'recipes/recipe_list.html', {'recipes': recipes})

@login_required
def recipe_detail(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    
    # If this is a POST request and user is the recipe creator, process the submitted data
    if request.method == 'POST' and request.user == recipe.created_by:
        recipe.title = request.POST.get('title')
        recipe.description = request.POST.get('description')
        recipe.ingredients = request.POST.get('ingredients')
        recipe.instructions = request.POST.get('instructions')
        recipe.prep_time = request.POST.get('prep_time')
        recipe.cook_time = request.POST.get('cook_time')
        recipe.servings = request.POST.get('servings')
        recipe.image_url = request.POST.get('image_url')
        recipe.save()
        
        messages.success(request, f'Recipe "{recipe.title}" updated successfully!')
        return redirect('recipe_detail', recipe_id=recipe.id)
    
    return render(request, 'recipes/recipe_detail.html', {'recipe': recipe})

@login_required
def recipe_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        ingredients = request.POST.get('ingredients')
        instructions = request.POST.get('instructions')
        prep_time = request.POST.get('prep_time')
        cook_time = request.POST.get('cook_time')
        servings = request.POST.get('servings')
        image_url = request.POST.get('image_url')
        
        recipe = Recipe.objects.create(
            title=title,
            description=description,
            ingredients=ingredients,
            instructions=instructions,
            prep_time=prep_time,
            cook_time=cook_time,
            servings=servings,
            image_url=image_url,
            created_by=request.user
        )
        messages.success(request, f'Recipe "{title}" created successfully!')
        return redirect('recipe_detail', recipe_id=recipe.id)
    
    return render(request, 'recipes/recipe_form.html')

@login_required
def recipe_delete(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id, created_by=request.user)
    
    if request.method == 'POST':
        recipe_title = recipe.title
        recipe.delete()
        messages.success(request, f'Recipe "{recipe_title}" has been deleted.')
        return redirect('recipe_list')
    
    return render(request, 'recipes/recipe_confirm_delete.html', {'recipe': recipe})

@login_required
def ai_recipe_generator(request):
    recipe = None # Initialize recipe as None
    recipe_id = request.GET.get('recipe_id')
    
    # If there is a recipe_id in the URL, try to get the recipe
    if recipe_id:
        try:
            recipe = Recipe.objects.get(id=recipe_id, created_by=request.user)
        except Recipe.DoesNotExist:
            messages.error(request, "The requested recipe could not be found.")

    if request.method == 'POST':
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Get POST parameters to determine request type
        tweak_prompt = request.POST.get('tweak_prompt')
        recipe_id = request.POST.get('recipe_id')
        edit_recipe_id = request.POST.get('edit_recipe_id')
        edit_type = request.POST.get('edit_type')

        # --- Handle Manual Edit --- 
        if edit_recipe_id and edit_type == 'manual':
            try:
                recipe = get_object_or_404(Recipe, id=edit_recipe_id, created_by=request.user)
                
                # Update the recipe with the manually entered values
                recipe.title = request.POST.get('edit_title')
                recipe.description = request.POST.get('edit_description')
                recipe.ingredients = request.POST.get('edit_ingredients')
                recipe.instructions = request.POST.get('edit_instructions')
                
                # Handle numeric fields safely
                try:
                    recipe.prep_time = int(request.POST.get('edit_prep_time', 0))
                    recipe.cook_time = int(request.POST.get('edit_cook_time', 0))
                    recipe.servings = int(request.POST.get('edit_servings', 1))
                except ValueError:
                    messages.warning(request, 'Some numeric fields had invalid values and were set to defaults.')
                    recipe.prep_time = recipe.prep_time or 0
                    recipe.cook_time = recipe.cook_time or 0
                    recipe.servings = recipe.servings or 1
                
                recipe.save()
                
                # Redirect to avoid resubmission
                return redirect(f'{reverse("ai_recipe_generator")}?recipe_id={recipe.id}')
                
            except Recipe.DoesNotExist:
                messages.error(request, "The recipe you tried to edit could not be found.")
                return redirect(reverse("ai_recipe_generator"))
            except Exception as e:
                messages.error(request, f'An unexpected error occurred during manual edit: {str(e)}')
                print(f"Unexpected error during manual edit: {e}")
                if recipe:
                    # Redirect with recipe ID if we have one
                    return redirect(f'{reverse("ai_recipe_generator")}?recipe_id={recipe.id}')
                return redirect(reverse("ai_recipe_generator"))

        # --- Tweak Existing Recipe --- 
        elif tweak_prompt and recipe_id:
            try:
                recipe = get_object_or_404(Recipe, id=recipe_id, created_by=request.user)
                
                # Construct prompt for tweaking
                tweak_context = (
                    f"Current Recipe:\n"
                    f"Title: {recipe.title}\n"
                    f"Description: {recipe.description}\n"
                    f"Ingredients:\n{recipe.ingredients}\n"
                    f"Instructions:\n{recipe.instructions}\n"
                    f"Prep Time: {recipe.prep_time} min, Cook Time: {recipe.cook_time} min, Servings: {recipe.servings}\n\n"
                    f"User request: Modify the above recipe as follows: {tweak_prompt}\n\n"
                    "Output the *entire modified* recipe details ONLY as a valid JSON object with the exact same structure as the initial generation request: "
                    '{"title": "...", "description": "...", "ingredients": [...], "instructions": [...], "prep_time": 30, "cook_time": 45, "servings": 4}'
                    "\n\nIMPORTANT: prep_time, cook_time, and servings MUST be integers, not strings."
                )

                # Call OpenAI for tweaked text
                response = client.chat.completions.create(
                    model="gpt-4o-mini", 
                    messages=[
                        {"role": "system", "content": "You are a helpful recipe assistant that modifies existing recipes based on user requests and outputs complete, updated recipe details as JSON. Ensure prep_time, cook_time, and servings are integers."},
                        {"role": "user", "content": tweak_context}
                    ],
                    temperature=0.5,
                    response_format={ "type": "json_object" }
                )
                response_content = response.choices[0].message.content

                try:
                    recipe_data = json.loads(response_content)
                    # Basic validation
                    required_keys = ['title', 'description', 'ingredients', 'instructions', 'prep_time', 'cook_time', 'servings']
                    if not all(key in recipe_data for key in required_keys):
                        raise ValidationError("AI tweak response missing required fields.")
                    
                    # Convert numeric fields from strings to integers if needed
                    numeric_fields = ['prep_time', 'cook_time', 'servings']
                    for field in numeric_fields:
                        # If it's already an int, keep as is
                        if isinstance(recipe_data[field], int):
                            continue
                        # If it's a string, try to convert to int
                        elif isinstance(recipe_data[field], str):
                            try:
                                recipe_data[field] = int(recipe_data[field])
                            except ValueError:
                                raise ValidationError(f"'{field}' value '{recipe_data[field]}' cannot be converted to an integer")
                        else:
                            raise ValidationError(f"'{field}' must be an integer or convertible string")
                    
                    # Validate list types
                    if not isinstance(recipe_data['ingredients'], list) or not isinstance(recipe_data['instructions'], list):
                        raise ValidationError("Ingredients/Instructions should be lists.")
                    
                    # Update the *existing* recipe object
                    recipe.title = recipe_data['title']
                    recipe.description = recipe_data['description']
                    recipe.ingredients = "\n".join(recipe_data['ingredients'])
                    recipe.instructions = "\n".join([f"{i+1}. {step}" for i, step in enumerate(recipe_data['instructions'])])
                    recipe.prep_time = recipe_data['prep_time']
                    recipe.cook_time = recipe_data['cook_time']
                    recipe.servings = recipe_data['servings']
                    recipe.save() 
                    
                    # --- Generate enhanced image for tweaked recipe --- 
                    try:
                        # Create an enhanced image prompt using GPT-4o-mini
                        image_prompt = create_enhanced_image_prompt(
                            client, 
                            recipe, 
                            context=tweak_prompt  # Pass the tweak prompt as additional context
                        )
                        
                        # Generate the image using the enhanced prompt
                        image_response = client.images.generate(
                            model="dall-e-3", 
                            prompt=image_prompt,
                            n=1,
                            size="1024x1024", # DALL-E 3's minimum size
                            quality="standard", # Use standard quality instead of HD to reduce costs
                            response_format="url"
                        )
                        image_url = image_response.data[0].url
                        
                        # Store the URL temporarily 
                        recipe.image_url = image_url
                        
                        # Download and save the image locally
                        if save_image_from_url(recipe, image_url):
                            messages.info(request, 'Delicious Studio Ghibli style image created for your recipe.')
                        else:
                            messages.warning(request, 'Recipe updated, but failed to save the image locally.')
                    except Exception as img_e:
                        messages.warning(request, f'Recipe updated, but failed to generate a new image: {str(img_e)}')
                        print(f"Failed to regenerate image for tweaked recipe {recipe.id}: {img_e}")
                    
                    # Make sure the recipe is saved with final updates
                    recipe.save()

                    # Redirect to avoid resubmission
                    return redirect(f'{reverse("ai_recipe_generator")}?recipe_id={recipe.id}')

                except (json.JSONDecodeError, ValidationError) as e:
                    messages.error(request, f"Error processing AI tweak response: {e}. Please try again.")
                    print(f"Invalid JSON or validation for tweak: {response_content}")
                    # Redirect back with the recipe ID
                    return redirect(f'{reverse("ai_recipe_generator")}?recipe_id={recipe.id}')
                
            except Recipe.DoesNotExist:
                 messages.error(request, "The recipe you tried to tweak could not be found.")
                 # No recipe to show, redirect to the initial form state
                 return redirect(reverse("ai_recipe_generator"))
            except openai.APIError as e:
                 messages.error(request, f'OpenAI API Error during tweak: {str(e)}')
                 if recipe:
                     return redirect(f'{reverse("ai_recipe_generator")}?recipe_id={recipe.id}')
                 return redirect(reverse("ai_recipe_generator"))
            except Exception as e:
                messages.error(request, f'An unexpected error occurred during tweak: {str(e)}')
                print(f"Unexpected error during tweak: {e}")
                # Redirect with recipe ID if available
                if recipe:
                    return redirect(f'{reverse("ai_recipe_generator")}?recipe_id={recipe.id}')
                return redirect(reverse("ai_recipe_generator"))

        # --- Generate New Recipe --- 
        else:
            user_prompt = request.POST.get('prompt', '')
            restrictions = request.POST.get('restrictions', '')
            
            # Construct prompt for initial generation
            prompt_parts = [
                f"Generate a detailed recipe based on the user request: '{user_prompt}'."
            ]
            if restrictions:
                prompt_parts.append(f"Dietary Restrictions/Exclusions: {restrictions}.")
            prompt_parts.append(
                "Provide the response ONLY as a valid JSON object with the following structure: "
                '{"title": "...", "description": "...", "ingredients": [...], "instructions": [...], "prep_time": ..., "cook_time": ..., "servings": ...}'
                "Ensure keys and string values use double quotes. prep_time, cook_time, servings should be integers."
            )
            generation_prompt = "\n".join(prompt_parts)

            try:
                # Call OpenAI for text
                response = client.chat.completions.create(
                    model="gpt-4o-mini", 
                    messages=[
                        {"role": "system", "content": "You are a helpful recipe assistant designed to output JSON."},
                        {"role": "user", "content": generation_prompt}
                    ],
                    temperature=0.5,
                    response_format={ "type": "json_object" }
                )
                response_content = response.choices[0].message.content

                try:
                    recipe_data = json.loads(response_content)
                    # Validation
                    required_keys = ['title', 'description', 'ingredients', 'instructions', 'prep_time', 'cook_time', 'servings']
                    if not all(key in recipe_data for key in required_keys):
                         raise ValidationError("AI response missing required fields.")
                    
                    # Convert numeric fields from strings to integers if needed
                    numeric_fields = ['prep_time', 'cook_time', 'servings']
                    for field in numeric_fields:
                        # If it's already an int, keep as is
                        if isinstance(recipe_data[field], int):
                            continue
                        # If it's a string, try to convert to int
                        elif isinstance(recipe_data[field], str):
                            try:
                                recipe_data[field] = int(recipe_data[field])
                            except ValueError:
                                raise ValidationError(f"'{field}' value '{recipe_data[field]}' cannot be converted to an integer")
                        else:
                            raise ValidationError(f"'{field}' must be an integer or convertible string")
                    
                    # Validate list types
                    if not isinstance(recipe_data['ingredients'], list) or not isinstance(recipe_data['instructions'], list):
                         raise ValidationError("Ingredients/Instructions should be lists.")

                    # Create the new recipe object (without image first)
                    recipe = Recipe.objects.create(
                        title=recipe_data['title'],
                        description=recipe_data['description'],
                        ingredients="\n".join(recipe_data['ingredients']),
                        instructions="\n".join([f"{i+1}. {step}" for i, step in enumerate(recipe_data['instructions'])]) ,
                        prep_time=recipe_data['prep_time'],
                        cook_time=recipe_data['cook_time'],
                        servings=recipe_data['servings'],
                        created_by=request.user,
                        is_ai_generated=True
                    )

                    # --- Generate enhanced image for new recipe --- 
                    try:
                        # Create an enhanced image prompt using GPT-4o-mini
                        image_prompt = create_enhanced_image_prompt(
                            client, 
                            recipe, 
                            context=f"{user_prompt} {restrictions}" # Use original input as context
                        )
                        
                        # Generate the image using the enhanced prompt
                        image_response = client.images.generate(
                            model="dall-e-3", 
                            prompt=image_prompt,
                            n=1,
                            size="1024x1024", # DALL-E 3's minimum size
                            quality="standard", # Use standard quality instead of HD to reduce costs
                            response_format="url"
                        )
                        image_url = image_response.data[0].url
                        
                        # Store the URL temporarily
                        recipe.image_url = image_url
                        
                        # Download and save the image locally
                        if save_image_from_url(recipe, image_url):
                            messages.info(request, 'Delicious Studio Ghibli style image created for your recipe.')
                        else:
                            messages.warning(request, 'Recipe created, but failed to save the image locally.')
                        
                        # Make sure the recipe is saved with both the URL and local image
                        recipe.save()
                    except Exception as img_e:
                        messages.warning(request, f'Recipe text saved, but failed to generate image: {str(img_e)}')
                        print(f"DALL-E Error for recipe {recipe.id}: {img_e}")
                    
                    # Redirect to avoid resubmission
                    return redirect(f'{reverse("ai_recipe_generator")}?recipe_id={recipe.id}')
                
                except (json.JSONDecodeError, ValidationError) as e:
                    messages.error(request, f"Error processing AI response: {e}. Please try again.")
                    print(f"Invalid JSON or validation for generation: {response_content}")
                    # Redirect to the form without a recipe
                    return redirect(reverse("ai_recipe_generator"))

            except openai.APIError as e:
                 messages.error(request, f'OpenAI API Error during generation: {str(e)}')
                 return redirect(reverse("ai_recipe_generator"))
            except Exception as e:
                messages.error(request, f'An unexpected error occurred during generation: {str(e)}')
                print(f"Unexpected error during generation: {e}")
                return redirect(reverse("ai_recipe_generator"))

    # --- Render the page --- 
    # GET request OR after POST processing
    return render(request, 'recipes/ai_recipe_generator.html', {'recipe': recipe})

@login_required
def meal_plan(request):
    # Get current week's start and end dates
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    # Get meal plans for the current week
    meal_plans = MealPlan.objects.filter(
        user=request.user,
        date__range=[start_of_week, end_of_week]
    ).order_by('date', 'meal_type')
    
    # Organize meal plans by day
    meal_plan_by_day = {}
    for day_code, day_name in MealPlan.DAY_CHOICES:
        day_date = start_of_week + timedelta(days=MealPlan.DAY_CHOICES.index((day_code, day_name)))
        day_plans = [plan for plan in meal_plans if plan.date == day_date]
        meal_plan_by_day[day_code] = {
            'date': day_date,
            'name': day_name,
            'meals': {meal_type: next((plan for plan in day_plans if plan.meal_type == meal_type), None) 
                    for meal_type, _ in MealPlan.MEAL_CHOICES}
        }
    
    # Get user's recipes for selection
    user_recipes = Recipe.objects.filter(created_by=request.user).order_by('-created_at')
    
    return render(request, 'recipes/meal_plan.html', {
        'meal_plan_by_day': meal_plan_by_day,
        'recipes': user_recipes,
        'start_date': start_of_week,
        'end_date': end_of_week,
    })

@login_required
@require_POST
def add_to_meal_plan(request):
    recipe_id = request.POST.get('recipe_id')
    day = request.POST.get('day')
    meal_type = request.POST.get('meal_type')
    date_str = request.POST.get('date')
    
    recipe = get_object_or_404(Recipe, id=recipe_id)
    
    # Create or update meal plan
    meal_plan, created = MealPlan.objects.update_or_create(
        user=request.user,
        day=day,
        meal_type=meal_type,
        date=date_str,
        defaults={'recipe': recipe}
    )
    
    messages.success(request, f'Added {recipe.title} to your meal plan for {meal_plan.get_day_display()} {meal_plan.get_meal_type_display()}')
    return redirect('meal_plan')

@login_required
def remove_from_meal_plan(request, meal_plan_id):
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=request.user)
    day = meal_plan.get_day_display()
    meal_type = meal_plan.get_meal_type_display()
    meal_plan.delete()
    
    messages.success(request, f'Removed recipe from your {day} {meal_type} meal plan')
    return redirect('meal_plan')

@login_required
def generate_grocery_list(request):
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Get meal plans for the selected date range
        meal_plans = MealPlan.objects.filter(
            user=request.user,
            date__range=[start_date, end_date]
        ).select_related('recipe') # Optimize query by fetching related recipes
        
        if not meal_plans:
            messages.warning(request, 'No meal plans found for the selected date range.')
            # Redirect back to form or meal plan? Redirecting to form for now.
            # To redirect to the form, we need the default date range again
            today = timezone.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return render(request, 'recipes/generate_grocery_list.html', {
                'start_date': start_of_week,
                'end_date': end_of_week,
            })

        # --- Extract Raw Ingredients --- 
        all_ingredients_raw = []
        for plan in meal_plans:
            if plan.recipe and plan.recipe.ingredients:
                recipe_ingredients = plan.recipe.ingredients.strip().split('\n')
                all_ingredients_raw.extend(filter(None, recipe_ingredients))
        
        if not all_ingredients_raw:
             messages.warning(request, 'No ingredients listed in the recipes for the selected meal plans.')
             today = timezone.now().date()
             start_of_week = today - timedelta(days=today.weekday())
             end_of_week = start_of_week + timedelta(days=6)
             return render(request, 'recipes/generate_grocery_list.html', {
                 'start_date': start_of_week,
                 'end_date': end_of_week,
             })

        # --- Call OpenAI to process the ingredient list --- 
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            
            prompt_ingredients = "\n".join(all_ingredients_raw)
            # --- Updated Prompt --- 
            prompt = (
                f"Here is a raw list of ingredients from multiple recipes:\n--- START LIST ---\n{prompt_ingredients}\n--- END LIST ---\n\n" 
                "Please process this list:\n" 
                "1. Identify the core ingredient name for each item (ignore quantities, units, and preparation instructions like 'chopped').\n" 
                "2. Combine duplicate ingredient names into a single entry.\n" 
                "3. Standardize capitalization (e.g., 'Onion', 'onion' -> 'Onion').\n" 
                "4. Ignore any non-ingredient lines.\n" 
                "Return ONLY a valid JSON object with a single key 'items'. The value of 'items' must be a list of unique, standardized ingredient name strings.\n" 
                "Example format: {\"items\": [\"Flour\", \"Sugar\", \"Eggs\", \"Onion\"]}"
            )
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an assistant that extracts unique ingredient names from lists and outputs structured JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1, # Very low temperature for consistency
                response_format={ "type": "json_object" }
            )
            
            response_content = response.choices[0].message.content
            
            # Create grocery list object
            grocery_list = GroceryList.objects.create(
                user=request.user,
                start_date=start_date,
                end_date=end_date
            )

            try:
                processed_data = json.loads(response_content)
                
                # --- Updated Validation --- 
                if not isinstance(processed_data, dict) or 'items' not in processed_data:
                    raise ValidationError("AI response missing 'items' key.")
                
                processed_items_list = processed_data['items']
                if not isinstance(processed_items_list, list):
                     raise ValidationError("Value for 'items' key is not a list.")

                grocery_items_to_create = []
                seen_items = set() # Keep track to ensure uniqueness if AI fails
                for item_name in processed_items_list:
                    if not isinstance(item_name, str) or not item_name.strip():
                        print(f"Skipping invalid grocery item data: {item_name}") 
                        continue 
                    
                    cleaned_name = item_name.strip().capitalize() # Basic cleaning/standardization
                    
                    if cleaned_name not in seen_items:
                        grocery_items_to_create.append(
                            # Store name, quantity is now empty/placeholder
                            GroceryItem(user=request.user, name=cleaned_name, quantity='') 
                        )
                        seen_items.add(cleaned_name)
                
                if not grocery_items_to_create:
                    # AI might return empty list if it couldn't parse anything
                    grocery_list.delete() # Clean up empty list
                    messages.warning(request, "Could not extract any valid ingredients from the recipes.")
                    # Render form again
                    today = timezone.now().date()
                    start_of_week = today - timedelta(days=today.weekday())
                    end_of_week = start_of_week + timedelta(days=6)
                    return render(request, 'recipes/generate_grocery_list.html', {
                        'start_date': start_of_week,
                        'end_date': end_of_week,
                    })

                # Bulk create grocery items
                created_items = GroceryItem.objects.bulk_create(grocery_items_to_create)
                
                # Add created items to the grocery list
                grocery_list.items.set(created_items)
                
                messages.success(request, 'Grocery list generated successfully!')
                return redirect('grocery_list_detail', list_id=grocery_list.id)

            except (json.JSONDecodeError, ValidationError) as e:
                grocery_list.delete() # Clean up list if processing failed
                messages.error(request, f'Error processing ingredients from AI: {e}. Please try again.')
                print(f"Invalid JSON or validation failed for grocery list: {response_content}")
                # Render form again
                today = timezone.now().date()
                start_of_week = today - timedelta(days=today.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                return render(request, 'recipes/generate_grocery_list.html', {
                    'start_date': start_of_week,
                    'end_date': end_of_week,
                })
                
        except openai.APIError as e:
            messages.error(request, f'OpenAI API Error generating grocery list: {str(e)}')
        except Exception as e:
            messages.error(request, f'An unexpected error occurred generating the grocery list: {str(e)}')
            print(f"Unexpected error in generate_grocery_list: {e}") # Log error

    # --- Handle GET request --- 
    # Get default date range for the form (current week)
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    return render(request, 'recipes/generate_grocery_list.html', {
        'start_date': start_of_week,
        'end_date': end_of_week,
    })

@login_required
def grocery_list_detail(request, list_id):
    grocery_list = get_object_or_404(GroceryList, id=list_id, user=request.user)
    return render(request, 'recipes/grocery_list_detail.html', {'grocery_list': grocery_list})

@login_required
@require_POST
def toggle_grocery_item(request, item_id):
    item = get_object_or_404(GroceryItem, id=item_id, user=request.user)
    item.is_purchased = not item.is_purchased
    item.save()
    
    return JsonResponse({'success': True, 'is_purchased': item.is_purchased})

# Helper function to download and save an image from a URL
def save_image_from_url(recipe, image_url):
    if not image_url:
        return False
    
    try:
        # Request the image
        response = requests.get(image_url, stream=True)
        
        # Check if the request was successful
        if response.status_code != 200:
            print(f"Failed to download image: HTTP {response.status_code}")
            return False
        
        # Generate a filename based on the recipe title
        file_name = f"{recipe.id}_{recipe.title.replace(' ', '_').lower()}.jpg"
        
        # Save the image to the recipe's ImageField
        recipe.image.save(file_name, ContentFile(response.content), save=True)
        
        # Return success
        return True
    
    except Exception as e:
        print(f"Error saving image: {str(e)}")
        return False

# Helper function to create enhanced DALL-E prompts using GPT-4o-mini
def create_enhanced_image_prompt(client, recipe, context=""):
    """
    Creates a detailed, enhanced prompt for DALL-E image generation
    using GPT-4o-mini based on recipe information
    
    Args:
        client: OpenAI client
        recipe: Recipe object with title, description, ingredients
        context: Optional additional context about the recipe
        
    Returns:
        A string containing the enhanced prompt for DALL-E
    """
    try:
        # Extract recipe details for the prompt
        ingredients_list = recipe.ingredients.split('\n')
        ingredients_text = ', '.join(ingredients_list[:5] if len(ingredients_list) > 5 else ingredients_list)
        
        prompt_request = (
            "Create a detailed image prompt for DALL-E to generate a high-quality Studio Ghibli style image of this dish:\n"
            f"Title: {recipe.title}\n"
            f"Description: {recipe.description}\n"
            f"Main ingredients: {ingredients_text}\n"
            f"Additional context: {context}\n\n"
            "Your prompt should:\n"
            "1. Describe the dish in vivid detail including colors, textures, and presentation\n"
            "2. Ensure the ENTIRE dish is clearly visible as the main focus\n"
            "3. Explictly ask it to strictly adhere to a Studio Ghibli style"
            "4. Suggest a rustic kitchen or dining table setting with natural light\n"
            "6. NOT include any text instructions like 'ensure' or 'make sure' - just the description\n\n"
            "Return ONLY the prompt text, nothing else."
        )
        
        # Get the prompt from GPT-4o-mini
        prompt_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You create detailed, vivid image prompts for food photography in Studio Ghibli style."},
                {"role": "user", "content": prompt_request}
            ],
            temperature=0.7,
            max_tokens=250
        )
        
        # Extract the generated prompt
        enhanced_prompt = prompt_response.choices[0].message.content.strip()
        print(f"Enhanced image prompt: {enhanced_prompt}")
        
        return enhanced_prompt
    except Exception as e:
        print(f"Error creating enhanced prompt: {str(e)}")
        # Fallback to basic prompt if something goes wrong
        return f"Studio Ghibli style illustration of {recipe.title}: {recipe.description[:150]}"
