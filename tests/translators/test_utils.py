from jako.translators.utils import detect_repeated_text


def test_detect_repeated_text():
    assert detect_repeated_text("helloworldhello", 15) is None
    assert detect_repeated_text("helloworldhello", 6) is None
    assert detect_repeated_text("helloworldhello", 3) == (0, "hel")
