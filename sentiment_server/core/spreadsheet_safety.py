FORMULA_PREFIXES = ("=", "+", "-", "@")


def escape_spreadsheet_formula(value):
    """Prevent CSV/XLSX formula injection for user-controlled text cells."""
    if not isinstance(value, str):
        return value
    if not value:
        return value
    first_visible = value.lstrip()[:1]
    if first_visible in FORMULA_PREFIXES:
        return f"'{value}"
    return value
