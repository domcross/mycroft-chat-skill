from mycroft import MycroftSkill, intent_file_handler


class MattermostForMycroft(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)

    @intent_file_handler('mycroft.for.mattermost.intent')
    def handle_mycroft_for_mattermost(self, message):
        self.speak_dialog('mycroft.for.mattermost')


def create_skill():
    return MattermostForMycroft()

