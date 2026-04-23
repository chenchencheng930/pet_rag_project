FOLLOWUP_QUESTION_MAP = {
    "skin": [
        {
            "key": "itching_area",
            "question": "瘙痒主要集中在哪些部位？",
            "type": "single",
            "options": ["耳朵", "脸部", "腹部", "四肢", "全身"]
        },
        {
            "key": "ear_inflammation_history",
            "question": "是否反复出现耳朵发炎？",
            "type": "single",
            "options": ["是", "否"]
        },
        {
            "key": "food_trigger",
            "question": "是否在换粮或吃某类零食后更明显？",
            "type": "single",
            "options": ["是", "否", "不确定"]
        }
    ],
    "urinary": [
        {
            "key": "straining_to_urinate",
            "question": "是否频繁蹲厕所但每次尿量很少？",
            "type": "single",
            "options": ["是", "否"]
        },
        {
            "key": "urine_color_change",
            "question": "是否有尿血或尿色明显变深？",
            "type": "single",
            "options": ["是", "否"]
        },
        {
            "key": "painful_urination",
            "question": "排尿时是否明显痛苦或叫唤？",
            "type": "single",
            "options": ["是", "否"]
        }
    ],
    "digestive": [
        {
            "key": "diarrhea_duration",
            "question": "腹泻持续了多久？",
            "type": "single",
            "options": ["1天内", "2-3天", "超过3天"]
        },
        {
            "key": "vomiting_with_diarrhea",
            "question": "是否同时伴随呕吐？",
            "type": "single",
            "options": ["是", "否"]
        },
        {
            "key": "food_related_trigger",
            "question": "是否吃油腻食物后更明显？",
            "type": "single",
            "options": ["是", "否", "不确定"]
        }
    ],
    "kidney": [
        {
            "key": "drinking_trend",
            "question": "最近饮水量是否持续增加？",
            "type": "single",
            "options": ["是", "否", "不确定"]
        },
        {
            "key": "urination_trend",
            "question": "最近排尿量是否持续增加？",
            "type": "single",
            "options": ["是", "否", "不确定"]
        },
        {
            "key": "weight_loss_recent",
            "question": "最近是否有体重下降？",
            "type": "single",
            "options": ["是", "否", "不确定"]
        }
    ],
    "heart": [
        {
            "key": "cough_time",
            "question": "咳嗽多发生在什么时候？",
            "type": "single",
            "options": ["夜间/清晨", "运动后", "全天随机", "无咳嗽"]
        },
        {
            "key": "resting_breathing_fast",
            "question": "安静休息时呼吸也偏快吗？",
            "type": "single",
            "options": ["是", "否", "不确定"]
        },
        {
            "key": "exercise_recovery",
            "question": "活动后恢复是否明显变慢？",
            "type": "single",
            "options": ["是", "否"]
        }
    ]
}


def should_ask_followup(assessment_result: dict, user_info: dict) -> bool:
    suspected = assessment_result.get("suspected_conditions", [])
    if not suspected:
        return True

    top1 = suspected[0]
    evidence_count = len(top1.get("evidence", []))
    key = top1.get("condition_key", "unknown")

    # 证据太少，追问
    if evidence_count <= 2:
        return True

    # 只有肥胖背景风险时，优先继续追问，避免压掉专科问题
    if key == "obesity":
        symptoms = user_info.get("symptoms", {})
        special_symptoms = [
            "itching", "vomiting", "diarrhea", "difficulty_urinating",
            "bloody_urine", "cough", "rapid_breathing",
            "limping", "joint_stiffness", "jaundice"
        ]
        if not any(symptoms.get(k) for k in special_symptoms):
            return True

    return False


def generate_followup_questions(assessment_result: dict, user_info: dict) -> list:
    suspected = assessment_result.get("suspected_conditions", [])
    if suspected:
        concern = suspected[0].get("condition_key", user_info.get("primary_concern", "unknown"))
    else:
        concern = user_info.get("primary_concern", "unknown")

    return FOLLOWUP_QUESTION_MAP.get(concern, [])


def merge_followup_answers(user_info: dict, followup_answers: dict) -> dict:
    merged = dict(user_info)

    symptoms = dict(merged.get("symptoms", {}))
    indicators = dict(merged.get("medical_indicators", {}))
    basic_info = dict(merged.get("basic_info", {}))

    # -------------------------
    # skin / 皮肤过敏方向
    # -------------------------
    itching_area = followup_answers.get("itching_area")
    if itching_area in ["耳朵", "脸部", "腹部", "四肢", "全身"]:
        symptoms["itching"] = True

        if itching_area == "耳朵":
            symptoms["recurrent_ear_inflammation"] = True
        if itching_area == "四肢":
            symptoms["paw_licking"] = True

    if followup_answers.get("ear_inflammation_history") == "是":
        symptoms["recurrent_ear_inflammation"] = True
        symptoms["itching"] = True

    if followup_answers.get("food_trigger") == "是":
        symptoms["itching"] = True
        symptoms["skin_redness"] = True

    # -------------------------
    # urinary / 泌尿方向
    # -------------------------
    if followup_answers.get("straining_to_urinate") == "是":
        symptoms["difficulty_urinating"] = True
        symptoms["small_urine_volume"] = True
        symptoms["frequent_urination"] = True

    if followup_answers.get("urine_color_change") == "是":
        symptoms["bloody_urine"] = True

    if followup_answers.get("painful_urination") == "是":
        symptoms["difficulty_urinating"] = True

    # -------------------------
    # digestive / 消化方向
    # -------------------------
    diarrhea_duration = followup_answers.get("diarrhea_duration")
    if diarrhea_duration in ["1天内", "2-3天", "超过3天"]:
        symptoms["diarrhea"] = True
        if diarrhea_duration == "超过3天":
            symptoms["appetite_loss"] = True
            symptoms["low_energy"] = True

    if followup_answers.get("vomiting_with_diarrhea") == "是":
        symptoms["vomiting"] = True
        symptoms["diarrhea"] = True

    if followup_answers.get("food_related_trigger") == "是":
        symptoms["fat_food_intolerance"] = True
        symptoms["vomiting"] = True

    # -------------------------
    # kidney / 肾脏方向
    # -------------------------
    if followup_answers.get("drinking_trend") == "是":
        symptoms["increased_drinking"] = True

    if followup_answers.get("urination_trend") == "是":
        symptoms["increased_urination"] = True

    if followup_answers.get("weight_loss_recent") == "是":
        symptoms["weight_loss"] = True

    # -------------------------
    # heart / 心脏方向
    # -------------------------
    cough_time = followup_answers.get("cough_time")
    if cough_time in ["夜间/清晨", "运动后", "全天随机"]:
        symptoms["cough"] = True
        if cough_time == "运动后":
            symptoms["exercise_intolerance"] = True

    if followup_answers.get("resting_breathing_fast") == "是":
        symptoms["rapid_breathing"] = True

    if followup_answers.get("exercise_recovery") == "是":
        symptoms["exercise_intolerance"] = True

    # -------------------------
    # obesity / 背景体况辅助
    # 可按需要继续加
    # -------------------------
    if basic_info.get("bcs") == "overweight":
        basic_info["bcs"] = "overweight"
    elif basic_info.get("bcs") == "obese":
        basic_info["bcs"] = "obese"

    merged["symptoms"] = symptoms
    merged["medical_indicators"] = indicators
    merged["basic_info"] = basic_info
    merged["followup_answers"] = followup_answers or {}

    return merged

