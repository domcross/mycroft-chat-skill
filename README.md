# <img src='icon.png' card_color='#4093DB' width='50' height='50' style='vertical-align:bottom'/> Mycroft Chat
The [Mycroft Chat](chat.mycroft.ai) allows you to interact with other community users.
This skill allows you to monitor Mycroft Chat and find out if you have been mentioned or if there are unread messages.
The messages can be read to you by Mycroft as well.

## About
In your [skill settings](home.mycroft.ai) you must enter your username (as given in your Mycroft Chat account settings) and your personal access token.
In case you do not have a token you can specify your login-id (usually that is your email) and your password.
NOTE: your password will be stored in clear text in your settings.json!)

There is also the option to set the time interval between refresh/check for updates.
When monitoring is active the skill will use that time period for automated checking.
The option "notify on updates" is only applicable when monitoring is active -
when the option is activated Mycroft willl speak out loud the number of unread messages and mentions.

## Examples

* "Are there unread messages on Mycroft Chat"
* "Name Mycroft Chat channels with unread messages"
* "Read all unread Mycroft Chat messages"
* "Read messages for the channel {name}"
* "Begin monitoring of Mycroft Chat"
* "Stop monitoring of Mycroft Chat"

## Advanced - Server configuration

The [Mycroft Chat](chat.mycroft.ai) is based on [Mattermost](https://www.mattermost.org/).
You can connect with this skill to any chat server that runs on Mattermost.

For this you must change in the server configuration in your [skill settings](home.mycroft.ai).
Default settings are for chat.mycroft.ai - so you should probably write these down in case you want to switch back to Mycroft Chat.
NOTE: change anything here and you are on your own! ;-)

Hint: for all intents you can use "Mattermost" instead of "Mycroft Chat", e.g. "Are there unread messages on Mattermost"

## Credits
Dominik (@domcross)

Skill [suggested](https://community.mycroft.ai/t/mattermost-for-mycroft/5293) by Andreas Lorenson (@andlo)

## Category
Daily
Information
**Productivity**

## Tags
#chat
#mattermost


[![Say Thanks to the author of this skill!](https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg)](https://saythanks.io/to/domcross)

