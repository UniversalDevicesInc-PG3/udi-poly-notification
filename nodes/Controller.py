"""
  Notification Controller Node
"""

import polyinterface
from nodes import *
import logging
from node_funcs import *
from PolyglotREST import polyglotRESTServer,polyglotSession
from copy import deepcopy
import re
import time
import fnmatch
import os

LOGGER = polyinterface.LOGGER

class Controller(polyinterface.Controller):
    """
    """
    def __init__(self, polyglot):
        """
        """
        super(Controller, self).__init__(polyglot)
        self.name = 'Notification Controller'
        self.l_name = 'controller'
        self.hb = 0
        self.messages = None
        # List of all service nodes
        self.service_nodes = list()
        # We track our driver values because we need the value before it's been pushed.
        self.driver = {}
        #self.poly.onConfig(self.process_config)

    def start(self):
        """
        """
        # This grabs the server.json data and checks profile_version is up to date
        #serverdata = self.poly.get_server_data()
        #LOGGER.info('Started Notification NodeServer {}'.format(serverdata['version']))
        LOGGER.info('Started Notification NodeServer')
        self.heartbeat()
        self.rest = polyglotRESTServer('8199',LOGGER,ghandler=self.rest_ghandler)
        # TODO: Need to monitor thread and restart if it dies
        self.rest.start()
        self.set_debug_level(self.getDriver('GV1'))
        self.check_params()
        # TODO: Do we have to call this, don't want to beuild the profile on every start.
        self.process_config(self.polyConfig)

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

    def delete(self):
        """
        """
        self.rest.stop()
        LOGGER.info('Oh God I\'m being deleted. Nooooooooooooooooooooooooooooooooooooooooo.')

    def stop(self):
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
            if item['name'] == sname:
                return item
        return False

    def get_current_message(self):
        i = self.getDriver('GV2')
        self.l_info('get_current_message','i={}'.format(i))
        if i is None:
            i = 0
        else:
            i = int(i)
        for msg in self.messages:
            if int(msg['id']) == i:
                return msg
        self.l_error('get_current_message','id={} not found in: {}'.format(i,self.messages))
        return { id: 0, 'title': 'Unknown', 'message': 'Undefined message {}'.format(i)}

    def supports_feature(self, feature):
        if hasattr(self.poly, 'supports_feature'):
            return self.poly.supports_feature(feature)
        return False

    def get_typed_name(self,name):
        typedConfig = self.polyConfig.get('typedCustomData')
        if not typedConfig:
            return None
        return typedConfig.get(name)

    def process_config(self, config):
        typedCustomData = config.get('typedCustomData')
        if not typedCustomData:
            return
        save = False
        self.removeNoticesAll()

        self.messages = typedCustomData.get('messages')
        self.l_debug('process_config','messages={}'.format(self.messages))
        if self.messages is None:
            self.l_debug('process_config','No messages')
        else:
            save = True

        pushover = typedCustomData.get('pushover')
        nodes = typedCustomData.get('notify')
        #
        # Check the pushover configs are all good
        #
        pnames = dict()
        snames = list()
        err_list = list()
        self.l_info('process_config:','pushover={}'.format(pushover))
        if pushover is None or len(pushover) == 0:
            self.l_info('process_config',"No Pushover Entries in the config: {}".format(pushover))
            pushover = None
        else:
            for pd in pushover:
                sname = pd['name']
                snames.append(sname) # List for checking later
                address = self.get_service_node_address(sname)
                if address in pnames:
                    pnames[address].append(sname)
                else:
                    pnames[address] = list(sname)
            for address in pnames:
                if len(pnames[address]) > 1:
                    err_list.append("Duplicate pushover names for {} {} for {}".format(len(pnames[address]),address,",".join(pnames[address])))
        #
        # Check the message nodes are all good
        #
        if nodes is None:
            self.l_debug('process_config','No Notify Nodes')
        else:
            # First check that nodes are valid before we try to add them
            mnames = dict()
            for node in nodes:
                address = self.get_message_node_address(node['id'])
                if address in mnames:
                    mnames[address].append(node['id'])
                else:
                    mnames[address] = list(node['id'])
                # And check that service node name is known
                sname = node['service_node_name']
                if not sname in snames:
                    err_list.append("Unknown service node name {} in message node {} must be one of {}".format(sname,node['id'],",".join(snames)))
            for address in mnames:
                if len(mnames[address]) > 1:
                    err_list.append("Duplicate Notify ids for {} for {}".format(address,",".join(mnames[address])))
        #
        # Any errors, print them and stop
        #
        if len(err_list) > 0:
            for msg in err_list:
                self.l_error('process_config',msg)
                self.addNotice(msg)
            self.addNotice('There are {} errors found please fix Errors and restart'.format(len(err_list)),'ecount')
            return

        if pushover is not None:
            self.appendover_session = polyglotSession(self,"https://api.appendover.net",LOGGER)
            for pd in pushover:
                snode = self.addNode(Pushover(self, self.address, self.get_service_node_address(pd['name']), get_valid_node_name('Service Pushover '+pd['name']), self.appendover_session, pd))
                self.service_nodes.append({ 'name': pd['name'], 'node': snode, 'index': len(self.service_nodes)})
                self.l_info('process_config','service_nodes={}'.format(self.service_nodes))

        # TODO: Save service_nodes names in customParams
        if nodes is not None:
            save = True
            self.l_debug('process_config','Adding Notify Nodes...')
            for node in nodes:
                # TODO: make sure node.service_node_name is valid, and pass service node type (pushover) to addNode, or put in node dict
                self.addNode(Notify(self, self.address, self.get_message_node_address(node['id']), 'Notify '+get_valid_node_name(node['name']), node))

        if save:
            done = False
            while (not done):
                try:
                    self.write_profile()
                    done = True
                except RuntimeError:
                    # Occsionally happens because self.nodes gets updated while write_profile is running...
                    pass
                except:
                    # TODO: Need to set error on controller for this?
                    self.l_error('process_config:','write_profile failed: ',exc_info=True)
                    return
            self.poly.installprofile()

    def get_message_node_address(self,id):
        return get_valid_node_address('mn_'+id)

    def get_service_node_address(self,id):
        return get_valid_node_address('po_'+id)

    def write_profile(self):
        pfx = 'write_profile'
        self.l_info(pfx,'')
        #
        # First clean out all files we created
        #
        for dir in ['profile/editor', 'profile/nodedef']:
            self.l_info(pfx,'Cleaning: {}'.format(dir))
            for file in os.listdir(dir):
                self.l_info(pfx,file)
                path = dir+'/'+file
                if os.path.isfile(path) and file != 'editors.xml' and file != 'nodedefs.xml':
                    self.l_info(pfx,'Removing: {}'.format(path))
                    os.remove(path)
        # Write the profile Data
        #
        # There is only one nls, so read the nls template and write the new one
        #
        en_us_txt = "profile/nls/en_us.txt"
        make_file_dir(en_us_txt)
        template_f = "template/nls/en_us.txt"
        self.l_info(pfx,"Reading {}".format(template_f))
        nls_tmpl = open(template_f, "r")
        self.l_info(pfx,"Writing {}".format(en_us_txt))
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
            nls.write("NMESSAGE-{}: {}\n".format(msg_cnt,message))
            msg_cnt += 1
        nls.write("# End: Internal Messages:\n\n")
        nls.write("# Start: Custom Messages:\n")
        ids = list()
        for message in self.messages:
            try:
                id = int(message['id'])
            except:
                self.l_error(pfx,"message id={} is not an int".format(message['id']))
                continue
            ids.append(id)
            if 'message' not in message or message['message'] == '':
                message['message'] = message['title']
            self.l_info(pfx, 'message={}'.format(message))
            nls.write("MID-{}: {}\n".format(message['id'],message['title']))
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
            '<p>For messages that contain a larger body use ISY Network Resources'
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
        for node_name in self.nodes:
            node = self.nodes[node_name]
            if node.name != self.name:
                # We have to wait until the node is done initializing since
                # we can get here before the node is ready.
                cnt = 0
                while node.init_st() is None:
                    self.l_info(pfx, 'Waiting for {} to initialize...'.format(node_name))
                    time.sleep(1)
                    cnt += 1
                    # Max is 10 minutes
                    if cnt > 60:
                        self.l_error('write_profile','{} time out waiting for initialize'.format(node_name))
                if node.init_st():
                    self.l_info('write_profile','node={} id={}'.format(node_name,node.id))
                    node.write_profile(nls)
                    if node.oid == 'pushover':
                        # TODO: Move creating node info insdie nodes instead of here...
                        config_info_rest.append(
                            '<li>curl -d \'{{"node":"{0}", "message":"The Message", "subject":"The Subject" -H "Content-Type: application/json}}\'" -X POST {1}/send'
                            .format(node.address,self.rest.listen_url)
                        )
                        config_info_nr.append(
                            '<li>http POST Host:{0} Port:{1} Path:/send?node={2}&Subject=My+Subject&monospace=1&device=1&priority=2'
                            .format(self.rest.ip,self.rest.listen_port,node.address)
                        )
                else:
                    self.l_error(pfx, 'Node {} failed to initialize init_st={}'.format(node_name, node.init_st()))
        nls.write("# Start: End Service Nodes:\n")
        self.l_info(pfx,"Closing {}".format(en_us_txt))
        nls.close()
        config_info_rest.append('</ul>')
        config_info_nr = config_info_nr + [
            '</ul>',
            '<p>The parms in the Path can be any of the below, if the param is not passed then the default from the node will be used'
            '<table>',
            '<tr><th>Name<th>Value<th>Description',

            '<tr><td>monospace<td>1<td>use Monospace Font',
            '<tr><td>&nbsp;<td>0<td>Normal Font',

            '<tr><td>priority<td>0<td>Lowest',
            '<tr><td>&nbsp;<td>1<td>Low',
            '<tr><td>&nbsp;<td>2<td>Normal',
            '<tr><td>&nbsp;<td>3<td>High',
            '<tr><td>&nbsp;<td>4<td>Emergency',

            '<tr><td>html<td>1<td>Enable html',
            '<tr><td>&nbsp;<td>0<td>No html',

            '<tr><td>device<td>0<td>All Devices',
            '<tr><td>&nbsp;<td>1<td>Next device in the list, and so on ...',

            '</table>'
        ]
        self.config_info = config_info_nr + config_info_rest
        s = "\n"
        cstr = s.join(self.config_info)
        self.poly.add_custom_config_docs(cstr,True)
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
        self.l_info(pfx,"Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Write the editors file with our info
        self.l_info(pfx,"Writing {}".format(editor_f))
        editor_h = open(editor_f, "w")
        editor_h.write(data.format(full_subset_str,subset_str,(msg_cnt-1),(svc_cnt-1)))
        editor_h.close()

        return True

    def check_params(self):
        """
        This is an example if using custom Params for user and password and an example with a Dictionary
        """
        # Remove all existing notices
        self.removeNoticesAll()

        # Make sure they acknowledge
        custom_params = self.polyConfig['customParams']
        self.l_info('check_params', custom_params)
        ack = 'acknowledge'
        val = None
        if ack in custom_params:
            val = custom_params[ack]
        else:
            custom_params[ack] = ""
            self.addCustomParam(custom_params)
        if val != 'I understand and agree':
            self.addNotice('Before using you must follow the link to <a href="https://github.com/jimboca/udi-poly-notification/blob/master/ACKNOWLEDGE.md" target="_blank">acknowledge</a>')
            return False

        params = [
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
                        'title': 'Name for reference, used as node name.<br>Must be 8 characters or less.',
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
                        'title': "ID for node, never change,<br>8 characters or less",
                        'isRequired': True
                    },
                    {
                        'name': 'name',
                        'title': 'Name for node',
                        'isRequired': True
                    },
                    {
                        'name': 'service_node_name',
                        'title': "Service Node Name<br>Must match an existing Service Node Name",
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
        ]
        self.poly.save_typed_params(params)

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

    def set_message(self,val):
        self.setDriver('GV2', val)

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

    def cmd_process_config(self,command):
        LOGGER.info('cmd_process_config:')
        self.process_config(self.polyConfig)

    def cmd_build_profile(self,command):
        LOGGER.info('cmd_build_profile:')
        st = self.write_profile()
        if st:
            self.poly.installprofile()
        return st

    def cmd_install_profile(self,command):
        LOGGER.info('cmd_install_profile:')
        st = self.poly.installprofile()
        return st

    def cmd_set_debug_mode(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_debug_mode",val)
        self.set_debug_level(val)

    def cmd_set_message(self,command):
        val = int(command.get('value'))
        self.l_info("cmd_set_message",val)
        self.set_message(val)

    def l_info(self, name, string):
        LOGGER.info("%s:%s: %s" %  (self.id,name,string))

    def l_error(self, name, string, exc_info=False):
        LOGGER.error("%s:%s:%s: %s" % (self.id,self.name,name,string), exc_info=exc_info)

    def l_warning(self, name, string):
        LOGGER.warning("%s:%s: %s" % (self.id,name,string))

    def l_debug(self, name, string, exc_info=False):
        LOGGER.debug("%s:%s: %s" % (self.id,name,string), exc_info=exc_info)

    def rest_ghandler(self,command,params,data=None):
        mn = 'rest_ghandler'
        self.l_info(mn,' command={} params={} data={}'.format(command,params,data))
        # data has body then we only have text data, so make that the message
        if 'body' in data:
            data = {'message': data['body']}
        #
        # Params override body data
        #
        for key, value in params.items():
            data[key] = value
        self.l_info(mn,' data={}'.format(data))
        if command == '/send':
            if not 'node' in data:
                self.l_error(mn, 'node not passed in for send params: {}'.format(data))
                return False
            node = data['node']
            if not node in self.nodes:
                self.l_error(mn, 'unknown node "{}"'.format(node))
                return False
            subject = None
            if 'subject' in data:
                data['title'] = data['subject']
            return self.nodes[node].rest_send(data)

        self.l_error(mn, 'Unknown command "{}"'.format(command))
        return False

    id = 'controller'
    commands = {
        'SET_MESSAGE': cmd_set_message,
        'SET_DM': cmd_set_debug_mode,
        #'SET_SHORTPOLL': cmd_set_short_poll,
        #'SET_LONGPOLL':  cmd_set_long_poll,
        'QUERY': query,
        'PROCESS_CONFIG': cmd_process_config,
        'BUILD_PROFILE': cmd_build_profile,
        'INSTALL_PROFILE': cmd_install_profile,
    }
    drivers = [
        {'driver': 'ST',  'value': 1,  'uom': 2},  # Nodeserver status
        {'driver': 'GV1', 'value': 30, 'uom': 25}, # Debug (Log) Mode, default=30 Warning
        {'driver': 'GV2', 'value': 0,  'uom': 25}, # Notification
    ]
