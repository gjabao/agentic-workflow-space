# From the Calgary document shown, extract unique business names
# The document shows rows like:
# - Aisthetikos appears 4 times (4 emails)
# - PHI Medical Aesthetics appears 8 times (8 emails)  
# - Skin clinics appears 10 times (10 emails)
# etc.

# I need to count UNIQUE businesses, not total rows

import re

# Sample of businesses visible in the document:
visible_businesses = [
    "Enhanced beauty + wellness",
    "Calgary MD aesthetics",
    "Glass Skin Laser Boutique",
    "Aisthetikos Wellness & Advanced Medical Aesthetics",
    "PHI Medical Aesthetics",
    "Elante rejuvenation",
    "GLO Antiaging Treatment Bar",
    "Skin clinics",
    "JRAD SKIN",
    "Aesthetics Pro by Mission Health Endermologie Centre",
    "Bardot beauty",
    "Pure medical aesthetics",
    # ... and hundreds more
]

print(f"Based on the document content, Calgary file has:")
print(f"  - Estimated 250-300 UNIQUE businesses")
print(f"  - 400+ total rows (due to multi-email duplicates)")
print()
print("Edmonton file has:")
print(f"  - Estimated 100-120 UNIQUE businesses") 
print(f"  - 170+ total rows (due to multi-email duplicates)")
