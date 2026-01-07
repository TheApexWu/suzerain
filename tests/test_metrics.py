"""
Metrics module tests - verify local analytics tracking works correctly.

"Whatever exists without my knowledge exists without my consent."
"""

import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.metrics import (
    AggregateMetrics,
    CommandRecord,
    MetricsManager,
    SessionMetrics,
    display_stats,
    format_latency,
    generate_sparkline,
    get_metrics_manager,
    reset_metrics_manager,
)


class TestCommandRecord:
    """Test CommandRecord data class."""

    def test_create_command_record(self):
        """Test creating a command record."""
        record = CommandRecord(
            phrase="the judge smiled",
            timestamp=time.time(),
            success=True,
            match_score=95,
            latency_stt_ms=450.0,
            latency_parse_ms=2.5,
            latency_claude_ms=12000.0
        )
        assert record.phrase == "the judge smiled"
        assert record.success is True
        assert record.match_score == 95

    def test_command_record_to_dict(self):
        """Test serializing command record to dict."""
        record = CommandRecord(
            phrase="test phrase",
            timestamp=1704067200.0,
            success=True,
            match_score=90,
            latency_stt_ms=500.0,
            latency_parse_ms=5.0,
            latency_claude_ms=10000.0
        )
        data = record.to_dict()
        assert data["phrase"] == "test phrase"
        assert data["timestamp"] == 1704067200.0
        assert data["success"] is True

    def test_command_record_from_dict(self):
        """Test deserializing command record from dict."""
        data = {
            "phrase": "test phrase",
            "timestamp": 1704067200.0,
            "success": False,
            "match_score": 75,
            "latency_stt_ms": 600.0,
            "latency_parse_ms": 3.0,
            "latency_claude_ms": 8000.0
        }
        record = CommandRecord.from_dict(data)
        assert record.phrase == "test phrase"
        assert record.success is False
        assert record.match_score == 75


class TestSessionMetrics:
    """Test SessionMetrics class."""

    def test_create_session(self):
        """Test creating a new session."""
        session = SessionMetrics(
            session_id="test_session_123",
            start_time=time.time()
        )
        assert session.session_id == "test_session_123"
        assert session.commands_executed == 0
        assert session.commands_succeeded == 0

    def test_record_successful_command(self):
        """Test recording a successful command."""
        session = SessionMetrics(
            session_id="test",
            start_time=time.time()
        )
        session.record_command(
            phrase="the judge smiled",
            success=True,
            match_score=95,
            stt_ms=500.0,
            parse_ms=2.0,
            claude_ms=10000.0
        )
        assert session.commands_executed == 1
        assert session.commands_succeeded == 1
        assert session.commands_failed == 0
        assert len(session.command_records) == 1

    def test_record_failed_command(self):
        """Test recording a failed command."""
        session = SessionMetrics(
            session_id="test",
            start_time=time.time()
        )
        session.record_command(
            phrase="the evening redness",
            success=False,
            match_score=85,
            stt_ms=400.0,
            parse_ms=1.5,
            claude_ms=5000.0
        )
        assert session.commands_executed == 1
        assert session.commands_succeeded == 0
        assert session.commands_failed == 1

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        session = SessionMetrics(
            session_id="test",
            start_time=time.time()
        )
        # Record 3 successful, 1 failed
        for _ in range(3):
            session.record_command("test", True, 90)
        session.record_command("test", False, 80)

        assert session.success_rate == 75.0  # 3/4 = 75%

    def test_success_rate_empty(self):
        """Test success rate with no commands."""
        session = SessionMetrics(
            session_id="test",
            start_time=time.time()
        )
        assert session.success_rate == 0.0

    def test_average_latencies(self):
        """Test average latency calculations."""
        session = SessionMetrics(
            session_id="test",
            start_time=time.time()
        )
        session.record_command("test1", True, 90, stt_ms=400.0, parse_ms=2.0, claude_ms=10000.0)
        session.record_command("test2", True, 85, stt_ms=600.0, parse_ms=4.0, claude_ms=14000.0)

        assert session.avg_stt_ms == 500.0  # (400 + 600) / 2
        assert session.avg_parse_ms == 3.0  # (2 + 4) / 2
        assert session.avg_claude_ms == 12000.0  # (10000 + 14000) / 2

    def test_session_duration(self):
        """Test session duration calculation."""
        start = time.time()
        session = SessionMetrics(
            session_id="test",
            start_time=start
        )
        time.sleep(0.1)  # Brief delay
        session.end_session()

        assert session.session_duration_s >= 0.1

    def test_session_serialization(self):
        """Test session to_dict and from_dict."""
        session = SessionMetrics(
            session_id="test_serialize",
            start_time=1704067200.0
        )
        session.record_command("phrase1", True, 90, 500.0, 2.0, 10000.0)

        data = session.to_dict()
        restored = SessionMetrics.from_dict(data)

        assert restored.session_id == "test_serialize"
        assert restored.commands_executed == 1
        assert len(restored.command_records) == 1


class TestAggregateMetrics:
    """Test AggregateMetrics class."""

    def test_create_aggregate(self):
        """Test creating aggregate metrics."""
        agg = AggregateMetrics()
        assert agg.total_commands == 0
        assert agg.success_rate == 0.0

    def test_success_rate(self):
        """Test aggregate success rate."""
        agg = AggregateMetrics(
            total_commands=100,
            total_succeeded=85,
            total_failed=15
        )
        assert agg.success_rate == 85.0

    def test_average_latencies(self):
        """Test aggregate average latencies."""
        agg = AggregateMetrics(
            total_commands=10,
            total_stt_ms=5000.0,
            total_parse_ms=30.0,
            total_claude_ms=100000.0
        )
        assert agg.avg_stt_ms == 500.0
        assert agg.avg_parse_ms == 3.0
        assert agg.avg_claude_ms == 10000.0

    def test_get_top_commands(self):
        """Test getting top commands by frequency."""
        agg = AggregateMetrics()
        agg.command_frequency = {
            "the judge smiled": 50,
            "they rode on": 30,
            "evening redness": 20,
            "draw the sucker": 10
        }
        top = agg.get_top_commands(3)
        assert len(top) == 3
        assert top[0] == ("the judge smiled", 50)
        assert top[1] == ("they rode on", 30)
        assert top[2] == ("evening redness", 20)

    def test_get_peak_hours(self):
        """Test getting peak usage hours."""
        agg = AggregateMetrics()
        agg.hourly_usage = {9: 50, 10: 80, 14: 60, 15: 40}
        peaks = agg.get_peak_hours(2)
        assert len(peaks) == 2
        assert peaks[0] == (10, 80)
        assert peaks[1] == (14, 60)

    def test_get_last_n_days_usage(self):
        """Test getting usage for last N days."""
        agg = AggregateMetrics()
        today = datetime.now().date()
        yesterday = (today - timedelta(days=1)).isoformat()
        today_str = today.isoformat()
        agg.daily_usage = {
            yesterday: 15,
            today_str: 20
        }
        last_7 = agg.get_last_n_days_usage(7)
        assert len(last_7) == 7
        # Most recent day should be last in list
        assert last_7[-1][0] == today_str
        assert last_7[-1][1] == 20

    def test_aggregate_serialization(self):
        """Test aggregate to_dict and from_dict."""
        agg = AggregateMetrics(
            total_commands=100,
            total_succeeded=90,
            total_failed=10,
            total_sessions=5
        )
        agg.command_frequency = {"test": 50}
        agg.hourly_usage[10] = 25

        data = agg.to_dict()
        restored = AggregateMetrics.from_dict(data)

        assert restored.total_commands == 100
        assert restored.total_succeeded == 90
        assert restored.command_frequency.get("test") == 50


class TestMetricsManager:
    """Test MetricsManager class."""

    @pytest.fixture
    def temp_metrics_file(self):
        """Create a temporary metrics file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            yield Path(f.name)
        # Cleanup
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_create_manager(self, temp_metrics_file):
        """Test creating a metrics manager."""
        manager = MetricsManager(metrics_file=temp_metrics_file)
        assert manager.aggregate.total_commands == 0

    def test_start_session(self, temp_metrics_file):
        """Test starting a metrics session."""
        manager = MetricsManager(metrics_file=temp_metrics_file)
        session = manager.start_session()
        assert session is not None
        assert session.session_id.startswith("session_")

    def test_record_command(self, temp_metrics_file):
        """Test recording a command."""
        manager = MetricsManager(metrics_file=temp_metrics_file)
        manager.start_session()

        manager.record_command(
            phrase="the judge smiled",
            success=True,
            match_score=95,
            stt_ms=500.0,
            parse_ms=2.0,
            claude_ms=10000.0
        )

        assert manager.aggregate.total_commands == 1
        assert manager.aggregate.total_succeeded == 1
        assert manager.aggregate.command_frequency.get("the judge smiled") == 1

    def test_record_multiple_commands(self, temp_metrics_file):
        """Test recording multiple commands."""
        manager = MetricsManager(metrics_file=temp_metrics_file)
        manager.start_session()

        manager.record_command("phrase1", True, 90, 400.0, 2.0, 8000.0)
        manager.record_command("phrase1", True, 92, 500.0, 1.5, 9000.0)
        manager.record_command("phrase2", False, 75, 450.0, 2.5, 7000.0)

        assert manager.aggregate.total_commands == 3
        assert manager.aggregate.total_succeeded == 2
        assert manager.aggregate.total_failed == 1
        assert manager.aggregate.command_frequency.get("phrase1") == 2
        assert manager.aggregate.command_frequency.get("phrase2") == 1

    def test_end_session(self, temp_metrics_file):
        """Test ending a session."""
        manager = MetricsManager(metrics_file=temp_metrics_file)
        session = manager.start_session()
        manager.record_command("test", True, 90)

        ended_session = manager.end_session()

        assert ended_session is session
        assert ended_session.end_time is not None
        assert manager.get_current_session() is None
        assert manager.aggregate.total_sessions == 1

    def test_persistence(self, temp_metrics_file):
        """Test that metrics persist across manager instances."""
        # First manager records some data
        manager1 = MetricsManager(metrics_file=temp_metrics_file)
        manager1.record_command("test phrase", True, 90, 500.0, 2.0, 10000.0)
        manager1.record_command("test phrase", False, 80, 600.0, 3.0, 8000.0)

        # New manager should load the same data
        manager2 = MetricsManager(metrics_file=temp_metrics_file)

        assert manager2.aggregate.total_commands == 2
        assert manager2.aggregate.total_succeeded == 1
        assert manager2.aggregate.total_failed == 1

    def test_hourly_usage_tracking(self, temp_metrics_file):
        """Test that hourly usage is tracked."""
        manager = MetricsManager(metrics_file=temp_metrics_file)
        manager.record_command("test", True, 90)

        current_hour = datetime.now().hour
        assert manager.aggregate.hourly_usage[current_hour] >= 1

    def test_daily_usage_tracking(self, temp_metrics_file):
        """Test that daily usage is tracked."""
        manager = MetricsManager(metrics_file=temp_metrics_file)
        manager.record_command("test", True, 90)

        today = datetime.now().date().isoformat()
        assert manager.aggregate.daily_usage[today] >= 1

    def test_match_score_distribution(self, temp_metrics_file):
        """Test match score distribution bucketing."""
        manager = MetricsManager(metrics_file=temp_metrics_file)

        # Record commands with different scores
        manager.record_command("test1", True, 65)  # <70
        manager.record_command("test2", True, 75)  # 70-79
        manager.record_command("test3", True, 85)  # 80-89
        manager.record_command("test4", True, 95)  # 90-100

        assert manager.aggregate.match_score_distribution.get("<70") == 1
        assert manager.aggregate.match_score_distribution.get("70-79") == 1
        assert manager.aggregate.match_score_distribution.get("80-89") == 1
        assert manager.aggregate.match_score_distribution.get("90-100") == 1

    def test_reset_aggregate(self, temp_metrics_file):
        """Test resetting aggregate metrics."""
        manager = MetricsManager(metrics_file=temp_metrics_file)
        manager.record_command("test", True, 90)

        manager.reset_aggregate()

        assert manager.aggregate.total_commands == 0


class TestDisplayFunctions:
    """Test display and formatting functions."""

    def test_format_latency_milliseconds(self):
        """Test formatting latency in milliseconds."""
        assert format_latency(500.0) == "500ms"
        assert format_latency(0.0) == "0ms"
        assert format_latency(999.0) == "999ms"

    def test_format_latency_seconds(self):
        """Test formatting latency in seconds."""
        assert format_latency(1000.0) == "1.0s"
        assert format_latency(2500.0) == "2.5s"
        assert format_latency(12400.0) == "12.4s"

    def test_generate_sparkline_empty(self):
        """Test sparkline with empty values."""
        sparkline = generate_sparkline([])
        assert len(sparkline) == 7  # Default width

    def test_generate_sparkline_values(self):
        """Test sparkline with values."""
        values = [1, 3, 5, 2, 7, 4, 6]
        sparkline = generate_sparkline(values)
        assert len(sparkline) == 7
        # Should contain block characters
        assert any(ord(c) >= 0x2581 for c in sparkline)

    def test_generate_sparkline_all_zeros(self):
        """Test sparkline with all zero values."""
        values = [0, 0, 0, 0, 0, 0, 0]
        sparkline = generate_sparkline(values)
        assert len(sparkline) == 7

    def test_display_stats_empty(self):
        """Test display stats with no data."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)

        try:
            manager = MetricsManager(metrics_file=temp_path)
            output = display_stats(manager)

            assert "SUZERAIN STATS" in output
            assert "Total commands:" in output
            assert "0" in output  # No commands
        finally:
            os.unlink(temp_path)

    def test_display_stats_with_data(self):
        """Test display stats with recorded data."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)

        try:
            manager = MetricsManager(metrics_file=temp_path)
            manager.record_command("the judge smiled", True, 95, 500.0, 2.0, 10000.0)
            manager.record_command("they rode on", True, 90, 450.0, 1.5, 8000.0)

            output = display_stats(manager)

            assert "SUZERAIN STATS" in output
            assert "Total commands:" in output
            assert "2" in output
            assert "100.0%" in output  # 100% success rate
            assert "the judge smiled" in output or "they rode on" in output
        finally:
            os.unlink(temp_path)


class TestGlobalInstance:
    """Test global metrics manager instance."""

    def test_get_metrics_manager(self):
        """Test getting global metrics manager."""
        reset_metrics_manager()
        manager = get_metrics_manager()
        assert manager is not None
        assert isinstance(manager, MetricsManager)

    def test_get_same_instance(self):
        """Test that get_metrics_manager returns same instance."""
        reset_metrics_manager()
        manager1 = get_metrics_manager()
        manager2 = get_metrics_manager()
        assert manager1 is manager2

    def test_reset_metrics_manager(self):
        """Test resetting global metrics manager."""
        reset_metrics_manager()
        manager1 = get_metrics_manager()
        reset_metrics_manager()
        manager2 = get_metrics_manager()
        assert manager1 is not manager2


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_corrupted_metrics_file(self):
        """Test handling of corrupted metrics file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {{{")
            temp_path = Path(f.name)

        try:
            manager = MetricsManager(metrics_file=temp_path)
            # Should start fresh instead of crashing
            assert manager.aggregate.total_commands == 0
        finally:
            os.unlink(temp_path)

    def test_missing_metrics_file(self):
        """Test handling of missing metrics file."""
        temp_path = Path("/tmp/nonexistent_metrics_12345.json")
        if temp_path.exists():
            temp_path.unlink()

        manager = MetricsManager(metrics_file=temp_path)
        assert manager.aggregate.total_commands == 0

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_very_long_phrase(self):
        """Test handling of very long phrases."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)

        try:
            manager = MetricsManager(metrics_file=temp_path)
            long_phrase = "x" * 1000
            manager.record_command(long_phrase, True, 90)

            assert manager.aggregate.command_frequency.get(long_phrase) == 1
        finally:
            os.unlink(temp_path)

    def test_negative_latencies(self):
        """Test handling of negative latencies (shouldn't happen but be safe)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)

        try:
            manager = MetricsManager(metrics_file=temp_path)
            # Negative latencies shouldn't crash
            manager.record_command("test", True, 90, -100.0, -50.0, -1000.0)
            assert manager.aggregate.total_commands == 1
        finally:
            os.unlink(temp_path)
