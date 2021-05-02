[![Build Status](https://travis-ci.org/jimboca/udi-poly-notification.svg?branch=master)](https://travis-ci.org/jimboca/udi-poly-notification)

# udi-poly-notification

This is the Notification Poly for the [Universal Devices ISY994i](https://www.universal-devices.com/residential/ISY) [Polyglot Interface](http://www.universal-devices.com/developers/polyglot/docs/) with  [Polyglot V2](https://github.com/Einstein42/udi-polyglotv2) to support sending many types of notifications, first on the list is Pushover.

(c) JimBoCA aka Jim Searle
MIT license.

## Support

This is discussed on the forum post [Polglot Notification Nodeserver](https://forum.universal-devices.com/forum/166-polyglot-notification-service-node-server/).  You can ask questions there.  If you have a bug or enhancement request filing an issue on the [Github Issue Page](https://github.com/jimboca/udi-poly-notification/issues) is preferred since it can easily get lost on the forum.

## Configuration

All information is on the [Configuration Page](https://github.com/jimboca/udi-poly-notification/blob/master/POLYGLOT_CONFIG.md) which is the same as information included on the Polyglot Notification Nodeserver Configuration Page.

## How it works

The nodeserver allows you to
1. MESSAGES: Create short messages under Config and send them to a Notification Service easily thru an ISY program
2. NOTIFY NODES: Create a node that can be added to a scene to send canned messages when the scene is controlled
3. LARGE MESSAGES WITH SYSTEM VARIABLES: Send ISY Network resources to the nodeserver REST interface where recipients are controlled by a program which can include a large message body with system variables!

## Nodes

There are 3 types of nodes
### Notification Controller
This is the main node which contains the Status of the nodeserver and provides access to your short messages that you setup in Config.
  - Status
    - Nodeserver Online
      - If the nodeserver crashes or exit this should change to False.  But for other issues, like Polyglot or Machine crash it will not change, so you should use Heartbeat as documented below if you really want to know when it not running.
  - Control
      - Debug level
        - This sets the amount of info that shows up in the log file, to minimize file size you should set this to warning, but if you are debugging issues or want to watch what is going on then change to info or debug.
  - Message
        -  This will contain the list of the short messages that you add in the configuration described on the [Configuration Page](https://github.com/jimboca/udi-poly-notification/blob/master/POLYGLOT_CONFIG.md).  The message chosen here or in a program, will be sent when you call Send on a Service or node.
### Service Nodes
These are the Services such as Pushover that are called when a Send is issued.  There can be multiple Services as defined in the Configuration Page
  - These are the nodes you can add to a program to configure and send any of your short message previously defined in Config which show in the Notification Controller node above.
    - Pushover Service Node
      - These nodes will be named "Service Pushover" plus the "Name" you used in the Pushover keys configuration.
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
          - This is the <a href="https://pushover.net/api#priority" target="_ blank">Pushover Priority</a>
            - Lowest
            - Low
            - Normal
            - High
            - Emergency
        - Retry
          - This is only for the Emergency <a href="https://pushover.net/api#priority">Priority</a>. It specifies how often (in seconds) the Pushover servers will send the same notification to the user.
        - Expires
          - This is only for the Emergency <a href="https://pushover.net/api#priority">Priority</a>. It specifies how many seconds your notification will continue to be retried for (every retry seconds)
### Message Retry
  When the nodeserver sends a message and there is an error it will set the Service Node's Last Status and Error, then will continue to retry sending the message every 5 seconds forever, or until the nodeserver is restarted.  See <a href="https://github.com/jimboca/udi-poly-notification/issues/19" target="_ blank">Add more retry and timeouts to message posting</a> and comment there if you have suggestions.
  If you are very concernted about catching the errors, you can create a program like:
```
If
        'Polyglot / Notification Controller / Service Pushover homeisy' Error is not None
 
Then
        Send Notification to 'Text-Jim' content 'Polyglot Notification Status'
        Send Notification to 'Email-Jim' content 'Polyglot Notification Status'
```
  and in that Custom Notification use something like
```
Subject: ${sys.program.#.name}
Body: 
Notification: ST=${sys.node.n005_controller.ST} HB=${var.2.232} 
  ${sys.node.n005_po_homeisy.name} ERR=${sys.node.n005_po_homeisy.ERR}
```
### Notify Nodes
Notify nodes are defined by user on the Configuration Page and are meant to be added to a Scene as a device. They send predefined messages when the device is turned ON or device is turned OFF.
  - This device can be turned on or off in a program as well
  - The only available messages are in the canned message list under the Notify node in your MyLighting Tree. If additional messages are desired, send a request on the forum
  - I may add the ability to add a custom list of messages if necessary
  - To disable the ON or OFF from sending a message, set the message to the first one "(BLANK)" and it will be ignore

## Deleting Nodes

When a Notify Node or Pushover Servicer Node is deleted under the Config tab, it WILL NOT be deleted from the NodeServer or the ISY. To delete a node, go under NODES on the Nodeserver.  Here you will see each of your nodes that you have ever created. A node can be deleted here by clicking on the X on the upper right of each node description. Restart the NodeServer and the nodes will be removed from both the node server and the ISY.

## Heartbeat monitoring

TODO: Add program info here

## Sending messages

###  Short Messages defined by user

The short messages that you added in Config are simple to send from a program. The first step is to add a Message in the config page, saving, and restarting the NodeServer. Then restart the admin console and then create a program. In the program you will set the message to be sent by adding the Notification Controller node and selecting the message. Then you will add the Service node, such as Pushover and select items such as: the Device to send it to, the priority, etc. Below is an example of sending a message 'Good Morning' that I have set up, to my phone with a Normal priority.

The structure of the program is a) set message in Notification Controller, b) choose any other parameters (optional), c) Send using one of your services.

```
HS Notify 01 - [ID 034D][Parent 0263]

If
        $s.HS.Current.DayNight is $s.HS.01.Morning

Then
        Set 'Notification Controller' Message Good Morning
        Set 'Notification Controller / Service Pushover homeisy' Device JimsPhone
        Set 'Notification Controller / Service Pushover homeisy' Priority Normal
        Set 'Notification Controller / Service Pushover homeisy' Send
```

### Notify Nodes with predefined messages

A Notify node accepts a Device ON / Device OFF from a scene or a program
- Create a Notify node in the Configuration using "Add Notify Nodes” as follows:
  - ID for Node: Set this to a short unique string (to be used for the nodeid in the ISY)
  - Name for Node: This text string will become the beginning of the message sent so descriptive names are helpful here. For example ‘Kitchen’. So when used with the predefined Light on message, the message delivered is ‘Kitchen Light on’
  - Service Node Name: Set to match to the Name of an existing Service Node you created, cap sensitive. In the above programming example, my Service Node Name is ‘homeisy’. This is the name I used for my Pushover service. Therefore if I want to use this Pushover service to deliver this predefined message, it needs to match this name and therefore would be ‘homeisy’. 
- Press 'Save Changes'
- Press 'Restart'

You should see the node show up in the ISY in the Admin Console, if it was already running and this is your first Notify Node, you will need to restart the admin console. If there are issues you should see messages in the Polyglot UI.

You can now add that node to a scene and when the scene is turned on or off, either by a controller or a program, the Message as defined in the node (one for on, one for off), will be sent.


### REST Interface

#### ISY Network Resource

This allows creating a simple network resource that can send messages via the Pushover service. These messages can contain text, system variables and any other node values etc. Additionally, they do not need to contain all the necessary paramaters for the Service, like user key, api key, devices, ...

- To create a Network Resource, use the following guide for each field under Configuration / Networking / Network Resources tab in the ISY Admin Console.  You can see all these options and apporpriate values in the Polyglot UI config page for the nodeserver which will show the real IP address and list out the actual values to use for device and sound.
  - First field: Select http
  - Second field: Select POST
  - Host: Enter the IP address of where the nodeserver is running. Example: IP of Polyisy can be found by your target IP, or in the Polyisy, under Settings / Polyisy Configuration. Example 10.0.1.23. 
  - Port: 8199 (Currently Hardcoded)
  - Path: /send?opt1=val1&opt2=val2...
    - Params
      - node=One of your Service nodes (required) in the format of po_example. Use all small letters and the po_ in front of your Pushover service name.
      - subject=Your subject (optional)
        - Use '+' for spaces, e.g. This+Is+The+Subject
      - The following are optional, and if not given then the defaults from your pushover node will be used
        - html 1 = allow html
        - monospace 1 = use monospace font
        - priority any legal [Pushover Priority](https://pushover.net/api#priority)
        - retry for Emergency Priority
        - expire for Emergency Priority
    - Example: /send?node=po_wind&subject=Weather+Update
      - This will send the message to the pushover node Wind with the subject Weather Update
  - Encode URL: not checked
  - Timeout: 5000
  - Mode: Raw Text
  - Body: The message body you want to send. It can be many lines and contain system variables, ISY nodes as well as other node server nodes as described in [ISY-994i Series:EMail and Networking Substitution Variables](https://wiki.universal-devices.com/index.php?title=ISY-994i_Series:EMail_and_Networking_Substitution_Variables)
	
An example below that outputs “38ºF, 14mph N, Gusts 23, Rain 78%” looks like this:

  ${var.1.28}ºF, ${var.2.48}mph N, Gusts ${var.2.49}, Rain ${sys.node.n002_weather.GV18}

  It includes the following:
   - ISY Integer variable #28, 
   - ISY State variable #48,
   - ISY State variable #49, 
   - Value of Nodeserver n002 (DarkSky) node GV18 (found under Polyisy/Dashboard/Darksky Nodes)
	
Once completed, save the new resource, then hit Save again under the resource tab,  then click on it an hit Test.Then create a program to send the new resource
```
Notification NR Test

If
        Time is  7:00:00AM
     Or Time is  6:00:00PM

Then
        Set 'Notification Controller / Service Pushover WIND' Priority Normal
        Set 'Notification Controller / Service Pushover WIND' Device JimsPhone
        Resource 'Test.1'
``` 
### Testing with REST interface directly.

You can test the REST interface from a command line by running curl:

curl -d '{"node":"po_develop", "message":"The Message", "subject":"The Subject"}' -H "Content-Type: application/json" -X POST http://192.168.86.77:8199/send
curl -d 'The message' -X POST 'http://192.168.86.77:8199/send?node=po_develop'

# Customized Content

I've been begging Michel and Chris to allow sending ISY "Customized Content" to a nodeserver.  This would make things much simpler.  Even better if ISY added Pushover as a service inside the Emails/Notifications page :)

## Installation

1. Backup Your ISY in case of problems!
   * Really, do the backup, please
2. Go to the Polyglot Store in the UI and click on Install for the Notification Nodeserver.
3. After installed, under Polyglot, go to Nodeservers menu and click on Add NodeServer. This will add the node server to your ISY
4. Go to the Configuration page and read those instructions. After configuration, restart the node sever.
5. Restart the ISY Admin Console if you already had it open

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

## Issues

### Forum
If you are having problems please post on the [Polyglot Notification Service Node Server](https://forum.universal-devices.com/forum/166-polyglot-notification-service-node-server/)

### Github
There is a list of known issues on the [Github Issues Page](https://github.com/jimboca/udi-poly-notification/issues)

### Log Package
You can also send a Log Package from the Polyglot UI in the Notifications -> Log page hit "Download Log Package", and PM that to JimBo on the forum.

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

- 1.0.4: 04/29/2020:
  - Enhancement: [Add more retry and timeouts to message posting](https://github.com/jimboca/udi-poly-notification/issues/19)
    - Changed to retry forever.
- 1.0.3: 04/29/2020:
  - Fix bug to only set ERR when there is an error
- 1.0.2: 04/29/2020:
  - Bug fix for improper initialization of Notify node sound
- 1.0.0: 04/29/2020:
  - Enhancement: [Add more retry and timeouts to message posting](https://github.com/jimboca/udi-poly-notification/issues/19)
    - See [Message Retry](https://github.com/jimboca/udi-poly-notification/blob/master/README.md#message-retry)
  - Enhancement: [Support setting custom sounds](https://github.com/jimboca/udi-poly-notification/issues/20)
  - Enhancement: [Generate config docs on the fly](https://github.com/jimboca/udi-poly-notification/issues/23)
- 0.1.17: 04/13/2021
  - Fixed Bug: [REST Interface Call Fails when priority param is specified](https://github.com/jimboca/udi-poly-notification/issues/18)
- 0.1.15: 03/05/2020
  - <a href="https://github.com/jimboca/udi-poly-notification/pull/15">Fixed incorrect char in Name Mapped Value</a>
- 0.1.14: 03/04/2020
  - Clean up documentation a little more
  - Add instructions for <a href="https://github.com/jimboca/udi-poly-notification/blob/master/README.md#notify-node>Adding a notify node</a> into a scene
  - Pushover Emergency reporting now works
  - Set Controller ST=True on startup
- 0.1.13: 02/28/2020
  - Set a notify node On or Off message to "(IGNORE)" to disable a message from being sent
  - Cleaned up documentation a little for Notify Nodes.
- 0.1.12: 02/29/2020
  - Fix bug from previous version casued by global search/replace.
- 0.1.11: 02/28/2020
  - Clean up error checking some more
- 0.1.10: 02/27/2020
  - Add some more error checking for valid service node names
  - Added a few more default messages
- 0.1.9: 02/25/2020
  - Add notices and error messages when notify node id's and pushover node names are not unique.
- 0.1.8: 02/18/2020
  - Fix crash in do_send https://github.com/jimboca/udi-poly-notification/issues/11
- 0.1.7: 02/10/2020
  - Avoid race condition when building profile and nodes are not added yet it will retry
  - Truncate pushover node names to 8 characters for users that don't follow instructions :)
- 0.1.6: 02/09/2020
  - Fixed creating list of devices.  WARNING: Check programs to make sure correct devices are still selected, order may change, but should never change again.
- 0.1.5: 02/01/2020
  - Remove references to Chump
  - Add info about adding network resources to configuration page
- 0.1.4: 12/22/2019
  - Use common nodedef for notification node instead of custom for each one since they are the same.
- 0.1.3: 12/12/2019
  - https://github.com/jimboca/udi-poly-notification/issues/3
- 0.1.2 10/19/2019
   - No longer use Chump pushover interface since it was easier to do it directly and now can use the monospace format
- 0.1.1 10/16/2019
  - Added more default messages, made it easier to add more in the future
- 0.1.0 10/15/2019
   - Add Acknowledge, Test on production device
- 0.0.6 10/14/2019
  - Notify nodes are now working
- 0.0.5 10/13/2019
  - Notify nodes are tied at creation time to a Service node.  They are still non functional.
- 0.0.4 10/12/2019
  - Start of Notify node, they are non-functional, but they exist.
- 0.0.3 10/11/2019
  - Lots of code and documentation cleanup, prep for release.
- 0.0.1 02/17/2019
  - Initial release for review.
