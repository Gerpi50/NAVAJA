"""
motor_video.py — Conversión entre formatos de video y extracción de audio.
Motor: FFmpeg (externo).
Soporta: MP4, MKV, AVI, MOV, WEBM, FLV, WMV, M4V, 3GP, TS, MPG, OGV, GIF
         + extracción de audio a MP3/WAV/FLAC/OPUS/AAC/M4A
"""
import shutil
import subprocess
from core.graph import BaseMotor


VIDEO_FMTS = [
    "mp4", "mkv", "avi", "mov", "webm", "flv",
    "wmv", "m4v", "3gp", "ts", "mpg", "mpeg",
    "ogv", "gif", "vob", "f4v",
]

AUDIO_OUT_FMTS = ["mp3", "wav", "flac", "opus", "aac", "m4a", "ogg"]

# Video → Video
VIDEO_CONVERSIONS = [
    (s, d) for s in VIDEO_FMTS for d in VIDEO_FMTS if s != d
]

# Video → Audio (extracción)
VIDEO_TO_AUDIO = [
    (v, a) for v in VIDEO_FMTS for a in AUDIO_OUT_FMTS
]

ALL_CONVERSIONS = VIDEO_CONVERSIONS + VIDEO_TO_AUDIO

# Codec por extensión de salida
VIDEO_CODEC_MAP = {
    "mp4":  ["-c:v", "libx264",  "-crf", "23", "-preset", "fast",
             "-c:a", "aac",      "-b:a", "192k"],
    "mkv":  ["-c:v", "libx264",  "-crf", "23", "-preset", "fast",
             "-c:a", "aac",      "-b:a", "192k"],
    "avi":  ["-c:v", "mpeg4",    "-q:v", "6",
             "-c:a", "mp3",      "-q:a", "4"],
    "mov":  ["-c:v", "libx264",  "-crf", "23",
             "-c:a", "aac",      "-b:a", "192k"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0",
             "-c:a", "libopus",  "-b:a", "128k"],
    "flv":  ["-c:v", "flv",      "-c:a", "mp3"],
    "wmv":  ["-c:v", "wmv2",     "-c:a", "wmav2"],
    "m4v":  ["-c:v", "libx264",  "-crf", "23",
             "-c:a", "aac",      "-b:a", "192k"],
    # H.263 solo admite 176x144, 352x288 y algunos más: con cualquier otro
    # tamaño FFmpeg cortaba con "rate, width or height". MPEG-4 + AAC
    # también es 3GP válido y acepta el video tal como viene.
    "3gp":  ["-c:v", "mpeg4",    "-q:v", "6",
             "-c:a", "aac",      "-b:a", "64k", "-ar", "16000", "-ac", "1"],
    "ts":   ["-c:v", "mpeg2video", "-c:a", "mp2"],
    # MPEG-1 solo acepta un puñado de combinaciones de tamaño y cuadros por
    # segundo; con un video cualquiera cortaba con "rate, width or height".
    # MPEG-2 es el mismo contenedor y se lleva bien con cualquier medida.
    "mpg":  ["-c:v", "mpeg2video", "-c:a", "mp2"],
    "mpeg": ["-c:v", "mpeg2video", "-c:a", "mp2"],
    "ogv":  ["-c:v", "libtheora", "-c:a", "libvorbis"],
    "gif":  ["-vf", "fps=15,scale=640:-1:flags=lanczos",
             "-loop", "0"],
    "vob":  ["-c:v", "mpeg2video", "-c:a", "ac3"],
    "f4v":  ["-c:v", "libx264",  "-c:a", "aac"],
}

AUDIO_CODEC_MAP = {
    "mp3":  ["-vn", "-codec:a", "libmp3lame", "-q:a", "2"],
    "wav":  ["-vn", "-codec:a", "pcm_s16le"],
    "flac": ["-vn", "-codec:a", "flac"],
    "opus": ["-vn", "-codec:a", "libopus",    "-b:a", "128k"],
    "aac":  ["-vn", "-codec:a", "aac",        "-b:a", "192k"],
    "m4a":  ["-vn", "-codec:a", "aac",        "-b:a", "192k"],
    "ogg":  ["-vn", "-codec:a", "libvorbis",  "-q:a", "5"],
}

FORMAT_MAP = {
    "mp4": "mp4", "mkv": "matroska", "avi": "avi",
    "mov": "mov", "webm": "webm",    "flv": "flv",
    "wmv": "asf", "m4v": "mp4",     "3gp": "3gp",
    "ts":  "mpegts", "mpg": "mpeg", "mpeg": "mpeg",
    "ogv": "ogg",    "gif": "gif",  "vob": "vob",
    "f4v": "f4v",
    # audio
    "mp3": "mp3",  "wav": "wav",  "flac": "flac",
    "opus": "opus","aac": "adts", "m4a":  "ipod",
    "ogg": "ogg",
}


class FFmpegVideoMotor(BaseMotor):
    NAME = "FFmpeg-Video"
    CONVERSIONS = ALL_CONVERSIONS

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("ffmpeg") is not None

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        from motors.motor_audio import build_af_filter
        is_audio_out = dst_ext in AUDIO_OUT_FMTS

        if is_audio_out:
            codec_args = list(AUDIO_CODEC_MAP.get(dst_ext, ["-vn"]))
        else:
            codec_args = list(VIDEO_CODEC_MAP.get(dst_ext, ["-c", "copy"]))

        fmt = FORMAT_MAP.get(dst_ext, dst_ext)

        af = build_af_filter(kwargs.get("audio_filter"))
        # El filtro de audio requiere recodificar la pista de audio; si el
        # destino copiaba streams ("-c copy"), forzamos un re-encode de audio.
        if af and "copy" in codec_args:
            codec_args = ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]

        # Subtítulos quemados en el video (burn-in): se incrustan con -vf.
        sub_path = kwargs.get("burn_subtitle_path")
        vf_args = []
        if sub_path and not is_audio_out:
            safe = sub_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            vf_args = ["-vf", f"subtitles='{safe}'"]
            # Quemar subtítulos exige recodificar el video.
            if "-c copy" in " ".join(codec_args) or "copy" in codec_args:
                codec_args = VIDEO_CODEC_MAP.get("mp4")

        cmd = ["ffmpeg", "-y", "-i", src_path]
        if af:
            cmd += ["-af", af]
        cmd += vf_args
        cmd += codec_args
        if kwargs.get("strip_metadata"):
            cmd += ["-map_metadata", "-1"]
        cmd += ["-f", fmt, dst_path]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error:\n{result.stderr[-800:]}")
