# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
import pymongo
from pymongo import MongoClient
import datetime
from report import Report, State
import pdb
from perspective_api import *
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()
ATLAS_URI = os.getenv("ATLAS_URI")

# Set up logging to the console
logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = "tokens.json"
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    tokens = json.load(f)
    discord_token = tokens["discord"]


class ModBot(discord.Client):
    def __init__(self, group_num=None, guild_id=None):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.group_num = group_num
        self.guild_id = guild_id
        self.mod_channels = {}  # Map from guild to the mod channel id for that guild
        self.reports = {}  # Map from user IDs to the state of their report
        self.curr_report_author = None  # Stores the author of the current report

        # Connect to MongoDB
        self.client = MongoClient(ATLAS_URI)
        self.db = self.client["DiscordBot"]
        self.collection = self.db["usernames"]

    async def on_ready(self):
        print(f"{self.user.name} has connected to Discord! It is these guilds:")
        for guild in self.guilds:
            print(f" - {guild.name}")
        print("Press Ctrl-C to quit.")

        # Parse the group number out of the bot's name
        match = re.search("[gG]roup (\d+) [bB]ot", self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception(
                'Group number not found in bot\'s name. Name format should be "Group # Bot".'
            )

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f"group-{self.group_num}-mod":
                    self.mod_channels[guild.id] = channel

    async def on_message(self, message):
        """
        This function is called whenever a message is sent in a channel that the bot can see (including DMs).
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel.
        """
        # Ignore messages from the bot
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

        mod_channel = self.mod_channels[self.guild_id]
        scores = score_format(eval_text(message.content))

        eval = None
        if (
            scores["scores"]["threat"] > 0.6
            or scores["scores"]["toxicity"] > 0.6
            or scores["scores"]["sexually_explicit"] > 0.6
        ):
            eval = "Alert! This message has been auto-flagged by our system."
            eval += f"\n\nMessage:: {message.content}"
            eval += f"\n\nScores: {scores}"
            await mod_channel.send(eval)
            await self.handle_dm(message, auto_flagged=True)

    async def handle_dm(self, message, auto_flagged=False):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply = "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        mod_channel = self.mod_channels[self.guild_id]
        responses = []

        if not auto_flagged:
            # Only respond to messages if they're part of a reporting flow
            if author_id not in self.reports and not message.content.startswith(
                Report.START_KEYWORD
            ):
                return

            # If we don't currently have an active report for this user, add one
            if author_id not in self.reports:
                self.reports[author_id] = Report(self)

            # Let the report class handle this message; forward all the messages it returns to us
            responses = await self.reports[author_id].handle_message(message)
            for r in responses:
                await message.channel.send(r)

            # If the report is complete or cancelled, remove it from our map
            if self.reports[author_id].report_complete():
                self.curr_report_author = author_id
                # Forward the report to the mod channel
                await mod_channel.send(f"Report Submitted.")

                # Handle moderator review
                self.reports[author_id].state = State.MODERATOR_REVIEW
                responses = await self.reports[author_id].handle_message(message)
                for r in responses:
                    await mod_channel.send(r)
        else:
            if author_id not in self.reports:
                self.reports[author_id] = Report(self)
            self.curr_report_author = author_id
            self.reports[author_id].state = State.AUTO_FLAGGED
            responses = await self.reports[author_id].handle_message(message)
            for r in responses:
                await mod_channel.send(r)

    async def handle_channel_message(self, message):
        # Moderator review flow
        if message.channel.name == f"group-{self.group_num}-mod":
            mod_channel = self.mod_channels[message.guild.id]
            responses = await self.reports[self.curr_report_author].handle_message(
                message
            )
            print("Message: ", message)
            print("Responses: ", responses)
            report_count = self.get_report_count(
                self.reports[self.curr_report_author].message_author_id
            )
            if report_count > 0:
                await mod_channel.send(
                    f"This user has been previously reported {report_count} times for malicious behavior."
                )
            for r in responses:
                await mod_channel.send(r)

            if self.reports[self.curr_report_author].mod_complete():
                await mod_channel.send("Thank you for your review.")
                if self.reports[self.curr_report_author].virtual_kidnapping:
                    if not self.reports[self.curr_report_author].fake:
                        await self.reports[self.curr_report_author].author_channel.send(
                            "We have detected the user's messages to be malicious and have quarantined them. Our model has flagged the contents of their messages as potentially real. Please exercise caution and contact your local law enforcement."
                        )
                    else:
                        await self.reports[self.curr_report_author].author_channel.send(
                            "We have detected the user's messages to be malicious and have quarantined them. Our model has flagged the contents of their messages as AI-generated. Although the threat is likely false, please exercise caution and contact your local law enforcement."
                        )
                self.save_report(
                    self.curr_report_author, self.reports[self.curr_report_author]
                )
                self.reports.pop(self.curr_report_author)
            return

        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f"group-{self.group_num}":
            return

    def get_report_count(self, user_id):
        # Query the database to check if the user ID exists
        report_count = self.collection.count_documents({"reported_user_id": user_id})
        return report_count

    def save_report(self, reporter_user_id, report):
        report_data = {
            "reporter_user_id": reporter_user_id,
            "reported_user_id": report.message_author_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc),
        }
        self.collection.insert_one(report_data)
        print("Report saved to database")


client = ModBot(group_num=27, guild_id=1211760623969370122)
client.run(discord_token)
