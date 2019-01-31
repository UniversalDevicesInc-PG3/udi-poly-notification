

import requests,json

class ntSession():

    def __init__(self,parent,logger,host,port):
        self.parent = parent
        self.logger = logger
        self.host    = host
        self.port    = port
        self.session = requests.Session()

    def post(self,path,payload,dump=True):
        url = "http://{}:{}/{}".format(self.host,self.port,path)
        if dump:
            payload = json.dumps(payload)
        self.l_debug('post',"Sending: url={0} payload={1}".format(url,payload))
        # No speical headers?
        self.session.headers.update(
                        {
                            "Content-Type": "application/json"
                        }
        )
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

    def l_info(self, name, string):
        self.logger.info("%s:%s: %s" %  (self.parent.l_name,name,string))

    def l_error(self, name, string, exc_info=False):
        self.logger.error("%s:%s: %s" % (self.parent.l_name,name,string), exc_info=exc_info)

    def l_warning(self, name, string):
        self.logger.warning("%s:%s: %s" % (self.parent.l_name,name,string))

    def l_debug(self, name, string):
        self.logger.debug("%s:%s: %s" % (self.parent.l_name,name,string))
