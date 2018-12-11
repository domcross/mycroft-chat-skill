from mycroft import MycroftSkill, intent_file_handler
from mycroft.util.format import nice_date, nice_time
from mycroft.util.log import LOG
from fuzzywuzzy import fuzz
from mattermostdriver import Driver
import mattermostdriver.exceptions as mme
from datetime import datetime
import time


class MattermostForMycroft(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)

    def initialize(self):
        self.state = "idle"
        self.mm = None
        # login
        self.username = self.settings.get("username", "")
        self.token = self.settings.get("token", "")
        self.login_id = self.settings.get("login_id", "")
        self.password = self.settings.get("password", "")
        # monitoring
        self.ttl = self.settings.get("ttl", 10) * 60
        self.notify_on_updates = self.settings.get("notify_on_updates", False)
        LOG.debug("username: {}".format(self.username))

        mm_driver_config = {
                'url': self.settings.get("url", "chat.mycroft.ai"),
                'scheme': self.settings.get("scheme", "https"),
                'port': self.settings.get("port", 443),
                'verify': self.settings.get("verify", True)
        }

        if self.token:
            mm_driver_config['token'] = self.token
        elif self.login_id and self.password:
            mm_driver_config['login_id'] = self.login_id
            mm_driver_config['password'] = self.password

        if self.username:
            self.mm = Driver(mm_driver_config)
            try:
                self.mm.login()
                self.userid = \
                    self.mm.users.get_user_by_username(self.username)['id']
                # TODO check if user is member of several teams?
                self.teamid = self.mm.teams.get_team_members_for_user(
                    self.userid)[0]['team_id']
                LOG.debug("userid: {} teamid: {}".format(self.userid, self.teamid))
            except (mme.ResourceNotFound, mme.HTTPError,
                    mme.NoAccessTokenProvided, mme.NotEnoughPermissions,
                    mme.InvalidOrMissingParameters) as e:
                LOG.debug("Exception: {}".format(e))
                self.mm = None
                self.speak_dialog("mattermost.error", {'exception': e})
            if self.mm:
                # info on all subscribed public channels as returned by MM
                # TODO tidy this up as self.channels is mostly obsolete
                self.channels = None
                self.channels_ts = 0
                # basic info of channels (not only unread as name suggest)
                # channel_id, display_name, (unread) msg_count, mentions
                self.unread = None
                self.unread_ts = 0
                self.usercache = {}
                self.prev_unread = 0
                self.prev_mentions = 0
                self.monitoring = False

    def on_websettings_changed(self):
        if self.mm:
            self.mm.logout()
        if self.monitoring:
            self.cancel_scheduled_event('Mattermost')
        self.initialize()

    # @intent_file_handler('mycroft.for.mattermost.intent')
    # def handle_mycroft_for_mattermost(self, message):
    #     self.speak_dialog('mycroft.for.mattermost')

    @intent_file_handler('read.unread.channel.intent')
    def read_channel_messages(self, message):
        if not self.mm:
            self.speak_dialog("skill.not.initialized")
            return
        elif self.state != "idle":
            return
        else:
            self.state = "speaking"
        chan = message.data.get('channel')
        LOG.debug("data {}".format(message.data))
        if not chan:
            self.speak_dialog('channel.unknown', data={'channel': ''})
            self.state = "idle"
            return
        best_unr = {}
        best_score = 66
        for unr in self._get_unread():
            score = fuzz.ratio(chan.lower(), unr['display_name'].lower())
            # LOG.debug("{}->{}".format(unr['display_name'], score))
            if score > best_score:
                best_unr = unr
                best_score = score
        LOG.debug("{} -> {}".format(best_unr, best_score))
        if not best_unr:
            self.speak_dialog('channel.unknown', data={'channel': chan})
        elif best_unr['msg_count'] == 0:
            self.speak_dialog('no.unread.channel.messages', data={'channel':
                                                                  chan})
        else:
            self._read_unread_channel(best_unr)
        self.state = "idle"

    @intent_file_handler('start.monitoring.intent')
    def start_monitoring_mattermost(self, message):
        if not self.mm:
            self.speak_dialog("skill.not.initialized")
            return
        LOG.debug("start monitoring with ttl {} secs".format(self.ttl))
        self.schedule_repeating_event(self._mattermost_monitoring_handler,
                                      None, self.ttl, 'Mattermost')
        self.monitoring = True
        self.speak_dialog('monitoring.active')

    @intent_file_handler('end.monitoring.intent')
    def end_monitoring_mattermost(self, message):
        LOG.debug("end monitoring")
        self.cancel_scheduled_event('Mattermost')
        self.monitoring = False
        self.speak_dialog('monitoring.inactive')

    @intent_file_handler('read.unread.messages.intent')
    def read_unread_messages(self, message):
        if not self.mm:
            self.speak_dialog("skill.not.initialized")
            return
        elif self.state != "idle":
            return
        else:
            self.state = "speaking"
        for unr in self._get_unread():
            if self.state == "stopped":
                break
            # here
            self._read_unread_channel(unr)
        self.state = "idle"

    @intent_file_handler('list.unread.channels.intent')
    def list_unread_channels(self, message):
        if not self.mm:
            self.speak_dialog("skill.not.initialized")
            return
        elif self.state != "idle":
            return
        else:
            self.state = "speaking"
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
                    if self.state == "stopped":
                        break
                    self.speak(res, wait=True)
        self.state = "idle"

    @intent_file_handler('unread.messages.intent')
    def check_unread_messages_and_mentions(self, message):
        if not self.mm:
            self.speak_dialog("skill.not.initialized")
            return
        elif self.state != "idle":
            return
        else:
            self.state = "speaking"
        unreadmsg = self._get_unread_msg_count()
        mentions = self._get_mention_count()
        response = self.__render_unread_dialog(unreadmsg, mentions)
        self.speak(response)
        self.state = "idle"

    def stop(self):
        # this requires mycroft-stop skill installed
        if self.state == "speaking":
            LOG.debug("stopping")
            self.state = "stopped"
            return True
        return False

    def _read_unread_channel(self, unr):
        if self.state == "stopped":
            return
        msg_count = unr['msg_count']
        if msg_count:
            channel_message = self.dialog_renderer.render(
                    "messages.for.channel", {
                        'display_name': unr['display_name']
                    })
            LOG.debug(channel_message)
            self.speak(channel_message)
            pfc = self.mm.posts.get_posts_for_channel(unr['channel_id'])
            order = pfc['order']
            # in case returned posts are less than number of unread
            # avoid 'index out of bounds'
            msg_count = msg_count if msg_count < len(order) else len(order)
            prev_date = ""
            for i in range(0, msg_count):
                if self.state == "stopped":
                    break
                # order starts with newest to oldest,
                # start to read the oldest of the unread
                post = pfc['posts'][order[msg_count - i - 1]]
                create_at = ""
                # nice_date does only support en-us yet - bummer!
                # MM timestamps are in millisecs, python in secs
                msg_date = nice_date(datetime.fromtimestamp(
                    post['create_at'] / 1000), self.lang,
                    now=datetime.now())
                if prev_date != msg_date:
                    create_at = msg_date + " "
                    prev_date = msg_date
                msg_time = nice_time(datetime.fromtimestamp(
                    post['create_at'] / 1000), self.lang)
                create_at += msg_time
                msg = self.dialog_renderer.render(
                    "message", {
                        'user_name': self._get_user_name(post['user_id']),
                        'create_at': create_at,
                        'message': post['message']
                    })
                LOG.debug(msg)
                self.speak(msg, wait=True)
            # mark channel as read
            self.mm.channels.view_channel(self.userid, {
                'channel_id': unr['channel_id']})
            # TODO clarify when to reset prev_unread/prev_mentions
            self.prev_unread = 0
            self.prev_mentions = 0

    def _get_unread_msg_count(self):
        unreadmsg = 0
        for unr in self._get_unread():
            if(unr['msg_count']):
                unreadmsg += unr['msg_count']
        return unreadmsg

    def _get_mention_count(self):
        mentions = 0
        for unr in self._get_unread():
            if(unr['mention_count']):
                mentions += unr['mention_count']
        return mentions

    def __render_unread_dialog(self, unreadmsg, mentions):
        LOG.debug("unread {} mentions {}".format(unreadmsg, mentions))
        response = ""
        if unreadmsg:
            response += self.dialog_renderer.render('unread.messages', {
                'unreadmsg': unreadmsg})
            response += " "
        if mentions:
            response += self.dialog_renderer.render('mentioned', {
                'mentions': mentions})
        if not response:
            response = self.dialog_renderer.render('no.unread.messages')
        return response

    def _mattermost_monitoring_handler(self):
        LOG.debug("mm monitoring handler")
        # do not update when last run was less than 30secs before
        if (time.time() - self.channels_ts) > 30:
            self._get_channels()
        if (time.time() - self.unread_ts) > 30:
            self._get_unread()
        if self.notify_on_updates:
            LOG.debug("check for notifications")
            unreadmsg = self._get_unread_msg_count()
            mentions = self._get_mention_count()
            # TODO clarify when to reset prev_unread/prev_mentions
            if unreadmsg > self.prev_unread:
                self.prev_unread = unreadmsg
            else:
                unreadmsg = 0
            if mentions > self.prev_mentions:
                self.prev_mentions = mentions
            else:
                mentions = 0
            LOG.debug("unread: {} mentions: {}".format(unreadmsg, mentions))
            if unreadmsg or mentions:
                self.speak(self.__render_unread_dialog(unreadmsg, mentions))

    def _get_channels(self):
        if (time.time() - self.channels_ts) > self.ttl:
            LOG.debug("get channels...")
            self.channels = self.mm.channels.get_channels_for_user(
                self.userid, self.teamid)
            self.channels_ts = time.time()
            LOG.debug("...done")
            # LOG.debug(self.channels)
        return self.channels

    def _get_unread(self):
        if (time.time() - self.unread_ts) > self.ttl:
            LOG.debug("get unread...")
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
            LOG.debug("...done")
            # LOG.debug(self.unread)
        return self.unread

    def _get_user_name(self, userid):
        if not (userid in self.usercache):
            user = self.mm.users.get_user(userid)
            self.usercache[userid] = user['username']
            # LOG.debug("usercache add {}->{}".format(userid, user['username']))
        return self.usercache[userid]


def create_skill():
    return MattermostForMycroft()


def shutdown(self):
        if self.mm:
            self.mm.logout()
        if self.monitoring:
            self.cancel_scheduled_event('Mattermost')
        super(MattermostForMycroft, self).shutdown()
