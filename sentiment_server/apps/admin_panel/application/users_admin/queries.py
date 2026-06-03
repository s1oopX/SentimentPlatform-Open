from apps.admin_panel.infra.selectors.users_admin import (
    get_filtered_users,
    get_user_by_id,
)


def build_user_list_response(
    *, search="", role="", status_filter="", excluded_user_id=None
):
    return get_filtered_users(
        search=search,
        role=role,
        status_filter=status_filter,
        excluded_user_id=excluded_user_id,
    )


def build_user_detail_response(pk, *, excluded_user_id=None):
    return get_user_by_id(pk, excluded_user_id=excluded_user_id)
