"""
  Notification Pushover Node

  TODO:
    - Make sure pushover name is get_valid_node_name, and Length
    - Clean out profile directory?
    - Make list of sounds
    - Allow groups of devices in configuration
"""
import polyinterface
import logging
from chump import Application
from node_funcs import make_file_dir

LOGGER = polyinterface.LOGGER

ERROR_NONE       = 0
ERROR_UNKNOWN    = 1
ERROR_APP_AUTH   = 2
ERROR_USER_AUTH  = 3
ERROR_MESSAGE_CREATE = 4
ERROR_MESSAGE_SEND   = 5

REMOVED_DEVICE = "RemovedDevice"

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
        self.customData = self.controller.polyConfig.get('customData', {})
        self.devices = self.customData.get('devices', {})
        self.l_info('start',"devices={}".format(self.devices))
        self.l_debug('start','Authorizing pushover app {}'.format(self.app_key))
        vstat = self.validate()
        if vstat is False:
            self.authorized = False
        else:
            self.authorized = True if vstat['status'] == 1 else False
        self.l_info('start',"Authorized={}".format(self.authorized))
        if self.authorized:
            self.l_info('start',"got devices={}".format(vstat['devices']))
            # TODO: Remember devices or always use index
            self.add_to_hash('all',self.devices)
            for device in vstat['devices']:
                self.add_to_hash(device,self.devices)
            self.l_info('start',"self.devices={}".format(self.devices))
            self.controller.saveCustomData({'devices': self.devices})
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


    def in_saved_list(self,name,list):
        for idx in list:
            if list[idx] == name:
                return idx
        return False

    def add_to_hash(self,name,list):
        # Find max in list
        next = 0
        add = True
        for idx in list:
            if list[idx] == name:
                add = False
            if int(idx) >= next:
                next = int(idx)+1
        if add:
            list[str(next)] = name

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
        # Open the output editors file
        output_f   = 'profile/editor/{0}.xml'.format(self.iname)
        make_file_dir(output_f)
        # Open the template, and read into a string for formatting.
        template_f = 'template/editor/pushover.xml'
        self.l_info(pfx,"Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Write the editors file with our info
        self.l_info(pfx,"Writing {}".format(output_f))
        editor_h = open(output_f, "w")
        # subset_str = '0-5'
        subset_str = '0-'+str(len(self.devices)-1)
        editor_h.write(data.format(self.iname,subset_str))
        editor_h.close()
        #
        # Open the output nodedefs file
        output_f   = 'profile/nodedef/{0}.xml'.format(self.iname)
        make_file_dir(output_f)
        # Open the template, and read into a string for formatting.
        template_f = 'template/nodedef/pushover.xml'
        self.l_info(pfx,"Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Write the nodedef file with our info
        self.l_info(pfx,"Writing {}".format(output_f))
        out_h = open(output_f, "w")
        out_h.write(data.format(self.id,self.iname))
        out_h.close()

        nls.write("\n# Entries for Pushover {} {}\n".format(self.id,self.name))
        nls.write("ND-{0}-NAME = {1}\n".format(self.id,self.name))
        for idx in self.devices:
            nls.write("POD_{}-{} = {}\n".format(self.iname,idx,self.devices[idx]))

    def l_info(self, name, string):
        LOGGER.info("%s:%s:%s: %s" %  (self.id,self.name,name,string))

    def l_error(self, name, string):
        LOGGER.error("%s:%s:%s: %s" % (self.id,self.name,name,string))

    def l_warning(self, name, string):
        LOGGER.warning("%s:%s:%s: %s" % (self.id,self.name,name,string))

    def l_debug(self, name, string, execInfo=False):
        LOGGER.debug("%s:%s:%s: %s" % (self.id,self.name,name,string))

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

    def get_device_name(self,dev=None):
        if dev is None:
            dev = self.get_device()
        self.l_debug('get_device_name','dev={}'.format(dev))
        if dev == 0:
            # This means all to chump
            return None
        return self.devices[str(dev)]

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

    def get_pushover_priority(self,val=None):
        if val is None:
            val = int(self.get_priority())
        return val - 2

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

    def cmd_send(self,command):
        self.l_info("cmd_send",'')
        # Default create message params
        md = self.parent.get_current_message()
        # md will contain title and message
        return self.do_send(md)

    def do_send(self,params):
        self.l_info('cmd_send','params={}'.format(params))
        # These may all eventually be passed in or pulled from drivers.
        if not 'message' in params:
            params['message'] = "NOT_SPECIFIED"
        if 'device' in params:
            params['device'] = self.get_device_name(params['device'])
        else:
            params['device'] = self.get_device_name()
        if 'priority' in params:
            params['priority'] = self.get_pushover_priority(params['priority'])
        else:
            params['priority'] = self.get_pushover_priority()
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
        #retry=30
        #expire=86400
        #sound=None
        #
        # Send the message
        #
        res = self.session.post("1/messages.json",params)
        if res is False:
            sent = False
        else:
            sent = True if res['status'] == 1 else False
        if not sent:
            self.set_error(ERROR_MESSAGE_SEND)
            return False
        #self.l_info('cmd_send','is_sent={} id={} sent_at={}'.format(message.is_sent, message.id, str(message.sent_at)))
        return sent

    def rest_send(self,params):
        self.l_debug('rest_handler','params={}'.format(params))
        return self.do_send(params)

    _init_st = None
    id = 'pushover'
    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 2},
        {'driver': 'ERR', 'value': 0, 'uom': 25},
        {'driver': 'GV1', 'value': 0, 'uom': 25},
        {'driver': 'GV2', 'value': 2, 'uom': 25},
        {'driver': 'GV3', 'value': 0, 'uom': 25}
    ]
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SET_DEVICE': cmd_set_device,
                'SET_PRIORITY': cmd_set_priority,
                'SET_FORMAT': cmd_set_format,
                'SEND': cmd_send
                }
