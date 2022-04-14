"""
  Notification Pushover Node

  TODO:
    - Make sure pushover name is get_valid_node_name, and Length
    - Clean out profile directory?
    - Make list of sounds
    - Allow groups of devices in configuration
"""
from udi_interface import Node,LOGGER
from threading import Thread,Event
import time
import logging
import collections
from node_funcs import make_file_dir,is_int,get_default_sound_index

ERROR_NONE       = 0
ERROR_UNKNOWN    = 1
ERROR_APP_AUTH   = 2
ERROR_USER_AUTH  = 3
ERROR_MESSAGE_CREATE = 4
ERROR_MESSAGE_SEND   = 5
ERROR_PARAM          = 6

REM_PREFIX = "REMOVED-"

# How many tries to get or post, -1 is forever
RETRY_MAX = -1
# How long to wait between tries, in seconds
RETRY_WAIT = 5

class Pushover(Node):
    """
    """
    def __init__(self, controller, primary, address, name, session, info):
        """
        """
        # Need these for l_debug
        self.name     = name
        self.address  = address
        self.controller = controller
        self.session  = session
        self.info     = info
        self.iname    = info['name']
        self.oid      = self.id
        self.id       = 'pushover_' + self.iname
        self.app_key  = self.info['app_key']
        self.user_key = self.info['user_key']
        self._sys_short = None
        LOGGER.debug('{} {}'.format(address,name))
        controller.poly.subscribe(controller.poly.START,                  self.handler_start, address)
        super(Pushover, self).__init__(controller.poly, primary, address, name)

    def handler_start(self):
        """
        """
        LOGGER.info('')
        # We track our driver values because we need the value before it's been pushed.
        self.driver = {}
        self.set_device(self.get_device())
        self.set_priority(self.get_priority())
        self.set_format(self.get_format())
        self.set_retry(self.get_retry())
        self.set_expire(self.get_expire())
        self.set_sound(self.get_sound())
        # TODO: This should be stored at the node level, but PG2 didn't allow
        # that so eventually it should be moved to the node?
        self.devices_list = self.controller.Data.get('devices_list',[])
        self.sounds_list  = self.controller.Data.get('sounds_list',[])
        LOGGER.info("devices_list={}".format(self.devices_list))
        LOGGER.debug('Authorizing pushover app {}'.format(self.app_key))
        vstat = self.validate()
        if vstat['status'] is False:
            self.authorized = False
        else:
            self.authorized = True if vstat['status'] == 1 else False
        LOGGER.info("Authorized={}".format(self.authorized))
        if self.authorized:
            LOGGER.info("got devices={}".format(vstat['data']['devices']))
            self.build_device_list(vstat['data']['devices'])
            self.build_sound_list()
            self.controller.Data['devices_list'] = self.devices_list
            self.controller.Data['sounds_list']  = self.sounds_list
            self.set_error(ERROR_NONE)
            self._init_st = True
        else:
            self.set_error(ERROR_APP_AUTH)
            self._init_st = False

    def validate(self):
        res = self.session.post("1/users/validate.json",
            {
                'user':  self.user_key,
                'token': self.app_key,
            })
        LOGGER.debug('got: {}'.format(res))
        return res


    # Add items in second list to first if they don't exist
    #  self.controler.add_to_list(self.devices_list,vstat['devices'])
    def build_device_list(self,vlist):
        if len(self.devices_list) == 0:
            self.devices_list.append('all')
        self.devices_list[0] = 'all'
        # Add new items
        for item in vlist:
            # If it's not in the saved list, append it
            if self.devices_list.count(item) == 0:
                self.devices_list.append(item)
        # Make sure items are in the passed in list, otherwise prefix it
        # in devices_list
        for item in self.devices_list:
            if item != 'all' and not item.startswith(REM_PREFIX) and vlist.count(item) == 0:
                self.devices_list[self.devices_list.index(item)] = REM_PREFIX + item
        LOGGER.info("devices_list={}".format(self.devices_list))

    # Build the list of sounds, make sure the order of the list never changes.
    # sounds_list is a list of 2 element lists with shortname, longname
    # It has to be a list to keep the order the same, and be able to store
    # in Polyglot params
    def build_sound_list(self):
        res = self.get("1/sounds.json")
        LOGGER.debug('got: {}'.format(res))
        # Always build a new list
        sounds_list  = []
        custom_index = 100 # First index for a custom sound
        if res['status']:
            #
            # Build list with default sounds
            #
            for skey in res['data']['sounds']:
                # Is it a default?
                idx = get_default_sound_index(skey)
                if idx >= 0:
                    sounds_list.append([skey, res['data']['sounds'][skey], idx])
            LOGGER.debug('sounds={}'.format(sounds_list))
            #
            # Add any custom sounds
            #
            # hash for quick lookup of name to index of existing sounds_list
            es = {}
            for item in self.sounds_list:
                es[item[0]] = item
                if len(item) == 3:
                    # New style, if already have custom ones saved remember the max index
                    if item[2] > custom_index:
                        custom_index = item[2]
            # Add to our list if not exists.
            for skey in res['data']['sounds']:
                # Add to list if we have it, otherwise append
                if skey in es:
                    # and not a default
                    if get_default_sound_index(skey) == -1:
                        item = es[skey]
                        if len(item) == 2:
                            # Old style, add index
                            custom_index += 1
                            sounds_list.append([item[0],item[1],custom_index])
                        else:
                            sounds_list.append(item)
                else:
                    custom_index += 1
                    sounds_list.append([skey, res['data']['sounds'][skey], custom_index])
            LOGGER.debug('sounds={}'.format(sounds_list))
            # Make sure items are in the existing list, otherwise prefix it in devices_list
            for item in self.sounds_list:
                if not item[0] in res['data']['sounds']:
                    name = item[0] if item[0].startswith(REM_PREFIX) else REM_PREFIX + item[0]
                    if len(item) == 2:
                        # Old style without index
                        custom_index += 1
                        sounds_list.append([item[0],name,custom_index])
                    else:
                        sounds_list.append([item[0],name,item[2]])
            self.sounds_list = sorted(sounds_list, key=lambda sound: sound[2])
            LOGGER.debug('sounds={}'.format(self.sounds_list))
        return res


    """
    This lets the controller know when we are initialized, or if we had
    an error.  Since it can't call our write_profile until we have initilized
      None  = Still initializing
      False = Failed
      True  = All Good
    """
    def init_st(self):
        return self._init_st

    def query(self):
        self.reportDrivers()

    def setDriver(self,driver,value):
        self.driver[driver] = value
        super(Pushover, self).setDriver(driver,value)

    def getDriver(self,driver):
        if driver in self.driver:
            return self.driver[driver]
        else:
            return super(Pushover, self).getDriver(driver)

    def config_info_rest(self):
        str = '<li>curl -d \'{{"node":"{0}", "message":"The Message", "subject":"The Subject" -H "Content-Type: application/json"}}\' -X POST {1}/send'.format(self.address,self.controller.rest.listen_url)
        return str

    def config_info_nr(self):
        if self.rest is None:
            rest_ip = "None"
            rest_port = "None"
        else:
            rest_ip = self.controller.rest.ip
            rest_port = self.controller.rest.listen_port
        info = [
            '<li>Example Network Resource settings for Pushover<ul><li>http<li>POST<li>Host:{0}<li>Port:{1}<li>Path: /send?node={2}&Subject=My+Subject&monospace=1&device=1&priority=2<li>Encode URL: not checked<li>Timeout: 5000<li>Mode: Raw Text</ul>'.format(rest_ip,rest_port,self.address),
            '</ul>',
            '<p>The parms in the Path can be any of the below, if the param is not passed then the default from the pushover node will be used'
            '<table>',
            '<tr><th>Name<th>Value<th>Description',
        ]
        i = 0
        t = 'device'
        for item in self.devices_list:
            info.append('<tr><td>{}<td>{}<td>{}'.format(t,i,item))
            i += 1
            t = '&nbsp;'
        t = 'sound'
        for item in self.sounds_list:
            info.append('<tr><td>{}<td>{}<td>{}'.format(t,item[2],item[1]))
            t = '&nbsp;'
        info = info + [
            '<tr><td>monospace<td>1<td>use Monospace Font',
            '<tr><td>&nbsp;<td>0<td>Normal Font',

            '<tr><td>priority<td>-2<td>Lowest',
            '<tr><td>&nbsp;<td>-1<td>Low',
            '<tr><td>&nbsp;<td>0<td>Normal',
            '<tr><td>&nbsp;<td>1<td>High',
            '<tr><td>&nbsp;<td>2<td>Emergency',

            '<tr><td>html<td>1<td>Enable html',
            '<tr><td>&nbsp;<td>0<td>No html',

            '<tr><td>retry<td>n<td>Set Emergency retry to n',
            '<tr><td>expire<td>n<td>Set Emergency exipre to n',

            '</table>'
        ]
        return ''.join(info)

    def write_profile(self,nls):
        pfx = 'write_profile'
        LOGGER.debug('')
        #
        # nodedefs
        #
        # Open the template, and read into a string for formatting.
        template_f = 'template/nodedef/pushover.xml'
        LOGGER.debug("Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Open the output nodedefs file
        output_f   = 'profile/nodedef/{0}.xml'.format(self.iname)
        make_file_dir(output_f)
        # Write the nodedef file with our info
        LOGGER.debug("Writing {}".format(output_f))
        out_h = open(output_f, "w")
        out_h.write(data.format(self.id,self.iname))
        out_h.close()
        #
        # nls
        #
        nls.write("\n# Entries for Pushover {} {}\n".format(self.id,self.name))
        nls.write("ND-{0}-NAME = {1}\n".format(self.id,self.name))
        idx = 0
        subst = []
        for item in self.devices_list:
            nls.write("POD_{}-{} = {}\n".format(self.iname,idx,item))
            # Don't include REMOVED's in list
            if not item.startswith(REM_PREFIX):
                subst.append(str(idx))
            idx += 1
        sound_subst = []
        for item in self.sounds_list:
            nls.write("POS_{}-{} = {}\n".format(self.iname,item[2],item[1]))
            # Don't include REMOVED's in list
            if not item[1].startswith(REM_PREFIX):
                sound_subst.append(str(item[2]))
        #
        # editor
        #
        # Open the template, and read into a string for formatting.
        template_f = 'template/editor/pushover.xml'
        LOGGER.debug("Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Write the editors file with our info
        output_f   = 'profile/editor/{0}.xml'.format(self.iname)
        make_file_dir(output_f)
        LOGGER.debug("Writing {}".format(output_f))
        editor_h = open(output_f, "w")
        # TODO: We could create a better subst with - and , but do we need to?
        # TODO: Test calling get_subset_str in node_funcs.py
        editor_h.write(data.format(self.iname,",".join(subst),",".join(sound_subst)))
        editor_h.close()

    def set_device(self,val):
        LOGGER.info(val)
        if val is None:
            val = 0
        val = int(val)
        LOGGER.info('Set GV1 to {}'.format(val))
        self.setDriver('GV1', val)

    def get_device(self):
        cval = self.getDriver('GV1')
        if cval is None:
            return 0
        return int(cval)

    def get_device_name_by_index(self,dev=None):
        LOGGER.debug('dev={}'.format(dev))
        if dev is None:
            dev = self.get_device()
            LOGGER.debug('dev={}'.format(dev))
        else:
            if not is_int(dev):
                LOGGER.error('Passed in {} is not an integer'.format(dev))
                return False
            dev = int(dev)
        dev_name = None
        try:
            # 0 is all, so return none, otherwise look up the name
            if dev > 0:
                dev_name = self.devices_list[dev]
        except:
            LOGGER.error('Bad device index {}'.format(dev),exc_info=True)
            self.set_error(ERROR_PARAM)
            return False
        return dev_name

    def set_st(self,val):
        LOGGER.info(val)
        if val is False or val is None:
            val = 0
        elif val is True:
            val = 1
        else:
            val = int(val)
        LOGGER.info('Set ST to {}'.format(val))
        self.setDriver('ST', val)

    def set_error(self,val):
        LOGGER.info(val)
        if val is False:
            val = 0
        elif val is True:
            val = 1
        LOGGER.info('Set ERR to {}'.format(val))
        self.setDriver('ERR', val)
        self.set_st(True if val == 0 else False)

    def set_priority(self,val):
        LOGGER.info(val)
        if val is None:
            val = 0
        val = int(val)
        LOGGER.info('Set GV2 to {}'.format(val))
        self.setDriver('GV2', val)

    def get_priority(self):
        cval = self.getDriver('GV2')
        if cval is None:
            return 0
        return int(self.getDriver('GV2'))

    def set_format(self,val):
        LOGGER.info(val)
        if val is None:
            val = 0
        val = int(val)
        LOGGER.info('Set GV3 to {}'.format(val))
        self.setDriver('GV3', val)

    def get_format(self):
        cval = self.getDriver('GV3')
        if cval is None:
            return 0
        return int(self.getDriver('GV3'))

    def set_retry(self,val):
        LOGGER.info(val)
        if val is None:
            val = 30
        val = int(val)
        LOGGER.info('Set GV4 to {}'.format(val))
        self.setDriver('GV4', val)

    def get_retry(self):
        cval = self.getDriver('GV4')
        if cval is None:
            return 30
        return int(self.getDriver('GV4'))

    def set_expire(self,val):
        LOGGER.info(val)
        if val is None:
            val = 10800
        val = int(val)
        LOGGER.info('Set GV5 to {}'.format(val))
        self.setDriver('GV5', val)

    def get_expire(self):
        cval = self.getDriver('GV5')
        if cval is None:
            return 10800
        return int(self.getDriver('GV5'))

    def get_sound(self):
        cval = self.getDriver('GV6')
        if cval is None:
            return 0
        return int(self.getDriver('GV6'))

    def set_sound(self,val):
        LOGGER.info(val)
        if val is None:
            val = 0
        val = int(val)
        LOGGER.info('Set GV6 to {}'.format(val))
        self.setDriver('GV6', val)

    def get_message(self):
        cval = self.getDriver('GV7')
        if cval is None:
            return 0
        return int(self.getDriver('GV7'))

    def set_message(self,val):
        LOGGER.info(val)
        if val is None:
            val = 0
        val = int(val)
        LOGGER.info('Set GV7 to {}'.format(val))
        self.setDriver('GV7', val)

    def get_sys_short(self):
        return self._sys_short

    def set_sys_short(self,val):
        LOGGER.info(val)
        self._sys_short = val

    # Returns pushover priority numbers which start at -2 and our priority nubmers that start at zero
    def get_pushover_priority(self,val=None):
        LOGGER.info('val={}'.format(val))
        if val is None:
            val = int(self.get_priority())
        else:
            val = int(val)
        val -= 2
        LOGGER.info('val={}'.format(val))
        return val

    # Returns pushover sound name from our index number
    def get_pushover_sound(self,val=None):
        LOGGER.info('val={}'.format(val))
        if val is None:
            val = int(self.get_sound())
        else:
            val = int(val)
        rval = 0
        for item in self.sounds_list:
            if item[2] == val:
                rval = item[0]
        LOGGER.info('{}'.format(rval))
        return rval

    # Returns pushover sound name by name, return default if not found
    def get_pushover_sound_by_name(self,name):
        LOGGER.info('name={}'.format(name))
        rval = False
        for item in self.sounds_list:
            if name == item[0]:
                rval = name
        if rval is False:
            LOGGER.error("No sound name found matching '{}".format(name))
            rval = 'pushover'
        LOGGER.info('{}'.format(rval))
        return rval

    def cmd_set_device(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_device(val)

    def cmd_set_priority(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_priority(val)

    def cmd_set_format(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_format(val)

    def cmd_set_retry(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_retry(val)

    def cmd_set_expire(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_expire(val)

    def cmd_set_sound(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_sound(val)

    def cmd_set_message(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_message(val)

    def cmd_set_sys_short(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_sys_short(val)

    def cmd_send_message(self,command):
        LOGGER.info('')
        # Default create message params
        md = self.controller.get_current_message()
        # md will contain title and message
        return self.do_send({ 'title': md['title'], 'message': md['message']})

    def cmd_send_sys_short(self,command):
        LOGGER.info('')
        return self.do_send({ 'message': self.controller.get_sys_short()})

    def cmd_send_my_message(self,command):
        LOGGER.info('')
        # Default create message params
        md = self.controller.get_message_by_id(self.get_message())
        # md will contain title and message
        return self.do_send({ 'title': md['title'], 'message': md['message']})

    def cmd_send_my_sys_short(self,command):
        LOGGER.info('')
        return self.do_send({ 'message': self.get_sys_short})

    # command={'address': 'po_dev', 'cmd': 'GV10', 'query': {'Device.uom25': '2', 'Priority.uom25': '2', 'Format.uom25': '0', 
    #          'Sound.uom25': '0', 'Retry.uom56': '30', 'Expire.uom56': '10800', 'Content.uom145': 'Temp: 54.6°F\nHumidity: 81%'}}
    def cmd_send_sys_short_with_params(self,command):
        LOGGER.debug(f'command={command}')
        query = command.get('query')
        self.set_device(query.get('Device.uom25'))
        self.set_priority(query.get('Priority.uom25'))
        self.set_format(query.get('Format.uom25'))
        self.set_sound(query.get('Sound.uom25'))
        self.set_retry(query.get('Retry.uom56'))
        self.set_expire(query.get('Expire.uom56'))
        #Can't do this since it changes the current sys short message which has no driver?
        #self.set_sys_short(query.get('Content.uom145'))
        msg = query.get('Content.uom145')
        if msg is None:
            LOGGER.warning(f"No sys short message passed in?")
            msg = "No Message Defined"
        return self.do_send({ 'message': msg})

    def do_send(self,params):
        LOGGER.info('params={}'.format(params))
        # These may all eventually be passed in or pulled from drivers.
        if not 'message' in params:
            params['message'] = "NOT_SPECIFIED"
        if 'device' in params:
            if is_int(params['device']):
                # It's an index, so getthe name
                params['device'] = self.get_device_name_by_index(params['device'])
                if params['device'] is False:
                    # Bad param, can't send
                    return
        else:
            params['device'] = self.get_device_name_by_index()
        if 'priority' in params:
            params['priority'] = self.get_pushover_priority(params['priority'])
        else:
            params['priority'] = self.get_pushover_priority()
        if 'sound' in params:
            if is_int(params['sound']):
                params['sound'] = self.get_pushover_sound(params['sound'])
            else:
                params['sound'] = self.get_pushover_sound_by_name(params['sound'])
        else:
            params['sound'] = self.get_pushover_sound()
        if params['priority'] == 2:
            if not 'retry' in params:
                params['retry'] = self.get_retry()
            if not 'expire' in params:
                params['expire'] = self.get_expire()
        if 'format' in params:
            if params['format'] == 1:
                params['html'] = 1
            elif params['format'] == 2:
                params['monospace'] = 1
            del params['format']
        elif not ('html' in params or 'monospace' in params):
            p = self.get_format()
            if p == 1:
                params['html'] = 1
            elif p == 2:
                params['monospace'] = 1
        params['user'] = self.user_key
        params['token'] = self.app_key
        #timestamp=None
        #url=None
        #url_title=None
        #callback=None
        #sound=None
        #
        # Send the message in a thread with retries
        #
        # Just keep serving until we are killed
        self.thread = Thread(target=self.post,args=(params,))
        self.thread.daemon = True
        LOGGER.debug('Starting Thread')
        st = self.thread.start()
        LOGGER.debug('Thread start st={}'.format(st))
        # Always have to return true case we don't know..
        return True

    def post(self,params):
        sent = False
        retry = True
        cnt  = 0
        # Clear error if there was one
        self.set_error(ERROR_NONE)
        LOGGER.debug('params={}'.format(params))
        while (not sent and retry and (RETRY_MAX < 0 or cnt < RETRY_MAX)):
            cnt += 1
            LOGGER.debug('try #{}'.format(cnt))
            res = self.session.post("1/messages.json",params)
            if res['status'] is True and res['data']['status'] == 1:
                sent = True
                self.set_error(ERROR_NONE)
            else:
                if 'data' in res:
                    if 'errors' in res['data']:
                        LOGGER.error('From Pushover: {}'.format(res['data']['errors']))
                # No status code or not 4xx code is
                LOGGER.debug('res={}'.format(res))
                if 'code' in res and (res['code'] is not None and (res['code'] >= 400 or res['code'] < 500)):
                    LOGGER.warning('Previous error can not be fixed, will not retry')
                    retry = False
                else:
                    LOGGER.warning('Previous error is retryable...')
            if (not sent):
                self.set_error(ERROR_MESSAGE_SEND)
                if (retry and (RETRY_MAX > 0 and cnt == RETRY_MAX)):
                    LOGGER.error('Giving up after {} tries'.format(cnt))
                    retry = False
            if (not sent and retry):
                time.sleep(RETRY_WAIT)
        #LOGGER.info('is_sent={} id={} sent_at={}'.format(message.is_sent, message.id, str(message.sent_at)))
        return sent

    def get(self,url,params={}):
        params['token'] = self.app_key
        sent = False
        retry = True
        cnt  = 0
        while (not sent and retry and (RETRY_MAX < 0 or cnt < RETRY_MAX)):
            cnt += 1
            LOGGER.warning('try {} #{}'.format(url,cnt))
            res = self.session.get(url,params)
            LOGGER.info('got {}'.format(res))
            if res['status'] is True and res['data']['status'] == 1:
                sent = True
                self.set_error(ERROR_NONE)
            else:
                if 'data' in res:
                    if 'errors' in res['data']:
                        LOGGER.error('From Pushover: {}'.format(res['data']['errors']))
                # No status code or not 4xx code is
                LOGGER.debug('res={}'.format(res))
                if 'code' in res and (res['code'] is not None and (res['code'] >= 400 or res['code'] < 500)):
                    LOGGER.warning('Previous error can not be fixed, will not retry')
                    retry = False
                else:
                    LOGGER.warning('Previous error is retryable...')
            if (not sent):
                self.set_error(ERROR_UNKNOWN)
                if (retry and (RETRY_MAX > 0 and cnt == RETRY_MAX)):
                    LOGGER.error('Giving up after {} tries'.format(cnt))
                    retry = False
            if (not sent and retry):
                time.sleep(RETRY_WAIT)
        #LOGGER.info('is_sent={} id={} sent_at={}'.format(message.is_sent, message.id, str(message.sent_at)))
        if 'data' in res:
            return { 'status': sent, 'data': res['data'] }
        else:
            return { 'status': sent, 'data': False }

    def rest_send(self,params):
        LOGGER.debug('params={}'.format(params))
        if 'priority' in params:
            # Our priority's start at 0 pushovers starts at -2... Should have used their numbers...
            # So assume rest calls pass in pushover number, so convert to our number.
            params['priority'] = int(params['priority']) + 2
        return self.do_send(params)

    _init_st = None
    id = 'pushover'
    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 2},
        {'driver': 'ERR', 'value': 0, 'uom': 25},
        {'driver': 'GV1', 'value': 0, 'uom': 25},
        {'driver': 'GV2', 'value': 2, 'uom': 25},
        {'driver': 'GV3', 'value': 0, 'uom': 25},
        {'driver': 'GV4', 'value': 30, 'uom': 56},
        {'driver': 'GV5', 'value': 10800, 'uom': 56},
        {'driver': 'GV6', 'value': 0, 'uom': 25},
        {'driver': 'GV7', 'value': 0, 'uom': 25},
    ]
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SET_DEVICE': cmd_set_device,
                'SET_PRIORITY': cmd_set_priority,
                'SET_FORMAT': cmd_set_format,
                'SET_RETRY': cmd_set_retry,
                'SET_EXPIRE': cmd_set_expire,
                'SET_SOUND': cmd_set_sound,
                'SET_MESSAGE': cmd_set_message,
                'SET_SYS_SHORT': cmd_set_sys_short,
                'SEND': cmd_send_message,
                'SEND_SYS_SHORT': cmd_send_sys_short,
                'SEND_MY_MESSAGE': cmd_send_my_message,
                'SEND_MY_SYS_SHORT': cmd_send_my_sys_short,
                'GV10': cmd_send_sys_short_with_params,
                }
