import os
import sqlite3
from datetime import datetime
from pytz import timezone

from telegram import Update
from telegram.ext import (
ApplicationBuilder,
CommandHandler,
MessageHandler,
ConversationHandler,
filters,
ContextTypes
)

from apscheduler.schedulers.background import BackgroundScheduler

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


BOT_TOKEN = "8646140424:AAEchMJ94H8aK7kZ6HSRffDgKvKPwoF7SLI"

VIDEO, TITLE, DESCRIPTION, TIME = range(4)

# DATABASE
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS videos(
id INTEGER PRIMARY KEY AUTOINCREMENT,
file TEXT,
title TEXT,
description TEXT,
time TEXT,
uploaded INTEGER DEFAULT 0
)
""")

conn.commit()

# SCHEDULER
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
scheduler.start()


# YOUTUBE AUTH
def youtube_service():
    creds = Credentials.from_authorized_user_file("token.json")
    return build("youtube", "v3", credentials=creds)


# UPLOAD FUNCTION
async def upload_video(context):

    data = context.job.data

    file = data["file"]
    title = data["title"]
    description = data["description"]
    chat_id = data["chat"]

    yt = youtube_service()

    request = yt.videos().insert(
        part="snippet,status",
        body={
            "snippet":{
                "title":title,
                "description":description,
                "categoryId":"22"
            },
            "status":{
                "privacyStatus":"public"
            }
        },
        media_body=MediaFileUpload(file)
    )

    response = request.execute()

    video_id = response["id"]

    link = f"https://youtube.com/watch?v={video_id}"

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ Video Uploaded\n\n{link}"
    )


# START
async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
    "🎬 YouTube Automation Bot\n\n"
    "Commands:\n"
    "/upload → upload new short\n"
    "/queue → view scheduled videos"
    )


# QUEUE
async def queue(update:Update, context:ContextTypes.DEFAULT_TYPE):

    cursor.execute("SELECT title,time FROM videos WHERE uploaded=0")

    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Queue empty")
        return

    msg="Scheduled Videos\n\n"

    for r in rows:
        msg+=f"{r[0]} — {r[1]}\n"

    await update.message.reply_text(msg)


# START UPLOAD
async def upload(update:Update, context:ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text("📹 Send video")

    return VIDEO


# RECEIVE VIDEO
async def get_video(update:Update, context:ContextTypes.DEFAULT_TYPE):

    video = update.message.video

    file = await video.get_file()

    path=f"videos/{video.file_id}.mp4"

    await file.download_to_drive(path)

    context.user_data["file"]=path

    await update.message.reply_text("✏️ Enter title")

    return TITLE


# TITLE
async def get_title(update:Update, context:ContextTypes.DEFAULT_TYPE):

    context.user_data["title"]=update.message.text

    await update.message.reply_text("📝 Enter description")

    return DESCRIPTION


# DESCRIPTION
async def get_description(update:Update, context:ContextTypes.DEFAULT_TYPE):

    context.user_data["description"]=update.message.text

    await update.message.reply_text(
    "⏰ Enter time\n\nExample:\n2026-03-08 21:30"
    )

    return TIME


# TIME
async def get_time(update:Update, context:ContextTypes.DEFAULT_TYPE):

    schedule_time=update.message.text

    file=context.user_data["file"]
    title=context.user_data["title"]
    description=context.user_data["description"]

    cursor.execute(
    "INSERT INTO videos(file,title,description,time) VALUES(?,?,?,?)",
    (file,title,description,schedule_time)
    )

    conn.commit()

    run_time=datetime.strptime(schedule_time,"%Y-%m-%d %H:%M")

    scheduler.add_job(
    upload_video,
    "date",
    run_date=run_time,
    data={
        "file":file,
        "title":title,
        "description":description,
        "chat":update.effective_chat.id
    }
    )

    await update.message.reply_text(
    f"✅ Video Scheduled\n\n{schedule_time}"
    )

    return ConversationHandler.END

# Time Vailadation


# MAIN
def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv=ConversationHandler(

    entry_points=[CommandHandler("upload",upload)],

    states={

    VIDEO:[MessageHandler(filters.VIDEO,get_video)],

    TITLE:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_title)],

    DESCRIPTION:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_description)],

    TIME:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_time)]

    },

    fallbacks=[]
    )

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("queue",queue))
    app.add_handler(conv)

    print("🚀 Bot Running")

    app.run_polling(drop_pending_updates=True)


if __name__=="__main__":
    main()
