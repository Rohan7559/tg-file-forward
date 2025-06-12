from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired, MessageIdInvalid, PeerIdInvalid
import time
import json
import os
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.auth.transport.requests import Request
import pickle
import tempfile
import sys

# Your API credentials
api_id = 28442198
api_hash = "c713058e2c450270587dad1b09b3c80c"

# Channel IDs from your channel list
source_channel = -1001709896616  # Sahej Wallpaper
target_channel = -1002779159453  # Scrap wallpaper

# Alternative: Try using channel usernames instead of IDs
# source_channel = "@sahej_wallpaper"  # Replace with actual username
# target_channel = "@scrap_wallpaper"  # Replace with actual username

# Google Drive folder ID
GDRIVE_FOLDER_ID = "1uEjjIWbF-vaZO26nvpJeX2iqv78qS_Yp"

# Log file to track forwarded messages and counter
LOG_FILE = "forwarded_messages.json"
COUNTER_FILE = "wall_counter.json"

# Initialize the client with your existing session
app = Client("forward_session", api_id=api_id, api_hash=api_hash)

def load_wall_counter():
    """Load the current wall counter"""
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, 'r') as f:
                return json.load(f).get('counter', 1)
        except (json.JSONDecodeError, FileNotFoundError):
            return 1
    return 1

def save_wall_counter(counter):
    """Save the current wall counter"""
    with open(COUNTER_FILE, 'w') as f:
        json.dump({'counter': counter}, f)

def get_next_wall_caption():
    """Get the next wall caption with incremented counter"""
    counter = load_wall_counter()
    caption = f"Wall {counter} by @lox_wall"
    save_wall_counter(counter + 1)
    return caption

def get_channel_info(channel_id):
    """Get detailed channel information and suggest fixes"""
    with app:
        try:
            chat = app.get_chat(channel_id)
            print(f"✓ Channel found: {chat.title}")
            print(f"  Type: {chat.type}")
            print(f"  ID: {chat.id}")
            if hasattr(chat, 'username') and chat.username:
                print(f"  Username: @{chat.username}")
            print(f"  Members count: {getattr(chat, 'members_count', 'Unknown')}")
            return chat
        except PeerIdInvalid:
            print(f"✗ Peer ID invalid for: {channel_id}")
            return None
        except Exception as e:
            print(f"✗ Error getting channel info: {e}")
            return None

def fix_channel_access():
    """Interactive function to help fix channel access issues"""
    print("\n🔧 CHANNEL ACCESS TROUBLESHOOTING")
    print("=" * 50)
    
    with app:
        me = app.get_me()
        print(f"Bot account: {me.first_name} (@{me.username if me.username else 'No username'})")
        print(f"Bot ID: {me.id}")
        
        print("\n📋 Checking all accessible chats...")
        
        # Get all dialogs to see what channels the bot can access
        accessible_channels = []
        try:
            for dialog in app.get_dialogs(limit=100):
                if dialog.chat.type in ["channel", "supergroup"]:
                    accessible_channels.append({
                        'title': dialog.chat.title,
                        'id': dialog.chat.id,
                        'username': getattr(dialog.chat, 'username', None),
                        'type': dialog.chat.type
                    })
        except Exception as e:
            print(f"Error getting dialogs: {e}")
        
        if accessible_channels:
            print(f"\n✅ Found {len(accessible_channels)} accessible channels/groups:")
            for i, channel in enumerate(accessible_channels, 1):
                username_part = f" (@{channel['username']})" if channel['username'] else ""
                print(f"{i:2d}. {channel['title']}{username_part}")
                print(f"    ID: {channel['id']} | Type: {channel['type']}")
        else:
            print("\n❌ No accessible channels found!")
            
        print("\n🎯 SOLUTIONS TO TRY:")
        print("1. Join the target channel manually:")
        print("   - Open Telegram app")
        print("   - Search for the channel")
        print("   - Join the channel")
        print("   - Make sure the bot account is added as admin")
        
        print("\n2. Use channel username instead of ID:")
        print("   - Find the channel's @username")
        print("   - Replace the ID with '@username' in the code")
        
        print("\n3. Add bot to channel as admin:")
        print("   - Go to channel settings")
        print("   - Add the bot as administrator")
        print("   - Give it permission to send messages")
        
        print("\n4. Verify channel IDs:")
        print("   Current source channel ID:", source_channel)
        print("   Current target channel ID:", target_channel)
        
        return accessible_channels

def authenticate_google_drive():
    """Authenticate with Google Drive API using token.pickle"""
    creds = None
    
    # Load existing credentials from token.pickle
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If credentials are not valid, refresh them
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save the refreshed credentials
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                print(f"Error refreshing Google Drive credentials: {e}")
                return None
        else:
            print("No valid Google Drive credentials found in token.pickle")
            return None
    
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Error building Google Drive service: {e}")
        return None

def upload_to_google_drive(service, file_path, file_name, folder_id):
    """Upload file to Google Drive folder"""
    try:
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        return file.get('id')
    except Exception as e:
        print(f"Error uploading to Google Drive: {e}")
        return None

def download_telegram_media(msg, temp_dir):
    """Download media from Telegram message to temporary directory"""
    try:
        if msg.photo:
            # For photos, get the largest size
            file_name = f"photo_{msg.id}_{int(time.time())}.jpg"
        elif msg.document:
            # For documents, use original filename or create one
            if hasattr(msg.document, 'file_name') and msg.document.file_name:
                file_name = msg.document.file_name
            else:
                # Create filename based on mime type
                ext = "jpg" if "jpeg" in msg.document.mime_type else "png"
                file_name = f"image_{msg.id}_{int(time.time())}.{ext}"
        else:
            return None, None
        
        file_path = os.path.join(temp_dir, file_name)
        
        # Download the file
        app.download_media(msg, file_name=file_path)
        
        return file_path, file_name
    except Exception as e:
        print(f"Error downloading media: {e}")
        return None, None

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
    """Check if message contains image files only - including all image formats"""
    if msg.photo:
        return True
    
    if msg.document and msg.document.mime_type:
        # Support all common image formats
        image_mime_types = [
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
            'image/webp', 'image/bmp', 'image/tiff', 'image/svg+xml',
            'image/heic', 'image/heif'
        ]
        return msg.document.mime_type.lower() in image_mime_types
    
    # Also check by file extension if mime type is not available
    if msg.document and hasattr(msg.document, 'file_name') and msg.document.file_name:
        file_name = msg.document.file_name.lower()
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.svg', '.heic', '.heif']
        return any(file_name.endswith(ext) for ext in image_extensions)
    
    return False

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

            # Check target channel with more detailed error handling
            try:
                target_chat = app.get_chat(target_channel)
                print(f"✓ Target channel accessible: {target_chat.title}")

                # Check if we have admin rights to send messages
                try:
                    # Try to get chat member info first
                    try:
                        member = app.get_chat_member(target_channel, me.id)
                        print(f"✓ Bot status in target channel: {member.status}")
                        
                        # Check if bot has necessary permissions
                        if member.status in ["administrator", "creator"]:
                            print("✓ Bot has admin rights")
                        elif member.status == "member":
                            print("⚠ Bot is only a member, may not have send permissions")
                        else:
                            print(f"⚠ Bot status: {member.status}")
                            
                    except Exception as member_error:
                        print(f"⚠ Could not check bot permissions: {member_error}")
                    
                    # Try to send a test message
                    test_caption = f"Wall {load_wall_counter()} by @lox_wall"
                    app.send_message(target_channel, f"🤖 Bot started successfully ✓\n📝 Next caption will be: {test_caption}\n🎯 Ready to forward all images!")
                    print("✓ Can send messages to target channel")
                except Exception as e:
                    print(f"✗ Cannot send messages to target channel: {e}")
                    print("  This usually means:")
                    print("  - Bot is not an admin in the channel")
                    print("  - Bot doesn't have 'Send Messages' permission")
                    print("  - Channel has restricted settings")
                    return False

            except PeerIdInvalid:
                print(f"✗ Cannot access target channel ID: {target_channel}")
                print("  This error means:")
                print("  - The channel ID is incorrect")
                print("  - Bot has never interacted with this channel")
                print("  - Bot is not a member of the channel")
                print("  - Channel is private and bot doesn't have access")
                
                # Run the troubleshooting function
                print("\n🔧 Running channel access troubleshooter...")
                accessible_channels = fix_channel_access()
                
                return False
            except Exception as e:
                print(f"✗ Error accessing target channel: {e}")
                return False

            return True
        except Exception as e:
            print(f"Error during channel check: {e}")
            return False

def forward_files():
    """Main function to forward image files from source to target channel and upload to Google Drive"""
    # Initialize Google Drive service
    drive_service = authenticate_google_drive()
    if not drive_service:
        print("⚠ Warning: Google Drive authentication failed. Files will only be forwarded to Telegram.")
    else:
        print("✓ Google Drive authenticated successfully")

    with app:
        try:
            # Load previously forwarded messages log
            forwarded_log = load_forwarded_log()

            forwarded_count = 0
            failed_count = 0
            skipped_count = 0
            gdrive_uploaded = 0
            gdrive_failed = 0

            print(f"\nLoaded log: {len(forwarded_log)} previously forwarded messages")
            print(f"Starting wall counter from: Wall {load_wall_counter()}")
            print("🚀 Starting to forward ALL image files (A to Z)...")

            # Create temporary directory for downloads
            with tempfile.TemporaryDirectory() as temp_dir:
                # Get ALL messages from source channel (no limit to ensure we get everything)
                print("📥 Fetching all messages from source channel...")
                all_messages = []
                
                # Fetch messages in batches to get everything
                offset_id = 0
                batch_size = 100
                total_fetched = 0
                
                while True:
                    try:
                        batch = list(app.get_chat_history(
                            source_channel, 
                            limit=batch_size,
                            offset_id=offset_id
                        ))
                        
                        if not batch:
                            break
                            
                        all_messages.extend(batch)
                        total_fetched += len(batch)
                        offset_id = batch[-1].id
                        
                        print(f"📥 Fetched {total_fetched} messages so far...")
                        
                        # Small delay to avoid rate limits
                        time.sleep(1)
                        
                    except Exception as e:
                        print(f"⚠ Error fetching batch: {e}")
                        break
                
                print(f"📥 Total messages fetched: {len(all_messages)}")
                
                # Process all messages
                for msg in all_messages:
                    if msg.id in forwarded_log:
                        skipped_count += 1
                        continue

                    if is_image_media(msg):
                        try:
                            # Get dynamic caption
                            caption = get_next_wall_caption()
                            
                            # Copy the message to Telegram channel
                            telegram_success = False
                            if msg.photo:
                                # For photos
                                app.send_photo(
                                    chat_id=target_channel,
                                    photo=msg.photo.file_id,
                                    caption=caption
                                )
                                telegram_success = True
                            elif msg.document and is_image_media(msg):
                                # For all image documents
                                app.send_document(
                                    chat_id=target_channel,
                                    document=msg.document.file_id,
                                    caption=caption
                                )
                                telegram_success = True

                            if telegram_success:
                                forwarded_count += 1
                                forwarded_log.add(msg.id)

                                media_type = "photo" if msg.photo else "image document"
                                print(f"✓ Sent {media_type} to Telegram with caption: {caption} (ID: {msg.id})")

                                # Upload to Google Drive if service is available
                                if drive_service:
                                    try:
                                        file_path, file_name = download_telegram_media(msg, temp_dir)
                                        if file_path and os.path.exists(file_path):
                                            gdrive_file_id = upload_to_google_drive(
                                                drive_service, file_path, file_name, GDRIVE_FOLDER_ID
                                            )
                                            if gdrive_file_id:
                                                gdrive_uploaded += 1
                                                print(f"✓ Uploaded to Google Drive: {file_name}")
                                            else:
                                                gdrive_failed += 1
                                                print(f"✗ Failed to upload to Google Drive: {file_name}")
                                            
                                            # Clean up the temporary file
                                            try:
                                                os.remove(file_path)
                                            except:
                                                pass
                                        else:
                                            gdrive_failed += 1
                                            print(f"✗ Failed to download media for Google Drive upload")
                                    except Exception as gdrive_error:
                                        gdrive_failed += 1
                                        print(f"✗ Google Drive upload error: {gdrive_error}")

                                print(f"Total processed: {forwarded_count}")

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
                                caption = get_next_wall_caption()
                                if msg.photo:
                                    app.send_photo(
                                        chat_id=target_channel,
                                        photo=msg.photo.file_id,
                                        caption=caption
                                    )
                                elif msg.document and is_image_media(msg):
                                    app.send_document(
                                        chat_id=target_channel,
                                        document=msg.document.file_id,
                                        caption=caption
                                    )

                                forwarded_count += 1
                                forwarded_log.add(msg.id)
                                print(f"✓ Sent message {msg.id} after flood wait with caption: {caption}")
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
            print(f"Successfully sent to Telegram: {forwarded_count} image files")
            print(f"Failed Telegram sends: {failed_count} files")
            print(f"Skipped (already processed): {skipped_count} files")
            print(f"Current wall counter: Wall {load_wall_counter()}")
            if drive_service:
                print(f"Successfully uploaded to Google Drive: {gdrive_uploaded} files")
                print(f"Failed Google Drive uploads: {gdrive_failed} files")
            print("Task completed!")

            # After completing batch forward, switch to monitoring mode
            print("\n🔄 Switching to monitoring mode for new files...")
            monitor_and_forward()

        except Exception as e:
            print(f"An error occurred: {e}")
            # Save log even if there's an error
            save_forwarded_log(forwarded_log)

def monitor_and_forward():
    """Monitor source channel and forward new image files in real-time"""
    # Initialize Google Drive service
    drive_service = authenticate_google_drive()
    if not drive_service:
        print("⚠ Warning: Google Drive authentication failed. Files will only be forwarded to Telegram.")
    else:
        print("✓ Google Drive authenticated successfully")

    with app:
        me = app.get_me()
        print(f"Logged in as: {me.first_name}")
        print("Monitoring for new image files... (Service will run continuously)")

        # Load previously forwarded messages log
        forwarded_log = load_forwarded_log()

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                while True:
                    # Check for new messages
                    for msg in app.get_chat_history(source_channel, limit=10):
                        if msg.id not in forwarded_log and is_image_media(msg):
                            try:
                                # Get dynamic caption
                                caption = get_next_wall_caption()
                                
                                # Send to Telegram
                                telegram_success = False
                                if msg.photo:
                                    app.send_photo(
                                        chat_id=target_channel,
                                        photo=msg.photo.file_id,
                                        caption=caption
                                    )
                                    telegram_success = True
                                elif msg.document and is_image_media(msg):
                                    app.send_document(
                                        chat_id=target_channel,
                                        document=msg.document.file_id,
                                        caption=caption
                                    )
                                    telegram_success = True

                                if telegram_success:
                                    forwarded_log.add(msg.id)
                                    save_forwarded_log(forwarded_log)
                                    print(f"✓ Auto-sent new image file to Telegram with caption: {caption} (ID: {msg.id})")

                                    # Upload to Google Drive
                                    if drive_service:
                                        try:
                                            file_path, file_name = download_telegram_media(msg, temp_dir)
                                            if file_path and os.path.exists(file_path):
                                                gdrive_file_id = upload_to_google_drive(
                                                    drive_service, file_path, file_name, GDRIVE_FOLDER_ID
                                                )
                                                if gdrive_file_id:
                                                    print(f"✓ Auto-uploaded to Google Drive: {file_name}")
                                                else:
                                                    print(f"✗ Failed to auto-upload to Google Drive: {file_name}")
                                                
                                                # Clean up the temporary file
                                                try:
                                                    os.remove(file_path)
                                                except:
                                                    pass
                                        except Exception as gdrive_error:
                                            print(f"✗ Google Drive auto-upload error: {gdrive_error}")

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
    print("🚀 Telegram Image File Forwarder with Google Drive Upload")
    print("🔧 Running on Render - Automatic Mode with Dynamic Captions")
    print("=" * 60)

    # Check if token.pickle exists
    if not os.path.exists('token.pickle'):
        print("⚠ Warning: token.pickle not found. Google Drive upload will be disabled.")
        print("Make sure token.pickle is in the same directory as this script.")

    # Show current wall counter
    current_counter = load_wall_counter()
    print(f"📝 Current wall counter: Wall {current_counter}")

    # First, check if we can access both channels
    if not check_channels():
        print("\n❌ Cannot proceed - channel access issues detected!")
        print("\n🔧 MANUAL STEPS TO FIX:")
        print("1. Open Telegram and join the target channel manually")
        print("2. Add your bot account to the target channel as an admin")
        print("3. Give the bot 'Send Messages' permission")
        print("4. Alternatively, use the channel's @username instead of the numeric ID")
        print("\n💡 TIP: The troubleshooter above showed all channels your bot can access.")
        print("Make sure your target channel is in that list!")
        sys.exit(1)

    # Auto-start with option 1 (batch forward) then switch to monitoring
    print("\n🔄 Auto-starting batch forward mode...")
    forward_files()
