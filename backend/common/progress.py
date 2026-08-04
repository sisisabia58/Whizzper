class NoOpProgress:
    """Callable stand-in for gr.Progress() in FastAPI (non-Gradio) contexts."""

    def __call__(self, *args, **kwargs):
        return None


NO_OP_PROGRESS = NoOpProgress()
