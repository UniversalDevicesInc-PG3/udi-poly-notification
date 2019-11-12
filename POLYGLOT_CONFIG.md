
# Polyglot Node Server Configuration

## Pushover

- Create an application at [Pushover](https://pushover.net/apps), then come back here.
- For each Pushover application you want to use, Click "Add Pushover Keys" below.
  - Add the "Name" which is used as the ISY node address, and can be maximum of eight characters.
  - Add the User Key which can be found on your [Pushover Dashboard](https://pushover.net/dashboard)
  - Add the Application Key
- Restart the Nodeserver

# Polyglot Notification Configuration

## Messages

These are the messages you want to send.  Create at least one message, restart NodeServer and re-open admin console to see the messages on the controller node.

- ID = This is the message ID.  It is used to build the profile, so you should never change this number if the message is referenced in a program!
- Title = The short message title, shown when selecting the message in the ISY Admin Console
- Message = The message body, if empty then it will be the same is the Title

<i>Note: The information below is generated on the fly and will be updated on each nodeserver restart or when discover or update profile is run from the Admin Console.  It takes a minute to update since it polls the pushover servers.</i>
