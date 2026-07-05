import pytest
from backend.queue.progress import ProgressReporter

def test_progress_reporter_monotonic_percentage():
    reporter = ProgressReporter()
    p1 = reporter.calculate_progress("downloading", 0.5)
    p2 = reporter.calculate_progress("transcribing", 0.1)
    assert p2 >= p1
    assert p1 >= 0
    assert p2 <= 100

def test_eta_calculation_sane():
    reporter = ProgressReporter()
    eta = reporter.calculate_eta(elapsed_seconds=10.0, progress_percent=50)
    assert eta == 10
    
    eta_zero = reporter.calculate_eta(elapsed_seconds=5.0, progress_percent=0)
    assert eta_zero is None
