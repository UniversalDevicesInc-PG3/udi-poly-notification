"""
  Notification Telegram Node
"""

from udi_interface import Node,LOGGER
from threading import Thread,Event
import time
import logging
import collections
from node_funcs import make_file_dir,is_int,get_default_sound_index

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
            self.users         = self.info['users']
        else:
            self.users         = list()
        self.user_id       = None
        LOGGER.debug('{} {}'.format(address,name))
        controller.poly.subscribe(controller.poly.START,                  self.handler_start, address)
        super(TelegramUB, self).__init__(controller.poly, primary, address, name)

    def handler_start(self):
        """
        """
        LOGGER.info('')
        vstat = self.validate()
        if vstat['status'] is False:
            self.authorized = False
        else:
            self.authorized = True if vstat['status'] == 1 else False
        LOGGER.info("Authorized={}".format(self.authorized))
        if self.authorized:
            self.set_error(ERROR_NONE)
            self._init_st = True
        else:
            self.set_error(ERROR_APP_AUTH)
            self._init_st = False

    def validate(self):
        LOGGER.debug('Authorizing Telegram app {}'.format(self.http_api_key))
        res = self.session.get(f"bot{self.http_api_key}/getUpdates")
        LOGGER.debug('got: {}'.format(res))
        self.user_id = None
        if 'status' in res and res['status']:
            # Send a message to the user that we started up
            if len(self.users) == 0:
                self.controller.Notices['telegramub'] = f"Please configure {self.iname} user"
            else:
                self.user_id = self.users[0]
                # TODO: Need to wait for confirmation that send actually completed, or do this one non-threaded?
                send_st = self.do_send({ 'text': f'{self.name} has started up'})
                self.controller.Notices.delete('telegramub')
        else:
            self.controller.Notices['telegramub'] = "Failed to authorize Telegram User Bot, see ERROR in log"

        return res



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
        str = '<li>curl -d \'{{"node":"{0}", "message":"The Message", "subject":"The Subject" -H "Content-Type: application/json"}}\' -X POST {1}/send'.format(self.address,self.controller.rest.listen_url)
        return str

    def config_info_nr(self):
        info = [
            '<li>Example Network Resource for Telegram User Bot<ul><li>http<li>POST<li>Host:{0}<li>Port:{1}<li>Path: /send?node={2}<li>Encode URL: not checked<li>Timeout: 5000<li>Mode: Raw Text</ul>'.format(self.controller.rest.ip,self.controller.rest.listen_port,self.address),
            '</ul>',
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

    def do_send(self,params):
        LOGGER.info('params={}'.format(params))
        # These may all eventually be passed in or pulled from drivers.
        if 'message' in params:
            params['text'] = params['message']
            del params['message']
        elif not 'text' in params:
            params['text'] = "NOT_SPECIFIED"
        if self.user_id is None:
            LOGGER.error(f"user {self.user_id} not defined for {self.iname}")
            self.set_error(ERROR_USER_AUTH)
            return False
        params['chat_id'] = self.user_id
        # Telegram doesn't support any of these...
        for key in ('device','priority','format','retry','expire','sound'):
            if key in params:
                del params[key]
        #
        # Send the message in a thread with retries
        #
        # Just keep serving until we are killed
        self.thread = Thread(target=self.post,args=(params,))
        self.thread.daemon = True
        LOGGER.debug('Starting Thread')
        st = self.thread.start()
        LOGGER.debug('Thread start st={}'.format(st))
        # Always have to return true case we don't know..
        return True

    def post(self,params):
        sent = False
        retry = True
        cnt  = 0
        # Clear error if there was one
        self.set_error(ERROR_NONE)
        LOGGER.debug('params={}'.format(params))
        while (not sent and retry and (RETRY_MAX < 0 or cnt < RETRY_MAX)):
            cnt += 1
            LOGGER.debug('try #{}'.format(cnt))
            res = self.session.post(f"bot{self.http_api_key}/sendmessage",params)
            LOGGER.debug('res={}'.format(res))
            if 'status' in res and res['status'] is True:
                sent = True
                self.set_error(ERROR_NONE)
            else:
                if 'data' in res:
                    if 'errors' in res['data']:
                        LOGGER.error('From Telegram: {}'.format(res['data']['errors']))
                # No status code or not 4xx code is
                if 'code' in res and (res['code'] is not None and (res['code'] >= 400 or res['code'] < 500)):
                    LOGGER.warning('Previous error can not be fixed, will not retry')
                    retry = False
                else:
                    LOGGER.warning('Previous error is retryable...')
            if (not sent):
                self.set_error(ERROR_MESSAGE_SEND)
                if (retry and (RETRY_MAX > 0 and cnt == RETRY_MAX)):
                    LOGGER.error('Giving up after {} tries'.format(cnt))
                    retry = False
            if (not sent and retry):
                time.sleep(RETRY_WAIT)
        #LOGGER.info('is_sent={} id={} sent_at={}'.format(message.is_sent, message.id, str(message.sent_at)))
        return sent

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
        {'driver': 'ST',  'value': 0, 'uom': 2},
        {'driver': 'ERR', 'value': 0, 'uom': 25},
    ]
    commands = {
                #'DON': setOn, 'DOF': setOff
                'SEND_MESSAGE': cmd_send_message,
                'SEND_SYS_SHORT': cmd_send_sys_short,
                }
