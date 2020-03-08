
# Polyglot Node Server Configuration
Please read <a href="https://github.com/jimboca/udi-poly-notification/blob/master/README.md" target="_ blank">README</a> for more information and insight to Configuration described below.

## Messages

These are short custom messages you want to send.  Create at least one message, save, then restart NodeServer and re-open admin console to see the messages on the Notification Controller Node.

- ID: This is the message ID.
  - It is used to build the profile inside of the ISY, so you should never change this number if ANY message is referenced in a program.
  - It also determines the order the messages show up in the drop down list in the node
- TITLE: The short message title. This is shown when selecting the message in the ISY Admin Console either under the Notification Controller Node, or when adding the Notification Controller to a program. See example in the README.
- MESSAGE: The message body, if empty then it will be the same as the Title

## Service Pushover Nodes Keys:

The Service nodes allow you to send messages to a service, currently the only supported service is Pushover.  You must define at least one Service Node. See below:

### Pushover

You must have a user key for the <a href="https://pushover.net/dashboard" target="_ blank">Pushover Service</a> and you will need at least one application key which are listed at the bottom of that page under "Your Applications". If you don't have one, or want to create a different one you can <a href="https://pushover.net/apps/clone/universal_devices" target="_ blank">clone the Universal Devices application</a>

You may create multiple Applications on Pushover, just list each one with a unique name.  This allows you to use different icons to easily distinguish and categorize the messages in the Pushover app, but is not necessary, depending on your other naming and message nomenclatures used:

- For each Pushover application you want to use, Click "Add Service Pushover Nodes" below.
  - Add the "Name" which is used as the ISY node address, and can be maximum of eight characters.
  - Add the User Key which can be found on your <a href="https://pushover.net/dashboard" target="_ blank">Pushover Dashboard</a>
  - Add the Application Key
- Save and Restart the Nodeserver

## Notify Nodes

A Notify node accepts a Device ON / Device OFF from a scene or a program. Create a Notify node in the Configuration using "Add Notify Nodes” as follows:
  - ID for Node: Set this to a short unique string (to be used for the nodei d in the ISY)
  - Name for Node: This text string will become the beginning of the message sent.
  - Service Node Name: Set to match to the Name of an existing Service Node you created above. 
- Press 'Save Changes'
- Press 'Restart'

You should see the node show up in the ISY in the Admin Console, if it was already running and this is your first Notify Node, you will need to restart the admin console. If there are issues you should see messages in the Polyglot UI.

## Assistant Relay

## Restart

After changing any configuration you must restart the node server.

## Help

Please see <a href="https://github.com/jimboca/udi-poly-notification/blob/master/README.md" target="_ blank">README</a> for more information.

<i>Note: The information below is generated on the fly and will be updated on each nodeserver restart or when discover or update profile is run from the Admin Console.  It takes a minute to update since it polls the pushover servers.</i>
