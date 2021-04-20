"""
  Notification Pushover Node

  TODO:
    - Make sure pushover name is get_valid_node_name, and Length
    - Clean out profile directory?
    - Make list of sounds
    - Allow groups of devices in configuration
"""
from threading import Thread,Event
import time
import polyinterface
import logging
from node_funcs import make_file_dir,is_int

LOGGER = polyinterface.LOGGER

ERROR_NONE       = 0
ERROR_UNKNOWN    = 1
ERROR_APP_AUTH   = 2
ERROR_USER_AUTH  = 3
ERROR_MESSAGE_CREATE = 4
ERROR_MESSAGE_SEND   = 5

REM_PREFIX = "REMOVED-"

class Pushover(polyinterface.Node):
    """
    """
    def __init__(self, controller, primary, address, name, session, info):
        """
        """
        # Need these for l_debug
        self.name     = name
        self.address  = address
        self.session  = session
        self.info     = info
        self.iname    = info['name']
        self.oid      = self.id
        self.id       = 'pushover_' + self.iname
        self.app_key  = self.info['app_key']
        self.user_key = self.info['user_key']
        self.l_debug('init','{} {}'.format(address,name))
        super(Pushover, self).__init__(controller, primary, address, name)

    def start(self):
        """
        """
        self.l_info('start','')
        # We track our driver values because we need the value before it's been pushed.
        self.driver = {}
        self.set_device(self.get_device())
        self.set_priority(self.get_priority())
        self.set_format(self.get_format())
        self.set_retry(self.get_retry())
        self.set_expire(self.get_expire())
        self.customData = self.controller.polyConfig.get('customData', {})
        self.devices_list = self.customData.get('devices_list',[])
        self.l_info('start',"devices_list={}".format(self.devices_list))
        self.l_debug('start','Authorizing pushover app {}'.format(self.app_key))
        vstat = self.validate()
        if vstat['status'] is False:
            self.authorized = False
        else:
            self.authorized = True if vstat['status'] == 1 else False
        self.l_info('start',"Authorized={}".format(self.authorized))
        if self.authorized:
            self.l_info('start',"got devices={}".format(vstat['data']['devices']))
            self.build_device_list(vstat['data']['devices'])
            self.controller.saveCustomData({'devices_list': self.devices_list})
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
        self.l_debug('validate','got: {}'.format(res))
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
        self.l_info('build_device_list',"devices_list={}".format(self.devices_list))


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
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        self.reportDrivers()

    def setDriver(self,driver,value):
        self.driver[driver] = value
        super(Pushover, self).setDriver(driver,value)

    def getDriver(self,driver):
        if driver in self.driver:
            return self.driver[driver]
        else:
            return super(Pushover, self).getDriver(driver)

    def write_profile(self,nls):
        pfx = 'write_profile'
        self.l_info(pfx,'')
        #
        # nodedefs
        #
        # Open the template, and read into a string for formatting.
        template_f = 'template/nodedef/pushover.xml'
        self.l_info(pfx,"Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Open the output nodedefs file
        output_f   = 'profile/nodedef/{0}.xml'.format(self.iname)
        make_file_dir(output_f)
        # Write the nodedef file with our info
        self.l_info(pfx,"Writing {}".format(output_f))
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

        #
        # editor
        #
        # Open the template, and read into a string for formatting.
        template_f = 'template/editor/pushover.xml'
        self.l_info(pfx,"Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Write the editors file with our info
        output_f   = 'profile/editor/{0}.xml'.format(self.iname)
        make_file_dir(output_f)
        self.l_info(pfx,"Writing {}".format(output_f))
        editor_h = open(output_f, "w")
        # TODO: We could create a better subst with - and , but do we need to?
        editor_h.write(data.format(self.iname,",".join(subst)))
        editor_h.close()

    def l_info(self, name, string):
        LOGGER.info("%s:%s:%s: %s" %  (self.id,self.name,name,string))

    def l_error(self, name, string, exc_info=False):
        LOGGER.error("%s:%s:%s: %s" % (self.id,self.name,name,string), exc_info=exc_info)

    def l_warning(self, name, string, exc_info=False):
        LOGGER.warning("%s:%s:%s: %s" % (self.id,self.name,name,string), exc_info=exc_info)

    def l_debug(self, name, string, exc_info=False):
        LOGGER.debug("%s:%s:%s: %s" % (self.id,self.name,name,string), exc_info=exc_info)

    def set_device(self,val):
        self.l_info('set_device',val)
        if val is None:
            val = 0
        val = int(val)
        self.l_info('set_device','Set GV1 to {}'.format(val))
        self.setDriver('GV1', val)

    def get_device(self):
        cval = self.getDriver('GV1')
        if cval is None:
            return 0
        return int(cval)

    def get_device_name_by_index(self,dev=None):
        if dev is None:
            dev = self.get_device()
        self.l_debug('get_device_name_by_index','dev={}'.format(dev))
        dev_name = None
        try:
            # 0 is all, so return none, otherwise look up the name
            if dev > 0:
                dev_name = self.devices_list[dev]
        except:
            self.l_error('get_device_name','Bad device index {}'.format(dev),exc_info=True)
        return dev_name

    def set_st(self,val):
        self.l_info('set_st',val)
        if val is False or val is None:
            val = 0
        elif val is True:
            val = 1
        else:
            val = int(val)
        self.l_info('set_st','Set ST to {}'.format(val))
        self.setDriver('ST', val)

    def set_error(self,val):
        self.l_info('set_error',val)
        if val is False:
            val = 0
        elif val is True:
            val = 1
        self.l_info('set_error','Set ERR to {}'.format(val))
        self.setDriver('ERR', val)
        self.set_st(True if val == 0 else False)

    def set_priority(self,val):
        self.l_info('set_priority',val)
        if val is None:
            val = 0
        val = int(val)
        self.l_info('set_priority','Set GV2 to {}'.format(val))
        self.setDriver('GV2', val)

    def get_priority(self):
        cval = self.getDriver('GV2')
        if cval is None:
            return 0
        return int(self.getDriver('GV2'))

    def set_format(self,val):
        self.l_info('set_format',val)
        if val is None:
            val = 0
        val = int(val)
        self.l_info('set_format','Set GV3 to {}'.format(val))
        self.setDriver('GV3', val)

    def get_format(self):
        cval = self.getDriver('GV3')
        if cval is None:
            return 0
        return int(self.getDriver('GV3'))

    def set_retry(self,val):
        self.l_info('set_retry',val)
        if val is None:
            val = 30
        val = int(val)
        self.l_info('set_retry','Set GV4 to {}'.format(val))
        self.setDriver('GV4', val)

    def get_retry(self):
        cval = self.getDriver('GV4')
        if cval is None:
            return 30
        return int(self.getDriver('GV4'))

    def set_expire(self,val):
        self.l_info('set_expire',val)
        if val is None:
            val = 10800
        val = int(val)
        self.l_info('set_expire','Set GV5 to {}'.format(val))
        self.setDriver('GV5', val)

    def get_expire(self):
        cval = self.getDriver('GV5')
        if cval is None:
            return 10800
        return int(self.getDriver('GV5'))

    # Returns pushover priority numbers which start at -2 and our priority nubmers that start at zero
    def get_pushover_priority(self,val=None):
        self.l_info("get_pushover_priority",'val={}'.format(val))
        if val is None:
            val = int(self.get_priority())
        else:
            val = int(val)
        val -= 2
        self.l_info("get_pushover_priority",'val={}'.format(val))
        return val

    def cmd_set_device(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_device",val)
        self.set_device(val)

    def cmd_set_priority(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_priority",val)
        self.set_priority(val)

    def cmd_set_format(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_format",val)
        self.set_format(val)

    def cmd_set_retry(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_retry",val)
        self.set_retry(val)

    def cmd_set_expire(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_expire",val)
        self.set_expire(val)

    def cmd_send(self,command):
        self.l_info("cmd_send",'')
        # Default create message params
        md = self.parent.get_current_message()
        # md will contain title and message
        return self.do_send({ 'title': md['title'], 'message': md['message']})

    def do_send(self,params):
        self.l_info('do_send','params={}'.format(params))
        # These may all eventually be passed in or pulled from drivers.
        if not 'message' in params:
            params['message'] = "NOT_SPECIFIED"
        if 'device' in params:
            if is_int(params['device']):
                # It's an index, so getthe name
                params['device'] = self.get_device_name_by_index(params['device'])
        else:
            params['device'] = self.get_device_name_by_index()
        if 'priority' in params:
            params['priority'] = self.get_pushover_priority(params['priority'])
        else:
            params['priority'] = self.get_pushover_priority()
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
        self.l_debug('cmd_send','Starting Thread')
        st = self.thread.start()
        self.l_debug('cmd_send','Thread start st={}'.format(st))
        # Always have to return true case we don't know..
        return True

    def post(self,params):
        sent = False
        retry = True
        cnt  = 0
        max  = 10
        retry_wait = 5
        while (not sent and retry and cnt < max):
            cnt += 1
            self.l_debug('post','send try #{}'.format(cnt))
            res = self.session.post("1/messages.json",params)
            if res['status'] is True and res['data']['status'] == 1:
                sent = True
                self.set_error(ERROR_NONE)
            else:
                if 'data' in res:
                    if 'errors' in res['data']:
                        self.l_error('post','From Pushover: {}'.format(res['data']['errors']))
                # No status code or not 4xx code is
                self.l_debug('post','res={}'.format(res))
                if 'code' in res and (res['code'] is not None and (res['code'] >= 400 or res['code'] < 500)):
                    self.l_warning('post','Previous error can not be fixed, will not retry')
                    retry = False 
                else:
                    self.l_warning('post','Previous error is retryable...')
            self.set_error(ERROR_MESSAGE_SEND)
            if (not sent and retry):
                time.sleep(retry_wait)
        if (cnt > max):
            self.l_error('post','Gave up after {} tries'.format(cnt))
        #self.l_info('cmd_send','is_sent={} id={} sent_at={}'.format(message.is_sent, message.id, str(message.sent_at)))
        return sent

    def rest_send(self,params):
        self.l_debug('rest_handler','params={}'.format(params))
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
        {'driver': 'GV5', 'value': 10800, 'uom': 56}
    ]
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SET_DEVICE': cmd_set_device,
                'SET_PRIORITY': cmd_set_priority,
                'SET_FORMAT': cmd_set_format,
                'SET_RETRY': cmd_set_retry,
                'SET_EXPIRE': cmd_set_expire,
                'SEND': cmd_send
                }
