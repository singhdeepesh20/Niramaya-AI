def normalize_username(username: str) -> str:
    """Canonicalize usernames so login and uniqueness checks ignore casing/spaces."""
    return username.strip().lower()
