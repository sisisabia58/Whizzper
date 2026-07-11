import os
import time
import huggingface_hub
import numpy as np
import torch
from typing import BinaryIO, Union, Tuple, List, Callable
import faster_whisper
from faster_whisper.vad import VadOptions
import ast
import ctranslate2
import whisper
import gradio as gr
from argparse import Namespace

from modules.utils.paths import (FASTER_WHISPER_MODELS_DIR, DIARIZATION_MODELS_DIR, UVR_MODELS_DIR, OUTPUT_DIR)
from modules.whisper.data_classes import *
from modules.whisper.base_transcription_pipeline import BaseTranscriptionPipeline


def split_long_segments(segments, max_words=12, max_duration=6.0):
    new_segments = []
    
    for seg in segments:
        if not hasattr(seg, "words") or seg.words is None or len(seg.words) == 0:
            new_segments.append(seg)
            continue
            
        current_words = []
        seg_start = None
        
        for w in seg.words:
            if seg_start is None:
                seg_start = w.start
                
            current_words.append(w)
            
            # Split conditions:
            # 1. Punctuation ending a clause/sentence (with a minimum of 4 words to avoid tiny chunks)
            ends_clause = w.word.strip().endswith(('.', '?', '!', ';', ','))
            # 2. Maximum words limit reached
            too_many_words = len(current_words) >= max_words
            # 3. Maximum duration reached
            too_long = (w.end - seg_start) >= max_duration
            
            if (ends_clause and len(current_words) >= 4) or too_many_words or too_long:
                from faster_whisper.transcribe import Segment as FWSegment
                text = "".join(x.word for x in current_words).strip()
                new_segments.append(FWSegment(
                    id=0,
                    seek=seg.seek,
                    start=seg_start,
                    end=w.end,
                    text=text,
                    tokens=[],
                    temperature=seg.temperature,
                    avg_logprob=seg.avg_logprob,
                    compression_ratio=seg.compression_ratio,
                    no_speech_prob=seg.no_speech_prob,
                    words=current_words
                ))
                current_words = []
                seg_start = None
                
        if current_words:
            from faster_whisper.transcribe import Segment as FWSegment
            text = "".join(x.word for x in current_words).strip()
            new_segments.append(FWSegment(
                id=0,
                seek=seg.seek,
                start=seg_start if seg_start is not None else seg.start,
                end=current_words[-1].end,
                text=text,
                tokens=[],
                temperature=seg.temperature,
                avg_logprob=seg.avg_logprob,
                compression_ratio=seg.compression_ratio,
                no_speech_prob=seg.no_speech_prob,
                words=current_words
            ))
            
    for idx, s in enumerate(new_segments):
        s.id = idx
        
    return new_segments


class FasterWhisperInference(BaseTranscriptionPipeline):
    def __init__(self,
                 model_dir: str = FASTER_WHISPER_MODELS_DIR,
                 diarization_model_dir: str = DIARIZATION_MODELS_DIR,
                 uvr_model_dir: str = UVR_MODELS_DIR,
                 output_dir: str = OUTPUT_DIR,
                 ):
        super().__init__(
            model_dir=model_dir,
            diarization_model_dir=diarization_model_dir,
            uvr_model_dir=uvr_model_dir,
            output_dir=output_dir
        )
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)

        self.model_paths = self.get_model_paths()
        self.device = self.get_device()
        self.available_models = self.model_paths.keys()

    def transcribe(self,
                   audio: Union[str, BinaryIO, np.ndarray],
                   progress: gr.Progress = gr.Progress(),
                   progress_callback: Optional[Callable] = None,
                   *whisper_params,
                   ) -> Tuple[List[Segment], float]:
        """
        transcribe method for faster-whisper.

        Parameters
        ----------
        audio: Union[str, BinaryIO, np.ndarray]
            Audio path or file binary or Audio numpy array
        progress: gr.Progress
            Indicator to show progress directly in gradio.
        progress_callback: Optional[Callable]
            callback function to show progress. Can be used to update progress in the backend.
        *whisper_params: tuple
            Parameters related with whisper. This will be dealt with "WhisperParameters" data class

        Returns
        ----------
        segments_result: List[Segment]
            list of Segment that includes start, end timestamps and transcribed text
        elapsed_time: float
            elapsed time for transcription
        """
        start_time = time.time()

        params = WhisperParams.from_list(list(whisper_params))

        if params.model_size != self.current_model_size or self.model is None or self.current_compute_type != params.compute_type:
            self.update_model(params.model_size, params.compute_type, progress)

        temp = params.temperature
        if temp == 0.0:
            temp = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

        try:
            from faster_whisper import BatchedInferencePipeline
            has_batched = True
        except ImportError:
            has_batched = False

        segments = None
        info = None

        if has_batched and params.batch_size > 1:
            try:
                from faster_whisper import BatchedInferencePipeline
                pipeline = BatchedInferencePipeline(self.model)
                
                kwargs = {
                    "language": params.lang,
                    "task": "translate" if params.is_translate else "transcribe",
                    "beam_size": params.beam_size,
                    "log_prob_threshold": params.log_prob_threshold,
                    "no_speech_threshold": params.no_speech_threshold,
                    "best_of": params.best_of,
                    "patience": params.patience,
                    "temperature": temp,
                    "compression_ratio_threshold": params.compression_ratio_threshold,
                    "length_penalty": params.length_penalty,
                    "repetition_penalty": params.repetition_penalty,
                    "no_repeat_ngram_size": params.no_repeat_ngram_size,
                    "prefix": params.prefix,
                    "suppress_blank": params.suppress_blank,
                    "suppress_tokens": params.suppress_tokens,
                    "max_initial_timestamp": params.max_initial_timestamp,
                    "word_timestamps": True,
                    "prepend_punctuations": params.prepend_punctuations,
                    "append_punctuations": params.append_punctuations,
                    "batch_size": params.batch_size
                }
                
                if params.initial_prompt is not None:
                    kwargs["initial_prompt"] = params.initial_prompt
                if params.max_new_tokens is not None:
                    kwargs["max_new_tokens"] = params.max_new_tokens
                if params.chunk_length is not None:
                    kwargs["chunk_length"] = params.chunk_length
                if params.hotwords is not None:
                    kwargs["hotwords"] = params.hotwords

                segments, info = pipeline.transcribe(audio=audio, **kwargs)
                segments = list(segments)
                segments = split_long_segments(segments)
            except Exception as e:
                print(f"[WhisperInference] Batched transcription failed: {e}. Falling back to sequential transcription.")
                segments = None

        if segments is None:
            segments, info = self.model.transcribe(
                audio=audio,
                language=params.lang,
                task="translate" if params.is_translate else "transcribe",
                beam_size=params.beam_size,
                log_prob_threshold=params.log_prob_threshold,
                no_speech_threshold=params.no_speech_threshold,
                best_of=params.best_of,
                patience=params.patience,
                temperature=temp,
                condition_on_previous_text=params.condition_on_previous_text,
                initial_prompt=params.initial_prompt,
                compression_ratio_threshold=params.compression_ratio_threshold,
                length_penalty=params.length_penalty,
                repetition_penalty=params.repetition_penalty,
                no_repeat_ngram_size=params.no_repeat_ngram_size,
                prefix=params.prefix,
                suppress_blank=params.suppress_blank,
                suppress_tokens=params.suppress_tokens,
                max_initial_timestamp=params.max_initial_timestamp,
                word_timestamps=True,
                prepend_punctuations=params.prepend_punctuations,
                append_punctuations=params.append_punctuations,
                max_new_tokens=params.max_new_tokens,
                chunk_length=params.chunk_length,
                hallucination_silence_threshold=params.hallucination_silence_threshold,
                hotwords=params.hotwords,
                language_detection_threshold=params.language_detection_threshold,
                language_detection_segments=params.language_detection_segments,
                prompt_reset_on_temperature=params.prompt_reset_on_temperature,
            )
        progress(0, desc="Loading audio..")

        segments_result = []
        for segment in segments:
            progress_n = segment.start / info.duration
            progress(progress_n, desc="Transcribing..")
            if progress_callback is not None:
                progress_callback(progress_n)
            segments_result.append(Segment.from_faster_whisper(segment))

        elapsed_time = time.time() - start_time
        return segments_result, elapsed_time

    def update_model(self,
                     model_size: str,
                     compute_type: str,
                     progress: gr.Progress = gr.Progress()
                     ):
        """
        Update current model setting

        Parameters
        ----------
        model_size: str
            Size of whisper model. If you enter the huggingface repo id, it will try to download the model
            automatically from huggingface.
        compute_type: str
            Compute type for transcription.
            see more info : https://opennmt.net/CTranslate2/quantization.html
        progress: gr.Progress
            Indicator to show progress directly in gradio.
        """
        progress(0, desc="Initializing Model..")

        model_size_dirname = model_size.replace("/", "--") if "/" in model_size else model_size
        if model_size not in self.model_paths and model_size_dirname not in self.model_paths:
            print(f"Model is not detected. Trying to download \"{model_size}\" from huggingface to "
                  f"\"{os.path.join(self.model_dir, model_size_dirname)} ...")
            huggingface_hub.snapshot_download(
                model_size,
                local_dir=os.path.join(self.model_dir, model_size_dirname),
            )
            self.model_paths = self.get_model_paths()
            gr.Info(f"Model is downloaded with the name \"{model_size_dirname}\"")

        self.current_model_size = self.model_paths[model_size_dirname]

        local_files_only = False
        hf_prefix = "models--Systran--faster-whisper-"
        official_model_path = os.path.join(self.model_dir, hf_prefix+model_size)
        if ((os.path.isdir(self.current_model_size) and os.path.exists(self.current_model_size)) or
            (model_size in faster_whisper.available_models() and os.path.exists(official_model_path))):
            local_files_only = True

        self.current_compute_type = compute_type
        self.model = faster_whisper.WhisperModel(
            device=self.device,
            model_size_or_path=self.current_model_size,
            download_root=self.model_dir,
            compute_type=self.current_compute_type,
            local_files_only=local_files_only
        )

    def get_model_paths(self):
        """
        Get available models from models path including fine-tuned model.

        Returns
        ----------
        Name list of models
        """
        model_paths = {model:model for model in faster_whisper.available_models()}
        faster_whisper_prefix = "models--Systran--faster-whisper-"

        existing_models = os.listdir(self.model_dir)
        wrong_dirs = [".locks", "faster_whisper_models_will_be_saved_here"]
        existing_models = list(set(existing_models) - set(wrong_dirs))

        for model_name in existing_models:
            if faster_whisper_prefix in model_name:
                model_name = model_name[len(faster_whisper_prefix):]

            if model_name not in whisper.available_models():
                model_paths[model_name] = os.path.join(self.model_dir, model_name)
        return model_paths

    @staticmethod
    def get_device():
        if torch.cuda.is_available():
            return "cuda"
        else:
            return "auto"

    @staticmethod
    def format_suppress_tokens_str(suppress_tokens_str: str) -> List[int]:
        try:
            suppress_tokens = ast.literal_eval(suppress_tokens_str)
            if not isinstance(suppress_tokens, list) or not all(isinstance(item, int) for item in suppress_tokens):
                raise ValueError("Invalid Suppress Tokens. The value must be type of List[int]")
            return suppress_tokens
        except Exception as e:
            raise ValueError("Invalid Suppress Tokens. The value must be type of List[int]")
