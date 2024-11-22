#!/usr/bin/env python3

"""Links/unlinks default Pipewire audio output device monitor channels to Snapcast sink.

This pipes all desktop audio through Snapcast for as long as the process remains running.
When it's terminated through SIGINT or SIGTERM, the link is broken. The script is idempotent
so if the link already exists at start-up or was already broken at shutdown, it continues
without error.

The Snapcast sink node must already exist in Pipewire and the nane must match SNAPCAST_SINK_NODE.
Use something like this to set up the sink (e.g. in a systemd oneshot service):

pactl load-module module-pipe-sink file=/run/snapserver/dispatch sink_name=Snapcast format=s16le rate=48000
"""

import subprocess
import json
import signal
import time
import logging


# Nothing fancy. Let systemd do the heavy lifting.
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


# The Snapcast sink node in Pipewire. It is expected to already exist.
SNAPCAST_SINK_NODE = "Snapcast"


# Requeest for clean shutdown
class ShutdownException(Exception): ...


def update_links(audio_sink_node: str, snapcast_sink_node: str, disconnect: bool):
    """Connect or disconnect sink monitor ports and Snapcast."""

    link_cmd = ["pw-link"]
    if disconnect:
        link_cmd.append("-d")
    for channel in ["FL", "FR"]:
        src_channel = f"{audio_sink_node}:monitor_{channel}"
        target_channel = f"{snapcast_sink_node}:playback_{channel}"
        ended_proc = subprocess.run(
            link_cmd + [src_channel, target_channel], capture_output=True, text=True
        )
        if ended_proc.returncode != 0:
            if (
                not disconnect
                and ended_proc.stderr == "failed to link ports: File exists\n"
            ):
                logging.warning(f"{src_channel} and {target_channel} were already connected.")
            elif (
                disconnect
                and ended_proc.stderr
                == "failed to unlink ports: No such file or directory\n"
            ):
                logging.warning(f"{src_channel} and {target_channel} were already disconnected.")
            else:
                logging.warning(ended_proc.stderr)
                ended_proc.check_returncode()


def _init_signal_handlers():
    """SIGINT or SIGTERM throws ShutdownException for clean shutdown."""

    def raise_shutdown_exception(signal_num, _):
        logging.info(f"Received signal {signal_num}")
        raise ShutdownException()

    signal.signal(signal.SIGINT, raise_shutdown_exception)
    signal.signal(signal.SIGTERM, raise_shutdown_exception)


def find_default_audio_sink() -> str:
    """Find the default audio sink from Pipewire dump."""

    pipewire_dump = json.loads(subprocess.check_output(["pw-dump"]))
    # Find the default audio sink name
    pipewire_defaults_dicts = [
        d
        for d in pipewire_dump
        if d["type"] == "PipeWire:Interface:Metadata"
        and d["props"]["metadata.name"] == "default"
    ]
    if len(pipewire_defaults_dicts) != 1:
        raise LookupError("Failed to find Pipewire defaults metadata.")
    default_sink_names = [
        d["value"]["name"]
        for d in pipewire_defaults_dicts[0]["metadata"]
        if d["key"] == "default.audio.sink"
    ]
    if len(default_sink_names) != 1:
        raise LookupError("Failed to find default audio sink.")
    return default_sink_names[0]


def _main():
    """Connect default audio sink to Snapcast sink, wait for interruption, and then disconnect them."""
    default_sink_name = find_default_audio_sink()
    # Link default audio sink to Snapcast
    update_links(default_sink_name, SNAPCAST_SINK_NODE, False)
    logging.info(f"Connected {default_sink_name} audio sink to {SNAPCAST_SINK_NODE}.")
    _init_signal_handlers()
    try:
        while True:
            time.sleep(60)
    except ShutdownException:
        logging.info("Caught shutdown request.")
    finally:
        # Unlink default audio sink to Snapcast
        update_links(default_sink_name, SNAPCAST_SINK_NODE, True)
        logging.info(f"Disconnect {default_sink_name} from {SNAPCAST_SINK_NODE}.")


if __name__ == "__main__":
    _main()
