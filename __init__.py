from mycroft import MycroftSkill, intent_file_handler
from mycroft.util.log import LOG
from mattermostdriver import Driver

class MattermostForMycroft(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)
        self.username = self.settings.get("username","")
        self.token = self.settings.get("token","")
        LOG.debug("username: {} token: {}".format(
                self.username, self.token))
        if self.username and self.token:
            self.mm = Driver({
                'url': 'chat.mycroft.ai',
                'token': self.token,
                'debug': False,
                'scheme': 'https',
                'port': 443,
                'verify': True
            })
            self.mm.login()
            self.userid = \
                self.mm.users.get_user_by_username(self.username)['id']
            self.teamid = self.mm.teams.get_team_members_for_user(
                self.userid)[0]['team_id']
            LOG.debug("id: {} teamid: {}".format(self.userid, self.teamid))

    @intent_file_handler('mycroft.for.mattermost.intent')
    def handle_mycroft_for_mattermost(self, message):
        self.speak_dialog('mycroft.for.mattermost')

    @intent_file_handler('unread.messages.intent')
    def handle_mycroft_for_mattermost(self, message):
        channels = self.mm.channels.get_channels_for_user(
            self.userid, self.teamid)

        unreadmsg = 0
        for chan in channels:
            channelid = chan['id']
            unread = self.mm.channels.get_unread_messages(
                self.userid, channelid)
            msg_count = unread['msg_count']
            if(msg_count):
                unreadmsg += msg_count
                display_name = chan['display_name']
                LOG.debug("channel {} has {} unread messages".format(
                    display_name, msg_count))
        if unreadmsg:
            self.speak_dialog("unread.messages", data={"unreadmsg": unreadmsg})
        else:
            self.speak_dialog('no.unread.messages')


def create_skill():
    return MattermostForMycroft()

