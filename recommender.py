import re


def infer_risk_level(user_info: dict) -> str:
    indicators = user_info.get("medical_indicators", {})
    symptoms = user_info.get("symptoms", {})

    abnormal_indicator_count = sum(1 for v in indicators.values() if v in ["high", "low"])
    symptom_count = sum(1 for v in symptoms.values() if v is True)

    if abnormal_indicator_count >= 2 or symptom_count >= 3:
        return "high"
    return "low"


def build_suspected_conditions(concern: str, user_info: dict) -> list:
    mapping = {
        "kidney": "疑似肾脏健康风险",
        "liver": "疑似肝脏代谢异常",
        "skin": "疑似皮肤屏障或过敏问题",
        "urinary": "疑似泌尿系统异常风险",
        "digestive": "疑似消化系统异常",
        "food_sensitivity": "疑似食物不耐受或敏感",
        "heart": "疑似心脏功能风险",
        "joint": "疑似骨关节问题",
        "obesity": "疑似体重管理风险",
        "blood_glucose": "疑似糖代谢异常风险",
        "dental": "疑似口腔健康异常",
        "unknown": "综合健康风险",
    }

    indicator_name_map = {
        "creatinine": "肌酐异常",
        "bun": "尿素氮异常",
        "phosphorus": "血磷异常",
        "urine_specific_gravity": "尿比重异常",
        "alt": "ALT异常",
        "ast": "AST异常",
        "total_bilirubin": "总胆红素异常",
        "albumin": "白蛋白异常",
        "urine_ph": "尿液pH异常",
        "urine_protein": "尿蛋白异常",
        "urine_crystals": "尿结晶异常",
        "glucose": "血糖异常",
        "wbc": "炎症/过敏相关指标异常",
        "heart_rate": "心率异常",
    }

    symptom_name_map = {
        "increased_drinking": "饮水增加",
        "increased_urination": "排尿增多",
        "low_energy": "精神状态下降",
        "appetite_loss": "食欲下降",
        "weight_loss": "体重下降",
        "jaundice": "黄疸表现",
        "vomiting": "呕吐",
        "abdominal_distension": "腹部鼓胀",
        "frequent_urination": "尿频",
        "difficulty_urinating": "排尿困难",
        "bloody_urine": "尿血",
        "small_urine_volume": "单次尿量少",
        "incontinence": "尿失禁",
        "increased_appetite": "食欲异常增加",
        "diarrhea": "腹泻/软便",
        "fat_food_intolerance": "油腻食物后不适",
        "weight_gain": "体重增加",
        "reduced_activity": "活动减少",
        "easy_panting": "容易气喘",
        "cough": "咳嗽",
        "exercise_intolerance": "运动耐受下降",
        "rapid_breathing": "呼吸急促",
        "fainting": "晕厥",
        "limping": "跛行",
        "joint_stiffness": "关节僵硬",
        "reluctance_to_move": "不愿活动",
        "difficulty_climbing_stairs": "上下楼困难",
        "bad_breath": "口臭",
        "gum_redness": "牙龈红肿",
        "gum_bleeding": "牙龈出血",
        "difficulty_eating": "进食困难",
        "itching": "瘙痒抓挠",
        "hair_loss": "异常掉毛",
        "skin_redness": "皮肤发红",
        "dandruff": "皮屑增多",
        "recurrent_ear_inflammation": "耳部反复炎症",
        "paw_licking": "频繁舔爪"
    }

    indicators = user_info.get("medical_indicators", {})
    symptoms = user_info.get("symptoms", {})

    indicator_evidence = []
    symptom_evidence = []
    evidence = []

    for k, v in indicators.items():
        if v in ["high", "low", "present"]:
            label = indicator_name_map.get(k, k)
            indicator_evidence.append(f"{label}（{v}）")
            evidence.append(f"{label}（{v}）")

    for k, v in symptoms.items():
        if v is True:
            label = symptom_name_map.get(k, k)
            symptom_evidence.append(label)
            evidence.append(label)

    if not evidence:
        evidence = ["当前主要依据基础信息与专科方向进行综合判断"]

    detail_map = {
        "kidney": {
            "clinical_summary": "当前信息提示风险主要集中在肾功能代谢负担、饮水排尿变化及慢性肾脏管理方向。",
            "risk_interpretation": "若同时伴随肌酐、尿素氮、血磷异常，通常提示肾脏代谢压力上升，需进一步结合尿检和肾功能指标综合判断。",
            "nutrition_focus": "营养干预重点应放在低磷、适度蛋白、肾脏支持及长期代谢负担控制。",
            "follow_up": "建议持续观察饮水量、排尿频率、精神状态、体重和食欲变化，并结合复查结果动态调整。"
        },
        "liver": {
            "clinical_summary": "当前信息提示问题更偏向肝脏代谢、胆汁代谢及消化耐受异常方向。",
            "risk_interpretation": "若伴随 ALT、AST 或总胆红素异常，并出现黄疸、食欲下降、呕吐等表现，应优先排查肝胆系统问题。",
            "nutrition_focus": "营养干预应优先考虑低负担、易消化、稳定代谢的肝脏支持方案。",
            "follow_up": "建议重点观察黄疸、精神状态、食欲、呕吐频率及腹围变化，并结合生化复查。"
        },
        "urinary": {
            "clinical_summary": "当前信息更偏向下泌尿道环境异常、尿液理化指标改变或结石风险方向。",
            "risk_interpretation": "当尿液 pH、尿蛋白、尿结晶异常，并伴有尿频、排尿困难或尿血时，通常提示泌尿系统需要优先关注。",
            "nutrition_focus": "营养干预应重点考虑泌尿道管理、尿液环境支持、提高饮水与降低结晶形成风险。",
            "follow_up": "建议重点记录排尿频率、单次尿量、如厕姿势变化和尿液颜色，必要时尽快完善尿检与影像检查。"
        },
        "digestive": {
            "clinical_summary": "当前信息提示主要问题集中在胃肠道耐受下降、消化吸收异常或炎症刺激方向。",
            "risk_interpretation": "如果腹泻、呕吐、食欲下降等表现持续存在，通常提示消化系统负担较高，必要时需排查胰腺或肠道炎症因素。",
            "nutrition_focus": "营养干预应优先考虑高消化率、温和配方、肠道支持及平稳换粮。",
            "follow_up": "建议持续观察粪便形态、呕吐次数、进食意愿及油腻食物后的反应。"
        },
        "food_sensitivity": {
            "clinical_summary": "当前信息更偏向食物相关不耐受或慢性敏感反应方向。",
            "risk_interpretation": "若症状与特定食物反复相关，尤其出现饭后瘙痒、腹泻或皮肤表现，应优先考虑饮食排查。",
            "nutrition_focus": "营养干预应重点考虑低敏、水解蛋白或单一蛋白策略，并减少复杂零食干扰。",
            "follow_up": "建议建立饮食记录，观察进食后皮肤与消化反应变化，便于后续定位诱因。"
        },
        "heart": {
            "clinical_summary": "当前信息提示心肺耐受下降及循环负担增加方向需要重点关注。",
            "risk_interpretation": "若咳嗽、呼吸急促、运动耐受下降或晕厥同时存在，通常提示心脏功能支持方向优先级较高。",
            "nutrition_focus": "营养干预应重点考虑低钠、心肌代谢支持和长期慢病管理方向。",
            "follow_up": "建议重点观察静息呼吸频率、咳嗽变化、活动恢复速度和夜间症状。"
        },
        "joint": {
            "clinical_summary": "当前信息更偏向骨关节活动受限、慢性关节炎症或退行性改变方向。",
            "risk_interpretation": "若跛行、关节僵硬、不愿活动或上下楼困难同时出现，通常提示关节问题优先级较高。",
            "nutrition_focus": "营养干预应重点考虑关节支持、抗炎思路及体重协同管理。",
            "follow_up": "建议持续观察活动意愿、起身速度、上下楼表现和疼痛波动。"
        },
        "obesity": {
            "clinical_summary": "当前信息提示体况评分、体重趋势与活动表现已偏向体重管理风险方向。",
            "risk_interpretation": "若仅表现为偏胖，可先作为慢性背景风险管理；若伴随明显活动下降、气喘等，则需要尽早干预。",
            "nutrition_focus": "营养干预应重点放在控能量、高饱腹、代谢支持及规律喂养。",
            "follow_up": "建议按周记录体重、体况评分和活动量变化，避免将超重问题长期放任。"
        },
        "blood_glucose": {
            "clinical_summary": "当前信息提示糖代谢异常方向值得重点排查。",
            "risk_interpretation": "若血糖异常并伴随饮水增多、排尿增多、体重下降或食欲异常增加，通常提示代谢异常方向优先级较高。",
            "nutrition_focus": "营养干预应重点关注稳定能量摄入、控制代谢波动和长期慢病饮食管理。",
            "follow_up": "建议持续观察饮水、排尿、体重与食欲变化，并结合血糖复查结果综合判断。"
        },
        "dental": {
            "clinical_summary": "当前信息更偏向口腔健康异常、牙龈炎症或进食受限方向。",
            "risk_interpretation": "若口臭、牙龈红肿、出血或进食困难并存，通常提示口腔问题需要尽早处理。",
            "nutrition_focus": "营养干预重点应放在维持摄食依从性和减少进食疼痛带来的营养影响。",
            "follow_up": "建议观察口腔气味、牙龈状态、咀嚼习惯及进食速度变化。"
        },
        "skin": {
            "clinical_summary": "当前信息更偏向皮肤屏障受损、慢性炎症或过敏相关问题方向。",
            "risk_interpretation": "当瘙痒、皮肤发红、异常掉毛、皮屑增多、耳部反复炎症或舔爪行为同时存在时，通常提示皮肤/过敏方向优先级较高。",
            "nutrition_focus": "营养干预应重点考虑低敏、皮肤屏障支持、脂肪酸平衡及减少潜在过敏原刺激。",
            "follow_up": "建议持续记录抓挠频率、发作部位、耳部情况、舔爪行为及与食物/环境变化的关联。"
        },
        "unknown": {
            "clinical_summary": "当前信息尚不足以形成单一明确专科方向，需要结合更多体征或检测指标综合判断。",
            "risk_interpretation": "现阶段更适合作为初筛结果，不能替代线下系统检查。",
            "nutrition_focus": "营养干预建议先选择温和、稳定、易消化的基础方案。",
            "follow_up": "建议继续补充异常指标与症状信息后再次评估。"
        }
    }

    detail = detail_map.get(concern, detail_map["unknown"])

    symptom_text = "、".join(symptom_evidence) if symptom_evidence else "暂无典型症状输入"
    indicator_text = "、".join(indicator_evidence) if indicator_evidence else "暂无关键指标异常"

    explanation = (
        f"当前评估重点偏向“{mapping.get(concern, '综合健康风险')}”方向。"
        f"症状层面主要表现为：{symptom_text}；"
        f"指标层面主要表现为：{indicator_text}。"
        f"{detail['nutrition_focus']}"
    )

    return [{
        "condition_name": mapping.get(concern, "综合健康风险"),
        "evidence": evidence,
        "explanation": explanation,
        "clinical_summary": detail["clinical_summary"],
        "risk_interpretation": detail["risk_interpretation"],
        "nutrition_focus": detail["nutrition_focus"],
        "follow_up": detail["follow_up"]
    }]



def build_health_advice(concern: str) -> list:
    advice_map = {
        "kidney": ["建议尽快复查肾功能及尿检", "关注饮水量、排尿频率和精神状态"],
        "liver": ["建议结合肝功能生化结果进一步判断", "若出现黄疸或食欲持续下降应尽快就医"],
        "skin": ["建议排查常见过敏原与环境刺激源", "避免频繁更换洗护用品和零食"],
        "urinary": ["建议重点观察排尿是否困难、频率是否异常", "如有尿血或频繁蹲厕应尽快就医"],
        "digestive": ["建议少量多餐，避免高刺激性食物", "如反复腹泻呕吐建议尽快就医"],
        "food_sensitivity": ["建议记录进食后反应并排查可疑原料", "后续可尝试低敏或单一蛋白方案"],
        "heart": ["建议监测呼吸频率和活动耐力", "如持续咳嗽或气喘建议尽快检查心脏功能"],
        "joint": ["建议减少高强度跳跃和爬楼", "关注起身困难和跛行变化"],
        "obesity": ["建议控制零食摄入并增加规律活动", "长期应关注体况评分变化"],
        "unknown": ["建议结合线下检查结果进一步评估"],
    }
    return advice_map.get(concern, ["建议结合线下检查结果进一步评估"])


def build_diet_advice(concern: str) -> list:
    advice_map = {
        "kidney": ["建议优先考虑低磷、肾脏护理型配方", "避免高盐高负担零食"],
        "liver": ["建议选择更易消化、负担较低的配方", "避免频繁换粮"],
        "skin": ["建议优先考虑低敏、皮肤支持型配方", "避免复杂原料零食"],
        "urinary": ["建议优先考虑泌尿道管理配方", "提升总饮水量可作为辅助管理手段"],
        "digestive": ["建议优先考虑高消化率、肠道支持型配方", "换粮过程建议7到10天逐步过渡"],
        "food_sensitivity": ["建议考虑低敏、水解蛋白或单一蛋白配方", "避免混喂多种零食"],
        "heart": ["建议优先考虑低钠、心脏支持方向配方", "避免高盐人类食物"],
        "joint": ["建议考虑关节支持型营养配方", "体重控制对关节减负也很重要"],
        "obesity": ["建议选择体重管理配方", "控制总能量摄入并保持规律喂养"],
        "unknown": ["建议根据专科方向选择针对性营养方案"],
    }
    return advice_map.get(concern, ["建议根据专科方向选择针对性营养方案"])


import re

def extract_product_name(text: str) -> str:
    patterns = [
        r"产品名称[:：]\s*(.+)",
        r"产品类别[:：]\s*(.+)",
        r"^([^\n]{4,60}处方粮[^\n]*)",
        r"^([^\n]{4,60}护理粮[^\n]*)",
        r"^([^\n]{4,60}猫粮[^\n]*)",
        r"^([^\n]{4,60}犬粮[^\n]*)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r"【.*?】", "", name).strip()
            return name

    # 如果前几行里有像商品标题的内容，也抓一条
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:5]:
        if len(line) <= 60 and ("粮" in line or "处方" in line or "护理" in line):
            clean_line = re.sub(r"【.*?】", "", line).strip()
            return clean_line

    return "未识别具体产品"



def build_product_recommendations(text: str, concern: str) -> list:
    product_name = extract_product_name(text)

    reason_map = {
        "kidney": ["匹配肾脏管理方向", "更符合低磷/肾脏护理思路"],
        "liver": ["匹配肝脏代谢支持方向", "适合作为低负担营养管理方案"],
        "skin": ["匹配皮肤与过敏管理方向", "更符合低敏支持思路"],
        "urinary": ["匹配泌尿系统管理方向", "有助于尿路环境支持"],
        "digestive": ["匹配肠胃消化支持方向", "更符合高消化率管理思路"],
        "food_sensitivity": ["匹配食物敏感管理方向", "适合低敏饮食尝试"],
        "heart": ["匹配心脏支持方向", "更符合低钠与代谢支持思路"],
        "joint": ["匹配骨关节支持方向", "有助于长期关节营养管理"],
        "obesity": ["匹配体重管理方向", "更符合控能量与代谢支持思路"],
        "unknown": ["与当前专科方向匹配"],
    }

    return [{
        "product_name": product_name,
        "reason": reason_map.get(concern, ["与当前专科方向匹配"])
    }]
def pick_best_product_text(filtered_items: list) -> str:
    if not filtered_items:
        return ""

    for item in filtered_items:
        meta = item.get("metadata", {})
        if meta.get("type") == "product":
            return item.get("text", "")

    return filtered_items[0].get("text", "")


def build_assessment_result(filtered_items: list, user_info: dict, assessment_result: dict) -> dict:
    summary = user_info["summary"]

    suspected_conditions = assessment_result.get("suspected_conditions", [])
    overall_risk_level = assessment_result.get("overall_risk_level", "low")

    if suspected_conditions:
        concern = suspected_conditions[0].get("condition_key", user_info.get("primary_concern", "unknown"))
    else:
        concern = user_info.get("primary_concern", "unknown")

    best_text = pick_best_product_text(filtered_items)

    return {
        "summary": summary,
        "suspected_conditions": suspected_conditions if suspected_conditions else build_suspected_conditions(concern, user_info),
        "overall_risk_level": overall_risk_level,
        "health_advice": build_health_advice(concern),
        "diet_advice": build_diet_advice(concern),
        "product_recommendations": build_product_recommendations(best_text, concern)
    }




