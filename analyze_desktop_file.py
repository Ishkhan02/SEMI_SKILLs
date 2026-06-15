#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import sys

# Load the analyzer module from SEMI_SKILLs
analyzer_path = Path(r'C:\Users\igevorgy\Desktop\SEMI_SKILLs\.github\skills\test-log-analyzer\scripts\analyze_test_logs.py').resolve()
spec = importlib.util.spec_from_file_location('analyze_test_logs', analyzer_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Analyze the specified file
input_file = Path(r'C:\Users\igevorgy\Desktop\File\1YUSK83G_001_S11P_N_20260526194205_M6251A0022AKX12NIA_T4C03.std')
print('Analyzing:', input_file)
print('File exists:', input_file.exists())
print()

try:
    df, info = mod.parse_stdf(input_file)
    metrics = mod.compute_metrics(df)
    report = mod.generate_report(df, metrics, info, input_file)
    print(report)
    
    # Save CSV
    csv_path = input_file.parent / f'{input_file.stem}_normalized.csv'
    df.to_csv(csv_path, index=False)
    print(f'\nCSV saved to: {csv_path}')
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
