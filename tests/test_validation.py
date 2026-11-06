from src.utils.importante.validation import is_http_url


def test_http_url_validation() -> None:
    assert is_http_url("https://cdn.discordapp.com/image.png")
    assert is_http_url("http://example.com")
    assert not is_http_url("javascript:alert(1)")
    assert not is_http_url("not-a-url")
    assert not is_http_url(None)
