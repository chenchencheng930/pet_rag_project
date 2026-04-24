from config import CONDITION_NAME_MAP, RISK_LEVEL_RULES


class AssessmentEngine:
    def assess(self, user_info: dict) -> dict:
        condition_results = []
        selected_concerns = user_info.get("primary_concerns") or user_info.get("user_selected_concerns") or []
        if isinstance(selected_concerns, str):
            selected_concerns = [selected_concerns]
        selected_concerns = [item for item in selected_concerns if item and item != "unknown"]

        kidney_result = self.assess_kidney(user_info)
        if kidney_result:
            condition_results.append(kidney_result)

        liver_result = self.assess_liver(user_info)
        if liver_result:
            condition_results.append(liver_result)

        urinary_result = self.assess_urinary(user_info)
        if urinary_result:
            condition_results.append(urinary_result)

        glucose_result = self.assess_blood_glucose(user_info)
        if glucose_result:
            condition_results.append(glucose_result)

        digestive_result = self.assess_digestive(user_info)
        if digestive_result:
            condition_results.append(digestive_result)

        obesity_result = self.assess_obesity(user_info)
        if obesity_result:
            condition_results.append(obesity_result)

        heart_result = self.assess_heart(user_info)
        if heart_result:
            condition_results.append(heart_result)

        joint_result = self.assess_joint(user_info)
        if joint_result:
            condition_results.append(joint_result)

        dental_result = self.assess_dental(user_info)
        if dental_result:
            condition_results.append(dental_result)

        skin_result = self.assess_skin(user_info)
        if skin_result:
            condition_results.append(skin_result)

        # 如果存在明确专科问题，肥胖作为次级风险，不抢第一
        special_keys = {"kidney", "liver", "urinary", "digestive", "heart", "joint", "skin", "dental", "blood_glucose"}

        special_results = [
            item for item in condition_results
            if item["condition_key"] in special_keys and item["score"] >= 30
        ]

        if special_results:
            for item in condition_results:
                if item["condition_key"] == "obesity":
                    item["score"] -= 20

        condition_results.sort(key=lambda x: x["score"], reverse=True)

        result_by_key = {
            item["condition_key"]: item
            for item in condition_results
            if item.get("condition_key")
        }

        display_results = []

        # 1. 用户主动勾选的方向必须进入评估结果。
        # 即使该方向当前分数较低，也作为“已选择关注方向/待排查方向”展示，避免多选时只显示第一个方向。
        for key in selected_concerns:
            if key in result_by_key:
                item = dict(result_by_key[key])
                if item.get("score", 0) < RISK_LEVEL_RULES["medium"]:
                    item["risk_level"] = "low"
                    item["evidence"] = item.get("evidence") or ["用户主动选择该关注方向"]
                    item["explanation"] = (
                        item.get("explanation")
                        or f"用户已选择“{CONDITION_NAME_MAP.get(key, key)}”作为关注方向，当前输入证据有限，建议结合更多症状和检查指标继续判断。"
                    )
                display_results.append(item)
            elif key in CONDITION_NAME_MAP:
                display_results.append({
                    "condition_key": key,
                    "condition_name": CONDITION_NAME_MAP[key],
                    "score": 0,
                    "risk_level": "low",
                    "evidence": ["用户主动选择该关注方向"],
                    "explanation": f"用户已选择“{CONDITION_NAME_MAP.get(key, key)}”作为关注方向，当前输入信息不足以形成中高风险判断，建议结合相关症状和检查指标继续评估。"
                })

        # 2. 同时保留评分系统识别出的中高风险方向。
        for item in condition_results:
            if item["risk_level"] in ["medium", "high"] and item["condition_key"] not in [r["condition_key"] for r in display_results]:
                display_results.append(item)

        if not display_results:
            display_results = condition_results[:1]

        overall_risk_level = "low"
        if any(item["risk_level"] == "high" for item in display_results):
            overall_risk_level = "high"
        elif any(item["risk_level"] == "medium" for item in display_results):
            overall_risk_level = "medium"

        return {
            "overall_risk_level": overall_risk_level,
            "suspected_conditions": display_results
        }

    def get_risk_level(self, score: int) -> str:
        if score >= RISK_LEVEL_RULES["high"]:
            return "high"
        if score >= RISK_LEVEL_RULES["medium"]:
            return "medium"
        return "low"

    def compose_explanation(self, parts: list, fallback: str, closing: str = "") -> str:
        if not parts:
            return fallback
        text = "；".join(parts) + "。"
        if closing:
            text += closing
        return text

    def build_result(self, key: str, score: int, evidence: list, explanation: str):
        if score < RISK_LEVEL_RULES["low"]:
            return None

        final_score = min(score, 100)

        return {
            "condition_key": key,
            "condition_name": CONDITION_NAME_MAP[key],
            "score": final_score,
            "risk_level": self.get_risk_level(final_score),
            "evidence": evidence,
            "explanation": explanation
        }

    def assess_kidney(self, user_info: dict):
        symptoms = user_info["symptoms"]
        indicators = user_info["medical_indicators"]

        score = 0
        evidence = []
        explanation_parts = []

        if indicators.get("creatinine") == "high":
            score += 30
            evidence.append("肌酐偏高")
            explanation_parts.append("肌酐偏高提示肾脏代谢废物清除压力增加")

        if indicators.get("bun") == "high":
            score += 25
            evidence.append("尿素氮偏高")
            explanation_parts.append("尿素氮偏高提示肾功能负担上升或蛋白代谢废物排出受限")

        if indicators.get("phosphorus") == "high":
            score += 20
            evidence.append("血磷偏高")
            explanation_parts.append("血磷偏高常见于肾脏排磷能力下降方向")

        if indicators.get("urine_specific_gravity") == "low":
            score += 10
            evidence.append("尿比重偏低")
            explanation_parts.append("尿比重偏低提示尿液浓缩能力可能下降")

        if symptoms.get("increased_drinking"):
            score += 15
            evidence.append("饮水明显增加")
            explanation_parts.append("饮水增加提示机体可能通过多饮来代偿代谢异常")

        if symptoms.get("increased_urination"):
            score += 15
            evidence.append("排尿明显增多")
            explanation_parts.append("排尿增多提示肾脏浓缩功能或体液调节能力值得进一步关注")

        if symptoms.get("low_energy"):
            score += 10
            evidence.append("精神差")
            explanation_parts.append("精神状态变差提示整体代谢负担可能已经影响日常状态")

        if symptoms.get("appetite_loss"):
            score += 10
            evidence.append("食欲下降")
            explanation_parts.append("食欲下降提示代谢异常可能已影响进食意愿")

        if symptoms.get("weight_loss"):
            score += 10
            evidence.append("体重下降")
            explanation_parts.append("体重下降提示慢性消耗或长期代谢负担增加")

        explanation = self.compose_explanation(
            explanation_parts,
            "当前输入信息与肾脏异常常见表现较为一致。",
            "营养管理建议优先考虑低磷、适度蛋白和肾脏支持方向。"
        )

        return self.build_result(
            "kidney",
            score,
            evidence,
            explanation
        )

    def assess_liver(self, user_info: dict):
        symptoms = user_info["symptoms"]
        indicators = user_info["medical_indicators"]

        score = 0
        evidence = []
        explanation_parts = []

        if indicators.get("alt") == "high":
            score += 25
            evidence.append("ALT偏高")
            explanation_parts.append("ALT偏高提示肝细胞损伤或肝脏代谢压力增加")

        if indicators.get("ast") == "high":
            score += 20
            evidence.append("AST偏高")
            explanation_parts.append("AST偏高提示肝脏或相关组织代谢异常方向值得关注")

        if indicators.get("total_bilirubin") == "high":
            score += 25
            evidence.append("总胆红素偏高")
            explanation_parts.append("总胆红素偏高提示胆汁代谢或肝胆排泄过程可能受影响")

        if indicators.get("albumin") == "low":
            score += 20
            evidence.append("白蛋白偏低")
            explanation_parts.append("白蛋白偏低提示肝脏合成功能方向需要进一步结合检查判断")

        if symptoms.get("jaundice"):
            score += 25
            evidence.append("出现黄疸")
            explanation_parts.append("黄疸表现提示肝胆代谢异常优先级较高")

        if symptoms.get("vomiting"):
            score += 10
            evidence.append("呕吐")
            explanation_parts.append("呕吐提示消化耐受性下降，需结合肝胆方向综合判断")

        if symptoms.get("appetite_loss"):
            score += 10
            evidence.append("食欲差")
            explanation_parts.append("食欲下降说明当前代谢负担可能已影响进食状态")

        if symptoms.get("abdominal_distension"):
            score += 15
            evidence.append("腹部鼓胀")
            explanation_parts.append("腹部鼓胀提示腹腔状态或肝胆相关问题值得进一步排查")

        explanation = self.compose_explanation(
            explanation_parts,
            "当前输入信息与肝脏异常常见表现较为一致。",
            "营养管理建议优先考虑低负担、易消化和肝脏支持方向。"
        )

        return self.build_result(
            "liver",
            score,
            evidence,
            explanation
        )

    def assess_urinary(self, user_info: dict):
        symptoms = user_info["symptoms"]
        indicators = user_info["medical_indicators"]

        score = 0
        evidence = []
        explanation_parts = []

        if indicators.get("urine_ph") in ["low", "high"]:
            score += 20
            evidence.append("尿液pH异常")
            explanation_parts.append("尿液pH异常，提示尿液环境稳定性下降，需关注结晶或结石形成风险")

        if indicators.get("urine_protein") == "present":
            score += 15
            evidence.append("尿蛋白有")
            explanation_parts.append("尿蛋白异常提示泌尿系统屏障或炎症方向值得进一步关注")

        if indicators.get("urine_crystals") == "present":
            score += 25
            evidence.append("尿结晶有")
            explanation_parts.append("尿液中出现结晶，提示下泌尿道环境异常或结石风险增加")

        if symptoms.get("frequent_urination"):
            score += 15
            evidence.append("排尿频繁")
            explanation_parts.append("存在尿频表现，提示膀胱刺激或排尿异常")

        if symptoms.get("difficulty_urinating"):
            score += 20
            evidence.append("排尿困难")
            explanation_parts.append("排尿困难提示下泌尿道阻塞或疼痛风险需要优先排查")

        if symptoms.get("bloody_urine"):
            score += 20
            evidence.append("尿中带血")
            explanation_parts.append("尿血提示泌尿道炎症、结石或黏膜损伤风险增加")

        if symptoms.get("small_urine_volume"):
            score += 10
            evidence.append("每次尿量少")
            explanation_parts.append("单次尿量偏少，说明排尿过程可能不顺畅")

        if symptoms.get("incontinence"):
            score += 10
            evidence.append("尿失禁/憋不住")
            explanation_parts.append("尿失禁表现提示泌尿控制能力下降或局部刺激")

        explanation = self.compose_explanation(
            explanation_parts,
            "当前输入信息与泌尿系统异常或结石风险较为一致。",
            "营养管理建议优先考虑泌尿道支持、促进饮水和稳定尿液环境。"
        )

        return self.build_result(
            "urinary",
            score,
            evidence,
            explanation
        )

    def assess_blood_glucose(self, user_info: dict):
        symptoms = user_info["symptoms"]
        indicators = user_info["medical_indicators"]

        score = 0
        evidence = []
        explanation_parts = []

        if indicators.get("glucose") == "high":
            score += 35
            evidence.append("血糖偏高")
            explanation_parts.append("血糖偏高提示糖代谢异常方向优先级较高")

        if symptoms.get("increased_drinking"):
            score += 15
            evidence.append("饮水增多")
            explanation_parts.append("饮水增多是常见代谢异常伴随表现之一")

        if symptoms.get("increased_urination"):
            score += 15
            evidence.append("排尿增多")
            explanation_parts.append("排尿增多提示体液调节与代谢状态可能受到影响")

        if symptoms.get("weight_loss"):
            score += 15
            evidence.append("体重下降")
            explanation_parts.append("体重下降提示机体能量利用异常可能已持续一段时间")

        if symptoms.get("increased_appetite"):
            score += 15
            evidence.append("食欲异常增加")
            explanation_parts.append("食欲异常增加提示代谢异常方向更值得关注")

        explanation = self.compose_explanation(
            explanation_parts,
            "当前输入信息与糖代谢异常常见表现较为一致。",
            "营养管理建议优先考虑稳定能量摄入和长期代谢支持方向。"
        )

        return self.build_result(
            "blood_glucose",
            score,
            evidence,
            explanation
        )

    def assess_digestive(self, user_info: dict):
        symptoms = user_info["symptoms"]

        score = 0
        evidence = []
        explanation_parts = []

        if symptoms.get("vomiting"):
            score += 20
            evidence.append("呕吐")
            explanation_parts.append("存在呕吐表现，提示胃肠道刺激或消化耐受下降")

        if symptoms.get("diarrhea"):
            score += 20
            evidence.append("腹泻")
            explanation_parts.append("存在腹泻/软便表现，提示肠道吸收功能或菌群稳定性可能受到影响")

        if symptoms.get("appetite_loss"):
            score += 15
            evidence.append("食欲下降")
            explanation_parts.append("伴随食欲下降，说明当前消化系统负担可能已影响正常进食状态")

        if symptoms.get("fat_food_intolerance"):
            score += 20
            evidence.append("油腻食物后不适")
            explanation_parts.append("对油腻食物耐受差，提示胰腺负担或脂肪消化能力下降方向值得关注")

        if symptoms.get("abdominal_distension"):
            score += 10
            evidence.append("腹胀")
            explanation_parts.append("出现腹胀，说明胃肠蠕动或消化过程可能存在异常")

        explanation = self.compose_explanation(
            explanation_parts,
            "当前输入信息与消化系统或胰腺问题常见表现较为一致。",
            "营养管理建议优先考虑高消化率、温和肠道支持和逐步换粮。"
        )

        return self.build_result(
            "digestive",
            score,
            evidence,
            explanation
        )

    def assess_obesity(self, user_info: dict):
        symptoms = user_info["symptoms"]
        basic_info = user_info["basic_info"]

        score = 0
        evidence = []
        explanation_parts = []

        if basic_info.get("bcs") == "overweight":
            score += 15
            evidence.append("BCS显示偏胖")
            explanation_parts.append("体况评分提示当前已处于偏胖状态")

        if basic_info.get("bcs") == "obese":
            score += 25
            evidence.append("BCS显示肥胖")
            explanation_parts.append("体况评分提示肥胖风险已经较为明确")

        if symptoms.get("weight_gain"):
            score += 10
            evidence.append("体重增加")
            explanation_parts.append("近期体重增加提示能量摄入与消耗平衡可能已被打破")

        if symptoms.get("reduced_activity"):
            score += 10
            evidence.append("活动减少")
            explanation_parts.append("活动量下降会进一步放大体重管理风险")

        if symptoms.get("easy_panting"):
            score += 10
            evidence.append("容易气喘")
            explanation_parts.append("容易气喘提示超重状态可能已增加心肺负担")

        explanation = self.compose_explanation(
            explanation_parts,
            "当前输入信息与体重管理风险较为一致。",
            "营养管理建议优先考虑控能量、高饱腹和规律喂养方向。"
        )

        return self.build_result(
            "obesity",
            score,
            evidence,
            explanation
        )

    def assess_heart(self, user_info: dict):
        symptoms = user_info["symptoms"]

        score = 0
        evidence = []
        explanation_parts = []

        if symptoms.get("cough"):
            score += 20
            evidence.append("咳嗽")
            explanation_parts.append("咳嗽提示心肺负担或循环相关问题方向值得关注")

        if symptoms.get("exercise_intolerance"):
            score += 20
            evidence.append("不耐运动")
            explanation_parts.append("运动耐受下降提示心肺储备能力可能不足")

        if symptoms.get("rapid_breathing"):
            score += 20
            evidence.append("呼吸急促")
            explanation_parts.append("呼吸急促提示循环或心肺负担增加")

        if symptoms.get("fainting"):
            score += 25
            evidence.append("晕厥")
            explanation_parts.append("晕厥提示循环稳定性下降，需要优先排查严重心脏风险")

        explanation = self.compose_explanation(
            explanation_parts,
            "当前输入信息与心脏相关异常常见表现较为一致。",
            "营养管理建议优先考虑低钠、心肌代谢支持和长期慢病管理方向。"
        )

        return self.build_result(
            "heart",
            score,
            evidence,
            explanation
        )

    def assess_joint(self, user_info: dict):
        symptoms = user_info["symptoms"]

        score = 0
        evidence = []
        explanation_parts = []

        if symptoms.get("limping"):
            score += 20
            evidence.append("跛行")
            explanation_parts.append("跛行提示局部关节或肢体负重异常")

        if symptoms.get("joint_stiffness"):
            score += 20
            evidence.append("关节僵硬")
            explanation_parts.append("关节僵硬提示活动灵活性下降或慢性关节问题可能存在")

        if symptoms.get("reluctance_to_move"):
            score += 20
            evidence.append("不愿活动")
            explanation_parts.append("不愿活动提示运动时不适或疼痛风险增加")

        if symptoms.get("difficulty_climbing_stairs"):
            score += 20
            evidence.append("上下楼困难")
            explanation_parts.append("上下楼困难提示关节负担、疼痛或活动受限更加明显")

        explanation = self.compose_explanation(
            explanation_parts,
            "当前输入信息与关节健康异常常见表现较为一致。",
            "营养管理建议优先考虑关节支持与体重协同管理方向。"
        )

        return self.build_result(
            "joint",
            score,
            evidence,
            explanation
        )

    def assess_dental(self, user_info: dict):
        symptoms = user_info["symptoms"]

        score = 0
        evidence = []
        explanation_parts = []

        if symptoms.get("bad_breath"):
            score += 20
            evidence.append("口臭")
            explanation_parts.append("口臭提示口腔菌斑、牙龈炎症或清洁状态异常")

        if symptoms.get("gum_redness"):
            score += 20
            evidence.append("牙龈红肿")
            explanation_parts.append("牙龈红肿提示口腔局部炎症反应活跃")

        if symptoms.get("gum_bleeding"):
            score += 20
            evidence.append("牙龈出血")
            explanation_parts.append("牙龈出血提示炎症或牙周问题需要尽快关注")

        if symptoms.get("difficulty_eating"):
            score += 20
            evidence.append("吃东西困难")
            explanation_parts.append("进食困难提示口腔疼痛或咀嚼受限已影响正常摄食")

        explanation = self.compose_explanation(
            explanation_parts,
            "当前输入信息与口腔健康异常常见表现较为一致。",
            "营养管理重点应放在维持摄食依从性并减少进食不适带来的影响。"
        )

        return self.build_result(
            "dental",
            score,
            evidence,
            explanation
        )

    def assess_skin(self, user_info: dict):
        symptoms = user_info["symptoms"]

        score = 0
        evidence = []
        explanation_parts = []

        if symptoms.get("itching"):
            score += 20
            evidence.append("瘙痒")
            explanation_parts.append("存在明显瘙痒，提示皮肤屏障受损或过敏刺激方向需要关注")

        if symptoms.get("hair_loss"):
            score += 15
            evidence.append("掉毛")
            explanation_parts.append("异常掉毛提示皮肤炎症、营养失衡或慢性刺激可能存在")

        if symptoms.get("skin_redness"):
            score += 20
            evidence.append("皮肤发红")
            explanation_parts.append("皮肤发红提示局部炎症反应或过敏反应活跃")

        if symptoms.get("dandruff"):
            score += 10
            evidence.append("皮屑多")
            explanation_parts.append("皮屑增多提示皮肤角质代谢异常或屏障状态不稳")

        if symptoms.get("recurrent_ear_inflammation"):
            score += 15
            evidence.append("耳朵反复发炎")
            explanation_parts.append("耳部反复炎症常与慢性过敏体质或皮肤问题并存")

        if symptoms.get("paw_licking"):
            score += 15
            evidence.append("舔爪")
            explanation_parts.append("频繁舔爪提示局部瘙痒、不适或过敏相关刺激持续存在")

        explanation = self.compose_explanation(
            explanation_parts,
            "当前输入信息与皮肤或过敏问题常见表现较为一致。",
            "营养管理建议优先考虑低敏、皮肤屏障支持和脂肪酸平衡方向。"
        )

        return self.build_result(
            "skin",
            score,
            evidence,
            explanation
        )
