# Recipe Helper

A comprehensive Django-based web application for managing recipes, meal planning, and grocery shopping, with AI-powered recipe generation capabilities.

## Features

- **Recipe Management**: Create, view, edit, and delete recipes with detailed information including ingredients, instructions, preparation time, and more.
- **AI Recipe Generation**: Generate new recipes or tweak existing ones using OpenAI integration.
- **Meal Planning**: Plan meals for the week with a calendar-based interface.
- **Grocery List Generation**: Automatically create grocery lists based on meal plans.
- **User Authentication**: Secure user registration and login system.
- **Image Support**: Upload images for recipes or use image URLs.

## Technology Stack

- **Backend**: Django 5.2
- **Database**: SQLite (default)
- **AI Integration**: OpenAI API
- **Media Storage**: Local file system

## Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Setup

1. Clone the repository:
   ```
   git clone <repository-url>
   cd recipe-helper
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```
   pip install django python-dotenv pillow openai
   ```

4. Create a `.env` file in the project root with the following content:
   ```
   SECRET_KEY=your_django_secret_key
   OPENAI_API_KEY=your_openai_api_key
   DEBUG=True
   ```

5. Run database migrations:
   ```
   python manage.py migrate
   ```

6. Create a superuser (admin) account:
   ```
   python manage.py createsuperuser
   ```

7. Start the development server:
   ```
   python manage.py runserver
   ```

8. Visit `http://127.0.0.1:8000` in your browser to use the application.

## Project Structure

- **recipe_planner/**: Main project settings and configuration
- **recipes/**: Main application with models, views, and templates
  - **models.py**: Database models for recipes, meal plans, and grocery lists
  - **views.py**: Views for all application functionality
  - **templates/**: HTML templates for the frontend
  - **urls.py**: URL routing for the application
- **media/**: Storage for uploaded images
- **venv/**: Virtual environment (not tracked in Git)

## Usage

### Recipe Management

- Browse recent recipes on the home page
- View your personal recipe collection
- Create new recipes with detailed information
- Edit or delete your existing recipes

### AI Recipe Generation

- Generate completely new recipes by providing preferences or ingredients
- Tweak existing recipes with specific modifications
- AI will suggest recipe details including ingredients, instructions, and cooking times

### Meal Planning

- Plan your meals for each day of the week
- Assign recipes to specific meal types (breakfast, lunch, dinner, snack)
- View and modify your meal plan in a calendar view

### Grocery Lists

- Generate grocery lists based on your meal plan for a specific time period
- Mark items as purchased
- Manage multiple grocery lists

## Environment Variables

Create a `.env` file in the project root with these variables:

- `SECRET_KEY`: Django secret key for security
- `OPENAI_API_KEY`: Your OpenAI API key for AI recipe generation
- `DEBUG`: Set to 'True' for development, 'False' for production

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b new-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin new-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- OpenAI for providing the API used in recipe generation
- Django project for the web framework 