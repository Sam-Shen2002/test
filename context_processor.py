def sidebar_permissions(request):
    if not request.user.is_authenticated:
        return {}

    return {
        'permissions': {
            'show_log_function': request.user.has_perm("Arcadyan_Web.add_uploadedlogfile"),
            'show_user': request.user.has_perm("auth.add_user"),
            'show_log': request.user.has_perm("django_db_logger.add_statuslog"),
            'show_roles': request.user.has_perm("members.add_group_list"),
        }
    }