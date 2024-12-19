from django.shortcuts import redirect, render
from functools import wraps

def require_authenticated_staff_or_superuser(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if not (request.user.is_staff or request.user.is_superuser):
            return render(request, '403.html', {'message': "Nie masz dostępu do tej strony"})

        return view_func(request, *args, **kwargs)

    return _wrapped_view

def require_authenticated_superuser(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if not request.user.is_superuser:
            return render(request, '403.html', {'message': "Nie masz dostępu do tej strony"})

        return view_func(request, *args, **kwargs)

    return _wrapped_view
