import pytest

from app.services.romaji import is_correct, to_romaji


@pytest.mark.parametrize(
    ("reading", "accepted", "rejected"),
    [
        ("がっこう", ["gakkou", "gakkoo", "gakkō"], ["gakko"]),
        ("ちょっと", ["chotto", "tyotto"], ["cchotto"]),
        ("コーヒー", ["koohii", "kōhī", "ko-hi-"], ["kohi"]),
        ("しんぶん", ["shimbun", "shinbun"], []),
        ("きんえん", ["kin'en"], []),
        ("マッチ", ["matchi", "macchi"], []),
        ("こんにちわ", ["konnichiwa"], ["konichiwa"]),
        ("とうきょう", ["toukyou", "tōkyō"], ["tokyo"]),
        ("せんせい", ["sensei", "sensee"], []),
        ("また あした", ["mata ashita", "mataashita"], []),
        ("を", ["o", "wo"], []),
        ("ｶﾞｯｺｳ", ["gakkou"], []),
    ],
)
def test_romaji_variants(reading: str, accepted: list[str], rejected: list[str]) -> None:
    for answer in accepted:
        assert is_correct([reading], answer), (reading, answer)
    for answer in rejected:
        assert not is_correct([reading], answer), (reading, answer)


def test_canonical_romaji() -> None:
    assert to_romaji("がっこう") == "gakkou"
    assert to_romaji("コーヒー") == "koohii"
