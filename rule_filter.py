def pet_type_match(text: str, pet_type: str) -> bool:
    if pet_type == "cat":
        return "猫" in text
    if pet_type == "dog":
        return ("犬" in text) or ("狗" in text)
    return True


def concern_match(text: str, concern: str) -> bool:
    mapping = {
        "kidney": ["肾", "肾脏", "CKD", "低磷"],
        "liver": ["肝", "肝脏", "胆红素", "肝性脑病"],
        "skin": ["皮肤", "过敏", "低敏", "水解蛋白"],
        "urinary": ["泌尿", "尿路", "结石", "鸟粪石", "膀胱炎"],
        "digestive": ["胃肠", "消化", "腹泻", "呕吐", "胰腺炎"],
        "food_sensitivity": ["食物敏感", "食物不耐受", "低敏", "水解蛋白"],
        "heart": ["心脏", "低钠", "牛磺酸", "左旋肉碱"],
        "joint": ["关节", "骨关节", "葡萄糖胺", "软骨素"],
        "obesity": ["肥胖", "体重管理", "减重", "左旋肉碱"],
        "unknown": [],
    }

    keywords = mapping.get(concern, [])
    if not keywords:
        return True

    return any(k in text for k in keywords)


def apply_rules(candidates: list, user_info: dict) -> list:
    filtered = []

    for item in candidates:
        text = item.get("text", "")

        if not pet_type_match(text, user_info["pet_type"]):
            continue

        if not concern_match(text, user_info["primary_concern"]):
            continue

        filtered.append(item)

    if filtered:
        return filtered

    return candidates
