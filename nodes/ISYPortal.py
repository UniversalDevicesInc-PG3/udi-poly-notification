"""
  Notification ISYPortal Node

  TODO:
    - 
"""
from email import message
from socket import MsgFlag
from udi_interface import Node,LOGGER
from threading import Thread
import time
from node_funcs import make_file_dir,is_int
from constants import SOUNDS_LIST

ERROR_NONE       = 0
ERROR_UNKNOWN    = 1
ERROR_APP_AUTH   = 2
ERROR_USER_AUTH  = 3
ERROR_MESSAGE_CREATE = 4
ERROR_MESSAGE_SEND   = 5
ERROR_PARAM          = 6

ALL_DEVICES  = 'all devices'
REM_PREFIX   = "REMOVED-"
DEVICES_LIST = 'devices_list_isyp'
GROUP_LIST  = 'groups_list_isyp'

# How many tries to get or post, -1 is forever
RETRY_MAX = -1
# How long to wait between tries, in seconds
RETRY_WAIT = 5

class ISYPortal(Node):
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
        self.id       = 'isyportal_' + self.iname
        if 'api_key' in self.info:
            self.api_key  = self.info['api_key']
        else:
            self.api_key = None
        self._sys_short = None
        LOGGER.debug('{} {}'.format(address,name))
        controller.poly.subscribe(controller.poly.START,                  self.handler_start, address)
        super(ISYPortal, self).__init__(controller.poly, primary, address, name)

    def handler_start(self):
        """
        """
        LOGGER.info('')
        # We track our driver values because we need the value before it's been pushed.
        self.driver = {}
        self.set_device(self.get_device())
        # Old deprecated devices list
        self.devices_list = self.controller.get_data(DEVICES_LIST,[])
        # New devices list is just groups
        self.groups_list  = self.controller.get_data(GROUP_LIST,[])
        self.sounds_list  = SOUNDS_LIST
        self.devices_and_groups = list()
        LOGGER.info("{}={}".format(DEVICES_LIST,self.devices_list))
        LOGGER.info("{}={}".format(GROUP_LIST,self.groups_list))
        LOGGER.debug('Authorizing ISYPortal api {}'.format(self.api_key))
        vstat = self.validate()
        if vstat['status'] is False:
            self.authorized = False
        else:
            self.authorized = True if vstat['status'] == 1 else False
        LOGGER.info("Authorized={}".format(self.authorized))
        if self.authorized:
            LOGGER.info("got isyportal devices={}".format(vstat['data']['data']))
            self.set_groups()
            self.set_error(ERROR_NONE)
            self._init_st = True
        else:
            self.set_error(ERROR_APP_AUTH)
            self._init_st = False
        
    def api_get(self,command):
        res = self.session.get(f"api/push/{command}",api_key=self.api_key)
        LOGGER.debug('got: {}'.format(res))
        return res

    def api_post(self,command,params):
        res = self.session.post(f"api/push/{command}",params,api_key=self.api_key,content="urlencode")
        LOGGER.debug('got: {}'.format(res))
        return res

    def validate(self):
        return self.api_get("tokens")

    def get_groups(self):
        data = self.api_get("groups")
        LOGGER.debug("got groups: {}".format(data))
        return data

    def set_groups(self):
        if GROUP_LIST in self.controller.Data:
            self.groups_list = self.controller.Data[GROUP_LIST]
        data = self.get_groups()
        LOGGER.info("got UDMobile groups={}".format(data['data']['data']))
        self.build_group_list(data['data']['data'])
        self.controller.Data[GROUP_LIST] = self.groups_list
        # Build the devices and groups list
        for item in self.devices_list:
            self.devices_and_groups.append({'type': 'device', 'id': item, 'name': item})
        for item in self.groups_list:
            self.devices_and_groups.append({'type': 'group', 'id': item['id'], 'name': item['name']})

    def group_id2name(self,id):
        for item in self.groups_list:
            if item['id'] == id:
                return item['name']
        return None

    def build_group_list(self,vlist):
        # Add new items to the group list
        dlist = list()
        # Make sure default is the first in the list
        # IF we have a device list (legacy) then it will already have the default
        if len(self.devices_list) == 0 and len(self.groups_list) == 0:
            self.groups_list.append({'id': '_default_', 'name': 'default'})
        for item in vlist:
            LOGGER.debug('group={}'.format(item))
            dlist.append(item['id'])
            # If it's not in the saved list, append it
            if self.group_id2name(item['id']) is None:
                self.groups_list.append({'id': item['id'], 'name': item['name']})
        # Make sure items are in the passed in list, otherwise prefix it in groups_list
        groups_list = list()
        for item in self.groups_list:
            if item['id'] == '_default_':
                next
            # Add removed prefix to items no longer in the list.
            if not item['name'].startswith(REM_PREFIX) and dlist.count(item['name']) == 0:
                groups_list.append({'id': item['id'], 'name': REM_PREFIX + item['name']})
            # Get rid of removed prefix if the group is back
            elif item['name'].startswith(REM_PREFIX):
                groups_list.append({'id': item['id'], 'name': item['name'][len(REM_PREFIX):] })
            else:
                groups_list.append(item)
        self.groups_list = groups_list
        LOGGER.info("groups_list={}".format(self.groups_list))

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
        super(ISYPortal, self).setDriver(driver,value)

    def getDriver(self,driver):
        if driver in self.driver:
            return self.driver[driver]
        else:
            return super(ISYPortal, self).getDriver(driver)

    def config_info_rest(self):
        if self.controller.rest is None:
            listen_url = None
        else:
            listen_url = self.controller.rest.listen_url
        str = '<li>curl -d \'{{"node":"{0}", "message":"The Message", "subject":"The Subject" -H "Content-Type: application/json"}}\' -X POST {1}/send'.format(self.address,listen_url)
        return str

    def config_info_nr(self):
        if self.controller.rest is None:
            rest_ip = "None"
            rest_port = "None"
        else:
            rest_ip = self.controller.rest.ip
            rest_port = self.controller.rest.listen_port
        info = [
            '<h4>Example Network Resource settings for ISYPortal</h4><ul><li>http<li>POST<li>Host:{0}<li>Port:{1}<li>Path: /send?node={2}&Subject=My+Subject&device=1&sound=2<li>Encode URL: not checked<li>Timeout: 5000<li>Mode: Raw Text</ul>'.format(rest_ip,rest_port,self.address),
            '<p>The parms in the Path can be any of the below, if the param is not passed then the default from the ISYPortal node will be used'
            '<table>',
            '<tr><th>Name<th>Value<th>Description',
        ]
        i = 0
        pt = ""
        for item in self.devices_and_groups:
            if item['type'] == pt:
                t = '&nbsp;'
            else:
                t = item['type']
            info.append('<tr><td>{}<td>{}<td>{}'.format(t,i,item['name']))
            pt = item['type']
            i += 1
        t = 'sound'
        i = 0
        for item in self.sounds_list:
            info.append('<tr><td>{}<td>{}<td>{}'.format(t,i,item['name']))
            i += 1
            t = '&nbsp;'
        info = info + [

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
        template_f = 'template/nodedef/isyportal.xml'
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
        out_h.write(data.format(self.id,self.iname,self.controller.sys_notify_editor))
        out_h.close()
        #
        # nls
        #
        nls.write("\n# Entries for ISYPortal {} {}\n".format(self.id,self.name))
        nls.write("ND-{0}-NAME = {1}\n".format(self.id,self.name))
        idx = 0
        subst = []
        for item in self.devices_list:
            nls.write("IPD_{}-{} = {} (deprecated)\n".format(self.iname,idx,item))
            # Don't include REMOVED's in list
            if not item.startswith(REM_PREFIX):
                subst.append(str(idx))
            idx += 1
        for item in self.groups_list:
            nls.write("IPD_{}-{} = {}\n".format(self.iname,idx,item['name']))
            # Don't include REMOVED's in list
            if not item['name'].startswith(REM_PREFIX):
                subst.append(str(idx))
            idx += 1
        # Make sure it has at least one
        if len(subst) == 0:
            subst.append('0')

        sound_subst = []
        idx = 0
        for item in self.sounds_list:
            nls.write("IPS_{}-{} = {}\n".format(self.iname,idx,item['name']))
            # Don't include REMOVED's in list
            if not item['name'].startswith(REM_PREFIX):
                sound_subst.append(str(idx))
            idx += 1
        
        #
        # editor
        #
        # Open the template, and read into a string for formatting.
        template_f = 'template/editor/isyportal.xml'
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

    def get_device_by_index(self,dev=None):
        LOGGER.debug('dev={}'.format(dev))
        if dev is None:
            dev = self.get_device()
            LOGGER.debug('dev={}'.format(dev))
        else:
            if not is_int(dev):
                LOGGER.error('Passed in {} is not an integer'.format(dev))
                return False
            dev = int(dev)
        if dev == 0:
            # 0 is all, so return False, otherwise look up the name
            return False
        if dev < len(self.devices_and_groups):
            return self.devices_and_groups[dev]
        else:
            LOGGER.error('Bad device/group index {} must be < {}'.format(dev,len(self.devices_and_groups)),exc_info=True)
            self.set_error(ERROR_PARAM)
            return False

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

    def get_sound(self):
        cval = self.getDriver('GV2')
        if cval is None:
            return 0
        return int(self.getDriver('GV2'))

    def set_sound(self,val):
        LOGGER.info(val)
        if val is None:
            val = 0
        val = int(val)
        LOGGER.info('Set GV2 to {}'.format(val))
        self.setDriver('GV2', val)

    def get_message(self):
        cval = self.getDriver('GV3')
        if cval is None:
            return 0
        return int(self.getDriver('GV3'))

    def set_message(self,val):
        LOGGER.info(val)
        if val is None:
            val = 0
        val = int(val)
        LOGGER.info('Set GV3 to {}'.format(val))
        self.setDriver('GV3', val)

    def get_sys_short(self):
        return self._sys_short

    def set_sys_short(self,val):
        LOGGER.info(val)
        self._sys_short = val

    # Returns ISYPortal priority numbers which start at -2 and our priority nubmers that start at zero
    def get_ISYPortal_priority(self,val=None):
        LOGGER.info('val={}'.format(val))
        if val is None:
            val = int(self.get_priority())
        else:
            val = int(val)
        val -= 2
        LOGGER.info('val={}'.format(val))
        return val

    # Returns ISYPortal sound name from our index number
    def get_ISYPortal_sound(self,val=None):
        LOGGER.info('val={}'.format(val))
        if val is None:
            val = int(self.get_sound())
        else:
            val = int(val)
        rval = self.sounds_list[val]['fname']
        LOGGER.info('{}'.format(rval))
        return rval

    # Returns ISYPortal sound name by name, return default if not found
    def get_ISYPortal_sound_by_name(self,name):
        LOGGER.info('name={}'.format(name))
        rval = False
        i = 0
        for item in self.sounds_list:
            if name == item['name']:
                rval = item['fname']
            i += 1
        if rval is False:
            LOGGER.error("No sound name found matching '{}".format(name))
            rval = self.sounds_list[0]['fname']
        LOGGER.info('{}'.format(rval))
        return rval

    def cmd_set_device(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_device(val)

    def cmd_set_sound(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_sound(val)

    def cmd_set_message(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_message(val)

    def cmd_set_sys_short(self,command):
        val = command.get('value')
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
        return self.do_send({ 'message': self.get_sys_short()})

    # command={'address': 'po_dev', 'cmd': 'GV10', 'query': {'Device.uom25': '2', 'Priority.uom25': '2', 'Format.uom25': '0', 
    #          'Sound.uom25': '0', 'Retry.uom56': '30', 'Expire.uom56': '10800', 'Content.uom145': 'Temp: 54.6°F\nHumidity: 81%'}}
    def cmd_send_sys_short_with_params(self,command):
        LOGGER.debug(f'command={command}')
        query = command.get('query')
        msg = query.get(f'Content.uom{self.controller.uom_t}')
        if msg is None:
            LOGGER.warning(f"No sys short message passed in?")
            msg = "No Message Defined"
        return self.do_send({ 'message': msg, 'device': query.get('Device.uom25'), 'sound': query.get('Sound.uom25')})

    def do_send(self,params):
        LOGGER.info('params={}'.format(params))
        # These may all eventually be passed in or pulled from drivers.
        if 'message' in params:
            if not 'title' in params and not 'body' in params:
                # Title is first line, body is the rest
                sp = params['message'].split("\n",1)
                params['title'] = sp[0]
                if len(sp) > 1:
                    params['body'] = sp[1]
            elif 'title' in params and 'body' in params:
                LOGGER.error("title, body, and message all passed in?  Not sure what to do with message={message}")
                return False
            elif 'title' in params:
                params['body'] = params['message']
            else:
                params['title'] = params['message']
            del params['message']
        # No body, which is required, so just make it a space :(
        if not 'body' in params:
            params['body'] = ' '
        device = 'default'
        # The device and group is in the same list, so both are accepted
        if 'device' in params:
            device_or_group = params['device']
            del params['device']
        elif 'group' in params:
            device_or_group = params['group']
            del params['group']
        else:
            device_or_group = None
        if device_or_group is not None:
            # It's an index, so get the name
            item = self.get_device_by_index(device_or_group)
            if item is not False:
                if item['type'] == 'device':
                    params['device'] = item['id']
                else:
                    params['group_id'] = item['id']
        sound = None
        if 'sound' in params:
            if is_int(params['sound']):
                sound = self.get_ISYPortal_sound(params['sound'])
            else:
                sound = self.get_ISYPortal_sound_by_name(params['sound'])
            del params['sound']
        else:
            sound = self.get_ISYPortal_sound()
        if not (sound == 'default' or sound is None):
            params['sound'] = sound
        #
        # Send the message in a thread with retries
        #
        # Just keep serving until we are killed
        self.thread = Thread(target=self.send,args=(params,))
        self.thread.daemon = True
        LOGGER.debug('Starting Thread')
        st = self.thread.start()
        LOGGER.debug('Thread start st={}'.format(st))
        # Always have to return true case we don't know..
        return True

    def send(self,params):
        sent = False
        retry = True
        cnt  = 0
        # Clear error if there was one
        self.set_error(ERROR_NONE)
        LOGGER.debug('params={}'.format(params))
        while (not sent and retry and (RETRY_MAX < 0 or cnt < RETRY_MAX)):
            cnt += 1
            LOGGER.info('try #{}'.format(cnt))
            res = self.api_post("notification/send",params)
            failed_count = False
            if 'data' in res and 'failedCount' in res['data']:
                failed_count = res['data']['failedCount'] 
            if res['status'] is True and failed_count == 0:
                sent = True
                self.set_error(ERROR_NONE)
                LOGGER.info(f"Message Sent: {params}")
            else:
                # No status code or not 4xx code is
                LOGGER.debug(f"issue status={res['status']} failed_count={failed_count} res={res}")
                if 'code' in res and (res['code'] is not None and (res['code'] >= 400 or res['code'] < 500)):
                    LOGGER.warning('Previous error can not be fixed, will not retry')
                    retry = False
                else:
                    LOGGER.warning('Previous error is retryable...')
                    if 'data' in res and 'failedCount' in res['data'] and res['data']['failedCount'] > 0:
                        LOGGER.error("From ISYPortal: Failed to send to {res['data']['failedCount']} devices, will send again")
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
            LOGGER.info('try {} #{}'.format(url,cnt))
            res = self.session.get(url,params)
            LOGGER.info('got {}'.format(res))
            if res['status'] is True and res['data']['status'] == 1:
                sent = True
                self.set_error(ERROR_NONE)
            else:
                if 'data' in res:
                    if 'errors' in res['data']:
                        LOGGER.error('From ISYPortal: {}'.format(res['data']['errors']))
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
            # Our priority's start at 0 ISYPortals starts at -2... Should have used their numbers...
            # So assume rest calls pass in ISYPortal number, so convert to our number.
            params['priority'] = int(params['priority']) + 2
        return self.do_send(params)

    _init_st = None
    id = 'isyportal'
    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 2},
        {'driver': 'ERR', 'value': 0, 'uom': 25},
        {'driver': 'GV1', 'value': 0, 'uom': 25},
        {'driver': 'GV2', 'value': 0, 'uom': 25},
        {'driver': 'GV3', 'value': 0, 'uom': 25},
    ]
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SET_DEVICE': cmd_set_device,
                'SET_SOUND': cmd_set_sound,
                'SET_MESSAGE': cmd_set_message,
                'SET_SYS_SHORT': cmd_set_sys_short,
                'SEND': cmd_send_message,
                'SEND_SYS_SHORT': cmd_send_sys_short,
                'SEND_MY_MESSAGE': cmd_send_my_message,
                'SEND_MY_SYS_SHORT': cmd_send_my_sys_short,
                'GV10': cmd_send_sys_short_with_params,
                }
