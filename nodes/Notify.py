"""
  Notification Notify Node

  TODO:
    - Make sure Notify name is get_valid_node_name, and Length
    - Clean out profile directory?

"""
import polyinterface
import logging
from node_funcs import make_file_dir

LOGGER = polyinterface.LOGGER

class Notify(polyinterface.Node):
    """
    """
    def __init__(self, controller, primary, address, name, info):
        """
        """
        #self.l_debug('init','{} {}'.format(self.address,self.name))
        self._init_st = None;
        self.info     = info
        self.iname    = info['name']
        self.iid      = info['id']
        self.id       = 'notify_' + self.iid
        self.service_node_name = self.info['service_node_name']
        super(Notify, self).__init__(controller, primary, address, name)

    def start(self):
        self.l_info('start','')
        # We track our driver values because we need the value before it's been pushed.
        self.driver = {}
        # Make sure we know who our service node is
        self.controller.get_service_node(self.service_node_name)
        #self.set_device(self.get_device())
        self.set_priority(self.get_priority())
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
        self.l_info(pfx,'')
        #
        # Open the output nodedefs file
        output_f   = 'profile/nodedef/{0}.xml'.format(self.iid)
        make_file_dir(output_f)
        # Open the template, and read into a string for formatting.
        template_f = 'template/nodedef/notify.xml'
        self.l_info(pfx,"Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Write the nodedef file with our info
        self.l_info(pfx,"Writing {}".format(output_f))
        out_h = open(output_f, "w")
        self.l_debug('write_profile','info={}'.format(self.info))
        out_h.write(data.format(self.id,'PO_D_'+self.service_node_name))
        out_h.close()
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


    _init_st = None
    id = 'notify'
    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 2},
        {'driver': 'ERR', 'value': 0, 'uom': 25},
        {'driver': 'GV1', 'value': 0, 'uom': 25},
        {'driver': 'GV2', 'value': 0, 'uom': 25},
        {'driver': 'GV3', 'value': 0, 'uom': 25},
        {'driver': 'GV4', 'value': 0, 'uom': 25},
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
