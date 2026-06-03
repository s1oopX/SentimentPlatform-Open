import apps.users.application.shared as application_shared


def update_user_profile(*, user, validated_data):
    new_avatar = validated_data.get("avatar")
    application_shared.validate_uploaded_avatar_file(new_avatar)

    previous_avatar_name = (
        user.avatar.name if getattr(user, "avatar", None) and user.avatar.name else ""
    )
    previous_avatar_storage = user.avatar.storage if previous_avatar_name else None

    changed_fields = list(validated_data.keys())
    for field, value in validated_data.items():
        setattr(user, field, value)
    user.save(update_fields=changed_fields + ["updated_at"])

    if previous_avatar_name and previous_avatar_name != user.avatar.name:
        previous_avatar_storage.delete(previous_avatar_name)

    return user


__all__ = ["update_user_profile"]
