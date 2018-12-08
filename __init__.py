from mycroft import MycroftSkill, intent_file_handler
from mycroft.util.log import LOG
from mattermostdriver import Driver


class MattermostForMycroft(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)
        self.username = self.settings.get("username", "")
        self.token = self.settings.get("token", "")
        # LOG.debug("username: {} token: {}".format(
        #        self.username, self.token))
        if self.username and self.token:
            self.mm = Driver({
                'url': 'chat.mycroft.ai',
                'token': self.token,
                'scheme': 'https',
                'port': 443,
                'verify': True
            })
            self.mm.login()
            self.userid = \
                self.mm.users.get_user_by_username(self.username)['id']
            # TODO: check if user is member of several teams?
            self.teamid = self.mm.teams.get_team_members_for_user(
                self.userid)[0]['team_id']
            LOG.debug("id: {} teamid: {}".format(self.userid, self.teamid))

    @intent_file_handler('mycroft.for.mattermost.intent')
    def handle_mycroft_for_mattermost(self, message):
        self.speak_dialog('mycroft.for.mattermost')

    @intent_file_handler('unread.messages.intent')
    def check_unread_messages_and_mentions(self, message):
        channels = self.mm.channels.get_channels_for_user(
            self.userid, self.teamid)

        unreadmsg = 0
        mentions = 0
        for chan in channels:
            if chan['team_id'] != self.teamid:
                continue
            unread = self.mm.channels.get_unread_messages(
                self.userid, chan['id'])
            if(unread['msg_count']):
                unreadmsg += unread['msg_count']
            if(unread['mention_count']):
                mentions += unread['mention_count']
            LOG.debug("channel {} has {} unread messages and {}  mentions".format(
                chan['display_name'], unread['msg_count'],
                unread['mention_count']))
        response = ""
        if unreadmsg:
            response += self.dialog_renderer.render("unread.messages", data={
                "unreadmsg": unreadmsg}) + " "
        if mentions:
            response += self.dialog_renderer.render("mentioned", data={
                "mentions": mentions})
        if response:
            self.speak(response)
        else:
            self.speak_dialog('no.unread.messages')


def create_skill():
    return MattermostForMycroft()
