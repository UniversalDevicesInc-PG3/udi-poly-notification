#!/usr/bin/env python
"""
This is a Notification NodeServer for Polyglot v2 written in Python3
by JimBo jimboca3@gmail.com
"""
import polyinterface
import sys
import time
from nodes import Controller
from nodes import Pushover

LOGGER = polyinterface.LOGGER

if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('notification')
        """
        Instantiates the Interface to Polyglot.
        The name doesn't really matter unless you are starting it from the
        command line then you need a line notification=N
        where N is the slot number.
        """
        polyglot.start()
        """
        Starts MQTT and connects to Polyglot.
        """
        control = Controller(polyglot)
        """
        Creates the Controller Node and passes in the Interface
        """
        control.runForever()
        """
        Sits around and does nothing forever, keeping your program running.
        """
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
