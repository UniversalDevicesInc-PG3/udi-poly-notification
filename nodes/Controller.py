"""
  Notification Controller Node
"""

import polyinterface
from nodes import *
import logging
from PolyglotREST import polyglotRESTServer

LOGGER = polyinterface.LOGGER

xref_messages = [
    { 'id':'fdo', 'title':None, 'message':'Front Door Open' },
    { 'id':'fdc', 'title':None, 'message':'Front Door Closed'},
    { 'id':'bdo', 'title':None, 'message':'Back Door Open'},
    { 'id':'bdc', 'title':None, 'message':'Back Door Closed'},
    { 'id':'gdo', 'title':None, 'message':'Garage Door Open'},
    { 'id':'gdc', 'title':None, 'message':'Garage Door Closed'},
]

class Controller(polyinterface.Controller):
    """
    """
    def __init__(self, polyglot):
        """
        """
        super(Controller, self).__init__(polyglot)
        self.name = 'Notification Controller'
        self.hb = 0

    def start(self):
        """
        """
        LOGGER.info('Started notification NodeServer')
        self.rest = polyglotRESTServer('8099',LOGGER,ghandler=self.rest_handler)
        # TODO: Need to monitor thread and restart if it dies
        self.rest.start()
        self.set_debug_level(self.getDriver('GV1'))
        self.check_params()
        self.discover()

    def shortPoll(self):
        pass

    def longPoll(self):
        self.heartbeat()

    def heartbeat(self):
        self.l_debug('heartbeat','hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    def query(self):
        #self.check_params()
        for node in self.nodes:
            self.nodes[node].reportDrivers()

    def discover(self, *args, **kwargs):
        """
        """
        self.poly.installprofile()
        #customParams = self.polyConfig.get('customParams', {})
        #pnodes = customParams.get('pushover')
        self.pnodes = self.get_typed_name('pushover')
        self.messages = xref_messages
        # name must be <= 11 characters, and dont change since it's used as the node address
        self.pnodes = [{'name': 'homeisy', 'user_key': 'tavzn48CN3tsp8iXwPwNgDxbfw3ngh', 'app_key': 'XY2bmjgRLzy4LANZREGd23WrewFawA'}]
        if self.pnodes is None or len(self.pnodes) == 0:
            self.l_info('discover',"No Pushover Entries in the config: {}".format(self.pnodes))
            return
        for pd in self.pnodes:
            self.addNode(Pushover(self, self.address, 'po_{}'.format(pd['name']), 'Pushover {}'.format(pd['name']), pd))

        #self.addNode(AssistantRelay(self, self.address, 'assistantrelay', 'AssistantRelay'))

    def delete(self):
        """
        """
        LOGGER.info('Oh God I\'m being deleted. Nooooooooooooooooooooooooooooooooooooooooo.')

    def stop(self):
        LOGGER.debug('NodeServer stopped.')

    def get_current_message(self):
        i = self.getDriver('GV2')
        if i is None:
            i = 0
        else:
            i = int(i)
        return self.messages[i]

    def supports_feature(self, feature):
        if hasattr(self.poly, 'supports_feature'):
            return self.poly.supports_feature(feature)
        return False

    def get_typed_name(self,name):
        typedConfig = self.polyConfig.get('typedCustomData')
        if not typedConfig:
            return None
        return typedConfig.get(name)

    def check_params(self):
        """
        This is an example if using custom Params for user and password and an example with a Dictionary
        """
        # Remove all existing notices
        self.removeNoticesAll()
        #if self.supports_feature('typedParams'):
        if True:
            params = [
                        {
                            'name': 'notifications',
                            'title': 'Notifications',
                            'desc': 'Your Notifications',
                            'isList': True,
                            'params': [
                                {
                                    'name': 'subject',
                                    'title': 'Subject',
                                    'isRequired': True
                                },
                                {
                                    'name': 'body',
                                    'title': 'Body (Optional)',
                                    'isRequired': False
                                },
                            ]
                        },
                        {
                            'name': 'pushover',
                            'title': 'Pushover Keys',
                            'desc': 'Config for https://pushover.net/',
                            'isList': True,
                            'params': [
                                {
                                    'name': 'name',
                                    'title': 'Account Name For Reference',
                                    'isRequired': True
                                },
                                {
                                    'name': 'key',
                                    'title': 'The User Key',
                                    'isRequired': True
                                },
                                {
                                    'name': 'apps',
                                    'title': 'Application Keys',
                                    'isRequired': True,
                                    'isList': True,
                                    #s'defaultValue': ['somename'],
                                },
                            ]
                        },
                        {
                            'name': 'assistant_relay',
                            'title': 'Assistant Relay',
                            'desc': 'Config for https://github.com/greghesp/assistant-relay',
                            'isList': True,
                            'params': [
                                {
                                    'name': 'host',
                                    'title': 'Host',
                                    'defaultValue': 'this_host_ip',
                                    'isRequired': True
                                },
                                {
                                    'name': 'port',
                                    'title': 'Port',
                                    'isRequired': True,
                                    'isList': False,
                                    'defaultValue': '3001',
                                },
                                {
                                    'name': 'users',
                                    'title': 'Users',
                                    'isRequired': True,
                                    'isList': True,
                                    'defaultValue': ['someuser'],
                                },
                            ]
                        }
                    ]
            self.poly.save_typed_params(params)
        else:
            txt = 'You need to run a newer version of polyglot that supports typedParams'
            self.l_error('check_params', txt)
            self.addNotice(txt)

        self.l_info('check_params', self.polyConfig['customParams'])
        #default = "None"
        #if 'assistant_remote_host' in self.polyConfig['customParams']:
        #    self.ar_host = self.polyConfig['customParams']['ar_host']
        #else:
        #    self.ar_host = default
        #    LOGGER.error('check_params: ar_host not defined in customParams, please add it.  Using {}'.format(self.ar_host))
        #    st = False
        #if 'ar_port' in self.polyConfig['customParams']:
        #    self.ar_port = self.polyConfig['customParams']['ar_port']
        #else:
        #    self.ar_port = default
        #    LOGGER.error('check_params: ar_post not defined in customParams, please add it.  Using {}'.format(self.ar_port))
        #    st = False

        # Make sure they are in the params
        #self.addCustomParam({'ar_host': self.ar_host, 'ar_port': self.ar_port })

        # Add a notice if they need to change the user/password from the default.
        #if self.user == default_user or self.password == default_password:
        #    # This doesn't pass a key to test the old way.
        #    self.addNotice('Please set proper user and password in configuration page, and restart this nodeserver')

    def set_all_logs(self,level):
        LOGGER.setLevel(level)
        #logging.getLogger('requests').setLevel(level)

    def set_debug_level(self,level):
        self.l_info('set_debug_level',level)
        if level is None:
            level = 20
        level = int(level)
        if level == 0:
            level = 20
        self.l_info('set_debug_level','Set GV1 to {}'.format(level))
        self.setDriver('GV1', level)
        # 0=All 10=Debug are the same because 0 (NOTSET) doesn't show everything.
        if level == 10:
            self.set_all_logs(logging.DEBUG)
        elif level == 20:
            self.set_all_logs(logging.INFO)
        elif level == 30:
            self.set_all_logs(logging.WARNING)
        elif level == 40:
            self.set_all_logs(logging.ERROR)
        elif level == 50:
            self.set_all_logs(logging.CRITICAL)
        else:
            self.l_error("set_debug_level","Unknown level {}".format(level))

    def cmd_install_profile(self,command):
        LOGGER.info('cmd_install_profile:')
        st = self.poly.installprofile()
        return st

    def cmd_set_debug_mode(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_debug_mode",val)
        self.set_debug_level(val)

    def l_info(self, name, string):
        LOGGER.info("%s:%s: %s" %  (self.id,name,string))

    def l_error(self, name, string):
        LOGGER.error("%s:%s: %s" % (self.id,name,string))

    def l_warning(self, name, string):
        LOGGER.warning("%s:%s: %s" % (self.id,name,string))

    def l_debug(self, name, string):
        LOGGER.debug("%s:%s: %s" % (self.id,name,string))

    def rest_handler(self,command,params,data=None):
        self.l_info('rest_handler',' command={} params={} data={}'.format(command,params,data))
        if command == '/send':
            if not 'node' in params:
                self.l_error('rest_handler', 'node not passed in for send params: {}'.format(params))
                return False
            node = params['node']
            if not node in self.nodes:
                self.l_error('rest_handler', 'unknown node "{}"'.format(node))
                return False
            self.nodes[node].rest_handler(command,params,data)
        return True

    """
    Optional.
    Since the controller is the parent node in ISY, it will actual show up as a node.
    So it needs to know the drivers and what id it will use. The drivers are
    the defaults in the parent Class, so you don't need them unless you want to add to
    them. The ST and GV1 variables are for reporting status through Polyglot to ISY,
    DO NOT remove them. UOM 2 is boolean.
    The id must match the nodeDef id="controller"
    In the nodedefs.xml
    """
    id = 'controller'
    commands = {
        'SET_DM': cmd_set_debug_mode,
        #'SET_SHORTPOLL': cmd_set_short_poll,
        #'SET_LONGPOLL':  cmd_set_long_poll,
        'QUERY': query,
        'DISCOVER': discover,
        'INSTALL_PROFILE': cmd_install_profile
    }
    drivers = [
        {'driver': 'ST',  'value': 1,  'uom': 2},  # Nodeserver status
        {'driver': 'GV1', 'value': 10, 'uom': 25}, # Debug (Log) Mode
        {'driver': 'GV2', 'value': 0,  'uom': 25}, # Notification
    ]
