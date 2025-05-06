# Cursor Editor Guidelines for Domy Project

## Technology Stack
- **Framework**: Django (Python web framework)
- **Frontend**: Vue3 components with Bootstrap 5
- **Database**: SQLite (in development), prosgress (in production)

## Coding Patterns

### Django Structure
- Follow Django's MVT (Model-View-Template) architecture
- Use class-based models with descriptive field names
- Keep URL patterns organized in app-specific `urls.py` files
- Use Django's auth system for user management

### Views
- Prefer function-based views over class-based views
- Use decorators (`@require_authenticated_staff_or_superuser`) for permission control
- For AJAX/JSON responses, use `JsonResponse` with proper status codes
- For form submissions, use `request.POST.get()` pattern
- For API endpoints, use `json.loads(request.body)` for parsing JSON data

### Templates
- Extend from `base.html` for consistent layout
- Use Bootstrap 5 for styling and components
- Place app-specific templates in their own directories
- Use partials for reusable components (e.g., `partials/_cart_sidebar.html`)

### Security
- Always use Django's CSRF protection
- Use decorators to enforce staff/superuser permissions for admin functions
- Validate all user inputs

### JavaScript
- Use vanilla JavaScript with occasional jQuery when needed
- Use fetch API for AJAX calls
- Handle responses with proper error checking

### Models
- Use descriptive names for models and fields
- Implement `__str__` methods for better admin representation
- Use appropriate field types and constraints
- Set related_name for reverse relationships

### Database Queries
- Use prefetch_related and select_related for optimizing queries
- Filter early to reduce database load
- Use Django's ORM features (e.g., Q objects for complex queries)

## Development Workflow
1. Create URL pattern in appropriate `urls.py`
2. Implement view function with proper permission decorators
3. Create template extending from base.html
4. Add UI elements using Bootstrap components
5. Implement necessary JavaScript functionality
6. Update navigation in base.html if needed

## Accessibility & UI Guidelines
- Menu items specific to staff/superusers should be conditionally displayed
- Use Bootstrap's responsive classes for mobile compatibility
- Use Django template variables for dynamic content
- Follow Polish language for user-facing text

## Common Patterns
- Staff/superuser views often use the `@require_authenticated_staff_or_superuser` decorator
- Form submissions typically redirect to a list view upon success
- AJAX responses follow the format: `{'status': 'success/error', 'message': '...'}` 
