#!/usr/bin/env python3

"""
  Simple GET handler with BaseHTTPServer
"""

from http.server import HTTPServer,BaseHTTPRequestHandler
from urllib import parse
from urllib.parse import parse_qsl
import socket, threading, sys, requests, json, time
import netifaces as ni

class requestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed_path = parse.urlparse(self.path)
        self.query = dict(parse_qsl(parsed_path.query))
        if 'debug' in self.query:
            message_parts = [
                'CLIENT VALUES:',
                'client_address={} ({})'.format(
                    self.client_address,
                    self.address_string()),
                'command={}'.format(self.command),
                'path={}'.format(self.path),
                'real path={}'.format(parsed_path.path),
                'query={}'.format(parsed_path.query),
                'query_dict={}'.format(self.query),
                'request_version={}'.format(self.request_version),
                '',
                'SERVER VALUES:',
                'server_version={}'.format(self.server_version),
                'sys_version={}'.format(self.sys_version),
                'protocol_version={}'.format(self.protocol_version),
                '',
                'HEADERS RECEIVED:',
            ]
            for name, value in sorted(self.headers.items()):
                message_parts.append(
                    '{}={}'.format(name, value.rstrip())
                )
        else:
            message_parts = ["Received: {0} {1}. ".format(parsed_path.path,self.query)]
        # Send back our repones
        # TODO: only send if we understand it.
        hrt = self.parent.get_handler(parsed_path.path,self.query)
        message_parts.append("Code: {0}".format(int(hrt['code'])))
        message_parts.append(hrt['message'])
        self.send_response(int(hrt['code']))
        self.send_header('Content-Type',
                         'text/plain; charset=utf-8')
        self.end_headers()
        message_parts.append('')
        message = '\r\n'.join(message_parts)
        message += '\r\n'
        self.wfile.write(message.encode('utf-8'))

    def log_message(self, fmt, *args):
        # Stop log messages going to stdout
        self.parent.logger.info('wtHandler:log_message' + fmt % args)

class polyglotREST():

   # port=9 means let the kernel give us a port
    def __init__(self, parent, logger, port=0):
        self.parent  = parent
        self.logger  = logger
        self.ip      = None
        self.port    = port

    def start(self):
        # TODO: This will fail if we don't have internet access...
        self.ip    = self.get_network_ip_rhost('8.8.8.8')
        if self.ip is False:
            self.logger.error("polyglotREST: Can not start on IP={0}".format(self.ip))
            return False
        self.logger.info("polyglotREST: Running on IP={0}".format(self.ip))
        self.address = (self.ip, self.port)
        self.logger.debug("polyglotREST: address={0}".format(self.address))
        # Get a handler and set parent to myself, so we can process the requests.
        eh = requestHandler
        eh.parent = self
        self.server = HTTPServer(self.address, requestHandler)
        self.url     = 'http://{0}:{1}'.format(self.server.server_address[0],self.server.server_address[1])
        self.listen_port = self.server.server_address[1]
        self.logger.info("polyglotREST: Running on: {0}".format(self.url))
        # Just keep serving until we are killed
        self.thread  = threading.Thread(target=self.server.serve_forever)
        # Need this so the thread will die when the main process dies
        self.thread.daemon = True
        self.thread.start()
        return True

    def get_handler(self,path,query):
        return self.parent.get_handler(path,query)

    def get_network_ip_rhost(self,rhost):
        self.logger.info("polyglotREST:get_network_ip: {0}".format(rhost))
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((rhost, 80))
            rt = s.getsockname()[0]
        except Exception as err:
            self.logger.error('polyglotREST:get_network_id: failed: {0}'.format(err), exc_info=True)
            rt = False
        finally:
            s.close()
        self.logger.info("polyglotREST:get_network_ip: Returning {0}".format(rt))
        return rt

    # This didn't work on a mac, needs a try/except, which I didn't like...
    # And assumes address zero...
    def get_network_ip(self):
        try:
            ifaddr = ni.ifaddresses(iface)[ni.AF_INET][0]
            if 'addr' in ifaddr and ifaddr['addr'] != '127.0.0.1':
                self.logger.info("polyglotREST:get_network_ip: Got {0}".format(rt))
                return ifaddr['addr']
        except:
            pass
        self.logger.info("polyglotREST:get_network_ip: Failed")
        return False

class polyglotRESTServer():

    def __init__(self,logger,client_id,client_secret,ghandler=None,oauth2_code=False):
        self.l_name = "polyglotRESTServer"
        self.logger = logger
        self.client_id = client_id
        self.client_secret = client_secret
        self.ghandler=ghandler
        self.oauth2_code = oauth2_code
        self.access_token = False
        self.token_type   = None

    def start(self):
        self.rest = polyglotREST(self,self.logger)
        self.st = self.rest.start()
        if self.st is False:
            self.l_error('polyglotRESTServer:start','REST server not started {}'.format(self.st))
            return False
        self.listen_url  = self.rest.url
        self.listen_port = self.rest.listen_port
        self.url = self.rest.url
        # Start the session for talking to wirelesstag server
        self.session = polyglotSession(self,self.logger,self)
        if self.oauth2_code != False:
            self.pull_access_token()
        self._slock = False
        return True

    def get_handler(self,command,params):
        """
        This is passed the incoming http get's to processes
        """
        self.l_debug('get_handler','command={}'.format(command))
        # This is from the oauth2 redirect with our code.
        if command == "/code":
            code = 200
            message = "\nGot code {}, asking for access token\n".format(params['code'])
            self.oauth2_code = params['code']
            self.l_info('get_handler','Got code: {}'.format(self.oauth2_code))
            tr = self.pull_access_token()
            if tr == False:
                code = 500
                message += "ERROR: Unable to get access token from code, see log"
            else:
                message += "SUCCESS, received our token, will save in Polyglot database for the future"
            if self.ghandler is not None:
                self.ghandler(command,{'oauth2_code': self.oauth2_code})
        elif command == "/favicon.ico":
            # Ignore this, where does it come from?
            code = 200
            message = "Ignored {0}".format(command)
        else:
            if self.ghandler is None:
                code = 500
                message = "Unknown command, no ghandler specified '{}'".format(command)
            else:
                ret = self.ghandler(command,params)
                if ret:
                    code = 200
                    message = 'Command {0} success'.format(command)
                else:
                    code = 500
                    message = 'Command {0} failed'.format(command)
        if code == 200:
            self.l_debug('get_handler','code={0} message={1}'.format(code,message))
        else:
            self.l_error('get_handler','code={0} message={1}'.format(code,message))
        return  { 'code': code, 'message': message }

    def pull_access_token(self,code=None):
        if code is not None:
            self.oauth2_code = code
        aret = self.session.post('oauth2/access_token.aspx',
                              {
                                  'client_id': self.client_id,
                                  'client_secret': self.client_secret,
                                  'code': self.oauth2_code
                              }, use_token=False)
        # This gives us:
        # {'token_type': 'Bearer', 'access_token': '...', 'expires_in': 9999999}
        if aret == False:
            self.l_error('pull_access_token','Failed')
            self.access_token = aret
            return aret
        self.access_token = aret['access_token']
        self.token_type   = aret['token_type']
        self.l_debug('start',"token_type={} access_token={}".format(self.token_type,self.access_token))

    def get_access_token(self):
        return self.access_token

    def get_token_type(self):
        return self.token_type

    def l_info(self, name, string):
        self.logger.info("%s: %s" %  (name,string))

    def l_error(self, name, string, exc_info=False):
        self.logger.error("%s: %s" % (name,string), exc_info=exc_info)

    def l_warning(self, name, string):
        self.logger.warning("%s: %s" % (name,string))

    def l_debug(self, name, string):
        self.logger.debug("%s: %s" % (name,string))

class polyglotSession():

    def __init__(self,parent,logger,polyglotRESTServer,tmgr_mac=None):
        self.parent = parent
        self.logger = logger
        self.polyglotRESTServer = polyglotRESTServer
        self.tmgr_mac = tmgr_mac
        self.tmgr_mac_st = False
        self.session = requests.Session()
        self.select_tag_manager()


    def select_tag_manager(self,force=False):
        if self.tmgr_mac is None:
            return True
        if not self.tmgr_mac_st or force:
            mgd = self.api_post_dn('ethAccount.asmx/SelectTagManager',{'mac':self.tmgr_mac})
            self.tmgr_mac_st = mgd['st']
            self.session.headers.update({'X-Set-Mac': self.tmgr_mac})
        return self.tmgr_mac_st

    def post(self,path,payload,use_token=True):
        url = "https://www.mytaglist.com/{}".format(path)
        self.l_debug('post',"Sending: url={0} payload={1}".format(url,payload))
        if use_token:
            access_token = self.polyglotRESTServer.get_access_token()
            if access_token is False:
                self.l_error('post',"No authorization for url={0} payload={1}".format(url,payload))
                return False
            token_type   = self.polyglotRESTServer.get_token_type()
            self.session.headers.update(
                {
                    "Authorization": "{0} {1}".format(token_type,access_token),
                    "Content-Type": "application/json"
                }
            )
        else:
            self.session.headers.update({})
        try:
            response = self.session.post(
                url,
                data=payload,
                timeout=60
            )
        # This is supposed to catch all request excpetions.
        except requests.exceptions.RequestException as e:
            self.l_error('post',"Connection error for %s: %s" % (url, e))
            return False
        self.l_debug('post',' Got: code=%s' % (response.status_code))
        if response.status_code == 200:
            #self.l_debug('http_post',"Got: text=%s" % response.text)
            try:
                d = json.loads(response.text)
            except (Exception) as err:
                self.l_error('http_post','Failed to convert to json {0}: {1}'.format(response.text,err), exc_info=True)
                return False
            return d
        elif response.status_code == 400:
            self.l_error('post',"Bad request: %s" % (url) )
        elif response.status_code == 404:
            self.l_error('post',"Not Found: %s" % (url) )
        elif response.status_code == 401:
            # Authentication error
            self.l_error('post',
                "Failed to authenticate, please check your username and password")
        else:
            self.l_error('post',"Unknown response %s: %s %s" % (response.status_code, url, response.text) )
        return False

    def api_post_d(self,path,payload,dump=True):
        """
        Call the api path with payload expecting data in d entry
        Return status and result
        """
        # If we failed to set tag manager, try again
        if not self.select_tag_manager(): return { 'st': False }
        return self.api_post_dn(path,payload,dump)

    def api_post_dn(self,path,payload,dump=True):
        """
        Just do the post, don't select tag manager
        """
        if dump:
            payload = json.dumps(payload)
        aret = self.post(path,payload)
        self.l_debug('post','path={0} got={1}'.format(path,aret))
        if aret == False or not 'd' in aret:
            mret = { 'st': False }
        else:
            mret = { 'st': True, 'result': aret['d'] }
        self.l_debug('post','ret={0}'.format(mret))
        return mret

    def l_info(self, name, string):
        self.logger.info("%s:%s: %s" %  (self.parent.l_name,name,string))

    def l_error(self, name, string, exc_info=False):
        self.logger.error("%s:%s: %s" % (self.parent.l_name,name,string), exc_info=exc_info)

    def l_warning(self, name, string):
        self.logger.warning("%s:%s: %s" % (self.parent.l_name,name,string))

    def l_debug(self, name, string):
        self.logger.debug("%s:%s: %s" % (self.parent.l_name,name,string))



def my_ghandler(command,params):
    return True

if __name__ == '__main__':
    import logging, time
    logging.basicConfig(
        level=10,
        format='%(levelname)s:\t%(name)s\t%(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    client_id     = "3b08b242-f0f8-41c0-ba29-6b0478cd0b77"
    client_secret = "0b947853-1676-4a63-a384-72769c88f3b1"
    code          = "d967868a-144e-49ed-921f-c27b65dda06a"
    obj = polyglotRESTServer(logger,client_id,client_secret,ghandler=my_ghandler)
    try:
        obj.start()
    except KeyboardInterrupt:
        logger.info('Exiting from keyboard interupt')
        sys.exit()
    # Manually get the access token
    #obj.pull_access_token(code)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as err:
        logger.error('polyglotREST: failed: {0}'.format(err), exc_info=True)
    sys.exit()
