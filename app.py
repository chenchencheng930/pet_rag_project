from flask import Flask, jsonify, request, render_template
import traceback
import os
import requests
import time
from rule_filter import apply_rules
from recommender import build_assessment_result
from assessment_engine import AssessmentEngine
from rag_engine import RagEngine
from db import get_db_connection
# followup_agent 已停用：评估接口不再返回 code=210 追问流程
import re
from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv


app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("FLASK_SECRET_KEY", "replace-with-a-real-secret")

COZE_BOT_ID = os.getenv("COZE_BOT_ID")
COZE_API_TOKEN = os.getenv("COZE_API_TOKEN")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,   # 本地开发先 False，https 部署再改 True
)



def ensure_user_phone_column():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM users LIKE 'phone'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(20) UNIQUE NULL")
                conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print("Warning: cannot ensure users.phone column:", e)
    finally:
        if conn:
            conn.close()

ensure_user_phone_column()

assessment_engine = AssessmentEngine()
rag_engine = RagEngine()




def format_dt(dt):
    if not dt:
        return ""
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt)


def is_text_has_emoji(value):
    """Reject most emoji/symbol pictographs in post/comment text."""
    if not value:
        return False
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001FAFF"
        "\U00002700-\U000027BF"
        "\U00002600-\U000026FF"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.search(value) is not None


def get_current_user_record():
    user_id = session.get("user_id")
    if not user_id:
        return None

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, phone, avatar_data, is_admin FROM users WHERE id=%s",
                (user_id,)
            )
            return cursor.fetchone()
    except Exception as e:
        print("Warning: cannot fetch current user:", e)
        return None
    finally:
        if conn:
            conn.close()


def is_admin_user(user=None):
    if not user:
        user = get_current_user_record()
    if not user:
        return False

    if int(user.get("is_admin") or 0) == 1:
        return True

    admin_usernames = [
        item.strip()
        for item in (os.getenv("ADMIN_USERNAMES") or "").split(",")
        if item.strip()
    ]
    admin_phones = [
        item.strip()
        for item in (os.getenv("ADMIN_PHONES") or "").split(",")
        if item.strip()
    ]

    return (user.get("username") in admin_usernames) or (user.get("phone") in admin_phones)


def ensure_community_schema():
    """Small idempotent schema upgrades for profile/community features."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # users: avatar + admin flag
            cursor.execute("SHOW COLUMNS FROM users LIKE 'avatar_data'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN avatar_data LONGTEXT NULL")

            cursor.execute("SHOW COLUMNS FROM users LIKE 'is_admin'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0")

            # posts: make sure user_id exists
            cursor.execute("SHOW COLUMNS FROM community_posts LIKE 'user_id'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE community_posts ADD COLUMN user_id INT NULL")

            # comments: user/reply/image support
            cursor.execute("SHOW COLUMNS FROM community_comments LIKE 'user_id'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE community_comments ADD COLUMN user_id INT NULL")

            cursor.execute("SHOW COLUMNS FROM community_comments LIKE 'parent_comment_id'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE community_comments ADD COLUMN parent_comment_id INT NULL")

            cursor.execute("SHOW COLUMNS FROM community_comments LIKE 'reply_to_user_id'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE community_comments ADD COLUMN reply_to_user_id INT NULL")

            cursor.execute("SHOW COLUMNS FROM community_comments LIKE 'image_url'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE community_comments ADD COLUMN image_url LONGTEXT NULL")

            # likes table for one-user-one-like toggle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS community_post_likes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    post_id INT NOT NULL,
                    user_id INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_post_user (post_id, user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # notifications table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS community_notifications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    actor_user_id INT NULL,
                    actor_name VARCHAR(255) NULL,
                    post_id INT NULL,
                    comment_id INT NULL,
                    type VARCHAR(50) NOT NULL,
                    message VARCHAR(500) NOT NULL,
                    is_read TINYINT(1) NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print("Warning: cannot ensure community schema:", e)
    finally:
        if conn:
            conn.close()


def create_notification(cursor, user_id, actor_user_id, actor_name, post_id, comment_id, notify_type, message):
    if not user_id or (actor_user_id and int(user_id) == int(actor_user_id)):
        return

    cursor.execute(
        """
        INSERT INTO community_notifications
        (user_id, actor_user_id, actor_name, post_id, comment_id, type, message)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, actor_user_id, actor_name, post_id, comment_id, notify_type, message)
    )



ensure_community_schema()

@app.route("/db-test", methods=["GET"])
def db_test():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS ok")
            row = cursor.fetchone()
        return jsonify({"code": 200, "message": "database connected", "data": row})
    except Exception as e:
        return jsonify({"code": 500, "message": "database error", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/")
def home():
    print("home session user_id =", session.get("user_id"))
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("index.html")



@app.route("/chat")
def chat():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("chat.html")




@app.route("/api/chat", methods=["POST"])
def api_chat():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"code": 401, "message": "未登录"}), 401

    if not COZE_BOT_ID or not COZE_API_TOKEN:
        return jsonify({"code": 500, "message": "Coze 配置缺失，请检查 .env 中的 COZE_BOT_ID 和 COZE_API_TOKEN"}), 500

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"code": 400, "message": "query 不能为空"}), 400

    headers = {
        "Authorization": f"Bearer {COZE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        create_payload = {
            "bot_id": COZE_BOT_ID,
            "user_id": str(user_id),
            "stream": False,
            "auto_save_history": True,
            "additional_messages": [
                {
                    "role": "user",
                    "content": query,
                    "content_type": "text"
                }
            ]
        }

        create_resp = requests.post(
            "https://api.coze.cn/v3/chat",
            headers=headers,
            json=create_payload,
            timeout=60
        )

        try:
            create_json = create_resp.json()
        except Exception:
            return jsonify({
                "code": 500,
                "message": "Coze 创建会话返回的不是合法 JSON",
                "raw": create_resp.text
            }), 500

        if create_resp.status_code != 200:
            return jsonify({
                "code": create_resp.status_code,
                "message": "Coze 创建会话失败",
                "data": create_json
            }), create_resp.status_code

        create_data = create_json.get("data") or {}
        conversation_id = create_data.get("conversation_id")
        chat_id = create_data.get("id") or create_data.get("chat_id")

        answer = extract_coze_answer(create_json)
        if answer:
            return jsonify({"code": 200, "message": "success", "data": {"answer": answer, "raw": create_json}})

        if not conversation_id or not chat_id:
            return jsonify({
                "code": 500,
                "message": "Coze 未返回 conversation_id 或 chat_id",
                "data": create_json
            }), 500

        final_chat_json = None
        terminal_status = None

        for _ in range(90):
            retrieve_resp = requests.get(
                "https://api.coze.cn/v3/chat/retrieve",
                headers=headers,
                params={"conversation_id": conversation_id, "chat_id": chat_id},
                timeout=30
            )

            try:
                retrieve_json = retrieve_resp.json()
            except Exception:
                return jsonify({
                    "code": 500,
                    "message": "Coze 查询会话状态返回的不是合法 JSON",
                    "raw": retrieve_resp.text
                }), 500

            if retrieve_resp.status_code != 200:
                return jsonify({
                    "code": retrieve_resp.status_code,
                    "message": "Coze 查询会话状态失败",
                    "data": retrieve_json
                }), retrieve_resp.status_code

            final_chat_json = retrieve_json
            status = (retrieve_json.get("data") or {}).get("status")
            terminal_status = status

            if status == "completed":
                break

            if status in ("failed", "requires_action", "canceled", "cancelled"):
                return jsonify({
                    "code": 500,
                    "message": f"Coze 会话未完成，状态：{status}",
                    "data": retrieve_json
                }), 500

            time.sleep(1)

        if terminal_status != "completed":
            return jsonify({
                "code": 504,
                "message": "Coze 回复超时，请稍后重试",
                "data": final_chat_json
            }), 504

        msg_resp = requests.get(
            "https://api.coze.cn/v3/chat/message/list",
            headers=headers,
            params={"conversation_id": conversation_id, "chat_id": chat_id},
            timeout=30
        )

        try:
            msg_json = msg_resp.json()
        except Exception:
            return jsonify({
                "code": 500,
                "message": "Coze 消息列表返回的不是合法 JSON",
                "raw": msg_resp.text
            }), 500

        if msg_resp.status_code != 200:
            return jsonify({
                "code": msg_resp.status_code,
                "message": "Coze 获取消息列表失败",
                "data": msg_json
            }), msg_resp.status_code

        answer = extract_coze_answer(msg_json)
        if not answer:
            return jsonify({"code": 500, "message": "未获取到模型回复", "data": msg_json}), 500

        return jsonify({"code": 200, "message": "success", "data": {"answer": answer, "raw": msg_json}})

    except requests.RequestException as e:
        return jsonify({"code": 500, "message": "调用 Coze 失败", "error": str(e)}), 500


def extract_coze_answer(payload):
    """Extract answer text from common Coze response shapes."""
    if not isinstance(payload, dict):
        return ""

    data = payload.get("data")

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("type") == "answer" and item.get("content"):
                return item.get("content")
        for item in data:
            if isinstance(item, dict) and item.get("role") == "assistant" and item.get("content"):
                return item.get("content")

    if isinstance(data, dict):
        if data.get("answer"):
            return data.get("answer")

        messages = data.get("messages") or data.get("message") or []
        if isinstance(messages, list):
            for item in messages:
                if isinstance(item, dict) and item.get("type") == "answer" and item.get("content"):
                    return item.get("content")
            for item in messages:
                if isinstance(item, dict) and item.get("role") == "assistant" and item.get("content"):
                    return item.get("content")

    if payload.get("answer"):
        return payload.get("answer")

    return ""


@app.route("/dashboard")
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("dashboard.html")


@app.route("/community")
def community():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("community.html")


@app.route("/reminder")
def reminder():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("reminder.html")


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("profile.html")


@app.route("/my_posts")
def my_posts():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("my_posts.html")

@app.route("/my-pets")
def my_pets():
    return render_template("my_pets.html")


@app.route("/login")
def login():
    return render_template("login.html")
def valid_phone(phone):
    return re.fullmatch(r"1\d{10}", phone or "") is not None

@app.route("/api/register", methods=["POST"])
def api_register():
    conn = None
    try:
        data = request.get_json(silent=True) or {}
        phone = (data.get("phone") or "").strip()
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

        if not phone or not username or not password:
            return jsonify({"code": 400, "message": "手机号、用户名、密码不能为空"}), 400
        if not valid_phone(phone):
            return jsonify({"code": 400, "message": "请输入正确的11位手机号"}), 400

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE phone=%s OR username=%s",
                (phone, username)
            )
            existed = cursor.fetchone()
            if existed:
                return jsonify({"code": 400, "message": "手机号或用户名已存在"}), 400

            password_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (phone, username, password) VALUES (%s, %s, %s)",
                (phone, username, password_hash)
            )
            user_id = cursor.lastrowid

        conn.commit()
        session["user_id"] = user_id
        session["username"] = username
        session["phone"] = phone
        session.permanent = True
        return jsonify({"code": 200, "message": "注册成功", "data": {"id": user_id, "username": username, "phone": phone}})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"code": 500, "message": "注册失败", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/login", methods=["POST"])
def api_login():
    conn = None
    try:
        data = request.get_json(silent=True) or {}
        phone = (data.get("phone") or "").strip()
        password = (data.get("password") or "").strip()

        if not phone or not password:
            return jsonify({"code": 400, "message": "手机号和密码不能为空"}), 400

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, phone, username, password FROM users WHERE phone=%s OR username=%s",
                (phone, phone)
            )
            user = cursor.fetchone()

        if not user or not check_password_hash(user["password"], password):
            return jsonify({"code": 400, "message": "手机号或密码错误"}), 400

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["phone"] = user["phone"]
        session.permanent = True
        print("login success, session user_id =", session.get("user_id"))
        return jsonify({
            "code": 200,
            "message": "登录成功",
            "data": {
                "id": user["id"],
                "username": user["username"],
                "phone": user["phone"]
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "message": "登录失败", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/me", methods=["GET"])
def api_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"code": 401, "message": "未登录"}), 401

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, phone, avatar_data, is_admin FROM users WHERE id=%s",
                (user_id,)
            )
            user = cursor.fetchone()

        if not user:
            session.clear()
            return jsonify({"code": 401, "message": "用户不存在"}), 401

        phone = user["phone"]
        masked_phone = phone[:3] + "****" + phone[-4:] if phone and len(phone) >= 11 else phone

        return jsonify({
            "code": 200,
            "message": "success",
            "data": {
                "id": user["id"],
                "username": user["username"],
                "phone": phone,
                "masked_phone": masked_phone,
                "avatar_data": user.get("avatar_data") or "",
                "is_admin": is_admin_user(user)
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "message": "获取用户信息失败", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()



@app.route("/api/account/username", methods=["POST"])
def api_account_username():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"code": 401, "message": "未登录"}), 401

    data = request.get_json(silent=True) or {}
    new_username = (data.get("username") or "").strip()

    if not new_username:
        return jsonify({"code": 400, "message": "用户名不能为空"}), 400

    if len(new_username) < 2 or len(new_username) > 20:
        return jsonify({"code": 400, "message": "用户名长度需为 2-20 个字符"}), 400

    # 只限制明显会破坏显示/数据库的特殊控制字符，不限制 emoji。
    if re.search(r"[<>\"'\\\\/]", new_username):
        return jsonify({"code": 400, "message": "用户名不能包含特殊符号 < > 引号 反斜杠 斜杠"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE username=%s AND id<>%s",
                (new_username, user_id)
            )
            if cursor.fetchone():
                return jsonify({"code": 400, "message": "该用户名已被占用"}), 400

            cursor.execute(
                "UPDATE users SET username=%s WHERE id=%s",
                (new_username, user_id)
            )

            # 同步历史帖子和评论展示名，避免个人主页改名后社区旧内容还是旧名。
            cursor.execute(
                "UPDATE community_posts SET author_name=%s WHERE user_id=%s",
                (new_username, user_id)
            )
            cursor.execute(
                "UPDATE community_comments SET author_name=%s WHERE user_id=%s",
                (new_username, user_id)
            )

        conn.commit()
        session["username"] = new_username
        return jsonify({"code": 200, "message": "用户名已更新", "data": {"username": new_username}})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"code": 500, "message": "用户名更新失败", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()




@app.route("/api/account/security", methods=["POST"])
def api_account_security():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"code": 401, "message": "未登录"}), 401

    data = request.get_json(silent=True) or {}
    old_password = (data.get("old_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()
    new_phone = (data.get("new_phone") or "").strip()

    if not old_password:
        return jsonify({"code": 400, "message": "请输入当前密码验证身份"}), 400
    if not new_phone and not new_password:
        return jsonify({"code": 400, "message": "请填写要更新的新手机号或新密码"}), 400
    if new_phone and not valid_phone(new_phone):
        return jsonify({"code": 400, "message": "请输入正确的11位手机号"}), 400
    if new_password and len(new_password) < 8:
        return jsonify({"code": 400, "message": "新密码长度至少8位"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT phone, password FROM users WHERE id=%s",
                (user_id,)
            )
            user = cursor.fetchone()
            if not user:
                session.clear()
                return jsonify({"code": 401, "message": "用户不存在"}), 401

            if not check_password_hash(user["password"], old_password):
                return jsonify({"code": 400, "message": "当前密码不正确"}), 400

            updates = []
            params = []

            if new_phone and new_phone != user["phone"]:
                cursor.execute(
                    "SELECT id FROM users WHERE phone=%s AND id<>%s",
                    (new_phone, user_id)
                )
                if cursor.fetchone():
                    return jsonify({"code": 400, "message": "该手机号已被其他账号使用"}), 400
                updates.append("phone=%s")
                params.append(new_phone)

            if new_password:
                updates.append("password=%s")
                params.append(generate_password_hash(new_password))

            if updates:
                params.append(user_id)
                cursor.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE id=%s",
                    tuple(params)
                )

        conn.commit()
        if new_phone:
            session["phone"] = new_phone
        return jsonify({"code": 200, "message": "更新成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"code": 500, "message": "账户安全更新失败", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()



@app.route("/api/profile/avatar", methods=["POST"])
def api_profile_avatar():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"code": 401, "message": "未登录"}), 401

    data = request.get_json(silent=True) or {}
    avatar_data = data.get("avatar_data") or ""

    if not avatar_data:
        return jsonify({"code": 400, "message": "头像不能为空"}), 400

    # base64 图片很长，简单限制一下，避免误传超大文件。
    if len(avatar_data) > 2_500_000:
        return jsonify({"code": 400, "message": "头像图片过大，请选择较小图片"}), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET avatar_data=%s WHERE id=%s",
                (avatar_data, user_id)
            )
        conn.commit()
        return jsonify({"code": 200, "message": "头像已更新", "data": {"avatar_data": avatar_data}})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"code": 500, "message": "头像保存失败", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"code": 200, "message": "已退出登录"})


@app.route("/api/pet-profile", methods=["GET"])
def get_pet_profile():
    conn = None
    try:
        username = request.args.get("username")
        if not username:
            return jsonify({"code": 400, "message": "username 不能为空"}), 400

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT pet_name, pet_gender, pet_type, age_stage, weight, bcs, sterilized, profile_notes, updated_at
                FROM pet_profiles
                WHERE username = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (username,)
            )
            row = cursor.fetchone()

        return jsonify({"code": 200, "message": "success", "data": row or {}})
    except Exception as e:
        return jsonify({"code": 500, "message": "failed to get pet profile", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route("/api/pet-profile", methods=["POST"])
def save_pet_profile():
    conn = None
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400

        username = data.get("username")
        pet_name = data.get("pet_name")
        pet_gender = data.get("pet_gender")
        pet_type = data.get("pet_type")
        age_stage = data.get("age_stage")
        weight = data.get("weight")
        bcs = data.get("bcs")
        sterilized = data.get("sterilized")
        profile_notes = data.get("profile_notes")

        if not username or not pet_type or not age_stage or not bcs:
            return jsonify({"code": 400, "message": "缺少必要字段"}), 400

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id FROM pet_profiles
                WHERE username = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (username,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE pet_profiles
                    SET pet_name=%s, pet_gender=%s, pet_type=%s, age_stage=%s, weight=%s, bcs=%s, sterilized=%s, profile_notes=%s
                    WHERE id=%s
                    """,
                    (pet_name, pet_gender, pet_type, age_stage, weight, bcs, sterilized, profile_notes, existing["id"])
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO pet_profiles (username, pet_name, pet_gender, pet_type, age_stage, weight, bcs, sterilized, profile_notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (username, pet_name, pet_gender, pet_type, age_stage, weight, bcs, sterilized, profile_notes)
                )

        conn.commit()
        return jsonify({"code": 200, "message": "success"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"code": 500, "message": "failed to save pet profile", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()



@app.route("/health", methods=["GET"])
def health():
    return jsonify({"code": 200, "message": "ok"})


@app.route("/assessment", methods=["POST"])
def assessment():
    conn = None
    try:
        data = request.get_json(silent=True) or {}
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400

        pet_type = data.get("pet_type", "")
        basic_info = data.get("basic_info", {})
        symptoms = data.get("symptoms", {})
        medical_indicators = data.get("medical_indicators", {})
        raw_primary_concern = data.get("primary_concern", "unknown")

        if isinstance(raw_primary_concern, list):
            selected_concerns = [item for item in raw_primary_concern if item]
        else:
            selected_concerns = [raw_primary_concern] if raw_primary_concern else []

        # 多症状/多关注点：不再只取第一个，而是保留完整列表。
        primary_concern = selected_concerns[0] if selected_concerns else "unknown"

        # 追问功能已停用：所有评估请求直接返回最终结果，不再进入 code=210 need_followup。
        user_info = {
            "pet_type": pet_type,
            "primary_concern": primary_concern,
            "primary_concerns": selected_concerns,
            "basic_info": basic_info,
            "symptoms": symptoms,
            "medical_indicators": medical_indicators,
            "user_selected_concerns": selected_concerns,
            "summary": {
                "pet_type": pet_type,
                "age_stage": basic_info.get("age_stage", "unknown"),
                "weight": basic_info.get("weight", 0),
                "bcs": basic_info.get("bcs", "normal")
            }
        }

        assessment_result = assessment_engine.assess(user_info)

        suspected_conditions = assessment_result.get("suspected_conditions", [])

        candidate_keys = [
            item.get("condition_key")
            for item in suspected_conditions
            if item.get("condition_key")
        ]

        # 综合用户勾选项 + 评估引擎识别出的中高风险方向。
        concern_keys = []
        for key in selected_concerns + candidate_keys:
            if key and key != "unknown" and key not in concern_keys:
                concern_keys.append(key)

        if not concern_keys:
            concern_keys = [primary_concern or "unknown"]

        # primary_concern 保留一个主方向兼容旧逻辑；primary_concerns 用于多方向过滤和推荐。
        concern_key = concern_keys[0]
        user_info["primary_concern"] = concern_key
        user_info["primary_concerns"] = concern_keys
        user_info["user_selected_concerns"] = selected_concerns

        all_candidates = []
        seen_candidate_texts = set()

        for current_concern in concern_keys:
            query = f"适合{pet_type}的{current_concern}方向处方粮推荐"
            retrieved_items = rag_engine.retrieve(
                pet_type=pet_type,
                concern_key=current_concern,
                query=query
            )

            for item in retrieved_items:
                item_copy = dict(item)
                metadata = dict(item_copy.get("metadata", {}))
                metadata["matched_concern"] = current_concern
                item_copy["metadata"] = metadata

                text_key = item_copy.get("text", "")
                if text_key and text_key not in seen_candidate_texts:
                    seen_candidate_texts.add(text_key)
                    all_candidates.append(item_copy)

        filtered_items = apply_rules(all_candidates, user_info)

        result = build_assessment_result(
            filtered_items=filtered_items,
            user_info=user_info,
            assessment_result=assessment_result
        )

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO assessments (pet_id, user_id, category, result, suggestion)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    None,
                    session.get("user_id"),
                    ",".join(concern_keys),
                    str(result.get("suspected_conditions", [])),
                    " | ".join(result.get("diet_advice", []))
                )
            )
        conn.commit()

        return jsonify({"code": 200, "message": "success", "data": result})

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"code": 500, "message": "assessment failed", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/community/posts", methods=["GET"])
def get_community_posts():
    conn = None
    try:
        current_user_id = session.get("user_id")
        current_user = get_current_user_record()
        current_is_admin = is_admin_user(current_user)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id, p.user_id, p.author_name, p.topic, p.content, p.image_url,
                       p.like_count, p.comment_count, p.created_at,
                       u.avatar_data
                FROM community_posts p
                LEFT JOIN users u ON p.user_id = u.id
                ORDER BY p.id DESC
                """
            )
            posts = cursor.fetchall()

            cursor.execute(
                """
                SELECT c.id, c.post_id, c.user_id, c.parent_comment_id, c.reply_to_user_id,
                       c.author_name, c.content, c.image_url, c.created_at,
                       u.avatar_data,
                       ru.username AS reply_to_username
                FROM community_comments c
                LEFT JOIN users u ON c.user_id = u.id
                LEFT JOIN users ru ON c.reply_to_user_id = ru.id
                ORDER BY c.id ASC
                """
            )
            comments = cursor.fetchall()

            liked_ids = set()
            if current_user_id:
                cursor.execute(
                    "SELECT post_id FROM community_post_likes WHERE user_id=%s",
                    (current_user_id,)
                )
                liked_ids = {row["post_id"] for row in cursor.fetchall()}

        comments_map = {}
        for item in comments:
            comments_map.setdefault(item["post_id"], []).append({
                "id": item["id"],
                "post_id": item["post_id"],
                "user_id": item.get("user_id"),
                "parent_comment_id": item.get("parent_comment_id"),
                "reply_to_user_id": item.get("reply_to_user_id"),
                "reply_to_username": item.get("reply_to_username") or "",
                "author_name": item.get("author_name") or "匿名用户",
                "avatar_data": item.get("avatar_data") or "",
                "content": item.get("content") or "",
                "image_url": item.get("image_url") or "",
                "created_at": format_dt(item.get("created_at"))
            })

        data = []
        for post in posts:
            is_owner = current_user_id and post.get("user_id") and int(current_user_id) == int(post["user_id"])
            data.append({
                "id": post["id"],
                "user_id": post.get("user_id"),
                "author_name": post.get("author_name") or "匿名用户",
                "avatar_data": post.get("avatar_data") or "",
                "topic": post.get("topic") or "",
                "content": post.get("content") or "",
                "image_url": post.get("image_url") or "",
                "like_count": post.get("like_count") or 0,
                "comment_count": post.get("comment_count") or 0,
                "created_at": format_dt(post.get("created_at")),
                "liked_by_me": post["id"] in liked_ids,
                "can_delete": bool(is_owner or current_is_admin),
                "comments_list": comments_map.get(post["id"], [])
            })

        return jsonify({
            "code": 200,
            "message": "success",
            "data": data,
            "current_user": {
                "id": current_user_id,
                "username": session.get("username"),
                "is_admin": current_is_admin
            }
        })

    except Exception as e:
        print("[GET posts] error =", e)
        traceback.print_exc()
        return jsonify({"code": 500, "message": "failed to fetch posts", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/community/posts/<int:post_id>/like", methods=["POST"])
def like_community_post(post_id):
    user_id = session.get("user_id")
    actor_name = session.get("username") or "匿名用户"

    if not user_id:
        return jsonify({"code": 401, "message": "请先登录后再点赞"}), 401

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, user_id FROM community_posts WHERE id=%s", (post_id,))
            post = cursor.fetchone()
            if not post:
                return jsonify({"code": 404, "message": "帖子不存在"}), 404

            cursor.execute(
                "SELECT id FROM community_post_likes WHERE post_id=%s AND user_id=%s",
                (post_id, user_id)
            )
            existed = cursor.fetchone()

            if existed:
                cursor.execute("DELETE FROM community_post_likes WHERE id=%s", (existed["id"],))
                liked = False
            else:
                cursor.execute(
                    "INSERT INTO community_post_likes (post_id, user_id) VALUES (%s, %s)",
                    (post_id, user_id)
                )
                liked = True
                create_notification(
                    cursor,
                    post.get("user_id"),
                    user_id,
                    actor_name,
                    post_id,
                    None,
                    "like",
                    f"{actor_name} 赞同了你的帖子"
                )

            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM community_post_likes WHERE post_id=%s",
                (post_id,)
            )
            like_count = cursor.fetchone()["cnt"]

            cursor.execute(
                "UPDATE community_posts SET like_count=%s WHERE id=%s",
                (like_count, post_id)
            )

        conn.commit()
        return jsonify({"code": 200, "message": "success", "data": {"liked": liked, "like_count": like_count}})
    except Exception as e:
        if conn:
            conn.rollback()
        traceback.print_exc()
        return jsonify({"code": 500, "message": "failed to like post", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/community/posts", methods=["POST"])
def create_community_post():
    conn = None
    try:
        user_id = session.get("user_id")
        author_name = (session.get("username") or "匿名用户").strip()

        if not user_id:
            return jsonify({"code": 401, "message": "请先登录后再发帖"}), 401

        data = request.get_json(silent=True) or {}
        topic = (data.get("topic") or "").strip()
        content = (data.get("content") or "").strip()
        image_url = data.get("image_url") or ""

        if not content:
            return jsonify({"code": 400, "message": "帖子内容不能为空"}), 400
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO community_posts
                (user_id, author_name, topic, content, image_url, like_count, comment_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, author_name, topic, content, image_url, 0, 0)
            )
            post_id = cursor.lastrowid

        conn.commit()
        return jsonify({"code": 200, "message": "success", "data": {"id": post_id}})
    except Exception as e:
        print("[POST posts] error =", e)
        traceback.print_exc()
        if conn:
            conn.rollback()
        return jsonify({"code": 500, "message": "failed to create post", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/community/comments", methods=["POST"])
def create_community_comment():
    conn = None
    try:
        user_id = session.get("user_id")
        author_name = (session.get("username") or "匿名用户").strip()

        if not user_id:
            return jsonify({"code": 401, "message": "请先登录后再评论"}), 401

        data = request.get_json(silent=True) or {}
        post_id = data.get("post_id")
        parent_comment_id = data.get("parent_comment_id")
        reply_to_user_id = data.get("reply_to_user_id")
        content = (data.get("content") or "").strip()
        image_url = data.get("image_url") or ""

        if not post_id:
            return jsonify({"code": 400, "message": "post_id 不能为空"}), 400
        if not content and not image_url:
            return jsonify({"code": 400, "message": "评论内容或图片不能为空"}), 400
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, user_id, author_name FROM community_posts WHERE id=%s", (post_id,))
            post = cursor.fetchone()
            if not post:
                return jsonify({"code": 404, "message": "帖子不存在"}), 404

            if parent_comment_id:
                cursor.execute(
                    "SELECT id, user_id, author_name FROM community_comments WHERE id=%s AND post_id=%s",
                    (parent_comment_id, post_id)
                )
                parent_comment = cursor.fetchone()
                if not parent_comment:
                    return jsonify({"code": 404, "message": "要回复的评论不存在"}), 404
                reply_to_user_id = reply_to_user_id or parent_comment.get("user_id")
            else:
                parent_comment = None

            cursor.execute(
                """
                INSERT INTO community_comments
                (post_id, user_id, parent_comment_id, reply_to_user_id, author_name, content, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (post_id, user_id, parent_comment_id, reply_to_user_id, author_name, content, image_url)
            )
            comment_id = cursor.lastrowid

            cursor.execute(
                """
                UPDATE community_posts
                SET comment_count = comment_count + 1
                WHERE id = %s
                """,
                (post_id,)
            )

            # Notify post owner for new comment.
            create_notification(
                cursor,
                post.get("user_id"),
                user_id,
                author_name,
                post_id,
                comment_id,
                "comment",
                f"{author_name} 评论了你的帖子"
            )

            # Notify replied comment owner.
            if reply_to_user_id:
                create_notification(
                    cursor,
                    reply_to_user_id,
                    user_id,
                    author_name,
                    post_id,
                    comment_id,
                    "reply",
                    f"{author_name} 回复了你的评论"
                )

        conn.commit()
        return jsonify({
            "code": 200,
            "message": "success",
            "data": {
                "id": comment_id,
                "post_id": post_id,
                "user_id": user_id,
                "parent_comment_id": parent_comment_id,
                "reply_to_user_id": reply_to_user_id,
                "reply_to_username": parent_comment.get("author_name") if parent_comment_id and parent_comment else "",
                "author_name": author_name,
                "content": content,
                "image_url": image_url,
                "created_at": format_dt(None)
            }
        })
    except Exception as e:
        if conn:
            conn.rollback()
        traceback.print_exc()
        return jsonify({"code": 500, "message": "failed to create comment", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/community/posts/<int:post_id>", methods=["DELETE"])
def delete_community_post(post_id):
    user = get_current_user_record()
    if not user:
        return jsonify({"code": 401, "message": "请先登录"}), 401

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, user_id FROM community_posts WHERE id=%s", (post_id,))
            post = cursor.fetchone()

            if not post:
                return jsonify({"code": 404, "message": "帖子不存在"}), 404

            if int(post.get("user_id") or 0) != int(user["id"]) and not is_admin_user(user):
                return jsonify({"code": 403, "message": "没有权限删除该帖子"}), 403

            cursor.execute("DELETE FROM community_post_likes WHERE post_id=%s", (post_id,))
            cursor.execute("DELETE FROM community_notifications WHERE post_id=%s", (post_id,))
            cursor.execute("DELETE FROM community_comments WHERE post_id=%s", (post_id,))
            cursor.execute("DELETE FROM community_posts WHERE id=%s", (post_id,))

        conn.commit()
        return jsonify({"code": 200, "message": "删除成功"})
    except Exception as e:
        if conn:
            conn.rollback()
        traceback.print_exc()
        return jsonify({"code": 500, "message": "删除帖子失败", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/community/notifications", methods=["GET"])
def get_community_notifications():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"code": 401, "message": "未登录"}), 401

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, type, message, post_id, comment_id, is_read, created_at
                FROM community_notifications
                WHERE user_id=%s
                ORDER BY id DESC
                LIMIT 30
                """,
                (user_id,)
            )
            rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM community_notifications
                WHERE user_id=%s AND is_read=0
                """,
                (user_id,)
            )
            unread_count = cursor.fetchone()["cnt"]

        return jsonify({
            "code": 200,
            "message": "success",
            "data": {
                "unread_count": unread_count,
                "items": [
                    {
                        "id": row["id"],
                        "type": row.get("type"),
                        "message": row.get("message"),
                        "post_id": row.get("post_id"),
                        "comment_id": row.get("comment_id"),
                        "is_read": row.get("is_read"),
                        "created_at": format_dt(row.get("created_at"))
                    }
                    for row in rows
                ]
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "message": "获取通知失败", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/community/notifications/read", methods=["POST"])
def mark_community_notifications_read():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"code": 401, "message": "未登录"}), 401

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE community_notifications SET is_read=1 WHERE user_id=%s",
                (user_id,)
            )
        conn.commit()
        return jsonify({"code": 200, "message": "success"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"code": 500, "message": "更新通知失败", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()




@app.route("/debug-routes")
def debug_routes():
    rows = []
    for rule in app.url_map.iter_rules():
        rows.append(f"{rule.rule} -> {sorted(rule.methods)} -> {rule.endpoint}")
    return "<br>".join(sorted(rows))



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
