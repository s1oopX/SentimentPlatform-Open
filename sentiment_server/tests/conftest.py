import os
import shutil
from pathlib import Path

import pytest


if os.name == 'nt':
    from _pytest.tmpdir import TempPathFactory
    from _pytest.pathlib import make_numbered_dir

    _COMPAT_TEMP_ROOT = Path(__file__).resolve().parents[1] / '.pytest_tmp_compat'

    def _get_windows_compatible_basetemp(self):
        if self._basetemp is not None:
            return self._basetemp

        basetemp = self._given_basetemp or _COMPAT_TEMP_ROOT
        if basetemp.exists():
            shutil.rmtree(basetemp, ignore_errors=True)
        basetemp.mkdir(mode=0o777, parents=True, exist_ok=True)
        self._basetemp = basetemp.resolve()
        return self._basetemp

    def _mk_windows_compatible_tmp(self, basename: str, numbered: bool = True):
        basename = self._ensure_relative_to_basetemp(basename)
        if numbered:
            return make_numbered_dir(
                root=self.getbasetemp(),
                prefix=basename,
                mode=0o777,
            )

        path = self.getbasetemp() / basename
        path.mkdir(mode=0o777)
        return path

    TempPathFactory.getbasetemp = _get_windows_compatible_basetemp
    TempPathFactory.mktemp = _mk_windows_compatible_tmp


@pytest.fixture
def user_password():
    return 'TestPass123!'


@pytest.fixture
def user_email():
    return 'testuser@example.com'


@pytest.fixture
def admin_email():
    return 'admin@example.com'


@pytest.fixture
def analyst_email():
    return 'analyst@example.com'
