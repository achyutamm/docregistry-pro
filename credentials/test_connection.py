"""
Test script to verify Google Sheets connection and add sample data
Run this before building the full application
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_connection():
    """Test connection to Google Sheets"""
    print("=" * 60)
    print("DocRegistry Pro - Google Sheets Connection Test")
    print("=" * 60)
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
            'INDEX_NO', 'SEARCH_NO', 'TITLE_STATUS'
        ]
        
        if headers == expected_headers:
            print("✅ Headers are correct!")
            print(f"   Found: {', '.join(headers)}")
        else:
            print("⚠️  Headers don't match expected format")
            print(f"   Expected: {', '.join(expected_headers)}")
            print(f"   Found: {', '.join(headers)}")
        print()
        
        # Step 5: Add test data
        print("Step 5: Adding test data...")
        test_records = [
            {
                'doc_type': 'Sale Deed',
                'date': '2025-11-06',
                'time': '14:30',
                'sro': 'Pune District',
                'party_name': 'Rajesh Kumar',
                'garvi_appli_no': 'GA2025001',
                'index_appli_no': 'IA2025001',
                'index_no': 'IDX001',
                'search_no': 'SRC001',
                'title_status': 'Completed'
            },
            {
                'doc_type': 'Lease Agreement',
                'date': '2025-11-06',
                'time': '15:00',
                'sro': 'Mumbai Central',
                'party_name': 'Priya Sharma',
                'garvi_appli_no': 'GA2025002',
                'index_appli_no': 'IA2025002',
                'index_no': 'IDX002',
                'search_no': 'SRC002',
                'title_status': 'Pending'
            },
            {
                'doc_type': 'Gift Deed',
                'date': '2025-11-06',
                'time': '16:15',
                'sro': 'Nagpur Office',
                'party_name': 'Amit Patel',
                'garvi_appli_no': 'GA2025003',
                'index_appli_no': 'IA2025003',
                'index_no': 'IDX003',
                'search_no': 'SRC003',
                'title_status': 'In Progress'
            }
        ]
        
        for i, record in enumerate(test_records, 1):
            # Generate entry ID
            entry_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(i)
            
            # Prepare row
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
                record['title_status']
            ]
            
            # Add to sheet
            sheet.append_row(row)
            print(f"   ✅ Added record {i}: {record['party_name']} - {record['doc_type']}")
        
        print()
        print(f"✅ Successfully added {len(test_records)} test records!")
        print()
        
        # Step 6: Read and display data
        print("Step 6: Reading data from sheet...")
        all_records = sheet.get_all_records()
        print(f"✅ Total records in sheet: {len(all_records)}")
        print()
        
        if all_records:
            print("Recent records:")
            print("-" * 60)
            for record in all_records[-3:]:  # Show last 3 records
                print(f"   ID: {record['ENTRY_ID']}")
                print(f"   Party: {record['PARTY_NAME']}")
                print(f"   Doc Type: {record['DOC_TYPE']}")
                print(f"   Status: {record['TITLE_STATUS']}")
                print("-" * 60)
        
        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED! Connection is working perfectly!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Check your Google Sheet - you should see 3 test records")
        print("2. Run 'streamlit run app.py' to launch the full application")
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
    test_connection()
