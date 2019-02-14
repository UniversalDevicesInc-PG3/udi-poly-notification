"""
  Notification Pushover Node
"""
import polyinterface
import logging
from chump import Application
from node_funcs import make_file_dir

LOGGER = polyinterface.LOGGER

xref_err = {
    'None':           0,
    'Illegal Value':  1,
    'App Auth':       2,
    'User Auth':      3,
    'Create Message': 4,
    'Send Message':   5,
    'Another Error':  6,
}

xref_devices = [
    'All',
    'JimsPhone',
    'AudreysPhone',
    'Nexus7-2013',
    'PixelC',
]

driversMap = [
    {'driver': 'ST',  'value': 0, 'uom': 2},
    {'driver': 'ERR', 'value': 0, 'uom': 25},
    {'driver': 'GV1', 'value': 0, 'uom': 25},
    {'driver': 'GV2', 'value': 2, 'uom': 25}
]

class Pushover(polyinterface.Node):
    """
    """
    def __init__(self, controller, primary, address, name, info):
        """
        """
        self.info     = info
        self.iname    = info['name']
        self.id       = 'pushover_' + self.iname
        self.app_key  = self.info['app_key']
        self.user_key = self.info['user_key']
        self.drivers = self._convertDrivers(driversMap)
        super(Pushover, self).__init__(controller, primary, address, name)

    def start(self):
        """
        """
        # We track our driver values because we need the value before it's been pushed.
        self.driver = {}
        self.set_device(self.get_device())
        self.set_priority(self.get_priority())
        self.l_debug('start','Authorizing pushover app {}'.format(self.app_key))
        self.app = Application(self.app_key)
        logger = logging.getLogger('chump')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(LOGGER.handlers[0])
        self.l_info('start',"Authorized={}".format(self.app.is_authenticated))
        if self.app.is_authenticated:
            self.l_debug('start','Authorizing pushover user {}'.format(self.user_key))
            self.user = self.app.get_user(self.user_key)
            self.l_info('start',"user authenticated={} devices={}".format(self.user.is_authenticated, self.user.devices))
            if self.user.is_authenticated:
                # TODO: Save devices in config, and use to build Profile
                # TODO: Remember devices or always use index
                # This will alwasy be an array to the current device
                self.devices = ["all"]
                for device in self.user.devices:
                    self.devices.append(device)
                self.l_info('start',"self.devices={}".format(self.devices))
                self.set_error('None')
                self._init_st = True
            else:
                self.set_error('User Auth')
                self._init_st = False
        else:
            self.set_error('App Auth')
            self._init_st = False

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
        subset_str = '0-'+len(self.devices)
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
        nls.write("ND-{0}-NAME = {1}\n".format(self.iname,self.name))
        cnt=0
        for name in self.devices:
            nls.write("POD_{}-{} = {}\n".format(self.iname,cnt,name))
            cnt += 1

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

    def get_device_name(self):
        dev = self.get_device()
        self.l_debug('get_device_name','dev={}'.format(dev))
        if dev == 0:
            # This means all to chump
            return None
        return xref_devices[dev]

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
        elif val in xref_err:
            val = xref_err[val]
        else:
            self.l_error('set_error','Unknown error "{}"'.format(val))
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

    def get_pushover_priority(self):
        return self.get_priority() - 2

    def cmd_set_device(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_device",val)
        self.set_device(val)

    def cmd_set_priority(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_priority",val)
        self.set_priority(val)

    def cmd_send(self,command):
        self.l_info("cmd_send",'')
        # Default create message params
        md = self.parent.get_current_message()
        message=md['message']
        title=md['title']
        return self.do_send(title=title, message=message)

    def do_send(self,message,title=None):
        # These may all eventually be passed in or pulled from drivers.
        html=False
        timestamp=None
        url=None
        url_title=None
        device=self.get_device_name()
        priority=self.get_pushover_priority()
        callback=None
        retry=30
        expire=86400
        sound=None
        #
        # Build the message
        #
        try:
            self.l_info('cmd_send','create_message: message={} device={} priority={}'.format(message,device,priority))
            message = self.user.create_message(
                message=message,
                device=device,
                priority=priority,
                title=title,
                html=html,
                timestamp=timestamp,
                url=url,
                url_title=url_title,
                callback=callback,
                retry=retry,
                expire=expire,
                sound=sound,
                )
        except Exception as err:
            self.l_error('cmd_send','create_message failed: {0}'.format(err))
            self.set_error('Create Message')
            return False
        #
        # Send the message
        #
        try:
            message.send()
        except Exception as err:
            self.l_error('cmd_send','send_message failed: {}'.format(err))
            self.set_error('Send Message')
            return False
        self.l_info('cmd_send','is_sent={} id={} sent_at={}'.format(message.is_sent, message.id, str(message.sent_at)))
        return message.is_sent

    def rest_send(self,title,body,params):
        self.l_debug('rest_handler','params={}'.format(params))
        return self.do_send(body,title)

    _init_st = None
    id = 'pushover'
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SET_DEVICE': cmd_set_device,
                'SET_PRIORITY': cmd_set_priority,
                'SEND': cmd_send
                }
