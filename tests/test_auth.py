"""Tests for auth functions and AWS connection CRUD in storage.db."""
import sqlite3

import pytest

from storage.db import (
    add_aws_connection,
    authenticate_user,
    create_schema,
    delete_aws_connection,
    get_aws_connections,
    get_connection,
    get_user_by_id,
    hash_password,
    register_user,
    update_aws_connection_status,
    update_user_profile,
    verify_password,
)


@pytest.fixture
def db_conn(tmp_path):
    """Fresh DB with schema for each test."""
    conn = get_connection(tmp_path / "test_auth.db")
    create_schema(conn)
    return conn


# =========================================================================
# Password hashing
# =========================================================================

class TestPasswordHashing:
    def test_round_trip(self):
        stored = hash_password("mysecret")
        assert verify_password("mysecret", stored)

    def test_wrong_password_fails(self):
        stored = hash_password("correct")
        assert not verify_password("wrong", stored)

    def test_different_salts(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        # Different salts -> different stored strings
        assert h1 != h2
        # But both still verify
        assert verify_password("same", h1)
        assert verify_password("same", h2)

    def test_malformed_hash_returns_false(self):
        assert not verify_password("any", "not-a-valid-hash")
        assert not verify_password("any", "")


# =========================================================================
# User registration
# =========================================================================

class TestRegisterUser:
    def test_creates_user(self, db_conn):
        uid = register_user(db_conn, "alice@test.com", "pass123", "Alice")
        assert uid.startswith("usr-")
        assert len(uid) == 16  # "usr-" + 12 hex chars

    def test_duplicate_email_raises(self, db_conn):
        register_user(db_conn, "dup@test.com", "pass1")
        with pytest.raises(ValueError, match="already registered"):
            register_user(db_conn, "dup@test.com", "pass2")

    def test_default_profile_name(self, db_conn):
        uid = register_user(db_conn, "bob@corp.io", "pw")
        user = get_user_by_id(db_conn, uid)
        assert user["profile_name"] == "bob"


# =========================================================================
# Authentication
# =========================================================================

class TestAuthenticateUser:
    def test_valid_creds_succeed(self, db_conn):
        register_user(db_conn, "auth@test.com", "secret")
        result = authenticate_user(db_conn, "auth@test.com", "secret")
        assert result is not None
        assert result["email"] == "auth@test.com"

    def test_wrong_password_returns_none(self, db_conn):
        register_user(db_conn, "auth2@test.com", "right")
        assert authenticate_user(db_conn, "auth2@test.com", "wrong") is None

    def test_nonexistent_email_returns_none(self, db_conn):
        assert authenticate_user(db_conn, "ghost@test.com", "any") is None

    def test_updates_last_login(self, db_conn):
        uid = register_user(db_conn, "login@test.com", "pw")
        # Before auth, last_login_at is NULL
        user_before = get_user_by_id(db_conn, uid)
        assert user_before["last_login_at"] is None

        authenticate_user(db_conn, "login@test.com", "pw")
        user_after = get_user_by_id(db_conn, uid)
        assert user_after["last_login_at"] is not None


# =========================================================================
# User profile
# =========================================================================

class TestUserProfile:
    def test_update_profile(self, db_conn):
        uid = register_user(db_conn, "profile@test.com", "pw", "Old Name")
        assert update_user_profile(db_conn, uid, "New Name")
        user = get_user_by_id(db_conn, uid)
        assert user["profile_name"] == "New Name"

    def test_update_nonexistent_user(self, db_conn):
        assert not update_user_profile(db_conn, "usr-doesnotexist", "Name")


# =========================================================================
# AWS Connection CRUD
# =========================================================================

class TestAWSConnectionCRUD:
    def test_add_and_get(self, db_conn):
        uid = register_user(db_conn, "aws@test.com", "pw")
        cid = add_aws_connection(
            db_conn, uid, "111111111111",
            "arn:aws:iam::111111111111:role/Test",
            connection_name="Prod",
        )
        assert isinstance(cid, int)

        conns = get_aws_connections(db_conn, uid)
        assert len(conns) == 1
        assert conns[0]["aws_account_id"] == "111111111111"
        assert conns[0]["connection_name"] == "Prod"

    def test_multiple_accounts_per_user(self, db_conn):
        uid = register_user(db_conn, "multi@test.com", "pw")
        add_aws_connection(db_conn, uid, "111", "arn:aws:iam::111:role/R")
        add_aws_connection(db_conn, uid, "222", "arn:aws:iam::222:role/R")

        conns = get_aws_connections(db_conn, uid)
        assert len(conns) == 2
        account_ids = {c["aws_account_id"] for c in conns}
        assert account_ids == {"111", "222"}

    def test_unique_constraint(self, db_conn):
        uid = register_user(db_conn, "uniq@test.com", "pw")
        add_aws_connection(db_conn, uid, "333", "arn:aws:iam::333:role/R")
        with pytest.raises(sqlite3.IntegrityError):
            add_aws_connection(db_conn, uid, "333", "arn:aws:iam::333:role/R2")

    def test_delete_connection(self, db_conn):
        uid = register_user(db_conn, "del@test.com", "pw")
        cid = add_aws_connection(db_conn, uid, "444", "arn:aws:iam::444:role/R")
        assert delete_aws_connection(db_conn, cid, uid)
        assert len(get_aws_connections(db_conn, uid)) == 0

    def test_delete_scoped_to_user(self, db_conn):
        uid1 = register_user(db_conn, "u1@test.com", "pw")
        uid2 = register_user(db_conn, "u2@test.com", "pw")
        cid = add_aws_connection(db_conn, uid1, "555", "arn:aws:iam::555:role/R")
        # uid2 should NOT be able to delete uid1's connection
        assert not delete_aws_connection(db_conn, cid, uid2)
        assert len(get_aws_connections(db_conn, uid1)) == 1

    def test_update_status(self, db_conn):
        uid = register_user(db_conn, "status@test.com", "pw")
        cid = add_aws_connection(db_conn, uid, "666", "arn:aws:iam::666:role/R")

        update_aws_connection_status(db_conn, cid, "success")
        conns = get_aws_connections(db_conn, uid)
        assert conns[0]["sync_status"] == "success"
        assert conns[0]["last_sync_at"] is not None

    def test_update_status_with_error(self, db_conn):
        uid = register_user(db_conn, "err@test.com", "pw")
        cid = add_aws_connection(db_conn, uid, "777", "arn:aws:iam::777:role/R")

        update_aws_connection_status(db_conn, cid, "failed", "AccessDenied")
        conns = get_aws_connections(db_conn, uid)
        assert conns[0]["sync_status"] == "failed"
        assert conns[0]["error_message"] == "AccessDenied"
