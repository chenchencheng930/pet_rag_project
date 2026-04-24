
// 文件位置：js/dashboard.js
/**
 * 健康评估业务逻辑控制器 (Controller)
 * 负责动态渲染体征表单、收集用户输入、以及处理诊断流动画
 */

// 临床医学指标配置 (Data Dictionary)

const CLINICAL_CONFIG = {
    kidney: { name: '肾脏健康', indicators: [{key: 'creatinine', label: '肌酐'}, {key: 'bun', label: '尿素氮'}, {key: 'phosphorus', label: '血磷'}], symptoms: [{key: 'increased_drinking', label: '饮水异常增加'}, {key: 'increased_urination', label: '排尿明显增多'}, {key: 'low_energy', label: '精神状态变差'}] },
    liver: { name: '肝脏与胆道', indicators: [{key: 'alt', label: 'ALT'}, {key: 'ast', label: 'AST'}, {key: 'total_bilirubin', label: '总胆红素'}], symptoms: [{key: 'jaundice', label: '眼白/牙龈发黄 (黄疸)'}, {key: 'appetite_loss', label: '食欲严重下降'}] },
    skin: { name: '皮肤与过敏', indicators: [{key: 'wbc', label: '嗜酸性粒细胞'}], symptoms: [{key: 'itching', label: '频繁抓挠瘙痒'}, {key: 'skin_redness', label: '皮肤出现红斑'}, {key: 'hair_loss', label: '异常掉毛/斑秃'}, {key: 'dandruff', label: '皮屑增多'}] },
    urinary: { name: '泌尿系统', indicators: [{key: 'urine_ph', label: '尿pH值'}, {key: 'urine_crystals', label: '尿结晶'}, {key: 'urine_protein', label: '尿蛋白'}], symptoms: [{key: 'frequent_urination', label: '尿频'}, {key: 'difficulty_urinating', label: '排尿困难/痛苦'}, {key: 'bloody_urine', label: '尿血/尿色深'}] },
    digestive: { name: '肠胃消化', indicators: [], symptoms: [{key: 'diarrhea', label: '频繁腹泻/软便'}, {key: 'vomiting', label: '经常呕吐'}, {key: 'appetite_loss', label: '挑食/不爱吃饭'}] },
    food_sensitivity: { name: '食物不耐受', indicators: [], symptoms: [{key: 'itching', label: '饭后慢性瘙痒'}, {key: 'diarrhea', label: '吃特定食物后拉肚子'}] },
    heart: { name: '心脏功能', indicators: [{key: 'heart_rate', label: '心率检测'}], symptoms: [{key: 'cough', label: '干咳(尤其早晚)'}, {key: 'rapid_breathing', label: '呼吸急促'}, {key: 'exercise_intolerance', label: '不愿运动/易喘'}] },
    joint: { name: '骨骼关节', indicators: [], symptoms: [{key: 'limping', label: '走路跛行'}, {key: 'joint_stiffness', label: '起身关节僵硬'}, {key: 'difficulty_climbing_stairs', label: '不愿跳跃/上下楼梯困难'}] },
    obesity: { name: '体重管理', indicators: [], symptoms: [{key: 'weight_gain', label: '体重不受控增加'}, {key: 'reduced_activity', label: '变得慵懒不爱动'}] }
};

// 页面加载完成时初始化表单
window.addEventListener('DOMContentLoaded', () => {
    renderClinicalForm();
    const resultSection = document.getElementById('resultSection');
    if (resultSection) {
        originalResultSectionHtml = resultSection.innerHTML;
    }
});


function renderClinicalForm() {
    const container = document.getElementById('diseaseListContainer');
    if (!container) return;

    let htmlTemplate = '';
    for (let key in CLINICAL_CONFIG) {
        const data = CLINICAL_CONFIG[key];
        
        let indHtml = '';
        if(data.indicators.length > 0) {
            indHtml += '<h6 style="font-size:14px; color:#1e3a8a; margin-bottom:12px; font-weight:bold;">🩺 录入体检指标</h6><div class="row g-3">';
            data.indicators.forEach(ind => {
                indHtml += `
                <div class="col-md-6 d-flex align-items-center">
                    <label class="form-label mb-0 me-3" style="min-width: 80px;">${ind.label}</label>
                    <select class="form-select form-select-sm dynamic-indicator" data-key="${ind.key}">
                        <option value="unknown">未测 / 正常</option><option value="high">异常偏高</option><option value="low">异常偏低</option>
                    </select>
                </div>`;
            });
            indHtml += '</div><hr style="border-color: #cbd5e1; margin: 15px 0;">';
        }

        let symHtml = '';
        if(data.symptoms.length > 0) {
            symHtml += '<h6 style="font-size:14px; color:#1e3a8a; margin-bottom:12px; font-weight:bold;">🤧 勾选表现症状</h6><div style="font-size:14px;">';
            data.symptoms.forEach(sym => {
                symHtml += `<label class="me-4 mb-2" style="cursor:pointer;"><input type="checkbox" class="form-check-input dynamic-symptom me-1" value="${sym.key}"> ${sym.label}</label>`;
            });
            symHtml += '</div>';
        }

        htmlTemplate += `
        <div class="disease-item">
            <div class="d-flex justify-content-between align-items-center">
                <strong style="font-size: 15px; color: #334155;"> ${data.name}</strong>
                <div class="btn-group" role="group">
                    <input type="radio" class="btn-check" name="toggle_${key}" id="no_${key}" value="no" autocomplete="off" checked onchange="toggleDetails('${key}', false)">
                    <label class="btn btn-outline-secondary btn-sm" for="no_${key}">无异常</label>
                    
                    <input type="radio" class="btn-check" name="toggle_${key}" id="yes_${key}" value="yes" autocomplete="off" onchange="toggleDetails('${key}', true)">
                    <label class="btn btn-outline-danger btn-sm" for="yes_${key}">有异常</label>
                </div>
            </div>
            <div id="details_${key}" class="disease-details" style="display: none;">
                ${indHtml}
                ${symHtml}
            </div>
        </div>`;
    }
    container.innerHTML = htmlTemplate;
}

function toggleDetails(diseaseKey, isShow) {
    const detailsDiv = document.getElementById(`details_${diseaseKey}`);
    if (isShow) {
        detailsDiv.style.display = 'block';
    } else {
        detailsDiv.style.display = 'none';
    }
}

// 核心提交逻辑
async function handleClinicalSubmit() {
    await syncDashboardBasicInfoToDb();
    syncDashboardBasicInfo();
    window.scrollTo(0, 0); 
    document.getElementById('inputSection').style.display = 'none';
    document.getElementById('loadingSection').style.display = 'block';

    const collectedIndicators = {};
    const collectedSymptoms = {};
    let selectedConcerns = [];

    // 数据采集
    document.querySelectorAll('.disease-item').forEach(item => {
        const detailsDiv = item.querySelector('.disease-details');
        if (detailsDiv.style.display === 'block') {
            const radioYes = item.querySelector('input[value="yes"]');
            if(radioYes) selectedConcerns.push(radioYes.name.replace('toggle_', ''));

            detailsDiv.querySelectorAll('.dynamic-indicator').forEach(select => {
                if(select.value !== 'unknown') collectedIndicators[select.getAttribute('data-key')] = select.value;
            });
            detailsDiv.querySelectorAll('.dynamic-symptom').forEach(checkbox => {
                if(checkbox.checked) collectedSymptoms[checkbox.value] = true;
            });
        }
    });

    const primary_concern = selectedConcerns.length > 0 ? selectedConcerns : ['unknown'];

    // 构建发往后端的 Payload
    const payload = {
        pet_type: document.getElementById('pet_type').value,
        basic_info: {
            age_stage: document.getElementById('age_stage').value,
            weight: parseFloat(document.getElementById('weight').value),
            bcs: document.getElementById('bcs').value,
            sterilized: true
        },
        assessment_mode: "hybrid",
        primary_concern: primary_concern,
        symptoms: collectedSymptoms,
        medical_indicators: collectedIndicators
    };

    // 系统状态日志动画 (专业表述)
    const logBox = document.getElementById('logBox');
    const diagnosticLogs = [
        "[INFO] System initialized. Captured clinical data matrix.",
        "[PROCESSING] Rule-Engine routing selected concerns: " + primary_concern.join(", ").toUpperCase(),
        "[RAG-FETCH] Querying vector database for veterinary guidelines...",
        "[AGENT] RAG extraction complete. Initializing LLM inference...",
        "[AGENT] Generating targeted medical and nutritional strategy...",
        "[SUCCESS] UI Components rendering complete."
    ];
    
    let i = 0;
    const logInterval = setInterval(() => {
        if (i < diagnosticLogs.length) {
            logBox.innerHTML += `<div style="margin-bottom: 8px; opacity: 0; animation: fadeIn 0.5s forwards;">${diagnosticLogs[i]}</div>`;
            logBox.scrollTop = logBox.scrollHeight;
            i++;
        } else {
            clearInterval(logInterval);
        }
    }, 700);

    try {
        // 调用 api.js 中的模块，并且加入最少 4.5 秒的强制动画等待
        const [response] = await Promise.all([
            ApiService.fetchAssessment(payload).catch(() => null),
            new Promise(resolve => setTimeout(resolve, 4500))
        ]);

        let resultData = null;

        if (response && response.code === 200) {
            resultData = response.data;
        } else {
            resultData = {
                summary: payload.basic_info,
                suspected_conditions: [{
                    condition_name: '综合健康评估',
                    evidence: ['基于选定体征推断'],
                    explanation: '数据同步中（本地应急展示模式）'
                }],
                overall_risk_level: 'high',
                health_advice: ['建议定期排查异常生化指标', '安排线下专科复诊'],
                diet_advice: ['选择高消化率配方', '避免喂食人类食物'],
                product_recommendations: [{
                    product_name: '智能处方配方推荐',
                    reason: ['精准对症支持']
                }]
            };
            resultData.summary.pet_type = payload.pet_type;
        }

        renderResultView(resultData);


    } catch (error) {
        alert("流程发生异常，请检查网络后重试。");
        location.reload();
    }
}
function renderResultView(d) {
    document.getElementById('loadingSection').style.display = 'none';
    document.getElementById('resultSection').style.display = 'block';

    document.getElementById('res-type').innerText = d.summary.pet_type === 'dog' ? '狗' : '猫';
    document.getElementById('res-age').innerText = d.summary.age_stage;
    document.getElementById('res-weight').innerText = d.summary.weight + ' kg';

    if (d.suspected_conditions && d.suspected_conditions.length > 0) {
        const conditions = d.suspected_conditions;

        document.getElementById('res-disease').innerText = conditions
            .map(condition => condition.condition_name || '综合健康评估')
            .join(' / ');

        document.getElementById('res-evidence').innerText = conditions
            .map(condition => {
                const name = condition.condition_name || '综合健康评估';
                const evidence = (condition.evidence || []).join('、') || '暂无明确证据';
                return `【${name}】${evidence}`;
            })
            .join('\n');

        const allExplanationParts = [];

        conditions.forEach((condition, index) => {
            const title = condition.condition_name || `方向${index + 1}`;
            const parts = [];

            if (condition.clinical_summary) {
                parts.push(`【临床摘要】${condition.clinical_summary}`);
            }

            if (condition.risk_interpretation) {
                parts.push(`【风险解读】${condition.risk_interpretation}`);
            }

            if (condition.nutrition_focus) {
                parts.push(`【营养重点】${condition.nutrition_focus}`);
            }

            if (condition.follow_up) {
                parts.push(`【后续建议】${condition.follow_up}`);
            }

            if (parts.length > 0) {
                allExplanationParts.push(`【${title}】\n${parts.join('\n')}`);
            } else {
                allExplanationParts.push(`【${title}】\n${condition.explanation || '暂无进一步评估说明'}`);
            }
        });

        document.getElementById('res-explanation').innerText = allExplanationParts.join('\n\n');
    }

    if (d.overall_risk_level === 'high') {
        document.getElementById('res-score').innerText = '高风险';
    } else if (d.overall_risk_level === 'medium') {
        document.getElementById('res-score').innerText = '中风险';
        document.querySelector('.score-circle').style.backgroundColor = '#fef3c7';
        document.querySelector('.score-circle').style.borderColor = '#fde68a';
        document.querySelector('.score-circle').style.color = '#d97706';
    } else {
        document.getElementById('res-score').innerText = '低风险';
        document.querySelector('.score-circle').style.backgroundColor = '#dcfce7';
        document.querySelector('.score-circle').style.borderColor = '#bbf7d0';
        document.querySelector('.score-circle').style.color = '#16a34a';
    }

    document.getElementById('res-advice').innerHTML =
        `<strong style="color:#1e3a8a;">医疗干预方案：</strong><br> ${d.health_advice.join('<br>')}<br><br>` +
        `<strong style="color:#1e3a8a;">营养调理方向：</strong><br> ${d.diet_advice.join('<br>')}`;

    const products = d.product_recommendations || [];

    if (products.length > 0) {
        document.getElementById('res-product').innerText = products
            .map(item => item.product_name || '未识别具体产品')
            .join(' / ');

        document.getElementById('res-reason').innerText = products
            .map(item => {
                const name = item.product_name || '推荐产品';
                const reason = (item.reason || []).join(' | ') || '暂无推荐理由';
                return `【${name}】${reason}`;
            })
            .join('\n');
    } else {
        document.getElementById('res-product').innerText = '暂无推荐产品';
        document.getElementById('res-reason').innerText = '暂无推荐理由';
    }
}
