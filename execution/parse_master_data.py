import pandas as pd
from io import StringIO

# Read from document 4 (Calgary complete data)
calgary_csv = open('/dev/stdin', 'r').read()

df = pd.read_csv(StringIO(calgary_csv), keep_default_na=False)

# Get unique businesses (deduplicate by business name)
unique_businesses = df.drop_duplicates(subset='Business Name', keep='first')

# Keep only the columns we need for enrichment input
output_cols = ['Business Name', 'Primary Contact', 'Phone', 'Email', 'City', 
               'Job Title', 'Contact LinkedIn', 'Website', 'Full Address', 'Type', 
               'Quadrant', 'Company Social', 'Personal Instagram', 'Status', 'Notes']

unique_businesses = unique_businesses[output_cols]

print(f"Total unique businesses in Calgary: {len(unique_businesses)}")
print(f"Businesses with existing emails: {len(unique_businesses[unique_businesses['Email'] != ''])}")
print(f"Businesses without emails: {len(unique_businesses[unique_businesses['Email'] == ''])}")

# Save to CSV
unique_businesses.to_csv('Calgary_All_Unique_Businesses.csv', index=False)
print("\n✓ Saved to: Calgary_All_Unique_Businesses.csv")
