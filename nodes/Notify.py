"""
  Notification Notify Node

  TODO:
    - Make sure Notify name is get_valid_node_name, and Length
    - Clean out profile directory?

"""
import polyinterface
import logging

LOGGER = polyinterface.LOGGER


class Notify(polyinterface.Node):
    """
    """
    def __init__(self, controller, primary, address, name, info):
        """
        """
        #self.l_debug('init','{} {}'.format(self.address,self.name))
        self.info     = info
        self.iname    = info['name']
        super(Notify, self).__init__(controller, primary, address, name)

    def start(self):
        self.l_info('start','')
        # We track our driver values because we need the value before it's been pushed.
        self.driver = {}

    def query(self):
        self.reportDrivers()

    """
    This lets the controller know when we are initialized, or if we had
    an error.  Since it can't call our write_profile until we have initilized
      None  = Still initializing
      False = Failed
      True  = All Good
    """
    def init_st(self):
        return True; #self._init_st

    # We don't need to do anything yet...
    def write_profile(self,nls):
        return True

    def setDriver(self,driver,value):
        self.driver[driver] = value
        super(Notify, self).setDriver(driver,value)

    def getDriver(self,driver):
        if driver in self.driver:
            return self.driver[driver]
        else:
            return super(Notify, self).getDriver(driver)

    def l_info(self, name, string):
        LOGGER.info("%s:%s:%s: %s" %  (self.id,self.name,name,string))

    def l_error(self, name, string):
        LOGGER.error("%s:%s:%s: %s" % (self.id,self.name,name,string))

    def l_warning(self, name, string):
        LOGGER.warning("%s:%s:%s: %s" % (self.id,self.name,name,string))

    def l_debug(self, name, string, execInfo=False):
        LOGGER.debug("%s:%s:%s: %s" % (self.id,self.name,name,string))

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

    def get_Notify_priority(self):
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
        # md will contain title and message
        return self.do_send(md)

    def do_send(self,params):
        self.l_info('cmd_send','params={}'.format(params))
        # These may all eventually be passed in or pulled from drivers.
        if 'message' in params:
            message=params['message']
        else:
            message="NOT_SPECIFIED"
        if 'title' in params:
            title=params['title']
        else:
            title=None
        html=False
        timestamp=None
        url=None
        url_title=None
        device=self.get_device_name()
        priority=self.get_Notify_priority()
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
            self.set_error(ERROR_MESSAGE_CREATE)
            return False
        #
        # Send the message
        #
        try:
            message.send()
        except Exception as err:
            self.l_error('cmd_send','send_message failed: {}'.format(err))
            self.set_error(ERROR_MESSAGE_SEND)
            return False
        self.l_info('cmd_send','is_sent={} id={} sent_at={}'.format(message.is_sent, message.id, str(message.sent_at)))
        return message.is_sent

    def rest_send(self,params):
        self.l_debug('rest_handler','params={}'.format(params))
        return self.do_send(params)

    _init_st = None
    id = 'notify'
    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 2},
        {'driver': 'ERR', 'value': 0, 'uom': 25},
        {'driver': 'GV1', 'value': 0, 'uom': 25},
        {'driver': 'GV2', 'value': 0, 'uom': 25}
        {'driver': 'GV3', 'value': 0, 'uom': 25}
        {'driver': 'GV4', 'value': 0, 'uom': 25}
        {'driver': 'GV5', 'value': 0, 'uom': 25}
    ]
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SET_DEVICE': cmd_set_device,
                'SET_PRIORITY': cmd_set_priority,
                'SEND': cmd_send,
                'DON': cmd_send,
                'DOF': cmd_send,
                }
