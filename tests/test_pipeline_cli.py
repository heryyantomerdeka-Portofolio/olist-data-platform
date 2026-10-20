
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pipeline


class TestPipelineT6(unittest.TestCase):

    @patch("pipeline.subprocess.run")
    def test_t6_runs_pytest(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["pytest"],
            returncode=0,
        )

        pipeline.run_t6()

        args, kwargs = mock_run.call_args
        command = args[0]

        self.assertEqual(command[0], sys.executable)
        self.assertEqual(
            command[1:4],
            ["-m", "pytest", "tests"],
        )
        self.assertIn("-q", command)
        self.assertEqual(kwargs["check"], False)

    @patch("pipeline.subprocess.run")
    def test_t6_raises_error_when_tests_fail(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["pytest"],
            returncode=2,
        )

        with self.assertRaisesRegex(RuntimeError, "exit code 2"):
            pipeline.run_t6()

    @patch("pipeline.subprocess.run")
    def test_t6_does_not_execute_real_pytest(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["pytest"],
            returncode=0,
        )

        pipeline.run_t6()

        mock_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
