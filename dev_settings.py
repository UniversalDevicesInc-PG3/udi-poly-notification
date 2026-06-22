"""Local dev edition override via dev_edition.txt (local dev install only)."""

import json
import logging
import os
from contextlib import contextmanager

from udi_interface import Custom
from udi_interface.custom import CLOGGER

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_DEV_EDITION_FILE = os.path.join(_PLUGIN_DIR, 'dev_edition.txt')
_ALLOWED_EDITIONS = {'Free', 'Standard', 'Professional', 'Production', 'Test'}


@contextmanager
def _suppress_custom_logger():
    old_level = CLOGGER.level
    CLOGGER.setLevel(logging.INFO)
    try:
        yield
    finally:
        CLOGGER.setLevel(old_level)


class DevSafeCustom(Custom):
    """Custom data store that never logs values (udi_interface CUSTOM debug is muted)."""

    def load(self, new_data, save=False):
        with _suppress_custom_logger():
            super().load(new_data, save=save)

    def __setitem__(self, key, notice):
        with _suppress_custom_logger():
            super().__setitem__(key, notice)

    def __setattr__(self, key, notice):
        with _suppress_custom_logger():
            super().__setattr__(key, notice)

    def delete(self, key):
        with _suppress_custom_logger():
            super().delete(key)

    def _redacted_view(self):
        raw = self.__dict__.get('_rawdata', {})
        return custom_data_log_label(raw)

    def __repr__(self):
        return f'<DevSafeCustom {self._redacted_view()}>'

    def __str__(self):
        return self._redacted_view()


def custom_data_log_label(data):
    if data is None:
        return 'custom data=None'
    if not isinstance(data, dict):
        return 'custom data=<non-dict>'
    keys = list(data.keys())
    if not keys:
        return 'custom data (0 keys)'
    return f'custom data ({len(keys)} keys; names={",".join(sorted(keys))})'


_STORE_URL_SUFFIXES = ('.zip', '.tgz', '.tar.gz')


def _server_json_dev_mode():
    try:
        with open(os.path.join(os.getcwd(), 'server.json'), encoding='utf-8') as f:
            data = json.load(f)
        return bool(data.get('devMode'))
    except (OSError, ValueError, TypeError):
        return False


def is_dev_mode(poly):
    config = poly.getConfig() if hasattr(poly, 'getConfig') else None
    if isinstance(config, dict) and config.get('devMode'):
        return True
    serverdata = getattr(poly, 'serverdata', None) or {}
    if serverdata.get('devMode'):
        return True
    return _server_json_dev_mode()


def _poly_config(poly):
    config = poly.getConfig() if hasattr(poly, 'getConfig') else None
    return config if isinstance(config, dict) else {}


def _install_url(poly):
    return str(_poly_config(poly).get('url', '')).strip()


def _nodeserver_home(poly):
    home = str(_poly_config(poly).get('home', '')).strip()
    if home:
        return home
    return os.getcwd()


def is_local_install(poly):
    """True for local dev nodeservers (devMode + symlink/git install, not store zip)."""
    if not is_dev_mode(poly):
        return False

    url = _install_url(poly).lower()
    if url.endswith(_STORE_URL_SUFFIXES):
        return False

    if _install_url(poly).startswith('lnk:'):
        return True

    for path in (_nodeserver_home(poly), os.getcwd()):
        if path and os.path.islink(path):
            return True

    src_url = _install_url(poly)
    if src_url and ('github.com' in src_url or src_url.startswith('/')):
        return True

    # devMode profile before PG3 config arrives (typical local NS startup)
    return True


def licensed_edition(poly):
    return poly.pg3init.get('edition', 'Free')


def dev_edition_override_active(poly, effective_edition):
    return is_local_install(poly) and effective_edition != licensed_edition(poly)


def _normalize_edition(value):
    edition = value.strip()
    if edition.lower() == 'production':
        return 'Standard'
    return edition


def _read_dev_edition_file():
    try:
        with open(_DEV_EDITION_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                return _normalize_edition(line)
    except FileNotFoundError:
        return None
    except OSError:
        return None
    return None


def resolve_edition(poly, logger):
    edition = licensed_edition(poly)
    if not is_local_install(poly):
        override = _read_dev_edition_file()
        if override is not None and override != edition:
            logger.warning(
                'Ignoring dev_edition.txt on non-local install (licensed %s, file %s)',
                edition,
                override,
            )
        return edition

    override = _read_dev_edition_file()
    if override is None:
        return edition

    if override not in _ALLOWED_EDITIONS:
        logger.warning('Ignoring invalid dev edition in dev_edition.txt: %r', override)
        return edition

    if override != edition:
        logger.warning(
            'Dev edition override: %s -> %s (dev_edition.txt, local install)',
            edition,
            override,
        )
    return override
