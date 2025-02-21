import shutil
import unittest
from tempfile import mkdtemp

import polars as pl
import polars.testing as plt

from micov._constants import (
    COLUMN_COVERED,
    COLUMN_COVERED_DTYPE,
    COLUMN_GENOME_ID,
    COLUMN_LENGTH,
    COLUMN_LENGTH_DTYPE,
    COLUMN_PERCENT_COVERED,
    COLUMN_PERCENT_COVERED_DTYPE,
    COLUMN_SAMPLE_ID,
    COLUMN_START,
    COLUMN_START_DTYPE,
    COLUMN_STOP,
    COLUMN_STOP_DTYPE,
)
from micov._view import View


def make_cov_pos(d, name):
    (
        pl.LazyFrame(
            [
                ["G1", "S1", 8, 100, 8.0],
                ["G2", "S1", 20, 100, 20.0],
                ["G3", "S1", 30, 100, 30.0],
                ["G3", "S2", 11, 100, 11.0],
                ["G4", "S2", 21, 100, 21.0],
                ["G2", "S3", 52, 100, 52.0],
                ["G3", "S3", 62, 100, 62.0],
                ["G4", "S3", 72, 100, 72.0],
                ["G5", "S3", 82, 100, 82.0],
                ["G4", "S1", 20, 100, 20.0],
            ],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_SAMPLE_ID, str),
                (COLUMN_COVERED, COLUMN_COVERED_DTYPE),
                (COLUMN_LENGTH, COLUMN_LENGTH_DTYPE),
                (COLUMN_PERCENT_COVERED, COLUMN_PERCENT_COVERED_DTYPE),
            ],
        ).sink_parquet(f"{d}/{name}.coverage.parquet")
    )

    (
        pl.LazyFrame(
            [
                ["G1", "S1", 1, 5],
                ["G1", "S1", 6, 10],
                ["G2", "S1", 30, 50],
                ["G3", "S1", 15, 30],
                ["G3", "S1", 75, 90],
                ["G4", "S1", 5, 15],
                ["G4", "S1", 45, 55],
                ["G3", "S2", 1, 11],
                ["G4", "S2", 30, 51],
                ["G2", "S3", 1, 52],
                ["G3", "S3", 1, 62],
                ["G4", "S3", 8, 13],
                ["G4", "S3", 20, 87],
                ["G5", "S3", 10, 92],
            ],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_SAMPLE_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
            ],
        ).sink_parquet(f"{d}/{name}.covered_positions.parquet")
    )


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.d = mkdtemp()
        self.name = "testdata"
        make_cov_pos(self.d, self.name)

        self.md = pl.DataFrame(
            [["S1", "a"], ["S2", "b"], ["S3", "c"], ["S4", "d"], ["S5", "e"]],
            orient="row",
            schema=[(COLUMN_SAMPLE_ID, str), ("foo", str)],
        )
        self.feat = pl.DataFrame(
            [
                [
                    "G1",
                ],
                [
                    "G2",
                ],
                [
                    "G3",
                ],
                [
                    "G4",
                ],
                [
                    "G5",
                ],
                [
                    "G6",
                ],
            ],
            orient="row",
            schema=[(COLUMN_GENOME_ID, str)],
        )

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_view_sample_superset(self):
        v = View(f"{self.d}/{self.name}", self.md, self.feat)

        obs_md = v.metadata().pl()
        obs_cov = v.coverages().pl()
        obs_pos = v.positions().pl()

        exp_md = self.md.filter(pl.col(COLUMN_SAMPLE_ID).is_in(["S1", "S2", "S3"]))
        exp_cov = pl.read_parquet(f"{self.d}/{self.name}.coverage.parquet")
        exp_pos = pl.read_parquet(f"{self.d}/{self.name}.covered_positions.parquet")

        plt.assert_frame_equal(
            obs_md, exp_md, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_cov, exp_cov, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_pos, exp_pos, check_column_order=False, check_row_order=False
        )

    def test_view_sample_subset(self):
        md = self.md.filter(pl.col(COLUMN_SAMPLE_ID).is_in(["S1", "S3", "S5"]))
        v = View(f"{self.d}/{self.name}", md, self.feat)

        obs_md = v.metadata().pl()
        obs_cov = v.coverages().pl()
        obs_pos = v.positions().pl()
        obs_fmd = v.feature_metadata().pl()

        exp_md = md.filter(pl.col(COLUMN_SAMPLE_ID).is_in(["S1", "S3"]))
        exp_cov = pl.read_parquet(f"{self.d}/{self.name}.coverage.parquet").filter(
            pl.col(COLUMN_SAMPLE_ID).is_in(["S1", "S3"])
        )
        exp_pos = pl.read_parquet(
            f"{self.d}/{self.name}.covered_positions.parquet"
        ).filter(pl.col(COLUMN_SAMPLE_ID).is_in(["S1", "S3"]))
        exp_fmd = pl.DataFrame(
            [
                ["G1", 0, 100, 100],
                ["G2", 0, 100, 100],
                ["G3", 0, 100, 100],
                ["G4", 0, 100, 100],
                ["G5", 0, 100, 100],
            ],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
                (COLUMN_LENGTH, COLUMN_LENGTH_DTYPE),
            ],
        )

        plt.assert_frame_equal(
            obs_md, exp_md, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_cov, exp_cov, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_pos, exp_pos, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_fmd, exp_fmd, check_column_order=False, check_row_order=False
        )

    def test_view_constrain_features(self):
        feat = self.feat.filter(pl.col(COLUMN_GENOME_ID).is_in(["G1", "G5", "G6"]))

        v = View(f"{self.d}/{self.name}", self.md, feat)

        obs_md = v.metadata().pl()
        obs_cov = v.coverages().pl()
        obs_pos = v.positions().pl()
        obs_fmd = v.feature_metadata().pl()

        exp_md = self.md.filter(pl.col(COLUMN_SAMPLE_ID).is_in(["S1", "S2", "S3"]))
        exp_cov = pl.read_parquet(f"{self.d}/{self.name}.coverage.parquet").filter(
            pl.col(COLUMN_GENOME_ID).is_in(["G1", "G5"])
        )
        exp_pos = pl.read_parquet(
            f"{self.d}/{self.name}.covered_positions.parquet"
        ).filter(pl.col(COLUMN_GENOME_ID).is_in(["G1", "G5"]))
        exp_fmd = pl.DataFrame(
            [["G1", 0, 100, 100], ["G5", 0, 100, 100]],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
                (COLUMN_LENGTH, COLUMN_LENGTH_DTYPE),
            ],
        )

        plt.assert_frame_equal(
            obs_md, exp_md, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_cov, exp_cov, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_pos, exp_pos, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_fmd, exp_fmd, check_column_order=False, check_row_order=False
        )

    def test_view_constrain_positions_full(self):
        feat = pl.DataFrame(
            [["G1", 0, 1000], ["G5", 0, 1000]],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
            ],
        )
        v = View(f"{self.d}/{self.name}", self.md, feat)

        obs_md = v.metadata().pl()
        obs_cov = v.coverages().pl()
        obs_pos = v.positions().pl()
        obs_fmd = v.feature_metadata().pl()

        exp_md = self.md.filter(pl.col(COLUMN_SAMPLE_ID).is_in(["S1", "S2", "S3"]))
        exp_cov = (
            pl.read_parquet(f"{self.d}/{self.name}.coverage.parquet")
            .filter(pl.col(COLUMN_GENOME_ID).is_in(["G1", "G5"]))
            .with_columns(
                pl.col(COLUMN_LENGTH) * 10, pl.col(COLUMN_PERCENT_COVERED) / 10
            )
        )
        exp_pos = pl.read_parquet(
            f"{self.d}/{self.name}.covered_positions.parquet"
        ).filter(pl.col(COLUMN_GENOME_ID).is_in(["G1", "G5"]))

        # the user is requesting a stop position outside of the size the genome but ok?
        exp_fmd = pl.DataFrame(
            [["G1", 0, 1000, 1000], ["G5", 0, 1000, 1000]],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
                (COLUMN_LENGTH, COLUMN_LENGTH_DTYPE),
            ],
        )

        plt.assert_frame_equal(
            obs_md, exp_md, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_cov, exp_cov, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_pos, exp_pos, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_fmd, exp_fmd, check_column_order=False, check_row_order=False
        )

    def test_view_constrain_positions_none(self):
        feat = pl.DataFrame(
            [["G1", 1000, 2000], ["G5", 1000, 2000]],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
            ],
        )

        with self.assertRaisesRegex(ValueError, "No positions left"):
            View(f"{self.d}/{self.name}", self.md, feat)

    def test_view_constrain_positions_bounds_simple(self):
        feat = pl.DataFrame(
            [["G1", 7, 9], ["G5", 0, 20]],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
            ],
        )
        v = View(f"{self.d}/{self.name}", self.md, feat)

        obs_md = v.metadata().pl()
        obs_cov = v.coverages().pl()
        obs_pos = v.positions().pl()
        obs_fmd = v.feature_metadata().pl()

        exp_md = self.md.filter(pl.col(COLUMN_SAMPLE_ID).is_in(["S1", "S2", "S3"]))

        exp_cov = pl.DataFrame(
            [["G1", "S1", 2, 2, 100.0], ["G5", "S3", 10, 20, 50.0]],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_SAMPLE_ID, str),
                (COLUMN_COVERED, COLUMN_COVERED_DTYPE),
                (COLUMN_LENGTH, COLUMN_LENGTH_DTYPE),
                (COLUMN_PERCENT_COVERED, COLUMN_PERCENT_COVERED_DTYPE),
            ],
        )
        # both start and stop are clipped for G1/S1
        # left bound of G5/S3 is outside of its interval so verify the correct
        # start is retained
        exp_pos = pl.DataFrame(
            [["G1", "S1", 7, 9], ["G5", "S3", 10, 20]],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_SAMPLE_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
            ],
        )
        exp_fmd = pl.DataFrame(
            [["G1", 7, 9, 2], ["G5", 0, 20, 20]],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
                (COLUMN_LENGTH, COLUMN_LENGTH_DTYPE),
            ],
        )

        plt.assert_frame_equal(
            obs_md, exp_md, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_cov, exp_cov, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_pos, exp_pos, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_fmd, exp_fmd, check_column_order=False, check_row_order=False
        )

    def test_view_constrain_positions_bounds_complex(self):
        feat = pl.DataFrame(
            [
                ["G1", 0, 100],
                ["G2", 40, 60],
                ["G3", 40, 60],
                ["G4", 90, 100],
                ["G5", 40, 60],
            ],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
            ],
        )
        v = View(f"{self.d}/{self.name}", self.md, feat)

        obs_md = v.metadata().pl()
        obs_cov = v.coverages().pl()
        obs_pos = v.positions().pl()
        obs_fmd = v.feature_metadata().pl()

        exp_md = self.md.filter(pl.col(COLUMN_SAMPLE_ID).is_in(["S1", "S2", "S3"]))

        exp_cov = pl.DataFrame(
            [
                ["G1", "S1", 8, 100, 8.0],
                ["G2", "S1", 10, 20, 50.0],
                ["G2", "S3", 12, 20, 60.0],
                ["G3", "S3", 20, 20, 100.0],
                ["G5", "S3", 20, 20, 100.0],
            ],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_SAMPLE_ID, str),
                (COLUMN_COVERED, COLUMN_COVERED_DTYPE),
                (COLUMN_LENGTH, COLUMN_LENGTH_DTYPE),
                (COLUMN_PERCENT_COVERED, COLUMN_PERCENT_COVERED_DTYPE),
            ],
        )

        exp_pos = pl.DataFrame(
            [
                ["G1", "S1", 1, 5],
                ["G1", "S1", 6, 10],
                ["G2", "S1", 40, 50],
                ["G2", "S3", 40, 52],
                ["G3", "S3", 40, 60],
                ["G5", "S3", 40, 60],
            ],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_SAMPLE_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
            ],
        )

        exp_fmd = pl.DataFrame(
            [
                ["G1", 0, 100, 100],
                ["G2", 40, 60, 20],
                ["G3", 40, 60, 20],
                ["G5", 40, 60, 20],
            ],
            orient="row",
            schema=[
                (COLUMN_GENOME_ID, str),
                (COLUMN_START, COLUMN_START_DTYPE),
                (COLUMN_STOP, COLUMN_STOP_DTYPE),
                (COLUMN_LENGTH, COLUMN_LENGTH_DTYPE),
            ],
        )

        plt.assert_frame_equal(
            obs_md, exp_md, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_cov, exp_cov, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_pos, exp_pos, check_column_order=False, check_row_order=False
        )
        plt.assert_frame_equal(
            obs_fmd, exp_fmd, check_column_order=False, check_row_order=False
        )


if __name__ == "__main__":
    unittest.main()
