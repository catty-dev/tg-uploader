import requests
from pyrogram import Client, filters
from pyromod import listen
import os
from configparser import ConfigParser
import sqlite3
from datetime import datetime
import random


config = ConfigParser()
config.read('config.ini')

api_id = config.get('TELEGRAM', 'API_ID')
api_hash = config.get('TELEGRAM', 'API_HASH')
bot_token = config.get('TELEGRAM', 'BOT_TOKEN')
upload_url = config.get('UPLOAD', 'URL')

con = sqlite3.connect("users.db")
cur = con.cursor()
cur.execute("create table if not exists users (userid BIGINT NOT NULL PRIMARY KEY, name TEXT, id INT NOT NULL, token TEXT NOT NULL)")

app = Client(
    "my_bot",
    api_id=api_id, api_hash=api_hash,
    bot_token=bot_token)

supported_types = [".jfif" ,".webp", ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".webm", ".mp3"]
USER_PROPS = ("userid", "name", "id", "token")

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
    param = list(keys) + [id]
    cur.execute(sql, param)
    con.commit()

async def get_user_keys(message):
    id = await message.chat.ask('send me your id')
    if id.text is not None and id.text.isdigit(): token = await message.chat.ask("send me your token")
    else: return await message.reply('invalid input')
    if token.text is None: return await message.reply('invalid input')
    keys=get_user_tg(message)
    keys.extend([id.text, token.text])
    return keys

def get_user_tg(message):
    id = message.from_user.id
    name = message.from_user.first_name
    if message.from_user.last_name is not None: name = message.from_user.first_name + message.from_user.last_name
    return [id, name]

def check_credentials(keys):
    id = keys[-2]
    token = keys[-1]
    url = upload_url
    data={"id": id, "token": token}
    response = requests.post(url, data=data)
    try:
        response.json()['status'] == 'invalid credentials'
        return False
    except: return True

# Function to get user information
@app.on_message(filters.command(["info"]) & filters.private)
async def get_info(app, message):
    if get_user_db(message.from_user.id) is False:
        return await message.reply('not authorized')
    values = get_user_db(message.from_user.id)
    await message.reply(f"telegram id: {str(values[0])} \ntelegram name: {str(values[1])} \nid: {str(values[-2])} \ntoken: {str(values[-1])}")

# Function to update credentials
@app.on_message(filters.command(["update"]) & filters.private)
async def update_credentials(app, message):
    if get_user_db(message.from_user.id) is False:
        return await message.reply('not authorized')
    user_keys = await get_user_keys(message)
    if not isinstance(user_keys, list): return
    if not check_credentials(user_keys): return await message.reply('invalid credentials')
    update_user_db(user_keys)
    await message.reply('credentials updated')

# Function to handle sign up
@app.on_message(filters.text | filters.command(["start"]) & filters.private)
async def handle_sign_up(app, message):
    if not get_user_db(message.from_user.id) is False:
        return await message.reply('send me what you want to upload to xD')
    else:
        user_keys = await get_user_keys(message)
        if not isinstance(user_keys, list): return
        if not check_credentials(user_keys): return await message.reply('invalid credentials')
        create_user_db(user_keys)
        await message.reply('success, you can now send media to upload')

# Function to handle incoming files
@app.on_message(filters.photo | filters.video | filters.animation | filters.sticker | filters.audio | filters.document)
async def handle_document(app, message):
    if get_user_db(message.from_user.id) is False:
        return await message.reply('not authorized')
    else:
        keys = get_user_db(message.from_user.id)
        id = keys[-2]
        token = keys[-1]

    randomnum = str(random.randint(10000, 99999))
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")

    # Get the File object from the message
    if message.photo is not None:
        file_object = message.photo
        file_name = now + randomnum + ".jpg"
    elif message.video is not None:
        file_object = message.video
        file_name = now + randomnum + ".mp4"
    elif message.animation is not None:
        file_object = message.animation
        file_name = now + randomnum + ".mp4"
    elif message.sticker is not None:
        file_object = message.sticker
        if file_object.mime_type == "video/webm":
            file_name = now + randomnum + ".webm"
        elif file_object.mime_type == "image/webp":
            file_name = now + randomnum + ".webp"
        else: return await message.reply('you cant upload this file type')
    elif message.audio is not None:
        file_object = message.audio
        file_name = now + randomnum + ".mp3"
    elif message.document is not None:
        file_object = message.document
        ext=os.path.splitext(file_object.file_name)
        if not ext[-1] in supported_types:
            return await message.reply('you cant upload this file type')
        file_name = now + randomnum + "." + file_object.file_name
    else: return await message.reply('you cant upload this file type')

    if file_object.file_size > 31457280:
        return await message.reply('file too large')

    msg = await message.reply(f"downloading your media...")

    async def progress(current, total):
        await msg.edit_text(f"downloading your media: {current * 100 / total:.1f}%")

    try:
        local_file_path = await app.download_media(message, file_name=file_name, progress=progress)
        await post_it(local_file_path, id, token, msg, file_name)
    except Exception as e: await msg.edit_text("ERROR while processing " + file_name + "\n" + str(e))
    os.remove(local_file_path)

# deliver your shitpost
async def post_it(local_file_path, id, token, msg, file_name):
    url = upload_url
    data={"id": id, "token": token}

    await msg.edit_text(f"uploading to website...")

    with open(local_file_path, 'rb') as fobj:
        response = requests.post(url, data=data, files={'imageupload': fobj})

    try: status = response.json()['status']
    except: return await msg.edit_text("ERROR no response from the server\n[" + file_name + "]")

    if not status == 'upload created':
        return await msg.edit_text("ERROR while uploading: " + status)

    url = response.json()['url']
    await msg.edit_text(f"{status} \n{url}")


app.run()