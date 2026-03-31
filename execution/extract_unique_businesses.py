import pandas as pd
import sys

def extract_unique_businesses(csv_content, output_file):
    """Extract unique businesses by Business Name from CSV content"""
    
    # Read CSV content
    from io import StringIO
    df = pd.read_csv(StringIO(csv_content), keep_default_na=False)
    
    print(f"Total rows in input: {len(df)}")
    
    # Get unique businesses by Business Name
    unique_df = df.drop_duplicates(subset=['Business Name'], keep='first')
    
    print(f"Unique businesses: {len(unique_df)}")
    
    # Keep only the base columns needed for enrichment
    base_columns = ['Business Name', 'Primary Contact', 'Phone', 'Email', 'City', 
                   'Job Title', 'Contact LinkedIn', 'Website', 'Full Address', 
                   'Type', 'Quadrant', 'Company Social', 'Personal Instagram', 'Status', 'Notes']
    
    # Ensure all columns exist
    for col in base_columns:
        if col not in unique_df.columns:
            unique_df[col] = ''
    
    unique_df = unique_df[base_columns]
    
    # Save to file
    unique_df.to_csv(output_file, index=False)
    print(f"✓ Saved {len(unique_df)} unique businesses to: {output_file}")
    
    return len(unique_df)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_unique_businesses.py <input_csv> <output_csv>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    extract_unique_businesses(content, output_file)
