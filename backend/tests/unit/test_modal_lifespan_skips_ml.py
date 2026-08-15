import os
from unittest.mock import patch


def test_lifespan_skips_local_ml_when_modal_configured():
    os.environ["MODAL_WEB_ENDPOINT_URL"] = "https://mock-endpoint.modal.run"
    with patch("backend.main.get_pipeline") as gp, \
         patch("backend.main.get_vad_model") as gv, \
         patch("backend.main.get_bgm_separation_inferencer") as gb:
        from backend.main import maybe_skip_local_ml_warmup
        maybe_skip_local_ml_warmup()
        gp.assert_not_called()
        gv.assert_not_called()
        gb.assert_not_called()
