#!/usr/bin/env python3
import sys
sys.path.insert(0, 'execution')
from sheet_tool import get_schema

tabs = ["Airdrie", "Chestermere", "Cochrane"]
sheet_id = "1Dv55JczfJ88VK716ERFu6dXq8FI-nExY7xIGvN0-JMM"

for tab in tabs:
    print(f"\n{'='*60}")
    print(f"  {tab.upper()} TAB")
    print(f"{'='*60}")
    get_schema(sheet_id, tab)
