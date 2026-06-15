#!/usr/bin/env python3
from pathlib import Path
import sys

# Load the analyzer module
analyzer_path = Path(r'.github/skills/test-log-analyzer/scripts/analyze_test_logs.py').resolve()
from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location('analyze_test_logs', analyzer_path)
mod = module_from_spec(spec)
spec.loader.exec_module(mod)

input_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('C:/Users/igevorgy/Desktop/File/Short.std')

# Record type analysis
try:
    lines = mod.stdf_to_atdf_lines(input_file)
    
    rec_counts = {}
    for line in lines:
        if ':' in line:
            rec_type = line.split('|')[0].strip()
            rec_counts[rec_type] = rec_counts.get(rec_type, 0) + 1
    
    print('Record Type Summary:')
    print('=' * 60)
    total = 0
    for rec_type in sorted(rec_counts.keys()):
        count = rec_counts[rec_type]
        total += count
        print(f'{rec_type:8s}: {count:10,d} records')
    print('-' * 60)
    print(f'TOTAL   : {total:10,d} records')
    print()
    
    # Show file metadata
    print('File Metadata (from MIR):')
    print('=' * 60)
    for line in lines[:10]:
        if 'MIR' in line:
            fields = line.split('|')
            print(f'Start time: {fields[1] if len(fields) > 1 else "N/A"}')
            print(f'End time: {fields[2] if len(fields) > 2 else "N/A"}')
            print(f'Lot ID: {fields[9] if len(fields) > 9 else "N/A"}')
            print(f'Part Type: {fields[10] if len(fields) > 10 else "N/A"}')
            print(f'Tester: {fields[11] if len(fields) > 11 else "N/A"}')
            break
    
    print()
    print('Data Analysis:')
    print('=' * 60)
    
    # Run the standard analysis
    prr_df, ptr_df, ftr_df = mod.parse_stdf(input_file)
    summary = mod.compute_summary(prr_df, ptr_df, ftr_df, top_n=5)
    print(mod.render_output(summary))
    
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
