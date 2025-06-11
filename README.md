# tg-file-scrap-to-tg-and-drive
A python script to scrap files (images) from other's channles without access and forward to your target channel and gooogle drive.

1. tg-drive.py

How It Works:

Authentication: Uses your existing token.pickle file for Google Drive API access
Dual Operation:

Forwards images to your Telegram channel
Downloads each image temporarily and uploads to Google Drive


File Naming: Creates meaningful filenames for Google Drive uploads
Cleanup: Automatically removes temporary files after upload

Key Features:

Batch Mode: Processes historical messages and uploads them to both Telegram and Google Drive
Monitor Mode: Real-time monitoring that automatically uploads new images to both destinations
Progress Tracking: Shows separate statistics for Telegram forwards and Google Drive uploads
Resilient: Continues working even if Google Drive authentication fails (Telegram-only mode)

------------------------------------------------------------------------------------------------------------------------------------------
