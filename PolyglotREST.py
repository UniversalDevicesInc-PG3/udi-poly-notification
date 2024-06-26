#!/usr/bin/env python3

"""
  Simple GET handler with BaseHTTPServer
"""

from http.server import HTTPServer,BaseHTTPRequestHandler
from urllib import parse
from urllib.parse import parse_qsl,quote_plus,urlparse,urlencode

import socket, threading, sys, requests, json, time
import netifaces as ni

class requestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed_path = urlparse(self.path)
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
            message_parts = ["do_GET:Received: {0} {1}. ".format(parsed_path.path,self.query)]
        # Send back our response
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

    def do_POST(self):
        self.parent.logger.info("do_POST: enter")
        parsed_path = urlparse(self.path)
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
            message_parts = ["do_POST:Received: {0} {1}. ".format(parsed_path.path,self.query)]
        content_len = int(self.headers.get('Content-Length'))
        content_type = self.headers.get('Content-Type')
        post_body = self.rfile.read(content_len)
        if post_body is not None:
            post_body = post_body.decode()
        if content_type == 'application/json':
            try:
                pdata = json.loads(post_body)
            except Exception as err:
                self.parent.logger.error('wtHandler: failed to parse body as json: {} Error={}'.format(post_body,err))
                pdata = { 'body': post_body }
        else:
            pdata = { 'body': post_body }
        # Send back our reponese
        # TODO: only send if we understand it.
        hrt = self.parent.get_handler(parsed_path.path,self.query,pdata)
        message_parts.append("Code: {0}".format(int(hrt['code'])))
        message_parts.append(hrt['message'])
        self.send_response(int(hrt['code']))
        self.send_header('Content-Type',
                         'text/plain; charset=utf-8')
        message_parts.append('')
        message = '\r\n'.join(message_parts)
        message += '\r\n'
        self.send_header("Content-Length", str(len(message)))
        self.end_headers()
        self.wfile.write(message.encode('utf-8'))

    def log_message(self, fmt, *args):
        # Stop log messages going to stdout
        if args[1] == "200":
            self.parent.logger.debug(fmt % args)
        else:
            # TODO: Pass a receive error to the parent.
            self.parent.logger.error(fmt % args)
            self.parent.logger.error(f'code="{args[1]}"')
            self.parent.get_handler("receive_error",fmt,args)

class polyglotREST():

   # port=9 means let the kernel give us a port
    def __init__(self, parent, logger, port=0):
        self.parent  = parent
        self.logger  = logger
        self.ip      = None
        self.port    = int(port)
        self.server = False

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
        done = False
        cnt = 60
        while not done and cnt > 0:
            try:
                self.server = HTTPServer(self.address, requestHandler)
                done = True
            except OSError as err:
                cnt -= 1
                if cnt > 0:
                    self.logger.error(f'polyglotREST:start: failed for port {self.port}: {type(err)} {err}, will try again in 5 seconds and give up in {cnt*5} seconds')
                    time.sleep(5)
            except Exception as err:
                    self.logger.error(f'polyglotREST:start: failed for port {self.port}: {type(err)} {err}, will not retry for this error')
                    cnt = 0
        if done is False:
            self.logger.error(f'Failed to start rest server.')
            self.server = False
            return False
        self.url     = 'http://{0}:{1}'.format(self.server.server_address[0],self.server.server_address[1])
        self.listen_port = self.server.server_address[1]
        self.logger.info("polyglotREST: Running on: {0}".format(self.url))
        # Just keep serving until we are killed
        self.thread  = threading.Thread(target=self.server.serve_forever)
        # Need this so the thread will die when the main process dies
        self.thread.daemon = True
        self.thread.start()
        return True

    def get_handler(self,path,query,data=None):
        return self.parent.get_handler(path,query,data)

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

    def stop(self):
        self.logger.info("polyglotREST:stop: Shutdoing down and closing")
        if self.server is not False:
            self.server.shutdown()
            self.server.server_close()

class polyglotRESTServer():

    def __init__(self,port,logger,client_id=None,client_secret=None,ghandler=None,oauth2_code=False):
        self.l_name = "polyglotRESTServer"
        self.logger = logger
        self.port   = int(port)
        self.rest   = None
        self.client_id = client_id
        self.client_secret = client_secret
        self.ghandler=ghandler
        self.oauth2_code = oauth2_code
        self.access_token = False
        self.token_type   = None

    def start(self):
        self.rest = polyglotREST(self,self.logger,self.port)
        self.st = self.rest.start()
        if self.st is False:
            return False
        self.ip          = self.rest.ip
        self.listen_url  = self.rest.url
        self.listen_port = self.rest.listen_port
        self.url = self.rest.url
        # Start the session for talking to wirelesstag server
        self.session = polyglotSession(self,self.logger,self)
        if self.oauth2_code != False:
            self.pull_access_token()
        self._slock = False
        return True

    def stop(self):
        self.rest.stop()

    def get_handler(self,command,params,post_data):
        """
        This is passed the incoming http get's to processes
        """
        self.logger.debug('command={}'.format(command))
        # This is from the oauth2 redirect with our code.
        if command == "/code":
            code = 200
            message = "\nGot code {}, asking for access token\n".format(params['code'])
            self.oauth2_code = params['code']
            self.logger.info('Got code: {}'.format(self.oauth2_code))
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
                code = 405
                message = "Unknown command, no ghandler specified '{}'".format(command)
            else:
                try:
                    ret = self.ghandler(command,params,post_data)
                    if ret:
                        code = 200
                        message = 'Command {0} success'.format(command)
                    else:
                        code = 406
                        message = 'Command {0} failed'.format(command)
                except:
                    message = "ghandler failed, see log"
                    self.logger.error('failed',exc_info=True)
                    code = 500
        if code == 200:
            self.logger.debug('code={0} message={1}'.format(code,message))
        else:
            self.logger.error('code={0} message={1}'.format(code,message))
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
            self.logger.error('Failed')
            self.access_token = aret
            return aret
        self.access_token = aret['access_token']
        self.token_type   = aret['token_type']
        self.logger.debug("token_type={} access_token={}".format(self.token_type,self.access_token))

    def get_access_token(self):
        return self.access_token

    def get_token_type(self):
        return self.token_type

class polyglotSession():

    def __init__(self,parent,url,logger):
        self.parent = parent
        self.url    = url #
        self.logger = logger
        # Our reusable session
        self.session = requests.Session()
        # Our headers never change...?
        self.session.headers.update(
            {
                "Content-Type": "application/json"
            }
        )

    # TODO: auth and api_key should be passed as a header list
    def get(self,path,params={},auth=None,api_key=None):
        url = "{}/{}".format(self.url,path)
        self.logger.debug("Sending: url={0} payload={1}".format(url,params))
        # No speical headers?
        headers = {
            "Content-Type": "application/json"
        }
        if auth is not None:
            headers['Authorization'] = auth
        if api_key is not None:
            headers['x-api-key'] = api_key
        self.logger.debug( "headers={}".format(headers))
        self.session.headers.update(headers)
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=(61,10)
            )
            self.logger.debug( "url={}".format(response.url))
        # This is supposed to catch all request excpetions.
        except requests.exceptions.RequestException as e:
            self.logger.error("Connection error for %s: %s" % (url, e))
            return False
        return(self.response(response,'get'))

    def post(self,path,payload,api_key=None,content="json"):
        self.logger.debug(f'start: path={path} payload={payload} api_key={api_key} content={content}')
        # No speical headers?
        headers = {
        }
        if api_key is not None:
            headers['x-api-key'] = api_key
        url = "{}/{}".format(self.url,path)
        if content == "json":
            headers['Content-Type'] = 'application/json'
            try:
                payload_out = json.dumps(payload)
            except Exception as e:
                self.logger.error('Error converting to json: {}'.format(payload))
                return False
        elif content == "urlencode":
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            payload_out = urlencode(payload)
        else:
            LOGGER.error("Unknown content={content}, must be json or urlencode")
            return { 'status': False, 'status_code': None, 'code': None }
        self.logger.debug("Sending: url={0} payload={1}".format(url,payload_out))
        self.logger.debug( "headers={}".format(headers))
        self.session.headers.update(headers)
        try:
            response = self.session.post(
                url,
                data=payload_out,
                timeout=(10,60)
            )
        # This is supposed to catch all request excpetions.
        except requests.exceptions.RequestException as e:
            self.logger.error("Connection error for %s: %s" % (url, e))
            return { 'status': False, 'status_code': None, 'code': None }
        return(self.response(response,'post'))

    def response(self,response,name):
        fname = 'reponse:'+name
        self.logger.debug(' Got: code=%s' % (response.status_code))
        self.logger.debug('      text=%s' % (response.text))
        json_data = False
        st = False
        if response.status_code == 200:
            self.logger.debug(' All good!')
            st = True
        elif response.status_code == 400:
            self.logger.error("Bad request: %s: text: %s" % (response.url,response.text) )
        elif response.status_code == 404:
            self.logger.error("Not Found: %s: text: %s" % (response.url,response.text) )
        elif response.status_code == 401:
            # Authentication error
            self.logger.error("Unauthorized: %s: text: %s" % (response.url,response.text) )
        elif response.status_code == 403:
            # Forbidden, ISY Portal returns this for bad api key
            self.logger.error("Forbidden: %s: text: %s" % (response.url,response.text) )
        elif response.status_code == 500:
            self.logger.error("Server Error: %s %s: text: %s" % (response.status_code,response.url,response.text) )
        elif response.status_code == 522:
            self.logger.error("Timeout Error: %s %s: text: %s" % (response.status_code,response.url,response.text) )
        else:
            self.logger.error("Unknown response %s: %s %s" % (response.status_code, response.url, response.text) )
            self.logger.error("Check system status: https://status.ecobee.com/")
        try:
            json_data = json.loads(response.text)
        except (Exception) as err:
            # Only complain about this error if we didn't have an error above
            if st:
                self.logger.error('Failed to convert to json {0}: {1}'.format(response.text,err), exc_info=True)
            json_data = False
        return { 'status': st, 'code': response.status_code, 'data': json_data }

    def l_info(self, name, string):
        self.logger.info("%s:%s: %s" %  (self.parent.name,name,string))

    def l_error(self, name, string, exc_info=False):
        self.logger.error("%s:%s: %s" % (self.parent.name,name,string), exc_info=exc_info)

    def l_warning(self, name, string):
        self.logger.warning("%s:%s: %s" % (self.parent.name,name,string))

    def l_debug(self, name, string):
        self.logger.debug("%s:%s: %s" % (self.parent.name,name,string))



def my_ghandler(command,params,data=None):
    print("my_ghandler: command={} params={} data={}".format(command,params,data))
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
    obj = polyglotRESTServer('8082',logger,client_id,client_secret,ghandler=my_ghandler)
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
