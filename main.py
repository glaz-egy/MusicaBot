# -*- coding: utf-8 -*-

from configparser import ConfigParser
from datetime import datetime, date
from argparse import ArgumentParser
from random import random, randint, choice
from youtube_dl import YoutubeDL
from copy import deepcopy
import discord
import hashlib
import asyncio
import pickle
import sys
import os

class LogControl:
    def __init__(self, FileName):
        self.Name = FileName

    async def Log(self, WriteText, write_type='a'):
        with open(self.Name, write_type, encoding='utf-8',) as f:
            f.write(datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')+'[Bot Log] '+WriteText+'\n')

    async def ErrorLog(self, WriteText, write_type='a'):
        with open(self.Name, write_type, encoding='utf-8') as f:
            f.write(datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')+'[Error Log] '+WriteText+'\n')

    async def MusicLog(self, WriteText, write_type='a'):
        with open(self.Name, write_type, encoding='utf-8') as f:
            f.write(datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')+'[Music Log] '+WriteText+'\n')

class VoiceEntry:
    def __init__(self, message, player):
        self.requester = message.author
        self.channel = message.channel
        self.player = player

    def __str__(self):
        fmt = '{} uploaded by {}: `{}`'.format(self.player.title, self.player.uploader, self.player.url)
        return fmt

class VoiceState:
    def __init__(self, bot):
        self.current = None
        self.voice = None
        self.bot = bot
        self.play_next_song = asyncio.Event()
        self.songs = asyncio.Queue()
        self.skip_votes = set() # a set of user_ids that voted
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    def is_playing(self):
        if self.voice is None or self.current is None:
            return False
        player = self.current.player
        return not player.is_done()

    @property
    def player(self):
        return self.current.player

    def skip(self):
        self.skip_votes.clear()
        if self.is_playing():
            self.player.stop()

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.songs.get()
            await NextSet(MusicMessage)
            if TitleFlag: await self.bot.send_message(self.current.channel, 'Now playing **{}**'.format(self.current))
            self.current.player.start()
            await self.play_next_song.wait()

class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, server):
        state = self.voice_states.get(server.id)
        if state is None:
            state = VoiceState(self.bot)
            self.voice_states[server.id] = state

        return state

    async def play(self, message, *, song : str):
        state = self.get_voice_state(message.server)
        opts = {'default_search': 'auto',
                'quiet': True,}

        if state.voice is None:
            voice_channel = message.author.voice_channel
            if voice_channel is None:
                await self.bot.send_message(message.channel, 'ボイスチャネルに入ってないじゃん!')
                await log.ErrorLog('User not in voice channel')
                return False
            state.voice = await self.bot.join_voice_channel(voice_channel)

        try:
            player = await state.voice.create_ytdl_player(song, ytdl_options=opts, after=state.toggle_next)
        except Exception as e:
            fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
            await self.bot.send_message(message.channel, fmt.format(type(e).__name__, e))
            await NextSet(MusicMessage)
        else:
            player.volume = 0.3
            entry = VoiceEntry(message, player)
            await log.MusicLog('{}: {}'.format(player.title, player.url))
            await state.songs.put(entry)

    async def pause(self, message):
        state = self.get_voice_state(message.server)
        if state.is_playing():
            player = state.player
            player.pause()

    async def resume(self, message):
        state = self.get_voice_state(message.server)
        if state.is_playing():
            player = state.player
            player.resume()

    async def stop(self, message):
        server = message.server
        state = self.get_voice_state(server)

        if state.current.player.is_playing():
            player = state.current.player
            player.stop()

        try:
            state.audio_player.cancel()
            del self.voice_states[server.id]
            await state.voice.disconnect()
        except:
            pass

    async def skip(self, message):
        state = self.get_voice_state(message.server)
        if not state.is_playing():
            await self.bot.send_message(message.channel, 'Not playing any music right now...')
            return

        state.skip()

def SavePlaylist(PLdata, FileName='playlist.plf'):
    with open(FileName, 'wb') as f:
        pickle.dump(PLdata, f)

def LoadPlaylist(FileName='playlist.plf'):
    with open(FileName, 'rb') as f:
        PLdata = pickle.load(f)
    return PLdata

def ArgsInit():
    parser = ArgumentParser(description='Playlist, log and config set args')
    parser.add_argument('--playlist', default='playlist.plf')
    parser.add_argument('--log', default='bot.log')
    parser.add_argument('--config', default='config.ini')
    return parser.parse_args()

PlayListFiles = {}
MusicMessage = None
player = None
PlayListName = []
NextList = []
RandomFlag = False
PauseFlag = False
PlayFlag = False
IbotFlag = False
TitleFlag = True
version = '''MusinaBot versioin: 0.0.1
A subset of PlatinaBot version: 2.3.5
Copyright (c) 2019 Glaz egy.'''
args = ArgsInit()
log = LogControl(args.log)
config = ConfigParser()
if os.path.isfile(args.config): config.read(args.config, encoding='utf-8')
else:
    log.ErrorLog('Config file not exist')
    sys.exit(1)
prefix = config['BOTDATA']['cmdprefix']
with open('help.dat', 'rb') as f:
    Data = pickle.load(f)
    CommandDict = Data['JP']
if os.path.isfile(args.playlist): PlayListFiles = LoadPlaylist(FileName=args.playlist)
else:
    PlayListFiles['default'] = {}
    SavePlaylist(PlayListFiles, FileName=args.playlist)
    PlayListFiles = LoadPlaylist(FileName=args.playlist)
NowPlayList = 'default'
PlayURLs = list(PlayListFiles[NowPlayList].keys())

client = discord.Client()

TrueORFalse = {'Enable': True,
                'Disable': False}

async def NextSet(message):
    global NowPlayList
    global player
    global PlayURLs
    if not RandomFlag: NowPlay = 0
    else:
        if not len(PlayURLs) == 0: NowPlay = randint(0, len(PlayURLs)-1)
        else: NowPlay = 0
    song = PlayURLs[NowPlay]
    await player.play(message, song=('https://www.youtube.com/watch?v='+ song if not 'http' in song else song))
    await log.MusicLog('Set {}'.format(PlayURLs[NowPlay]))
    PlayURLs.remove(PlayURLs[NowPlay])
    if len(PlayURLs) == 0:
        PlayURLs = list(PlayListFiles[NowPlayList].keys())

async def ListOut(message, all=False, List=False):
    global NowPlayList
    OutFlag = False
    if all:
        await log.Log('Play list check all')
        URLs = [[]]
        keys = []
        for key, value in PlayListFiles.items():
            OutFlag = False
            URLs[-1].append('')
            keys.append(key)
            if key == NowPlayList: keys[-1] += '(Now playlist)'
            if not len(value) == 0:
                for url, title in value.items():
                    if title is None: title = YoutubeDL().extract_info(url=url, download=False, process=False)['title']
                    url = 'https://www.youtube.com/watch?v='+ url if not 'http' in url else url
                    URLs[-1][-1] += '-'+title+'\n'+url+'\n'
                    if len(URLs[-1][-1]) > 750:
                        OutFlag = True
                        await EmbedOut(message.channel, 'All playlist: page{}'.format(len(URLs[-1])), keys[-1], URLs[-1][-1], 0x6b8e23)
                        URLs[-1].append('')
            if not OutFlag or URLs[-1][-1] != '':
                await EmbedOut(message.channel, 'All playlist: page{}'.format(len(URLs[-1])), keys[-1], URLs[-1][-1], 0x6b8e23)
    elif List:
        Keys = ['']
        for key in PlayListFiles.keys():
            if key == NowPlayList: Keys[-1] += key+'(Now playlist)\n'
            else: Keys[-1] += key+'\n'
            if len(Keys[-1]) > 750:
                OutFlag = True
                await EmbedOut(message.channel, 'Playlist List: page{}'.format(len(Keys)), 'Playlists', Keys[-1], 0x6a5acd)
                Keys.append('')
        if not OutFlag or Keys[-1] != '':
            await EmbedOut(message.channel, 'Playlist List: page{}'.format(len(Keys)), 'Playlists', Keys[-1], 0x6a5acd)
    else:
        await log.Log('Call playlist is {}'.format(PlayListFiles[NowPlayList]))
        URLs = ['']
        if not len(PlayListFiles[NowPlayList]) == 0:
            for url, title in PlayListFiles[NowPlayList].items():
                if title is None: title = YoutubeDL().extract_info(url=url, download=False, process=False)['title']
                url = 'https://www.youtube.com/watch?v='+ url if not 'http' in url else url
                URLs[-1] += '-'+title+'\n'+url+'\n'
                if len(URLs[-1]) > 750:
                    OutFlag = True
                    await EmbedOut(message.channel, 'Now playlist: page{}'.format(len(URLs)), NowPlayList, URLs[-1], 0x708090)
                    URLs.append('')
        if not OutFlag or URLs[-1] != '':
            await EmbedOut(message.channel, 'Now playlist: page{}'.format(len(URLs)), NowPlayList, URLs[-1], 0x708090)

async def EmbedOut(channel, disc, playname, url, color):
    embed = discord.Embed(description=disc, colour=color)
    embed.add_field(name=playname, value=url if url != '' else 'Empty', inline=True)
    await client.send_message(channel, embed=embed)

async def PermissionErrorFunc(message):
    await client.send_message(message.channel, 'このコマンドは君じゃ使えないんだよなぁ')
    await log.ErrorLog('Do not have permissions')

def CmdSpliter(cmd, index, sufIndex=False):
    Flag = True
    if '"' in cmd[index]:
        tempStr = cmd[index]
        while Flag:
            index += 1
            tempStr += ' ' + cmd[index]
            if '"' in cmd[index]: break
        SplitStr = tempStr.replace('"', '').strip()
    else: SplitStr = cmd[index]
    if sufIndex: return SplitStr, index
    else: return SplitStr

async def OptionError(message, cmd):
    if len(cmd) > 1:
        await client.send_message(message.channel, 'オプションが間違っている気がするなぁ')
        await log.ErrorLog('The option is incorrect error')
        return
    await client.send_message(message.channel, '`'+cmd[0]+'`だけじゃ何したいのか分からないんだけど')
    await log.ErrorLog('no option error') 

async def NotArgsment(message):
    await client.send_message(message.channel, 'オプションに引数が無いよ！')
    await log.ErrorLog('Not argment')

@client.event
async def on_ready():
    await log.Log('Bot is Logging in!!')

@client.event
async def on_message(message):
    global MusicMessage, player
    global NowPlayList, PlayURLs, RandomFlag
    global PauseFlag, PlayFlag, IbotFlag, TitleFlag
    if message.content.startswith(prefix+'music'):
        urlUseFlag = False
        cmdFlag = False
        cmd = message.content.split()
        if '--list' in cmd:
            await ListOut(message)
            return
        if '--list-all' in cmd:
            await ListOut(message, all=True)
            return
        if '--list-list' in cmd:
            await ListOut(message, List=True)
            return
        if '--list-change' in cmd:
            temp = NowPlayList
            try:
                NowPlayList = cmd[cmd.index('--list-change')+1]
            except:
                NowPlayList = 'default'
            try:
                PlayURLs = list(PlayListFiles[NowPlayList].keys())
                await client.send_message(message.channel, 'プレイリストが{}から{}へ変更されました'.format(temp, NowPlayList))
                await log.MusicLog('Play list change {} to {}'.format(temp, NowPlayList))
            except:
                await client.send_message(message.channel, 'そのプレイリストは存在しません')
                await log.ErrorLog('Request not exist Play list ')
                NowPlayList = temp
            return
        if '--list-make' in cmd:
            try:
                PlayListName = cmd[cmd.index('--list-make')+1]
            except:
                await NotArgsment(message)
                return
            if PlayListName in PlayListFiles.keys():
                await client.send_message(message.channel, 'そのプレイリストはすでに存在します')
                await log.ErrorLog('Make request exist play list')
            else:
                PlayListFiles[PlayListName] = {}
                SavePlaylist(PlayListFiles, FileName=args.playlist)
                NowPlayList = PlayListName
                PlayURLs = list(PlayListFiles[NowPlayList].keys())
                await client.send_message(message.channel, '新しくプレイリストが作成されました')
                await log.MusicLog('Make play list {}'.format(PlayListName))
            return
        if '--list-delete' in cmd:
            try:
                PlayListName = cmd[cmd.index('--list-delete')+1]
            except:
                await NotArgsment(message)
                return
            if PlayListName in PlayListFiles.keys() and not 'default' == PlayListName:
                del PlayListFiles[PlayListName]
                SavePlaylist(PlayListFiles, FileName=args.playlist)
                await client.send_message(message.channel, '{}を削除します'.format(PlayListName))
                await log.MusicLog('Remove play list {}'.format(PlayListName))
                if NowPlayList == PlayListName:
                    NowPlayList = 'default'
                    PlayURLs = list(PlayListFiles[NowPlayList].keys())
            else:
                await client.send_message(message.channel, 'そのプレイリストは存在しません')
                await log.ErrorLog('Delete request not exist play list')
            return
        if '--list-rename' in cmd:
            try:
                prePlayListName = cmd[cmd.index('--list-rename')+1]
                sufPlayListName = cmd[cmd.index('--list-rename')+2]
            except:
                await NotArgsment(message)
                return
            if sufPlayListName in PlayListFiles.keys() and not 'default' == prePlayListName:
                await client.send_message(message.channel, 'そのプレイリストはすでに存在します')
                await log.ErrorLog('Make request exist play list')
            elif prePlayListName in PlayListFiles.keys() and not 'default' == prePlayListName:
                PlayListFiles[sufPlayListName] = deepcopy(PlayListFiles[prePlayListName])
                if NowPlayList == prePlayListName: NowPlayList = sufPlayListName
                del PlayListFiles[prePlayListName]
                SavePlaylist(PlayListFiles, FileName=args.playlist)
                PlayURLs = list(PlayListFiles[NowPlayList].keys())
                await client.send_message(message.channel, '{}の名前を{}に変更します'.format(prePlayListName, sufPlayListName))
                await log.MusicLog('Rename play list {}'.format(prePlayListName))
            elif 'default' == prePlayListName:
                await client.send_message(message.channel, 'defaultを変更することは出来ません')
                await log.ErrorLog('Cannot renaem default')
            else:
                await client.send_message(message.channel, 'そのプレイリストは存在しません')
                await log.ErrorLog('Rename request not exist play list')
            return
        if '--list-clear' in cmd:
            try:
                ClearPlaylist = cmd[cmd.index('--list-clear')+1]
            except:
                await NotArgsment(message)
            if ClearPlaylist in PlayListFiles.keys():
                PlayListFiles[ClearPlaylist] = {}
                await client.send_message(message.channel, '{}をクリアしました'.format(ClearPlaylist))
                await log.MusicLog('Cleared {}'.format(ClearPlaylist))
                SavePlaylist(PlayListFiles, FileName=args.playlist)
                PlayURLs = list(PlayListFiles[NowPlayList].keys())
            else:
                await client.send_message(message.channel, 'そのプレイリストは存在しません')
                await log.ErrorLog('Clear request not exist play list')
            return
        if '--list-clear-all' in cmd:
            for key in PlayListFiles.keys():
                PlayListFiles[key] = {}
                await client.send_message(message.channel, '{}をクリアしました'.format(key))
                await log.MusicLog('Cleared {}'.format(key))
            SavePlaylist(PlayListFiles, FileName=args.playlist)
            return
        if len(cmd) >= 2:
            for cmdpar in cmd:
                if '$' in cmdpar:
                    urlUseFlag = True
                    url = cmdpar.replace('$', '')
        MusicMessage = message
        if '--play' in cmd:
            RandomFlag = False
            TitleFlag = True
            if '-r' in cmd: RandomFlag = True
            if PauseFlag: await player.resume(message)
            else:
                if len(PlayURLs) >= 1: music = randint(0, len(PlayURLs)-1)
                elif len(PlayURLs) == 0: music = 0
                else:
                    await client.send_message(message.channle, 'プレイリストに曲が入ってないよ！')
                    await log.ErrorLog('Not music in playlist')
                    return
                try:
                    player = MusicPlayer(client)
                    song = PlayURLs[music if RandomFlag else 0] if not urlUseFlag else url
                    await player.play(message, song=('https://www.youtube.com/watch?v='+ song if not 'http' in song else song))
                    if not urlUseFlag: PlayURLs.remove(PlayURLs[music if RandomFlag else 0])
                    if len(PlayURLs) == 0: PlayURLs = list(PlayListFiles[NowPlayList].keys())
                    PlayFlag = True
                    await client.change_presence(game=discord.Game(name='MusicPlayer'))
                except discord.errors.InvalidArgument:
                    pass
                except discord.ClientException:
                    await log.ErrorLog('Already Music playing')
                    await client.send_message(message.channel, 'Already Music playing')
            cmdFlag = True
        if '-r' in cmd:
            RandomFlag = True
            cmdFlag = True
        if '-n' in cmd:
            RandomFlag = False
            cmdFlag = True
        if '--no-out' in cmd:
            TitleFlag = False
            cmdFlag = True
        if '--next' in cmd:
            await log.MusicLog('Music skip')
            await player.skip(message)
            cmdFlag = True
        if '--stop' in cmd:
            if player is None:
                await client.send_message(message.channel, '今、プレイヤーは再生してないよ！')
                await log.ErrorLog('Not play music')
                return
            await client.change_presence(game=(None if not IbotFlag else discord.Game(name='IBOT')))
            await log.MusicLog('Music stop')
            await player.stop(message)
            PlayFlag = False
            player = None
            PlayURLs = list(PlayListFiles[NowPlayList].keys())
            cmdFlag = True
        if '--pause' in cmd:
            await log.MusicLog('Music pause')
            await player.pause(message)
            PauseFlag = True
            cmdFlag = True
        if not cmdFlag: await OptionError(message, cmd)
    elif message.content.startswith(prefix+'addmusic'):
        NotFound = True
        links = message.content.split()[1:]
        if links[0] in PlayListFiles.keys():
            ListName = links[0]
            links.remove(links[0])
        else: ListName = NowPlayList
        ineed = ['']
        for link in links:
            linkraw = deepcopy(link)
            link = link.replace('https://www.youtube.com/watch?v=', '')
            link = link.replace('https://youtu.be/', '')
            if not link in PlayListFiles[ListName]:
                try:
                    PlayListFiles[ListName][link] = YoutubeDL().extract_info(url=link, download=False, process=False)['title']
                    PlayURLs.append(link)
                    await log.MusicLog('Add {}'.format(link))
                    ineed[-1] += '-{}\n'.format(PlayListFiles[ListName][link])
                    NotFound = False
                    if len(ineed[-1]) > 750:
                        await EmbedOut(message.channel, 'Wish List page {}'.format(len(ineed)), 'Music', ineed[-1], 0x303030)
                        ineed.append('')
                        NotFound = True
                except:
                    await client.send_message(message.channel, '{} なんて無いよ'.format(linkraw))
                    await log.ErrorLog('{} is Not Found'.format(linkraw))
            else:
                await log.MusicLog('Music Overlap {}'.format(link))
                await client.send_message(message.channel, 'その曲もう入ってない？')
        SavePlaylist(PlayListFiles, FileName=args.playlist)
        if not ineed[-1] == '' and not NotFound: await EmbedOut(message.channel, 'Wish List page {}'.format(len(ineed)), 'Music', ineed[-1], 0x303030)
    elif message.content.startswith(prefix+'delmusic'):
        NotFound = True
        links = message.content.split()[1:]
        if links[0] in PlayListFiles.keys():
            ListName = links[0]
            links.remove(links[0])
        else: ListName = NowPlayList
        notneed = ['']
        for link in links:
            link = link.replace('https://www.youtube.com/watch?v=', '')
            link = link.replace('youtube.com/watch?v=', '')
            link = link.replace('https://youtu.be/', '')
            try:
                print(link)
                Title = PlayListFiles[ListName][link]
                del PlayListFiles[ListName][link]
                try:
                    PlayURLs.remove(link)
                except:
                    pass
                NotFound = False
                notneed[-1] += '-{}\n'.format(Title)
                await log.MusicLog('Del {}'.format(link))
                if len(notneed[-1]) > 750:
                    await EmbedOut(message.channel, 'Delete List page {}'.format(len(notneed)), 'Music', notneed[-1], 0x749812)
                    notneed.append('')
                    NotFound = True
            except:
                await log.ErrorLog('{} not exist list'.format(link))
                await client.send_message(message.channel, 'そんな曲入ってたかな？')
        SavePlaylist(PlayListFiles, FileName=args.playlist)
        if not notneed[-1] == '' and not NotFound: await EmbedOut(message.channel, 'Delete List page {}'.format(len(notneed)), 'Music', notneed[-1], 0x749812)
        if len(PlayURLs) == 0: PlayURLs = list(PlayListFiles[NowPlayList].keys())
    elif message.content.startswith(prefix+'help'):
        cmds = message.content.split()
        if len(cmds) > 1:
            for cmd in cmds:
                if cmd == 'role' or cmd == 'music' or cmd == 'spell' or cmd == 'study':
                    cmdline = ''
                    for key, value in CommandDict[cmd].items():
                        cmdline += key + ': ' + value + '\n'
                    embed = discord.Embed(description=cmd+' Commmand List', colour=0x008b8b)
                    embed.add_field(name='Commands', value=cmdline, inline=True)
                    await client.send_message(message.channel, embed=embed)
        else:
            cmdline = ''
            for key, value in CommandDict['help'].items():
                cmdline += key + ': ' + value + '\n'
            embed = discord.Embed(description='Commmand List', colour=0x4169e1)
            embed.add_field(name='Commands', value=cmdline, inline=True)
            await client.send_message(message.channel, embed=embed)
    elif message.content.startswith(prefix+'exit'):
        AdminCheck = (message.author.id == config['ADMINDATA']['botowner'] if config['ADMINDATA']['botowner'] != 'None' else False)
        if TrueORFalse[config['ADMINDATA']['passuse']] and not AdminCheck:
            HashWord = hashlib.sha256(message.content.split()[1].encode('utf-8')).hexdigest()
            AdminCheck = (HashWord == config['ADMINDATA']['passhash'] if config['ADMINDATA']['passhash'] != 'None' else False)
        if AdminCheck:
            await log.Log('Bot exit')
            await client.close()
            await sys.exit(0)
        else:
            PermissionErrorFunc(message)
    elif message.content.startswith(prefix+'version'):
        await log.Log(version)
        await client.send_message(message.channel, version)
    elif message.content.startswith(prefix+'debug'):
        await client.send_message(message.channel, client.email)
    elif message.content.startswith(prefix+'description'):
        await client.send_message(message.channel, 'MusinaBotはPlatinaBotの機能を縮小し、MusicBot機能のみを残したBotです\nPlatinaBot: https://github.com/glaz-egy/PlatinaBot')
    elif message.content.startswith(prefix):
        await client.send_message(message.channel, '該当するコマンドがありません')
        await log.ErrorLog('Command is notfound')

@client.event
async def on_member_join(member):
    if TrueORFalse[config['JOINCONF']['joinevent']]:
        jointexts = config['JOINCONF']['jointext'].replace('\n', '')
        jointexts = jointexts.split('@/')
        text = jointexts[randint(0, len(jointexts)-1)].strip()
        channel = client.get_channel(config['BOTDATA']['mainch'])
        readme = client.get_channel(config['BOTDATA']['readmech'])
        if channel is None or readme is None: return
        text = text.replace('[MenberName]', member.name)
        text = text.replace('[ChannelName]', readme.name)
        await client.send_message(channel, text)
    await log.Log('Join {}'.format(member.name))
    print('Join {}'.format(member.name))

client.run(config['BOTDATA']['token'])
