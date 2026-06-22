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
import markdown2
from distutils.version import StrictVersion
from telegram_funcs import (
    sanitize_telegram_row,
    sanitize_users,
    telegram_ok,
    telegram_description,
    chat_id_from_updates,
    coerce_chat_id,
    bot_link_from_get_me,
    external_link,
)
from dev_settings import (
    resolve_edition,
    DevSafeCustom,
    custom_data_log_label,
    dev_edition_override_active,
    licensed_edition,
)

_DEV_EDITION_NOTICE_KEYS = ('dev_edition_override', 'dev_edition_mismatch')

PROFILE_NODE_WAIT_MAX = 180
_SLOT_PREFIX_RE = re.compile(r'^n\d+_(.+)$')

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
        self.edition = self.poly.pg3init.get('edition', 'Free')
        self.has_sys_editor_full = True if (
            StrictVersion(self.poly.pg3init['isyVersion']) >= StrictVersion('5.6.2')
            # All versions since isPG3x was added to PG3 and PG3x works with sys_notify_full
            # But, now one more version to full support the data coming from the IoX http post
            and (
                'isPG3x' in self.poly.pg3init
                and ( 
                    (self.poly.pg3init['isPG3x'] is True and StrictVersion(self.poly.pg3init['pg3Version']) >= StrictVersion('3.1.31'))
                    or (self.poly.pg3init['isPG3x'] is not True and StrictVersion(self.poly.pg3init['pg3Version']) >= StrictVersion('3.1.23'))
                    ) 
                )
            ) else False
        self.sys_notify_editor = '_sys_notify_full' if self.has_sys_editor_full else '_sys_notify_short'
        self.sys_notify_uom_t  = 147 if self.has_sys_editor_full else 145
        LOGGER.warning(f'has_sys_editor_full={self.has_sys_editor_full} editor={self.sys_notify_editor}')
        self.drivers = [
            {'driver': 'ST',  'value': 1,  'uom': 25, 'name': "Nodeserver Status"},
            {'driver': 'GV1', 'value': 0,  'uom': 25, 'name': 'REST Status'},
            {'driver': 'GV2', 'value': 0,  'uom': 25, 'name': 'Message'},
        ]
        self.uuid    = self.poly.pg3init['uuid']
        self.nodename = os.uname().nodename
        # List of all service nodes
        self.service_nodes = list()
        self.first_run = True
        self.ready     = False
        self.profile_installed = False
        self.profile_nodes_written = set()
        self.pending_profile_nodes = set()
        self.n_queue = []
        # We track our driver values because we need the value before it's been pushed.
        # Is this necessary anymore in PG3?
        self.driver = {}
        self.Notices         = Custom(poly, 'notices')
        self.Params          = Custom(poly, 'customparams')
        self.Data            = DevSafeCustom(poly, 'customdata')
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
        poly.subscribe(poly.DISCOVER,               self.handler_discover_telegram)
        self.handler_start_st      = None
        self.handler_params_st     = None
        self.handler_data_st       = None
        self.handler_typed_data_st = None
        self.handler_config_st     = None
        self.write_profile_lock = Lock() # Lock for syncronizing acress threads
        self._telegram_typed_save_in_progress = False
        self._pending_typed_data = None
        self.telegramub_session = None
        self.init_typed()
        poly.ready()
        self.Notices.clear()
        poly.addNode(self, conn_status="ST")
        self._install_poly_address_hooks()

    def slot_prefixed_address(self, address):
        try:
            profile_num = int(self.poly.profileNum)
        except (TypeError, ValueError):
            return None
        return 'n{:03d}_{}'.format(profile_num, address)

    def resolve_node_address(self, address):
        nodes = self.poly.nodes_internal
        if address is None or address == 'all':
            return address
        if address in nodes:
            return address
        prefixed = self.slot_prefixed_address(address)
        if prefixed and prefixed in nodes:
            LOGGER.debug('Resolved node address {} -> {}'.format(address, prefixed))
            return prefixed
        match = _SLOT_PREFIX_RE.match(address)
        if match:
            bare = match.group(1)
            if bare in nodes:
                LOGGER.debug('Resolved node address {} -> {}'.format(address, bare))
                return bare
        return address

    def register_node_aliases(self, node):
        nodes = self.poly.nodes_internal
        prefixed = self.slot_prefixed_address(node.address)
        if prefixed and prefixed != node.address:
            nodes[prefixed] = node
        match = _SLOT_PREFIX_RE.match(node.address)
        if match:
            bare = match.group(1)
            if bare not in nodes:
                nodes[bare] = node

    def link_config_node_aliases(self, config):
        if not config or 'nodes' not in config:
            return
        nodes = self.poly.nodes_internal
        for node in config['nodes']:
            addr = node.get('address')
            if not addr:
                continue
            match = _SLOT_PREFIX_RE.match(addr)
            if match:
                bare = match.group(1)
                if bare in nodes and addr not in nodes:
                    nodes[addr] = nodes[bare]
            else:
                prefixed = self.slot_prefixed_address(addr)
                if prefixed and prefixed not in nodes and addr in nodes:
                    nodes[prefixed] = nodes[addr]

    def _install_poly_address_hooks(self):
        if getattr(self.poly, '_address_hooks_installed', False):
            return
        controller = self
        handle_input = self.poly._handleInput

        def _handleInput(key, item, published):
            if (
                key in ('command', 'query', 'status')
                and isinstance(item, dict)
                and item.get('address') not in (None, 'all')
            ):
                resolved = controller.resolve_node_address(item['address'])
                if resolved != item['address']:
                    item = dict(item)
                    item['address'] = resolved
            return handle_input(key, item, published)

        self.poly._handleInput = _handleInput
        self.poly._address_hooks_installed = True

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
        else:
            self.register_node_aliases(anode)
        return anode

    def handler_start(self):
        LOGGER.info(f"Started Notification NodeServer {self.poly.serverdata['version']}")
        self.poly.updateProfile()
        self.heartbeat()
        self.handler_start_st = True

    def handler_config_done(self):
        LOGGER.debug("enter")
        self.handler_config_st = True
        config = self.poly.getConfig()
        if config:
            self.link_config_node_aliases(config)
        self._update_edition()
        self._flush_pending_typed_data()
        LOGGER.debug("exit")

    def add_node_done(self):
        LOGGER.debug("enter")
        configurationHelp = './POLYGLOT_CONFIG.md';
        if os.path.isfile(configurationHelp):
            cfgdoc = markdown2.markdown_path(configurationHelp)
            self.poly.setCustomParamsDoc(cfgdoc)        
        if self.has_sys_editor_full:
            if (
                (self.poly.pg3init['isPG3x'] is True and StrictVersion(self.poly.pg3init['pg3Version']) == StrictVersion('3.1.31'))
                or (self.poly.pg3init['isPG3x'] is not True and StrictVersion(self.poly.pg3init['pg3Version']) == StrictVersion('3.1.23'))
            ):
                msg = f"This version of PG3 {self.poly.pg3init['pg3Version']} will not work properly with Pushover or UDPortal nodes, Please upgrade modules and restart PG3. isyVersion={self.poly.pg3init['isyVersion']} isPG3x={self.poly.pg3init['isPG3x']} pg3Version={self.poly.pg3init['pg3Version']}"
                self.Notices['upgrade'] = msg
                LOGGER.error(msg)                
        else:
            msg = f"Please upgrade modules and reboot to allow usage of Full Custom System Notifications. isyVersion={self.poly.pg3init['isyVersion']} isPG3x={self.poly.pg3init['isPG3x']} pg3Version={self.poly.pg3init['pg3Version']} See <a href='https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/blob/master/README.md#system-customizations' target='_ blank'>System Customizations</a>"
            self.Notices['upgrade'] = msg
            LOGGER.warning(msg)
        cnt = 120
        waited = 0
        warn_after = 5
        warned_wait = False
        while (cnt > 0 and (
            self.handler_start_st is None
            or self.handler_params_st is None
            or self.handler_data_st is None
            or self.handler_typed_data_st is None)):
            msg = (
                f'Waiting for all handlers to complete start={self.handler_start_st} '
                f'params={self.handler_params_st} data={self.handler_data_st} '
                f'typed_data={self.handler_typed_data_st} cnt={cnt}'
            )
            if waited >= warn_after:
                LOGGER.warning(msg)
                warned_wait = True
            else:
                LOGGER.debug(msg)
            time.sleep(1)
            cnt -= 1
            waited += 1
        if cnt == 0:
            LOGGER.error('Timed out waiting for all handlers to complete')
            LOGGER.error('Exiting...')
            self.poly.stop()
        else:
            if warned_wait:
                LOGGER.warning(f'Wait for all handlers cleared after {waited} seconds')
            elif waited > 0:
                LOGGER.debug(f'Wait for all handlers cleared after {waited} seconds')
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

    def _query_content(self, query, uom):
        if not query or not isinstance(query, dict):
            return None
        msg = query.get(f'Content.uom{uom}')
        if msg is None:
            msg = query.get(f'.uom{uom}')
        return msg

    def _notice_missing_notification_content(self, query):
        LOGGER.error(
            'Notification content missing in command query (expected Content.uom147, .uom147, Content.uom145, or .uom145): %s',
            query,
        )
        self.Notices['missing_notification_content'] = (
            'Notification content was missing. Check your ISY program notification fields '
            '(subject/body) and try again.'
        )

    def _missing_notification_message(self):
        return {
            'subject': 'ERROR',
            'body': 'No message passed in',
            'message': 'ERROR\nNo message passed in',
        }

    def get_message_short(self, query):
        if not query or not isinstance(query, dict):
            return None
        msg = self._query_content(query, 145)
        if msg is None or str(msg).strip() == '':
            return None
        # Entire message and title is first line, body is the rest
        sp = msg.split("\n", 1)
        ret = {'message': msg, 'subject': sp[0]}
        if len(sp) > 1:
            ret['body'] = sp[1]
        else:
            ret['body'] = ' '
        return ret

    # New: 'message': {'notification': {'formatted': {'mimetype': 'text/plain', 'from': '', 'subject': 'program[0]: node[#]=node[#] null null received', 'body': ''}, '@_id': '1'}
    def get_message_long(self,query):
        msg = self._query_content(query, 147)
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
    def get_message_from_query(self, query):
        LOGGER.debug(f'enter query={query}')
        reboot = False
        if self.has_sys_editor_full:
            # New _sys_editor_full
            msg = self.get_message_long(query)
            if msg is None:
                # May need a reboot to get proper uom, but for now only UDMobile
                reboot = True
                # Check for the old one
                msg = self.get_message_short(query)
                if msg is None:
                    self._notice_missing_notification_content(query)
                    msg = self._missing_notification_message()
        else:
            # Old _sys_editor_short
            msg = self.get_message_short(query)
            if msg is None:
                # New _sys_editor_full
                msg = self.get_message_long(query)
                if msg is None:
                    self._notice_missing_notification_content(query)
                    msg = self._missing_notification_message()
        msg['reboot'] = reboot
        LOGGER.debug(f'exit msg={msg}')
        return msg
    
    def get_service_node(self,sname):
        LOGGER.debug(f'start: {sname}')
        for item in self.service_nodes:
            LOGGER.debug(f'  check: {item}')
            if item['name'] == sname or item['node'].address == sname or item['node'].name == sname:
                return item
        l = list()
        for item in self.service_nodes:
            l.append(f"{item['name']},{item['node'].address},{item['node'].name}")
        LOGGER.error(f"Unknown service node {sname} must be one of: " + ", ".join(l))
        return False

    def _profile_child_nodes(self):
        seen = set()
        nodes = []
        for node in self.poly.nodes():
            if node.name == self.name:
                continue
            key = getattr(node, 'address', None) or getattr(node, 'id', None) or id(node)
            if key in seen:
                continue
            seen.add(key)
            nodes.append(node)
        return nodes

    def _profile_asset_paths(self, node):
        paths = []
        iname = getattr(node, 'iname', None)
        if iname:
            paths.append(f'profile/nodedef/{iname}.xml')
            paths.append(f'profile/editor/{iname}.xml')
        address = getattr(node, 'address', None)
        if address and address != iname:
            paths.append(f'profile/editor/{address}.xml')
        return paths

    def _wait_for_node_init(self, node):
        cnt = PROFILE_NODE_WAIT_MAX
        while node.init_st() is None and cnt > 0:
            if cnt == PROFILE_NODE_WAIT_MAX or cnt % 5 == 0:
                LOGGER.warning(
                    f'Waiting for {node.name} to initialize, timeout in {cnt} seconds...'
                )
            time.sleep(1)
            cnt -= 1
        init_state = node.init_st()
        if init_state is True and cnt < PROFILE_NODE_WAIT_MAX:
            LOGGER.warning(f'{node.name} is initialized...')
        return init_state

    def _notice_profile_node_init_failed(self, node):
        err_code = None
        if hasattr(node, 'getDriver'):
            try:
                err_code = node.getDriver('ERR')
            except Exception:
                err_code = None
        msg = (
            f'{node.name} failed to initialize and was skipped in this profile rebuild. '
        )
        hint = getattr(node, 'init_error_message', None)
        if hint:
            msg += hint
        else:
            msg += 'Fix its configuration (API keys/credentials) and save again.'
        if err_code is not None:
            try:
                if int(err_code) != 0:
                    msg += f' (ERR={err_code})'
            except (TypeError, ValueError):
                pass
        notice_key = f'profile_init_{getattr(node, "address", node.name)}'
        LOGGER.error(msg)
        self.Notices[notice_key] = msg

    def _clear_profile_init_notices(self):
        for key in list(self.Notices.keys()):
            if key == 'profile_init_errors' or str(key).startswith('profile_init_'):
                try:
                    self.Notices.delete(key)
                except Exception:
                    LOGGER.debug('delete notice %s failed', key, exc_info=True)

    def get_current_message(self):
        return(self.get_message_by_id(self.getDriver('GV2')))

    def _empty_message(self):
        return {'id': 0, 'title': '', 'message': ''}

    def get_message_by_id(self, id):
        LOGGER.debug('id=%s', id)
        if id is None:
            id = 0
        else:
            id = int(id)
        if id == 0:
            return self._empty_message()
        if not self.messages:
            LOGGER.warning('id=%s not found: no messages configured', id)
            return {
                'id': id,
                'title': 'Unknown',
                'message': 'Undefined message {}'.format(id),
            }
        for msg in self.messages:
            if not isinstance(msg, dict):
                continue
            mid = msg.get('id')
            if mid is None:
                continue
            if int(mid) == id:
                return msg
        LOGGER.warning('id=%s not found in configured messages', id)
        return {
            'id': id,
            'title': 'Unknown',
            'message': 'Undefined message {}'.format(id),
        }

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

    def get_service_node_address_whatsapp(self,id):
        return get_valid_node_address('wa_'+id)

    def _typed_data_dict(self):
        out = {}
        try:
            for k in self.TypedData.keys():
                out[k] = self.TypedData[k]
        except Exception:
            pass
        return out

    def _telegram_notice_key(self, name):
        return f'telegramub_{name}'

    def _ensure_telegram_session(self):
        if self.telegramub_session is None:
            self.telegramub_session = polyglotSession(
                self, "https://api.telegram.org", LOGGER
            )
        return self.telegramub_session

    def persist_telegram_users(self, name, users):
        td = self._typed_data_dict()
        rows = td.get('telegramub')
        if not isinstance(rows, list):
            return False
        clean_users = sanitize_users(users)
        new_rows = []
        updated = False
        for row in rows:
            if not isinstance(row, dict):
                new_rows.append(row)
                continue
            row = dict(row)
            if str(row.get('name', '')).strip() == name:
                if row.get('users') != clean_users:
                    row['users'] = clean_users
                    updated = True
            new_rows.append(row)
        if not updated:
            return False
        td['telegramub'] = new_rows
        self._telegram_typed_save_in_progress = True
        self.TypedData.load(td, save=True)
        return True

    def _sync_telegram_node_users(self, name, users):
        clean_users = sanitize_users(users)
        for item in self.service_nodes:
            node = item.get('node')
            if item.get('name') != name:
                continue
            if hasattr(node, 'users'):
                node.users = list(clean_users)
                if clean_users:
                    node.user_id = coerce_chat_id(clean_users[0])
                if hasattr(node, 'set_ready'):
                    node.set_ready(True)
                if hasattr(node, 'set_error'):
                    node.set_error(0)
                break

    def _discover_telegram_chat_id(self, row):
        session = self._ensure_telegram_session()
        token = row['http_api_key']
        name = row['name']
        notice_key = self._telegram_notice_key(name)

        me_res = session.get(f"bot{token}/getMe")
        if not telegram_ok(me_res):
            msg = (
                f"Telegram {name}: invalid bot token: "
                f"{telegram_description(me_res)}"
            )
            LOGGER.error(msg)
            self.Notices[notice_key] = msg
            return None

        updates_res = session.get(f"bot{token}/getUpdates")
        if not telegram_ok(updates_res):
            msg = (
                f"Telegram {name}: getUpdates failed: "
                f"{telegram_description(updates_res)}"
            )
            LOGGER.error(msg)
            self.Notices[notice_key] = msg
            return None

        chat_id = chat_id_from_updates(updates_res.get('data'))
        if chat_id is not None:
            self.Notices.delete(notice_key)
            return coerce_chat_id(chat_id)

        bot_link = bot_link_from_get_me(me_res.get('data'))
        if bot_link:
            self.Notices[notice_key] = (
                f"Telegram {name}: send /start to your bot at "
                f'{external_link(bot_link, bot_link)}, '
                f"then restart the nodeserver."
            )
        else:
            self.Notices[notice_key] = (
                f"Telegram {name}: send /start to your bot, then restart "
                f"the nodeserver."
            )
        return None

    def _auto_discover_telegram(self, telegramub):
        if getattr(self, '_telegram_typed_save_in_progress', False):
            return False
        persisted = False
        for row in telegramub:
            if not isinstance(row, dict):
                continue
            row['users'] = sanitize_users(row.get('users', []))
            if row['users']:
                self.Notices.delete(self._telegram_notice_key(row['name']))
                continue
            chat_id = self._discover_telegram_chat_id(row)
            if chat_id is None:
                continue
            if self.persist_telegram_users(row['name'], [str(chat_id)]):
                row['users'] = [str(chat_id)]
                self.Notices[f"telegramub_ok_{row['name']}"] = (
                    f"Telegram {row['name']}: discovered and saved chat_id {chat_id}."
                )
                persisted = True
        return persisted

    def handler_discover_telegram(self, _data=None):
        LOGGER.info('Telegram DISCOVER')
        td = self._typed_data_dict()
        rows = td.get('telegramub') or []
        if not rows:
            self.Notices['telegram_discover'] = 'No Telegram service nodes configured.'
            return

        ready = 0
        waiting = []
        for row in rows:
            cleaned = sanitize_telegram_row(row)
            if cleaned is None:
                continue
            if cleaned.get('users'):
                ready += 1
                continue
            chat_id = self._discover_telegram_chat_id(cleaned)
            if chat_id is None:
                waiting.append(cleaned['name'])
                continue
            if self.persist_telegram_users(cleaned['name'], [str(chat_id)]):
                self._sync_telegram_node_users(cleaned['name'], [str(chat_id)])
                ready += 1
                self.Notices[f"telegramub_ok_{cleaned['name']}"] = (
                    f"Telegram {cleaned['name']}: discovered and saved chat_id {chat_id}."
                )

        if waiting:
            self.Notices['telegram_discover'] = (
                f"Still waiting for /start on: {', '.join(waiting)}."
            )
        elif ready:
            self.Notices['telegram_discover'] = (
                f"Telegram discover: {ready} node(s) ready."
            )
        else:
            self.Notices['telegram_discover'] = (
                'Telegram discover: no valid bot tokens configured.'
            )

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
                    'desc': 'Telegram Bot API notifications. Paste BotFather token; user chat id is auto-discovered after /start.',
                    'isList': True,
                    'params': [
                        {
                            'name': 'name',
                            'title': 'Name for reference, used as node name. Must be 8 characters or less.',
                            'isRequired': True
                        },
                        {
                            'name': 'http_api_key',
                            'title': 'HTTP API Key (BotFather token)',
                            'defaultValue': 'your_http_api_key',
                            'isRequired': True
                        },
                        {
                            'name': 'users',
                            'title': 'User chat id (optional — auto-discovered after /start)',
                            'isRequired': False,
                            'isList': True,
                        },
                    ]
                },
                {
                    'name': 'whatsapp',
                    'title': 'WhatsApp Service Nodes (CallMeBot)',
                    'desc': 'Free personal WhatsApp notifications via https://www.callmebot.com/',
                    'isList': True,
                    'params': [
                        {
                            'name': 'name',
                            'title': 'Name for reference, used as node name. Must be 8 characters or less.',
                            'isRequired': True
                        },
                        {
                            'name': 'recipients',
                            'title': 'Recipients (each person activates CallMeBot on their own phone)',
                            'isRequired': True,
                            'isList': True,
                            'params': [
                                {
                                    'name': 'phone',
                                    'title': 'Phone with country code (e.g. +1234567890)',
                                    'isRequired': True
                                },
                                {
                                    'name': 'apikey',
                                    'title': 'CallMeBot API key for this phone',
                                    'isRequired': True
                                },
                            ],
                        },
                    ]
                }
            ],
            True
        )
        LOGGER.debug('exit')

    def handler_data(self,data):
        LOGGER.debug('Enter %s', custom_data_log_label(data))
        if data is None:
            self.handler_data_st = False
        else:
            self.Data.load(data)
            self.handler_data_st = True
        self._flush_pending_typed_data()

    def _params_dict(self):
        out = {}
        try:
            for k in self.Params.keys():
                out[k] = self.Params[k]
        except Exception:
            pass
        return out or None

    def _update_edition(self, params=None):
        self.edition = resolve_edition(self.poly, LOGGER)
        self._sync_dev_edition_notice()

    def _clear_service_notices(self):
        preserved = {
            key: self.Notices[key]
            for key in _DEV_EDITION_NOTICE_KEYS
            if key in self.Notices
        }
        self.Notices.clear()
        for key, message in preserved.items():
            self.Notices[key] = message

    def _sync_dev_edition_notice(self):
        override_key = 'dev_edition_override'
        mismatch_key = 'dev_edition_mismatch'
        licensed = licensed_edition(self.poly)

        if dev_edition_override_active(self.poly, self.edition):
            notice = (
                f'Edition override active (local dev only): licensed {licensed}, '
                f'running as {self.edition} via dev_edition.txt.'
            )
            self.Notices[override_key] = notice
            self.Notices.delete(mismatch_key)
            LOGGER.warning(notice)
        else:
            self.Notices.delete(override_key)
            self.Notices.delete(mismatch_key)

    def _flush_pending_typed_data(self):
        pending = self._pending_typed_data
        if pending is None:
            return
        if (
            self.handler_params_st is None
            or self.handler_data_st is None
            or self.handler_config_st is None
        ):
            return
        self._pending_typed_data = None
        self.handler_typed_data(pending)

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
        LOGGER.debug('Enter %s', custom_data_log_label(data))
        self.Params.load(data)
        self._update_edition(params=data)
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
                self.Notices[val] = 'Please Define <a href="https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/blob/master/POLYGLOT_CONFIG.md#portal_api_key">portal_api_key</a> or review configuration help section below.'
            else:
                self.Notices.delete(val)
                # Start the UDMobile node
                self.udmobile_session = polyglotSession(self,"https://my.isy.io",LOGGER)
                snode = self.add_node(UDMobile(self, self.address, 'udmobile', get_valid_node_name('UD Mobile'), self.udmobile_session, self.portal_api_key))
                self.service_nodes.append({ 'name': snode.name, 'node': snode, 'index': len(self.service_nodes)})
                LOGGER.info('service_nodes={}'.format(self.service_nodes))

        self.handler_params_st = st
        self._flush_pending_typed_data()
        # Dont' start on first run cause we need handler_typed_data to be completed
        # add_node_done will do it on first start 
        if not self.first_run:
            # When data changes build the profile, 
            self.write_profile()
            self.start_rest_server()

    def handler_typed_data(self, data):
        LOGGER.debug("Enter data={}".format(data))
        completing_persist = getattr(self, '_telegram_typed_save_in_progress', False)
        if completing_persist:
            self._telegram_typed_save_in_progress = False

        self.TypedData.load(data)
        if data is None:
            self.handler_typed_data_st = False
            return False

        if (
            self.handler_params_st is None
            or self.handler_data_st is None
            or self.handler_config_st is None
        ):
            self._pending_typed_data = data
            LOGGER.warning(
                'Deferring typed_data until config loaded '
                '(params=%s data=%s config=%s)',
                self.handler_params_st,
                self.handler_data_st,
                self.handler_config_st,
            )
            return False

        self._update_edition()

        # If we have already been run on startup, clear service notices.
        if self.handler_config_st is not None:
            self._clear_service_notices()

        el = list()

        #We are not getting this returned in data??? Report to Bob.
        #self.rest_port = data.get('rest_port',None)

        #
        # List of errors to print at the end in a Notice
        err_list = list()

        self.messages = data.get('messages', el)
        LOGGER.info('messages={}'.format(self.messages))
        validated_messages = []
        for msg in self.messages:
            if not isinstance(msg, dict):
                err_list.append(
                    f"Invalid message entry {msg!r}. Delete or fix id/title/message."
                )
                continue
            mid = msg.get('id')
            if mid is None or str(mid).strip() == '':
                err_list.append(
                    f"Invalid message entry {msg}. Missing/empty id."
                )
                continue
            try:
                int(mid)
            except (TypeError, ValueError):
                err_list.append(
                    f"Invalid message entry {msg}. id must be numeric."
                )
                continue
            validated_messages.append(msg)
        self.messages = validated_messages
        if len(self.messages) == 0:
            LOGGER.info('No messages')

        #
        # List of all service node names
        snames   = { 'udmobile': { 'type': 'udmobile', 'name': 'udmobile'}}

        def _typed_node_name(node_type, node):
            if not isinstance(node, dict):
                err_list.append(
                    f"Invalid {node_type} node entry {node!r}. Delete this node or fix the name."
                )
                return None
            name = str(node.get('name', '')).strip()
            if not name:
                err_list.append(
                    f"Invalid {node_type} node entry {node}. Missing/empty name. Delete this node or fix the name."
                )
                return None
            return name

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
                sname = _typed_node_name('pushover', pd)
                if sname is None:
                    continue
                # Save info for later
                pd['type'] = 'pushover'
                snames[sname] = pd
                # Check for duplicates
                address = self.get_service_node_address(sname)
                if not address in pnames:
                    pnames[address] = list()
                pnames[address].append(sname)
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
                sname = _typed_node_name('ISYPortal', pd)
                if sname is None:
                    continue
                # Save info for later
                pd['type'] = 'isyportal'
                snames[sname] = pd
                # Check for duplicates
                address = self.get_service_node_address(sname)
                if not address in unames:
                    unames[address] = list()
                unames[address].append(sname)
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
                sname = _typed_node_name('telegramub', pd)
                if sname is None:
                    continue
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
            sanitized_telegram = []
            for pd in telegramub:
                cleaned = sanitize_telegram_row(pd)
                if cleaned is None:
                    label = pd.get('name', pd) if isinstance(pd, dict) else pd
                    err_list.append(
                        f"Telegram {label}: missing/invalid name or bot token. "
                        f"See README Telegram section for BotFather setup."
                    )
                    continue
                pd.update(cleaned)
                sanitized_telegram.append(pd)
            if sanitized_telegram:
                telegramub = sanitized_telegram
            else:
                telegramub = None
        #
        # Check the whatsapp configs are all good
        #
        whatsapp = data.get('whatsapp', el)
        wnames = dict()
        LOGGER.info('whatsapp={}'.format(whatsapp))
        if len(whatsapp) == 0:
            LOGGER.warning("No WhatsApp Entries in the config: {}".format(whatsapp))
            whatsapp = None
        else:
            for pd in whatsapp:
                sname = _typed_node_name('whatsapp', pd)
                if sname is None:
                    continue
                pd['type'] = 'whatsapp'
                snames[sname] = pd
                address = self.get_service_node_address_whatsapp(sname)
                if not address in wnames:
                    wnames[address] = list()
                wnames[address].append(sname)
                recipients = pd.get('recipients')
                if not isinstance(recipients, list) or len(recipients) == 0:
                    err_list.append(
                        f"WhatsApp {sname}: at least one recipient (phone + apikey) is required."
                    )
                    continue
                for idx, recipient in enumerate(recipients):
                    if not isinstance(recipient, dict):
                        err_list.append(
                            f"WhatsApp {sname}: invalid recipient entry at index {idx}."
                        )
                        continue
                    phone = str(recipient.get('phone', '')).strip()
                    apikey = str(recipient.get('apikey', '')).strip()
                    if not phone.startswith('+'):
                        err_list.append(
                            f"WhatsApp {sname}: recipient phone {phone or '(empty)'} must include country code and start with +."
                        )
                    if not apikey:
                        err_list.append(
                            f"WhatsApp {sname}: recipient {phone or '(empty)'} is missing CallMeBot apikey."
                        )
            for address in wnames:
                if len(wnames[address]) > 1:
                    err_list.append("Duplicate whatsapp names for {} items {} from {}".format(
                        len(wnames[address]), address, ",".join(wnames[address])
                    ))
        #
        # Check the notify nodes are all good
        #
        notify_nodes    = data.get('notify',el)
        if len(notify_nodes) == 0:
            LOGGER.warning('No Notify Nodes')
        else:
            # First check that notify_nodes are valid before we try to add them
            mnames = dict()
            for node in notify_nodes:
                if not isinstance(node, dict):
                    err_list.append(
                        f"Invalid notify node entry {node!r}. Delete this node or fix id/name."
                    )
                    continue
                node_id = str(node.get('id', '')).strip()
                if not node_id:
                    err_list.append(
                        f"Invalid notify node entry {node}. Missing/empty id. Delete this node or fix id."
                    )
                    continue
                node_name = str(node.get('name', '')).strip()
                if not node_name:
                    err_list.append(
                        f"Invalid notify node entry {node}. Missing/empty name. Delete this node or fix the name."
                    )
                    continue
                address = self.get_message_node_address(node_id)
                if not address in mnames:
                    mnames[address] = list()
                mnames[address].append(node_id)
                # And check that service node name is known
                if 'service_node_name' in node:
                    sname = node['service_node_name']
                    if not sname in snames:
                        err_list.append("Unknown service node name {} in notify node {} must be one of {}".format(sname,node,",".join(snames)))
                else:
                    err_list.append(
                        "No service node name in notify node {} must be one of {}. Delete this node or set a valid service node name.".format(
                            node, ",".join(snames)
                        )
                    )
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
            self.Notices['typed_data'] = (
                f'There are {len(err_list)} typed data errors. Delete invalid nodes or fix names/ids, then restart.'
            )
            self.handler_typed_data_st = False
            self._sync_dev_edition_notice()
            return

        if telegramub and not completing_persist:
            if self._auto_discover_telegram(telegramub):
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

        if whatsapp is not None:
            self.whatsapp_session = polyglotSession(self, "https://api.callmebot.com", LOGGER)
            for pd in whatsapp:
                if self.edition == "Free":
                    err = f"Can't add WhatsApp node {pd['name']} in {self.edition} Edition"
                    LOGGER.error(err)
                    self.Notices[pd['name']] = err
                else:
                    snode = self.add_node(WhatsApp(
                        self,
                        self.address,
                        self.get_service_node_address_whatsapp(pd['name']),
                        get_valid_node_name('Service WhatsApp ' + pd['name']),
                        self.whatsapp_session,
                        pd,
                    ))
                    self.service_nodes.append({'name': pd['name'], 'node': snode, 'index': len(self.service_nodes)})
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
        self._sync_dev_edition_notice()

        # When data changes build the profile, except when first starting up since
        # that will be done by the config handler
        if not self.first_run:
            self.write_profile()

    def write_profile(self):
        LOGGER.info('enter')
        self.write_profile_lock.acquire()
        try:
            self.Notices['profile_rebuild'] = 'Profile rebuild in progress'
            self.profile_installed = False
            st = True
            profile_nodes_written = set()
            pending_profile_nodes = set()
            failed_profile_node_names = []
            self._clear_profile_init_notices()

            child_nodes = self._profile_child_nodes()
            node_init_states = []
            for node in child_nodes:
                node_init_states.append((node, self._wait_for_node_init(node)))

            preserve_profile_files = set()
            for node, init_state in node_init_states:
                if init_state is False:
                    failed_profile_node_names.append(node.name)
                    self._notice_profile_node_init_failed(node)
                    for path in self._profile_asset_paths(node):
                        if os.path.isfile(path):
                            preserve_profile_files.add(os.path.basename(path))

            for dir in ['profile/editor', 'profile/nodedef']:
                if os.path.exists(dir):
                    LOGGER.debug('Cleaning: {}'.format(dir))
                    for file in os.listdir(dir):
                        LOGGER.debug(file)
                        path = dir+'/'+file
                        if not os.path.isfile(path):
                            continue
                        if file == 'editors.xml':
                            continue
                        if file in preserve_profile_files:
                            LOGGER.debug('Preserving failed node profile asset: {}'.format(path))
                            continue
                        LOGGER.debug('Removing: {}'.format(path))
                        os.remove(path)

            if not os.path.exists('profile/nodedef'):
                os.mkdir('profile/nodedef')
            template_f = 'template/nodedef/nodedefs.xml'
            LOGGER.debug("Reading {}".format(template_f))
            with open(template_f, "r") as myfile:
                data = myfile.read()
            output_f = 'profile/nodedef/nodedefs.xml'
            make_file_dir(output_f)
            LOGGER.debug("Writing {}".format(output_f))
            with open(output_f, "w") as out_h:
                out_h.write(data.format(self.sys_notify_editor))

            en_us_txt = "profile/nls/en_us.txt"
            make_file_dir(en_us_txt)
            template_f = "template/nls/en_us.txt"
            LOGGER.debug("Reading {}".format(template_f))
            with open(template_f, "r") as nls_tmpl:
                LOGGER.debug("Writing {}".format(en_us_txt))
                with open(en_us_txt, "w") as nls:
                    nls.write("# From: {}\n".format(template_f))
                    for line in nls_tmpl:
                        nls.write(line)
                    nls.write("# End: {}\n\n".format(template_f))
                    msg_cnt = 0
                    nls.write("# Start: Internal Messages:\n")
                    for message in get_messages():
                        nls.write("NMESSAGE-{} = {}\n".format(msg_cnt, message))
                        msg_cnt += 1
                    nls.write("# End: Internal Messages:\n\n")
                    nls.write("# Start: Custom Messages:\n")
                    ids = list()
                    if self.messages is None:
                        self.messages = [{'id': 0, 'title': "Default"}]
                        LOGGER.warning("No User Messages, define some in Configuration if desired")
                    else:
                        for message in self.messages:
                            if 'id' not in message:
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
                            nls.write("MID-{} = {}\n".format(message['id'], message['title']))
                    nls.write("# End: Custom Messages:\n\n")

                    nls.write("# Start: Service Nodes\n")
                    svc_cnt = 0
                    nls.write("NFYN--1 = Unknown\n")
                    if self.service_nodes is not None:
                        for pd in self.service_nodes:
                            nls.write("NFYN-{} = {}\n".format(pd['index'], pd['name']))
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
                    nls.write("# Start: Custom Service Nodes:\n")
                    self.devices = list()
                    for node, init_state in node_init_states:
                        if init_state is True:
                            LOGGER.info('node={} id={}'.format(node.name, node.id))
                            node.write_profile(nls)
                            profile_nodes_written.update([node.address, node.name, node.id])
                            config_info_nr.append(node.config_info_nr())
                            config_info_rest.append(node.config_info_rest())
                        elif init_state is None:
                            LOGGER.warning(
                                'Node {} still initializing; deferring profile write'.format(node.name)
                            )
                            pending_profile_nodes.update([node.address, node.name, node.id])
                        else:
                            LOGGER.error(
                                'Node {} failed to initialize init_st={}'.format(node.name, init_state)
                            )
                    nls.write("\n# Start: End Service Nodes:\n")

            LOGGER.debug(f'st={st}')
            if st is False:
                LOGGER.error('Invalid custom message ids; can not write profile')
                self.Notices['profile_rebuild'] = (
                    'Profile rebuild failed: fix invalid custom message ids and save again'
                )
                return False

            if failed_profile_node_names:
                self.Notices['profile_init_errors'] = (
                    f'{len(failed_profile_node_names)} service node(s) failed to initialize; '
                    f'profile was updated for healthy nodes. Fix credentials and save again.'
                )

            config_info_rest.append('</ul>')
            self.config_info = config_info_nr + config_info_rest
            config_doc_file = "POLYGLOT_CONFIG.md"
            LOGGER.debug("Reading {}".format(config_doc_file))
            with open(config_doc_file, "r") as myfile:
                data = myfile.read()
            self.poly.setCustomParamsDoc(markdown2.markdown(data) + "\n".join(self.config_info))

            full_subset_str = ",".join(map(str, ids))
            LOGGER.debug(f"MESSAGE:full_subset_str={full_subset_str}")
            subset_str = get_subset_str(ids)
            LOGGER.debug(f"MESSAGE:subset_str={subset_str}")
            editor_f = "profile/editor/custom.xml"
            make_file_dir(editor_f)
            template_f = 'template/editor/custom.xml'
            LOGGER.debug("Reading {}".format(template_f))
            with open(template_f, "r") as myfile:
                data = myfile.read()
            LOGGER.debug("Writing {}".format(editor_f))
            with open(editor_f, "w") as editor_h:
                editor_h.write(data.format(full_subset_str, subset_str, (msg_cnt - 1), (svc_cnt - 1)))

            self.poly.updateProfile()
            self.profile_installed = True
            self.profile_nodes_written = profile_nodes_written
            self.pending_profile_nodes = pending_profile_nodes
            self.Notices['profile_rebuild'] = 'Profile rebuilt, restart admin console'
            if len(pending_profile_nodes) > 0:
                LOGGER.warning('Profile installed with pending nodes: {}'.format(",".join(sorted(pending_profile_nodes))))
            for node in self.poly.nodes():
                if hasattr(node, 'flush_send_queue'):
                    node.flush_send_queue()
            return True
        finally:
            self.write_profile_lock.release()

    def is_profile_node_written(self,node):
        if node is None:
            return False
        keys = [getattr(node, 'address', None), getattr(node, 'name', None), getattr(node, 'id', None)]
        for key in keys:
            if key and key in self.profile_nodes_written:
                return True
        return False

    def on_service_node_ready(self,node):
        if node is None:
            return
        if not self.profile_installed:
            return
        if not self.is_profile_node_written(node):
            LOGGER.warning('Service node {} initialized after profile install; rebuilding profile...'.format(node.name))
            self.write_profile()
        elif hasattr(node, 'flush_send_queue'):
            node.flush_send_queue()

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
        msg = command.get('value')
        if msg is None:
            parsed = self.get_message_from_query(command.get('query'))
            msg = parsed['message']
        self.set_sys_short(msg)

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

