"""
  Notification Google Assistant Relay Node
"""
import polyinterface
from ntSession import ntSession

LOGGER = polyinterface.LOGGER

class AssistantRelay(polyinterface.Node):
    """
    """
    def __init__(self, controller, primary, address, name):
        """
        """
        super(AssistantRelay, self).__init__(controller, primary, address, name)
        self.l_name = name

    def start(self):
        """
        """
        self.setDriver('ST', 1)
        self.set_user(self.getDriver('GV1'))
        # Start the session for talking to wirelesstag server
        self.session = ntSession(self,LOGGER,self.controller.ar_host,self.controller.ar_port)
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

    def cmd_send(self,command):
        self.l_info("cmd_send",'')
        #11curl -d '{"command":"This is Izzy, can you hear me?", "user":"jna", "broadcast":"true"}' -H "Content-Type: application/json" -X POST http://192.168.86.79:3001/assistant
        self.session.post('assistant',{"command":"Izzy is alive", "user":"jna", "broadcast":"true"})

    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 2},
        {'driver': 'GV1', 'value': 0, 'uom': 25},
    ]
    id = 'assistantrelay'
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SET_USER': cmd_set_user,
                'SEND': cmd_send
                }
