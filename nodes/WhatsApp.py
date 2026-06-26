"""
  Notification WhatsApp Node (CallMeBot / TextMeBot)
"""

from udi_interface import Node, LOGGER
from threading import Thread, Lock
from copy import deepcopy
import time

from node_funcs import (
    make_file_dir,
    is_int,
    SendQueue,
    send_queue_storage_key,
    load_send_queue,
    persist_send_queue,
    get_send_queue_debouncer,
)

PROVIDER_CALLMEBOT = 'callmebot'
PROVIDER_TEXTMEBOT = 'textmebot'
WHATSAPP_PROVIDERS = (PROVIDER_CALLMEBOT, PROVIDER_TEXTMEBOT)

WHATSAPP_PROVIDER_CONFIG = {
    PROVIDER_CALLMEBOT: {
        'label': 'CallMeBot',
        'base_url': 'https://api.callmebot.com',
        'path': 'whatsapp.php',
        'phone_param': 'phone',
    },
    PROVIDER_TEXTMEBOT: {
        'label': 'TextMeBot',
        'base_url': 'https://api.textmebot.com',
        'path': 'send.php',
        'phone_param': 'recipient',
    },
}


def normalize_whatsapp_provider(raw, default=PROVIDER_CALLMEBOT):
    if raw is None or str(raw).strip() == '':
        return default
    key = str(raw).strip().lower().replace(' ', '').replace('_', '').replace('-', '')
    aliases = {
        'callmebot': PROVIDER_CALLMEBOT,
        'callme': PROVIDER_CALLMEBOT,
        'textmebot': PROVIDER_TEXTMEBOT,
        'textme': PROVIDER_TEXTMEBOT,
    }
    return aliases.get(key, key)


ERROR_NONE = 0
ERROR_UNKNOWN = 1
ERROR_APP_AUTH = 2
ERROR_USER_AUTH = 3
ERROR_MESSAGE_CREATE = 4
ERROR_MESSAGE_SEND = 5

RETRY_MAX = -1
RETRY_WAIT = 5
RECIPIENT_DELAY = 3
TEXTMEBOT_SEND_INTERVAL = 5
SEND_QUEUE_MAX = 128
SEND_QUEUE_MAX_AGE = 3600
FAILED_REQUEUE_MAX = 5
RATE_LIMIT_COOLDOWN = 60


class WhatsApp(Node):
    def __init__(self, controller, primary, address, name, session, info):
        self.name = name
        self.address = address
        self.controller = controller
        self.session = session
        self.info = info
        self.iname = info['name']
        self.oid = self.id
        self.id = 'whatsapp_' + self.iname
        self.provider = normalize_whatsapp_provider(info.get('provider'))
        self.recipients = self._normalize_recipients(info.get('recipients'))
        self.phones_list = self._build_phones_list()
        self._sys_short = None
        self._send_lock = Lock()
        self._flush_timer_lock = Lock()
        self._flush_timer = None
        self._rate_limited_until = 0
        self._last_textmebot_send_at = 0
        self.authorized = False
        self._init_st = None
        self.send_queue = SendQueue(SEND_QUEUE_MAX, SEND_QUEUE_MAX_AGE)
        self.driver = {}
        LOGGER.debug('{} {}'.format(address, name))
        controller.poly.subscribe(controller.poly.START, self.handler_start, address)
        super(WhatsApp, self).__init__(controller.poly, primary, address, name)

    def _normalize_recipients(self, recipients):
        normalized = []
        if not isinstance(recipients, list):
            return normalized
        for entry in recipients:
            if not isinstance(entry, dict):
                continue
            phone = str(entry.get('phone', '')).strip()
            apikey = str(entry.get('apikey', '')).strip()
            if phone or apikey:
                normalized.append({'phone': phone, 'apikey': apikey})
        return normalized

    def _build_phones_list(self):
        phones = ['All Recipients']
        for recipient in self.recipients:
            phone = recipient.get('phone', '')
            if phone and phone not in phones:
                phones.append(phone)
        return phones

    def _recipients_for_index(self, phone_idx=None):
        if phone_idx is None:
            phone_idx = self.get_phone_index()
        elif not is_int(phone_idx):
            LOGGER.error('Phone index {} is not an integer'.format(phone_idx))
            self.set_error(ERROR_PARAM)
            return []
        phone_idx = int(phone_idx)
        if phone_idx == 0:
            return list(self.recipients)
        idx = phone_idx - 1
        if 0 <= idx < len(self.recipients):
            return [self.recipients[idx]]
        LOGGER.error(
            'Bad phone index {} must be < {}'.format(phone_idx, len(self.phones_list))
        )
        self.set_error(ERROR_PARAM)
        return []

    def _send_notice_key(self):
        return f'whatsapp_send_{self.iname}'

    def _notice_key(self):
        return f'whatsapp_{self.iname}'

    def _provider_label(self):
        cfg = WHATSAPP_PROVIDER_CONFIG.get(self.provider, {})
        return cfg.get('label', self.provider)

    def _callmebot_ok(self, res):
        # CallMeBot returns HTML (not JSON). 200/201/210 all mean accepted/queued.
        if not isinstance(res, dict):
            return False
        code = res.get('code')
        if code not in (200, 201, 210):
            return False
        data = res.get('data')
        if isinstance(data, str):
            lower = data.lower()
            if 'message queued' in lower:
                return True
            if 'error' in lower and 'queued' not in lower:
                return False
        return True

    def _textmebot_ok(self, res):
        if not isinstance(res, dict):
            return False
        if res.get('code') != 200:
            return False
        data = res.get('data')
        if isinstance(data, str):
            lower = data.lower()
            if 'result:' in lower and 'success' in lower:
                return True
            if 'success!' in lower:
                return True
            if 'error' in lower:
                return False
        return True

    def _send_ok(self, res):
        if self.provider == PROVIDER_TEXTMEBOT:
            return self._textmebot_ok(res)
        return self._callmebot_ok(res)

    def _callmebot_rate_limited(self, res):
        return isinstance(res, dict) and res.get('code') == 503

    def _textmebot_rate_limited(self, res):
        return isinstance(res, dict) and res.get('code') in (429, 503)

    def _send_rate_limited(self, res):
        if self.provider == PROVIDER_TEXTMEBOT:
            return self._textmebot_rate_limited(res)
        return self._callmebot_rate_limited(res)

    def _is_rate_limited(self):
        return time.time() < self._rate_limited_until

    def _mark_rate_limited(self):
        self._rate_limited_until = time.time() + RATE_LIMIT_COOLDOWN
        self._persist_rate_limited_until()

    def _rate_limit_key(self):
        return f'rate_limited_until_whatsapp_{self.iname}_{self.provider}'

    def _load_rate_limited_until(self):
        raw = self.controller.get_data(self._rate_limit_key(), None)
        if raw is None and self.provider == PROVIDER_CALLMEBOT:
            raw = self.controller.get_data(f'rate_limited_until_whatsapp_{self.iname}', 0)
        try:
            until = float(raw or 0)
        except (TypeError, ValueError):
            until = 0
        if until > time.time():
            self._rate_limited_until = until
            LOGGER.info(
                'WhatsApp %s (%s): restored rate-limit cooldown (~%ss remaining)',
                self.iname,
                self._provider_label(),
                int(until - time.time()),
            )
        else:
            self._rate_limited_until = 0

    def _persist_rate_limited_until(self):
        key = self._rate_limit_key()
        if self._rate_limited_until > time.time():
            get_send_queue_debouncer().write_now(
                self.controller, key, self._rate_limited_until
            )
        else:
            get_send_queue_debouncer().write_now(self.controller, key, 0)

    def _callmebot_error(self, res):
        if isinstance(res, dict):
            code = res.get('code')
            if code == 503:
                return 'CallMeBot rate limit (too many requests) — wait and try again'
            if res.get('errorMessage') and res['errorMessage'] != 'Unknown response':
                return res['errorMessage']
            data = res.get('data')
            if isinstance(data, str) and data.strip():
                return data.strip()
        return 'Unknown CallMeBot error'

    def _textmebot_error(self, res):
        if isinstance(res, dict):
            code = res.get('code')
            if code in (429, 503):
                return 'TextMeBot rate limit (too many requests) — wait and try again'
            if res.get('errorMessage') and res['errorMessage'] != 'Unknown response':
                return res['errorMessage']
            data = res.get('data')
            if isinstance(data, str) and data.strip():
                return data.strip()
        return 'Unknown TextMeBot error'

    def _send_error(self, res):
        if self.provider == PROVIDER_TEXTMEBOT:
            return self._textmebot_error(res)
        return self._callmebot_error(res)

    def _valid_text(self, text):
        if text is None:
            return False
        s = str(text).strip()
        return s not in ('', 'NOT_SPECIFIED', 'NOT_DEFINED', 'None')

    def _is_error_placeholder(self, msg):
        if not self._valid_text(msg):
            return True
        s = str(msg).strip()
        return s == 'ERROR' or s.startswith('ERROR\n')

    def _wait_textmebot_interval(self):
        if self.provider != PROVIDER_TEXTMEBOT:
            return
        wait = TEXTMEBOT_SEND_INTERVAL - (time.time() - self._last_textmebot_send_at)
        if wait > 0:
            LOGGER.debug(
                'TextMeBot %s: waiting %.1fs before next message',
                self.iname,
                wait,
            )
            time.sleep(wait)

    def _note_textmebot_send(self):
        if self.provider == PROVIDER_TEXTMEBOT:
            self._last_textmebot_send_at = time.time()

    def _send_sync(self, phone, apikey, text):
        with self._send_lock:
            self._wait_textmebot_interval()
            cfg = WHATSAPP_PROVIDER_CONFIG[self.provider]
            params = {
                cfg['phone_param']: phone,
                'text': text,
                'apikey': apikey,
            }
            sent = False
            retry = True
            cnt = 0
            last_res = None
            label = self._provider_label()
            while not sent and retry and (RETRY_MAX < 0 or cnt < RETRY_MAX):
                cnt += 1
                LOGGER.debug('%s try #%s phone=%s', label, cnt, phone)
                last_res = self.session.get(cfg['path'], params=params)
                self._note_textmebot_send()
                LOGGER.debug('%s res=%s', label, last_res)
                if self._send_ok(last_res):
                    sent = True
                elif self._send_rate_limited(last_res):
                    self._mark_rate_limited()
                    retry = False
                else:
                    if isinstance(last_res, dict) and last_res.get('code') is not None and 400 <= last_res['code'] < 500:
                        retry = False
                    elif isinstance(last_res, dict) and last_res.get('retryable') is False:
                        retry = False
                    if not sent and retry:
                        time.sleep(RETRY_WAIT)
            return sent, last_res

    def _send_queue_key(self):
        return send_queue_storage_key('whatsapp', self.iname)

    def _load_persisted_send_queue(self):
        self._load_rate_limited_until()
        load_send_queue(self.controller, self._send_queue_key(), self.send_queue, LOGGER)
        if self.send_queue.size() > 0:
            self._update_send_queue_notice()

    def _persist_send_queue(self, immediate=False):
        persist_send_queue(
            self.controller, self._send_queue_key(), self.send_queue, immediate=immediate
        )

    def enqueue_send(self, text, recipients, reason, retry_count=0):
        payload = {
            'text': text,
            'recipients': deepcopy(recipients),
            '_retry_count': retry_count,
        }
        dropped = self.send_queue.enqueue(payload)
        if dropped is not None:
            LOGGER.warning(
                'WhatsApp {} queue full ({}), dropped oldest queued message'
                .format(self.iname, SEND_QUEUE_MAX)
            )
        LOGGER.warning(
            'Queued WhatsApp {} message ({} pending): {}'
            .format(self.iname, self.send_queue.size(), reason)
        )
        self._persist_send_queue()
        self._update_send_queue_notice()

    def requeue_failed_send(self, text, recipients, reason, retry_count=0):
        retry_count += 1
        if retry_count > FAILED_REQUEUE_MAX:
            LOGGER.error(
                'WhatsApp {} dropped queued message after {} retries: {}'
                .format(self.iname, FAILED_REQUEUE_MAX, reason)
            )
            return
        self.enqueue_send(text, recipients, reason, retry_count=retry_count)
        self._schedule_flush_queue()

    def _update_send_queue_notice(self):
        n = self.send_queue.size()
        key = self._send_notice_key()
        if n > 0:
            wait = max(0, int(self._rate_limited_until - time.time()))
            self.controller.Notices[key] = (
                f'WhatsApp {self.iname}: {n} message(s) queued for {self._provider_label()} '
                f'(rate limit). Retrying in ~{wait}s.'
            )
        elif not self._is_rate_limited():
            self.controller.Notices.delete(key)

    def _schedule_flush_queue(self):
        if self.send_queue.size() == 0:
            return
        with self._flush_timer_lock:
            if self._flush_timer is not None and self._flush_timer.is_alive():
                return
            delay = max(1.0, self._rate_limited_until - time.time())
            self._flush_timer = Thread(target=self._delayed_flush, args=(delay,))
            self._flush_timer.daemon = True
            self._flush_timer.start()

    def _delayed_flush(self, delay):
        time.sleep(delay)
        self.flush_send_queue()

    def flush_send_queue(self):
        if not self.authorized:
            return 0
        if self._is_rate_limited():
            self._schedule_flush_queue()
            return 0
        items = self.send_queue.pop_all()
        self._persist_send_queue(immediate=True)
        if len(items) == 0:
            return 0
        payloads, stale = self.send_queue.keep_fresh(items)
        if stale > 0:
            LOGGER.warning(
                'Dropped {} stale queued WhatsApp {} messages'
                .format(stale, self.iname)
            )
        sent_count = 0
        for payload in payloads:
            if self.post(
                payload['text'],
                payload['recipients'],
                from_queue=True,
                retry_count=payload.get('_retry_count', 0),
            ):
                sent_count += 1
        if sent_count > 0:
            LOGGER.warning(
                'Flushed {} queued WhatsApp {} message(s)'
                .format(sent_count, self.iname)
            )
        self._update_send_queue_notice()
        return sent_count

    def validate(self):
        notice_key = self._notice_key()
        self.controller.Notices.delete(notice_key)

        if not self.recipients:
            msg = f"WhatsApp {self.iname}: at least one recipient is required"
            LOGGER.error(msg)
            self.controller.Notices[notice_key] = msg
            return {'status': False, 'error': msg}

        errors = []
        rate_limited = False
        startup_text = f'{self.name} has started up'
        for recipient in self.recipients:
            phone = recipient['phone']
            apikey = recipient['apikey']
            if not phone.startswith('+'):
                errors.append(f"{phone or '(empty)'}: phone must include country code and start with +")
                continue
            if not apikey:
                errors.append(f"{phone}: missing {self._provider_label()} apikey")
                continue
            if self._is_rate_limited():
                rate_limited = True
                self.enqueue_send(
                    startup_text,
                    [{'phone': phone, 'apikey': apikey}],
                    'startup validation (rate limit cooldown)',
                )
                continue
            sent, res = self._send_sync(phone, apikey, startup_text)
            if sent:
                LOGGER.info(
                    'WhatsApp %s (%s): startup test message sent to %s',
                    self.iname,
                    self._provider_label(),
                    phone,
                )
                continue
            if self._send_rate_limited(res):
                rate_limited = True
                self.enqueue_send(
                    startup_text,
                    [{'phone': phone, 'apikey': apikey}],
                    'startup validation (rate limited)',
                )
                continue
            errors.append(f"{phone}: {self._send_error(res)}")

        if rate_limited:
            self._persist_send_queue(immediate=True)
            self._schedule_flush_queue()

        if errors:
            msg = f"WhatsApp {self.iname}: " + "; ".join(errors)
            LOGGER.error(msg)
            self.controller.Notices[notice_key] = msg
            return {'status': False, 'error': msg}

        return {'status': True, 'rate_limited': rate_limited}

    def handler_start(self):
        LOGGER.info('')
        self._load_persisted_send_queue()
        self.driver = {}
        self.phones_list = self._build_phones_list()
        self.set_phone(self.get_phone_index())
        self.set_message(self.get_message())
        vstat = self.validate()
        self.init_error_message = None
        if vstat.get('status') is not True:
            self.authorized = False
            self.init_error_message = vstat.get('error')
        else:
            self.authorized = True
        LOGGER.info("Authorized={}".format(self.authorized))
        if self.authorized:
            self.set_error(ERROR_NONE)
            self._init_st = True
            if vstat.get('rate_limited'):
                LOGGER.warning(
                    'WhatsApp %s startup validation rate limited; startup test message queued',
                    self.iname,
                )
                self.controller.Notices[self._notice_key()] = (
                    f'WhatsApp {self.iname}: startup test message queued ({self._provider_label()} rate limit)'
                )
            self.controller.on_service_node_ready(self)
        else:
            self.set_error(ERROR_APP_AUTH)
            self._init_st = False
        self.flush_send_queue()

    def init_st(self):
        return self._init_st

    def query(self):
        self.reportDrivers()

    def config_info_rest(self):
        if self.controller.rest is None:
            listen_url = None
        else:
            listen_url = self.controller.rest.listen_url
        return '<li>curl -d \'{{"node":"{0}", "message":"The Message", "subject":"The Subject"}}\' -H "Content-Type: application/json" -X POST {1}/send'.format(
            self.address, listen_url
        )

    def config_info_nr(self):
        if self.controller.rest is None:
            rest_ip = "None"
            rest_port = "None"
        else:
            rest_ip = self.controller.rest.ip
            rest_port = self.controller.rest.listen_port
        return (
            '<h4>Example Network Resource for WhatsApp ({0})</h4>'
            '<ul><li>http<li>POST<li>Host:{1}<li>Port:{2}<li>Path: /send?node={3}'
            '<li>Encode URL: not checked<li>Timeout: 5000<li>Mode: Raw Text</ul>'
        ).format(self._provider_label(), rest_ip, rest_port, self.address)

    def write_profile(self, nls):
        LOGGER.debug('')
        template_f = 'template/nodedef/whatsapp.xml'
        LOGGER.debug("Reading {}".format(template_f))
        with open(template_f, "r") as myfile:
            data = myfile.read()
        output_f = 'profile/nodedef/{0}.xml'.format(self.iname)
        make_file_dir(output_f)
        LOGGER.debug("Writing {}".format(output_f))
        with open(output_f, "w") as out_h:
            out_h.write(data.format(self.id, self.iname, self.controller.sys_notify_editor))

        nls.write("\n# Entries for WhatsApp {} {}\n".format(self.id, self.name))
        nls.write("ND-{0}-NAME = {1}\n".format(self.id, self.name))
        subst = []
        for idx, phone in enumerate(self.phones_list):
            nls.write("WAP_{0}-{1} = {2}\n".format(self.iname, idx, phone))
            subst.append(str(idx))
        if len(subst) == 0:
            subst.append('0')

        template_f = 'template/editor/whatsapp.xml'
        LOGGER.debug("Reading {}".format(template_f))
        with open(template_f, "r") as myfile:
            data = myfile.read()
        output_f = 'profile/editor/{0}.xml'.format(self.iname)
        make_file_dir(output_f)
        LOGGER.debug("Writing {}".format(output_f))
        with open(output_f, "w") as editor_h:
            editor_h.write(data.format(self.iname, ",".join(subst)))

    def set_st(self, val):
        LOGGER.info(val)
        if val is False or val is None:
            val = 0
        elif val is True:
            val = 1
        else:
            val = int(val)
        LOGGER.info('Set ST to {}'.format(val))
        self.setDriver('ST', val)

    def set_error(self, val):
        LOGGER.info(val)
        if val is False:
            val = 0
        elif val is True:
            val = 1
        LOGGER.info('Set ERR to {}'.format(val))
        self.setDriver('ERR', val)
        self.set_st(True if val == 0 else False)

    def get_phone_index(self):
        cval = self.getDriver('GV1')
        if cval is None:
            return 0
        return int(cval)

    def set_phone(self, val):
        LOGGER.info(val)
        if val is None:
            val = 0
        val = int(val)
        LOGGER.info('Set GV1 to {}'.format(val))
        self.setDriver('GV1', val)

    def get_message(self):
        cval = self.getDriver('GV3')
        if cval is None:
            return 0
        return int(cval)

    def set_message(self, val):
        LOGGER.info(val)
        if val is None:
            val = 0
        val = int(val)
        LOGGER.info('Set GV3 to {}'.format(val))
        self.setDriver('GV3', val)

    def get_sys_short(self):
        LOGGER.debug('sys_short={}'.format(self._sys_short))
        return self._sys_short

    def set_sys_short(self, val):
        LOGGER.info('val={}'.format(val))
        self._sys_short = val

    def cmd_set_phone(self, command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_phone(val)

    def cmd_set_message(self, command):
        val = int(command.get('value'))
        LOGGER.info(val)
        self.set_message(val)

    def cmd_set_sys_short(self, command):
        LOGGER.debug('command={}'.format(command))
        msg = command.get('value')
        if msg is None:
            parsed = self.controller.get_message_from_query(command.get('query'))
            if self._is_error_placeholder(parsed.get('message')):
                LOGGER.error(
                    'WhatsApp {}: could not read system custom content from command'
                    .format(self.iname)
                )
                self.set_error(ERROR_MESSAGE_CREATE)
                return False
            msg = parsed['message']
        LOGGER.info(msg)
        self.set_sys_short(msg)
        return True

    def cmd_send_message(self, command):
        LOGGER.info('')
        md = self.controller.get_current_message()
        return self.do_send({'title': md['title'], 'text': md['message']})

    def cmd_send_sys_short(self, command):
        LOGGER.info('')
        msg = self.controller.get_sys_short()
        if self._is_error_placeholder(msg):
            LOGGER.error(
                'WhatsApp {}: no system custom message — use System Custom Content on the controller first'
                .format(self.iname)
            )
            self.set_error(ERROR_MESSAGE_CREATE)
            return False
        return self.do_send({'message': msg})

    def cmd_send_my_message(self, command):
        LOGGER.info('')
        md = self.controller.get_message_by_id(self.get_message())
        return self.do_send({'title': md['title'], 'text': md['message']})

    def cmd_send_my_sys_short(self, command):
        LOGGER.info('')
        msg = self.get_sys_short()
        if self._is_error_placeholder(msg):
            msg = None
        if not self._valid_text(msg):
            LOGGER.error(
                'WhatsApp {}: no custom message on this node — use System Custom Content first'
                .format(self.iname)
            )
            self.set_error(ERROR_MESSAGE_CREATE)
            return False
        return self.do_send({'message': msg})

    def cmd_send_sys_short_with_params(self, command):
        LOGGER.debug('command={}'.format(command))
        query = command.get('query')
        phone_idx = None
        if query.get('Phone.uom25') is not None:
            phone_idx = int(query.get('Phone.uom25'))
            self.set_phone(phone_idx)
        msg = self.controller.get_message_from_query(query)
        if msg['body'] == '' or msg['body'] == ' ':
            params = {'message': msg['message']}
        else:
            params = {'title': msg['subject'], 'message': msg['body']}
        if phone_idx is not None:
            params['phone'] = phone_idx
        return self.do_send(params)

    def _assemble_text(self, params):
        params = dict(params)
        title = params.pop('title', None)
        if 'message' in params:
            params['text'] = params['message']
            del params['message']
        if params.get('text') is None or str(params.get('text', '')).strip() == '':
            params['text'] = "NOT_SPECIFIED"
        if title:
            if params['text'] and params['text'] != "NOT_SPECIFIED":
                params['text'] = f"{title}\n{params['text']}"
            else:
                params['text'] = title
        for key in ('device', 'priority', 'format', 'retry', 'expire', 'sound', 'subject', 'phone'):
            params.pop(key, None)
        return params.get('text', "NOT_SPECIFIED")

    def do_send(self, params):
        LOGGER.info('params={}'.format(params))
        if not self.recipients:
            LOGGER.error(f"No recipients configured for {self.iname}")
            self.set_error(ERROR_USER_AUTH)
            return False
        params = dict(params)
        phone_idx = params.pop('phone', None)
        recipients = self._recipients_for_index(phone_idx)
        if not recipients:
            return False
        text = self._assemble_text(params)
        if not self._valid_text(text):
            LOGGER.error('WhatsApp {}: empty message, not sending'.format(self.iname))
            self.set_error(ERROR_MESSAGE_CREATE)
            return False
        if self._is_rate_limited():
            self.enqueue_send(text, recipients, f'{self._provider_label()} rate limit active')
            self._schedule_flush_queue()
            return True
        if self.authorized:
            self.flush_send_queue()
        self.thread = Thread(target=self.post, args=(text, recipients, False, 0))
        self.thread.daemon = True
        LOGGER.debug('Starting Thread')
        self.thread.start()
        return True

    def post(self, text, recipients=None, from_queue=False, retry_count=0):
        if recipients is None:
            recipients = self._recipients_for_index()
        if self._is_rate_limited():
            if not from_queue:
                self.enqueue_send(text, recipients, f'{self._provider_label()} rate limit active')
            else:
                self.enqueue_send(
                    text, recipients, f'{self._provider_label()} still rate limited', retry_count=retry_count
                )
            self._schedule_flush_queue()
            return False
        phones = [r.get('phone', '') for r in recipients]
        LOGGER.info(
            'WhatsApp %s (%s): sending to %s recipient(s): %s',
            self.iname,
            self._provider_label(),
            len(recipients),
            ', '.join(phones),
        )
        all_sent = True
        self.set_error(ERROR_NONE)
        for i, recipient in enumerate(recipients):
            if i > 0 and self.provider != PROVIDER_TEXTMEBOT:
                time.sleep(RECIPIENT_DELAY)
            phone = recipient['phone']
            apikey = recipient['apikey']
            if not phone.startswith('+') or not apikey:
                LOGGER.error(f"Invalid recipient config for {self.iname}: {recipient}")
                all_sent = False
                continue
            sent, res = self._send_sync(phone, apikey, text)
            if not sent:
                LOGGER.error(
                    '%s send failed for %s: %s',
                    self._provider_label(),
                    phone,
                    self._send_error(res),
                )
                all_sent = False
                if self._send_rate_limited(res):
                    remaining = recipients[i:]
                    self.enqueue_send(
                        text,
                        remaining,
                        f'{self._provider_label()} rate limit on {phone}',
                        retry_count=retry_count,
                    )
                    self._schedule_flush_queue()
                    break
                if from_queue and retry_count < FAILED_REQUEUE_MAX:
                    remaining = recipients[i:]
                    self.requeue_failed_send(
                        text,
                        remaining,
                        self._send_error(res),
                        retry_count=retry_count,
                    )
                    break
        if all_sent:
            self._update_send_queue_notice()
            self.set_error(ERROR_NONE)
            if self.send_queue.size() > 0 and not self._is_rate_limited():
                self.flush_send_queue()
        else:
            if self.send_queue.size() == 0:
                self.set_error(ERROR_MESSAGE_SEND)
        return all_sent

    def rest_send(self, params):
        LOGGER.debug('params={}'.format(params))
        params = dict(params)
        if 'message' in params and 'text' not in params:
            params['text'] = params['message']
            del params['message']
        return self.do_send(params)

    id = 'WhatsApp'
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': 'Last Status'},
        {'driver': 'ERR', 'value': 0, 'uom': 25, 'name': 'Error'},
        {'driver': 'GV1', 'value': 0, 'uom': 25, 'name': 'Phone'},
        {'driver': 'GV3', 'value': 0, 'uom': 25, 'name': 'User Message'},
    ]
    commands = {
        'SET_PHONE': cmd_set_phone,
        'SET_MESSAGE': cmd_set_message,
        'SET_SYS_CUSTOM': cmd_set_sys_short,
        'SEND': cmd_send_message,
        'SEND_SYS_CUSTOM': cmd_send_sys_short,
        'SEND_MY_MESSAGE': cmd_send_my_message,
        'SEND_MY_SYS_CUSTOM': cmd_send_my_sys_short,
        'GV10': cmd_send_sys_short_with_params,
    }
