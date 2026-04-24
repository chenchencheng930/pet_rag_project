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
    return render_template("dashboard.html")


@app.route("/community")
def community():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("community.html")


@app.route("/reminder")
def reminder():
    return render_template("reminder.html")


@app.route("/profile")
def profile():
    return render_template("profile.html")


@app.route("/my_posts")
def my_posts():
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
                "SELECT id, username, phone FROM users WHERE id=%s",
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
                "masked_phone": masked_phone
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "message": "获取用户信息失败", "error": str(e)}), 500
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
        print("[GET posts] start")

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, author_name, topic, content, image_url, like_count, comment_count, created_at
                FROM community_posts
                ORDER BY id DESC
                """
            )
            posts = cursor.fetchall()

            cursor.execute(
                """
                SELECT id, post_id, author_name, content, created_at
                FROM community_comments
                ORDER BY id ASC
                """
            )
            comments = cursor.fetchall()

        comments_map = {}
        for item in comments:
            comments_map.setdefault(item["post_id"], []).append({
                "id": item["id"],
                "author_name": item["author_name"],
                "content": item["content"],
                "created_at": format_dt(item["created_at"])
            })

        data = []
        for post in posts:
            data.append({
                "id": post["id"],
                "author_name": post.get("author_name") or "匿名用户",
                "topic": post.get("topic") or "",
                "content": post.get("content") or "",
                "image_url": post.get("image_url") or "",
                "like_count": post.get("like_count") or 0,
                "comment_count": post.get("comment_count") or 0,
                "created_at": format_dt(post.get("created_at")),
                "comments_list": comments_map.get(post["id"], [])
            })

        print("[GET posts] success")
        return jsonify({"code": 200, "message": "success", "data": data})

    except Exception as e:
        print("[GET posts] error =", e)
        traceback.print_exc()
        return jsonify({"code": 500, "message": "failed to fetch posts", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/community/posts/<int:post_id>/like", methods=["POST"])
def like_community_post(post_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE community_posts
                SET like_count = like_count + 1
                WHERE id = %s
                """,
                (post_id,)
            )
        conn.commit()
        return jsonify({"code": 200, "message": "success"})
    except Exception as e:
        if conn:
            conn.rollback()
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
        print("[POST posts] data =", data)

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
        print("[POST posts] success, post_id =", post_id)

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
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400

        post_id = data.get("post_id")
        content = (data.get("content") or "").strip()

        if not post_id:
            return jsonify({"code": 400, "message": "post_id 不能为空"}), 400
        if not content:
            return jsonify({"code": 400, "message": "评论内容不能为空"}), 400

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO community_comments (post_id, author_name, content)
                VALUES (%s, %s, %s)
                """,
                (post_id, author_name, content)
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

        conn.commit()

        return jsonify({
            "code": 200,
            "message": "success",
            "data": {
                "id": comment_id,
                "post_id": post_id,
                "author_name": author_name,
                "content": content
            }
        })
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"code": 500, "message": "failed to create comment", "error": str(e)}), 500
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
