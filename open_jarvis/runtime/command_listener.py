"""Command listening helpers."""

from __future__ import annotations

import os

import speech_recognition as sr

from open_jarvis.audio.speech_backend import (
    recognition_mode,
    transcribe_audio,
)
from open_jarvis.health.observability import record_runtime_event
from open_jarvis.runtime.ui_bridge import send_state
from open_jarvis.security.jarvis_admin import format_actionable_message


# ============================================================
# SPEECH RECOGNIZER
# ============================================================

_cmd_recognizer = sr.Recognizer()

_cmd_recognizer.energy_threshold = int(
    os.getenv("JARVIS_ENERGY_THRESHOLD", "300")
)

_cmd_recognizer.dynamic_energy_threshold = False

_cmd_recognizer.pause_threshold = float(
    os.getenv("JARVIS_PAUSE_THRESHOLD", "1.0")
)


# ============================================================
# MICROPHONE
# ============================================================

# We tested your microphones and device #1 successfully
# recognized "Jarvis".
MICROPHONE_DEVICE_INDEX = int(
    os.getenv("JARVIS_MICROPHONE_DEVICE_INDEX", "1")
)


# ============================================================
# COMMAND LISTENER
# ============================================================

def listen_for_command(*, logger, send_log, speak) -> str:
    """Listen for one spoken command."""

    try:

        with sr.Microphone(
            device_index=MICROPHONE_DEVICE_INDEX
        ) as source:

            logger.info(
                "Listening for command using microphone device %s.",
                MICROPHONE_DEVICE_INDEX,
            )

            print(
                "Listening for command..."
            )

            send_log(
                "[VOICE] Listening started"
            )

            send_state(
                "LISTENING",
                "Voice input active"
            )

            try:

                audio = _cmd_recognizer.listen(
                    source,
                    timeout=10,
                    phrase_time_limit=20,
                )

            except sr.WaitTimeoutError:

                logger.debug(
                    "No speech detected before command timeout."
                )

                return ""

    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:

        logger.warning(
            "Microphone not detected while listening for a command: %s",
            exc,
        )

        record_runtime_event(
            "microphone_missing",
            "Microphone not detected",
            "warning",
            {
                "mode": recognition_mode(),
                "device_index": MICROPHONE_DEVICE_INDEX,
            },
        )

        send_log(
            "[ERROR] Microphone not detected. "
            "Check input device settings."
        )

        send_state(
            "ERROR",
            "Microphone not detected"
        )

        return ""

    # ========================================================
    # SPEECH → TEXT
    # ========================================================

    try:

        command = transcribe_audio(
            _cmd_recognizer,
            audio,
            language="en-US",
        )

        if not command:

            if recognition_mode() == "offline":

                speak(
                    format_actionable_message(
                        "I heard something, but couldn't decode it.",
                        "Offline speech recognition returned an empty transcription.",
                        "Speak a little closer to the microphone and try again.",
                    )
                )

            return ""

        # ====================================================
        # COMMAND SUCCESSFULLY RECOGNIZED
        # ====================================================

        logger.info(
            "Recognized command: %s",
            command,
        )

        print(
            f"You: {command}"
        )

        send_log(
            f"[CMD] You: {command}"
        )

        record_runtime_event(
            "command_recognized",
            command,
            "info",
            {
                "mode": recognition_mode(),
                "device_index": MICROPHONE_DEVICE_INDEX,
            },
        )

        return command.lower()

    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:

        logger.warning(
            "Speech recognition failed: %s",
            exc,
        )

        record_runtime_event(
            "voice_error",
            "Speech recognition failure",
            "warning",
            {
                "mode": recognition_mode(),
                "device_index": MICROPHONE_DEVICE_INDEX,
            },
        )

        speak(
            format_actionable_message(
                "Voice recognition is unavailable.",
                "Neither online nor offline speech recognition could transcribe the audio.",
                "Check your internet connection, microphone, and offline model path.",
            )
        )

        return ""