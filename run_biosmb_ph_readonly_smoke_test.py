from helpers.biosmb_emulator import local_biosmb_manager


PUMP_STREAMS = {
    2: "acetic acid",
    3: "sodium acetate",
    4: "Arium water",
}
PH_VALVES = ["P2", "P3", "P4"]


inlet_names = ["", "Acetic acid", "Sodium acetate", "Arium water", "", "", ""]
outlet_names = ["PH_2 measurement", "", "", "", "", ""]


with local_biosmb_manager(
    port=4865,
    inlet_names=inlet_names,
    outlet_names=outlet_names,
) as biosmb:
    flows = biosmb.get_all_flows()

    print("Pump readbacks")
    for pump_number, stream_name in PUMP_STREAMS.items():
        flow = flows[pump_number - 1]
        print(f"pump {pump_number}: {stream_name}, {flow:.3f} mL/min")

    print("\nValve states")
    for valve_name in PH_VALVES:
        state = biosmb.get_valve(valve_name)
        print(f"{valve_name}: {state.name.lower()}")

    current_ph = biosmb.get_ph(2)
    print(f"\ncurrent pH from PH_2: {current_ph:.4f}")

    sensors = biosmb.get_all_sensors()
    print("\nSensor keys")
    print(", ".join(sorted(sensors.keys())))

print("\nRead-only emulator smoke test complete.")
print("No pump enables, flow writes, or valve-open commands were issued.")
