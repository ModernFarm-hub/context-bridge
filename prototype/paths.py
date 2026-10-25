# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""State paths independent of source checkout or current directory."""
import os
from pathlib import Path
import platform


def data_home():
    override = os.environ.get('CONTEXT_BRIDGE_HOME')
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise ValueError('CONTEXT_BRIDGE_HOME must be an absolute path')
        return path
    if platform.system() == 'Darwin':
        return Path.home() / 'Library/Application Support/ContextBridge'
    if platform.system() == 'Windows':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'ContextBridge'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'context-bridge'
