import os
import sys

print("=== Analyzing path resolution ===")

# The batch file does: cd /d "C:\Users\USUARIO\Desktop\motor HPR"
target_dir = r"C:\Users\USUARIO\Desktop\motor HPR"

# And sets: set PYTHONPATH=%CD%\src
python_path = os.path.join(target_dir, "src")
print(f"PYTHONPATH would be: {python_path}")

# And runs: python "src\desktop\app.py"
app_py = os.path.join(target_dir, "src", "desktop", "app.py")
print(f"app.py path: {app_py}")

# Now simulate what Python does with __file__
print("\n=== Scenario 1: Python run from target_dir ===")
__file__ = app_py
abs_file = os.path.abspath(__file__)
print(f"__file__: {abs_file}")
parent1 = os.path.dirname(abs_file)
parent2 = os.path.dirname(parent1)
print(f"After 1 dirname: {parent1}")
print(f"After 2 dirname (inserted to sys.path): {parent2}")
expected = r"C:\Users\USUARIO\Desktop\motor HPR\HPR\src"
print(f"Expected sys.path insert: {expected}")
print(f"Match: {parent2 == expected}")

print("\n=== Scenario 2: What duplication might look like ===")
# If __file__ had an extra "motor HPR" segment
bad_file = r"C:\Users\USUARIO\Desktop\motor HPR\motor HPR\HPR\src\desktop\app.py"
abs_bad = os.path.abspath(bad_file)
print(f"Bad __file__: {abs_bad}")
parent1_bad = os.path.dirname(abs_bad)
parent2_bad = os.path.dirname(parent1_bad)
print(f"After 1 dirname: {parent1_bad}")
print(f"After 2 dirname: {parent2_bad}")
# This would insert "C:\Users\USUARIO\Desktop\motor HPR\motor HPR\HPR\src"

print("\n=== Scenario 3: Using %~dp0 in batch file ===")
# If batch file uses %~dp0, it gets the directory of the batch script
# Let's say the batch file is at C:\Users\USUARIO\Desktop\motor HPR\test_hpr.bat
batch_dir = r"C:\Users\USUARIO\Desktop\motor HPR"
# %~dp0 would give: C:\Users\USUARIO\Desktop\motor HPR\
# cd /d %~dp0 would change to that directory
# Then Python would resolve __file__ relative to that directory

print(f"If batch uses: cd /d %~dp0")
print(f"  Directory: {batch_dir}")
print(f"  PYTHONPATH: {os.path.join(batch_dir, 'src')}")
print(f"  app.py: {os.path.join(batch_dir, 'src', 'desktop', 'app.py')}")

print("\n=== Key issue ===")
print("The batch file hardcodes the path: C:\\Users\\USUARIO\\Desktop\\motor HPR")
print("If the actual location differs, or if there's a path resolution issue,")
print("Python may resolve __file__ incorrectly.")
print("")
print("Fix: Use %~dp0 to make the batch file self-contained relative to its location")
print("      and avoid hardcoded absolute paths.")