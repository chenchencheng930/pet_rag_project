// 文件位置：js/api.js
/**
 * 核心网络通信模块 (API Service)
 * 处理前端与后端 Flask 及 RAG 向量数据库的数据交互
 */

const ApiService = {
    async fetchAssessment(payload) {
        const response = await fetch('/assessment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        return await response.json();
    }
};
