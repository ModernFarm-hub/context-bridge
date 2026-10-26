# SPDX-License-Identifier: Apache-2.0
"""Local profile configuration, with read compatibility for legacy identities."""

def local_identity(data):
    library = data.get('library_id', data.get('tenant'))
    profile = data.get('profile_id', data.get('employee'))
    if not isinstance(library, str) or not library or not isinstance(profile, str) or not profile:
        raise ValueError('Local library_id and profile_id are required')
    return library, profile


def profile_directory(directory, name=None):
    """Named libraries have separate files and databases, never shared ownership."""
    import re
    from pathlib import Path
    if name is None or name == 'default':
        return Path(directory)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', name):
        raise ValueError('Profile name must contain 1–64 letters, digits, underscores or hyphens, starting with a letter or digit')
    return Path(directory)/'profiles'/name
