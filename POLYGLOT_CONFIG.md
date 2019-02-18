
# Polyglot Notifiction Configuration

## Messages

These are the messages you you want to send.  Create at least one messge, restart NodeServer and re-open admin console to see the messages on the controller node.

ID = This is the message ID.  It is used to build the profile, so you never change this number if the message is referenced in a program!

Title = The short message title, shown when selecting the message in the ISY Admin Console

Message = The message body, if empty then it will be the same is the Title

## Pushover

- Create an application at [Pushover](https://pushover.net/api#registration)
- Add the "Name" which is used as the ISY node address, and can be eight characters max.
- Add the User and Applicaiton Keys for your pushover.
- Restart the Nodeserver
