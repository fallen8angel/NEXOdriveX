# AI2-style NEXO Mando radar track helper.
#
# This keeps the patch focused on AI2-safe NEXO behavior.
# It does not modify car.capnp and does not add SCC vision object fields.

from opendbc.car.hyundai.values import CAR

try:
  from opendbc.car.isotp_parallel_query import IsoTpParallelQuery
except Exception:
  from openpilot.selfdrive.car.isotp_parallel_query import IsoTpParallelQuery


def enable_radar_tracks(CP, can_recv, can_send):
  if CP.carFingerprint != CAR.HYUNDAI_NEXO:
    return

  if not CP.openpilotLongitudinalControl:
    return

  print("NEXO AI2: try to enable radar tracks")
  rdr_fw_address = 0x7d0

  try:
    for i in range(20):
      try:
        query = IsoTpParallelQuery(can_send, can_recv, CP.sccBus, [rdr_fw_address], [b"\x10\x07"], [b"\x50\x07"])
        for _addr, _dat in query.get_data(0.1).items():
          new_config = b"\x00\x00\x00\x01\x00\x01"
          data_id = b"\x01\x42"
          write_dat_request = b"\x2e"
          write_dat_response = b"\x6e"
          query = IsoTpParallelQuery(can_send, can_recv, CP.sccBus, [rdr_fw_address], [write_dat_request + data_id + new_config], [write_dat_response])
          query.get_data(0)
          print(f"NEXO AI2: radar tracks enable try {i + 1}")
          break
        break
      except Exception as e:
        print(f"NEXO AI2: radar tracks enable failed {i}: {e}")
  except Exception as e:
    print("NEXO AI2: failed to enable radar tracks " + str(e))

  print("NEXO AI2: end radar tracks enable")
