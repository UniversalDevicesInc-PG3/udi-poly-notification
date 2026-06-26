
import os
import re
import json
import time
import logging
from collections import deque
from threading import Lock, Timer

QUEUE_LOGGER = logging.getLogger(__name__)
SEND_QUEUE_SAVE_DELAY = 1.0


def get_messages():
    _MESSAGES = [
        '(IGNORE)',
        'On',
        'Off',
        'Light on',
        'Light off',
        'Open',
        'Closed',
        'Locked',
        'Unlocked',
        'Jammed',
        'Motion detected',
        'Water leak',
        'Rang',
        'At home',
        'Away',
        'Offline',
        'Low battery',
        'Armed',
        'Disarmed',
        'Triggered',
        "Don't forget!",
        'WARNING',
        'EMERGENCY',
        'Heat warning',
        'Cold warning',
        'Reset',
        'Problem',
        'Okay',
        'Good',
        'Bad',
        'Started',
        'Finished',
        'Sleeping',
        'Awake',
        'Alive',
        'Dead',
        'Not Responding',
    ]
    return _MESSAGES

# These are the default Pushover sounds, we save this so
# the order never changes, and they are always first in the list.
_DEFAULT_SOUNDS = [
    'pushover',
    'bike',
    'bugle',
    'cashregister',
    'classical',
    'cosmic',
    'falling',
    'gamelan',
    'incoming',
    'intermission',
    'magic',
    'mechanical',
    'pianobar',
    'siren',
    'spacealarm',
    'tugboat',
    'alien',
    'climb',
    'persistent',
    'echo',
    'updown',
    'vibrate',
    'none',
]

def get_default_sound_index(name):
    try:
        return _DEFAULT_SOUNDS.index(name)
    except ValueError:
        return -1

# Removes invalid charaters for ISY Node description
def get_valid_node_name(name):
    # Only allow utf-8 characters
    #  https://stackoverflow.com/questions/26541968/delete-every-non-utf-8-symbols-froms-string
    name = bytes(name, 'utf-8').decode('utf-8','ignore')
    # Remove <>`~!@#$%^&*(){}[]?/\;:"'` characters from name
    return re.sub(r"[<>`~!@#$%^&*(){}[\]?/\\;:\"']+", "", name)

def get_valid_node_address(name):
    return get_valid_node_name(name)[:14].lower()

def toC(tempF):
  # Round to the nearest .5
  return round(((tempF - 32) / 1.8) * 2) / 2

def toF(tempC):
  # Round to nearest whole degree
  return int(round(tempC * 1.8) + 32)

def getMapName(map,val):
  val = int(val)
  for name in map:
    if int(map[name]) == val:
      return name

def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def make_file_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        # TODO: Trap this?
        os.makedirs(directory)
    return True

def get_profile_info(logger):
    pvf = 'profile/version.txt'
    try:
        with open(pvf) as f:
            pv = f.read().replace('\n', '')
            f.close()
    except Exception as err:
        logger.error('get_profile_info: failed to read  file {0}: {1}'.format(pvf,err), exc_info=True)
        pv = 0
    return { 'version': pv }

def get_server_data(logger):
    # Read the SERVER info from the json.
    sfile = 'server.json'
    try:
        with open(sfile) as data:
            serverdata = json.load(data)
    except Exception as err:
        logger.error('get_server_data: failed to read file {0}: {1}'.format(sfile,err), exc_info=True)
        return False
    data.close()
    # Get the version info
    try:
        version = serverdata['credits'][0]['version']
    except (KeyError, ValueError):
        logger.info('Version not found in server.json.')
        version = '0.0.0.0'
    # Split version into two floats.
    sv = version.split(".");
    v1 = 0;
    v2 = 0;
    if len(sv) == 1:
        v1 = int(v1[0])
    elif len(sv) > 1:
        v1 = float("%s.%s" % (sv[0],str(sv[1])))
        if len(sv) == 3:
            v2 = int(sv[2])
        else:
            v2 = float("%s.%s" % (sv[2],str(sv[3])))
    serverdata['version'] = version
    serverdata['version_major'] = v1
    serverdata['version_minor'] = v2
    return serverdata

def get_profile_info(logger):
    pvf = 'profile/version.txt'
    try:
        with open(pvf) as f:
            pv = f.read().replace('\n', '')
    except Exception as err:
        logger.error('get_profile_info: failed to read  file {0}: {1}'.format(pvf,err), exc_info=True)
        pv = 0
    f.close()
    return { 'version': pv }

def get_subset_str(subset):
    if len(subset) == 0:
        # No data, just use zero
        return '0'
    subset_str = ""
    subset.sort()
    while len(subset) > 0:
        x = subset.pop(0)
        if subset_str != "":
            subset_str += ","
        subset_str += str(x)
        if len(subset) > 0 and x == subset[0] - 1:
            y = subset.pop(0)
            while len(subset) > 0 and (y == subset[0] or y == subset[0] - 1):
                y = subset.pop(0)
            subset_str += "-" + str(y)
    return(subset_str)

class SendQueue:
    def __init__(self, max_items=128, max_age=3600):
        self.max_items = max_items
        self.max_age = max_age
        self.items = deque()
        self.lock = Lock()

    def enqueue(self, payload):
        dropped = None
        with self.lock:
            self.items.append({'ts': time.time(), 'payload': payload})
            while len(self.items) > self.max_items:
                dropped = self.items.popleft()
        return dropped

    def pop_all(self):
        with self.lock:
            items = list(self.items)
            self.items.clear()
        return items

    def clear(self):
        with self.lock:
            self.items.clear()

    def size(self):
        with self.lock:
            return len(self.items)

    def snapshot(self):
        with self.lock:
            return [{'ts': item['ts'], 'payload': item['payload']} for item in self.items]

    def restore(self, items):
        validated = []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict) or 'payload' not in item:
                    continue
                try:
                    ts = float(item.get('ts', time.time()))
                except (TypeError, ValueError):
                    ts = time.time()
                validated.append({'ts': ts, 'payload': item['payload']})
        with self.lock:
            self.items.clear()
            for item in validated:
                self.items.append(item)
            while len(self.items) > self.max_items:
                self.items.popleft()

    def keep_fresh(self, items):
        now = time.time()
        fresh = []
        stale = 0
        for item in items:
            ts = item.get('ts', 0)
            if now - ts <= self.max_age:
                fresh.append(item.get('payload'))
            else:
                stale += 1
        return fresh, stale

    def filter_fresh_items(self, items):
        now = time.time()
        fresh = []
        stale = 0
        for item in items:
            ts = item.get('ts', 0)
            if now - ts <= self.max_age:
                fresh.append(item)
            else:
                stale += 1
        return fresh, stale


class DebouncedCustomSaver:
    """Coalesce rapid controller.Data writes for the same key."""

    def __init__(self, delay=SEND_QUEUE_SAVE_DELAY):
        self.delay = delay
        self._lock = Lock()
        self._timers = {}

    def schedule(self, controller, key, value):
        with self._lock:
            timer = self._timers.pop(key, None)
            if timer is not None:
                timer.cancel()
            timer = Timer(self.delay, self._write, args=(controller, key, value, key))
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def write_now(self, controller, key, value):
        with self._lock:
            timer = self._timers.pop(key, None)
            if timer is not None:
                timer.cancel()
        controller.Data[key] = value

    def _write(self, controller, key, value, timer_key):
        with self._lock:
            if self._timers.get(timer_key) is not None:
                self._timers.pop(timer_key, None)
        controller.Data[key] = value


_SEND_QUEUE_DEBOUNCER = DebouncedCustomSaver()


def get_send_queue_debouncer():
    return _SEND_QUEUE_DEBOUNCER


def send_queue_storage_key(service, iname=None):
    if iname:
        return f'send_queue_{service}_{iname}'
    return f'send_queue_{service}'


def load_send_queue(controller, key, queue, logger=None):
    log = logger or QUEUE_LOGGER
    raw = controller.get_data(key, [])
    if not isinstance(raw, list):
        if raw not in (None, []):
            log.warning('Ignoring corrupt send queue data for %s', key)
        return 0, 0
    fresh_items, stale = queue.filter_fresh_items(raw)
    queue.restore(fresh_items)
    if stale > 0:
        log.warning('Dropped %s stale queued notification(s) for %s', stale, key)
    loaded = queue.size()
    if loaded > 0:
        log.info('Restored %s queued notification(s) for %s', loaded, key)
    if stale > 0 or loaded != len(raw):
        persist_send_queue(controller, key, queue, immediate=True)
    return loaded, stale


def persist_send_queue(controller, key, queue, immediate=False, debouncer=None):
    if debouncer is None:
        debouncer = get_send_queue_debouncer()
    snapshot = queue.snapshot()
    if immediate:
        debouncer.write_now(controller, key, snapshot)
    else:
        debouncer.schedule(controller, key, snapshot)
