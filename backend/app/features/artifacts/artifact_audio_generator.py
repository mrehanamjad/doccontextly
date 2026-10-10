# artifact_audio_generator.py
"""
Audio generation for Voice Overview artifacts.

Pipeline:
1. Take a two-host AudioOverviewArtifact (dialogue script).
2. Synthesize each line with edge-tts using a fixed voice per host.
3. Stitch all line-level audio clips into a single MP3 with pydub,
   adding small natural pauses between turns.
4. Return the local file path + total duration so the caller can
   upload it to storage (ImageKit) and persist the URL.

"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

import edge_tts
from pydub import AudioSegment

from app.core.logger import logger
from app.features.artifacts.schema import AudioOverviewArtifact, AudioOverviewVoiceStyle


# ── Voice configuration ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class HostVoiceConfig:
    voice: str
    rate: str = "+0%"
    pitch: str = "+0Hz"


@dataclass(frozen=True)
class VoiceStyleConfig:
    host_1: HostVoiceConfig
    host_2: HostVoiceConfig


# Microsoft Edge neural voices. 
VOICE_STYLES: Dict[str, VoiceStyleConfig] = {
    AudioOverviewVoiceStyle.DEFAULT.value: VoiceStyleConfig(
        host_1=HostVoiceConfig(voice="en-US-AndrewMultilingualNeural", rate="+2%"),
        host_2=HostVoiceConfig(voice="en-US-AvaMultilingualNeural", rate="+2%"),
    ),
    AudioOverviewVoiceStyle.ENERGETIC.value: VoiceStyleConfig(
        host_1=HostVoiceConfig(voice="en-US-GuyNeural", rate="+8%"),
        host_2=HostVoiceConfig(voice="en-US-JennyNeural", rate="+8%"),
    ),
    AudioOverviewVoiceStyle.CALM.value: VoiceStyleConfig(
        host_1=HostVoiceConfig(voice="en-US-BrianMultilingualNeural", rate="-4%"),
        host_2=HostVoiceConfig(voice="en-US-AriaNeural", rate="-4%"),
    ),
}

DEFAULT_VOICE_STYLE = AudioOverviewVoiceStyle.DEFAULT.value

# Small silence inserted between consecutive dialogue turns so it doesn't
# sound like the hosts are talking over each other.
TURN_GAP_MS = 380
# Slightly longer pause after the very first line (intro beat) and before
# the very last line (outro beat) for a more natural podcast cadence.
INTRO_OUTRO_GAP_MS = 550

# Bound concurrent TTS requests so we don't hammer the edge-tts endpoint
# or blow up memory with too many in-flight synthesis tasks at once.
MAX_CONCURRENT_SYNTHESIS = 4


@dataclass
class AudioGenerationResult:
    file_path: str
    duration_seconds: float
    line_count: int


class ArtifactAudioGenerationError(Exception):
    """Raised when audio synthesis/stitching fails entirely."""


class ArtifactAudioGenerator:
    """Synthesizes a two-host dialogue script into a single stitched audio file."""

    def __init__(self, voice_style: str = DEFAULT_VOICE_STYLE):
        self.voice_style = VOICE_STYLES.get(voice_style, VOICE_STYLES[DEFAULT_VOICE_STYLE])

    async def generate(
        self,
        artifact: AudioOverviewArtifact,
        output_dir: Optional[str] = None,
    ) -> AudioGenerationResult:
        """
        Synthesize the full dialogue into a single MP3 file on disk.

        Args:
            artifact: The structured dialogue script (host_1 / host_2 lines).
            output_dir: Directory to write the final stitched file into.
                        Defaults to the system temp dir.

        Returns:
            AudioGenerationResult with the local file path and duration.
        """
        if not artifact.dialogue:
            raise ArtifactAudioGenerationError("Dialogue script is empty, nothing to synthesize.")

        output_dir = output_dir or tempfile.gettempdir()
        os.makedirs(output_dir, exist_ok=True)

        work_dir = tempfile.mkdtemp(prefix="voice_overview_", dir=output_dir)
        line_paths: List[Optional[str]] = [None] * len(artifact.dialogue)

        try:
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNTHESIS)

            async def synth_line(index: int, speaker: str, text: str) -> None:
                async with semaphore:
                    path = os.path.join(work_dir, f"line_{index:04d}.mp3")
                    await self._synthesize_line(speaker=speaker, text=text, out_path=path)
                    line_paths[index] = path

            tasks = [
                synth_line(i, line.speaker, line.text)
                for i, line in enumerate(artifact.dialogue)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            failures = [r for r in results if isinstance(r, Exception)]
            if failures:
                logger.error(f"{len(failures)}/{len(tasks)} dialogue lines failed TTS synthesis")
                if len(failures) == len(tasks):
                    raise ArtifactAudioGenerationError(
                        f"All {len(tasks)} dialogue lines failed to synthesize: {failures[0]}"
                    )

            stitched = self._stitch_clips(line_paths)
            if stitched is None or len(stitched) == 0:
                raise ArtifactAudioGenerationError("No audio clips were available to stitch together.")

            final_path = os.path.join(output_dir, f"voice_overview_{uuid.uuid4().hex}.mp3")
            stitched.export(final_path, format="mp3", bitrate="128k")

            duration_seconds = round(len(stitched) / 1000.0, 2)
            logger.info(
                f"Voice overview synthesized: {len(artifact.dialogue)} lines, "
                f"{duration_seconds}s duration -> {final_path}"
            )

            return AudioGenerationResult(
                file_path=final_path,
                duration_seconds=duration_seconds,
                line_count=len(artifact.dialogue),
            )

        finally:
            self._cleanup_dir(work_dir)

    # ── Per-line synthesis ─────────────────────────────────────────────────────

    async def _synthesize_line(self, speaker: str, text: str, out_path: str) -> None:
        """Synthesize a single dialogue line to an mp3 file using the host's voice."""
        text = (text or "").strip()
        if not text:
            # Write a tiny silent placeholder so stitching doesn't break on empty lines.
            AudioSegment.silent(duration=200).export(out_path, format="mp3")
            return

        host_cfg = self.voice_style.host_1 if speaker == "host_1" else self.voice_style.host_2

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=host_cfg.voice,
                rate=host_cfg.rate,
                pitch=host_cfg.pitch,
            )
            await communicate.save(out_path)
        except Exception as e:
            logger.warning(f"TTS synthesis failed for a line (speaker={speaker}): {e}")
            raise

    # ── Stitching ──────────────────────────────────────────────────────────────

    def _stitch_clips(self, line_paths: List[Optional[str]]) -> Optional[AudioSegment]:
        """Concatenate per-line clips in order, inserting natural pauses between turns."""
        combined: Optional[AudioSegment] = None
        total = len(line_paths)

        for i, path in enumerate(line_paths):
            if not path or not os.path.exists(path):
                continue

            try:
                clip = AudioSegment.from_file(path, format="mp3")
            except Exception as e:
                logger.warning(f"Failed to load synthesized clip at index {i}: {e}")
                continue

            if combined is None:
                combined = clip
                continue

            gap = INTRO_OUTRO_GAP_MS if i in (1, total - 1) else TURN_GAP_MS
            combined = combined + AudioSegment.silent(duration=gap) + clip

        return combined

    @staticmethod
    def _cleanup_dir(path: str) -> None:
        """Best-effort cleanup of the per-line working directory."""
        try:
            import shutil
            shutil.rmtree(path, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to clean up temp dir {path}: {e}")


def get_audio_generator(voice_style: str = DEFAULT_VOICE_STYLE) -> ArtifactAudioGenerator:
    """Factory matching the project's get_* dependency-style helpers."""
    return ArtifactAudioGenerator(voice_style=voice_style)