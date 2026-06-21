# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.6.23] - 2026-06-20

### Fixed

- **Telegram notifications (Fixes #56):** Use Bot API `sendMessage` (urlencoded POST), parse Telegram `ok`/`description` responses, merge/strip invalid parameters, coerce `chat_id`, and discover chat id from `getUpdates` when users list is empty. Notify nodes guard against out-of-range NMESSAGE indices.

## [3.6.22] - 2026-06-20

### Fixed

- **Controller GV3 sync (#60):** Stop reporting undefined GV3 on the controller node. System custom content remains in-memory via `SET_SYS_CUSTOM`; controller nodeDef no longer references a nonexistent GV3 status.

## [3.6.21] - 2026-06-20

### Fixed

- **Typed data validation:** Pushover, ISYPortal, TelegramUB, and Notify entries with missing/empty names or ids are rejected with PG3 notices instead of crashing `handler_typed_data` (fixes `KeyError: 'name'` on invalid Telegram nodes).
- **Missing notification content:** `get_message_short()` no longer raises `UnboundLocalError` when ISY program query lacks `Content.uom145`; controller logs an error and sets notice `missing_notification_content`.
- **Profile rebuild with failed service nodes:** `write_profile()` now continues for healthy nodes when a service node fails init (e.g. invalid Pushover app token). Failed nodes keep existing profile assets, get per-node `profile_init_*` notices, and a summary `profile_init_errors` notice.

### Changed

- **Makefile:** `make production` now also builds `Notification-Production-Free-<NSVERSION>.zip`.

## [3.6.20] - 2026-05-28

### Fixed

- **ISY short node addresses:** controller resolves bare addresses (`udmobile`, `mn_boot`) to profile slot prefixes (`n001_udmobile`) and registers aliases so ISY commands no longer fail with "node address does not exist".

---

## [3.6.19] - 2026-05-27

### Fixed

- **Post-outage profile recovery:** service-node readiness now triggers controller-level profile recovery when startup finished with pending nodes, so UD Mobile/ISY Portal no longer require a manual plugin restart after DNS/network recovery.
- **Profile build tracking:** controller now tracks `profile_installed`, profiled service nodes, and pending nodes, with longer bounded waits for late startup and clearer deferred-node logging.
- **Queued delivery while recovering:** UD Mobile and ISY Portal now use bounded send queues (`128` max, `1 hour` max age), enqueue when not deliver-ready, and flush automatically after profile/service recovery.
- **Portal send result visibility:** `failedCount` parsing is now strict integer handling with `WARNING` logs when API accepts a request but reports failed deliveries.

---

## [3.6.18] - 2026-05-25

### Fixed

- **Startup wait logging:** controller handler-start waits now stay at `DEBUG` for brief normal delays, escalate to `WARNING` only for longer waits, and log a matching cleared message once startup recovers.

---

## [3.6.17] - 2026-05-25

### Changed

- **Documentation:** release notes now live in `CHANGELOG.md`, and `README.md` links here instead of carrying the full historical notes inline.

### Fixed

- **UD Mobile / ISY Portal startup:** normalize transport errors from `PolyglotREST` GET calls so DNS and connection failures return structured error results instead of crashing startup threads on boolean subscripting.
- **Startup retry behavior:** `UDMobile` and `ISYPortal` now retry `my.isy.io` startup validation and group fetches with exponential backoff for retryable DNS / connect / 5xx failures, while still failing fast on non-retryable auth errors like `401` / `403`.
- **Delayed DNS recovery:** if a notification service node initializes after startup once DNS comes back, it now rebuilds the generated profile so the node server can recover cleanly without a manual restart.
- **Readiness waits and log spam:** controller/profile waits and UD Mobile send-on-startup waits now log less aggressively and no longer loop forever in the failing startup case.

---

## Earlier releases

The following entries were migrated from `README.md` (original wording preserved).

Important! As of 3.5.2 sending to ISYPortal "devices" is deprecated. See [ISY Portal](README.md#isy-portal).

- 3.6.16: 01/01/2025
  - Fixed: [Group Names Not Updated on Change](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/58)
  - Fixed: [UDM Notification Group index's are changing](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/57)
- 3.6.15: 06/06/2024
  - Fixed Notify node sending to UDMobile
- 3.6.14: 05/10/2024
  - Fixed: [Increase Read timeout](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/54)
  - Fixed: [Pushover: Use Customization Subject as Title](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/55)
  - Also for Notify Node's use the Node Name as the title
- 3.6.12: 01/19/2024
  - Added more info to the "Please Define api key" message.
- 3.6.11: 08/19/2023
  - Fixed: [ERROR after adding portal api key](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/50)
- 3.6.10: 08/16/2023
  - Properly set config doc on startup
  - Add node names for PG3 UI
  - UD Mobile wait to send message until node is ready in case message is sent on startup
- 3.6.8: 06/25/2023
  - Add support for UDMobile [notify node](README.md#notify-nodes-with-predefined-messages) with updated [instructions](README.md#notify-nodes-with-predefined-messages).
  - Fix Pushover defaults when not supplied
  - Only show reboot message for UD Mobile, will add for others when Admin Console is fixed.
- 3.6.7: 06/23/2023
  - Update to pass NS version the new way
- 3.6.6: 06/22/2023
  - Fix bug which caused a lot of the configuration documentation to not show up
    - Also add more info to configuration doc, still more to add.
- 3.6.5: 06/22/2023
  - Fixed error message
- 3.6.4: 06/21/2023
  - Now requires an even newer version of PG3/PG3x, which isn't released yet, to fix pushover messages using sys_notify_full
  - Trap old uom issues with UD Mobile nodes
- 3.6.3: 06/20/2023
  - Bug fixes for new [System Customizations](README.md#system-customizations)
- 3.6.2: 06/15/2023
  - Support _sys_notify_full and _sys_notify_short based on ISY Version and PG3 version. See [System Customizations](README.md#system-customizations)
- 3.6.0: 06/08/2023 (In Beta Only)
  - Convert to sys_notify_full to send full custom messages!
  - Only compatible with IoX 5.6.2 and above
  - Release for testing with PG3 & UD Mobile.
- 3.5.9: 06/11/2023
  - Fixed usage of devices and groups for ISYPortal nodes.
  - Fixed [Crash on restart](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/40)
  - Fixed [Crash on bad Config data](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/42)
  - Fixed [Crash when message id is not defined](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/43)
  - Fixed [Do not try to initialize Pushover when initialize fails](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/27)
- 3.5.8: 06/06/2023
  - Fixes for Free version to start UDMobile node.
- 3.5.4: 05/23/2023
  - Support "Free" Limited version. See [Editions](README.md#editions)
- 3.5.3: 05/23/2023
  - Many fixes for [UD Mobile](README.md#ud-mobile) node.
- 3.5.2: 05/21/2023
  - Add group selection to [ISY Portal](README.md#isy-portal) and list devices as deprecated.
- 3.5.1: 05/20/2023
  - Added [UD Mobile](README.md#ud-mobile) node.
- 3.4.4: 07/04/2022
  - First production release of ISYPortal notifications
  - Fix bug in 'Send Sys Short' for ISYPortal and Pushover
- 3.4.3: 06/29/2022
  - Clean up Configuration page for ISY Portal
  - Fix error on initial install startup
  - Clean up REST server start and error reporting
  - Should be ready for production release if no issues are found
- 3.4.2: 06/28/2022
  - Fix issues with configurable rest server port
- 3.4.1: 06/28/2020
  - Fix to all setting REST Server port to another port, or nothing which means to not start the REST Server.
- 3.4.0: 06/27/2022
  - Initial support of ISY Portal notifications used by UD Mobile.
- 3.3.4: 04/14/2022
  - Fix [Editor missing subset](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/36)
  - Fix [Remove optional from Command Parameters](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/39)
  - Fix [Crash when bad device index is passed in](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/35)
  - Fix [Crash in handler_typed_data calling write_profile](https://github.com/UniversalDevicesInc-PG3/udi-poly-notification/issues/34)
  - Force udi_interface 3.0.40
- 3.3.3: 04/04/2022
  - Force latest udi_interface
- 3.3.2: 04/03/2022
  - Don't crash if telegram node is defined, but not given a name.
- 3.3.1: 04/03/2022
  - Fix issue caused by 3.3.0 where old programs referencing "Send" didn't work, they now show as "Send Message (old from controller)"
  - Added "Message" and "Short Custom Content" to Pushover node, which makes more sense than referencing the message from the Controller node.
  - Added "Send Sys Short With Params" to set all message params and send message in one program line.
- 3.3.0: 03/29/2022
  - Add Sys Short Messsages
- 3.2.4: 03/08/2022
  - Stop calls poly.stop
- 3.2.3: 02/23/2022
  - Added Telegram info to PG3 Configurtion page.
- 3.2.2: 02/22/2022
  - Now required to enter userid in config, could possibly support multiple in the future.
  - Clear validate error on success
  - Fix crash in Telgram send broken in last release
- 3.2.1: 02/22/2022
  - Initial production release of Telegram User Bot
- 3.2.0: 02/21/2022 BETA
  - Initial add of Telegram for testing
- 3.1.1: 02/04/2022
  - Add new 'REST Status' on Controller, see Monitoring section for more information.
    - This was discovered as an issue if ISY sends a post that contains spaces
- 3.1.0: Never officially released
- 3.0.4: 02/02/2022
  - Clean up logging in session, no real change
- 3.0.3: 01/25/2022
  - Fix initialization of controller messages
- 3.0.2: 01/23/2022
  - Fix crash on new install
- 3.0.1: 01/08/2022
  - Fix crash on notify node
- 3.0.0: 01/08/2022
  - First PG3 release
- 1.0.11-1.0.12: 07/26/2021:
  - Fix when sound integers are not in order
- 1.0.10: 07/25/2021:
  - Fix [Not all service node defaults are being passed to send](https://github.com/jimboca/udi-poly-notification/issues/29)
  - Also, now allow passing sound by name instead of just the index in REST calls.
- 1.0.9: 07/24/2021:
  - Fix: [Command Name discrepancy Query/Refresh](https://github.com/jimboca/udi-poly-notification/issues/16)
    - Also fixes so query command works
- 1.0.8: 07/24/2021:
  - Fix: [Support setting custom sounds](https://github.com/jimboca/udi-poly-notification/issues/20)
    - Default Pushover sounds are now always first in the list, followed by custom sounds.
    - IMPORTANT: After updating and restarting the nodeserver AND restarted admin console:
      - All custom sounds indexes have changed, so you must edit your programs that have custom sounds.
      - If you have custom sounds and they were first in the list, then all sound indexes have change, so edit your programs
      - The indexes are all properly tracked now so they will never change in the future.
- 1.0.7: 06/18/2021:
  - Bug: Fix getting current sound on first restart after adding a new Service nodes
  - Buf: Fix error on restart calling server stop
- 1.0.6: 05/02/2021:
  - Bug: Fix checking device index when passed in directly from network resource
- 1.0.5: 05/01/2020:
  - Bug: Fixed Notify Node Names
- 1.0.4: 05/01/2020:
  - Enhancement: [Add more retry and timeouts to message posting](https://github.com/jimboca/udi-poly-notification/issues/19)
    - Changed to retry forever.
- 1.0.3: 04/29/2020:
  - Fix bug to only set ERR when there is an error
- 1.0.2: 04/29/2020:
  - Bug fix for improper initialization of Notify node sound
- 1.0.0: 04/29/2020:
  - Enhancement: [Add more retry and timeouts to message posting](https://github.com/jimboca/udi-poly-notification/issues/19)
    - See [Message Retry](README.md#message-retry-and-controller-status)
  - Enhancement: [Support setting custom sounds](https://github.com/jimboca/udi-poly-notification/issues/20)
  - Enhancement: [Generate config docs on the fly](https://github.com/jimboca/udi-poly-notification/issues/23)
- 0.1.17: 04/13/2021
  - Fixed Bug: [REST Interface Call Fails when priority param is specified](https://github.com/jimboca/udi-poly-notification/issues/18)
- 0.1.15: 03/05/2020
  - [Fixed incorrect char in Name Mapped Value](https://github.com/jimboca/udi-poly-notification/pull/15)
- 0.1.14: 03/04/2020
  - Clean up documentation a little more
  - Add instructions for [adding a notify node](README.md#notify-nodes-with-predefined-messages) into a scene
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
  - Fixed creating list of devices. WARNING: Check programs to make sure correct devices are still selected, order may change, but should never change again.
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
  - Notify nodes are tied at creation time to a Service node. They are still non functional.
- 0.0.4 10/12/2019
  - Start of Notify node, they are non-functional, but they exist.
- 0.0.3 10/11/2019
  - Lots of code and documentation cleanup, prep for release.
- 0.0.1 02/17/2019
  - Initial release for review.
