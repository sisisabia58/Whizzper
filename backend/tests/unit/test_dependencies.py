def test_cryptography_and_oauth_imports():
    import cryptography
    import google_auth_oauthlib
    assert cryptography.__version__ is not None
