from beginner.cog import Cog
from beginner.logging import create_logger
from beginner.scheduler import schedule
from beginner.tags import tag
from datetime import datetime, timedelta
import asyncio
import discord
import re


class Bumping(Cog):
    @Cog.listener()
    async def on_ready(self):
        self.role = self.get_role("bumpers")
        self.channel = self.get_channel("bumping")
        self.explanation_message = await self.get_explanation_message()
        self.logger.debug("Cog ready")

    @Cog.listener()
    async def on_message(self, message):
        if message.channel != self.channel:
            return

        if self.is_bump_success_confirmation(message):
            self.schedule_bump(timedelta(hours=2))

        elif self.is_bump_fail_confirmation(message):
            self.schedule_bump(
                timedelta(minutes=self.get_failed_next_bump_timer(message))
            )

        author = message.author
        if author.id != self.server.me.id:
            await self.clean_up_messages()

        if not author.bot:
            await self.channel.send(
                f"{author.mention} please wait for the next bump reminder",
                delete_after=10,
            )

    def schedule_bump(self, next_bump):
        return schedule(
            "bump-reminder", next_bump, self.bump_reminder, no_duplication=True
        )

    def is_bump_success_confirmation(self, message):
        if len(message.embeds) == 0:
            return False

        if message.author.id != 302050872383242240:  # If not disboard bot
            return False

        return "Bump done" in message.embeds[0].description

    def is_bump_fail_confirmation(self, message):
        if len(message.embeds) == 0:
            return False

        if message.author.id != 302050872383242240:  # If not disboard bot
            return False

        return "Please wait" in message.embeds[0].description

    def get_failed_next_bump_timer(self, message):
        return int(re.findall(r"\d+", message.embeds[0].description)[-1])

    @tag("schedule", "disboard-bump-reminder")
    async def bump_reminder(self):
        self.logger.debug(f"SENDING BUMP REMINDER: {self.role.name}")
        message = await self.channel.send(
            f"{self.role.mention} It's been 2hrs since the last bump!"
            f"Use the command `!d bump` now!"
        )

    @Cog.listener()
    async def on_raw_reaction_add(self, reaction):
        if reaction.emoji.name != "🔔":
            return

        if reaction.message_id != self.explanation_message.id:
            return

        member = self.server.get_member(reaction.user_id)
        if member.bot:
            return

        if self.role not in member.roles:
            await self.add_bumper_role(member)

    @Cog.listener()
    async def on_raw_reaction_remove(self, reaction):
        if reaction.emoji.name != "🔔":
            return

        if reaction.message_id != self.explanation_message.id:
            return

        member = self.server.get_member(reaction.user_id)
        if member.bot:
            return

        if self.role in member.roles:
            await self.remove_bumper_role(member)

    async def add_bumper_role(self, member):
        await member.add_roles(self.role)
        await self.channel.send(
            f"{member.mention} you will be tagged by bump reminders", delete_after=10
        )

    async def clean_up_messages(self):
        messages = self.channel.history(
            after=self.explanation_message, oldest_first=False
        )
        message_pools = {"failure": [], "success": [], "deleting": []}
        last_status = "deleting"
        async for message in messages:
            use_pool = "deleting"
            if message.content == "!d bump":
                use_pool = last_status
                last_status = "deleting"
            elif self.is_bump_success_confirmation(message):
                use_pool = last_status = "success"
            elif self.is_bump_fail_confirmation(message):
                use_pool = last_status = "failure"

            if (datetime.utcnow() - message.created_at).days < 7:
                message_pools[use_pool].append(message)

        delete = message_pools["deleting"]
        if len(message_pools["success"]) >= 2:
            delete.extend(message_pools["failure"])
            delete.extend(message_pools["success"][2:])

        elif len(message_pools["failure"]) >= 2:
            delete.extend(message_pools["failure"][2:])
            delete.extend(message_pools["success"])

        else:
            delete.extend(message_pools["failure"])
            delete.extend(message_pools["success"])

        await self.channel.delete_messages(delete)

    async def create_explanation_message(self):
        message = await self.channel.send(
            embed=discord.Embed(
                description=(
                    f"To help us stay at the top of Disboard join the *Bump Squad* by reacting with the 🔔, "
                    f"react again to leave the squad"
                ),
                color=0x306998,
            ).set_author(name="Beginner.py Bump Squad", icon_url=self.server.icon_url)
        )
        await message.add_reaction("🔔")
        return message

    async def get_explanation_message(self):
        messages = await self.channel.history(oldest_first=True, limit=1).flatten()
        if len(messages) == 0:
            return await self.create_explanation_message()
        return messages[0]

    async def remove_bumper_role(self, member):
        await member.remove_roles(self.role)
        await self.channel.send(
            f"{member.mention} you will no longer be tagged by bump reminders",
            delete_after=10,
        )


def setup(client):
    client.add_cog(Bumping(client))
