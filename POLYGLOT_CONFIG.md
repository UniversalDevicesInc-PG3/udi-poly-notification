
# Polyglot Node Server Configuration

## Pushover

- Make sure you have an API key as discussed on the [README](https://github.com/jimboca/udi-poly-notification/blob/master/README.md).
- For each Pushover application you want to use, Click "Add Pushover Keys" below.
  - Add the "Name" which is used as the ISY node address, and can be maximum of eight characters.
  - Add the User Key which can be found on your [Pushover Dashboard](https://pushover.net/dashboard)
  - Add the Application Key
- Restart the Nodeserver

## Common Notification Configuration

## Messages

These are the messages you want to send.  Create at least one message, restart NodeServer and re-open admin console to see the messages on the controller node.

- ID = This is the message ID.
  - It is used to build the profile, so you should never change this number if ANY message is referenced in a program.
  - It also determines the order the messages show up in the
- Title = The short message title, shown when selecting the message in the ISY Admin Console
- Message = The message body, if empty then it will be the same is the Title

## Restart

After changing any configuration you must restart the node server.

## Help

Please see [README](https://github.com/jimboca/udi-poly-notification/blob/master/README.md) for more information.

<i>Note: The information below is generated on the fly and will be updated on each nodeserver restart or when discover or update profile is run from the Admin Console.  It takes a minute to update since it polls the pushover servers.</i>
