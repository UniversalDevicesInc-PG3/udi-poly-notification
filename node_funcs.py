
import os
import re
import json


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
