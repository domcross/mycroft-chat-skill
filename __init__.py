from mycroft import MycroftSkill, intent_file_handler
from mycroft.util.log import LOG
from mattermostdriver import Driver
from datetime import datetime
import time

class MattermostForMycroft(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)
        self.username = self.settings.get("username", "")
        self.token = self.settings.get("token", "")
        self.ttl = self.settings.get("ttl", 10) * 60
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
            # TODO check if user is member of several teams?
            self.teamid = self.mm.teams.get_team_members_for_user(
                self.userid)[0]['team_id']
            LOG.debug("id: {} teamid: {}".format(self.userid, self.teamid))
            # TODO scheduled update of channels?
            self.channels_ts = 0
            self.channels = None #self._get_channels()
            self.unread_ts = 0
            self.unread = None #self._get_unread()
            self.usercache = {}

    @intent_file_handler('mycroft.for.mattermost.intent')
    def handle_mycroft_for_mattermost(self, message):
        self.speak_dialog('mycroft.for.mattermost')

    @intent_file_handler('read.unread.messages.intent')
    def read_unread_messages(self, message):
        for unr in self._get_unread():
            msg_count = unr['msg_count']
            if msg_count:
                channel_message = self.dialog_renderer.render(
                        "messages.for.channel", {
                            'display_name': unr['display_name']
                        })
                self.speak(channel_message)
                pfc = self.mm.posts.get_posts_for_channel(unr['channel_id'])
                order = pfc['order']
                for i in range(0, msg_count):
                    post = pfc['posts'][order[msg_count - i - 1]]
                    message = self.dialog_renderer.render(
                        "message", {
                            'user_name': self._get_user_name(post['user_id']),
                            'create_at': datetime.fromtimestamp(
                                post['create_at'] / 1000).strftime(
                                    '%Y-%m-%d %H:%M:%S'),  # TODO use nicetime
                            'message': post['message']
                        })
                    self.speak(message)  # TODO react to "stop"

    @intent_file_handler('list.unread.channels.intent')
    def list_unread_channels(self, message):
        for unr in self._get_unread():
            responses = []
            if(unr['msg_count'] and unr['mention_count']):
                responses.append(self.dialog_renderer.render(
                    "channel.unread.and.mentioned", {
                        'msg_count': unr['msg_count'],  # TODO use nice_number
                        'display_name': unr['display_name'],
                        'mention_count': unr['mention_count']
                    }))
            elif unr['msg_count']:
                responses.append(self.dialog_renderer.render(
                    "channel.unread", {
                        'msg_count': unr['msg_count'],  # TODO use nice_number
                        'display_name': unr['display_name']
                    }))
            elif unr['mention_count']:
                responses.append(self.dialog_renderer.render(
                    "channel.mentioned", {
                        'mention_count': unr['mention_count'],
                        'display_name': unr['display_name']
                    }))

            if responses:
                for res in responses:
                    self.speak(res)

    @intent_file_handler('unread.messages.intent')
    def check_unread_messages_and_mentions(self, message):
        unreadmsg = 0
        mentions = 0
        for unr in self._get_unread():
            if(unr['msg_count']):
                unreadmsg += unr['msg_count']
            if(unr['mention_count']):
                mentions += unr['mention_count']
        response = ""
        if unreadmsg:
            response += self.dialog_renderer.render("unread.messages", {
                'unreadmsg': unreadmsg})
            response += " "
        if mentions:
            response += self.dialog_renderer.render("mentioned", {
                "mentions": mentions})
        if response:
            self.speak(response)
        else:
            self.speak_dialog('no.unread.messages')

    def _get_channels(self):
        if (time.time() - self.channels_ts) > self.ttl:
            self.channels = self.mm.channels.get_channels_for_user(
                self.userid, self.teamid)
            self.channels_ts = time.time()
        return self.channels

    def _get_unread(self):
        if (time.time() - self.unread_ts) > self.ttl:
            unread = []
            for chan in self._get_channels():
                if chan['team_id'] != self.teamid:
                    continue
                unr = self.mm.channels.get_unread_messages(
                        self.userid, chan['id'])
                unread.append({
                    'display_name': chan['display_name'],
                    'msg_count': unr['msg_count'],
                    'mention_count': unr['mention_count'],
                    'channel_id': chan['id']
                })
            self.unread = unread
            self.unread_ts = time.time()
        return self.unread

    def _get_user_name(self, userid):
        if not (userid in self.usercache):
            user = self.mm.users.get_user(userid)
            self.usercache[userid] = user['username']
        return self.usercache[userid]


def create_skill():
    return MattermostForMycroft()


def shutdown(self):
        self.mm.logout()
        super(MattermostForMycroft, self).shutdown()
