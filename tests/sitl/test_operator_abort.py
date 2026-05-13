from pathlib import Path

from drone_toolkit.app.integration_wiring import PX4SITLScenarioHarnessV1


def test_operator_abort_reaches_aborted_terminal_state():
    harness = PX4SITLScenarioHarnessV1(artifact_dir="artifacts/sitl")
    result = harness.run_scenario(
        scenario_id="operator_abort",
        mission_plan={"mission_id": "m1-operator-abort"},
        expected_terminal_states=["ABORTED"],
        expected_failsafe_events=["MISSION_ABORT"],
        runtime_state_sequence=["IDLE", "PRECHECK", "ARMED", "ENROUTE", "ABORTED"],
        runtime_event_sequence=[
            {"kind": "MISSION_ABORT", "severity": "critical", "source": "operator"}
        ],
        metadata={"scenario_type": "abort"},
    )

    assert result.passed is True
    assert result.final_state == "ABORTED"
    assert Path(result.artifact_paths["json_trace"]).exists()
