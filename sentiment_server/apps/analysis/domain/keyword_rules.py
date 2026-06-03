def iter_normalized_keywords(value):
    if not isinstance(value, (list, tuple)):
        return

    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized:
            yield normalized


def normalize_keywords(value):
    return list(iter_normalized_keywords(value))
