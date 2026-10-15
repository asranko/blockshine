import os
from datetime import timedelta

# Isolate tests from any production database configuration.
os.environ["DATABASE_URL"] = "sqlite:///./lub_test.db"
os.environ["SECRET_KEY"] = "ci-test-key-not-for-production"
os.environ["ENVIRONMENT"] = "test"

from fastapi.testclient import TestClient
import main


client = TestClient(main.app)


def register(username: str):
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"{username}@example.com",
            "username": username,
            "display_name": f"Test {username}",
            "password": "Test-only-password-2026!",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload["access_token"], payload["user"]


def auth(token: str):
    return {"Authorization": f"Bearer {token}"}


def make_post(token: str, body: str = "اختبار آلي لفترة الانتظار قبل نشر المنشور."):
    response = client.post(
        "/api/posts",
        headers=auth(token),
        json={"body": body, "intention": "أفيد", "topic": "اختبار"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def age_post_past_fridge(post_id: str):
    with main.SessionLocal() as db:
        post = db.get(main.Post, post_id)
        assert post is not None
        post.confirm_after = main.now_utc() - timedelta(seconds=2)
        db.commit()


def setup_function():
    main.Base.metadata.drop_all(main.engine)
    main.Base.metadata.create_all(main.engine)


def teardown_function():
    main.Base.metadata.drop_all(main.engine)


def test_health_identifies_sqlite_as_non_postgres():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database_backend"] == "sqlite"
    assert response.json()["postgres_configured"] is False


def test_meta_encodes_lub_product_rules():
    response = client.get("/api/meta")
    assert response.status_code == 200
    data = response.json()
    assert data["fridge_hours"] == 12
    assert data["intentions"] == ["أفيد", "أتعلم", "أوثّق ذكرى", "أطلب مساعدة"]
    assert data["signals"] == ["استفدت", "فكرت", "تواصلت معك"]


def test_pending_post_cannot_be_confirmed_early_or_appear_in_public_feed():
    token, _ = register("qa_author")
    post = make_post(token)

    early = client.post(f"/api/posts/{post['id']}/confirm", headers=auth(token))
    assert early.status_code == 409, early.text

    feed = client.get("/api/posts").json()["items"]
    assert all(item["id"] != post["id"] for item in feed)

    mine = client.get("/api/posts/mine", headers=auth(token)).json()["items"]
    assert any(item["id"] == post["id"] and item["status"] == "pending" for item in mine)


def test_post_publishes_only_after_elapsed_fridge_and_explicit_confirmation():
    token, _ = register("qa_publish")
    post = make_post(token)
    age_post_past_fridge(post["id"])

    confirmed = client.post(f"/api/posts/{post['id']}/confirm", headers=auth(token))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "published"

    feed = client.get("/api/posts").json()["items"]
    assert any(item["id"] == post["id"] for item in feed)


def test_users_cannot_edit_delete_or_confirm_other_users_posts():
    owner_token, _ = register("qa_owner")
    stranger_token, _ = register("qa_stranger")
    post = make_post(owner_token)

    update = client.patch(
        f"/api/posts/{post['id']}",
        headers=auth(stranger_token),
        json={"body": "محاولة تعديل غير مصرح بها.", "intention": "أفيد", "topic": "اختبار"},
    )
    assert update.status_code == 403

    delete = client.delete(f"/api/posts/{post['id']}", headers=auth(stranger_token))
    assert delete.status_code == 403

    confirm = client.post(f"/api/posts/{post['id']}/confirm", headers=auth(stranger_token))
    assert confirm.status_code == 403


def test_semantic_signals_do_not_expose_public_aggregate_counts():
    owner_token, _ = register("qa_signal_owner")
    reader_token, _ = register("qa_signal_reader")
    post = make_post(owner_token)
    age_post_past_fridge(post["id"])
    published = client.post(f"/api/posts/{post['id']}/confirm", headers=auth(owner_token))
    assert published.status_code == 200, published.text

    signal = client.put(
        f"/api/posts/{post['id']}/signals/فكرت",
        headers=auth(reader_token),
    )
    assert signal.status_code == 200, signal.text

    feed = client.get("/api/posts", headers=auth(reader_token)).json()["items"]
    item = next(item for item in feed if item["id"] == post["id"])
    assert item["my_signals"] == ["فكرت"]
    assert "signals" not in item



def test_hidden_profile_posts_are_not_visible_or_interactable_by_others():
    owner_token, _ = register("qa_hidden_owner")
    reader_token, _ = register("qa_hidden_reader")
    created = client.post(
        "/api/posts",
        headers=auth(owner_token),
        json={"body": "منشور خاص لا يظهر عند إخفاء الملف الشخصي.", "intention": "أفيد", "topic": "موضوع خاص"},
    )
    assert created.status_code == 201, created.text
    post = created.json()
    age_post_past_fridge(post["id"])
    confirmed = client.post(f"/api/posts/{post['id']}/confirm", headers=auth(owner_token))
    assert confirmed.status_code == 200, confirmed.text

    hidden = client.patch(
        "/api/profile",
        headers=auth(owner_token),
        json={"display_name": "Hidden Owner", "bio": "", "profile_hidden": True},
    )
    assert hidden.status_code == 200, hidden.text

    feed = client.get("/api/posts", headers=auth(reader_token)).json()["items"]
    assert all(item["id"] != post["id"] for item in feed)

    comment = client.post(
        f"/api/posts/{post['id']}/comments",
        headers=auth(reader_token),
        json={"body": "تعليق غير مصرح به"},
    )
    assert comment.status_code == 404

    signal = client.put(
        f"/api/posts/{post['id']}/signals/فكرت",
        headers=auth(reader_token),
    )
    assert signal.status_code == 404

    saved = client.put(f"/api/posts/{post['id']}/save", headers=auth(reader_token))
    assert saved.status_code == 404

    report = client.post(
        f"/api/posts/{post['id']}/reports",
        headers=auth(reader_token),
        json={"reason": "spam", "details": ""},
    )
    assert report.status_code == 404

    topics = client.get("/api/discovery/topics").json()["items"]
    assert all(item["topic"] != "موضوع خاص" for item in topics)
