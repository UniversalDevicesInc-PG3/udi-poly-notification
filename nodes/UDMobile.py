"""
  Notification UDMobile Node

  TODO:
    - 
"""
from email import message
from socket import MsgFlag
from udi_interface import Node,LOGGER,Custom
from threading import Thread
import time
from copy import deepcopy
from node_funcs import (
    make_file_dir,
    is_int,
    SendQueue,
    send_queue_storage_key,
    load_send_queue,
    persist_send_queue,
)
from constants import SOUNDS_LIST
from datetime import datetime
from dev_settings import custom_data_log_label

ERROR_NONE       = 0
ERROR_UNKNOWN    = 1
ERROR_APP        = 2
ERROR_APP_AUTH   = 3
ERROR_MESSAGE_CREATE = 4
ERROR_MESSAGE_SEND   = 5
ERROR_PARAM          = 6
ERROR_MAX            = 7

REM_PREFIX = "REMOVED-"
GROUP_LIST = 'group_list_udmobile'

# How many tries to get or post, -1 is forever
RETRY_MAX = -1
# How long to wait between tries, in seconds
RETRY_WAIT = 5
# Startup validation retries use exponential backoff.
# A non-positive value retries forever for retryable failures such as
# DNS resolution, connection errors, and upstream 5xx responses.
# Non-retryable auth failures such as 401/403 still fail immediately.
STARTUP_RETRY_MAX = -1
# Initial wait before the next startup validation retry, in seconds.
STARTUP_RETRY_WAIT = 1
# Maximum exponential-backoff delay between startup retries, in seconds.
STARTUP_RETRY_MAX_WAIT = 8
READY_WAIT_MAX = 30
READY_LOG_INTERVAL = 5
SEND_QUEUE_MAX = 128
SEND_QUEUE_MAX_AGE = 3600
FAILED_REQUEUE_MAX = 5

class UDMobile(Node):
    """
    """
    def __init__(self, controller, primary, address, name, session, api_key):
        """
        """
        self.ready = False
        self.name     = name
        self.address  = address
        self.controller = controller
        self.session  = session
        self.api_key  = api_key
        self._sys_short = None
        self.handler_data_st = None
        self.msg_cnt  = 0
        self.send_queue = SendQueue(SEND_QUEUE_MAX, SEND_QUEUE_MAX_AGE)
        LOGGER.debug('{} {}'.format(address,name))
        controller.poly.subscribe(controller.poly.START,                  self.handler_start, address)
        super(UDMobile, self).__init__(controller.poly, primary, address, name)

    def handler_start(self):
        """
        """
        LOGGER.info('')
        self._load_persisted_send_queue()
        self.groups_list = self.controller.get_data(GROUP_LIST,[])
        self.sounds_list  = SOUNDS_LIST
        LOGGER.debug('controller.%s', custom_data_log_label(dict(self.controller.Data)))
        LOGGER.info("{}={}".format(GROUP_LIST,self.groups_list))
        LOGGER.debug('Authorizing UDMobile api {}'.format(self.api_key))
        validation = self.validate()
        self.authorized = validation.get('status', False) is True
        LOGGER.info("Authorized={}".format(self.authorized))
        if self.authorized:
            groups = self.get_groups(retry=True)
            if self.set_groups(groups):
                self.set_error(ERROR_NONE)
                self._init_st = True
                self.controller.on_service_node_ready(self)
                params = { 'system': True, 'title': f'{self.controller.nodename} {self.controller.uuid} Notification Node Server {self.controller.edition} Edition Startup.' }
                if self.controller.edition == 'Free':
                    params['body'] = 'Please upgrade to Standard version to get all features'
                else:
                    params['body'] = ' '
                self.do_send(params)
            else:
                self._init_st = False
        else:
            self._init_st = False
        self.ready = True
        self.flush_send_queue()

    def api_get(self,command):
        return self.check_result(
            self.session.get(f"api/push/{command}",api_key=self.api_key)
        )

    def api_post(self,command,params):
        return self.check_result(
            self.session.post(f"api/push/{command}",params,
                              api_key=self.api_key,content="urlencode",)
        )

    def get_error_message(self,res,default='Unknown error'):
        if res is None or res is False:
            return default
        message = res.get('errorMessage')
        if message:
            return message
        code = res.get('code')
        if code is not None:
            return 'HTTP {}'.format(code)
        return default

    def is_retryable_result(self,res):
        if res is None or res is False:
            return True
        return res.get('retryable', res.get('code') is None or res.get('code', 0) >= 500)

    def api_get_with_backoff(self,command,description):
        attempt = 0
        wait = STARTUP_RETRY_WAIT
        res = None
        max_attempts = STARTUP_RETRY_MAX
        retry_forever = max_attempts <= 0
        while retry_forever or attempt < max_attempts:
            attempt += 1
            res = self.api_get(command)
            if res.get('status'):
                return res
            if not self.is_retryable_result(res):
                break
            if not retry_forever and attempt >= max_attempts:
                break
            attempt_label = '{}'.format(attempt) if retry_forever else '{}/{}'.format(attempt, max_attempts)
            LOGGER.warning(
                '{} failed on attempt {}: {}. Retrying in {} seconds...'.format(
                    description,
                    attempt_label,
                    self.get_error_message(res, 'Unknown error'),
                    wait,
                )
            )
            time.sleep(wait)
            wait = min(wait * 2, STARTUP_RETRY_MAX_WAIT)
        if res is not None and not res.get('status'):
            LOGGER.error(
                '{} failed after {}: {}'.format(
                    description,
                    '{} attempt(s)'.format(attempt) if not retry_forever else 'retrying until a non-retryable error occurs',
                    self.get_error_message(res, 'Unknown error'),
                )
            )
        return res

    def check_result(self,res):
        LOGGER.debug('got: {}'.format(res))
        if res.get('status'):
            return res
        if res.get('code') == 403:
            self.set_error(ERROR_APP_AUTH,"Please verify your portal_api_key value")
        else:
            self.set_error(ERROR_APP,self.get_error_message(res,'Unable to reach my.isy.io'))
        return res
    
    def validate(self):
        return self.api_get_with_backoff("tokens","UD Mobile token validation")

    def get_groups(self,retry=False):
        if retry:
            data = self.api_get_with_backoff("groups","UD Mobile group fetch")
        else:
            data = self.api_get("groups")
        LOGGER.debug("got groups: {}".format(data))
        return data

    def set_groups(self,data=None):
        if GROUP_LIST in self.controller.Data:
            self.groups_list = self.controller.Data[GROUP_LIST]
        if data is None:
            data = self.get_groups()
        groups = data.get('data', {}).get('data') if isinstance(data.get('data'), dict) else None
        if groups is None:
            LOGGER.error('Failed to get UDMobile groups: {}'.format(self.get_error_message(data,'Unknown error')))
            return False
        LOGGER.info("got UDMobile groups={}".format(groups))
        self.build_group_list(groups)
        self.controller.Data[GROUP_LIST] = self.groups_list
        return True

    def group_id2name(self,id):
        for item in self.groups_list:
            if item['id'] == id:
                return item['name']
        return None

    def group_id2index(self,id):
        cnt = 0
        for item in self.groups_list:
            if item['id'] == id:
                return cnt
            cnt += 1
        return None

    def build_group_list(self,vlist):
        # Make sure default is the first in the list
        if len(self.groups_list) == 0:
            self.groups_list.append({'id': '_default_', 'name': 'default'})
        elif self.groups_list[0]['id'] == 'default':
            # Fix mine with old default
            self.groups_list[0] = {'id': '_default_', 'name': 'default'}
        elif self.groups_list[0]['id'] != '_default_':
            # For NS's that were created before we added defaults, this will
            # increment all indexes so programs will need to be updated.
            self.groups_list.insert(0,{'id': '_default_', 'name': 'default'})
        # Add any new groups to the groups_list, and create hash of id->name
        idhash = dict()
        for item in vlist:
            LOGGER.debug('group={}'.format(item))
            idhash[item['id']] = item['name']
            # If it's not in the saved list, append it
            gidx = self.group_id2index(item['id'])
            if gidx is None:
                self.groups_list.append({'id': item['id'], 'name': item['name']})
            else:
                # Check for name changes
                if self.groups_list[gidx]['name'] != item['name']:
                    self.groups_list[gidx]['name'] = item['name']
        # Make sure items are in the passed in list, otherwise prefix it in groups_list
        groups_list = list()
        for item in self.groups_list:
            if item['id'] == '_default_':
                # Force it to fix previous bug that added REM_PREFIX
                item['name'] = 'default'
            else:
                # Add or remove the removed prefix to items
                if item['id'] in idhash:
                    if item['name'].startswith(REM_PREFIX):
                        # It came back, get rid of removed prefix
                        item['name'] = item['name'][len(REM_PREFIX):]
                elif not item['name'].startswith(REM_PREFIX):
                    # It's gone, add the prefix
                    item['name'] = REM_PREFIX + item['name']
            groups_list.append(item)
        self.groups_list = groups_list
        LOGGER.info("groups_list={}".format(self.groups_list))

    """
    This lets the controller know when we are initialized, or if we had
    an error.  Since it can't call our write_profile until we have initilized
      None  = Still initializing
      False = Failed
      True  = All Good
    """
    def init_st(self):
        return self._init_st

    def query(self):
        self.reportDrivers()

    def config_info_rest(self):
        if self.controller.rest is None:
            listen_url = None
        else:
            listen_url = self.controller.rest.listen_url
        str = '<li>curl -d \'{{"node":"{0}", "message":"The Message", "subject":"The Subject" -H "Content-Type: application/json"}}\' -X POST {1}/send'.format(self.address,listen_url)
        return str

    def config_info_nr(self):
        if self.controller.rest is None or self.controller.rest.ip is None:
            rest_ip = "None"
            rest_port = "None"
        else:
            rest_ip = self.controller.rest.ip
            rest_port = self.controller.rest.listen_port
        info = [
            '<h4>Example Network Resource settings for UDMobile</h4><ul><li>http<li>POST<li>Host:{0}<li>Port:{1}<li>Path: /send?node={2}&Subject=My+Subject&group=1&sound=2<li>Encode URL: not checked<li>Timeout: 5000<li>Mode: Raw Text</ul>'.format(rest_ip,rest_port,self.address),
            '<p>The parms in the Path can be any of the below, if the param is not passed then the default from the UDMobile node will be used'
            '<table>',
            '<tr><th>Name<th>Index<th>ID<th>Description',
        ]
        i = 0
        t = 'group'
        for item in self.groups_list:
            info.append('<tr><td>{}<td>{}<td>{}<td>{}'.format(t,i,item['id'],item['name']))
            i += 1
            t = '&nbsp;'
        t = 'sound'
        i = 0
        for item in self.sounds_list:
            info.append('<tr><td>{}<td>{}<td>{}<td>{}'.format(t,i,'&nbsp;',item['name']))
            i += 1
            t = '&nbsp;'
        info = info + [

            '</table>'
        ]
        return ''.join(info)

    def write_profile(self,nls):
        pfx = 'write_profile'
        LOGGER.debug('')
        #
        # nls
        #
        nls.write("\n# Entries for UD Mobile {} {}\n".format(self.id,self.name))
        nls.write("ND-{0}-NAME = {1}\n".format(self.id,self.name))
        idx = 0
        subst = []
        for item in self.groups_list:
            nls.write("IPD_{}-{} = {}\n".format(self.id,idx,item['name']))
            # Don't include REMOVED's in list
            if not item['name'].startswith(REM_PREFIX):
                subst.append(str(idx))
            idx += 1
        # Make sure it has at least one
        if len(subst) == 0:
            subst.append('0')

        sound_subst = []
        idx = 0
        for item in self.sounds_list:
            nls.write("IPS_{}-{} = {}\n".format(self.id,idx,item['name']))
            # Don't include REMOVED's in list
            if not item['name'].startswith(REM_PREFIX):
                sound_subst.append(str(idx))
            idx += 1
        
        #
        # editor
        #
        # Open the template, and read into a string for formatting.
        template_f = 'template/editor/udmobile.xml'
        LOGGER.debug("Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Write the editors file with our info
        output_f   = 'profile/editor/{0}.xml'.format(self.address)
        make_file_dir(output_f)
        LOGGER.debug("Writing {}".format(output_f))
        editor_h = open(output_f, "w")
        # TODO: We could create a better subst with - and , but do we need to?
        # TODO: Test calling get_subset_str in node_funcs.py
        editor_h.write(data.format(self.address,",".join(subst),",".join(sound_subst)))
        editor_h.close()

    def get_group_name_by_index(self,gidx=None):
        LOGGER.debug('gidx={}'.format(gidx))
        if not is_int(gidx):
            LOGGER.error('Passed in {} is not an integer'.format(gidx))
            return False
        gidx = int(gidx)
        try:
            group = self.groups_list[gidx]
        except:
            LOGGER.error('Bad group index {} groups={}'.format(gidx,",".join(self.groups_list)),exc_info=True)
            self.set_error(ERROR_PARAM,f'Unknown group name or index {gidx}')
            return False
        LOGGER.debug('gidx={} group={}'.format(gidx,group))
        return group['name']

    def set_st(self,val):
        LOGGER.info(val)
        if val is False or val is None:
            val = 0
        elif val is True:
            val = 1
        else:
            val = int(val)
        LOGGER.info('Set ST to {}'.format(val))
        self.setDriver('ST', val)

    def set_error(self,val,message=None):
        LOGGER.info(val)
        if val is False:
            val = 0
        elif val is True:
            val = 1
        LOGGER.info('Set ERR to {}'.format(val))
        self.setDriver('ERR', val)
        self.set_st(True if val == 0 else False)
        if val == 0:
            self.controller.poly.Notices.delete(f'udmobile_err')
        else:
            self.err_notice('udmobile_err',message)

    def err_notice(self,name,err_str):
            self.controller.poly.Notices[name] = f"ERROR: {datetime.now().strftime('%m/%d/%Y %H:%M:%S')} See log for: {err_str}"

    # Returns UDMobile sound name from our index number
    def get_UDMobile_sound(self,val=None):
        LOGGER.info('val={}'.format(val))
        if val is None:
            val = int(self.get_sound())
        else:
            val = int(val)
        rval = self.sounds_list[val]['fname']
        LOGGER.info('{}'.format(rval))
        return rval

    # Returns UDMobile sound name by name, return default if not found
    def get_UDMobile_sound_by_name(self,name):
        LOGGER.info('name={}'.format(name))
        rval = False
        i = 0
        for item in self.sounds_list:
            if name == item['name']:
                rval = item['fname']
            i += 1
        if rval is False:
            LOGGER.error("No sound name found matching '{}".format(name))
            rval = self.sounds_list[0]['fname']
        LOGGER.info('{}'.format(rval))
        return rval

    # This is what we got back for _sys_notify_short
    # command={'address': 'udmobile', 'cmd': 'GV10', 'query': {'Group.uom25': '2', 'Sound.uom25': '1', 'Content.uom145': 'Simple Title\nSimple Body\nBody line 2'}}
    def wait_until_ready(self):
        wait = 0
        while not self.ready and wait < READY_WAIT_MAX:
            if self.init_st() is False:
                LOGGER.error('UD Mobile failed to initialize, can not send message')
                return False
            if wait == 0 or wait % READY_LOG_INTERVAL == 0:
                LOGGER.warning('Waiting for UD Mobile node to be ready...')
            time.sleep(1)
            wait += 1
        if not self.ready:
            self.set_error(ERROR_MESSAGE_SEND,'Timed out waiting for UD Mobile initialization')
            LOGGER.error('Timed out waiting for UD Mobile node to be ready')
            return False
        if self.init_st() is False:
            LOGGER.error('UD Mobile initialization failed, can not send message')
            return False
        return True

    def cmd_send_message(self,command):
        LOGGER.debug(f'command={command}')
        params = dict()
        query = command.get('query')
        val = query.get('Group.uom25')
        if val is None:
            LOGGER.warning(f"No Group passed in for command: {command}")
        else:
            params['group'] = val
        val = query.get('Sound.uom25')
        if val is None:
            LOGGER.warning(f"No Sound passed in for command: {command}")
        else:
            params['sound'] = val
        msg = self.controller.get_message_from_query(query)
        params['title'] = msg['subject']
        params['body']  = msg['body']
        if ('reboot' in params and params['reboot'] is True):
            self.Notices['reboot_iox'] = f"WARNING: You need to reboot IoX to support long messages for: {msg}"
        if not self.wait_until_ready():
            self.enqueue_send(params, 'UD Mobile not ready from command path')
            return True
        return self.do_send(params)

    def can_deliver(self):
        return (
            self.init_st() is True
            and self.controller.profile_installed is True
            and self.controller.is_profile_node_written(self)
        )

    def _send_queue_key(self):
        return send_queue_storage_key('udmobile')

    def _load_persisted_send_queue(self):
        load_send_queue(self.controller, self._send_queue_key(), self.send_queue, LOGGER)

    def _persist_send_queue(self, immediate=False):
        persist_send_queue(
            self.controller, self._send_queue_key(), self.send_queue, immediate=immediate
        )

    def enqueue_send(self,params,reason):
        qparams = deepcopy(params)
        dropped = self.send_queue.enqueue(qparams)
        if dropped is not None:
            LOGGER.warning('UD Mobile queue full ({}), dropped oldest notification'.format(SEND_QUEUE_MAX))
        LOGGER.warning('Queued UD Mobile notification ({} pending): {}'.format(self.send_queue.size(), reason))
        self._persist_send_queue()

    def flush_send_queue(self):
        if not self.can_deliver():
            return 0
        items = self.send_queue.pop_all()
        self._persist_send_queue(immediate=True)
        if len(items) == 0:
            return 0
        payloads, stale = self.send_queue.keep_fresh(items)
        if stale > 0:
            LOGGER.warning('Dropped {} stale queued UD Mobile notifications'.format(stale))
        for params in payloads:
            self.do_send(params)
        LOGGER.warning('Flushed {} queued UD Mobile notifications'.format(len(payloads)))
        return len(payloads)

    def _dispatch_send(self,params):
        self.thread = Thread(target=self.send,args=(params,))
        self.thread.daemon = True
        LOGGER.debug(f'Starting Thread {self.msg_cnt}')
        st = self.thread.start()
        LOGGER.debug('Thread start st={}'.format(st))
        return True

    def do_send(self,params):
        params = deepcopy(params)
        LOGGER.info('params={}'.format(params))
        if self.can_deliver():
            self.flush_send_queue()
        system = False
        if 'system' in params:
            system = params['system']
        # Fix up what a notify node sends.
        if 'device' in params:
            params['group'] = params['device']
            del params['device']
        if 'message' in params:
            params['title'] = params['message']
            params['body'] = ' '
            del params['message']
        if 'group' in params:
            if is_int(params['group']) and params['group'] == 0:
                LOGGER.info('Using default group')
            else:
                if is_int(params['group']):
                    # It's an index, so get the name
                    group = self.get_group_name_by_index(params['group'])
                    if group is False:
                        # Bad param, can't send
                        return
                params['groupid'] = group
            del params['group']
        if 'sound' in params:
            if is_int(params['sound']):
                sound = self.get_UDMobile_sound(params['sound'])
            else:
                sound = self.get_UDMobile_sound_by_name(params['sound'])
            if sound is None:
                del params['sound']
            else:
               params['sound'] = sound
        if not system and self.controller.edition == 'Free' and self.msg_cnt >= 8:
            self.set_error(ERROR_MAX,f'Reached max daily message count, please upgrde to Standard Edition {params}')
            params['title'] = 'Reached max daily message count, please upgrde to Standard Edition'
            params['body'] = ' '
        if not self.can_deliver():
            self.enqueue_send(params, 'UD Mobile can_deliver gate is false')
            return True
        self._dispatch_send(params)
        if not system:
            self.msg_cnt += 1
        # Always have to return true case we don't know..
        return True

    def requeue_failed_send(self, params, reason):
        retry_count = int(params.get('_retry_count', 0)) + 1
        if retry_count > FAILED_REQUEUE_MAX:
            LOGGER.error('UD Mobile failed message exceeded requeue max {}, dropping. reason={}'.format(FAILED_REQUEUE_MAX, reason))
            return
        qparams = deepcopy(params)
        qparams['_retry_count'] = retry_count
        self.enqueue_send(qparams, 'failed delivery (attempt {}): {}'.format(retry_count, reason))

    def send(self,params):
        sent = False
        retry = True
        cnt  = 0
        requeue_reason = None
        # Clear error if there was one
        self.set_error(ERROR_NONE)
        LOGGER.debug('params={}'.format(params))
        while (not sent and retry and (RETRY_MAX < 0 or cnt < RETRY_MAX)):
            cnt += 1
            LOGGER.info('try #{}'.format(cnt))
            res = self.api_post("notification/send",params)
            failed_count = 0
            if 'data' in res and 'failedCount' in res['data']:
                try:
                    failed_count = int(res['data']['failedCount'])
                except (TypeError, ValueError):
                    failed_count = -1
            if res['status'] is True and failed_count == 0:
                sent = True
                self.set_error(ERROR_NONE)
                LOGGER.info(f"Message Sent: {params}")
            else:
                # No status code or not 4xx code is
                LOGGER.debug(f"issue status={res['status']} failed_count={failed_count} res={res}")
                if failed_count > 0:
                    LOGGER.warning("UD Mobile accepted request but failed delivery count={}, payload={}".format(failed_count, res.get('data')))
                    retry = False
                    requeue_reason = 'failedCount={}'.format(failed_count)
                if 'code' in res and (res['code'] is not None and (res['code'] >= 400 and res['code'] < 500)):
                    LOGGER.warning('Previous error can not be fixed, will not retry')
                    retry = False
                    if requeue_reason is None:
                        requeue_reason = 'http {}'.format(res['code'])
                else:
                    LOGGER.warning('Previous error is retryable...')
                    if 'data' in res and 'failedCount' in res['data'] and res['data']['failedCount'] > 0:
                        LOGGER.error("From UDMobile: Failed to send to {} groups, will send again".format(res['data']['failedCount']))
            if (not sent):
                self.set_error(ERROR_MESSAGE_SEND,"ERROR Sending message")
                if (retry and (RETRY_MAX > 0 and cnt == RETRY_MAX)):
                    LOGGER.error('Giving up after {} tries'.format(cnt))
                    retry = False
            if (not sent and retry):
                time.sleep(RETRY_WAIT)
        if not sent and requeue_reason is not None:
            self.requeue_failed_send(params, requeue_reason)
        #LOGGER.info('is_sent={} id={} sent_at={}'.format(message.is_sent, message.id, str(message.sent_at)))
        return sent

    def get(self,url,params={}):
        params['token'] = self.app_key
        sent = False
        retry = True
        cnt  = 0
        while (not sent and retry and (RETRY_MAX < 0 or cnt < RETRY_MAX)):
            cnt += 1
            LOGGER.info('try {} #{}'.format(url,cnt))
            res = self.session.get(url,params)
            LOGGER.info('got {}'.format(res))
            if res['status'] is True and res['data']['status'] == 1:
                sent = True
                self.set_error(ERROR_NONE)
            else:
                if 'data' in res:
                    if 'errors' in res['data']:
                        LOGGER.error('From UDMobile: {}'.format(res['data']['errors']))
                # No status code or not 4xx code is
                LOGGER.debug('res={}'.format(res))
                if 'code' in res and (res['code'] is not None and (res['code'] >= 400 or res['code'] < 500)):
                    LOGGER.warning('Previous error can not be fixed, will not retry')
                    retry = False
                else:
                    LOGGER.warning('Previous error is retryable...')
            if (not sent):
                self.set_error(ERROR_UNKNOWN,"Unknown ERROR")
                if (retry and (RETRY_MAX > 0 and cnt == RETRY_MAX)):
                    LOGGER.error('Giving up after {} tries'.format(cnt))
                    retry = False
            if (not sent and retry):
                time.sleep(RETRY_WAIT)
        #LOGGER.info('is_sent={} id={} sent_at={}'.format(message.is_sent, message.id, str(message.sent_at)))
        if 'data' in res:
            return { 'status': sent, 'data': res['data'] }
        else:
            return { 'status': sent, 'data': False }

    def rest_send(self,params):
        LOGGER.debug('params={}'.format(params))
        if 'priority' in params:
            # Our priority's start at 0 UDMobiles starts at -2... Should have used their numbers...
            # So assume rest calls pass in UDMobile number, so convert to our number.
            params['priority'] = int(params['priority']) + 2
        return self.do_send(params)

    _init_st = None
    id = 'udmobile'
    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 2,  'name': 'Last Status'},
        {'driver': 'ERR', 'value': 0, 'uom': 25, 'name': 'Error'},
    ]
    commands = {
                'GV10': cmd_send_message,
                }
