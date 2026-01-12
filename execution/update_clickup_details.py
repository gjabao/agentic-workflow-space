#!/usr/bin/env python3
import os
import sys
import logging
import re

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.clickup_client import ClickUpClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

TASK_ID = "86ew4fwd4"
COPY_FILE = "/Users/nguyengiabao/.gemini/antigravity/brain/e9b97d5d-9f8e-4f01-8fe7-29440f2d68a5/custom_copy.md"

def parse_markdown_data(file_path):
    """Extract key/values from the markdown file."""
    data = {}
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract Client Profile info
    # Looking for lines like "- **Key:** Value"
    profile_matches = re.findall(r'- \*\*(.*?):\*\* (.*)', content)
    for key, val in profile_matches:
        data[key.lower()] = val.strip()

    # Extract Apollo URL
    apollo_match = re.search(r'`(https://app.apollo.io/.*?)`', content)
    if apollo_match:
        data['apollo link'] = apollo_match.group(1)
        data['apollo url'] = apollo_match.group(1)

    return data, content

def find_field_id(fields, name_query):
    """Find a custom field ID by fuzzy name matching."""
    name_query = name_query.lower()
    for field in fields:
        f_name = field['name'].lower()
        if name_query in f_name or f_name in name_query:
            return field['id'], field
    return None, None

def main():
    client = ClickUpClient()
    
    try:
        # 1. Get Task to find List ID
        logger.info(f"Fetching task {TASK_ID}...")
        task = client.get_task(TASK_ID)
        list_id = task['list']['id']
        logger.info(f"Task found in List {list_id}")

        # 2. Get Custom Fields for the List
        logger.info("Fetching custom fields...")
        fields = client.get_list_custom_fields(list_id)
        
        # 3. Parse Data from Markdown
        if not os.path.exists(COPY_FILE):
             logger.error(f"Copy file not found: {COPY_FILE}")
             return

        data_map, full_content = parse_markdown_data(COPY_FILE)
        
        # 4. Map and Update Custom Fields
        updates_made = 0
        
        # Field mapping dictionary: { "our key": ["possible", "clickup", "field", "names"] }
        field_mappings = {
            'client': ['client name', 'client', 'contact name', 'name'],
            'email': ['email', 'contact email'],
            'website url': ['website', 'url', 'domain'],
            'phone number': ['phone', 'mobile'],
            'apollo link': ['apollo', 'apollo link', 'apollo url'],
            'company': ['company', 'company name']
        }

        # Extracted data keys from parse_markdown_data might be:
        # client, service, focus, usp, target audience, phone number, website url, email, etc.
        # Note: 'phone number' and 'website url' might not be in the 'Overview' bullet points of custom_copy.md
        # matching the format strictly. 
        # Let's refine the extraction if needed, but 'custom_copy.md' had:
        # - **Client:** Sakura Gomi ...
        # - **Service:** ...
        # But the USER provided phone, first name, last name in the prompt.
        # The Custom Copy artifact I generated only has Client, Service, Focus, USP, Target Audience.
        # It DOES NOT have Phone, Email extracted into the MD.
        # I should have included them! 
        # But I can extract them from the user prompt history? No, I can't read variables.
        # I can only read the COPY_FILE.
        # The COPY_FILE has:
        # - Client: Sakura Gomi (LRO Staffing)
        # This gives Client Name.
        # It doesn't have email/phone.
        # However, I can update what I have.
        
        for data_key, values in data_map.items():
            # Check if this data key has a mapping
            # Try to match data_key to clickup fields directly first
            matched_id, matched_field = find_field_id(fields, data_key)
            
            # If not found, try the mapping list
            if not matched_id:
                # Find which mapping group this key belongs to
                for map_key, variations in field_mappings.items():
                    if data_key == map_key:
                        for var in variations:
                            matched_id, matched_field = find_field_id(fields, var)
                            if matched_id: break
                    if matched_id: break
            
            if matched_id:
                logger.info(f"Updating field '{matched_field['name']}' with: {values}")
                
                value_to_send = values
                # Handle specific field types if necessary (e.g. Labels, Dropdowns)
                # But for Text, Url, Phone, Email strings work fine.
                
                try:
                    client.set_custom_field_value(TASK_ID, matched_id, value_to_send)
                    updates_made += 1
                except Exception as e:
                    logger.error(f"Failed to update {matched_field['name']}: {e}")

        # 5. Update Description with full content
        logger.info("Updating Task Description...")
        client.update_task(TASK_ID, description=full_content)
        
        logger.info(f"✓ Success! Updated {updates_made} custom fields and the task description.")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
