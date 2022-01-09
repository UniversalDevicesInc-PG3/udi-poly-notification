"""
  Notification Google Assistant Relay Node
"""
from udi_interface import Node,LOGGER
from ntSession import ntSession

class AssistantRelay(Node):
    """
    """
    def __init__(self, controller, primary, address, name):
        """
        """
        controller.poly.subscribe(controller.poly.START,                  self.handler_start, address)
        super(AssistantRelay, self).__init__(controller.poly, primary, address, name)
        self.l_name = name

    def handler_start(self):
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

    def set_user(self,val):
        LOGGER.info(val)
        if val is None:
            val = 0
        val = int(val)
        LOGGER.info('Set GV1 to {}'.format(val))
        self.setDriver('GV1', val)

    def cmd_set_user(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_user(val)

    def cmd_send(self,command):
        LOGGER.info('')
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
