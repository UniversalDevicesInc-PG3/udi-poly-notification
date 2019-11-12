[![Build Status](https://travis-ci.org/jimboca/udi-poly-notification.svg?branch=master)](https://travis-ci.org/jimboca/udi-poly-notification)

# udi-poly-notification

This is the Notification Poly for the [Universal Devices ISY994i](https://www.universal-devices.com/residential/ISY) [Polyglot Interface](http://www.universal-devices.com/developers/polyglot/docs/) with  [Polyglot V2](https://github.com/Einstein42/udi-polyglotv2) to support sending many types of notifications, first on the list is Pushover.

(c) JimBoCA aka Jim Searle
MIT license.

## Support

This is discussed on the forum post [Polglot V2 Notification Nodeserver](https://forum.universal-devices.com/topic/TBD/).  You can ask questions there.  If you have a bug or enhancement request filing an issue on the [Github Issue Page](https://github.com/jimboca/udi-poly-notification/issues) is preferred since it can easily get lost on the forum.

## Configuration

The [Configuration Page](https://github.com/jimboca/udi-poly-notification/blob/master/POLYGLOT_CONFIG.md) is the same as the information included on the Polyglot Notification Nodeserver Configuration Page.

## How it works

Will add more information here when finalized someday...

## Nodes

There are 3 types of nodes
- Controller
  - This is the main node which contains the Status of the nodeserver.
  - Status
    - Nodeserver Online
      - If the nodeserver crashes or exit this should change to False.  But for other issues, like Polyglot or Machine crash it will not change, so you should use Heartbeat as documented below if you really want to know when it not running.
  - Control
      - Debug level
        - This sets the amount of info that shows up in the log file, to minimize file size you should set this to warning, but if you are debugging issues or want to watch what is going on then change to info or debug.
      - Message
        -  This will contain the list of Messages you add in the configuration described on the [Configuration Page](https://github.com/jimboca/udi-poly-notification/blob/master/POLYGLOT_CONFIG.md).  The chosen message will be sent when you call Send on a Service or node.
- Service Nodes
  - For services such as Pushover, can be multiple for each Service if defined in the Configuration Page
    - Pushover Service Node
      - These nodes will be named "Pushover" plus the "Name" you used in the Pushover keys configuration.  These are the nodes you can add to a program to configure and send the message defined in the Controller node.
      - Status
        - Last Status
          - This will be True if the last message was sent successfully
        - Error
          - This will show the Last error when it happens.
            - None
            - Illegal Value
            - App Auth
            - User Auth
            - Create Message
            - Send Message
      - Control
        - Device
          - This is the Pushover Device as configured on the pushover site.
        - Priority
          - This is the Pushover Priority
            - Lowest
            - Low
            - Normal
            - High
            - Emergency
  - Message Nodes
    - Message nodes defined by user on the Configuration Page
    - They are meant to be added to a Scene and send messages when DON or DOFF is received.s
    - They are going to be complicated, not sure how to do it properly yet...

## Heartbeat monitoring

TODO: And program info here


## Installation

1. Backup Your ISY in case of problems!
   * Really, do the backup, please
2. Go to the Polyglot Store in the UI and install Notification.
3. Add Notification NodeServer in Polyglot
4. Go to the Configuration page and read those instructions.

## Requirements
1. [Polyglot V2](https://github.com/UniversalDevicesInc/polyglot-v2) >= 2.2.6
1. When using a RaspberryPi it should be run on Raspian Stretch
  To check your version: ```cat /etc/os-release```
  and the first line should look like ```PRETTY_NAME="Raspbian GNU/Linux 9 (stretch)"```
  It is possible to upgrade from Jessie to Stretch, but I would recommend just
  re-imaging the SD card.  Some helpful links:
    * https://www.raspberrypi.org/blog/raspbian-stretch/
    * https://linuxconfig.org/raspbian-gnu-linux-upgrade-from-jessie-to-raspbian-stretch-9
1. This has only been tested with ISY 5.0.16 so it is not confirmed to work with any prior version.

## Issues Paige

See [Github Issues](https://github.com/jimboca/udi-poly-notification/issues)

## Upgrading

### From the store

1. Open the Polyglot web page, go to nodeserver store and click "Update" for "Notification".
    * You can always answer "No" when asked to install profile.  The nodeserver will handle this for you.
2. Go to the Notification Control Page, and click restart

### The manual way

1. ```cd ~/.polyglot/nodeservers/Notification```
2. ```git pull```
3. ```./install.sh```
4. Open the polyglot web page, and restart the node server
5. If you had the Admin Console open, then close and re-open.


## Release Notes

- 0.0.1 02/17/2019
  - Initial release for review
