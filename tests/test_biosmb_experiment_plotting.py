"""Tests for reusable BioSMB experiment preparation and plotting."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from helpers.biosmb_experiment_data import (
    BLOCK_COLUMN,
    FLOW_COLUMNS,
    PH2_COLUMN,
    SCHEDULE_COLUMN,
    TIME_COLUMN,
    aggregate_time_bins,
    assign_reconstructed_schedule,
    build_mass_flow_intervals,
    default_stream_specs,
    detect_controller_actions,
    ping_pong_targets,
)
from helpers.biosmb_experiment_plotting import (
    plot_mass_flow_intervals,
    plot_minute_tracking_and_inputs,
    plot_seconds_tracking_and_inputs,
)


def make_experiment_data() -> pd.DataFrame:
    """Return deterministic 121-second data with two controlled actions."""

    elapsed = np.arange(121, dtype=float)
    timestamps = pd.Timestamp("2026-08-07T10:00:00Z") + pd.to_timedelta(
        elapsed,
        unit="s",
    )
    acid_flow = np.where(
        elapsed < 30.0,
        5.0,
        np.where(elapsed < 90.0, 6.0, 4.0),
    )
    sodium_flow = np.where(
        elapsed < 30.0,
        4.0,
        np.where(elapsed < 90.0, 3.0, 5.0),
    )
    water_flow = np.full_like(elapsed, 5.0)
    data = pd.DataFrame(
        {
            TIME_COLUMN: timestamps,
            PH2_COLUMN: 4.3 + 0.002 * elapsed,
            "mfcs-mass.acid-mass-grams": 1000.0 - 5.0 * elapsed / 60.0,
            "mfcs-mass.sodium-mass-grams": 1100.0 - 4.0 * elapsed / 60.0,
            "mfcs-mass.water-mass-grams": 1200.0 + 0.1 * elapsed / 60.0,
            "elapsed_seconds": elapsed,
        }
    )
    for column in FLOW_COLUMNS:
        data[column] = 0.0
    data["biosmb-flows[0]"] = acid_flow
    data["biosmb-flows[1]"] = sodium_flow
    data["biosmb-flows[3]"] = water_flow
    return data


class BioSMBExperimentPlottingTests(unittest.TestCase):
    def test_ping_pong_targets_repeat_without_duplicate_endpoints(self) -> None:
        sequence = ping_pong_targets([3.9, 4.3, 4.7], 8)
        np.testing.assert_allclose(
            sequence,
            [3.9, 4.3, 4.7, 4.3, 3.9, 4.3, 4.7, 4.3],
        )

    def test_schedule_assignment_uses_detected_action_blocks(self) -> None:
        data = make_experiment_data()
        streams = default_stream_specs()
        events = detect_controller_actions(data, stream_specs=streams)
        prepared, scheduled_events = assign_reconstructed_schedule(
            data,
            events,
            target_values=[3.9, 4.3, 4.7],
            steps_per_setpoint=1,
        )

        self.assertEqual(events["sample_index"].tolist(), [30, 90])
        self.assertEqual(scheduled_events[BLOCK_COLUMN].tolist(), [0, 1])
        self.assertEqual(
            scheduled_events[SCHEDULE_COLUMN].tolist(),
            [3.9, 4.3],
        )
        self.assertEqual(prepared.loc[0, SCHEDULE_COLUMN], 3.9)
        self.assertEqual(prepared.loc[89, SCHEDULE_COLUMN], 3.9)
        self.assertEqual(prepared.loc[90, SCHEDULE_COLUMN], 4.3)

    def test_mass_flow_intervals_preserve_sign_units_and_invalid_water(
        self,
    ) -> None:
        data = make_experiment_data()
        streams = default_stream_specs(water_mass_valid=False)
        intervals = build_mass_flow_intervals(
            data,
            interval_seconds=60.0,
            stream_specs=streams,
            densities_g_ml={
                "acid": 1.0,
                "sodium_acetate": 1.0,
                "water": 1.0,
            },
        )

        acid = intervals.loc[intervals["stream"].eq("acid")]
        sodium = intervals.loc[intervals["stream"].eq("sodium_acetate")]
        water = intervals.loc[intervals["stream"].eq("water")]
        np.testing.assert_allclose(acid["actual_flow_ml_min"], 5.0)
        np.testing.assert_allclose(sodium["actual_flow_ml_min"], 4.0)
        self.assertTrue(water["actual_flow_ml_min"].isna().all())
        self.assertTrue((water["mass_derived_flow_ml_min"] < 0.0).all())
        np.testing.assert_allclose(intervals["duration_seconds"], 60.0)

    def test_minute_aggregation_is_separate_from_raw_seconds(self) -> None:
        data = make_experiment_data()
        streams = default_stream_specs()
        events = detect_controller_actions(data, stream_specs=streams)
        prepared, _ = assign_reconstructed_schedule(
            data,
            events,
            target_values=[3.9, 4.3, 4.7],
            steps_per_setpoint=1,
        )
        minute = aggregate_time_bins(
            prepared,
            interval_seconds=60.0,
            stream_specs=streams,
        )

        self.assertEqual(len(prepared), 121)
        self.assertEqual(len(minute), 3)
        self.assertEqual(minute["sample_count"].tolist(), [60, 60, 1])
        self.assertAlmostEqual(
            minute.loc[0, "ph2_mean"],
            np.mean(prepared.loc[:59, PH2_COLUMN]),
            places=12,
        )

    def test_plotting_interfaces_create_separate_resolution_figures(
        self,
    ) -> None:
        data = make_experiment_data()
        streams = default_stream_specs()
        events = detect_controller_actions(data, stream_specs=streams)
        prepared, scheduled_events = assign_reconstructed_schedule(
            data,
            events,
            target_values=[3.9, 4.3, 4.7],
            steps_per_setpoint=1,
        )
        minute = aggregate_time_bins(
            prepared,
            interval_seconds=60.0,
            stream_specs=streams,
        )
        intervals = build_mass_flow_intervals(
            prepared,
            interval_seconds=60.0,
            stream_specs=streams,
            densities_g_ml={
                "acid": 1.0,
                "sodium_acetate": 1.0,
                "water": 1.0,
            },
        )
        generated_at = datetime(2026, 8, 7, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            temporary_path = Path(temp_dir)
            seconds_path = temporary_path / "seconds.png"
            minutes_path = temporary_path / "minutes.png"
            mass_path = temporary_path / "acid.png"

            plot_seconds_tracking_and_inputs(
                prepared,
                scheduled_events,
                streams,
                tolerance=0.1,
                experiment_label="Test",
                figure_path=seconds_path,
                generated_at=generated_at,
            )
            plot_minute_tracking_and_inputs(
                minute,
                scheduled_events,
                streams,
                tolerance=0.1,
                experiment_label="Test",
                figure_path=minutes_path,
                generated_at=generated_at,
            )
            plot_mass_flow_intervals(
                intervals,
                streams[0],
                interval_label="One-Minute",
                experiment_label="Test",
                figure_path=mass_path,
                generated_at=generated_at,
            )

            for path in (seconds_path, minutes_path, mass_path):
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()
