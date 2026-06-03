from ipaddress import ip_address


def _normalize_ip(value):
    if not value:
        return None

    try:
        return ip_address(value.strip()).compressed
    except ValueError:
        return None


def get_request_ip(request):
    remote_addr = request.META.get("REMOTE_ADDR")
    return _normalize_ip(remote_addr) or remote_addr
