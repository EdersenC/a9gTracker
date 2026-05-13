from pathlib import Path

from drone_toolkit.app.integration_wiring import PX4SITLScenarioHarnessV1


def _artifact_dir() -> Path:
    return Path("artifacts/sitl")


def test_nominal_waypoint_mission_completes_without_failsafe():
    harness = PX4SITLScenarioHarnessV1(artifact_dir=str(_artifact_dir()))
    result = harness.run_scenario(
        scenario_id="nominal_waypoint",
        mission_plan={
            "mission_id": "m1-nominal",
            "waypoints": [{"lat": 47.3977419, "lon": 8.5455938, "alt_m": 10.0}],
            "rth_policy": {"enabled": True},
        },
        expected_terminal_states=["COMPLETED"],
        expected_failsafe_events=[],
        runtime_state_sequence=["IDLE", "PRECHECK", "ARMED", "ENROUTE", "COMPLETED"],
        runtime_event_sequence=[],
        metadata={"scenario_type": "nominal"},
    )

    assert result.passed is True
    assert result.final_state == "COMPLETED"
    assert Path(result.artifact_paths["json_trace"]).exists()
