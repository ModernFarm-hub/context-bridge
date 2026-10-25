# SPDX-License-Identifier: Apache-2.0
"""Local profile configuration, with read compatibility for legacy identities."""

def local_identity(data):
    library = data.get('library_id', data.get('tenant'))
    profile = data.get('profile_id', data.get('employee'))
    if not isinstance(library, str) or not library or not isinstance(profile, str) or not profile:
        raise ValueError('Local library_id and profile_id are required')
    return library, profile
