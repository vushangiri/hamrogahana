"""Local storage adapter, bounded uploads and PostgreSQL lease-based FFmpeg jobs."""

import json
import math
import subprocess
import uuid
from datetime import timedelta
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import or_, select

from ..extensions import db
from ..models import Job, Media, now
from .core import audit, locked_store

Image.MAX_IMAGE_PIXELS = 30_000_000


def root():
    path = Path(current_app.config["MEDIA_ROOT"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def path_for(key):
    if not key or Path(key).name != key:
        raise ValueError("Invalid media key")
    return root() / key


def inspect_video(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        data = json.loads(result.stdout)
        streams = [s for s in data["streams"] if s.get("codec_type") == "video"]
        v = streams[0]
        duration = float(data["format"]["duration"])
        if (
            len(streams) != 1
            or not math.isfinite(duration)
            or not 5 <= duration <= 60
        ):
            raise ValueError("Use a supported 5–60 second video")
        width, height = v["width"], v["height"]
        if not 1 <= width <= 4096 or not 1 <= height <= 4096:
            raise ValueError("Use a video up to 4096 pixels per side")
        return duration
    except (subprocess.SubprocessError, KeyError, IndexError, json.JSONDecodeError, TypeError, OSError):
        raise ValueError("Cannot read this video") from None


def compress_image(source):
    """Decode supported still images, orient them and emit bounded WebP variants."""
    generated = []
    try:
        with Image.open(source) as im:
            if im.width * im.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError("Use an image under 30 megapixels")
            im.verify()
        with Image.open(source) as im:
            image = ImageOps.exif_transpose(im)
            image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
            variants = {}
            for width in (320, 640, 1280):
                resized = image.copy()
                resized.thumbnail((width, width), Image.Resampling.LANCZOS)
                dest = uuid.uuid4().hex + ".webp"
                generated.append(dest)
                resized.save(path_for(dest), "WEBP", quality=80, method=4)
                variants[str(width)] = dest
        return variants
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        for key in generated:
            path_for(key).unlink(missing_ok=True)
        raise ValueError("Use a supported image under 30 megapixels, or PDF for evidence") from None


def transcode_video(source, output, thumb):
    inspect_video(source)
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(source),
            "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease:force_divisible_by=2,"
            "pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
            "-c:v", "libx264", "-preset", "fast", "-crf", "26", "-pix_fmt", "yuv420p",
            "-threads", "2", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
            "-map_metadata", "-1", str(output),
        ], check=True, timeout=600, capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", "1", "-i", str(output),
            "-frames:v", "1", "-vf", "scale=360:640", "-threads", "1", str(thumb),
        ], check=True, timeout=30, capture_output=True,
    )


def upload(file, store, kind, product=None):
    store = locked_store(store.id)
    if not file or not file.filename:
        raise ValueError("Select a file")
    if kind in ("image", "reel") and not product:
        raise ValueError("Select a product")
    if kind == "reel":
        count = db.session.scalar(
            select(db.func.count())
            .select_from(Media)
            .where(
                Media.product_id == product.id,
                Media.kind == "reel",
                Media.status.in_(["queued", "processing", "ready"]),
            )
        )
        if count >= store.plan.reels:
            raise ValueError("Reel allowance reached")
    if (
        kind == "image"
        and len([m for m in product.media if m.kind == "image" and m.status == "ready"]) >= 8
    ):
        raise ValueError("Maximum eight images per product")
    cap = (100 if kind == "reel" else 10) * 1024 * 1024
    key = uuid.uuid4().hex + ".upload"
    target = path_for(key)
    try:
        size = 0
        with target.open("wb") as out:
            while block := file.stream.read(1024 * 1024):
                size += len(block)
                if size > cap:
                    raise ValueError(f"Maximum upload size: {cap // 1024 // 1024} MB")
                out.write(block)
        if not size:
            raise ValueError("Empty file")
        m = Media(
            store_id=store.id, product_id=product.id if product else None, kind=kind, source=key
        )
        if kind == "reel":
            # Probe runs in worker as well; validation cannot block a web worker.
            db.session.add(m)
            db.session.flush()
            db.session.add(Job(media_id=m.id))
        else:
            if kind in ("payment", "document") and target.read_bytes()[:5] == b"%PDF-":
                m.status = "ready"
                m.output = key
            else:
                m.variants = compress_image(target)
                m.output = m.variants["1280"]
                m.thumbnail = m.variants["320"]
                m.status = "ready"
            db.session.add(m)
            db.session.flush()
        audit("media.uploaded", m.id, kind=kind)
        return m
    except Exception:
        target.unlink(missing_ok=True)
        raise


def process_one():
    cutoff = now() - timedelta(minutes=15)
    job = db.session.scalar(
        select(Job)
        .where(or_(Job.state == "queued", (Job.state == "processing") & (Job.leased_at < cutoff)))
        .order_by(Job.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if not job:
        db.session.rollback()
        return False
    token = uuid.uuid4()
    job.state, job.leased_at, job.token = "processing", now(), token
    job.attempts += 1
    media = db.session.get(Media, job.media_id)
    if media.status not in ("queued", "processing"):
        job.state = "cancelled"
        db.session.commit()
        return True
    media.status = "processing"
    mid, jid, source = media.id, job.id, media.source
    db.session.commit()
    output, thumb = uuid.uuid4().hex + ".mp4", uuid.uuid4().hex + ".webp"
    try:
        transcode_video(path_for(source), path_for(output), path_for(thumb))
        error = None
    except (ValueError, subprocess.SubprocessError, OSError) as exc:
        error = str(exc)[:400]
    db.session.expire_all()
    job = db.session.scalar(select(Job).where(Job.id == jid).with_for_update())
    media = db.session.scalar(select(Media).where(Media.id == mid).with_for_update())
    if job.token != token:
        db.session.rollback()
        path_for(output).unlink(missing_ok=True)
        path_for(thumb).unlink(missing_ok=True)
        return True
    if error:
        job.error = media.error = error
        job.state = media.status = "failed" if job.attempts >= 3 else "queued"
    elif media.status == "processing":
        media.status, media.output, media.thumbnail = "ready", output, thumb
        job.state = "done"
        path_for(source).unlink(missing_ok=True)
    else:
        job.state = "cancelled"
    db.session.commit()
    if error or job.state == "cancelled":
        path_for(output).unlink(missing_ok=True)
        path_for(thumb).unlink(missing_ok=True)
    return True
