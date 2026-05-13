from pathlib import Path

from drone_toolkit.app.integration_wiring import PX4SITLScenarioHarnessV1


def test_failsafe_geofence_breach_transitions_to_hold_or_rth():
    harness = PX4SITLScenarioHarnessV1(artifact_dir="artifacts/sitl")
    result = harness.run_scenario(
        scenario_id="failsafe_geofence_breach",
        mission_plan={
            "mission_id": "m1-geofence",
            "geofence": {"type": "cylinder", "radius_m": 30.0},
        },
        expected_terminal_states=["HOLD", "RTH"],
        expected_failsafe_events=["GEOFENCE_BREACH"],
        runtime_state_sequence=["IDLE", "PRECHECK", "ARMED", "ENROUTE", "HOLD"],
        runtime_event_sequence=[
            {
                "kind": "GEOFENCE_BREACH",
                "severity": "critical",
                "source": "runtime",
            }
        ],
        metadata={"scenario_type": "failsafe"},
    )

    assert result.passed is True
    assert result.final_state in {"HOLD", "RTH"}
    assert Path(result.artifact_paths["json_trace"]).exists()
