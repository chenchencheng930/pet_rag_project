from config import DISEASE_MAP


def normalize_input(user_input: dict) -> dict:
    pet_type = str(user_input.get("pet_type", "")).strip().lower()
    age = str(user_input.get("age", "")).strip()
    symptom = str(user_input.get("symptom", "")).strip()
    sterilized = str(user_input.get("sterilized", "")).strip()
    allergy = str(user_input.get("allergy", "")).strip()
    budget = str(user_input.get("budget", "")).strip()

    if pet_type in ["猫", "cat"]:
        pet_type = "cat"
    elif pet_type in ["狗", "犬", "dog"]:
        pet_type = "dog"

    symptom_key = DISEASE_MAP.get(symptom, symptom)
    age_stage = parse_age_stage(pet_type, age)

    return {
        "pet_type": pet_type,
        "age": age,
        "age_stage": age_stage,
        "symptom": symptom,
        "symptom_key": symptom_key,
        "sterilized": sterilized,
        "allergy": allergy,
        "budget": budget
    }


def parse_age_stage(pet_type: str, age_text: str) -> str:
    try:
        age_num = float(age_text.replace("岁", "").strip())
    except Exception:
        return "unknown"

    if pet_type == "cat":
        if age_num < 1:
            return "kitten"
        elif age_num < 7:
            return "adult"
        else:
            return "senior"

    if pet_type == "dog":
        if age_num < 1:
            return "puppy"
        elif age_num < 7:
            return "adult"
        else:
            return "senior"

    return "unknown"


def build_query(normalized: dict) -> str:
    pet_type_map = {"cat": "猫", "dog": "犬"}
    pet_name = pet_type_map.get(normalized["pet_type"], normalized["pet_type"])

    parts = [
        f"适合{pet_name}的处方粮推荐",
        f"年龄：{normalized['age']}",
        f"症状：{normalized['symptom']}"
    ]

    if normalized["sterilized"]:
        parts.append(f"是否绝育：{normalized['sterilized']}")
    if normalized["allergy"] and normalized["allergy"] != "无":
        parts.append(f"过敏信息：{normalized['allergy']}")
    if normalized["budget"]:
        parts.append(f"预算：{normalized['budget']}")

    return "；".join(parts)
