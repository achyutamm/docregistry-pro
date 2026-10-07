"""
Send WhatsApp messages that were queued while the WhatsApp service was down
(new-entry group messages and Party 1 document checklists).

Runs via GitHub Actions every 15 minutes (.github/workflows/whatsapp-queue.yml).
Does nothing when the queue is empty or WhatsApp is still down.

Usage:
    python whatsapp_queue_sender.py
"""

from utils import whatsapp_queue
from utils.whatsapp_sender import baileys_connected


def run():
    items = whatsapp_queue.pending()
    if not items:
        print("No pending WhatsApp messages.")
        return
    print(f"{len(items)} pending WhatsApp message(s).")
    if not baileys_connected():
        print("WhatsApp service is still not connected — will try again next run.")
        return
    result = whatsapp_queue.flush()
    print(f"Sent {result['sent']}, still pending {result['remaining']}, "
          f"could not send {result['failed']}"
          + (f", stopped: {result['stopped']}" if result["stopped"] else "") + ".")


if __name__ == "__main__":
    run()
