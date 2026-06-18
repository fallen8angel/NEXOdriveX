from collections import deque
from cereal import car, log
import cereal.messaging as messaging
from opendbc.car import DT_CTRL, structs
from opendbc.car.interfaces import MAX_CTRL_SPEED
from opendbc.car.volkswagen.values import CarControllerParams as VWCarControllerParams
from opendbc.car.hyundai.interface import ENABLE_BUTTONS as HYUNDAI_ENABLE_BUTTONS
from opendbc.car.hyundai.carstate import PREV_BUTTON_SAMPLES as HYUNDAI_PREV_BUTTON_SAMPLES

from openpilot.selfdrive.selfdrived.events import Events, ET

from openpilot.common.params import Params

ButtonType = structs.CarState.ButtonEvent.Type
GearShifter = structs.CarState.GearShifter
EventName = log.OnroadEvent.EventName
NetworkLocation = structs.CarParams.NetworkLocation


class CarSpecificEvents:
  def __init__(self, CP: structs.CarParams):
    self.CP = CP

    self.steering_unpressed = 0
    self.low_speed_alert = False
    self.no_steer_warning = False
    self.silent_steer_warning = 1

    self.cruise_buttons: deque = deque([], maxlen=HYUNDAI_PREV_BUTTON_SAMPLES)

    self.do_shutdown = False
    self.params = Params()
    self.frame = 0
    self.mute_door = False
    self.mute_seatbelt = False
    self.vCruise_prev = 250
    self.carrotCruise_prev = False

  def update_params(self):
    if self.frame % 100 == 0:
      self.mute_seatbelt = self.params.get_bool("MuteSeatbelt")
      self.mute_door = self.params.get_bool("MuteDoor")
    
  def update(self, CS: car.CarState, CS_prev: car.CarState, CC: car.CarControl):
    self.frame += 1
    self.update_params()
    if self.CP.brand in ('body', 'mock'):
      events = Events()

    elif self.CP.brand == 'ford':
      events = self.create_common_events(CS, CS_prev, extra_gears=[GearShifter.manumatic])

    elif self.CP.brand == 'nissan':
      events = self.create_common_events(CS, CS_prev, extra_gears=[GearShifter.brake])

    elif self.CP.brand == 'chrysler':
      events = self.create_common_events(CS, CS_prev, extra_gears=[GearShifter.low])

      if self.CP.minSteerSpeed > 0. and CS.vEgo < (self.CP.minSteerSpeed + 0.5):
        self.low_speed_alert = True
      elif CS.vEgo > (self.CP.minSteerSpeed + 1.):
        self.low_speed_alert = False
      if self.low_speed_alert:
        events.add(EventName.belowSteerSpeed)

    elif self.CP.brand == 'honda':
      events = self.create_common_events(CS, CS_prev, pcm_enable=False)

      if self.CP.pcmCruise and CS.vEgo < self.CP.minEnableSpeed:
        events.add(EventName.belowEngageSpeed)

      if self.CP.pcmCruise:
        if CS.cruiseState.enabled and not CS_prev.cruiseState.enabled:
          events.add(EventName.pcmEnable)
        elif not CS.cruiseState.enabled and (CC.actuators.accel >= 0. or not self.CP.openpilotLongitudinalControl):
          if CS.vEgo < self.CP.minEnableSpeed + 2.:
            events.add(EventName.speedTooLow)
          else:
            events.add(EventName.cruiseDisabled)
      if self.CP.minEnableSpeed > 0 and CS.vEgo < 0.001:
        events.add(EventName.manualRestart)

    elif self.CP.brand == 'toyota':
      events = self.create_common_events(CS, CS_prev)

      if self.CP.openpilotLongitudinalControl:
        if CS.cruiseState.standstill and not CS.brakePressed:
          events.add(EventName.resumeRequired)
        if CS.vEgo < self.CP.minEnableSpeed:
          events.add(EventName.belowEngageSpeed)
          if CC.actuators.accel > 0.3:
            events.add(EventName.speedTooLow)
          if CS.vEgo < 0.001:
            events.add(EventName.manualRestart)

    elif self.CP.brand == 'gm':
      events = self.create_common_events(CS, CS_prev, extra_gears=[GearShifter.sport, GearShifter.low,
                                                                   GearShifter.eco, GearShifter.manumatic],
                                         pcm_enable=self.CP.pcmCruise)

      if CS.vEgo < self.CP.minEnableSpeed and not (CS.standstill and CS.brake >= 20 and
                                                   self.CP.networkLocation == NetworkLocation.fwdCamera):
        events.add(EventName.belowEngageSpeed)
      if CS.cruiseState.standstill:
        events.add(EventName.resumeRequired)
      if CS.vEgo < self.CP.minSteerSpeed:
        events.add(EventName.belowSteerSpeed)

    elif self.CP.brand == 'volkswagen':
      events = self.create_common_events(CS, CS_prev, extra_gears=[GearShifter.eco, GearShifter.sport, GearShifter.manumatic],
                                         pcm_enable=self.CP.pcmCruise)

      if (self.CP.minSteerSpeed - 1e-3) > VWCarControllerParams.DEFAULT_MIN_STEER_SPEED and CS.vEgo < (self.CP.minSteerSpeed + 1.):
        self.low_speed_alert = True
      elif CS.vEgo > (self.CP.minSteerSpeed + 2.):
        self.low_speed_alert = False
      if self.low_speed_alert:
        events.add(EventName.belowSteerSpeed)

      if self.CP.openpilotLongitudinalControl:
        if CS.vEgo < self.CP.minEnableSpeed + 0.5:
          events.add(EventName.belowEngageSpeed)
        if CC.enabled and CS.vEgo < self.CP.minEnableSpeed:
          events.add(EventName.speedTooLow)

    elif self.CP.brand == 'hyundai':
      # NEXO 실험 모드 지원
      self.cruise_buttons.append(any(ev.type in HYUNDAI_ENABLE_BUTTONS for ev in CS.buttonEvents))
      events = self.create_common_events(CS, CS_prev, extra_gears=(GearShifter.sport, GearShifter.manumatic),
                                         pcm_enable=self.CP.pcmCruise, allow_enable=True, allow_button_cancel=False)

      if CS.vEgo < (self.CP.minSteerSpeed + 2.) and self.CP.minSteerSpeed > 10.:
        self.low_speed_alert = True
      if CS.vEgo > (self.CP.minSteerSpeed + 4.):
        self.low_speed_alert = False
      if self.low_speed_alert:
        events.add(EventName.belowSteerSpeed)

    else:
      events = self.create_common_events(CS, CS_prev)

    if CC.enabled:
      if self.vCruise_prev == 0 and CS.vCruise > 0:
        events.add(EventName.audioPrompt)

    if self.carrotCruise_prev != CS.carrotCruise:
      events.add(EventName.audioPrompt)

    self.carrotCruise_prev = CS.carrotCruise
    self.vCruise_prev = CS.vCruise

    return events

  def create_common_events(self, CS: structs.CarState, CS_prev: car.CarState, extra_gears=None, pcm_enable=True,
                           allow_enable=True, allow_button_cancel=True):
    events = Events()
    
    if CS.doorOpen and not self.mute_door:
      events.add(EventName.doorOpen)
    if CS.seatbeltUnlatched and not self.mute_seatbelt:
      events.add(EventName.seatbeltNotLatched)
    if CS.gearShifter == GearShifter.park:
      events.add(EventName.wrongGear)
    if CS.gearShifter == GearShifter.neutral:
      events.add(EventName.wrongGear)
    if CS.gearShifter == GearShifter.reverse:
      events.add(EventName.reverseGear)
    if not CS.cruiseState.available:
      events.add(EventName.wrongCarMode)
    if CS.espDisabled:
      events.add(EventName.espDisabled)
    if CS.espActive:
      events.add(EventName.espActive)
    if CS.stockFcw:
      events.add(EventName.stockFcw)
    if CS.stockAeb:
      events.add(EventName.stockAeb)
    if CS.vEgo > MAX_CTRL_SPEED:
      events.add(EventName.speedTooHigh)
    if CS.cruiseState.nonAdaptive:
      events.add(EventName.wrongCruiseMode)
    if CS.brakeHoldActive and self.CP.openpilotLongitudinalControl:
      events.add(EventName.brakeHold)
    if CS.parkingBrake:
      events.add(EventName.parkBrake)
    if CS.accFaulted:
      events.add(EventName.accFaulted)
    if CS.steeringPressed:
      events.add(EventName.steerOverride)
    if CS.brakePressed and CS.standstill:
      events.add(EventName.preEnableStandstill)
    if CS.gasPressed:
      events.add(EventName.gasPressedOverride)
    if CS.vehicleSensorsInvalid:
      events.add(EventName.vehicleSensorsInvalid)
    if CS.invalidLkasSetting:
      events.add(EventName.invalidLkasSetting)
    if CS.lowSpeedAlert:
      events.add(EventName.belowSteerSpeed)
    if CS.buttonEnable:
      events.add(EventName.buttonEnable)

    for b in CS.buttonEvents:
      if b.type == ButtonType.cancel and (allow_button_cancel or not self.CP.pcmCruise):
        events.add(EventName.buttonCancel)
        if CS.gearShifter == GearShifter.park and not self.do_shutdown:
          self.do_shutdown = True
          self.params.put_bool("DoShutdown", True)

    self.steering_unpressed = 0 if CS.steeringPressed else self.steering_unpressed + 1
    if CS.steerFaultTemporary:
      if CS.steeringPressed and (not CS_prev.steerFaultTemporary or self.no_steer_warning):
        self.no_steer_warning = True
      else:
        self.no_steer_warning = False

        if self.silent_steer_warning > 0 or CS.standstill or self.steering_unpressed < int(1.5 / DT_CTRL):
          self.silent_steer_warning += 1
          if self.silent_steer_warning > 20:
            events.add(EventName.steerTempUnavailableSilent)
        else:
          events.add(EventName.steerTempUnavailable)
    else:
      self.no_steer_warning = False
      self.silent_steer_warning = 0
    if CS.steerFaultPermanent:
      events.add(EventName.steerUnavailable)

    if pcm_enable:
      if CS.cruiseState.enabled and not CS_prev.cruiseState.enabled and allow_enable:
        events.add(EventName.pcmEnable)
      elif not CS.cruiseState.enabled:
        events.add(EventName.pcmDisable)


    if not self.CP.pcmCruise:
      if CS.activateCruise > 0 and CS_prev.activateCruise <= 0:
        if not events.contains(ET.NO_ENTRY):
          events.add(EventName.buttonEnable)
      elif CS.activateCruise < 0 and CS_prev.activateCruise >= 0:
        events.add(EventName.buttonCancel)
      if CS.softHoldActive > 0:
        events.add(EventName.softHold)

    return events
