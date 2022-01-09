"""
  Notification Controller Node
"""

from udi_interface import Node,LOGGER,Custom,LOG_HANDLER
from nodes import *
import logging
from node_funcs import *
from PolyglotREST import polyglotRESTServer,polyglotSession
from copy import deepcopy
import re
import time
import fnmatch
import os

class Controller(Node):
    """
    """
    def __init__(self, poly, primary, address, name):
        """
        """
        super(Controller, self).__init__(poly, primary, address, name)
        self.hb = 0
        self.messages = None
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
        self.handler_start_st      = None
        self.handler_params_st     = None
        self.handler_data_st       = None
        self.handler_typed_data_st = None
        self.handler_config_st     = None
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
            LOGGER.error('Failed to add node address')
        return anode

    def handler_start(self):
        LOGGER.info(f"Started Notification NodeServer {self.poly.serverdata['version']}")
        self.heartbeat()
        self.handler_start_st = True

    def handler_config_done(self):
        LOGGER.debug("enter")
        # This is supposed to only run after we have received and
        # processed all config data, just add a check here.
        cnt = 60
        while ((self.handler_start_st is None
            or self.handler_params_st is None
            or self.handler_data_st is None
            or self.handler_typed_data_st is None)
            and cnt > 0
        ):
            LOGGER.warning(f'Waiting for all handlers to complete start={self.handler_start_st} params={self.handler_params_st} data={self.handler_data_st} typed_data={self.handler_typed_data_st} cnt={cnt}')
            time.sleep(1)
            cnt -= 1
        if cnt == 0:
            LOGGER.error('Timed out waiting for all handlers to complete')
            self.poly.stop()
            return
        if self.handler_params_st:
            self.rest = polyglotRESTServer('8199',LOGGER,ghandler=self.rest_ghandler)
            # TODO: Need to monitor thread and restart if it dies
            self.rest.start()
        else:
            LOGGER.error(f'Unable to start REST Server until config params are correctd ({self.handler_params_st})')
        #
        # Always rebuild profile on startup?
        #
        if self.first_run:
            self.write_profile()
        self.handler_config_st = True
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
        self.rest.stop()
        LOGGER.info('Oh God I\'m being deleted. Nooooooooooooooooooooooooooooooooooooooooo.')

    def stop(self):
        LOGGER.debug('NodeServer stopping.')
        self.rest.stop()
        LOGGER.debug('NodeServer stopped.')

    def setDriver(self,driver,value):
        self.driver[driver] = value
        super(Controller, self).setDriver(driver,value)

    def getDriver(self,driver):
        if driver in self.driver:
            return self.driver[driver]
        else:
            return super(Controller, self).getDriver(driver)

    def get_service_node(self,sname):
        for item in self.service_nodes:
            if item['name'] == sname or item['node'].address == sname or item['node'].name == sname:
                return item['node']
        l = list()
        for item in self.service_nodes:
            l.extend([item['name'],item['node'].address,item['node'].name])
        LOGGER.error(f"Unknown service node {sname} must be one of: " + ", ".join(l))
        return False

    def get_current_message(self):
        i = self.getDriver('GV2')
        LOGGER.info('i={}'.format(i))
        if i is None:
            i = 0
        else:
            i = int(i)
        for msg in self.messages:
            if int(msg['id']) == i:
                return msg
        LOGGER.error('id={} not found in: {}'.format(i,self.messages))
        return { id: 0, 'title': 'Unknown', 'message': 'Undefined message {}'.format(i)}

    def get_typed_name(self,name):
        typedConfig = self.polyConfig.get('typedCustomData')
        if not typedConfig:
            return None
        return typedConfig.get(name)

    def get_message_node_address(self,id):
        return get_valid_node_address('mn_'+id)

    def get_service_node_address(self,id):
        return get_valid_node_address('po_'+id)

    def init_typed(self):
        self.TypedParams.load(
            [
                {
                    'name': 'messages',
                    'title': 'Messages',
                    'desc': 'Your Custom Messages',
                    'isList': True,
                    'params': [
                        {
                            'name': 'id',
                            'title': "ID (Must be integer, should never change!)",
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
                    'title': 'Assistant Relay Service Nodes',
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
            ],
            True
        )

    def handler_data(self,data):
        LOGGER.debug(f'Enter data={data}')
        if data is None:
            self.handler_data_st = False
        else:
            self.Data.load(data)
            self.handler_data_st = True

    def handler_params(self, data):
        LOGGER.debug("Enter data={}".format(data))
        self.Params.load(data)
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
        self.handler_params_st = st

    def handler_typed_data(self, data):
        LOGGER.debug("Enter data={}".format(data))
        self.TypedData.load(data)
        if data is None:
            self.handler_typed_data_st = False
            return False

        el = list()

        self.messages = data.get('messages',el)
        LOGGER.info('messages={}'.format(self.messages))
        if len(self.messages) == 0:
            LOGGER.info('No messages')

        #
        # Check the pushover configs are all good
        #
        pushover = data.get('pushover',el)
        nodes    = data.get('notify',el)
        pnames   = dict()
        snames   = list()
        err_list = list()
        LOGGER.info('pushover={}'.format(pushover))
        if len(pushover) == 0:
            LOGGER.warning("No Pushover Entries in the config: {}".format(pushover))
            pushover = None
        else:
            for pd in pushover:
                sname = pd['name']
                snames.append(sname) # List for checking later
                address = self.get_service_node_address(sname)
                if not address in pnames:
                    pnames[address] = list()
                pnames[address].append(sname)
            for address in pnames:
                if len(pnames[address]) > 1:
                    err_list.append("Duplicate pushover names for {} items {} from {}".format(len(pnames[address]),address,",".join(pnames[address])))
        #
        # Check the message nodes are all good
        #
        if len(nodes) == 0:
            LOGGER.warning('No Notify Nodes')
        else:
            # First check that nodes are valid before we try to add them
            mnames = dict()
            for node in nodes:
                address = self.get_message_node_address(node['id'])
                if not address in mnames:
                    mnames[address] = list()
                mnames[address].append(node['id'])
                # And check that service node name is known
                sname = node['service_node_name']
                if not sname in snames:
                    err_list.append("Unknown service node name {} in message node {} must be one of {}".format(sname,node['id'],",".join(snames)))
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
                self.Notices['msg'+cnt]
                cnt += 1
            self.Notices['typed_data'] = f'There are {ecount} errors found please fix Errors and restart.'
            self.handler_typed_data_st = False
            return

        if pushover is not None:
            self.pushover_session = polyglotSession(self,"https://api.pushover.net",LOGGER)
            for pd in pushover:
                snode = self.add_node(Pushover(self, self.address, self.get_service_node_address(pd['name']), get_valid_node_name('Service Pushover '+pd['name']), self.pushover_session, pd))
                self.service_nodes.append({ 'name': pd['name'], 'node': snode, 'index': len(self.service_nodes)})
                LOGGER.info('service_nodes={}'.format(self.service_nodes))

        # TODO: Save service_nodes names in customParams
        if nodes is not None:
            save = True
            LOGGER.debug('Adding Notify Nodes...')
            for node in nodes:
                # TODO: make sure node.service_node_name is valid, and pass service node type (pushover) to addNode, or put in node dict
                self.add_node(Notify(self, self.address, self.get_message_node_address(node['id']), 'Notify '+get_valid_node_name(node['name']), node))

        # When data changes build the profile, except when first starting up since
        # that will be done by the config handler
        if not self.first_run:
            self.write_pofile()
        self.handler_typed_data_st = True

    def write_profile(self):
        pfx = 'write_profile'
        LOGGER.info('enter')
        # Good unless there is an error.
        st = True
        #
        # First clean out all files we created
        #
        for dir in ['profile/editor', 'profile/nodedef']:
            LOGGER.debug('Cleaning: {}'.format(dir))
            for file in os.listdir(dir):
                LOGGER.debug(file)
                path = dir+'/'+file
                if os.path.isfile(path) and file != 'editors.xml' and file != 'nodedefs.xml':
                    LOGGER.debug('Removing: {}'.format(path))
                    os.remove(path)
        # Write the profile Data
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
        for message in self.messages:
            try:
                id = int(message['id'])
            except:
                LOGGER.error("message id={} is not an int".format(message['id']))
                st = False
                continue
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
        for pd in self.service_nodes:
            nls.write("NFYN-{} = {}\n".format(pd['index'],pd['name']))
            svc_cnt += 1
        nls.write("# End: Service Nodes\n\n")
        config_info_nr = [
            '<h3>Create ISY Network Resources</h3>',
            '<p>For messages that contain a larger body use ISY Network Resources. More information available at <a href="https://github.com/jimboca/udi-poly-notification/blob/master/README.md#rest-interface" target="_ blank">README - REST Interfae</a>'
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
                    LOGGER.warning('Waiting for {} to initialize...'.format(node.name))
                    time.sleep(1)
                    cnt -= 1
                if node.init_st():
                    LOGGER.info('node={} id={}'.format(node.name,node.id))
                    node.write_profile(nls)
                    config_info_nr.append(node.config_info_nr())
                    config_info_rest.append(node.config_info_rest())
                else:
                    LOGGER.error( 'Node {} failed to initialize init_st={}'.format(node.name, node.init_st()))
                    st = False
        nls.write("# Start: End Service Nodes:\n")
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
        subset_str = get_subset_str(ids)
        full_subset_str = ",".join(map(str,ids))
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

    def rest_ghandler(self,command,params,data=None):
        if not self.handler_params_st:
            LOGGER.error("Disabled until acknowledge instructions are completed.")
        mn = 'rest_ghandler'
        LOGGER.debug('command={} params={} data={}'.format(command,params,data))
        # data has body then we only have text data, so make that the message
        if 'body' in data:
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
            return fnode.rest_send(data)

        LOGGER.error('Unknown command "{}"'.format(command))
        return False

    id = 'controller'
    commands = {
        'SET_MESSAGE': cmd_set_message,
        #'SET_SHORTPOLL': cmd_set_short_poll,
        #'SET_LONGPOLL':  cmd_set_long_poll,
        'QUERY': query,
        'BUILD_PROFILE': cmd_build_profile,
        'INSTALL_PROFILE': cmd_install_profile,
    }
    drivers = [
        {'driver': 'ST',  'value': 1,  'uom': 25}, # Nodeserver status
        {'driver': 'GV2', 'value': 0,  'uom': 25}, # Notification
    ]
