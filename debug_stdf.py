from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

print("Starting debug script")

root = Path(r'C:\Users\igevorgy\Desktop\SEMI_SKILLs')
analyzer_path = root / '.github' / 'skills' / 'test-log-analyzer' / 'scripts' / 'analyze_test_logs.py'

print(f"Loading analyzer from: {analyzer_path}")
print(f"Analyzer exists: {analyzer_path.exists()}")

spec = spec_from_file_location('analyze_test_logs', analyzer_path)
mod = module_from_spec(spec)
spec.loader.exec_module(mod)

print("Analyzer loaded")

input_file = Path(r'C:\Users\igevorgy\Desktop\File\Short.std')
print(f"Input file exists: {input_file.exists()}")

lines = mod.stdf_to_atdf_lines(input_file)
print(f"Parsed {len(lines)} lines")

# Find PRR records
prr_lines = [l for l in lines if l.startswith('PRR|')]
print(f'Total PRR records: {len(prr_lines)}\n')

print('First 3 PRR records:')
for i, line in enumerate(prr_lines[:3]):
    fields = line.split('|')
    print(f'PRR {i+1}: {len(fields)} fields')
    print(f'  {line[:200]}')
