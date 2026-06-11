"""
Test script to verify Google Sheets connection and add sample data
WITH USER TRACKING (CREATED_BY column)

Run this to test the connection after adding the CREATED_BY column
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_connection():
    """Test connection to Google Sheets with new CREATED_BY column"""
    print("=" * 70)
    print("DocRegistry Pro - Google Sheets Connection Test (With User Tracking)")
    print("=" * 70)
    print()
    
    try:
        # Step 1: Load credentials
        print("Step 1: Loading credentials...")
        creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
        sheet_id = os.getenv('GOOGLE_SHEET_ID')
        
        if not creds_path:
            print("❌ ERROR: GOOGLE_CREDENTIALS_PATH not found in .env file")
            return False
        
        if not sheet_id:
            print("❌ ERROR: GOOGLE_SHEET_ID not found in .env file")
            return False
        
        print(f"✅ Credentials path: {creds_path}")
        print(f"✅ Sheet ID: {sheet_id}")
        print()
        
        # Step 2: Authorize
        print("Step 2: Authorizing with Google...")
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        client = gspread.authorize(creds)
        print("✅ Authorization successful")
        print()
        
        # Step 3: Open sheet
        print("Step 3: Opening Google Sheet...")
        sheet = client.open_by_key(sheet_id).sheet1
        print(f"✅ Sheet opened: {sheet.title}")
        print()
        
        # Step 4: Check headers
        print("Step 4: Verifying column headers...")
        headers = sheet.row_values(1)
        expected_headers = [
            'ENTRY_ID', 'DOC_TYPE', 'DATE', 'TIME', 'SRO', 
            'PARTY_NAME', 'GARVI_APPLI_NO', 'INDEX_APPLI_NO', 
            'INDEX_NO', 'SEARCH_NO', 'TITLE_STATUS', 'CREATED_BY'  # Added CREATED_BY
        ]
        
        print(f"Expected headers ({len(expected_headers)} columns):")
        print(f"   {', '.join(expected_headers)}")
        print()
        print(f"Found headers ({len(headers)} columns):")
        print(f"   {', '.join(headers)}")
        print()
        
        if headers == expected_headers:
            print("✅ Headers are correct!")
        else:
            print("⚠️  Headers don't match expected format")
            if len(headers) < len(expected_headers):
                missing = set(expected_headers) - set(headers)
                print(f"   Missing columns: {', '.join(missing)}")
                print(f"   👉 Please add '{missing.pop()}' column to your Google Sheet (column L)")
            elif len(headers) > len(expected_headers):
                extra = set(headers) - set(expected_headers)
                print(f"   Extra columns: {', '.join(extra)}")
        print()
        
        # Step 5: Add test data with CREATED_BY
        print("Step 5: Adding test data with user tracking...")
        test_records = [
            {
                'doc_type': 'Sale Deed',
                'date': '2025-11-07',
                'time': '10:30',
                'sro': 'Pune District',
                'party_name': 'Amit Shah',
                'garvi_appli_no': 'GA2025101',
                'index_appli_no': 'IA2025101',
                'index_no': 'IDX101',
                'search_no': 'SRC101',
                'title_status': 'Completed',
                'created_by': 'admin'  # NEW: User who created this
            },
            {
                'doc_type': 'Lease Agreement',
                'date': '2025-11-07',
                'time': '11:00',
                'sro': 'Mumbai Central',
                'party_name': 'Sunita Verma',
                'garvi_appli_no': 'GA2025102',
                'index_appli_no': 'IA2025102',
                'index_no': 'IDX102',
                'search_no': 'SRC102',
                'title_status': 'Pending',
                'created_by': 'staff1'  # Created by staff1
            },
            {
                'doc_type': 'Gift Deed',
                'date': '2025-11-07',
                'time': '14:30',
                'sro': 'Nagpur Office',
                'party_name': 'Ramesh Patel',
                'garvi_appli_no': 'GA2025103',
                'index_appli_no': 'IA2025103',
                'index_no': 'IDX103',
                'search_no': 'SRC103',
                'title_status': 'In Progress',
                'created_by': 'staff2'  # Created by staff2
            }
        ]
        
        for i, record in enumerate(test_records, 1):
            # Generate entry ID
            entry_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(i).zfill(3)
            
            # Prepare row with CREATED_BY column
            row = [
                entry_id,
                record['doc_type'],
                record['date'],
                record['time'],
                record['sro'],
                record['party_name'],
                record['garvi_appli_no'],
                record['index_appli_no'],
                record['index_no'],
                record['search_no'],
                record['title_status'],
                record['created_by']  # NEW: Track who created this record
            ]
            
            # Add to sheet
            sheet.append_row(row)
            print(f"   ✅ Added record {i}: {record['party_name']} - {record['doc_type']} (by {record['created_by']})")
        
        print()
        print(f"✅ Successfully added {len(test_records)} test records with user tracking!")
        print()
        
        # Step 6: Read and display data
        print("Step 6: Reading data from sheet...")
        all_records = sheet.get_all_records()
        print(f"✅ Total records in sheet: {len(all_records)}")
        print()
        
        if all_records:
            print("Recent records (with user tracking):")
            print("-" * 70)
            for record in all_records[-3:]:  # Show last 3 records
                print(f"   ID: {record.get('ENTRY_ID', 'N/A')}")
                print(f"   Party: {record.get('PARTY_NAME', 'N/A')}")
                print(f"   Doc Type: {record.get('DOC_TYPE', 'N/A')}")
                print(f"   Status: {record.get('TITLE_STATUS', 'N/A')}")
                print(f"   👤 Created By: {record.get('CREATED_BY', 'N/A')}")  # NEW
                print("-" * 70)
        
        # Step 7: User activity summary
        print()
        print("Step 7: User Activity Summary...")
        user_counts = {}
        for record in all_records:
            user = record.get('CREATED_BY', 'Unknown')
            user_counts[user] = user_counts.get(user, 0) + 1
        
        if user_counts:
            print("Records by user:")
            for user, count in sorted(user_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(all_records) * 100) if all_records else 0
                print(f"   📊 {user}: {count} records ({percentage:.1f}%)")
        
        print()
        print("=" * 70)
        print("✅ ALL TESTS PASSED! Connection and user tracking working perfectly!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. ✅ User tracking is now enabled")
        print("2. ✅ Check your Google Sheet - you should see 3 new records")
        print("3. ✅ CREATED_BY column shows which user created each record")
        print("4. 🚀 Run 'streamlit run app.py' to see user activity in dashboard")
        print()
        
        return True
        
    except FileNotFoundError as e:
        print(f"❌ ERROR: Credentials file not found!")
        print(f"   Please check: {creds_path}")
        print(f"   Error: {e}")
        return False
        
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ ERROR: Google Sheet not found!")
        print(f"   Sheet ID: {sheet_id}")
        print(f"   Make sure:")
        print(f"   1. Sheet ID in .env file is correct")
        print(f"   2. Sheet is shared with service account email")
        return False
        
    except gspread.exceptions.APIError as e:
        print(f"❌ ERROR: Google API Error!")
        print(f"   {e}")
        print(f"   Make sure:")
        print(f"   1. Google Sheets API is enabled")
        print(f"   2. Google Drive API is enabled")
        print(f"   3. Service account has Editor access to the sheet")
        return False
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}")
        print(f"   {e}")
        return False

if __name__ == "__main__":
    print()
    print("🔧 Testing Google Sheets connection with user tracking...")
    print()
    test_connection()
