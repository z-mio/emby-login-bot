# -*- coding: UTF-8 -*-
import datetime
import json
import logging
import os
import sqlite3

import pyrogram
import pytz
import requests
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pyrogram import Client, filters
from pyrogram.types import BotCommand

scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Shanghai'))
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s: %(message)s',
    level=logging.INFO
)


def get_config(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def write_config(path, modified_config):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(modified_config, f, allow_unicode=True)


##################################################
config = get_config("config.yaml")
# bot配置
admin = config['user']['admin']
bot_token = config['user']['bot_token']
api_id = config['user']['api_id']
api_hash = config['user']['api_hash']
# 其他配置
intervals = config['scraping_task']['intervals']
chat = config['scraping_task']['chat_id']
bf_time = config['backup_database']['time']
# proxy
scheme = config['proxy']['scheme']
hostname = config['proxy']['hostname']
port = config['proxy']['port']
proxy = {
    "scheme": scheme,  # 支持“socks4”、“socks5”和“http”
    "hostname": hostname,
    "port": port
}

##################################################
# emby
emby_url = config['emby']['emby_url'].removesuffix('/')
XEmbyToken = config['emby']['XEmbyToken']
##################################################
if os.path.exists('my_bot.session'):
    app = (
        Client("my_bot", proxy=proxy)
        if scheme and hostname and port
        else Client("my_bot")
    )
elif scheme and hostname and port:
    app = Client(
        "my_bot", proxy=proxy,
        api_id=api_id, api_hash=api_hash,
        bot_token=bot_token)
else:
    app = Client(
        "my_bot",
        api_id=api_id, api_hash=api_hash,
        bot_token=bot_token)

##################################################

connection = sqlite3.connect('emby.db')
cc = connection.cursor()
cc.execute('''create table if not exists userinfo
          (chat_id           int    primary key  not null,
           emby_user_id      text                not null,
           emby_user_name    text                not null,
           datecreated       text                not null,
           tg_user_name      text                not null);''')

connection.close()


##################################################

# 设置菜单
@app.on_message(filters.command('menu') & filters.private)
async def menu(_, message):
    # 私聊可见
    a_bot_menu = [BotCommand(command="start", description="开始"),
                  BotCommand(command="zc", description="注册账号"),
                  BotCommand(command="cz", description="重置密码"),
                  BotCommand(command="info", description="账号信息"),
                  BotCommand(command="delete", description="注销账号"),
                  BotCommand(command="help", description="帮助"),
                  ]

    # 管理员私聊可见
    admin_bot_menu = [BotCommand(command="cz", description="重置密码"),
                      BotCommand(command="info", description="账号信息"),
                      BotCommand(command="i", description="查询账号信息"),
                      BotCommand(command="delete", description="删除账号"),
                      BotCommand(command="bf", description="备份数据库"),
                      ]
    # 群聊可见
    b_bot_menu = [BotCommand(command="zi", description="吱~"),
                  ]
    await app.delete_bot_commands()
    await app.set_bot_commands(a_bot_menu, scope=pyrogram.types.BotCommandScopeAllPrivateChats())
    await app.set_bot_commands(admin_bot_menu, scope=pyrogram.types.BotCommandScopeChat(chat_id=admin))
    await app.set_bot_commands(b_bot_menu)
    await app.send_message(chat_id=message.chat.id, text="菜单设置成功，请退出聊天界面重新进入来刷新菜单")


# 开始
@app.on_message(filters.command('start') & filters.private)
async def start(_, message):
    text = '''
注册账号：/zc+Emby用户名
重置密码：/cz+Emby用户名
账号信息：/info
注销账号：/delete+Emby用户名
'''
    await app.send_message(chat_id=message.chat.id, text=text)


# 帮助
@app.on_message(filters.command('help') & filters.private)
async def _help(_, message):
    await app.send_message(chat_id=message.chat.id, text="有问题请联系管理员")


# 吱一声
@app.on_message(filters.command('zi'))
async def zi(_, message):
    await app.send_message(chat_id=message.chat.id, text="吱~")


# 注册
@app.on_message(filters.command('zc') & filters.private)
async def register(_, message):
    if username := ' '.join(message.command[1:]):
        with Database('emby.db') as a:
            result = a.execute(f"select * from userinfo where chat_id = {message.chat.id}").fetchone()
        # 查询telegram用户id，判断是否已注册
        if result is None:
            r = registered(username)
            datecreated = get_registration_time(r)
            # 用户名已存在
            if 'A user with the name' not in r.text:
                registered_json = json.loads(r.text)  # 注册
                uid = registered_json['Id']
                edit_permissions(uid)  # 修改权限
                text = f'''
Emby用户名：<code>{username}</code>
——————
cf优选线路：
主机名：https://cf.zi0.icu/
测速地址： https://speed.cloudflare.com/
端口：443
——————
法国直连线路：
主机名：https://zby.zi0.icu/
端口：443
——————
默认无密码，直接输入账号登录，然后自行设置密码
建议使用客户端播放，客户端下载：<a href="https://download.misakaf.org/Emby">Emby客户端</a>
其他教程：<a href="https://wiki.misakaf.org/#/">Wiki</a>
'''

                tg_username = f"@{message.from_user.username}"
                # 将用户信息写入数据库
                with Database('emby.db') as a:
                    a.execute(f'''
                    insert into userinfo (chat_id, emby_user_id, emby_user_name, datecreated, tg_user_name) 
                    values ({message.chat.id}, '{uid}', '{username}', '{datecreated}', '{tg_username}')''')

                await app.send_message(chat_id=message.chat.id, text=text, disable_web_page_preview=True)
            else:
                await app.send_message(chat_id=message.chat.id, text="用户名已存在")
        else:
            await app.send_message(chat_id=message.chat.id, text=f"您已注册过账号，请勿重复注册\nEmby用户名：{result[2]}")
    else:
        await app.send_message(chat_id=message.chat.id, text="请加上用户名 例：<code>/zc abc</code>")


# 重置密码
@app.on_message(filters.command('cz') & filters.private)
async def reset_password(_, message):
    if username := ' '.join(message.command[1:]):
        with Database('emby.db') as a:
            result = a.execute(f"select * from userinfo where  emby_user_name = '{username}'").fetchone()
        if result:
            if result[0] == message.chat.id or message.chat.id == admin:
                rep = reset_emby_password(result[1])
                if rep.status_code == 204:
                    await app.send_message(chat_id=message.chat.id, text="重置成功，默认无密码")
                else:
                    await app.send_message(chat_id=message.chat.id, text=f"重置失败：{rep}")
            else:
                await app.send_message(chat_id=message.chat.id,
                                       text="请使用注册时的tg账号重置密码，有问题请联系管理员 /help ")
        else:
            await app.send_message(chat_id=message.chat.id, text="用户名不存在")
    else:
        await app.send_message(chat_id=message.chat.id, text="请加上用户名 例：<code>/cz abc</code>")


# 用户信息
@app.on_message(filters.command('info') & filters.private)
async def user_info(_, message):
    with Database('emby.db') as a:
        result = a.execute(f"select * from userinfo where  chat_id = {message.chat.id}").fetchone()
    if result:
        u = json.loads(get_user(result[1]).text)
        text = f'''Emby用户名：<code>{result[2]}</code>

注册时间：{result[3] or u['DateCreated']}

账号状态：{'🔴禁用' if u['Policy']['IsDisabled'] else '🟢正常'}

cf优选线路：
-主机名：https://cf.zi0.icu/
-端口：443
——————
法国直连线路：
-主机名：https://zby.zi0.icu/
-端口：443'''
        await app.send_message(chat_id=message.chat.id, text=text, disable_web_page_preview=True)
    else:
        await app.send_message(chat_id=message.chat.id, text='您还未注册账号')


# 查询用户信息
@app.on_message(filters.command('i') & filters.private)
async def admin_user_info(_, message):
    if message.chat.id != admin:
        return
    username = message.command[1]
    with Database('emby.db') as a:
        result = a.execute(f"select * from userinfo where  emby_user_name = '{username}'").fetchone()
    if result:
        uu = get_user(result[1])
        u = json.loads(uu.text)
        datecreated = get_registration_time(uu)
        text = f'''Emby用户名：<code>{username}</code>
tg用户名：<code>{result[0]}</code> | {result[4]}
注册时间：{result[3] or datecreated}
账号状态：{'🔴禁用' if u['Policy']['IsDisabled'] else '🟢正常'}
管理用户：<a href="{emby_url}/web/index.html#!/users/user?userId={result[1]}">点击跳转</a>
'''
        await app.send_message(chat_id=message.chat.id, text=text, disable_web_page_preview=True)
    else:
        await app.send_message(chat_id=message.chat.id, text='用户不存在')


# 删除账号
@app.on_message(filters.command('delete') & filters.private)
async def user_info(_, message):
    if username := ' '.join(message.command[1:]):
        if message.chat.id != admin:
            with Database('emby.db') as a:
                result = a.execute(f"select * from userinfo where  chat_id = {message.chat.id}").fetchone()
        else:
            with Database('emby.db') as a:
                result = a.execute(f"select * from userinfo where  emby_user_name = '{username}'").fetchone()
        if username == result[2]:
            d = deletes_user(result[1])
            with Database('emby.db') as a:
                a.execute(f"delete from userinfo where emby_user_name = '{username}'")
            if not d.text:
                await app.send_message(chat_id=message.chat.id, text='注销成功')
            elif d.text == 'User not found':
                await app.send_message(chat_id=message.chat.id, text='用户不存在')
            else:
                await app.send_message(chat_id=message.chat.id, text=f'错误，请联系管理员！\n---\n{d.text}')
        else:
            await app.send_message(chat_id=message.chat.id, text='用户名不正确')
    else:
        await app.send_message(chat_id=message.chat.id, text="请加上用户名 例：<code>/delete abc</code>")


#################################################################


# 刮削进度推送
async def task():
    g = get_scheduledtask('6330ee8fb4a957f33981f89aa78b030f')
    g = json.loads(g.text)
    if g['State'] == 'Running':
        try:
            await app.send_message(chat_id=chat, text=f"刮削进度：{g['CurrentProgressPercentage']}")
        except Exception as a:
            logging.error(a)


# 备份数据库
@app.on_message(filters.command('bf') & filters.private)
async def backup_database(_, message):
    if message.chat.id == admin:
        await app.send_document(
            chat_id=admin, document='emby.db', caption='#用户信息备份'
        )


# 备份数据库
async def bd():
    await app.send_document(
        chat_id=admin, document='emby.db', caption='#用户信息定时备份'
    )


# 定时任务
def timed_task():
    if chat and intervals:
        scheduler.add_job(task, 'interval', minutes=int(intervals))
    if bf_time:
        scheduler.add_job(bd, trigger=CronTrigger.from_crontab(bf_time))

    scheduler.start()


#################################################################
# 开关数据库
class Database:
    def __init__(self, db_path):
        self.db_path = db_path

    def __enter__(self):
        self.connection = sqlite3.connect(self.db_path)
        return self.connection.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.commit()
        self.connection.close()


# 获取注册时间
def get_registration_time(r):
    # 将时间字符串转换为 datetime 对象
    time_str = json.loads(r.text)['DateCreated'].split('.')[0]
    time_obj = datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S")
    # 将 UTC 时间转换为本地时间
    local_tz = datetime.timezone(datetime.timedelta(hours=8))  # 设置时区为上海
    local_time = time_obj.replace(tzinfo=datetime.timezone.utc).astimezone(local_tz)
    return local_time.strftime("%Y-%m-%d %H:%M:%S")


#################################################################
# 注册
def registered(name):
    url = f'{emby_url}/Users/New'
    header = {"X-Emby-Token": XEmbyToken}
    body = {"Name": name}
    return requests.post(url, json=body, headers=header, timeout=10)


# 修改权限
def edit_permissions(user_id):
    url = f'{emby_url}/Users/{user_id}/Policy'
    header = {"X-Emby-Token": XEmbyToken}
    body = {
        "IsAdministrator": False,
        "IsHidden": True,
        "IsHiddenRemotely": True,
        "IsDisabled": False,
        "EnableRemoteControlOfOtherUsers": False,
        "EnableSharedDeviceControl": False,
        "EnableRemoteAccess": True,
        "EnableLiveTvManagement": False,
        "EnableLiveTvAccess": True,
        "EnableMediaPlayback": True,
        "EnableAudioPlaybackTranscoding": False,
        "EnableVideoPlaybackTranscoding": False,
        "EnablePlaybackRemuxing": True,
        "EnableContentDeletion": False,
        "EnableContentDownloading": False,
        "EnableSubtitleDownloading": False,
        "EnableSubtitleManagement": False,
        "EnableSyncTranscoding": False,
        "EnableMediaConversion": False,
        "EnableAllDevices": True,
        "SimultaneousStreamLimit": 3
    }
    return requests.post(url, json=body, headers=header, timeout=10)


# 重置密码
def reset_emby_password(user_id):
    url = f"{emby_url}/Users/{user_id}/Password"
    header = {"X-Emby-Token": XEmbyToken}
    body = {"ResetPassword": True}
    return requests.post(url, json=body, headers=header, timeout=10)


# 通过id获取用户信息
def get_user(user_id):
    url = f'{emby_url}/Users/{user_id}'
    header = {"X-Emby-Token": XEmbyToken}
    return requests.get(url, headers=header, timeout=10)


# 删除账号
def deletes_user(user_id):
    url = f'{emby_url}/Users/{user_id}'
    header = {"X-Emby-Token": XEmbyToken}
    return requests.delete(url, headers=header, timeout=10)


# 获取定时任务
def get_scheduledtask(task_id):
    url = f'{emby_url}/ScheduledTasks/{task_id}'
    header = {"X-Emby-Token": XEmbyToken}
    return requests.get(url, headers=header, timeout=10)


if __name__ == '__main__':
    timed_task()
    app.run()
