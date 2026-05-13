from pathlib import Path

from drone_toolkit.app.integration_wiring import PX4SITLScenarioHarnessV1


def test_failsafe_low_battery_transitions_to_rth():
    harness = PX4SITLScenarioHarnessV1(artifact_dir="artifacts/sitl")
    result = harness.run_scenario(
        scenario_id="failsafe_low_battery",
        mission_plan={"mission_id": "m1-low-battery"},
        expected_terminal_states=["RTH", "HOLD"],
        expected_failsafe_events=["LOW_BATTERY"],
        runtime_state_sequence=["IDLE", "PRECHECK", "ARMED", "ENROUTE", "RTH"],
        runtime_event_sequence=[
            {"kind": "LOW_BATTERY", "severity": "warning", "source": "telemetry"}
        ],
        metadata={"scenario_type": "failsafe"},
    )

    assert result.passed is True
    assert result.final_state in {"RTH", "HOLD"}
    assert Path(result.artifact_paths["json_trace"]).exists()
