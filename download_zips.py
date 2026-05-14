# import requests

# # download_zips.py - MOCK MODE (WORKS IMMEDIATELY)
# import os
# import smartsheet
# import os
# import requests
# import zipfile
# from datetime import datetime

# SMARTSHEET_TOKEN = "7xcmOm3neR6SXBXda7fY9qis3Bg9z9VsBZ6T6"
# SHEET_ID = "7220178429366148"
#!/usr/bin/env python3

#!/usr/bin/env python3
"""
Script to download all attachments from a Smartsheet sheet.
Requires: pip install requests --break-system-packages
"""
"""
Script to download all attachments from a Smartsheet sheet.
Requires: pip install requests --break-system-packages
"""
import requests
import os
import sys
from pathlib import Path


class SmartsheetAttachmentDownloader:
    def __init__(self, access_token, sheet_id, start_row=436):
        """
        Initialize the downloader.

        Args:
            access_token (str): Smartsheet API access token
            sheet_id (str): Sheet ID
            start_row (int): Row number to start processing from
        """
        self.access_token = access_token
        self.sheet_id = sheet_id
        self.start_row = start_row

        self.base_url = "https://api.smartsheet.com/2.0"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def get_row_attachments(self):
        """Fetch rows and collect attachments starting from start_row."""
        print("📥 Fetching rows from Smartsheet...")

        all_attachments = []
        url = f"{self.base_url}/sheets/{self.sheet_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            sheet_data = response.json()

            rows = sheet_data.get("rows", [])
            print(f"  → Found {len(rows)} rows")
            print(f"  → Starting from row {self.start_row}")

            for i, row in enumerate(rows, 1):

                # ✅ Skip rows before chosen start row
                if i < self.start_row:
                    continue

                row_id = row.get("id")
                if not row_id:
                    continue

                if i % 10 == 0:
                    print(f"  → Processing row {i}/{len(rows)}...")

                attachments = self.get_attachments_for_row(row_id)
                all_attachments.extend(attachments)

        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching rows: {e}")

        print(f"✓ Total attachments found: {len(all_attachments)}")
        return all_attachments

    def get_attachments_for_row(self, row_id):
        """Get attachments for a specific row."""
        url = f"{self.base_url}/sheets/{self.sheet_id}/rows/{row_id}/attachments"

        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching attachments for row {row_id}: {e}")
            return []

    def get_attachment_url(self, attachment_id):
        """Fetch download URL for attachment."""
        url = f"{self.base_url}/sheets/{self.sheet_id}/attachments/{attachment_id}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("url")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching attachment URL: {e}")
            return None

    def download_attachment(self, attachment, output_dir):
        """Download a single attachment."""
        attachment_id = attachment.get("id")
        attachment_name = attachment.get(
            "name", f"attachment_{attachment_id}"
        )
        attachment_url = attachment.get("url")

        if not attachment_url:
            print(f"Fetching URL for: {attachment_name}")
            attachment_url = self.get_attachment_url(attachment_id)

        if not attachment_url:
            return False, "Could not get download URL"

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        file_path = os.path.join(output_dir, attachment_name)

        if os.path.exists(file_path):
            print(f"⏭ Already exists, skipping: {attachment_name}")
            return True, None

        try:
            download_headers = {}
            if not attachment_url.startswith("https://s3.amazonaws.com/"):
                download_headers = self.headers

            response = requests.get(
                attachment_url,
                headers=download_headers,
                stream=True,
            )
            response.raise_for_status()

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"✓ Downloaded: {attachment_name}")
            return True, None

        except requests.exceptions.RequestException as e:
            return False, f"Download error: {e}"
        except IOError as e:
            return False, f"Save error: {e}"

    def download_all_attachments(self, output_dir="smartsheet_attachments"):
        """Download all attachments."""
        print(f"Starting download from row {self.start_row}")
        print("-" * 60)

        total_downloaded = 0
        total_skipped = 0
        total_failed = 0
        failed_files = []

        attachments = self.get_row_attachments()

        if attachments:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            print(f"\nDownloading to: {os.path.abspath(output_dir)}\n")

            for i, attachment in enumerate(attachments, 1):
                print(f"[{i}/{len(attachments)}] ", end="")

                attachment_id = attachment.get("id")
                attachment_name = attachment.get(
                    "name", f"attachment_{attachment_id}"
                )
                file_path = os.path.join(output_dir, attachment_name)

                if os.path.exists(file_path):
                    print(f"⏭ Already exists, skipping: {attachment_name}")
                    total_skipped += 1
                else:
                    success, error_msg = self.download_attachment(
                        attachment, output_dir
                    )
                    if success:
                        total_downloaded += 1
                    else:
                        total_failed += 1
                        failed_files.append(
                            {
                                "name": attachment_name,
                                "id": attachment_id,
                                "error": error_msg,
                            }
                        )

        print("\n" + "=" * 60)
        print("Download complete!")
        print(f"Downloaded: {total_downloaded}")
        print(f"Skipped: {total_skipped}")
        print(f"Failed: {total_failed}")
        print("=" * 60)

        return failed_files


def main():
    """Run script."""

    if len(sys.argv) >= 3:
        access_token = sys.argv[1]
        sheet_id = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else "smartsheet_attachments"
        start_row = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    else:
        print("Smartsheet Attachment Downloader")
        print("=" * 60)

        access_token = input("Enter API token: ").strip()
        sheet_id = input("Enter Sheet ID: ").strip()
        output_dir = input(
            "Output directory (default: smartsheet_attachments): "
        ).strip() or "smartsheet_attachments"

        start_row_input = input(
            "Start from row number (default: 1): "
        ).strip()
        start_row = int(start_row_input) if start_row_input else 1

    if not access_token or not sheet_id:
        print("Error: token and sheet ID required")
        sys.exit(1)

    downloader = SmartsheetAttachmentDownloader(
        access_token,
        sheet_id,
        start_row,
    )

    failed_files = downloader.download_all_attachments(output_dir)

    if failed_files:
        sys.exit(1)


if __name__ == "__main__":
    main()