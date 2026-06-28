import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from constants import SOUNDS_LIST
from node_funcs import SendQueue
from nodes.ISYPortal import ISYPortal


class _StubISYPortal(ISYPortal):
    def __init__(self):
        self.address = 'ip_isyp'
        self.name = 'ISY Portal'
        self.driver = {'GV2': 0}
        self.sounds_list = SOUNDS_LIST
        self.devices_and_groups = [
            {'type': 'group', 'id': '_default_', 'name': 'default'},
        ]
        self.send_queue = SendQueue(128, 3600)
        self._init_st = True
        self.controller = SimpleNamespace(
            profile_installed=True,
            is_profile_node_written=lambda _node: True,
            get_message_from_query=lambda query: {
                'subject': 'Test Subject',
                'body': 'Test Body',
            },
        )
        self.enqueued = None

    def getDriver(self, driver):
        if driver in self.driver:
            return self.driver[driver]
        return 0

    def can_deliver(self):
        return False

    def flush_send_queue(self):
        return 0

    def enqueue_send(self, params, reason):
        self.enqueued = (params, reason)
        return True


def test_do_send_omitted_sound_uses_default():
    node = _StubISYPortal()
    assert node.do_send({'title': 'Subject', 'body': 'Body'}) is True
    assert node.enqueued is not None
    assert 'sound' not in node.enqueued[0]


def test_cmd_send_sys_short_with_params_without_sound():
    node = _StubISYPortal()
    command = {
        'address': 'ip_isyp',
        'cmd': 'GV10',
        'query': {
            'Content.uom147': {
                'notification': {
                    'formatted': {
                        'subject': 'Bersaglio: Occupancy Changed',
                        'body': 'Home State: 4',
                    },
                },
            },
        },
    }
    assert node.cmd_send_sys_short_with_params(command) is True
    assert node.enqueued[0]['title'] == 'Test Subject'
    assert node.enqueued[0]['body'] == 'Test Body'
    assert 'sound' not in node.enqueued[0]
