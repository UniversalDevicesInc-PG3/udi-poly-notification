import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from nodes.WhatsApp import (
    WhatsApp,
    PROVIDER_CALLMEBOT,
    PROVIDER_TEXTMEBOT,
    TEXTMEBOT_SEND_INTERVAL,
    normalize_whatsapp_provider,
)
from threading import Lock

wa_mod = sys.modules['nodes.WhatsApp']


class _StubWhatsApp(WhatsApp):
    def __init__(self, provider):
        self.provider = provider
        self.iname = 'test'


def test_normalize_whatsapp_provider_defaults_and_aliases():
    assert normalize_whatsapp_provider(None) == PROVIDER_CALLMEBOT
    assert normalize_whatsapp_provider('') == PROVIDER_CALLMEBOT
    assert normalize_whatsapp_provider('CallMeBot') == PROVIDER_CALLMEBOT
    assert normalize_whatsapp_provider('call-me-bot') == PROVIDER_CALLMEBOT
    assert normalize_whatsapp_provider('TextMeBot') == PROVIDER_TEXTMEBOT
    assert normalize_whatsapp_provider('text me bot') == PROVIDER_TEXTMEBOT
    assert normalize_whatsapp_provider('unknown') == 'unknown'


def test_callmebot_ok():
    node = _StubWhatsApp(PROVIDER_CALLMEBOT)
    ok = {
        'code': 200,
        'data': '<p><b>Message queued.</b> You will receive it in a few seconds.',
    }
    assert node._send_ok(ok) is True
    bad = {'code': 200, 'data': '<p>Error: invalid apikey</p>'}
    assert node._send_ok(bad) is False


def test_textmebot_ok():
    node = _StubWhatsApp(PROVIDER_TEXTMEBOT)
    ok = {
        'code': 200,
        'data': 'Sending message...<br>Result: <b>Success!</b>',
    }
    assert node._send_ok(ok) is True
    bad = {'code': 200, 'data': 'Result: Error'}
    assert node._send_ok(bad) is False


def test_rate_limit_detection():
    callme = _StubWhatsApp(PROVIDER_CALLMEBOT)
    textme = _StubWhatsApp(PROVIDER_TEXTMEBOT)
    assert callme._send_rate_limited({'code': 503}) is True
    assert callme._send_rate_limited({'code': 429}) is False
    assert textme._send_rate_limited({'code': 429}) is True
    assert textme._send_rate_limited({'code': 503}) is True


def test_textmebot_interval_wait(monkeypatch):
    node = _StubWhatsApp(PROVIDER_TEXTMEBOT)
    node._send_lock = Lock()
    node._last_textmebot_send_at = 1000.0
    sleeps = []
    monkeypatch.setattr(wa_mod.time, 'time', lambda: 1003.0)
    monkeypatch.setattr(wa_mod.time, 'sleep', lambda s: sleeps.append(s))
    node._wait_textmebot_interval()
    assert sleeps == [TEXTMEBOT_SEND_INTERVAL - 3.0]


def test_textmebot_interval_skipped_for_callmebot(monkeypatch):
    node = _StubWhatsApp(PROVIDER_CALLMEBOT)
    node._last_textmebot_send_at = 1000.0
    sleeps = []
    monkeypatch.setattr(wa_mod.time, 'sleep', lambda s: sleeps.append(s))
    node._wait_textmebot_interval()
    assert sleeps == []
