
# Polyglot Node Server Configuration

<h1>Pushover</h1>

You must create an Application on <A href=https://pushover.net/api#registration>Pushover</A>

### Pushover Configuration

- Create an application at [Pushover](https://pushover.net/api#registration)
- Add the "Name" which is used as the ISY node address, and can be eight characters max.
- Add the User and Application Keys for your pushover.
- Restart the Nodeserver

# Polyglot Notification Configuration

## Messages

These are the messages you you want to send.  Create at least one messge, restart NodeServer and re-open admin console to see the messages on the controller node.

- ID = This is the message ID.  It is used to build the profile, so you should never change this number if the message is referenced in a program!
- Title = The short message title, shown when selecting the message in the ISY Admin Console
- Message = The message body, if empty then it will be the same is the Title
