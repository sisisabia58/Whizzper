from backend.common.progress import NO_OP_PROGRESS, NoOpProgress


def test_no_op_progress_is_callable():
    p = NoOpProgress()
    assert p(0.5, desc="test") is None
    assert NO_OP_PROGRESS(1.0) is None
