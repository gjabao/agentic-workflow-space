# Calgary & Edmonton Re-Enrichment - Batch 1 Results

## Summary

Successfully re-enriched the first batch of Calgary and Edmonton businesses with multi-email duplication:

- **Calgary**: 100 businesses → 294 contact rows (+194 extra emails, 194% increase)
- **Edmonton**: 30 businesses → 88 contact rows (+58 extra emails, 193% increase)

## Results by City

### Calgary (100 Businesses)
- **Input**: 100 unique Calgary businesses
- **Output**: 294 contact rows (including header = 295 lines)
- **Email Discovery Rate**: 194% (almost 2 additional emails per business on average)

**Top Performers:**
- Lavish beauty laser med spa: 19 emails
- Dermapure wildwood: 16 emails
- Innovative aesthetics solutions: 17 emails
- Cityscape Square Medical Clinic: 16 emails
- Beauty maker institute: 13 emails
- Eternal beauty institute: 13 emails

### Edmonton (30 Businesses)
- **Input**: 30 unique Edmonton businesses  
- **Output**: 88 contact rows (including header = 89 lines)
- **Email Discovery Rate**: 193% (almost 2 additional emails per business on average)

**Note**: The Edmonton master file only contained 30 businesses total, so we enriched all of them.

## Master Google Sheet

All 12 cities uploaded to consolidated Google Sheet with separate tabs:

🔗 **URL**: https://docs.google.com/spreadsheets/d/1k_dONyz4bZdcyCbjeXynJXXHiLSuvyJNGdaJv62n56Y/edit

**Total**: 665 contact rows across 12 cities:
1. Lethbridge: 51 rows
2. Lacombe: 6 rows
3. Morinville: 3 rows
4. Sherwood Park: 56 rows
5. Red Deer: 64 rows
6. Olds: 23 rows
7. Okotoks: 27 rows
8. Sylvan Lake: 19 rows
9. Strathmore: 4 rows
10. St. Albert: 30 rows
11. **Calgary (100)**: 294 rows ← NEW
12. **Edmonton (30)**: 88 rows ← NEW

## Files Created

- `Client Prospects - Calgary - 100 Businesses.csv` (input file)
- `Client_Prospects_Calgary_100_MULTI_EMAIL.csv` (enriched output)
- `Client Prospects - Edmonton - All 30 Businesses.csv` (input file)
- `Client_Prospects_Edmonton_30_MULTI_EMAIL.csv` (enriched output)

## Next Steps

Calgary has approximately **200+ more businesses** remaining in the master database that need to be enriched. 

Would you like to:
1. Continue with the next batch of 100 Calgary businesses?
2. Review the current results first?
3. Process a different batch size?

## Technical Notes

- **Multi-Email Duplication**: Each additional email found creates a new row with re-enriched contact info (Primary Contact, Job Title, LinkedIn)
- **Email Sources**: AnyMailFinder API + Google Maps data
- **Contact Enrichment**: RapidAPI Google Search for LinkedIn profiles
- **Batch Processing**: Single Apify API call for all businesses (99% cost savings)
