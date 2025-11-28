import subprocess
import os
import sys

BMINOR_SCRIPT = 'bminor.py'
TEST_FOLDER = os.path.join('test', 'scanner')

# Diccionario: nombre del archivo -> salida esperada
test_cases = {
    'good0.bminor': 0,
    'good1.bminor': 0,
    'good2.bminor': 0,
    'good3.bminor': 0,
    'good4.bminor': 0,
    'good5.bminor': 0,
    'good6.bminor': 0,
    'good7.bminor': 0,
    'good8.bminor': 0,
    'good9.bminor': 0,
    
    'bad0.bminor': 1,
    'bad1.bminor': 1,
    'bad2.bminor': 1,
    'bad3.bminor': 1,
    'bad4.bminor': 1,
    'bad5.bminor': 1,
    'bad6.bminor': 1,
    'bad7.bminor': 1,
    'bad8.bminor': 1,
    'bad9.bminor': 1,
}

print("Running tests...\n")
for file_name, expected_exit in test_cases.items():
    path = os.path.join(TEST_FOLDER, file_name)
    if not os.path.exists(path):
        print(f"Test file doesn't exist '{path}'")
        continue
    result = subprocess.run(['python', BMINOR_SCRIPT, '--scan', path], stdout=sys.stdout,stderr=sys.stderr,text=True)
    actual_exit = result.returncode

    status = 'OK' if actual_exit == expected_exit else 'ERROR'
    print(f"{file_name}: Expected={expected_exit}, Actual={actual_exit} → {status}")