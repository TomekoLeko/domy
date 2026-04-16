# Cursor guidance (backend-focused)

This repository is the Django backend.

The React frontend is a separate project (outside this repository). When implementing changes for UI/requests from the frontend, adjust only the backend pieces here (endpoints, CORS/CSRF/session behavior), and coordinate the frontend changes in the external React repo.

## CSRF for cross-domain SPA

The React SPA must obtain CSRF token from the backend before `POST`/`PUT`/`PATCH`/`DELETE`.

Use:

- `GET /api/auth/csrf/` with `credentials: 'include'` (recommended)
- `GET /api/auth/me/` with `credentials: 'include'` (legacy alias)

This endpoint sets the `csrftoken` cookie and returns JSON:

- `csrfToken`: string
- `user`: object or `null`

Then the frontend should send the token as `X-CSRFToken` together with `credentials: 'include'` on mutating requests.

