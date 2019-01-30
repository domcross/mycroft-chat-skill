# Copyright 2018, domcross
# Github https://github.com/domcross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
        # login data
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
                self.channel_subscriptions = None
                self.channel_subs_ts = 0
                # basic info of channels
                # channel_id, display_name, (unread) msg_count, mentions
                self.channel_info = None
                self.channel_info_ts = 0
                self.usercache = {}
                self.prev_unread = 0
                self.prev_mentions = 0
                if self.settings.get('monitoring', False):
                    self.monitoring = True
                    self.schedule_repeating_event(self._mattermost_monitoring_handler,
                                      None, self.ttl, 'Mattermost')
                else:
                    self.monitoring = False

        # Check and then monitor for credential changes
        self.settings.set_changed_callback(self.on_websettings_changed)

    def on_websettings_changed(self):
        LOG.debug("websettings changed!")
        if self.mm:
            self.mm.logout()
        if self.monitoring:
            self.cancel_scheduled_event('Mattermost')
        self.initialize()

    @intent_file_handler('read.unread.channel.intent')
    def read_channel_messages(self, message):
        if not self.mm:
            self.speak_dialog("skill.not.initialized")
            return
        elif self.state != "idle":
            return
        else:
            self.state = "speaking"
        channel_name = message.data.get('channel')
        LOG.debug("data {}".format(message.data))
        if not channel_name:
            self.speak_dialog('channel.unknown', data={'channel': ''})
            self.state = "idle"
            return
        # do some fuzzy matching on channel
        best_chan = {}
        best_score = 66  # minimum score required
        for chan in self._get_channel_info():
            score = fuzz.ratio(channel_name.lower(),
                               chan['display_name'].lower())
            # LOG.debug("{}->{}".format(unr['display_name'], score))
            if score > best_score:
                best_chan = chan
                best_score = score
        LOG.debug("{} -> {}".format(best_chan, best_score))
        if not best_chan:
            self.speak_dialog('channel.unknown',
                              data={'channel': channel_name})
        elif best_chan['msg_count'] == 0:
            self.speak_dialog('no.unread.channel.messages',
                              data={'channel': channel_name})
        else:
            self._read_unread_channel(best_chan)
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
        self.settings['monitoring'] = True
        self.settings.store(force=True)
        self.speak_dialog('monitoring.active')

    @intent_file_handler('end.monitoring.intent')
    def end_monitoring_mattermost(self, message):
        LOG.debug("end monitoring")
        self.cancel_scheduled_event('Mattermost')
        self.monitoring = False
        self.settings['monitoring'] = False
        self.settings.store(force=True)
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
        for chan in self._get_channel_info():
            if self.state == "stopped":
                break
            self._read_unread_channel(chan)
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

        count = 0
        for ch in self._get_channel_info():
            responses = []
            if(ch['msg_count'] and ch['mention_count']):
                responses.append(self.dialog_renderer.render(
                    "channel.unread.and.mentioned", {
                        'msg_count': ch['msg_count'],  # TODO use nice_number
                        'display_name': ch['display_name'],
                        'mention_count': ch['mention_count']
                    }))
            elif ch['msg_count']:
                responses.append(self.dialog_renderer.render(
                    "channel.unread", {
                        'msg_count': ch['msg_count'],  # TODO use nice_number
                        'display_name': ch['display_name']
                    }))
            elif ch['mention_count']:
                responses.append(self.dialog_renderer.render(
                    "channel.mentioned", {
                        'mention_count': ch['mention_count'],
                        'display_name': ch['display_name']
                    }))

            if responses:
                count += 1
                for res in responses:
                    if self.state == "stopped":
                        break
                    self.speak(res, wait=True)

        if count == 0:
            # no unread/mentions
            self.speak_dialog('no.unread.messages')
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
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text('unread: {} mentions: {}'.format(unreadmsg,
                                                                   mentions))
        self.speak(response, wait=True)
        self.enclosure.activate_mouth_events()
        self.enclosure.mouth_reset()
        self.state = "idle"

    def stop(self):
        # this requires mycroft-stop skill installed
        if self.state == "speaking":
            LOG.debug("stopping")
            self.state = "stopped"
            return True
        return False

    def _read_unread_channel(self, chan):
        if self.state == "stopped":
            return
        msg_count = chan['msg_count']
        if msg_count:
            channel_message = self.dialog_renderer.render(
                    "messages.for.channel", {
                        'display_name': chan['display_name']
                    })
            LOG.debug(channel_message)
            self.speak(channel_message)
            pfc = self.mm.posts.get_posts_for_channel(chan['channel_id'])
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
                time.sleep(.3)
            # mark channel as read
            self.mm.channels.view_channel(self.userid, {
                'channel_id': chan['channel_id']})
            # TODO clarify when to reset prev_unread/prev_mentions
            self.prev_unread = 0
            self.prev_mentions = 0

    def _get_unread_msg_count(self):
        unreadmsg = 0
        for chan in self._get_channel_info():
            if(chan['msg_count']):
                unreadmsg += chan['msg_count']
        return unreadmsg

    def _get_mention_count(self):
        mentions = 0
        for chan in self._get_channel_info():
            if(chan['mention_count']):
                mentions += chan['mention_count']
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
        if (time.time() - self.channel_subs_ts) > 30:
            self._get_channel_subscriptions()
        if (time.time() - self.channel_info_ts) > 30:
            self._get_channel_info()

        LOG.debug("check for notifications")
        unreadmsg = self._get_unread_msg_count()
        mentions = self._get_mention_count()
        # TODO clarify when to reset prev_unread/prev_mentions
        if unreadmsg != self.prev_unread:
            self.prev_unread = unreadmsg
        else:
            unreadmsg = 0
        if mentions != self.prev_mentions:
            self.prev_mentions = mentions
        else:
            mentions = 0

        LOG.debug("unread: {} mentions: {}".format(unreadmsg, mentions))
        if unreadmsg or mentions:
            # display unread and mentions on Mark-1/2 display
            display_text = self.dialog_renderer.render(
                    'display.message.count', {'unread': unreadmsg,
                                              'mentions': mentions})
            if self.config_core.get("enclosure").get("platform", "") == \
               'mycroft_mark_1':
                self.enclosure.deactivate_mouth_events()
                self.enclosure.mouth_text(display_text)
                # clear display after 30 seconds
                self.schedule_event(self._mattermost_display_handler, 30, None,
                                    'mmdisplay')
            elif self.config_core.get("enclosure").get("platform", "") == \
                 'mycroft_mark_2':
                self.gui.show_text(display_text, "MATTERMOST")

            if self.notify_on_updates:
                self.speak(self.__render_unread_dialog(unreadmsg, mentions))

    def _mattermost_display_handler(self):
        # clear display and reset display handler
        self.enclosure.activate_mouth_events()
        self.enclosure.mouth_reset()
        self.cancel_scheduled_event('mmdisplay')

    def _get_channel_subscriptions(self):
        # update channel subscriptions only every second ttl interval
        if (time.time() - self.channel_subs_ts) > (self.ttl * 2):
            LOG.debug("get channel subscriptions...")
            self.channel_subscriptions = self.mm.channels.get_channels_for_user(
                self.userid, self.teamid)
            self.channel_subs_ts = time.time()
            LOG.debug("...done")
            # LOG.debug(self.channel_subscriptions)
        return self.channel_subscriptions

    def _get_channel_info(self):
        if (time.time() - self.channel_info_ts) > self.ttl:
            LOG.debug("get channel info...")
            info = []
            for chan in self._get_channel_subscriptions():
                if chan['team_id'] != self.teamid:
                    continue
                unr = self.mm.channels.get_unread_messages(
                        self.userid, chan['id'])
                info.append({
                    'display_name': chan['display_name'],
                    'msg_count': unr['msg_count'],
                    'mention_count': unr['mention_count'],
                    'channel_id': chan['id']
                })
            self.channel_info = info
            self.channel_info_ts = time.time()
            LOG.debug("...done")
            # LOG.debug(self.channel_info)
        return self.channel_info

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
