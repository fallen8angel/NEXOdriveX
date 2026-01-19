#!/usr/bin/env python3
import time

import numpy as np

from cereal import car, log, messaging
from common.numpy_fast import interp
from openpilot.common.constants import CV
from openpilot.common.params import Params
from openpilot.system.hardware import HARDWARE
from openpilot.system.manager.process_config import managed_processes
from openpilot.system.hardware import HARDWARE


def _cal_curve_speed(sm, v_ego):
  md = sm['modelV2']
  if len(md.position.x) != 33 or len(md.position.y) != 33:
    return 255.

  x = np.asarray(md.position.x, dtype=np.float64)
  y = np.asarray(md.position.y, dtype=np.float64)

  k = 5
  if len(y) >= k:
    y = np.convolve(y, np.ones(k)/k, mode='same')

  dy = np.gradient(y, x)
  d2y = np.gradient(dy, x)
  curv = d2y / np.power(1.0 + dy*dy, 1.5)

  t_min, t_max = 0.7, 2.5
  x_min = max(8.0, v_ego * t_min)
  x_max = min(80.0, v_ego * t_max)
  mask = (x >= x_min) & (x <= x_max)
  if np.sum(mask) < 8:
    return 255.

  curv = curv[mask]

  # a_y_max = 2.975 - v_ego * 0.0375
  # a_y_max = 1.3
  a_y_max = interp(
    v_ego,
    [0.0, 10.0, 20.0, 30.0, 40.0],  # 0, 36, 72, 108, 144 km/h
    [1.6, 1.45, 1.30, 1.15, 1.05]
  )
  a_y_max = float(np.clip(a_y_max, 0.9, 1.6))
  v_curv = np.sqrt(a_y_max / np.clip(np.abs(curv), 3e-5, None))
  model_speed = float(np.percentile(v_curv, 10) * 0.90)

  min_speed = 32. * CV.KPH_TO_MS
  target = float(max(model_speed, min_speed))

  prev = getattr(_cal_curve_speed, "_prev", 255.0)
  if target < v_ego - 0.3:
    out = target
  elif target > v_ego + 1.0:
    out = 255.0
  else:
    out = prev

  if np.isnan(out):
    out = 255.0

  _cal_curve_speed._prev = out
  return out



if __name__ == "__main__":
  CP = car.CarParams(notCar=True, wheelbase=1, steerRatio=10)
  Params().put("CarParams", CP.to_bytes())

  procs = ['camerad', 'ui', 'modeld', 'calibrationd', 'plannerd', 'dmonitoringmodeld', 'dmonitoringd',
           'navi_controller', 'locationd', 'card']

  HARDWARE.set_power_save(False)

  for p in procs:
    managed_processes[p].start()

  pm = messaging.PubMaster(['controlsState', 'deviceState', 'pandaStates', 'carParams', 'carState', 'carControl'])
  sm = messaging.SubMaster(['modelV2'])

  msgs = {s: messaging.new_message(s) for s in ['controlsState', 'deviceState', 'carParams', 'carControl']}
  msgs['deviceState'].deviceState.started = True
  msgs['deviceState'].deviceState.deviceType = HARDWARE.get_device_type()
  msgs['carParams'].carParams.openpilotLongitudinalControl = True

  msgs['pandaStates'] = messaging.new_message('pandaStates', 1)
  msgs['pandaStates'].pandaStates[0].ignitionLine = True
  msgs['pandaStates'].pandaStates[0].pandaType = log.PandaState.PandaType.dos

  speed = 70. / 3.6
  try:
    while True:
      time.sleep(1 / 100)  # continually send, rate doesn't matter

      sm.update(0)
      curve_speed_ms = _cal_curve_speed(sm, 19.4)
      print(f'curve_speed_ms: {curve_speed_ms}')

      msgs['carState'] = messaging.new_message('carState')
      msgs['carState'].carState.vEgoCluster = speed
      msgs['carState'].carState.vEgo = speed
      #msgs['carControl'].carControl.debugText = "Speed: {}\nTest\nTEST...TEST".format(speed)

      try:
        for s in msgs:
          pm.send(s, msgs[s])
      except:
        pass

  except KeyboardInterrupt:
    for p in procs:
      managed_processes[p].stop()
