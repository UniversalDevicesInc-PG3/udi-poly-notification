
# Polyglot Node Server Configuration

## Service Nodes

The Serice nodes allow you to send messages to a service, currently the only supported service is Pushover.  You must also define at least one Service Node.

### Pushover

You must have a user key for the <a href="https://pushover.net/dashboard" target="_ blank">Pushover Service</a> and you will need at least one application key which are listed at the bottom of that page under "Your Applications". If you don't have one, or want to create a different one you can <a href="https://pushover.net/apps/clone/universal_devices" target="_ blank">clone the Universal Devices application</a>

You may create multiple Applications on Pushover, just list each one with a unique name.  This allows you to use different icons to easily distinguish and categorize the messages in the Pushover app.

To add the configuration:

- For each Pushover application you want to use, Click "Add Pushover Service Nodes" below.
  - Add the "Name" which is used as the ISY node address, and can be maximum of eight characters.
  - Add the User Key which can be found on your <a href="https://pushover.net/dashboard" target="_ blank">Pushover Dashboard</a>
  - Add the Application Key
- Restart the Nodeserver

## Common Notification Configuration

## Messages

These are short custom messages you want to send.  Create at least one message, restart NodeServer and re-open admin console to see the messages on the controller node.

- ID = This is the message ID.
  - It is used to build the profile, so you should never change this number if ANY message is referenced in a program.
  - It also determines the order the messages show up in the
- Title = The short message title, shown when selecting the message in the ISY Admin Console
- Message = The message body, if empty then it will be the same is the Title

## Restart

After changing any configuration you must restart the node server.

## Help

Please see <a href="https://github.com/jimboca/udi-poly-notification/blob/master/README.md" target="_ blank">README</a> for more information.

<i>Note: The information below is generated on the fly and will be updated on each nodeserver restart or when discover or update profile is run from the Admin Console.  It takes a minute to update since it polls the pushover servers.</i>
