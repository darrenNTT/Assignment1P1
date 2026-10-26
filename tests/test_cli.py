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
        # block should NOT be printed (per the `if a.prepay_month and
        # a.prepay_amount:` truthy check in main()).
        monkeypatch.setattr(
            "sys.argv",
            ["cli.py", "500000", "9", "60", "--prepay-month", "12"],
        )
        main()
        captured = capsys.readouterr()
        assert "interest_saved" not in captured.out
