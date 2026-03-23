"""
Audit logging: middleware and utilities.
"""
import re
from .models import AuditLog


def get_client_ip(request):
    """Get client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def get_action_from_method(method):
    """Map HTTP method to action."""
    mapping = {'POST': 'create', 'PUT': 'update', 'PATCH': 'update', 'DELETE': 'delete'}
    return mapping.get(method.upper(), 'other')


def parse_api_path(path):
    """Extract resource and object_id from API path like /api/patients/5/."""
    # Remove /api/ prefix if present
    match = re.match(r'^/api/(.+)$', path)
    if not match:
        return '', ''
    rest = match.group(1).strip('/')
    parts = rest.split('/')
    resource = parts[0] if parts else ''
    object_id = parts[1] if len(parts) > 1 and parts[1].isdigit() else ''
    return resource.replace('-', '_'), object_id


def log_audit(request, action=None, resource=None, object_id=None, object_repr=None, extra=None):
    """Manually log an audit event."""
    path = getattr(request, 'path', '') or ''
    method = getattr(request, 'method', '') or 'GET'
    r, oid = parse_api_path(path)
    resource = resource or r
    object_id = object_id or oid
    action = action or get_action_from_method(method)
    user = getattr(request, 'user', None)
    if user and not user.is_authenticated:
        user = None

    try:
        ip = get_client_ip(request) if request else None
    except Exception:
        ip = None
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''

    AuditLog.objects.create(
        user=user,
        action=action,
        path=path,
        method=method,
        resource=resource,
        object_id=str(object_id) if object_id else '',
        object_repr=(object_repr or '')[:255],
        ip_address=ip,
        user_agent=user_agent,
        extra=extra,
    )


class AuditLogMiddleware:
    """
    Log POST, PUT, PATCH, DELETE requests to /api/ (excluding reports/logs to avoid recursion).
    """
    MUTATE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method in self.MUTATE_METHODS and request.path.startswith('/api/'):
            if '/reports/logs' in request.path:
                return response
            try:
                log_audit(request)
            except Exception:
                pass
        return response
