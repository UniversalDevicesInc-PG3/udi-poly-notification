"""
  Notification Telegram Node
"""

from udi_interface import Node,LOGGER
from threading import Thread,Event
import time
import logging
import collections
from copy import deepcopy
from node_funcs import (
    make_file_dir,
    is_int,
    get_default_sound_index,
    SendQueue,
    send_queue_storage_key,
    load_send_queue,
    persist_send_queue,
)
from telegram_funcs import (
    telegram_ok,
    telegram_description,
    coerce_chat_id,
    chat_id_from_updates,
    sanitize_users,
    bot_link_from_get_me,
    external_link,
)

ERROR_NONE       = 0
ERROR_UNKNOWN    = 1
ERROR_APP_AUTH   = 2
ERROR_USER_AUTH  = 3
ERROR_MESSAGE_CREATE = 4
ERROR_MESSAGE_SEND   = 5

REM_PREFIX = "REMOVED-"

# How many tries to get or post, -1 is forever
RETRY_MAX = -1
# How long to wait between tries, in seconds
RETRY_WAIT = 5
SEND_QUEUE_MAX = 128
SEND_QUEUE_MAX_AGE = 3600
FAILED_REQUEUE_MAX = 5

class TelegramUB(Node):
    """
    """
    def __init__(self, controller, primary, address, name, session, info):
        """
        """
        # Need these for l_debug
        self.name     = name
        self.address  = address
        self.controller = controller
        self.session  = session
        self.info     = info
        self.iname    = info['name']
        self.oid      = self.id
        self.id       = 'telegramub_' + self.iname
        self.http_api_key  = self.info['http_api_key']
        # Initial releases didn't have this
        if 'users' in self.info:
            self.users         = sanitize_users(self.info['users'])
        else:
            self.users         = list()
        self.user_id       = None
        self.authorized    = False
        self._init_st      = None
        self.send_queue = SendQueue(SEND_QUEUE_MAX, SEND_QUEUE_MAX_AGE)
        LOGGER.debug('{} {}'.format(address,name))
        controller.poly.subscribe(controller.poly.START,                  self.handler_start, address)
        super(TelegramUB, self).__init__(controller.poly, primary, address, name)

    def handler_start(self):
        """
        """
        LOGGER.info('')
        self._load_persisted_send_queue()
        vstat = self.validate()
        if vstat.get('status') is not True:
            self.authorized = False
            self.set_ready(False)
            self.set_error(vstat.get('error', ERROR_APP_AUTH))
            self._init_st = False
        else:
            self.authorized = True
            self.set_ready(True)
            self.set_error(ERROR_NONE)
            self._init_st = True
            self.controller.on_service_node_ready(self)
            self.flush_send_queue()
        LOGGER.info("Authorized={}".format(self.authorized))

    def _send_queue_key(self):
        return send_queue_storage_key('telegram', self.iname)

    def _load_persisted_send_queue(self):
        load_send_queue(self.controller, self._send_queue_key(), self.send_queue, LOGGER)

    def _persist_send_queue(self, immediate=False):
        persist_send_queue(
            self.controller, self._send_queue_key(), self.send_queue, immediate=immediate
        )

    def enqueue_send(self, params, reason):
        qparams = deepcopy(params)
        dropped = self.send_queue.enqueue(qparams)
        if dropped is not None:
            LOGGER.warning(
                'Telegram {} queue full ({}), dropped oldest notification'
                .format(self.iname, SEND_QUEUE_MAX)
            )
        LOGGER.warning(
            'Queued Telegram {} notification ({} pending): {}'
            .format(self.iname, self.send_queue.size(), reason)
        )
        self._persist_send_queue()

    def flush_send_queue(self):
        if not self.authorized:
            return 0
        items = self.send_queue.pop_all()
        self._persist_send_queue(immediate=True)
        if len(items) == 0:
            return 0
        payloads, stale = self.send_queue.keep_fresh(items)
        if stale > 0:
            LOGGER.warning(
                'Dropped {} stale queued Telegram {} notifications'
                .format(stale, self.iname)
            )
        for params in payloads:
            self.post(params, retry_count=int(params.get('_retry_count', 0)))
        LOGGER.warning(
            'Flushed {} queued Telegram {} notifications'
            .format(len(payloads), self.iname)
        )
        return len(payloads)

    def requeue_failed_send(self, params, reason, retry_count=0):
        retry_count = int(params.get('_retry_count', retry_count)) + 1
        if retry_count > FAILED_REQUEUE_MAX:
            LOGGER.error(
                'Telegram {} failed message exceeded requeue max {}, dropping. reason={}'
                .format(self.iname, FAILED_REQUEUE_MAX, reason)
            )
            return
        qparams = deepcopy(params)
        qparams['_retry_count'] = retry_count
        self.enqueue_send(
            qparams, 'failed delivery (attempt {}): {}'.format(retry_count, reason)
        )

    def _resolve_user_id(self):
        if self.user_id is not None:
            return self._coerce_chat_id(self.user_id)
        if self.users:
            return coerce_chat_id(self.users[0])
        return None

    def _coerce_chat_id(self, val):
        return coerce_chat_id(val)

    def _notice_key(self):
        return f'telegramub_{self.iname}'

    def validate(self):
        LOGGER.debug('Authorizing Telegram app {}'.format(self.http_api_key))
        self.users = sanitize_users(self.users)
        self.user_id = None
        notice_key = self._notice_key()
        token = self.http_api_key

        me_res = self.session.get(f"bot{token}/getMe")
        LOGGER.debug('getMe: {}'.format(me_res))
        if not telegram_ok(me_res):
            msg = (
                f"Failed to authorize Telegram bot {self.iname}: "
                f"{telegram_description(me_res)}"
            )
            LOGGER.error(msg)
            self.controller.Notices[notice_key] = msg
            return {
                'status': False,
                'error': ERROR_APP_AUTH,
                'data': me_res.get('data') if isinstance(me_res, dict) else False,
            }

        res = self.session.get(f"bot{token}/getUpdates")
        LOGGER.debug('getUpdates: {}'.format(res))
        if not telegram_ok(res):
            msg = (
                f"Telegram {self.iname} getUpdates failed: "
                f"{telegram_description(res)}"
            )
            LOGGER.error(msg)
            self.controller.Notices[notice_key] = msg
            return {
                'status': False,
                'error': ERROR_APP_AUTH,
                'data': res.get('data') if isinstance(res, dict) else False,
            }

        self.controller.Notices.delete(notice_key)
        self.controller.Notices.delete('telegramub')

        if not self.users:
            discovered = chat_id_from_updates(res.get('data'))
            if discovered is not None:
                self.user_id = coerce_chat_id(discovered)
                self.users = [str(self.user_id)]
                self.controller.persist_telegram_users(self.iname, self.users)
            else:
                bot_link = bot_link_from_get_me(me_res.get('data'))
                if bot_link:
                    self.controller.Notices[notice_key] = (
                        f"Telegram {self.iname}: send /start to your bot at "
                        f'{external_link(bot_link, bot_link)}, '
                        f"then restart the nodeserver."
                    )
                else:
                    self.controller.Notices[notice_key] = (
                        f"Telegram {self.iname}: send /start to your bot, then "
                        f"restart the nodeserver."
                    )
                return {
                    'status': False,
                    'error': ERROR_USER_AUTH,
                    'data': res.get('data'),
                }
        else:
            self.user_id = coerce_chat_id(self.users[0])

        if self.user_id is None:
            msg = f"Telegram {self.iname}: invalid user id in configuration"
            LOGGER.error(msg)
            self.controller.Notices[notice_key] = msg
            return {
                'status': False,
                'error': ERROR_USER_AUTH,
                'data': res.get('data'),
            }

        self.do_send({'text': f'{self.name} has started up'}, startup_test=True)
        return {'status': True, 'data': res.get('data')}



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
        if self.controller.rest is None:
            rest_ip = "None"
            rest_port = "None"
        else:
            rest_ip = self.controller.rest.ip
            rest_port = self.controller.rest.listen_port
        info = [
            '<h4>Example Network Resource for Telegram User Bot</h4><ul><li>http<li>POST<li>Host:{0}<li>Port:{1}<li>Path: /send?node={2}<li>Encode URL: not checked<li>Timeout: 5000<li>Mode: Raw Text</ul>'.format(rest_ip,rest_port,self.address),
        ]
        return ''.join(info)

    def write_profile(self,nls):
        LOGGER.debug('')
        #
        # nodedefs
        #
        # Open the template, and read into a string for formatting.
        template_f = 'template/nodedef/telegramub.xml'
        LOGGER.debug("Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Open the output nodedefs file
        output_f   = 'profile/nodedef/{0}.xml'.format(self.iname)
        make_file_dir(output_f)
        # Write the nodedef file with our info
        LOGGER.debug("Writing {}".format(output_f))
        out_h = open(output_f, "w")
        out_h.write(data.format(self.id,self.iname))
        out_h.close()
        #
        # nls
        #
        nls.write("\n# Entries for Telegram User Bot {} {}\n".format(self.id,self.name))
        nls.write("ND-{0}-NAME = {1}\n".format(self.id,self.name))
        #
        # editor
        #
        # Open the template, and read into a string for formatting.
        template_f = 'template/editor/telegramub.xml'
        LOGGER.debug("Reading {}".format(template_f))
        with open (template_f, "r") as myfile:
            data=myfile.read()
            myfile.close()
        # Write the editors file with our info
        output_f   = 'profile/editor/{0}.xml'.format(self.iname)
        make_file_dir(output_f)
        LOGGER.debug("Writing {}".format(output_f))
        editor_h = open(output_f, "w")
        # TODO: We could create a better subst with - and , but do we need to?
        # TODO: Test calling get_subset_str in node_funcs.py
        editor_h.write(data.format(self.iname))
        editor_h.close()

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

    def set_ready(self, val):
        LOGGER.info('Set Ready to {}'.format(val))
        if val is True:
            val = 1
        elif val is False or val is None:
            val = 0
        else:
            val = int(val)
        self.setDriver('GV1', val)

    def set_error(self,val):
        LOGGER.info(val)
        if val is False:
            val = 0
        elif val is True:
            val = 1
        LOGGER.info('Set ERR to {}'.format(val))
        self.setDriver('ERR', val)
        self.set_st(True if val == 0 else False)


    def cmd_send_message(self,command):
        LOGGER.info('')
        # Default create message params
        md = self.controller.get_current_message()
        # md will contain title and message
        return self.do_send({ 'title': md['title'], 'text': md['message']})

    def cmd_send_sys_short(self,command):
        LOGGER.info('')
        return self.do_send({ 'message': self.controller.get_sys_short()})

    def do_send(self, params, startup_test=False):
        LOGGER.info('params={}'.format(params))
        params = dict(params)
        title = params.pop('title', None)
        if 'message' in params:
            params['text'] = params['message']
            del params['message']
        if 'text' not in params:
            params['text'] = "NOT_SPECIFIED"
        if title:
            if params['text'] and params['text'] != "NOT_SPECIFIED":
                params['text'] = f"{title}\n{params['text']}"
            else:
                params['text'] = title
        chat_id = self._resolve_user_id()
        if chat_id is None:
            LOGGER.error(f"user not defined for {self.iname}")
            self.set_ready(False)
            self.set_error(ERROR_USER_AUTH)
            return False
        self.user_id = chat_id
        params['chat_id'] = chat_id
        # Telegram doesn't support any of these...
        for key in ('device','priority','format','retry','expire','sound','subject'):
            if key in params:
                del params[key]
        if startup_test:
            return self.post(params)
        if not self.authorized:
            self.enqueue_send(params, 'Telegram not authorized')
            return True
        self.flush_send_queue()
        self.thread = Thread(target=self.post, args=(params, 0))
        self.thread.daemon = True
        LOGGER.debug('Starting Thread')
        st = self.thread.start()
        LOGGER.debug('Thread start st={}'.format(st))
        # Always have to return true case we don't know..
        return True

    def post(self, params, retry_count=0):
        self.set_error(ERROR_NONE)
        LOGGER.debug('params={}'.format(params))
        res = self.session.post(
            f"bot{self.http_api_key}/sendMessage",
            params,
            content="urlencode",
        )
        LOGGER.debug('res={}'.format(res))
        if telegram_ok(res):
            self.set_error(ERROR_NONE)
            self.set_ready(True)
            return True
        LOGGER.error('From Telegram sendMessage: {}'.format(telegram_description(res)))
        data = res.get('data') if isinstance(res, dict) else None
        if isinstance(data, dict) and data.get('error_code') in (400, 401, 403, 404):
            self.set_error(ERROR_MESSAGE_SEND)
            return False
        if isinstance(res, dict) and res.get('code') is not None and 400 <= res['code'] < 500:
            LOGGER.warning('Previous error can not be fixed, will not requeue')
            self.set_error(ERROR_MESSAGE_SEND)
            return False
        if isinstance(res, dict) and res.get('retryable') is False:
            self.set_error(ERROR_MESSAGE_SEND)
            return False
        self.set_error(ERROR_MESSAGE_SEND)
        self.requeue_failed_send(params, telegram_description(res), retry_count)
        return False

    def get(self,url,params={}):
        params['token'] = self.http_api_key
        sent = False
        retry = True
        cnt  = 0
        while (not sent and retry and (RETRY_MAX < 0 or cnt < RETRY_MAX)):
            cnt += 1
            LOGGER.warning('try {} #{}'.format(url,cnt))
            res = self.session.get(url,params)
            LOGGER.info('got {}'.format(res))
            if res['status'] is True and res['data']['status'] == 1:
                sent = True
                self.set_error(ERROR_NONE)
            else:
                if 'data' in res:
                    if 'errors' in res['data']:
                        LOGGER.error('From Telegram: {}'.format(res['data']['errors']))
                # No status code or not 4xx code is
                LOGGER.debug('res={}'.format(res))
                if 'code' in res and (res['code'] is not None and (res['code'] >= 400 or res['code'] < 500)):
                    LOGGER.warning('Previous error can not be fixed, will not retry')
                    retry = False
                else:
                    LOGGER.warning('Previous error is retryable...')
            if (not sent):
                self.set_error(ERROR_UNKNOWN)
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
        params['text'] = params['message']
        del params['message']
        return self.do_send(params)

    _init_st = None
    id = 'Telegram'
    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 2, 'name': 'Last Status'},
        {'driver': 'ERR', 'value': 0, 'uom': 25, 'name': 'Error'},
        {'driver': 'GV1', 'value': 0, 'uom': 2,  'name': 'Ready'},
    ]
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SEND_MESSAGE': cmd_send_message,
                'SEND_SYS_CUSTOM': cmd_send_sys_short,
                }