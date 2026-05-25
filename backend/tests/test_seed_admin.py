from atlaslens.api.auth import hash_password, verify_password


class TestSeedAdminHelpers:
    def test_password_roundtrip(self) -> None:
        pw = "admin-pass-1234"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)
        assert not verify_password("wrong", hashed)

    def test_unique_hashes(self) -> None:
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2
