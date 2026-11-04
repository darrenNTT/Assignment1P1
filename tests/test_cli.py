"""
Test suite for cli.py's main() entry point.

NOTE: Some tests in this file are EXPECTED TO FAIL against the current
implementation, intentionally revealing bugs that already exist in the
underlying calculator functions (e.g. the amortisation_schedule()
off-by-one bug surfaces here as a schedule row count mismatch at the
CLI output level). No source files are modified by this test suite.
"""
import json

from cli import main


class TestMainNormalExecution:
    def test_main_prints_summary_json(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["cli.py", "500000", "9", "60"])
        main()
        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert output["currency"] == "INR"
        assert "emi" in output

    def test_main_summary_only_single_json_block(self, monkeypatch, capsys):
        # Without --schedule or prepay args, only one JSON block should print
        monkeypatch.setattr("sys.argv", ["cli.py", "500000", "9", "60"])
        main()
        captured = capsys.readouterr()
        # Should parse as exactly one JSON object with no trailing content
        output = json.loads(captured.out.strip())
        assert isinstance(output, dict)


class TestMainScheduleFlag:
    def test_main_with_schedule_prints_rows(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["cli.py", "100000", "9", "12", "--schedule"])
        main()
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")

        # Count how many printed lines are schedule-row dict reprs
        # (identified by the "'month':" key appearing in the line).
        schedule_row_lines = [line for line in lines if "'month':" in line]

        # BUG: amortisation_schedule() currently returns tenure_months - 1
        # rows (verified: amortisation_schedule(100_000, 9, 12) returns 11
        # rows, not 12), so this CLI-level assertion is EXPECTED TO FAIL
        # against the current implementation, surfacing the same
        # off-by-one bug at the CLI output level.
        assert len(schedule_row_lines) == 12


class TestMainPrepaymentArgs:
    def test_main_with_prepayment_prints_savings_json(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "sys.argv",
            ["cli.py", "500000", "9", "60", "--prepay-month", "12", "--prepay-amount", "50000"],
        )
        main()
        captured = capsys.readouterr()
        assert "interest_saved" in captured.out
        assert "months_saved" in captured.out

    def test_main_without_both_prepay_args_skips_prepayment_output(self, monkeypatch, capsys):
        # Only --prepay-month supplied, --prepay-amount omitted -> prepayment
        # block should NOT be printed (per the `if a.prepay_month is not
        # None and a.prepay_amount is not None:` check in main()).
        monkeypatch.setattr(
            "sys.argv",
            ["cli.py", "500000", "9", "60", "--prepay-month", "12"],
        )
        main()
        captured = capsys.readouterr()
        assert "interest_saved" not in captured.out

    def test_main_with_zero_prepay_amount_still_prints_prepayment_output(self, monkeypatch, capsys):
        # Regression test for a CLI bug found during manual smoke testing:
        # main() originally checked `if a.prepay_month and
        # a.prepay_amount:`, a truthy check. Since 0 is falsy in Python,
        # passing --prepay-amount 0 (a legitimate, explicit value meaning
        # "no prepayment") caused the entire prepayment JSON block to be
        # skipped, even though --prepay-month was supplied. This was
        # fixed by changing the check to `is not None` comparisons, which
        # correctly distinguish "argument omitted" (None) from "argument
        # explicitly set to zero" (0). This test asserts the prepayment
        # block IS printed for --prepay-amount 0, with the exact values
        # expected for a zero-amount prepayment (see PROMPT_LOG.md).
        monkeypatch.setattr(
            "sys.argv",
            ["cli.py", "500000", "9", "60", "--prepay-month", "12", "--prepay-amount", "0"],
        )
        main()
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # The output is two JSON blocks printed back-to-back (summary,
        # then prepayment savings). Split on the second block's opening
        # brace to parse it independently.
        full_output = captured.out
        second_block_start = full_output.index("{", full_output.index("}") + 1)
        prepayment_output = json.loads(full_output[second_block_start:])

        assert prepayment_output["interest_saved"] == 0.0
        assert prepayment_output["months_saved"] == 0
        assert prepayment_output["new_tenure"] == 60
