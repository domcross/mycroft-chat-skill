# <img src='icon.png' card_color='#4093DB' width='50' height='50' style='vertical-align:bottom'/> Mattermost for Mycroft
Monitor Mattermost for mycroft and find out if you have been mentioned or if there are unread messages. Messages can be read by Mycroft as well.

## About
In your skill settings at home.mycroft.ai you must enter your username (as given in Mattermost account settings) and your personal access token. In case you do not have a token you can specify your login-id (usually that is your email) and your password. NOTE: your password will be stored in clear text in your settings.json!)

There is also the option to set the time interval between refresh/check for updates. When monitoring is active the skill will use that time period for automated checking.
The option "notify on updates" is only applicable when monitoring is active - when option is activated Mycroft willl speak out loud the number of unread messages and mentions.

You can also specify the server configuration. Default settings are for chat.mycroft.ai so you should already be ready to go. NOTE: change anything here and you are on your own! ;-)

## Examples
* "Are there unread messages on Mattermost"
* "Name Mattermost channels with unread messages"
* "Read all unread messages"
* "Read messages for the channel {name}"
* "Begin monitoring of mattermost"
* "End monitoring of mattermost"

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



