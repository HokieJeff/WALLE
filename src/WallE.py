import os
import discord
import sys
import yaml
from discord.ext import commands
from typing import NamedTuple

class DiscordConfig(NamedTuple):
    token: str
    logging_channel_id: int

def load_config():
    current_dir = os.path.dirname(__file__)
    config_path = os.path.join(current_dir, 'BotConfig.yml')
    try:
        with open(config_path, 'r', encoding='utf8') as config:
            data = yaml.load(config, Loader=yaml.FullLoader)
    except:
        sys.exit('Error loading config file.  Shutting Down...')
    return data

config = load_config()
dc = config['discord']
discord_conf = DiscordConfig(dc['token'], dc['log_channel_id'])

intents = discord.Intents.default()  # Allow the use of custom intents
intents.members = True

client = commands.Bot(command_prefix = '.', intents = intents)

client.load_extension('cogs.StreamAlert')

@client.event
async def on_ready():
    print('Bot initialized!')

client.run(discord_conf.token, bot=True)



