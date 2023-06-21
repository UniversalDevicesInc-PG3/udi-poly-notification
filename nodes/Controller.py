"""
  Notification Controller Node
"""

from udi_interface import Node,LOGGER,Custom,LOG_HANDLER
from nodes import *
import logging
from node_funcs import *
from PolyglotREST import polyglotRESTServer,polyglotSession
from copy import deepcopy
from threading import Lock
import re
import time
import fnmatch
import os
from distutils.version import StrictVersion

class Controller(Node):
    """
    """
    def __init__(self, poly, primary, address, name):
        """
        """
        super(Controller, self).__init__(poly, primary, address, name)
        self.hb = 0
        self.messages = None
        self.rest = None
        self.rest_port = None
        self._sys_short_msg = None
        #  pg3init={'uuid': '00:0d:b9:52:ce:50', 'profileNum': 2, 
        #  'logLevel': 'DEBUG', 'token': 'vuXtqI5ILW**A&Zf', 'mqttHost': 'localhost', 'mqttPort': 1888, 'secure': 1, 
        #  'pg3Version': '3.1.21', 'isyVersion': '5.6.2', 'edition': 'Free'}
        LOGGER.warning(f'init={self.poly.pg3init}')
        self.edition = self.poly.pg3init['edition']
        self.has_sys_editor_full = True if (
            StrictVersion(self.poly.pg3init['isyVersion']) >= StrictVersion('5.6.2')
            # All versions since isPG3x was added to PG3 and PG3x works with sys_notify_full
            # But, now one more version to full support the data coming from the IoX http post
            and (
                'isPG3x' in self.poly.pg3init
                and ( 
                    (self.poly.pg3init['isPG3X'] is True and StrictVersion(self.poly.pg3init['pg3Version']) > StrictVersion('3.1.31'))
                    or (self.poly.pg3init['isPG3X'] is not True and StrictVersion(self.poly.pg3init['pg3Version']) > StrictVersion('3.1.23'))
                    ) 
                )
            ) else False
        self.sys_notify_editor = '_sys_notify_full' if self.has_sys_editor_full else '_sys_notify_short'
        self.sys_notify_uom_d  = 148 if self.has_sys_editor_full else 146
        self.sys_notify_uom_t  = 147 if self.has_sys_editor_full else 145
        LOGGER.warning(f'has_sys_editor_full={self.has_sys_editor_full} editor={self.sys_notify_editor}')
        self.drivers = [
            {'driver': 'ST',  'value': 1,  'uom': 25}, # Nodeserver status
            {'driver': 'GV1', 'value': 0,  'uom': 25}, # REST Status
            {'driver': 'GV2', 'value': 0,  'uom': 25}, # Message
            {'driver': 'GV3', 'value': 0,  'uom': self.sys_notify_uom_d}, # Custom Content
        ]
        self.uuid    = self.poly.pg3init['uuid']
        self.nodename = os.uname().nodename
        # List of all service nodes
        self.service_nodes = list()
        self.first_run = True
        self.ready     = False
        self.n_queue = []
        # We track our driver values because we need the value before it's been pushed.
        # Is this necessary anymore in PG3?
        self.driver = {}
        self.Notices         = Custom(poly, 'notices')
        self.Params          = Custom(poly, 'customparams')
        self.Data            = Custom(poly, 'customdata')
        self.TypedParams     = Custom(poly, 'customtypedparams')
        self.TypedData       = Custom(poly, 'customtypeddata')
        poly.subscribe(poly.START,                  self.handler_start, address) 
        poly.subscribe(poly.POLL,                   self.handler_poll)
        poly.subscribe(poly.ADDNODEDONE,            self.node_queue)
        poly.subscribe(poly.CONFIGDONE,             self.handler_config_done)
        poly.subscribe(poly.CUSTOMPARAMS,           self.handler_params)
        poly.subscribe(poly.CUSTOMDATA,             self.handler_data)
        poly.subscribe(poly.CUSTOMTYPEDDATA,        self.handler_typed_data)
        poly.subscribe(poly.LOGLEVEL,               self.handler_log_level)
        poly.subscribe(poly.STOP,                   self.handler_stop)
        self.handler_start_st      = None
        self.handler_params_st     = None
        self.handler_data_st       = None
        self.handler_typed_data_st = None
        self.handler_config_st     = None
        self.write_profile_lock = Lock() # Lock for syncronizing acress threads
        self.init_typed()
        poly.ready()
        self.Notices.clear()
        poly.addNode(self, conn_status="ST")

    '''
    node_queue() and wait_for_node_event() create a simple way to wait
    for a node to be created.  The nodeAdd() API call is asynchronous and
    will return before the node is fully created. Using this, we can wait
    until it is fully created before we try to use it.
    '''
    def node_queue(self, data):
        self.n_queue.append(data['address'])
        if (data['address'] == self.address):
            LOGGER.debug("Controller add done")
            self.add_node_done()

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.1)
        self.n_queue.pop()

    """
    Everyone should call this instead of poly.addNode so they are added one at a time.
    """
    def add_node(self,node):
        anode = self.poly.addNode(node)
        LOGGER.debug(f'got {anode}')
        self.wait_for_node_done()
        if anode is None:
            LOGGER.error(f'Failed to add node {node}')
        return anode

    def handler_start(self):
        LOGGER.info(f"Started Notification NodeServer {self.poly.serverdata['version']}")
        self.poly.updateProfile()
        self.heartbeat()
        self.handler_start_st = True

    def handler_config_done(self):
        LOGGER.debug("enter")
        self.handler_config_st = True
        LOGGER.debug("exit")

    def add_node_done(self):
        LOGGER.debug("enter")
        if not self.has_sys_editor_full:
            msg = f"Please upgrade modules and reboot to allow usage of Full Custom System Notifications. isyVersion={self.poly.pg3init['isyVersion']} isPG3x={self.poly.pg3init['isPG3X']} pg3Version={self.poly.pg3init['pg3Version']} See <a href='https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/blob/master/README.md#system-customizations' target='_ blank'>System Customizations</a>"
            self.Notices['upgrade'] = msg
            LOGGER.warning(msg)
        cnt = 120
        while (cnt > 0 and (
            self.handler_start_st is None
            or self.handler_params_st is None
            or self.handler_data_st is None
            or self.handler_typed_data_st is None)):
            LOGGER.warning(f'Waiting for all handlers to complete start={self.handler_start_st} params={self.handler_params_st} data={self.handler_data_st} typed_data={self.handler_typed_data_st} cnt={cnt}')
            time.sleep(1)
            cnt -= 1
        if cnt == 0:
            LOGGER.error('Timed out waiting for all handlers to complete')
            LOGGER.error('Exiting...')
            self.poly.stop()
        else:
            if cnt < 60:
                LOGGER.warning(f'Done waiting, all looks good')
            self.start_rest_server()
            self.write_profile()
            self.first_run = False
        LOGGER.debug("exit")
    
    def handler_poll(self, polltype):
        if polltype == 'longPoll':
            self.heartbeat()

    def heartbeat(self):
        LOGGER.debug('hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    def query(self):
        #self.check_params()
        for node in self.poly.nodes():
            node.reportDrivers()

    def delete(self):
        if self.rest is not None:
            self.rest.stop()
        LOGGER.info('Oh God I\'m being deleted. Nooooooooooooooooooooooooooooooooooooooooo.')

    def handler_stop(self):
        LOGGER.debug('NodeServer stopping.')
        if self.rest is not None:
            self.rest.stop()
        LOGGER.debug('NodeServer stopped.')
        self.poly.stop()

    def setDriver(self,driver,value):
        self.driver[driver] = value
        super(Controller, self).setDriver(driver,value)

    def getDriver(self,driver):
        if driver in self.driver:
            return self.driver[driver]
        else:
            return super(Controller, self).getDriver(driver)

    def get_message_short(self,query):
        msg = query.get(f'Content.uom145')
        if msg is None:
            return ret
        # Entire message and title is first line, body is the rest
        sp = msg.split("\n",1)
        ret = { 'message': msg, 'subject': sp[0] }
        if len(sp) > 1:
            ret['body'] = sp[1]
        else:
            ret['body'] = ' '
        return ret

    # New: 'message': {'notification': {'formatted': {'mimetype': 'text/plain', 'from': '', 'subject': 'program[0]: node[#]=node[#] null null received', 'body': ''}, '@_id': '1'}
    def get_message_long(self,query):
        msg = query.get(f'Content.uom147')
        if msg is None:
            return msg
        # Contains subject & body
        ret = msg['notification']['formatted']
        if (ret['body'] == ""):
            ret['message'] = ret['subject']
            ret['body'] = ' '
        else:
            ret['message'] = ret['subject'] + "\n" + ret['body']
        return ret

    # Format old short or new long query.
    def get_message_from_query(self,query):
        reboot = False
        if self.has_sys_editor_full:
            # New _sys_editor_full
            msg = self.get_message_long(query)
            if msg is None:
                # Check for the old one
                msg = self.get_message_short(query)
                if msg is None:
                    msg = { 'subject': "ERROR", 'body': "No message passed in"}
                else:
                    reboot = True
            else:
                ret = self.get_message_long(msg)
        else:
            # Old _sys_editor_short
            msg = self.get_message_short(query)
            if msg is None:
                # New _sys_editor_full
                msg = self.get_message_long(query)
                if msg is None:
                    msg = { 'subject': "ERROR", 'body': "No message passed in"}
                else:
                    reboot = True
        if reboot:
            self.Notices['reboot_iox'] = "ERROR: You need to reboot our IoX to fix references to sys_notify editors"
        msg['reboot'] = reboot
        return msg
    
    def get_service_node(self,sname):
        for item in self.service_nodes:
            if item['name'] == sname or item['node'].address == sname or item['node'].name == sname:
                return item
        l = list()
        for item in self.service_nodes:
            l.extend([item['name'],item['node'].address,item['node'].name])
        LOGGER.error(f"Unknown service node {sname} must be one of: " + ", ".join(l))
        return False

    def get_current_message(self):
        return(self.get_message_by_id(self.getDriver('GV2')))

    def get_message_by_id(self,id):
        LOGGER.info(f'id={id}')
        if id is None:
            id = 0
        else:
            id = int(id)
        for msg in self.messages:
            if int(msg['id']) == id:
                return msg
        LOGGER.error('id={} not found in: {}'.format(id,self.messages))
        return { id: 0, 'title': 'Unknown', 'message': 'Undefined message {}'.format(id)}

    def get_typed_name(self,name):
        typedConfig = self.polyConfig.get('typedCustomData')
        if not typedConfig:
            return None
        return typedConfig.get(name)

    def get_message_node_address(self,id):
        return get_valid_node_address('mn_'+id)

    def get_service_node_address(self,id):
        return get_valid_node_address('po_'+id)

    def get_service_node_address_isyportal(self,id):
        return get_valid_node_address('ip_'+id)

    def get_service_node_address_telegramub(self,id):
        return get_valid_node_address('tu_'+id)

    def init_typed(self):
        LOGGER.debug('enter')
        self.TypedParams.load(
            [
                #{   
                #    'name': 'rest_port', 
                #    'title': 'REST Server Port',
                #    'isRequired': False, 
                #    'type': 'NUMBER',
                #    'defaultValue': 8199
                #},
                {
                    'name': 'messages',
                    'title': 'Messages',
                    'desc': 'Your Custom Messages',
                    'isList': True,
                    'params': [
                        {
                            'name': 'id',
                            'title': "ID (Must be integer greater than zero and should never change!)",
                            'isRequired': True,
                        },
                        {
                            'name': 'title',
                            'title': 'Title (Should be short)',
                            'isRequired': True
                        },
                        {
                            'name': 'message',
                            'title': 'Message (If empty, assume same as title)',
                            'isRequired': False
                        },
                    ]
                },
                {
                    'name': 'pushover',
                    'title': 'Pushover Service Nodes',
                    'desc': 'Config for https://pushover.net/',
                    'isList': True,
                    'params': [
                        {
                            'name': 'name',
                            'title': 'Name for reference, used as node name. Must be 8 characters or less.',
                            'isRequired': True
                        },
                        {
                            'name': 'user_key',
                            'title': 'The User Key',
                            'isRequired': True
                        },
                        {
                            'name': 'app_key',
                            'title': 'Application Key',
                            'isRequired': True,
                            'isList': False,
                            #s'defaultValue': ['somename'],
                        },
                    ]
                },
                {
                    'name': 'isyportal',
                    'title': 'ISYPortal Service Nodes',
                    'desc': 'Config for UD Portal Notifications',
                    'isList': True,
                    'params': [
                        {
                            'name': 'name',
                            'title': 'Name for reference, used as node name. Must be 8 characters or less.',
                            'isRequired': True
                        },
                        {
                            'name': 'api_key',
                            'title': 'Portal API Key',
                            'isRequired': True,
                            'isList': False,
                            #s'defaultValue': ['somename'],
                        },
                    ]
                },
                {
                    'name': 'notify',
                    'title': 'Notify Nodes',
                    'desc': 'Notify Nodes to create',
                    'isList': True,
                    'params': [
                        {
                            'name': 'id',
                            'title': "ID for node, never change, 8 characters or less",
                            'isRequired': True
                        },
                        {
                            'name': 'name',
                            'title': 'Name for node',
                            'isRequired': True
                        },
                        {
                            'name': 'service_node_name',
                            'title': "Service Node Name Must match an existing Service Node Name",
                            'isRequired': True
                        },
                    ]
                },
                {
                    'name': 'assistant_relay',
                    'title': 'Assistant Relay Service Node',
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
                },
                {
                    'name': 'telegramub',
                    'title': 'Telegram User Bot Service Node',
                    'desc': 'Config for https://github.com/greghesp/assistant-relay',
                    'isList': True,
                    'params': [
                        {
                            'name': 'name',
                            'title': 'Name for reference, used as node name. Must be 8 characters or less.',
                            'isRequired': True
                        },
                        {
                            'name': 'http_api_key',
                            'title': 'HTTP API Key',
                            'defaultValue': 'your_http_api_key',
                            'isRequired': True
                        },
                        {
                            'name': 'users',
                            'title': 'Users',
                            'isRequired': True,
                            'isList': True,
                            'defaultValue': ['someuserid'],
                        },
                    ]
                }
            ],
            True
        )
        LOGGER.debug('exit')

    def handler_data(self,data):
        LOGGER.debug(f'Enter data={data}')
        if data is None:
            self.handler_data_st = False
        else:
            self.Data.load(data)
            self.handler_data_st = True

    def get_data(self,param,default):
        if param in self.Data:
            return self.Data[param]
        else:
            return default
    
    def start_rest_server(self):
        self.Notices.delete('rest')
        msg = False
        if self.handler_params_st is True:
            if self.rest is None:
                if self.rest_port is None or self.rest_port == "":
                    msg = f"Not starting REST Server, rest_port={self.rest_port}"
                else:
                    LOGGER.info("Starting REST Server...")
                    self.rest = polyglotRESTServer(self.rest_port,LOGGER,ghandler=self.rest_ghandler)
                    # TODO: Need to monitor thread and restart if it dies?
                    if (self.rest.start() is True):
                        self.setDriver('GV1',1)
                    else:
                        self.setDriver('GV1',0)
                        msg = f"REST Server not started for rest_port={self.rest_port}, check log for error"
            else:
                msg = f"REST Sever already running ({self.rest})"
        else:
            msg = f'Unable to start REST Server until config params are corrected ({self.handler_params_st})'
        if msg is not False:
            self.Notices['rest'] = msg;

    def handler_params(self, data):
        LOGGER.debug("Enter data={}".format(data))
        self.Params.load(data)
        if not 'rest_port' in data:
            self.Params['rest_port'] = '8199'
            return
        if not 'portal_api_key' in data:
            self.Params['portal_api_key'] = 'PleaseDefine'
            return
        self.rest_port = data['rest_port']
        self.portal_api_key = data['portal_api_key']
        # Assume we are good unless something bad is found
        st = True
        # Make sure they acknowledge
        ack = 'acknowledge'
        val = None
        if ack in data:
            val = data[ack]
        else:
            val = ""
            self.Params[ack] = val
            # Return because we will be called again since we added the param that was deleted.
            st = False
        if val != 'I understand and agree':
            self.Notices[ack] = 'Before using you must follow the link to <a href="https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/blob/master/ACKNOWLEDGE.md" target="_blank">acknowledge</a>'
            st = False
        else:
            self.Notices.delete(ack)

        if st:
            val = "portal_api_key"
            if self.Params[val] == 'PleaseDefine':
                self.Notices[val] = 'Please Define portal_api_key'
            else:
                self.Notices.delete(val)
                # Start the UDMobile node
                self.udmobile_session = polyglotSession(self,"https://my.isy.io",LOGGER)
                snode = self.add_node(UDMobile(self, self.address, 'udmobile', get_valid_node_name('UD Mobile'), self.udmobile_session, self.portal_api_key))
                self.service_nodes.append({ 'name': snode.name, 'node': snode, 'index': len(self.service_nodes)})
                LOGGER.info('service_nodes={}'.format(self.service_nodes))

        self.handler_params_st = st
        # Dont' start on first run cause we need handler_typed_data to be completed
        # add_node_done will do it on first start 
        if not self.first_run:
            # When data changes build the profile, 
            self.write_profile()
            self.start_rest_server()

    def handler_typed_data(self, data):
        LOGGER.debug("Enter data={}".format(data))
        self.TypedData.load(data)
        if data is None:
            self.handler_typed_data_st = False
            return False

        # If we have already been run on startup, clear any notices.
        if self.handler_config_st is not None:
            self.Notices.clear()

        el = list()

        #We are not getting this returned in data??? Report to Bob.
        #self.rest_port = data.get('rest_port',None)

        self.messages = data.get('messages',el)
        LOGGER.info('messages={}'.format(self.messages))
        if len(self.messages) == 0:
            LOGGER.info('No messages')

        #
        # List of all service node names
        snames   = dict()
        # List of errors to print at the end in a Notice        
        err_list = list()

        #
        # Check the pushover configs are all good
        #
        pushover = data.get('pushover',el)
        # Pushover node names
        pnames   = dict()
        LOGGER.info('pushover={}'.format(pushover))
        if len(pushover) == 0:
            LOGGER.warning("No Pushover Entries in the config: {}".format(pushover))
            pushover = None
        else:
            for pd in pushover:
                if 'name' in pd:
                    sname = pd['name']
                    # Save info for later
                    pd['type'] = 'pushover'
                    snames[sname] = pd
                    # Check for duplicates
                    address = self.get_service_node_address(sname)
                    if not address in pnames:
                        pnames[address] = list()
                    pnames[address].append(sname)
                else:
                    err_list.append("Missing name in pushover node {}".format(pd))
                    continue
            for address in pnames:
                if len(pnames[address]) > 1:
                    err_list.append("Duplicate pushover names for {} items {} from {}".format(len(pnames[address]),address,",".join(pnames[address])))

        #
        # Check the isyportal configs are all good
        #
        isyportal = data.get('isyportal',el)
        # ISYPortal node names
        unames   = dict()
        LOGGER.info('isyportal={}'.format(isyportal))
        if len(isyportal) == 0:
            LOGGER.warning("No ISYPortal Entries in the config: {}".format(isyportal))
            isyportal = None
        else:
            for pd in isyportal:
                if 'name' in pd:
                    sname = pd['name']
                    # Save info for later
                    pd['type'] = 'isyportal'
                    snames[sname] = pd
                    # Check for duplicates
                    address = self.get_service_node_address(sname)
                    if not address in unames:
                        unames[address] = list()
                    unames[address].append(sname)
                else:
                    err_list.append("Missing name in ISYPortal node {}".format(pd))
                    continue
            for address in unames:
                if len(unames[address]) > 1:
                    err_list.append("Duplicate isyportal names for {} items {} from {}".format(len(unames[address]),address,",".join(unames[address])))

        #
        # Check the telegramub configs are all good
        #
        telegramub = data.get('telegramub',el)
        # Telegram node names
        tnames   = dict()
        LOGGER.info('telegramub={}'.format(telegramub))
        if len(telegramub) == 0:
            LOGGER.warning("No Telegram User Bot Entries in the config: {}".format(telegramub))
            telegramub = None
        else:
            for pd in telegramub:
                if 'name' in pd:
                    sname = pd['name']
                else:
                    sname = 'telegramub'
                # Save info for later
                pd['type'] = 'telegramub'
                snames[sname] = pd
                # Check for duplicates...
                address = self.get_service_node_address_telegramub(sname)
                if not address in tnames:
                    tnames[address] = list()
                tnames[address].append(sname)
            for address in tnames:
                if len(tnames[address]) > 1:
                    err_list.append("Duplicate names for {} items {} from {}".format(len(tnames[address]),address,",".join(tnames[address])))
        #
        # Check the message notify_nodes are all good
        #
        notify_nodes    = data.get('notify',el)
        if len(notify_nodes) == 0:
            LOGGER.warning('No Notify Nodes')
        else:
            # First check that notify_nodes are valid before we try to add them
            mnames = dict()
            for node in notify_nodes:
                address = self.get_message_node_address(node['id'])
                if not address in mnames:
                    mnames[address] = list()
                mnames[address].append(node['id'])
                # And check that service node name is known
                if 'service_node_name' in node:
                    sname = node['service_node_name']
                    if not sname in snames:
                        err_list.append("Unknown service node name {} in message node {} must be one of {}".format(sname,node,",".join(snames)))
                else:
                    err_list.append("No service node name in message node {} must be one of {}".format(sname,node,",".join(snames)))
            for address in mnames:
                if len(mnames[address]) > 1:
                    err_list.append("Duplicate Notify ids for {} items {} from {}".format(len(mnames[address]),address,",".join(mnames[address])))
        #
        # Any errors, print them and stop
        #
        if len(err_list) > 0:
            cnt = 1
            for msg in err_list:
                LOGGER.error(msg)
                self.Notices[f'msg{cnt}'] = msg
                cnt += 1
            self.Notices['typed_data'] = f'There are {len(err_list)} errors found please fix Errors and restart.'
            self.handler_typed_data_st = False
            return

        if pushover is not None:
            self.pushover_session = polyglotSession(self,"https://api.pushover.net",LOGGER)
            for pd in pushover:
                if self.edition == "Free":
                    err = f"Can't add Pushover node {pd['name']} in {self.edition} Edition"
                    LOGGER.error(err)
                    self.Notices[pd['name']] = err
                else:
                    snode = self.add_node(Pushover(self, self.address, self.get_service_node_address(pd['name']), get_valid_node_name('Service Pushover '+pd['name']), self.pushover_session, pd))
                    self.service_nodes.append({ 'name': pd['name'], 'node': snode, 'index': len(self.service_nodes)})
                    LOGGER.info('service_nodes={}'.format(self.service_nodes))

        if isyportal is not None:
            # https://wiki.universal-devices.com/index.php?title=UD_Mobile#Notifications_Tab
            # Protocol: https | POST | Host = my.isy.io | Port = 443 | Path = /api/push/notification/send | Mode = Raw Text
            # Header: Add x-api-key with the value as your API Key copied from UD Mobile. 
            # Body: title=message_title&body=message_body where message_title and message_body are replaced by your desired title and body values.
            self.isyportal_session = polyglotSession(self,"https://my.isy.io",LOGGER)
            for pd in isyportal:
                if self.edition == "Free":
                    err = f"Can't add ISYPortal node {pd['name']} in {self.edition} Edition"
                    LOGGER.error(err)
                    self.Notices[pd['name']] = err
                else:
                    snode = self.add_node(ISYPortal(self, self.address, self.get_service_node_address_isyportal(pd['name']), get_valid_node_name('Service ISYPortal '+pd['name']), self.isyportal_session, pd))
                    self.service_nodes.append({ 'name': pd['name'], 'node': snode, 'index': len(self.service_nodes)})
                    LOGGER.info('service_nodes={}'.format(self.service_nodes))

        if telegramub is not None:
            self.telegramub_session = polyglotSession(self,"https://api.telegram.org",LOGGER)
            for pd in telegramub:
                if self.edition == "Free":
                    err = f"Can't add Telegram node {pd['name']} in {self.edition} Edition"
                    LOGGER.error(err)
                    self.Notices[pd['name']] = err
                else:
                    snode = self.add_node(TelegramUB(self, self.address, self.get_service_node_address_telegramub(pd['name']), get_valid_node_name('Service TelegramUB '+pd['name']), self.telegramub_session, pd))
                    self.service_nodes.append({ 'name': pd['name'], 'node': snode, 'index': len(self.service_nodes)})
                    LOGGER.info('service_nodes={}'.format(self.service_nodes))

        # TODO: Save service_nodes names in customParams
        if notify_nodes is not None:
            save = True
            LOGGER.debug('Adding Notify notify_nodes...')
            for node in notify_nodes:
                # TODO: make sure node.service_node_name is valid, and pass service node type (pushover) to addNode, or put in node dict
                node['service_type'] = snames[node['service_node_name']]['type']
                self.add_node(Notify(self, self.address, self.get_message_node_address(node['id']), 'Notify '+get_valid_node_name(node['name']), node))

        self.handler_typed_data_st = True

        # When data changes build the profile, except when first starting up since
        # that will be done by the config handler
        if not self.first_run:
            self.write_profile()

    def write_profile(self):
        pfx = 'write_profile'
        LOGGER.info('enter')
        self.write_profile_lock.acquire()
        # Good unless there is an error.
        st = True
        #
        # First clean out all files we created
        #
        for dir in ['profile/editor', 'profile/nodedef']:
            if os.path.exists(dir):
                LOGGER.debug('Cleaning: {}'.format(dir))
                for file in os.listdir(dir):
                    LOGGER.debug(file)
                    path = dir+'/'+file
                    if os.path.isfile(path) and file != 'editors.xml':
                        LOGGER.debug('Removing: {}'.format(path))
                        os.remove(path)
        #
        # Write the profile Data
        #
        #
        # nodedef
        #
        if not os.path.exists('profile/nodedef'):
            os.mkdir('profile/nodedef')
        # Open the template, and read into a string for formatting.
        template_f = 'template/nodedef/nodedefs.xml'
        LOGGER.debug("Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Open the output nodedefs file
        output_f   = 'profile/nodedef/nodedefs.xml'
        make_file_dir(output_f)
        # Write the nodedef file with our info
        LOGGER.debug("Writing {}".format(output_f))
        out_h = open(output_f, "w")
        out_h.write(data.format(self.sys_notify_editor))
        out_h.close()
        #
        # There is only one nls, so read the nls template and write the new one
        #
        en_us_txt = "profile/nls/en_us.txt"
        make_file_dir(en_us_txt)
        template_f = "template/nls/en_us.txt"
        LOGGER.debug("Reading {}".format(template_f))
        nls_tmpl = open(template_f, "r")
        LOGGER.debug("Writing {}".format(en_us_txt))
        nls      = open(en_us_txt,  "w")
        nls.write("# From: {}\n".format(template_f))
        for line in nls_tmpl:
            nls.write(line)
        nls_tmpl.close()
        # Get all the indexes and write the nls.
        nls.write("# End: {}\n\n".format(template_f))
        msg_cnt = 0
        nls.write("# Start: Internal Messages:\n")
        for message in get_messages():
            nls.write("NMESSAGE-{} = {}\n".format(msg_cnt,message))
            msg_cnt += 1
        nls.write("# End: Internal Messages:\n\n")
        nls.write("# Start: Custom Messages:\n")
        ids = list()
        if self.messages is None:
            self.messages = list()
            self.messages.append({'id':0, 'title':"Default"})
            LOGGER.warning("No User Messages, define some in Configuration if desired")
        else:
            for message in self.messages:
                if not 'id' in message:
                    LOGGER.error("message id not defined, please define as a integer")
                    continue
                if message['id'] == '':
                    LOGGER.error("message id='{}' is empty, please define as a unique integer".format(message['id']))
                    continue
                try:
                    id = int(message['id'])
                except:
                    LOGGER.error("message id={} is not an int".format(message['id']))
                    st = False
                    continue
                LOGGER.debug(f'MESSAGE:id={id}')
                ids.append(id)
                if 'message' not in message or message['message'] == '':
                    message['message'] = message['title']
                LOGGER.debug('message={}'.format(message))
                nls.write("MID-{} = {}\n".format(message['id'],message['title']))
        #
        nls.write("# End: Custom Messages:\n\n")

        nls.write("# Start: Service Nodes\n")
        svc_cnt = 0
        nls.write("NFYN--1 = Unknown\n")
        if self.service_nodes is not None:
            for pd in self.service_nodes:
                nls.write("NFYN-{} = {}\n".format(pd['index'],pd['name']))
                svc_cnt += 1
        nls.write("# End: Service Nodes\n\n")
        config_info_nr = [
            '<h3>Create ISY Network Resources</h3>',
            '<p>For messages that contain a larger body use ISY Network Resources. More information available at <a href="https://github.com/jimboca/udi-poly-notification/blob/master/README.md#rest-interface" target="_ blank">README - REST Interface</a>'
            '<ul>'
        ]
        config_info_rest = [
            '<h3>Sending REST Commands</h3>',
            '<p>Pass /send with node=the_node'
            '<p>By default it is sent based on the current selected params of that node for device and priority.'
            '<ul>'
        ]
        # Call the write profile on all the nodes.
        nls.write("# Start: Custom Service Nodes:\n")
        # This is a list of all possible devices we can select, they are provided by the service nodes
        self.devices = list()
        for node in self.poly.nodes():
            if node.name != self.name:
                # We have to wait until the node is done initializing since
                # we can get here before the node is ready.
                cnt = 60
                while node.init_st() is None and cnt > 0:
                    LOGGER.warning(f'Waiting for {node.name} to initialize, timeout in {cnt} seconds...')
                    time.sleep(1)
                    cnt -= 1
                if node.init_st():
                    if cnt < 60:
                        LOGGER.warning(f'{node.name} is initialized...')
                    LOGGER.info('node={} id={}'.format(node.name,node.id))
                    node.write_profile(nls)
                    config_info_nr.append(node.config_info_nr())
                    config_info_rest.append(node.config_info_rest())
                else:
                    LOGGER.error( 'Node {} failed to initialize init_st={}'.format(node.name, node.init_st()))
                    #st = False
        nls.write("\n# Start: End Service Nodes:\n")
        LOGGER.debug(f'st={st}')
        if st is False:
            LOGGER.error('Not all nodes initialized, can not write profile')
            return
        LOGGER.debug("Closing {}".format(en_us_txt))
        nls.close()
        config_info_rest.append('</ul>')
        self.config_info = config_info_nr + config_info_rest
        s = "\n"
        #
        # SEt the Custom Config Doc
        #
        self.poly.setCustomParamsDoc(s.join(self.config_info))
        #
        # editor/custom.xml
        #
        # The subset string for message id's
        full_subset_str = ",".join(map(str,ids))
        LOGGER.debug(f"MESSAGE:full_subset_str={full_subset_str}")
        subset_str = get_subset_str(ids)
        LOGGER.debug(f"MESSAGE:subset_str={subset_str}")
        # Open the output editors fileme
        editor_f   = "profile/editor/custom.xml"
        make_file_dir(editor_f)
        # Open the template, and read into a string for formatting.
        template_f = 'template/editor/custom.xml'
        LOGGER.debug("Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Write the editors file with our info
        LOGGER.debug("Writing {}".format(editor_f))
        editor_h = open(editor_f, "w")
        editor_h.write(data.format(full_subset_str,subset_str,(msg_cnt-1),(svc_cnt-1)))
        editor_h.close()
        #
        # Send it to the ISY
        #
        if st:
            self.poly.updateProfile()
        self.write_profile_lock.release()
        return st

    def handler_log_level(self,level):
        LOGGER.info(f'enter: level={level}')
        if level['level'] < 10:
            LOGGER.info("Setting basic config to DEBUG...")
            LOG_HANDLER.set_basic_config(True,logging.DEBUG)
            slevel = logging.DEBUG
        else:
            LOGGER.info("Setting basic config to WARNING...")
            LOG_HANDLER.set_basic_config(True,logging.WARNING)
            slevel = logging.WARNING
        #logging.getLogger('requests').setLevel(slevel)
        #logging.getLogger('urllib3').setLevel(slevel)
        LOGGER.info(f'exit: slevel={slevel}')

    def set_message(self,val):
        self.setDriver('GV2', val)

    def set_sys_short(self,val):
        #self.setDriver('GV3', val)
        self._sys_short_msg = val
        
    def get_sys_short(self):
        return self._sys_short_msg if self._sys_short_msg is not None else "NOT_DEFINED"
        
    def cmd_build_profile(self,command):
        LOGGER.info('cmd_build_profile:')
        st = self.write_profile()
        if st:
            self.poly.updateProfile()
        return st

    def cmd_install_profile(self,command):
        LOGGER.info('cmd_install_profile:')
        st = self.poly.updateProfile()
        return st

    def cmd_set_message(self,command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_message(val)

    def cmd_set_sys_short(self,command):
        LOGGER.debug(f'command={command}')
        self.set_sys_short(command.get('value'))

    def rest_ghandler(self,command,params,data=None):
        if not self.handler_params_st:
            LOGGER.error("Disabled until acknowledge instructions are completed.")
        mn = 'rest_ghandler'
        LOGGER.debug('command={} params={} data={}'.format(command,params,data))

        # Receive error?
        if command == "receive_error":
            LOGGER.error(params % data)
            self.setDriver("GV1",3)
            return True

        self.setDriver("GV1",1)
        # data has body then we only have text data, so make that the message
        if not data is None and 'body' in data:
            data = {'message': data['body']}
        
        #
        # Params override body data
        #
        for key, value in params.items():
            data[key] = value
        LOGGER.debug('data={}'.format(data))
        if command == '/send':
            if not 'node' in data:
                LOGGER.error( 'node not passed in for send params: {}'.format(data))
                return False
            fnode = self.get_service_node(data['node'])
            if fnode is False:
                LOGGER.error( 'unknown service node "{}"'.format(data['node']))
                return False
            subject = None
            if 'subject' in data:
                data['title'] = data['subject']
            return fnode['node'].rest_send(data)

        LOGGER.error('Unknown command "{}"'.format(command))
        return False

    id = 'controller'
    commands = {
        'SET_MESSAGE': cmd_set_message,
        'SET_SYS_CUSTOM': cmd_set_sys_short,
        #'SET_SHORTPOLL': cmd_set_short_poll,
        #'SET_LONGPOLL':  cmd_set_long_poll,
        'QUERY': query,
        'BUILD_PROFILE': cmd_build_profile,
        'INSTALL_PROFILE': cmd_install_profile,
    }

