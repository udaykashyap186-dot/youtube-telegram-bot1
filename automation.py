import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from apscheduler.schedulers.background import BackgroundScheduler

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


BOT_TOKEN = "8646140424:AAEchMJ94H8aK7kZ6HSRffDgKvKPwoF7SLI"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

scheduler = BackgroundScheduler()
scheduler.start()

sessions = {}

# ---------------- YOUTUBE AUTH ---------------- #

def youtube_auth():

    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


youtube = youtube_auth()

# ---------------- COMMANDS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = """
🚀 *YouTube Shorts Upload Bot*

Commands:

/upload – Upload a new Short
/cancel – Cancel current upload

Steps:
1️⃣ Send video
2️⃣ Send title
3️⃣ Send description
4️⃣ Send schedule time

Format:
`YYYY-MM-DD HH:MM`
"""

    await update.message.reply_text(msg, parse_mode="Markdown")


async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):

    sessions[update.message.chat_id] = {}

    await update.message.reply_text(
        "📤 Send the video you want to upload."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    sessions.pop(update.message.chat_id, None)

    await update.message.reply_text("❌ Upload cancelled.")


# ---------------- VIDEO ---------------- #

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat = update.message.chat_id

    if chat not in sessions:
        return

    file = await update.message.video.get_file()

    os.makedirs("videos", exist_ok=True)

    path = f"videos/{file.file_id}.mp4"

    await file.download_to_drive(path)

    sessions[chat]["video"] = path

    await update.message.reply_text("📝 Send the video title.")


# ---------------- TEXT HANDLER ---------------- #

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat = update.message.chat_id

    if chat not in sessions:
        return

    session = sessions[chat]

    text = update.message.text

    if "title" not in session:

        session["title"] = text

        await update.message.reply_text("📄 Send video description.")

        return


    if "description" not in session:

        session["description"] = text

        await update.message.reply_text(
            "⏰ Send schedule time\nExample:\n2026-03-10 18:30"
        )

        return


    if "time" not in session:

        try:

            run_time = datetime.strptime(text, "%Y-%m-%d %H:%M")

        except:

            await update.message.reply_text(
                "❌ Invalid time format."
            )

            return

        session["time"] = run_time

        scheduler.add_job(
            upload_video,
            "date",
            run_date=run_time,
            args=[
                session["video"],
                session["title"],
                session["description"]
            ]
        )

        await update.message.reply_text(
            "✅ Video scheduled successfully!"
        )

        sessions.pop(chat)


# ---------------- UPLOAD FUNCTION ---------------- #

def upload_video(video_path, title, description):

    request = youtube.videos().insert(

        part="snippet,status",

        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["shorts"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public"
            }
        },

        media_body=MediaFileUpload(video_path)

    )

    response = request.execute()

    print("Uploaded Video ID:", response["id"])


# ---------------- MAIN ---------------- #

def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upload", upload))
    app.add_handler(CommandHandler("cancel", cancel))

    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.TEXT, handle_text))

    print("Bot Running...")

    app.run_polling()


if __name__ == "__main__":
    main()
