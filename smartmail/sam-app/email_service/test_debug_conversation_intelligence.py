"""Unit tests for the local conversation-intelligence debug CLI."""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import debug_conversation_intelligence as debug_cli


class TestDebugConversationIntelligenceCLI(unittest.TestCase):
    def test_read_message_prefers_inline_message(self):
        parser = debug_cli.build_parser()
        args = parser.parse_args(["--message", "Travel week"])

        self.assertEqual(debug_cli._read_message(args), "Travel week")

    def test_read_message_uses_file_input(self):
        parser = debug_cli.build_parser()
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("Finished my FTP test today.")
            path = handle.name
        self.addCleanup(lambda: os.remove(path) if os.path.exists(path) else None)

        args = parser.parse_args(["--file", path])
        self.assertEqual(debug_cli._read_message(args), "Finished my FTP test today.")

    def test_read_message_uses_stdin_fallback(self):
        parser = debug_cli.build_parser()
        args = parser.parse_args([])

        self.assertEqual(
            debug_cli._read_message(args, stdin_text="Only two days this week"),
            "Only two days this week",
        )

    def test_main_requires_openai_api_key(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = debug_cli.main(["--message", "Hello"])

        self.assertEqual(exit_code, 2)
        self.assertIn("OPENAI_API_KEY is required", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")

    def test_main_rejects_empty_message(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = debug_cli.main([], stdin_text="   ")

        self.assertEqual(exit_code, 2)
        self.assertIn("No message provided", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")

    def test_main_reports_missing_file(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = debug_cli.main(["--file", "/tmp/does-not-exist-smartmail.txt"])

        self.assertEqual(exit_code, 2)
        self.assertIn("Message file not found", stderr.getvalue())

    def test_main_prints_pretty_json_with_raw_message(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             mock.patch.object(
                 debug_cli,
                 "analyze_conversation_intelligence",
                 return_value={
                     "intent": "availability_update",
                     "complexity_score": 3,
                     "model_name": "gpt-test",
                     "resolution_source": "resolver",
                     "intent_resolution_reason": "priority_resolver",
                     "signals": {"has_availability_constraint": True},
                 },
             ), \
             redirect_stdout(stdout), \
             redirect_stderr(stderr):
            exit_code = debug_cli.main(
                ["--message", "Travel week", "--pretty", "--raw"]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["intent"], "availability_update")
        self.assertEqual(payload["raw_message"], "Travel week")
        self.assertIn("elapsed_ms", payload)

    def test_main_repeat_outputs_list(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             mock.patch.object(
                 debug_cli,
                 "analyze_conversation_intelligence",
                 return_value={
                     "intent": "check_in",
                     "complexity_score": 2,
                     "model_name": "gpt-test",
                     "resolution_source": "judge",
                     "intent_resolution_reason": "ambiguous",
                 },
             ), \
             redirect_stdout(stdout), \
             redirect_stderr(stderr):
            exit_code = debug_cli.main(
                ["--message", "Weekly update", "--repeat", "2"]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["run"], 1)
        self.assertEqual(payload[1]["run"], 2)


if __name__ == "__main__":
    unittest.main()
