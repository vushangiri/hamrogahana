import shutil
import subprocess

import pytest

from app.services.media import inspect_video, path_for


def test_path_traversal(app):
    with app.app_context(), pytest.raises(ValueError):
        path_for("../secret")


@pytest.mark.parametrize("duration,valid", [(4, False), (5, True), (61, False)])
def test_ffprobe_actual_duration(tmp_path, duration, valid):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg unavailable")
    path = tmp_path / "test.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=gold:s=180x320:r=5",
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    if valid:
        assert inspect_video(path) == duration
    else:
        with pytest.raises(ValueError):
            inspect_video(path)


def test_ffprobe_rejects_fake_extension(tmp_path):
    if not shutil.which("ffprobe"):
        pytest.skip("ffprobe unavailable")
    path = tmp_path / "fake.mp4"
    path.write_text("not a video")
    with pytest.raises(ValueError):
        inspect_video(path)


@pytest.mark.parametrize("format,mode", [("JPEG", "RGB"), ("PNG", "RGBA"), ("TIFF", "RGB")])
def test_image_conversion_and_resize(app, tmp_path, format, mode):
    from PIL import Image

    from app.services.media import compress_image

    source = tmp_path / "input"
    Image.new(mode, (1800, 1400), "gold").save(source, format)
    with app.app_context():
        variants = compress_image(source)
        for width, key in variants.items():
            with Image.open(path_for(key)) as result:
                assert result.format == "WEBP"
                assert result.size == (int(width), round(int(width) * 1400 / 1800))
                if mode == "RGBA":
                    # Opaque inputs may have their redundant alpha channel removed by WebP.
                    assert result.mode in ("RGB", "RGBA")
                assert path_for(key).stat().st_size < source.stat().st_size


def test_image_conversion_preserves_transparency(app, tmp_path):
    from PIL import Image

    from app.services.media import compress_image

    source = tmp_path / "transparent.png"
    Image.new("RGBA", (100, 100), (255, 0, 0, 0)).save(source)
    with app.app_context():
        variants = compress_image(source)
        with Image.open(path_for(variants["1280"])) as result:
            assert result.size == (100, 100)
            assert result.getpixel((0, 0))[3] == 0


def test_image_conversion_rejects_invalid(app, tmp_path):
    from app.services.media import compress_image

    source = tmp_path / "fake.jpg"
    source.write_text("invalid")
    with app.app_context(), pytest.raises(ValueError, match="supported image"):
        compress_image(source)


@pytest.mark.parametrize("container,codec", [("mov", "mpeg4"), ("webm", "libvpx-vp9")])
def test_video_conversion_accepts_other_formats(tmp_path, container, codec):
    import json

    from PIL import Image

    from app.services.media import transcode_video

    source, output, thumb = (tmp_path / name for name in (f"input.{container}", "out.mp4", "thumb.webp"))
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
         "color=c=gold:s=320x180:r=5", "-t", "5", "-c:v", codec, "-threads", "1", str(source)],
        check=True,
    )
    transcode_video(source, output, thumb)
    data = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output)]
    ))
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert (video["width"], video["height"]) == (720, 1280)
    assert video["pix_fmt"] == "yuv420p"
    assert float(data["format"]["duration"]) == 5
    with Image.open(thumb) as image:
        assert image.format == "WEBP" and image.size == (360, 640)


def test_photo_adjustments(app, tmp_path):
    from PIL import Image
    from app.services.media import compress_image
    source = tmp_path / 'photo.png'
    Image.new('RGB', (200, 100), (100, 100, 100)).save(source)
    with app.app_context():
        variants = compress_image(source, {'rotate': 90, 'square': True, 'brightness': .5})
        with Image.open(path_for(variants['1280'])) as result:
            assert result.size == (100, 100)
            assert 45 <= result.getpixel((50, 50))[0] <= 55


def test_video_trim_and_mute(tmp_path):
    import json
    from app.services.media import transcode_video
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg unavailable')
    source, output, thumb = (tmp_path / name for name in ('source.mp4', 'trim.mp4', 'trim.webp'))
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=gold:s=160x120:r=5', '-f', 'lavfi', '-i', 'sine=frequency=440',
                    '-t', '8', '-c:v', 'mpeg4', '-c:a', 'aac', '-threads', '1', str(source)], check=True)
    transcode_video(source, output, thumb, {'start': 1, 'end': 6, 'mute': True})
    data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                               '-show_format', '-of', 'json', str(output)]))
    assert abs(float(data['format']['duration']) - 5) < .1
    assert all(stream['codec_type'] != 'audio' for stream in data['streams'])
    with pytest.raises(ValueError, match='at least 5 seconds'):
        transcode_video(source, output, thumb, {'start': 5, 'end': 6})
