#!/usr/bin/env python3
"""
NEXO 실험 모드 지원 설정 스크립트
이 스크립트는 NEXOdriveX에서 NEXO 차량의 실험 모드를 활성화합니다.
"""

from pathlib import Path

def apply_nexo_experimental_support():
  # 1. values.py 업데이트 - NEXO를 EV_CAR에 추가
  values_path = Path("opendbc_repo/opendbc/car/hyundai/values.py")
  if values_path.exists():
    text = values_path.read_text(encoding="utf-8")
    
    # EV_CAR 세트에 NEXO 추가
    if 'EV_CAR = {' in text and 'CAR.NEXO' not in text:
      text = text.replace(
        'EV_CAR = {CAR.IONIQ_EV_2020, CAR.IONIQ_EV_LTD, CAR.KONA_EV, CAR.KIA_NIRO_EV, CAR.KIA_NIRO_EV_2ND_GEN, CAR.KONA_EV_2022,',
        'EV_CAR = {CAR.IONIQ_EV_2020, CAR.IONIQ_EV_LTD, CAR.KONA_EV, CAR.KIA_NIRO_EV, CAR.KIA_NIRO_EV_2ND_GEN, CAR.KONA_EV_2022, CAR.NEXO,'
      )
      values_path.write_text(text, encoding="utf-8")
      print("✓ NEXO를 EV_CAR 세트에 추가했습니다.")
    else:
      print("✓ NEXO는 이미 EV_CAR 세트에 포함되어 있습니다.")
  else:
    print("⚠ values.py를 찾을 수 없습니다.")

  # 2. display name 업데이트
  display_name_patch()

def display_name_patch():
  """NEXO 차량명 업데이트"""
  path = Path("opendbc_repo/opendbc/car/hyundai/values.py")
  if path.exists():
    text = path.read_text(encoding="utf-8")
    old = 'HyundaiCarInfo("Hyundai nexo ", "All"'
    new = 'HyundaiCarInfo("Hyundai NEXO", "All"'
    
    if old in text:
      text = text.replace(old, new, 1)
      path.write_text(text, encoding="utf-8")
      print("✓ NEXO 표시명을 업데이트했습니다.")
    elif new in text:
      print("✓ NEXO 표시명이 이미 업데이트되어 있습니다.")

if __name__ == "__main__":
  print("🚀 NEXOdriveX - NEXO 실험 모드 설정 시작")
  print("-" * 50)
  apply_nexo_experimental_support()
  print("-" * 50)
  print("✓ NEXO 실험 모드 설정 완료")
