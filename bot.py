import os
import shutil
import time
import random
import string
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS, MAX_FILE_SIZE, WORK_DIR, OUTPUT_DIR
from obfuscator import APKObfuscator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Client("apk_obfuscator_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "🔥 **APK Obfuscator Bot**\n\n"
        "Send me an APK file and I'll obfuscate it!\n"
        "Features:\n"
        "- ProGuard Obfuscation\n"
        "- String Encryption\n"
        "- Anti-Debug Protection\n"
        "- Control Flow Obfuscation\n\n"
        "Commands:\n"
        "/start - Show this\n"
        "/help - More info\n"
        "/info - Get APK info\n"
        "/protect - Full protection\n"
        "/encrypt - Encrypt DEX"
    )

@app.on_message(filters.command("help"))
async def help_cmd(client, message):
    await message.reply_text(
        "📖 **Help**\n\n"
        "Send any APK file directly.\n"
        "Bot will obfuscate and return protected APK.\n\n"
        "Commands:\n"
        "/info <file> - Show APK details\n"
        "/obfuscate <file> - Obfuscate only\n"
        "/protect <file> - Full protection\n"
        "/encrypt <file> - Encrypt resources\n\n"
        "Max file size: 50 MB"
    )

@app.on_message(filters.command("info") & filters.reply)
async def info_cmd(client, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply_text("❌ Reply to an APK file")
        return
    file_path = await message.reply_to_message.download()
    try:
        from androguard.core.bytecodes.apk import APK
        apk = APK(file_path)
        info = (
            f"📦 **APK Info**\n\n"
            f"Package: `{apk.get_package()}`\n"
            f"Version: {apk.get_androidversion_name()} ({apk.get_androidversion_code()})\n"
            f"Min SDK: {apk.get_min_sdk_version()}\n"
            f"Target SDK: {apk.get_target_sdk_version()}\n"
            f"Permissions: {len(apk.get_permissions())}\n"
            f"Size: {os.path.getsize(file_path) / 1024 / 1024:.2f} MB"
        )
        await message.reply_text(info)
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
    finally:
        os.remove(file_path)

@app.on_message(filters.document & filters.private)
async def handle_apk(client, message):
    if message.document.file_name.endswith('.apk'):
        if message.document.file_size > MAX_FILE_SIZE:
            await message.reply_text("❌ File too large. Max 50 MB.")
            return

        msg = await message.reply_text("⏳ Downloading APK...")
        file_path = await message.download(file_name=f"{WORK_DIR}/{message.document.file_name}")

        await msg.edit_text("⏳ Obfuscating APK...")
        output_name = f"obfuscated_{int(time.time())}_{''.join(random.choices(string.ascii_lowercase, k=6))}.apk"
        output_path = os.path.join(OUTPUT_DIR, output_name)

        try:
            obf = APKObfuscator(file_path, output_path)
            obf.run()

            await msg.edit_text("✅ Uploading protected APK...")
            await client.send_document(
                message.chat.id,
                output_path,
                caption="🔥 **Protected APK Ready!**\n\nObfuscated + Encrypted + Anti-Debug",
                force_document=True
            )
            await msg.delete()
        except Exception as e:
            logger.error(f"Error: {e}")
            await msg.edit_text(f"❌ Error: {str(e)}")
        finally:
            os.remove(file_path)
            if os.path.exists(output_path):
                os.remove(output_path)

@app.on_message(filters.command("protect") & filters.reply)
async def protect_cmd(client, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply_text("❌ Reply to an APK file")
        return
    await handle_apk(client, message.reply_to_message)

@app.on_message(filters.command("obfuscate") & filters.reply)
async def obfuscate_cmd(client, message):
    await handle_apk(client, message.reply_to_message)

@app.on_message(filters.command("encrypt") & filters.reply)
async def encrypt_cmd(client, message):
    await handle_apk(client, message.reply_to_message)

if __name__ == "__main__":
    logger.info("🔥 Bot Started!")
    app.run()
