import requests
from pyrogram import Client, filters
from pyromod import listen
import os
from datetime import datetime
from configparser import ConfigParser
import sqlite3

config = ConfigParser()
config.read('config.ini')

api_id = config.get('TELEGRAM', 'API_ID')
api_hash = config.get('TELEGRAM', 'API_HASH')
bot_token = config.get('TELEGRAM', 'BOT_TOKEN')
upload_url = config.get('UPLOAD', 'URL')

con = sqlite3.connect("users.db")
cur = con.cursor()
cur.execute("create table if not exists users (userid BIGINT NOT NULL PRIMARY KEY, username TEXT, realname TEXT, id INT NOT NULL, token TEXT NOT NULL)")

app = Client(
    "my_bot",
    api_id=api_id, api_hash=api_hash,
    bot_token=bot_token)

now = datetime.now().strftime("%Y%m%d%H%M%S%f")
supported_types = [".jfif" ,".webp", ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".webm", ".mp3"]
USER_PROPS = ("userid", "username", "realname", "id", "token")

def get_user_db(id):
    sql = "SELECT * FROM users WHERE userid = ?"
    param = id
    cur.execute(sql, (param, ))
    row = cur.fetchone()
    if row is None:
        return False
    return row

def create_user_db(keys):
    sql = "INSERT INTO users("
    sql += ", ".join("`%s`" % k for k in USER_PROPS)
    sql += ") VALUES ("
    sql += ", ".join("?" for i in range(len(USER_PROPS)))
    sql += ")"
    param = list(keys)
    cur.execute(sql, param)
    con.commit()

def update_user_db(keys):
    id = keys[0]
    sql = "UPDATE users SET "
    sql += ", ".join("`%s` = ?" % k for k in USER_PROPS)
    sql += " WHERE userid = ?"
    param = list(keys) + [id, ]
    cur.execute(sql, param)
    con.commit()

async def get_user_keys(message):
    id = await message.chat.ask('send me your id')
    if id.text.isdigit(): token = await message.chat.ask("send me your token")
    else: return await message.reply('invalid input')
    keys=get_user_tg(message)
    keys.extend([id.text, token.text])
    return keys

def get_user_tg(message):
    id = message.from_user.id
    username = message.from_user.username if message.from_user.username is not None else None
    realname = message.from_user.first_name
    if message.from_user.last_name is not None: realname = message.from_user.first_name + message.from_user.last_name
    return [id, username, realname]

# Function to get user information
@app.on_message(filters.command(["info"]) & filters.private)
async def handle_document(app, message):
    if get_user_db(message.from_user.id) == False:
        return await message.reply('not authorized')
    else: values = get_user_db(message.from_user.id)
    return await message.reply(f"telegram id: {str(values[0])} \nname: {str(values[2])} \nid: {str(values[-2])} \ntoken: {str(values[-1])}")

# Function to update credentials
@app.on_message(filters.command(["update"]) & filters.private)
async def update_credentials(app, message):
    if get_user_db(message.from_user.id) == False:
        return await message.reply('not authorized')
    else: update_user_db(await get_user_keys(message))
    return await message.reply('credentials updated')

# Function to handle sign up
@app.on_message(filters.text | filters.command(["start"]) & filters.private)
async def handle_sign_up(app, message):
    if not get_user_db(message.from_user.id) == False:
        return await message.reply('send me what you want to upload to xD')
    else:
        create_user_db(await get_user_keys(message))
        return await message.reply('success, you can now send media to upload')

# Function to handle incoming files
@app.on_message(filters.photo | filters.video | filters.animation | filters.sticker | filters.audio | filters.document)
async def handle_document(app, message):
    if get_user_db(message.from_user.id) == False:
        return await message.reply('not authorized')
    else: values = get_user_db(message.from_user.id)
    id = values[-2]
    token = values [-1]

    # Get the File object from the message
    if message.photo is not None:
        file_object = message.photo
    elif message.video is not None:
        file_object = message.video
    elif message.animation is not None:
        file_object = message.animation
    elif message.sticker is not None:
        file_object = message.sticker
    elif message.audio is not None:
        file_object = message.audio
    elif message.document is not None:
        file_object = message.document
        ext=os.path.splitext(file_object.file_name)
        if not ext[-1] in supported_types:
            return await message.reply('you cant upload this file type')
    else: return await message.reply('you cant upload this file type')

    if file_object.file_size > 3e+7:
        return await message.reply('file too large')

    local_file_path = await app.download_media(message)

    try: await post_it(local_file_path, message, id, token)
    except Exception as e: await message.reply("ERROR: " + e)
    return os.remove(local_file_path)

# deliver your shitpost
async def post_it(local_file_path, message, id, token):
    url = upload_url
    data={"id": id, "token": token}

    with open(local_file_path, 'rb') as fobj:
        response = requests.post(url, data=data, files={'imageupload': fobj})

    status = response.json()['status']
    if not status == 'upload created':
        return await message.reply("ERROR: " + status)

    url = response.json()['url']
    await message.reply(f"{status} \n{url}")

app.run()