

import requests,json
from urllib.parse import quote_plus

class ntSession():

    def __init__(self,parent,logger,host,port):
        self.parent = parent
        self.logger = logger
        self.host    = host
        self.port    = port
        self.session = requests.Session()

    def post(self,path,payload,dump=True):
        url = "http://{}:{}/{}".format(self.host,self.port,quote_plus(path))
        if dump:
            payload = json.dumps(payload)
        LOGGER.debug("Sending: url={0} payload={1}".format(url,payload))
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
            LOGGER.error("Connection error for %s: %s" % (url, e))
            return False
        LOGGER.debug(' Got: code=%s' % (response.status_code))
        if response.status_code == 200:
            #LOGGER.debug("Got: text=%s" % response.text)
            try:
                d = json.loads(response.text)
            except (Exception) as err:
                LOGGER.error('Failed to convert to json {0}: {1}'.format(response.text,err), exc_info=True)
                return False
            return d
        elif response.status_code == 400:
            LOGGER.error("Bad request: %s" % (url) )
        elif response.status_code == 404:
            LOGGER.error("Not Found: %s" % (url) )
        elif response.status_code == 401:
            # Authentication error
            LOGGER.error(
                "Failed to authenticate, please check your username and password")
        else:
            LOGGER.error("Unknown response %s: %s %s" % (response.status_code, url, response.text) )
        return False

