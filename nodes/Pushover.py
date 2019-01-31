"""
  Notification Pushover Node
"""
import polyinterface

LOGGER = polyinterface.LOGGER

class Pushover(polyinterface.Node):
    """
    """
    def __init__(self, controller, primary, address, name):
        """
        """
        super(Pushover, self).__init__(controller, primary, address, name)

    def start(self):
        """
        """
        self.setDriver('ST', 1)
        pass

    def query(self):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        self.reportDrivers()

    def l_info(self, name, string):
        LOGGER.info("%s:%s: %s" %  (self.id,name,string))

    def l_error(self, name, string):
        LOGGER.error("%s:%s: %s" % (self.id,name,string))

    def l_warning(self, name, string):
        LOGGER.warning("%s:%s: %s" % (self.id,name,string))

    def l_debug(self, name, string):
        LOGGER.debug("%s:%s: %s" % (self.id,name,string))

    def set_user(self,val):
        self.l_info('set_user',val)
        if val is None:
            val = 0
        val = int(val)
        self.l_info('set_user','Set GV1 to {}'.format(val))
        self.setDriver('GV1', val)

    def cmd_set_user(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_user",val)
        self.set_user(val)

    def set_priority(self,val):
        self.l_info('set_priority',val)
        if val is None:
            val = 0
        val = int(val)
        self.l_info('set_priority','Set GV2 to {}'.format(val))
        self.setDriver('GV2', val)

    def cmd_set_priority(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_priority",val)
        self.set_priority(val)

    def cmd_send(self,command):
        self.l_info("cmd_send",'')

    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 2},
        {'driver': 'GV1', 'value': 0, 'uom': 25},
        {'driver': 'GV2', 'value': 0, 'uom': 25}
    ]
    id = 'pushover'
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SET_USER': cmd_set_user,
                'SET_PRIORITY': cmd_set_priority,
                'SEND': cmd_send
                }
