# I'll manually count the unique businesses from the documents provided
# Document 3: Edmonton has approximately 200 unique business entries
# Document 4: Calgary has approximately 300+ unique business entries

# For now, let me create a test to see how many we can process
print("From the documents you provided:")
print("- Calgary master file: ~300+ businesses (many already with multiple emails)")
print("- Edmonton master file: ~200+ businesses (many already with multiple emails)")
print("\nThese files appear to already be enriched with the multi-email system.")
print("\nTo re-enrich and find additional missed emails, I need to:")
print("1. Extract ONLY unique business names (deduplicate)")
print("2. Run fresh enrichment on all of them")
print("3. Merge results with existing data")
