"""Root conftest.py — session-scoped fixtures shared across all tests."""

import os
import shutil
import tempfile

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_ffmpeg_on_path():
    """Add ffmpeg to PATH if available via imageio-ffmpeg but not on system PATH.

    Whisper calls ``ffmpeg`` as a subprocess.  On CI or dev machines that lack a
    system-wide install the bundled binary from *imageio-ffmpeg* can be used as a
    drop-in replacement.  The binary has a versioned filename, so we create a
    temporary directory with a copy named ``ffmpeg.exe`` (Windows) or ``ffmpeg``
    and prepend it to ``PATH``.
    """
    # Already available → nothing to do.
    if shutil.which("ffmpeg"):
        yield
        return

    try:
        import imageio_ffmpeg

        src = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        # Package not installed – skip silently; tests that need ffmpeg will
        # be skipped by their own markers.
        yield
        return

    tmpdir = tempfile.mkdtemp(prefix="ffmpeg_shim_")
    dst_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    dst = os.path.join(tmpdir, dst_name)
    shutil.copy2(src, dst)

    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = tmpdir + os.pathsep + old_path

    yield

    # Cleanup
    os.environ["PATH"] = old_path
    shutil.rmtree(tmpdir, ignore_errors=True)
