

const CommunityDataStore = {
    feeds: [
        {
            id: 1001,
            authorName: '系统验证专家',
            avatarUrl: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Admin',
            publishTime: '10分钟前',
            petInfo: '平台主治医师',
            topic: '营养配方',
            content: '处方粮的过渡期建议延长至 10-14 天，特别是针对伴有消化系统敏感的患犬。可以通过逐步增加处方粮比例，观察其粪便形态及进食意愿来动态调整。',
            imageUrl: '',
            likes: 24,
            comments: 8,
            isLiked: false
        }
    ],

    getCurrentUser() {
        return localStorage.getItem('currentUser') || '匿名访客';
    }
};

let currentSelectedImage = null;

document.addEventListener('DOMContentLoaded', async () => {
    await loadPostsFromServer();
});


function renderFeedList() {
    const container = document.getElementById('feedContainer');
    if (!container) return;

    container.innerHTML = ''; 

    CommunityDataStore.feeds.forEach(post => {
        const likeClass = post.isLiked ? 'interaction-btn active' : 'interaction-btn';
        const topicHtml = post.topic ? `<span class="topic-tag">#${post.topic}</span>` : '';
        const imageHtml = post.imageUrl ? `<img src="${post.imageUrl}" class="feed-image" alt="附件影像">` : '';

        const postHtml = `
            <article class="feed-item" id="post-${post.id}">
                <div class="feed-header">
                    <img src="${post.avatarUrl}" alt="用户头像" class="author-avatar">
                    <div class="author-info">
                        <span class="author-name">${post.authorName}</span>
                        <div class="author-meta">
                            <span>${post.publishTime}</span>
                            <span class="pet-tag">${post.petInfo}</span>
                        </div>
                    </div>
                </div>
                <div class="feed-content">
                    ${topicHtml} ${post.content}
                    ${imageHtml}
                </div>
                <div class="feed-footer">
                    <div class="${likeClass}" onclick="toggleLike(${post.id})">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                        </svg>
                        <span>赞同 ${post.likes}</span>
                    </div>
                    <div class="interaction-btn">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                        </svg>
                        <span>评论 ${post.comments}</span>
                    </div>
                </div>
            </article>
        `;
        container.insertAdjacentHTML('beforeend', postHtml);
    });
}

function handleImageSelection(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            currentSelectedImage = e.target.result;
            document.getElementById('imagePreview').src = currentSelectedImage;
            document.getElementById('imagePreviewContainer').style.display = 'block';
        };
        reader.readAsDataURL(file);
    }
}

function removeImage() {
    currentSelectedImage = null;
    document.getElementById('fileUpload').value = '';
    document.getElementById('imagePreviewContainer').style.display = 'none';
}

function submitPost() {
    const inputEl = document.getElementById('postInput');
    const topicEl = document.getElementById('topicInput'); // 获取新的文本框
    const content = inputEl.value.trim();
    
    // 获取话题，并安全过滤用户可能误输入的开头 # 号
    let topic = topicEl.value.trim();
    topic = topic.replace(/^#+/, ''); 

    if (!content) {
        alert('发布内容不可为空');
        return;
    }

    // 标准 Payload 格式
    const requestPayload = {
        author: CommunityDataStore.getCurrentUser(),
        content: content,
        topic: topic,
        image_base64: currentSelectedImage
    };

    // 本地前端状态更新
    const newPost = {
        id: Date.now(),
        authorName: requestPayload.author,
        avatarUrl: 'https://api.dicebear.com/7.x/avataaars/svg?seed=' + requestPayload.author,
        post.created_at || '刚刚',
        petInfo: '系统注册用户',
        topic: requestPayload.topic,
        content: requestPayload.content,
        imageUrl: requestPayload.image_base64,
        likes: 0,
        comments: 0,
        isLiked: false
    };

    CommunityDataStore.feeds.unshift(newPost);
    
    // 初始化表单状态
    inputEl.value = '';
    topicEl.value = '';
    removeImage();
    renderFeedList();
}

function toggleLike(postId) {
    const post = CommunityDataStore.feeds.find(p => p.id === postId);
    if (post) {
        post.isLiked = !post.isLiked;
        post.likes += post.isLiked ? 1 : -1;
        renderFeedList();
    }
}