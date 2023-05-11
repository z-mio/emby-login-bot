# emby-login-bot

``` yaml
user:
  admin: 123456789 # 管理员用户id,可通过@get_id_bot获取id
  api_hash: 
  # api_id、api_hash在 https://my.telegram.org/apps 获取
  api_id: 
  bot_token:  # bot的api token，从 @BotFather 获取
proxy: # 支持“socks4”、“socks5”和“http”，不填则为关闭，海外服务器为空即可
  hostname: 127.0.0.1
  port: 7890
  scheme: http
emby:
  emby_url: http://127.0.0.1:8096 # emby地址
  XEmbyToken: # emby token
scraping_task: # 定时推送刮削进度，为空则不不开启
  chat_id: # 群组/频道/用户的id
  intervals: 30 # 间隔时间，默认为30分钟推送一次
backup_database: # 定时备份数据库
  time: '0 3 * * *' # 格式为5位cron表达式
```
