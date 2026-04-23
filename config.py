import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, "knowledge_base")
ASSESSMENTS_DIR = os.path.join(KNOWLEDGE_BASE_DIR, "assessments")
PRODUCTS_DIR = os.path.join(KNOWLEDGE_BASE_DIR, "products")

TOP_K = 5

DISEASE_MAP = {
    "心脏病": "heart",
    "肾病": "kidney",
    "胃病": "digestive",
    "消化系统疾病": "digestive",
    "胰腺炎": "digestive",
    "骨关节疾病": "joint",
    "关节病": "joint",
    "过敏": "skin",
    "皮肤病": "skin",
    "泌尿问题": "urinary",
    "超重": "obesity",
    "肥胖": "obesity"
}

CONDITION_NAME_MAP = {
    "kidney": "肾脏异常风险",
    "liver": "肝脏异常风险",
    "urinary": "泌尿系统异常风险",
    "blood_glucose": "血糖异常风险",
    "digestive": "消化系统异常风险",
    "obesity": "肥胖与体重管理风险",
    "heart": "心脏异常风险",
    "joint": "骨关节异常风险",
    "dental": "口腔健康风险",
    "skin": "皮肤/过敏风险"
}

RISK_LEVEL_RULES = {
    "low": 20,
    "medium": 40,
    "high": 70
}
