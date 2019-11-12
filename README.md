[![Build Status](https://travis-ci.org/jimboca/udi-poly-notification.svg?branch=master)](https://travis-ci.org/jimboca/udi-poly-notification)

# udi-poly-notification

This is the Notification Poly for the [Universal Devices ISY994i](https://www.universal-devices.com/residential/ISY) [Polyglot Interface](http://www.universal-devices.com/developers/polyglot/docs/) with  [Polyglot V2](https://github.com/Einstein42/udi-polyglotv2) to support sending many types of notifications, first on the list is Pushover.

(c) JimBoCA aka Jim Searle
MIT license.

## Support

This is discussed on the forum post [Polglot V2 Notification Nodeserver](https://forum.universal-devices.com/topic/TBD/)  You can ask questions on that post, or file an issue here on github if you like https://github.com/jimboca/udi-poly-notification/issues

## Configuration

The [Configuration Document](https://github.com/jimboca/udi-poly-notification/blob/master/POLYGLOT_CONFIG.md) is the same as the information included on the Polyglot Notification Nodeserver Configuration Page.

## How it works

Will add more information here when finalized

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



## TODO

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

If you are going to purchase a Tag Manager or Tags, please use [My Referral Link](https://goo.gl/XVcSKZ)

If you have issues, please create an issue https://github.com/jimboca/udi-wirelesstag-poly/issues  If you have questions please use the forum.

- 0.0.1 02/17/2019
  - Initial release for review
