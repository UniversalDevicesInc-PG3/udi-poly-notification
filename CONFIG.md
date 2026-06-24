
# Polyglot Node Server Configuration
Please read <a href="https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/blob/master/README.md" target="_ blank">README</a> for more information and insight to Configuration described below.

## Custom Configuration Parameters

### acknowledge
<a href="https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/blob/master/ACKNOWLEDGE.md" target="_blank">Acknowledge</a>: Before using you must follow the link and follow do as instructed.

### rest_port
Default setting of 8199 is almost always ok, however if this port is used by something else it must be changed.  If you are not using the REST interface, then no need to worry about it.  In the future this will default to 0 to turn off this feature since it's not really needed anymore.

### portal\_api\_key

This is the key for sending messages to the UD Portal to create the special <a href="https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/blob/master/README.md#ud-mobile" target="_blank">UD Mobile node</a>. 

The API key can be obtained in UD Mobile -> Notification Tab -> Settings (Gear Icon).  However UDM can configure the Node Server with this parameter automatically if you click "Notifications" on the Home Tab.

## Messages

These are short custom messages you want to send.  These are no longer the recommended way, the <a href="https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/blob/master/README.md#system-customizations">System Customizations</a> are a better way.

But you can still use this if desired. Create at least one message, save, then restart NodeServer and re-open admin console to see the messages on the Notification Controller Node and the service nodes.

- ID: This is the message ID.
  - It is used to build the profile inside of the ISY, so you should never change this number if ANY message is referenced in a program.
  - It also determines the order the messages show up in the drop down list in the node
- TITLE: The short message title. This is shown when selecting the message in the ISY Admin Console either under the Notification Controller Node, or when adding the Notification Controller to a program. See example in the README.
- MESSAGE: The message body, if empty then it will be the same as the Title

## Service Nodes Keys:

The Service nodes allow you to send messages to a service, currently the only supported services are 
- Pushover
- UD Portal
- Telegram
- WhatsApp (CallMeBot)

### Pushover

You must have a user key for the <a href="https://pushover.net/dashboard" target="_ blank">Pushover Service</a> and you will need at least one application key which are listed at the bottom of that page under "Your Applications". If you don't have one, or want to create a different one you can <a href="https://pushover.net/apps/clone/universal_devices" target="_ blank">clone the Universal Devices application</a>

You may create multiple Applications on Pushover, just list each one with a unique name.  This allows you to use different icons to easily distinguish and categorize the messages in the Pushover app, but is not necessary, depending on your other naming and message nomenclatures used:

- For each Pushover application you want to use, Click "Add Service Pushover Nodes" below.
  - Add the "Name" which is used as the ISY node address, and can be maximum of eight characters.
  - Add the User Key which can be found on your <a href="https://pushover.net/dashboard" target="_ blank">Pushover Dashboard</a>
  - Add the Application Key
- Save and Restart the Nodeserver

Each Pushover service node keeps its own device and sound lists (keyed by node name), so multiple applications or different user keys no longer share or corrupt device indices. If you use multiple Pushover rows with **different user keys**, PG3 shows an informational notice; each node still maintains its own device picker after restart.

## UD Portal

These send messages to the UD Portal which are received by the UD Mobile app.  You crease service nodes, or use the UD Mobile node which is always created and uses the main portal_api_key Custom Config Parameter.

## Telegram

1. Open <a href="https://telegram.me/botfather" target="_blank">BotFather</a> and log in to Telegram if prompted
2. Click **Start** at the bottom of the chat
3. Send `/newbot` and follow BotFather's prompts (bot name and username)
4. Copy the HTTP API token BotFather returns and paste it into a **Telegram User Bot Service Node** row

- **HTTP API Key:** BotFather token (required)
- **Users:** optional; leave empty for auto-discovery after you send `/start` to your bot
- After Save, PG3 shows a notice with your bot link if chat id is not known yet
- After `/start`, **Restart** the nodeserver to auto-fill **Users** (PG3x has no Discover button, and Save Changes only works when config changed)
- The Telegram service node **Ready** status (`GV1`) is true when token and chat id are valid

Optional fallback: paste your numeric Telegram user id from <a href="https://t.me/RawDataBot" target="_blank">@RawDataBot</a> into **Users**.

## WhatsApp (CallMeBot)

Free personal WhatsApp text notifications via the <a href="https://www.callmebot.com/blog/free-api-whatsapp-messages/" target="_blank">CallMeBot API</a>. Setup is done entirely in PG3x configuration — no extra Python libraries required.

**Limitations:** CallMeBot does not support WhatsApp group chats. Each recipient must activate CallMeBot on their own phone; one API key sends only to that phone number. To notify multiple people, add multiple recipient rows on one service node (each gets the same message as an individual DM).

*Per recipient (repeat for each person):*
1. Add CallMeBot contact **+34 684 73 40 44** in WhatsApp
2. Send: `I allow callmebot to send me messages`
3. Receive API key in WhatsApp reply (or send `Recover APIKey` if lost)

*In PG3x:*
4. Click **Add WhatsApp Service Nodes (CallMeBot)** below
5. Set **Name** (8 characters or less, used as ISY node id)
6. Add one or more **Recipients** rows with **Phone** (include country code, e.g. `+1234567890`) and **CallMeBot API key**
7. Save and Restart — the nodeserver sends a startup test message to each recipient

## Notify Nodes

A Notify node accepts a Device ON / Device OFF from a scene or a program. Create a Notify node in the Configuration using "Add Notify Nodes” as follows:
  - ID for Node: Set this to a short unique string (to be used for the nodei d in the ISY)
  - Name for Node: This text string will become the beginning of the message sent.
  - Service Node Name: Set to match to the Name of an existing Service Node you created above, cap sensitive. 
- Press 'Save Changes'
- Press 'Restart'

You should see the node show up in the ISY in the Admin Console, if it was already running and this is your first Notify Node, you will need to restart the admin console. If there are issues you should see messages in the Polyglot UI.

## Assistant Relay

## Restart

After changing any configuration you must restart the node server.

## Help

Please see <a href="https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/blob/master/README.md" target="_ blank">README</a> for more information.

<i>Note: The information below is generated on the fly and will be updated on each nodeserver restart or when discover or update profile is run from the Admin Console.  It takes a minute to update since it polls the pushover servers.</i>
