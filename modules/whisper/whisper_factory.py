from typing import Optional
import os

from modules.utils.paths import (
    FASTER_WHISPER_MODELS_DIR,
    DIARIZATION_MODELS_DIR,
    OUTPUT_DIR,
    INSANELY_FAST_WHISPER_MODELS_DIR,
    WHISPER_MODELS_DIR,
    UVR_MODELS_DIR,
)
from modules.whisper.data_classes import WhisperImpl
from modules.utils.logger import get_logger

logger = get_logger()


class WhisperFactory:
    @staticmethod
    def create_whisper_inference(
        whisper_type: str,
        whisper_model_dir: str = WHISPER_MODELS_DIR,
        faster_whisper_model_dir: str = FASTER_WHISPER_MODELS_DIR,
        insanely_fast_whisper_model_dir: str = INSANELY_FAST_WHISPER_MODELS_DIR,
        diarization_model_dir: str = DIARIZATION_MODELS_DIR,
        uvr_model_dir: str = UVR_MODELS_DIR,
        output_dir: str = OUTPUT_DIR,
        endpoint_url: Optional[str] = None,
    ):
        os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
        whisper_type = whisper_type.strip().lower()

        if (
            whisper_type == WhisperImpl.MODAL.value
            or os.environ.get("MODAL_WEB_ENDPOINT_URL")
            or os.environ.get("MODAL_ENDPOINTS")
            or endpoint_url
        ):
            from modules.whisper.modal_whisper_inference import ModalWhisperInference
            logger.info("Using Modal serverless GPU inference pipeline.")
            return ModalWhisperInference(endpoint_url=endpoint_url, output_dir=output_dir)

        import torch
        from modules.whisper.faster_whisper_inference import FasterWhisperInference
        from modules.whisper.whisper_Inference import WhisperInference
        from modules.whisper.insanely_fast_whisper_inference import InsanelyFastWhisperInference

        if whisper_type == WhisperImpl.FASTER_WHISPER.value:
            if torch.xpu.is_available():
                logger.warning(
                    "XPU is detected but faster-whisper only supports CUDA. "
                    "Automatically switching to insanely-whisper implementation."
                )
                return InsanelyFastWhisperInference(
                    model_dir=insanely_fast_whisper_model_dir,
                    output_dir=output_dir,
                    diarization_model_dir=diarization_model_dir,
                    uvr_model_dir=uvr_model_dir,
                )
            return FasterWhisperInference(
                model_dir=faster_whisper_model_dir,
                output_dir=output_dir,
                diarization_model_dir=diarization_model_dir,
                uvr_model_dir=uvr_model_dir,
            )
        if whisper_type == WhisperImpl.WHISPER.value:
            return WhisperInference(
                model_dir=whisper_model_dir,
                output_dir=output_dir,
                diarization_model_dir=diarization_model_dir,
                uvr_model_dir=uvr_model_dir,
            )
        if whisper_type == WhisperImpl.INSANELY_FAST_WHISPER.value:
            return InsanelyFastWhisperInference(
                model_dir=insanely_fast_whisper_model_dir,
                output_dir=output_dir,
                diarization_model_dir=diarization_model_dir,
                uvr_model_dir=uvr_model_dir,
            )
        return FasterWhisperInference(
            model_dir=faster_whisper_model_dir,
            output_dir=output_dir,
            diarization_model_dir=diarization_model_dir,
            uvr_model_dir=uvr_model_dir,
        )
