from enum import Enum, auto
import discord
import re


class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    REPORT_COMPLETE = auto()
    AWAITING_CATEGORY = auto()
    IMMINENT_DANGER_SELECTION = auto()
    IMMINENT_DANGER = auto()
    ADDITIONAL_MESSAGE = auto()
    AWAITING_ADDITIONAL_MESSAGE = auto()
    AWAITING_BLOCK = auto()
    CONFIRM_SUBMIT = auto()
    MODERATOR_REVIEW = auto()
    AWAITING_ABUSE_VERIFICATION = auto()
    MOD_COMPLETE = auto()
    # FINAL = auto()


class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    CATEGORIES = (
        "'spam', 'inappropriate content', 'hate speech', 'imminent danger', or 'other'"
    )

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
        self.message_author = None
        self.imminent_danger = False
        self.virtual_kidnapping = False
        self.message_type = None  # photo or text?
        self.fake = None  # do our models tell us this is fake?
        self.block_user = False
        self.additional_message = None

    async def handle_message(self, message):
        # print(self.state)
        """
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord.
        """

        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]

        if self.state == State.REPORT_START:
            reply = "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]

        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search("/(\d+)/(\d+)/(\d+)", message.content)
            if not m:
                return [
                    "I'm sorry, I could not read the message link you sent. Please try again or say `cancel` to cancel."
                ]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return [
                    "I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."
                ]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return [
                    "It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."
                ]
            try:
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return [
                    "It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."
                ]

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.MESSAGE_IDENTIFIED
            self.message = message.content
            self.message_author = message.author.name
            return [
                "I found this message:",
                "```" + message.author.name + ": " + message.content + "```",
                "Is this the message you'd like to report? Please respond with 'yes' or 'no'.",
            ]

        if self.state == State.MESSAGE_IDENTIFIED:
            if message.content.lower() == "yes":
                self.state = State.AWAITING_CATEGORY
                return [
                    "What category would you like to report this message under? Please respond with "
                    + self.CATEGORIES
                    + "."
                ]
            elif message.content.lower() == "no":
                self.state = State.AWAITING_MESSAGE
                return ["Please copy paste the link to the message you want to report."]
            else:
                return [
                    "I'm sorry, I didn't understand that. Please respond with 'yes' or 'no'."
                ]

        if self.state == State.AWAITING_CATEGORY:
            category = message.content
            category_dict = {
                "spam": "Spam includes unsolicited, low-quality communications. ",
                "inappropriate content": "Inappropriate content contains sexually explicit, violent, or otherwise inappropriate content.",
                "hate speech": "Hate Speech: Hate speech contains discriminatory or derogatory language or images.",
                "imminent danger": "Imminent Danger contains threats of self-harm, violence, or kidnapping.",
                "other": "Other: Reported content doesn't fit into the above categories.",
            }
            if category in ["spam", "inappropriate content", "hate speech"]:
                self.state = State.ADDITIONAL_MESSAGE
                return [  # TODO: Insert description of what this abuse type is + our policy on it in text below
                    f"You've selected that this message falls under: {category}. {category_dict[category]} Please provide any additional details you'd like to include in your report."
                ]
            elif category == "other":
                self.state = State.ADDITIONAL_MESSAGE
                return [
                    f"You've selected: {category}. {category_dict[category]} Please explain why you reported this message and provide any additional details you'd like to include in your report."
                ]
            elif category == "imminent danger":
                self.state = State.IMMINENT_DANGER_SELECTION
                self.imminent_danger = True
                return [
                    f"Thank you for your urgency. You've selected: {category}. {category_dict[category]} To further inform the action we should take, please select which category this falls under. Respond with 'sh' for self-harm or suicidal intent, 'ct' for credible threat of violence, or 'kt' for kidnapping threat."
                    # TODO: maybe we should add an 'other' category here as well?
                ]
            else:
                return [
                    "I'm sorry, I couldn't understand the category. Please respond with "
                    + self.CATEGORIES
                    + "."
                ]

        if self.state == State.IMMINENT_DANGER_SELECTION:
            category = message.content
            if category in ["sh", "ct"]:
                self.state = State.ADDITIONAL_MESSAGE
                if category == "sh":
                    type = "self-harm or suicidal intent"
                elif category == "ct":
                    type = "credible threat of violence"
                return [  # TODO: Insert description of what this abuse type is + our policy on it in text below
                    f"You've selected that this message falls under: {type}. Our moderator's have been notified of this report. Please provide any additional details you'd like to include in your report."
                ]
            elif category == "kt":
                self.state = State.ADDITIONAL_MESSAGE
                self.virtual_kidnapping = True
                return [
                    f"You've selected that this message falls under: kidnapping threat. Our moderator's have been notified of this report, and the message is being run through our AI-detection model. Please provide any additional details you'd like to include in your report."
                ]
            else:
                return [
                    f"I'm sorry, I couldn't understand the category. Respond with 'sh' for self-harm or suicidal intent, 'ct' for credible threat of violence, or 'kt' for kidnapping."
                ]

        if self.state == State.ADDITIONAL_MESSAGE:
            self.additional_message = message.content
            self.state = State.AWAITING_ADDITIONAL_MESSAGE
            return [
                "Are there other messages you would like to flag? Please respond with 'yes' or 'no'.",
            ]

        if self.state == State.AWAITING_ADDITIONAL_MESSAGE:
            if message.content.lower() == "yes":
                reply = "The same process will be repeated for the next message.\n\n"
                reply += "Thank you for starting the reporting process. "
                reply += "Say `help` at any time for more information.\n\n"
                reply += (
                    "Please copy paste the link to the message you want to report.\n"
                )
                reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
                self.state = State.AWAITING_MESSAGE
                return [reply]
            elif message.content.lower() == "no":
                self.state = State.AWAITING_BLOCK
                return [
                    "Would you like to block this user from sending you more messages in the future? Please respond with 'yes' or 'no'."
                ]
            else:
                return [
                    "I'm sorry, I didn't understand that. Please respond with 'yes' or 'no'."
                ]

        if self.state == State.AWAITING_BLOCK:
            if message.content.lower() == "yes":
                self.state = State.CONFIRM_SUBMIT
                self.block_user = True
                return [
                    f"Message has been deleted. {self.message_author} is now blocked from sending you messages in the future. Do you want to submit this report? Please respond with 'yes' or 'no'."
                ]
            elif message.content.lower() == "no":
                self.state = State.CONFIRM_SUBMIT
                return [
                    "Message has been deleted. This user will continue to be allowed to send you messages in the future. Do you want to submit this report? Please respond with 'yes' or 'no'."
                ]
            else:
                return [
                    "I'm sorry, I didn't understand that. Please respond with 'yes' or 'no'."
                ]

        if self.state == State.CONFIRM_SUBMIT:
            if message.content.lower() == "yes":
                self.state = State.REPORT_COMPLETE
                if self.imminent_danger:
                    return [
                        "Thank you for your report. It has been submitted. Due to the urgent nature of this case, it has been moved to the front of our priority queue."
                    ]
                else:
                    return [
                        "Thank you for your report, our moderators will review the message shortly."
                    ]
            elif message.content.lower() == "no":
                self.state = State.REPORT_COMPLETE
                return ["Report cancelled."]
            else:
                return [
                    "I'm sorry, I didn't understand that. Please respond with 'yes' or 'no'."
                ]

        # entering moderator flow below!
        if self.state == State.MODERATOR_REVIEW:
            self.state = State.AWAITING_ABUSE_VERIFICATION
            return [
                f"Please review the contents of ths report and decide if this is a safety violation. Respond with 'yes' or 'no'. \n Attached is the flagged message: {self.__dict__}"
            ]

        if self.state == State.AWAITING_ABUSE_VERIFICATION:
            if message.content.lower() == "yes":
                self.state = State.MOD_COMPLETE
                return [
                    "This report is not an abuse violation. No further action is needed."
                ]
            elif message.content.lower() == "no":
                self.state = State.MOD_COMPLETE
                return [
                    "This report is not an abuse violation. No further action is needed."
                ]
            else:
                return [
                    "I'm sorry, I didn't understand that. Please respond with 'yes' or 'no'."
                ]

        if self.state == State.MOD_COMPLETE:
            return ["Thank you for your review."]

        # if self.state == State.REPORT_COMPLETE:
        #     self.report_complete()

        return []

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE

    def mod_complete(self):
        return self.state == State.MOD_COMPLETE
