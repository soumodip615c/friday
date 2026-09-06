"""Wake-word listener helpers."""

from __future__ import annotations

import os
import time

import speech_recognition as sr

from open_jarvis.audio.speech_backend import (
    recognition_mode,
    transcribe_audio,
)
from open_jarvis.audio.wake_word import (
    build_wake_word_config,
    wake_word_detected,
)
from open_jarvis.health.observability import (
    record_runtime_event,
)


WAKE_WORD_CONFIG = build_wake_word_config()

WAKE_WORD = str(
    WAKE_WORD_CONFIG["wake_word"]
)


# How long FRIDAY stays active after the wake word.
ACTIVE_TIMEOUT = int(
    os.getenv(
        "JARVIS_ACTIVE_TIMEOUT",
        "60",
    )
)


# Confirmed working microphone.
MICROPHONE_DEVICE_INDEX = int(
    os.getenv(
        "JARVIS_MICROPHONE_DEVICE_INDEX",
        "1",
    )
)


_wake_recognizer = sr.Recognizer()

_wake_recognizer.energy_threshold = int(
    os.getenv(
        "JARVIS_ENERGY_THRESHOLD",
        "300",
    )
)

_wake_recognizer.dynamic_energy_threshold = True


# ------------------------------------------------------------
# ACTIVE STATE
# ------------------------------------------------------------

active = False


def listen_for_wake_word(
    *,
    logger,
    send_log,
) -> None:
    """Listen continuously for the FRIDAY wake word."""

    global active

    if not WAKE_WORD_CONFIG["enabled"]:

        send_log(
            "[WARN] Wake-word mode disabled. "
            "Use text commands or push-to-talk."
        )

        record_runtime_event(
            "wake_word",
            "Wake-word mode disabled",
            "warning",
            {
                "mode": recognition_mode(),
            },
        )

        return

    while True:

        # ----------------------------------------------------
        # IMPORTANT
        #
        # When FRIDAY is already active, DO NOT touch the
        # microphone here.
        #
        # The command listener needs exclusive access to it.
        # ----------------------------------------------------

        if active:
            time.sleep(0.2)
            continue

        try:

            # ------------------------------------------------
            # STANDBY MICROPHONE
            # ------------------------------------------------

            with sr.Microphone(
                device_index=MICROPHONE_DEVICE_INDEX
            ) as source:

                logger.debug(
                    "Wake listener using microphone device %s.",
                    MICROPHONE_DEVICE_INDEX,
                )

                _wake_recognizer.adjust_for_ambient_noise(
                    source,
                    duration=0.1,
                )

                audio = _wake_recognizer.listen(
                    source,
                    timeout=3,
                    phrase_time_limit=3,
                )

            # ------------------------------------------------
            # SPEECH → TEXT
            # ------------------------------------------------

            text = transcribe_audio(
                _wake_recognizer,
                audio,
                language="en-US",
                prefer_offline=True,
            )

            if not text:
                continue

            logger.debug(
                "Wake listener heard: %s",
                text,
            )

            # ------------------------------------------------
            # CHECK WAKE WORD
            # ------------------------------------------------

            if wake_word_detected(
                text,
                config=WAKE_WORD_CONFIG,
            ):

                active = True

                print(
                    "\n🟢 Wake word detected!"
                )

                send_log(
                    "WAKE WORD DETECTED"
                )

                send_log(
                    "[VOICE] FRIDAY active - "
                    "continuous conversation enabled"
                )

                record_runtime_event(
                    "wake_word",
                    "Wake word detected",
                    "info",
                    {
                        "mode": recognition_mode(),
                        "active_timeout": ACTIVE_TIMEOUT,
                        "microphone_device": (
                            MICROPHONE_DEVICE_INDEX
                        ),
                    },
                )

        except (
            OSError,
            RuntimeError,
            ValueError,
            sr.WaitTimeoutError,
        ):

            logger.debug(
                "Wake-word listener swallowed an exception.",
                exc_info=True,
            )

            # Give the microphone/audio system a moment
            # before trying again.
            time.sleep(0.2)