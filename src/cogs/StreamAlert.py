import dateutil.parser
import discord
import json
import os
import requests
import sys
import traceback
import yaml
from dateutil.tz import tzutc
from discord.ext import commands, tasks

def load_config():
    current_dir = os.path.dirname(__file__)
    config_path = os.path.join(current_dir, '../BotConfig.yml')
    try:
        with open(config_path, 'r', encoding='utf8') as config:
            data = yaml.load(config, Loader=yaml.FullLoader)
    except:
        sys.exit('Error loading config file.  Shutting Down...')
    return data

class StreamAlert(commands.Cog):
    _client_id = None           # Twitch client id
    _client_secret = None       # Twitch client secret
    _access_token = None        # Twitch access token
    _streams = None             # Information on streams we're tracking for stream alert discord notifications
    _log_channel = None         # Channel to log to

    def __init__(self, client):
        self.client = client
        self.stream_alert.start()
        self.renew_access_token.start()
        self.ready = False

    @commands.Cog.listener()
    async def on_ready(self):
        config = load_config()
        self._client_id = config['twitch']['client_id']
        self._client_secret = config['twitch']['client_secret']
        self._streams = config['streams']
        log_channel_id = config['discord']['log_channel_id']
        if log_channel_id:
            self._log_channel = self.client.get_channel(log_channel_id)
            if not self._log_channel:
                await self.log('Could not establish log channel {}'.format(log_channel_id))
        await self.get_access_token()
        await self.log('StreamAlert cog loaded!')
        await self.log('Logged on as {0}!'.format(self.client.user))
        self.ready = True

    @commands.command()
    @commands.has_role("Mod")
    async def enable(self, ctx):
        self.ready = True
        await ctx.send('Stream alerts are enabled!')

    @commands.command()
    @commands.has_role("Mod")
    async def disable(self, ctx):
        self.ready = False
        await ctx.send('Stream alerts are disabled!')
    
    @commands.command()
    @commands.has_role("Mod")
    async def status(self, ctx):
        await ctx.send('Stream alerts is currently {0}.'.format('enabled' if self.ready else 'disabled'))

    @tasks.loop(seconds=30.0)
    async def stream_alert(self):
        if self.ready:
            try:
                start_times = self.get_stream_start_times(self._streams.keys())
                await self.send_alerts(start_times)
            except Exception as ex:
                await self.log('***Error: {0}***'.format(ex))
                await self.log(traceback.format_exc())

    # Renew twitch access token if we get to 30 days
    @tasks.loop(hours=24 * 30)
    async def renew_access_token(self):
        if self.ready:
            await self.get_access_token()

    async def send_alerts(self, start_times):
        for item in start_times:
            streamer = item[0]
            channel_id = self._streams[streamer]['announcement_channel_id']
            channel = self.client.get_channel(channel_id)
            last_alert = await self.get_time_of_last_alert(streamer, channel)
            start_time = dateutil.parser.parse(item[1])
            if last_alert:
                last_alert = last_alert.replace(tzinfo=tzutc())
            if not last_alert or last_alert < start_time:
                am = discord.AllowedMentions(everyone=True)
                alert_msg = self._streams[streamer]['alert_msg']
                await channel.send(alert_msg, allowed_mentions=am)

    async def get_time_of_last_alert(self, streamer, channel):
        channel_id = self._streams[streamer]['announcement_channel_id']
        msg = self._streams[streamer]['alert_msg']
        channel = self.client.get_channel(channel_id)
        msgs = await channel.history(limit=10).flatten()
        for m in msgs:
            if m.content == msg:
                return m.created_at

    def get_stream_start_times(self, ids):
        searchterm = '&user_login='.join(ids)
        url = 'https://api.twitch.tv/helix/streams?user_login={}'.format(
            searchterm)
        headers = {'Client-Id': self._client_id,
                   'Authorization': 'Bearer {}'.format(self._access_token)}
        r = requests.get(url, headers=headers)
        j = json.loads(r.content)
        if len(j['data']) > 0:
            return [(x['user_login'], x['started_at']) for x in j['data']]
        return []

    async def get_access_token(self):
        try:
            r = requests.post('https://id.twitch.tv/oauth2/token?client_id={}&client_secret={}&grant_type=client_credentials'.format(
                self._client_id, self._client_secret))
            j = json.loads(r.content)
            self._access_token = j['access_token']
            await self.log('Access token successfully obtained!')
        except:
            await self.log('Error obtaining access token. Shutting Down...')
            sys.exit('Error obtaining access token')

    async def log(self, log_msg):
        print(log_msg)
        if self._log_channel:
            await self._log_channel.send(log_msg)


def setup(client):
    client.add_cog(StreamAlert(client))
