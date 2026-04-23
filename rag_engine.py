import os
from typing import List, Dict

from config import ASSESSMENTS_DIR, PRODUCTS_DIR, TOP_K


class RagEngine:
    def __init__(self):
        self.docs_cache = {}

    def _get_product_dir(self, pet_type: str, concern_key: str) -> str:
        pet_dir = "dogs" if pet_type == "dog" else "cats"
        return os.path.join(PRODUCTS_DIR, pet_dir, concern_key)

    def _read_txt(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _read_docx(self, file_path: str) -> str:
        try:
            from docx import Document
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except Exception:
            return ""

    def _read_file(self, file_path: str) -> str:
        lower = file_path.lower()
        if lower.endswith(".txt"):
            return self._read_txt(file_path)
        if lower.endswith(".docx"):
            return self._read_docx(file_path)
        return ""

    def _load_documents(self, pet_type: str, concern_key: str) -> List[Dict]:
        cache_key = f"{pet_type}_{concern_key}"
        if cache_key in self.docs_cache:
            return self.docs_cache[cache_key]

        documents = []

        assessment_file = os.path.join(ASSESSMENTS_DIR, f"{concern_key}.txt")
        product_dir = self._get_product_dir(pet_type, concern_key)

        print("assessment_file =", assessment_file)
        print("product_dir =", product_dir)

        if os.path.exists(assessment_file):
            text = self._read_file(assessment_file)
            if text.strip():
                documents.append({
                    "text": text,
                    "metadata": {"source": assessment_file, "type": "assessment"}
                })

        if os.path.exists(product_dir):
            for root, _, files in os.walk(product_dir):
                for name in files:
                    if name.lower().endswith((".txt", ".docx")):
                        file_path = os.path.join(root, name)
                        text = self._read_file(file_path)
                        if text.strip():
                            documents.append({
                                "text": text,
                                "metadata": {"source": file_path, "type": "product"}
                            })

        print("documents count =", len(documents))
        self.docs_cache[cache_key] = documents
        return documents

    def _get_keywords(self, concern_key: str, query: str) -> List[str]:
        keyword_map = {
            "kidney": ["肾", "肾脏", "慢性肾病", "CKD", "低磷", "护肾"],
            "liver": ["肝", "肝脏", "肝功能", "胆红素", "肝性脑病"],
            "skin": ["皮肤", "过敏", "低敏", "水解蛋白", "瘙痒"],
            "urinary": ["泌尿", "尿路", "结石", "鸟粪石", "膀胱炎", "尿液"],
            "digestive": ["胃肠", "消化", "腹泻", "呕吐", "肠道", "胰腺炎"],
            "food_sensitivity": ["食物敏感", "食物不耐受", "水解蛋白", "低敏"],
            "heart": ["心脏", "心衰", "低钠", "牛磺酸", "左旋肉碱", "心肌"],
            "joint": ["关节", "骨关节", "葡萄糖胺", "软骨素", "Omega-3"],
            "obesity": ["肥胖", "体重管理", "减重", "左旋肉碱", "饱腹感"],
            "unknown": [],
        }

        keywords = keyword_map.get(concern_key, []).copy()

        for chunk in query.split("；"):
            chunk = chunk.strip()
            if chunk:
                keywords.append(chunk)

        return keywords

    def retrieve(self, pet_type: str, concern_key: str, query: str) -> List[Dict]:
        documents = self._load_documents(pet_type, concern_key)
        if not documents:
            raise ValueError(f"未找到知识库内容: pet_type={pet_type}, concern_key={concern_key}")

        keywords = self._get_keywords(concern_key, query)
        results = []

        for doc in documents:
            text = doc["text"]
            score = 0.0

            for kw in keywords:
                if kw and kw in text:
                    score += 1.0

            if pet_type == "cat" and "猫" in text:
                score += 2.0
            if pet_type == "dog" and ("犬" in text or "狗" in text):
                score += 2.0

            if doc["metadata"].get("type") == "product":
                score += 0.5

            results.append({
                "text": text,
                "score": score,
                "metadata": doc["metadata"]
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:TOP_K]
