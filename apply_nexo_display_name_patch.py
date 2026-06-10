from pathlib import Path

path = Path("opendbc_repo/opendbc/car/hyundai/values.py")
text = path.read_text(encoding="utf-8")
old = 'HyundaiCarDocs("Hyundai Nexo", "All", car_parts=CarParts.common([CarHarness.hyundai_h]))'
new = 'HyundaiCarDocs("Hyundai NEXO", "All", car_parts=CarParts.common([CarHarness.hyundai_h]))'

if old not in text and new in text:
  print("Already patched: Hyundai NEXO display name is already uppercase.")
elif old not in text:
  raise SystemExit("Patch target not found. Please check the HYUNDAI_NEXO block in values.py.")
else:
  path.write_text(text.replace(old, new, 1), encoding="utf-8")
  print("Patched: Hyundai Nexo -> Hyundai NEXO")
