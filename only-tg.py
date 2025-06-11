from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired, MessageIdInvalid, PeerIdInvalid
import time
import json
import os

# Your API credentials
api_id = 28442198
api_hash = "c713058e2c450270587dad1b09b3c80c"

# Channel IDs from your channel list
source_channel = -1001709896616  # Sahej Wallpaper
target_channel = -1002645515061  # Scrap channel

# Log file to track forwarded messages
LOG_FILE = "forwarded_messages.json"

# Initialize the client with your existing session
app = Client("forward_session", api_id=api_id, api_hash=api_hash)

def load_forwarded_log():
    """Load the log of already forwarded messages"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return set(json.load(f))
        except (json.JSONDecodeError, FileNotFoundError):
            return set()
    return set()

def save_forwarded_log(forwarded_ids):
    """Save the log of forwarded messages"""
    with open(LOG_FILE, 'w') as f:
        json.dump(list(forwarded_ids), f)

def is_image_media(msg):
    """Check if message contains image files only"""
    return bool(msg.photo or
                (msg.document and msg.document.mime_type and
                 msg.document.mime_type.startswith('image/')))

def check_channels():
    """Check if we can access both channels"""
    with app:
        try:
            me = app.get_me()
            print(f"Logged in as: {me.first_name} (@{me.username if me.username else 'No username'})")

            print("\nChecking channel access...")

            # Check source channel
            try:
                source_chat = app.get_chat(source_channel)
                print(f"✓ Source channel accessible: {source_chat.title}")
            except PeerIdInvalid:
                print(f"✗ Cannot access source channel ID: {source_channel}")
                print("  Make sure you're a member of this channel")
                return False
            except Exception as e:
                print(f"✗ Error accessing source channel: {e}")
                return False

            # Check target channel
            try:
                target_chat = app.get_chat(target_channel)
                print(f"✓ Target channel accessible: {target_chat.title}")

                # Check if we have admin rights to send messages
                try:
                    app.send_message(target_channel, "Test message - will be deleted")
                    # Delete the test message immediately
                    messages = app.get_chat_history(target_channel, limit=1)
                    for msg in messages:
                        if msg.text == "Test message - will be deleted":
                            app.delete_messages(target_channel, msg.id)
                            break
                    print("✓ Can send messages to target channel")
                except Exception as e:
                    print(f"⚠ Warning: May not have permission to send messages: {e}")

            except PeerIdInvalid:
                print(f"✗ Cannot access target channel ID: {target_channel}")
                print("  Make sure you're a member of this channel")
                return False
            except Exception as e:
                print(f"✗ Error accessing target channel: {e}")
                return False

            return True
        except Exception as e:
            print(f"Error during channel check: {e}")
            return False

def forward_files():
    """Main function to forward image files from source to target channel"""
    with app:
        try:
            # Load previously forwarded messages log
            forwarded_log = load_forwarded_log()

            forwarded_count = 0
            failed_count = 0
            skipped_count = 0

            print(f"\nLoaded log: {len(forwarded_log)} previously forwarded messages")
            print("Starting to forward image files...")

            # Get messages from source channel (increased limit for more files)
            for msg in app.get_chat_history(source_channel, limit=500):
                if msg.id in forwarded_log:
                    skipped_count += 1
                    continue

                if is_image_media(msg):
                    try:
                        # Copy the message instead of forwarding to avoid showing source
                        if msg.photo:
                            # For photos
                            app.send_photo(
                                chat_id=target_channel,
                                photo=msg.photo.file_id,
                                caption="by @lox_wall"
                            )
                        elif msg.document and msg.document.mime_type.startswith('image/'):
                            # For image documents
                            app.send_document(
                                chat_id=target_channel,
                                document=msg.document.file_id,
                                caption="by @lox_wall"
                            )

                        forwarded_count += 1
                        forwarded_log.add(msg.id)

                        media_type = "photo" if msg.photo else "image document"
                        print(f"✓ Sent {media_type} (ID: {msg.id}) - Total: {forwarded_count}")

                        # Save log periodically (every 10 messages)
                        if forwarded_count % 10 == 0:
                            save_forwarded_log(forwarded_log)

                        # Add delay to avoid flood limits
                        time.sleep(3)

                    except FloodWait as e:
                        print(f"⚠ Flood wait: sleeping for {e.value} seconds...")
                        time.sleep(e.value)
                        # Retry sending after flood wait
                        try:
                            if msg.photo:
                                app.send_photo(
                                    chat_id=target_channel,
                                    photo=msg.photo.file_id,
                                    caption="by @lox_wall"
                                )
                            elif msg.document and msg.document.mime_type.startswith('image/'):
                                app.send_document(
                                    chat_id=target_channel,
                                    document=msg.document.file_id,
                                    caption="by @lox_wall"
                                )

                            forwarded_count += 1
                            forwarded_log.add(msg.id)
                            print(f"✓ Sent message {msg.id} after flood wait")
                        except Exception as retry_error:
                            failed_count += 1
                            print(f"✗ Failed to send message {msg.id} after retry: {retry_error}")

                    except ChatAdminRequired:
                        failed_count += 1
                        print(f"✗ Admin rights required to send message {msg.id}")

                    except Exception as e:
                        failed_count += 1
                        print(f"✗ Failed to send message {msg.id}: {str(e)}")

                else:
                    # Skip non-image messages
                    continue

            # Save final log
            save_forwarded_log(forwarded_log)

            print(f"\n📊 Summary:")
            print(f"Successfully sent: {forwarded_count} image files")
            print(f"Failed: {failed_count} files")
            print(f"Skipped (already processed): {skipped_count} files")
            print("Task completed!")

        except Exception as e:
            print(f"An error occurred: {e}")
            # Save log even if there's an error
            save_forwarded_log(forwarded_log)

def monitor_and_forward():
    """Monitor source channel and forward new image files in real-time"""
    with app:
        me = app.get_me()
        print(f"Logged in as: {me.first_name}")
        print("Monitoring for new image files... (Press Ctrl+C to stop)")

        # Load previously forwarded messages log
        forwarded_log = load_forwarded_log()

        try:
            while True:
                # Check for new messages
                for msg in app.get_chat_history(source_channel, limit=10):
                    if msg.id not in forwarded_log and is_image_media(msg):
                        try:
                            if msg.photo:
                                app.send_photo(
                                    chat_id=target_channel,
                                    photo=msg.photo.file_id,
                                    caption="by @lox_wall"
                                )
                            elif msg.document and msg.document.mime_type.startswith('image/'):
                                app.send_document(
                                    chat_id=target_channel,
                                    document=msg.document.file_id,
                                    caption="by @lox_wall"
                                )

                            forwarded_log.add(msg.id)
                            save_forwarded_log(forwarded_log)
                            print(f"✓ Auto-sent new image file (ID: {msg.id})")

                        except Exception as e:
                            print(f"✗ Failed to send new message {msg.id}: {e}")

                # Wait before checking again
                time.sleep(30)  # Check every 30 seconds

        except KeyboardInterrupt:
            print("\nStopping monitor...")
            save_forwarded_log(forwarded_log)
        except Exception as e:
            print(f"Monitor error: {e}")
            save_forwarded_log(forwarded_log)
            time.sleep(60)  # Wait 1 minute before retrying

if __name__ == "__main__":
    print("Telegram Image File Forwarder")
    print("=" * 35)

    # First, check if we can access both channels
    if not check_channels():
        print("\n❌ Cannot proceed - channel access issues detected!")
        print("\nPossible solutions:")
        print("1. Join both channels if you haven't already")
        print("2. Verify the channel IDs are correct")
        print("3. Make sure the channels are public or you have proper access")
        print("4. Ensure you have permission to send messages in the target channel")
        exit(1)

    # Choose mode
    mode = input("\nChoose mode:\n1. Forward recent image files (default)\n2. Monitor and auto-forward new image files\nEnter choice (1 or 2): ").strip()

    if mode == "2":
        print("\nStarting real-time monitoring mode...")
        monitor_and_forward()
    else:
        print("\nStarting batch forward mode...")
        forward_files()
