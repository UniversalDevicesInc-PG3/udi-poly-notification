import time

from node_funcs import (
    SendQueue,
    DebouncedCustomSaver,
    send_queue_storage_key,
    load_send_queue,
    persist_send_queue,
)


class MockData(dict):
    def __init__(self):
        super().__init__()
        self.writes = []

    def __setitem__(self, key, value):
        self.writes.append((key, value))
        super().__setitem__(key, value)


class MockController:
    def __init__(self, data=None):
        self.Data = MockData()
        if data:
            for key, value in data.items():
                self.Data[key] = value

    def get_data(self, param, default):
        return self.Data.get(param, default)


def test_snapshot_restore_round_trip():
    queue = SendQueue(max_items=4, max_age=3600)
    queue.enqueue({'title': 'one'})
    queue.enqueue({'title': 'two'})
    restored = SendQueue(max_items=4, max_age=3600)
    restored.restore(queue.snapshot())
    assert restored.size() == 2
    items = restored.pop_all()
    assert items[0]['payload']['title'] == 'one'
    assert items[1]['payload']['title'] == 'two'


def test_restore_trims_to_max_items():
    queue = SendQueue(max_items=2, max_age=3600)
    queue.restore([
        {'ts': 1.0, 'payload': {'n': 1}},
        {'ts': 2.0, 'payload': {'n': 2}},
        {'ts': 3.0, 'payload': {'n': 3}},
    ])
    assert queue.size() == 2
    items = queue.pop_all()
    assert items[0]['payload']['n'] == 2
    assert items[1]['payload']['n'] == 3


def test_load_send_queue_drops_stale_items():
    controller = MockController({
        'send_queue_udmobile': [
            {'ts': time.time() - 7200, 'payload': {'old': True}},
            {'ts': time.time(), 'payload': {'fresh': True}},
        ],
    })
    queue = SendQueue(max_items=128, max_age=3600)
    loaded, stale = load_send_queue(controller, 'send_queue_udmobile', queue)
    assert loaded == 1
    assert stale == 1
    items = queue.pop_all()
    assert items[0]['payload'] == {'fresh': True}
    assert controller.Data['send_queue_udmobile'] == items


def test_load_send_queue_tolerates_corrupt_data():
    controller = MockController({'send_queue_udmobile': 'bad'})
    queue = SendQueue()
    loaded, stale = load_send_queue(controller, 'send_queue_udmobile', queue)
    assert loaded == 0
    assert stale == 0
    assert queue.size() == 0


def test_persist_send_queue_writes_snapshot():
    controller = MockController()
    queue = SendQueue()
    queue.enqueue({'text': 'hello'})
    persist_send_queue(controller, 'send_queue_whatsapp_foo', queue, immediate=True)
    assert controller.Data['send_queue_whatsapp_foo'][0]['payload']['text'] == 'hello'


def test_send_queue_storage_key():
    assert send_queue_storage_key('udmobile') == 'send_queue_udmobile'
    assert send_queue_storage_key('pushover', 'po') == 'send_queue_pushover_po'


def test_debounced_custom_saver_coalesces_writes():
    controller = MockController()
    saver = DebouncedCustomSaver(delay=0.05)
    saver.schedule(controller, 'k', [1])
    saver.schedule(controller, 'k', [1, 2])
    time.sleep(0.12)
    assert controller.Data['k'] == [1, 2]
    assert len(controller.Data.writes) == 1


def test_debounced_write_now_cancels_pending():
    controller = MockController()
    saver = DebouncedCustomSaver(delay=1.0)
    saver.schedule(controller, 'k', [1])
    saver.write_now(controller, 'k', [2])
    assert controller.Data['k'] == [2]
    time.sleep(0.05)
    assert controller.Data['k'] == [2]
    assert len(controller.Data.writes) == 1
