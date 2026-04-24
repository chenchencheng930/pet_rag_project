// 文件位置：js/api.js


const ApiService = {
    async fetchAssessment(payload) {
        const response = await fetch('/assessment', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        return await response.json();
    }
};
