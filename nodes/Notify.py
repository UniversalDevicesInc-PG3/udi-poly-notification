"""
  Notification Notify Node

  TODO:
    - Make sure Notify name is get_valid_node_name, and Length
    - Clean out profile directory?

"""
import polyinterface
import logging
from node_funcs import *

LOGGER = polyinterface.LOGGER

class Notify(polyinterface.Node):
    """
    """
    def __init__(self, controller, primary, address, name, info):
        """
        """
        #self.l_debug('init','{} {}'.format(self.address,self.name))
        self._init_st = None;
        self.oid      = self.id
        self.info     = info
        self.iname    = info['name']
        self.iid      = info['id']
        self.service_node_name = self.info['service_node_name']
        # TODO: pushoer_ should be passed in by looking up the server_node_name...
        self.service_node_type = 'pushover'
        self.id       = self.service_node_type + '_' + self.service_node_name + '_notify'
        super(Notify, self).__init__(controller, primary, address, name)

    def start(self):
        self.l_info('start','')
        # We track our driver values because we need the value before it's been pushed.
        self.driver = {}
        self.set_message_on(self.get_message_on())
        self.set_message_off(self.get_message_off())
        self.set_device(self.get_device())
        self.set_priority(self.get_priority())
        self.set_format(self.get_format())
        # Make sure we know who our service node is
        self.service_node = self.controller.get_service_node(self.service_node_name)
        if self.service_node is False:
            self.l_error('start',"No service node '{}' name exists".format(self.service_node_name))
            self._init_st = False
            # TODO: Set ERROR Flag
        else:
            self.set_node(self.service_node['index'])
            self._init_st = True

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
        return self._init_st;

    def write_profile(self,nls):
        pfx = 'write_profile'
        self.l_info(pfx,"Appending to nls")
        # TODO: Used passed
        nls.write("ND-{0}-NAME = {1}\n".format(self.id,self.name))
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

    def set_message_on(self,val):
        self.l_info('set_message_on',val)
        dv = 'GV1'
        self.l_info('set_message_on','Set {} to {}'.format(dv,int(val)))
        self.setDriver(dv, val)

    def get_message_on(self):
        cval = self.getDriver('GV1')
        if cval is None:
            return 0
        return int(cval)

    def set_message_off(self,val):
        self.l_info('set_message_off',val)
        dv = 'GV2'
        self.l_info('set_message_on','Set {} to {}'.format(dv,int(val)))
        self.setDriver(dv, val)

    def get_message_off(self):
        cval = self.getDriver('GV2')
        if cval is None:
            return 0
        return int(cval)

    def set_node(self,val):
        self.l_info('set_node',val)
        dv = 'GV3'
        self.l_info('set_node','Set {} to {}'.format(dv,val))
        self.setDriver(dv, val)

    def set_error(self,val):
        self.l_info('set_error',val)
        if val is False:
            val = 0
        elif val is True:
            val = 1
        self.l_info('set_error','Set ERR to {}'.format(val))
        self.setDriver('ERR', val)
        self.set_st(True if val == 0 else False)

    def set_device(self,val):
        dv = 'GV4'
        self.l_info('set_device',val)
        if val is None:
            val = 0
        val = int(val)
        self.l_info('set_device','Set {} to {}'.format(dv,val))
        self.setDriver(dv, val)

    def get_device(self):
        cval = self.getDriver('GV4')
        if cval is None:
            return 0
        return int(cval)

    def set_priority(self,val):
        dv = 'GV5'
        self.l_info('set_priority',val)
        if val is None:
            val = 0
        val = int(val)
        self.l_info('set_priority','Set {} to {}'.format(dv,val))
        self.setDriver(dv, val)

    def get_priority(self):
        cval = self.getDriver('GV5')
        if cval is None:
            return 0
        return int(cval)

    def set_format(self,val):
        dv = 'GV6'
        self.l_info('set_format',val)
        if val is None:
            val = 0
        val = int(val)
        self.l_info('set_format','Set {} to {}'.format(dv,val))
        self.setDriver(dv, val)

    def get_format(self):
        cval = self.getDriver('GV6')
        if cval is None:
            return 0
        return int(cval)

    def cmd_set_message_on(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_message_on",val)
        self.set_message_on(val)

    def cmd_set_message_off(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_message_off",val)
        self.set_message_off(val)

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

    def cmd_send_on(self,command):
        self.l_info("cmd_send_on",''.format(command))
        self.send_msg(self.get_message_on())

    def cmd_send_off(self,command):
        self.l_info("cmd_send_off",''.format(command))
        self.send_msg(self.get_message_off())

    def send_msg(self,mi):
        msg = get_messages()[mi]
        # md will contain title and message
        self.l_info("cmd_send_on","msg={}".format(msg))
        st = self.service_node['node'].do_send(
            {
                #'title': ,
                'message': self.iname+' '+msg,
                'device': self.get_device(),
                'priority': self.get_priority(),
                'format': self.get_format(),
            }
        )
        self.set_st(st)


    _init_st = None
    id = 'notify'
    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 2},
        {'driver': 'ERR', 'value': 0, 'uom': 25},
        {'driver': 'GV1', 'value': 1, 'uom': 25},
        {'driver': 'GV2', 'value': 2, 'uom': 25},
        {'driver': 'GV3', 'value': 0, 'uom': 25},
        {'driver': 'GV4', 'value': 0, 'uom': 25},
        {'driver': 'GV5', 'value': 2, 'uom': 25},
        {'driver': 'GV6', 'value': 0, 'uom': 25}
    ]
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SET_MESSAGE_DON': cmd_set_message_on,
                'SET_MESSAGE_DOF': cmd_set_message_off,
                'SET_DEVICE': cmd_set_device,
                'SET_PRIORITY': cmd_set_priority,
                'SET_FORMAT': cmd_set_format,
                'DON': cmd_send_on,
                'DOF': cmd_send_off,
                }
