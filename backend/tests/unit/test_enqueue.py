import pytest
from unittest.mock import MagicMock, patch

from backend.queue.enqueue import CeleryEnqueueError, enqueue_task, check_redis_broker


def test_check_redis_broker_missing_url():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(CeleryEnqueueError, match="REDIS_URL is not set"):
            check_redis_broker()


def test_enqueue_task_pings_redis_and_uses_ignore_result():
    mock_task = MagicMock()
    with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
        with patch("redis.from_url") as mock_from_url:
            mock_from_url.return_value.ping.return_value = True
            enqueue_task(mock_task, "task-uuid")
    mock_task.apply_async.assert_called_once_with(
        args=("task-uuid",),
        kwargs={},
        ignore_result=True,
    )


def test_enqueue_task_with_kwargs():
    mock_task = MagicMock()
    with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
        with patch("redis.from_url") as mock_from_url:
            mock_from_url.return_value.ping.return_value = True
            enqueue_task(mock_task, batch_id="b1", offset=0)
    mock_task.apply_async.assert_called_once_with(
        args=(),
        kwargs={"batch_id": "b1", "offset": 0},
        ignore_result=True,
    )
