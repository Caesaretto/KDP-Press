"""Unit tests for the provider-agnostic generate_image() in generate_page.py.

Covers: provider selection logic, fal.ai primary path, OpenAI primary path,
auto-fallback on failure, IMAGE_FALLBACK=0 disables fallback, host-allowlist
rejection of unknown image URLs.

NO real API calls — both `fal_client` and the OpenAI SDK are monkeypatched.
"""
from __future__ import annotations

import io
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _tiny_png_bytes(color: str = "white") -> bytes:
    img = Image.new("RGB", (8, 12), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def clean_env(monkeypatch):
    """Strip all image-provider env vars so tests start from a known state."""
    for key in ("IMAGE_PROVIDER", "IMAGE_MODEL_FAL", "IMAGE_QUALITY_OPENAI",
                "IMAGE_FALLBACK", "FAL_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def _fake_fal_client(image_bytes: bytes,
                     url: str = "https://fal.media/files/abc/123.png"):
    """Build a fake fal_client module that returns a fake result dict."""
    fake = types.ModuleType("fal_client")

    def subscribe(model, arguments):
        return {"images": [{"url": url, "width": 1024, "height": 1536}]}

    fake.subscribe = subscribe
    return fake


def _patch_url_fetch(monkeypatch, image_bytes: bytes):
    """Patch _fetch_image_url to return canned bytes (no real network)."""
    import generate_page as gp
    monkeypatch.setattr(gp, "_fetch_image_url",
                        lambda url, timeout=60: image_bytes)


def _patch_openai_response(client_mock: MagicMock, image_bytes: bytes) -> None:
    """Configure a MagicMock OpenAI client to return b64-encoded image."""
    import base64
    msg = types.SimpleNamespace(
        b64_json=base64.b64encode(image_bytes).decode(),
        url=None,
    )
    client_mock.images.generate.return_value = types.SimpleNamespace(data=[msg])


# ── Provider selection ───────────────────────────────────────────────────────

def test_default_provider_is_fal_when_fal_key_set(clean_env, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk-test")
    img_bytes = _tiny_png_bytes()
    fake = _fake_fal_client(img_bytes)
    monkeypatch.setitem(sys.modules, "fal_client", fake)
    _patch_url_fetch(monkeypatch, img_bytes)

    import generate_page as gp
    result = gp.generate_image("test prompt", client=MagicMock())
    assert isinstance(result, Image.Image)
    assert result.size == (8, 12)  # tiny PNG fixture size


def test_default_provider_is_openai_when_no_fal_key(clean_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    img_bytes = _tiny_png_bytes()
    client = MagicMock()
    _patch_openai_response(client, img_bytes)

    import generate_page as gp
    result = gp.generate_image("test prompt", client=client)
    client.images.generate.assert_called_once()
    args, kwargs = client.images.generate.call_args
    assert kwargs.get("model") == "gpt-image-1"
    assert isinstance(result, Image.Image)


def test_explicit_provider_openai_overrides_fal_key(clean_env, monkeypatch):
    """Setting IMAGE_PROVIDER=openai forces OpenAI even if FAL_KEY exists."""
    monkeypatch.setenv("FAL_KEY", "fk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("IMAGE_PROVIDER", "openai")
    img_bytes = _tiny_png_bytes()
    client = MagicMock()
    _patch_openai_response(client, img_bytes)

    import generate_page as gp
    gp.generate_image("p", client=client)
    client.images.generate.assert_called_once()


def test_explicit_provider_fal_forces_fal(clean_env, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("IMAGE_PROVIDER", "fal")
    img_bytes = _tiny_png_bytes()
    fake = _fake_fal_client(img_bytes)
    subscribe_calls: list[tuple] = []
    fake.subscribe = lambda model, arguments: (
        subscribe_calls.append((model, arguments)),
        {"images": [{"url": "https://fal.media/x.png"}]},
    )[1]
    monkeypatch.setitem(sys.modules, "fal_client", fake)
    _patch_url_fetch(monkeypatch, img_bytes)

    import generate_page as gp
    gp.generate_image("p", client=MagicMock())
    assert subscribe_calls, "fal subscribe was not called"


def test_fal_model_defaults_to_schnell(clean_env, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk-test")
    img_bytes = _tiny_png_bytes()
    seen_models: list[str] = []
    fake = types.ModuleType("fal_client")
    fake.subscribe = lambda model, arguments: (
        seen_models.append(model),
        {"images": [{"url": "https://fal.media/x.png"}]},
    )[1]
    monkeypatch.setitem(sys.modules, "fal_client", fake)
    _patch_url_fetch(monkeypatch, img_bytes)

    import generate_page as gp
    gp.generate_image("p", client=MagicMock())
    assert seen_models == ["fal-ai/flux/schnell"]


def test_image_model_fal_env_overrides_default(clean_env, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk-test")
    monkeypatch.setenv("IMAGE_MODEL_FAL", "fal-ai/flux/dev")
    img_bytes = _tiny_png_bytes()
    seen_models: list[str] = []
    fake = types.ModuleType("fal_client")
    fake.subscribe = lambda model, arguments: (
        seen_models.append(model),
        {"images": [{"url": "https://fal.media/x.png"}]},
    )[1]
    monkeypatch.setitem(sys.modules, "fal_client", fake)
    _patch_url_fetch(monkeypatch, img_bytes)

    import generate_page as gp
    gp.generate_image("p", client=MagicMock())
    assert seen_models == ["fal-ai/flux/dev"]


def test_dev_model_uses_28_steps(clean_env, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk-test")
    monkeypatch.setenv("IMAGE_MODEL_FAL", "fal-ai/flux/dev")
    img_bytes = _tiny_png_bytes()
    seen_args: list[dict] = []
    fake = types.ModuleType("fal_client")
    fake.subscribe = lambda model, arguments: (
        seen_args.append(arguments),
        {"images": [{"url": "https://fal.media/x.png"}]},
    )[1]
    monkeypatch.setitem(sys.modules, "fal_client", fake)
    _patch_url_fetch(monkeypatch, img_bytes)

    import generate_page as gp
    gp.generate_image("p", client=MagicMock())
    assert seen_args[0]["num_inference_steps"] == 28


def test_schnell_uses_4_steps(clean_env, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk-test")
    img_bytes = _tiny_png_bytes()
    seen_args: list[dict] = []
    fake = types.ModuleType("fal_client")
    fake.subscribe = lambda model, arguments: (
        seen_args.append(arguments),
        {"images": [{"url": "https://fal.media/x.png"}]},
    )[1]
    monkeypatch.setitem(sys.modules, "fal_client", fake)
    _patch_url_fetch(monkeypatch, img_bytes)

    import generate_page as gp
    gp.generate_image("p", client=MagicMock())
    assert seen_args[0]["num_inference_steps"] == 4


# ── Auto-fallback ───────────────────────────────────────────────────────────

def test_fal_failure_falls_back_to_openai(clean_env, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    # fal raises
    fake = types.ModuleType("fal_client")
    fake.subscribe = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fal down"))
    monkeypatch.setitem(sys.modules, "fal_client", fake)
    # OpenAI returns
    img_bytes = _tiny_png_bytes()
    client = MagicMock()
    _patch_openai_response(client, img_bytes)

    import generate_page as gp
    result = gp.generate_image("p", client=client)
    client.images.generate.assert_called_once()
    assert isinstance(result, Image.Image)


def test_fallback_disabled_propagates_error(clean_env, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("IMAGE_FALLBACK", "0")
    fake = types.ModuleType("fal_client")
    fake.subscribe = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fal down"))
    monkeypatch.setitem(sys.modules, "fal_client", fake)
    client = MagicMock()
    img_bytes = _tiny_png_bytes()
    _patch_openai_response(client, img_bytes)

    import generate_page as gp
    with pytest.raises(RuntimeError, match="fal down"):
        gp.generate_image("p", client=client)
    client.images.generate.assert_not_called()


def test_openai_failure_falls_back_to_fal(clean_env, monkeypatch):
    """If primary is OpenAI and FAL_KEY is set, failure should try fal."""
    monkeypatch.setenv("FAL_KEY", "fk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("IMAGE_PROVIDER", "openai")
    client = MagicMock()
    client.images.generate.side_effect = RuntimeError("openai down")
    img_bytes = _tiny_png_bytes()
    fake = _fake_fal_client(img_bytes)
    monkeypatch.setitem(sys.modules, "fal_client", fake)
    _patch_url_fetch(monkeypatch, img_bytes)

    import generate_page as gp
    result = gp.generate_image("p", client=client)
    assert isinstance(result, Image.Image)


def test_no_credentials_propagates_error(clean_env, monkeypatch):
    """No FAL_KEY and no OPENAI_API_KEY: cannot fall back, raises."""
    # default provider becomes openai, but client.images.generate will be
    # called and the mock can raise to simulate auth failure
    client = MagicMock()
    client.images.generate.side_effect = RuntimeError("no api key")
    import generate_page as gp
    with pytest.raises(RuntimeError):
        gp.generate_image("p", client=client)


# ── Host allowlist ──────────────────────────────────────────────────────────

def test_fetch_rejects_non_https():
    import generate_page as gp
    with pytest.raises(RuntimeError, match="non-HTTPS"):
        gp._fetch_image_url("http://fal.media/x.png")


def test_fetch_rejects_unknown_host():
    import generate_page as gp
    with pytest.raises(RuntimeError, match="Refusing image host"):
        gp._fetch_image_url("https://evil.example.com/x.png")


def test_fetch_allows_fal_media(monkeypatch):
    """Verify fal.media is in the allowlist (network call still patched)."""
    import generate_page as gp
    captured: list[str] = []
    class FakeResponse:
        def read(self): return b"OK"
        def __enter__(self): return self
        def __exit__(self, *a): pass
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda url, timeout=60: (captured.append(url), FakeResponse())[1],
    )
    out = gp._fetch_image_url("https://fal.media/files/abc.png")
    assert out == b"OK"
    assert captured == ["https://fal.media/files/abc.png"]


def test_fetch_allows_replicate_delivery(monkeypatch):
    import generate_page as gp
    class FakeResponse:
        def read(self): return b"OK"
        def __enter__(self): return self
        def __exit__(self, *a): pass
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda url, timeout=60: FakeResponse(),
    )
    assert gp._fetch_image_url("https://replicate.delivery/abc.png") == b"OK"


def test_fal_without_key_raises_clear_error(clean_env, monkeypatch):
    """If IMAGE_PROVIDER=fal but FAL_KEY missing, error message is clear."""
    monkeypatch.setenv("IMAGE_PROVIDER", "fal")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")  # OK for fallback
    monkeypatch.setenv("IMAGE_FALLBACK", "0")  # no fallback so error propagates
    import generate_page as gp
    with pytest.raises(RuntimeError, match="FAL_KEY"):
        gp.generate_image("p", client=MagicMock())
