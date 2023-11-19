import discord
import datetime
import asyncio
from time import time
from json import load, dump

bot = discord.Bot()
polls = {}
prev_roles = {}
"""
Config options:
DEV_MODE: bool - whether the bot is in development mode
DEV_ID: int - the only server the bot will respond to commands in if in development mode
IGNORED_USERS: list - a list of user ids that the bot will not mute
TOKEN: str - the bot's token
VOTES_TO_MUTE: int - the number of votes (yes - no) required to mute a user
TIME_TO_VOTE: int - the number of seconds a poll will last before expiring
"""
try:
    config = load(open("config.json", "r"))
except FileNotFoundError:
    print("config file not found, falling back on default config.")
    config = {
        "DEV_MODE": False,
        "DEV_ID": 999999999999999,
        "IGNORED_USERS": [],
        "TOKEN": "change_me",
        "VOTES_TO_MUTE": 3,
        "TIME_TO_VOTE": 2 * 60,
    }
    dump(config, open("config.json", "w"), indent=4)


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")


async def clean(message: discord.Message):
    await asyncio.sleep(config["TIME_TO_VOTE"])
    if message.id in polls:
        await message.edit(content="Poll completed. Member was not muted.")
        polls.pop(message.id, None)


async def mute_and_remove_roles(reaction: discord.Reaction):
    t = polls[reaction.message.id][0]
    user = polls[reaction.message.id][1]
    duration = datetime.timedelta(minutes=t)
    if user not in prev_roles:
        prev_roles[user] = user.roles
    else:
        prev_roles[user] = prev_roles[user] + user.roles
    await user.edit(roles=[])
    await user.timeout_for(duration)
    await reaction.message.edit(
        content=f"poll completed. mute for {user.mention} ends <t:{int(time())+t*60}:R>."
    )
    polls.pop(reaction.message.id, None)
    await asyncio.sleep(t * 60)
    if user in prev_roles:
        await user.edit(roles=prev_roles[user])
        prev_roles.pop(user, None)
    await reaction.message.edit(content="poll completed. mute over.")


@bot.slash_command(description="call for a vote to mute a user")
async def mute_vote(
    ctx: discord.ApplicationContext,
    member: discord.Option(discord.Member, required=True),
    minutes: discord.Option(int, required=True),
):
    if config["DEV_MODE"] and ctx.guild_id != config["DEV_ID"]:
        await ctx.respond("bot is in development mode", ephemeral=True)
        return
    if minutes <= 0:
        await ctx.respond("cannot mute for less than 1 minute", ephemeral=True)
        return
    if member.id == bot.user.id or member.id in config["IGNORED_USERS"]:
        await ctx.respond("you buffoon, you can't mute that person!", ephemeral=True)
        return
    if member.top_role.position > ctx.guild.get_member(bot.user.id).top_role.position:
        await ctx.respond(
            "cannot mute a user with a higher role than this bot", ephemeral=True
        )
        return
    await ctx.respond(f"ok", ephemeral=True)
    message = await ctx.channel.send(
        f"should {member.mention} be muted for {minutes} minutes? (created by {ctx.author.mention})"
    )
    await message.add_reaction("✅")
    await message.add_reaction("❌")
    polls[message.id] = (minutes, member)
    await clean(message)


@bot.slash_command(description="unmute a muted user")
async def unmute_user(
    ctx: discord.ApplicationContext,
    member: discord.Option(discord.Member, required=True),
):
    if config["DEV_MODE"] and ctx.guild_id != config["DEV_ID"]:
        await ctx.respond("bot is in development mode", ephemeral=True)
        return
    if member not in prev_roles:
        await ctx.respond("the specified user is not muted", ephemeral=True)
    elif ctx.author.id == member.id:
        await ctx.respond("you cannot unmute yourself", ephemeral=True)
    else:
        await ctx.respond("unmuting", ephemeral=True)
        await member.timeout(None)
        await member.edit(roles=prev_roles[member])
        prev_roles.pop(member, None)


async def check_for_vote_end(reaction: discord.Reaction):
    if reaction.message.id in polls:
        # print(reaction.message.reactions)
        yes_count, no_count = None, None
        for r in reaction.message.reactions:
            if r.emoji == "✅":
                yes_count = r.count
            elif r.emoji == "❌":
                no_count = r.count
                if (
                    yes_count is not None
                    and no_count is not None
                    and yes_count - no_count >= config["VOTES_TO_MUTE"]
                ):
                    await mute_and_remove_roles(reaction)


@bot.event
async def on_reaction_add(reaction: discord.Reaction, member: discord.Member):
    await check_for_vote_end(reaction)


@bot.event
async def on_reaction_remove(reaction: discord.Reaction, member: discord.Member):
    await check_for_vote_end(reaction)


bot.run(config["TOKEN"])
