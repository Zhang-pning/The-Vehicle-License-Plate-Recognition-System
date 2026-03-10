let currentFile, selectedExample, examples;
let updateTip, uploadArea, fileInput, exampleGrid, recognizeBtn, resultSection, resultImg, plateList, uploadContent, uploadPreview;

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM 加载完成');
    updateTip = document.getElementById('updateTip');
    uploadArea = document.getElementById('uploadArea');
    fileInput = document.getElementById('fileInput');
    exampleGrid = document.getElementById('exampleGrid');
    recognizeBtn = document.getElementById('recognizeBtn');
    resultSection = document.getElementById('resultSection');
    resultImg = document.getElementById('resultImg');
    plateList = document.getElementById('plateList');
    uploadContent = document.getElementById('uploadContent');
    uploadPreview = document.getElementById('uploadPreview');

    if (!uploadArea) console.error('uploadArea 未找到');
    if (!fileInput) console.error('fileInput 未找到');
    if (!recognizeBtn) console.error('recognizeBtn 未找到');
    if (!exampleGrid) console.error('exampleGrid 未找到');

    currentFile = null;
    selectedExample = null;
    examples = [];
    loadExamples();
    bindEvents();
});

function showUploadPreview(file) {
    if (!uploadPreview || !uploadContent) {
        console.error('showUploadPreview: 元素不存在');
        return;
    }
    const reader = new FileReader();
    reader.onload = function(e) {
        uploadPreview.src = e.target.result;
        uploadPreview.style.display = 'block';
        uploadContent.style.display = 'none';
    };
    reader.readAsDataURL(file);
}

function resetUploadArea() {
    if (!uploadPreview || !uploadContent) return;
    uploadPreview.style.display = 'none';
    uploadContent.style.display = 'block';
    uploadPreview.src = '';
}

function bindEvents() {
    console.log('绑定事件开始');

    if (uploadArea) {
        uploadArea.addEventListener('click', () => {
            console.log('上传区域被点击');
            fileInput.click();
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }

    if (uploadArea) {
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0]);
            }
        });
    }

    if (recognizeBtn) {
        recognizeBtn.addEventListener('click', recognize);
    }

    const logoutBtn = document.getElementById('logoutBtn');
    const aboutBtn = document.getElementById('aboutBtn');
    const closeAbout = document.getElementById('closeAbout');

    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    } else {
        console.error('logoutBtn 未找到');
    }

    if (aboutBtn) {
        aboutBtn.addEventListener('click', showAbout);
    } else {
        console.error('aboutBtn 未找到');
    }

    if (closeAbout) {
        closeAbout.addEventListener('click', hideAbout);
    } else {
        console.error('closeAbout 未找到');
    }

    window.addEventListener('click', (e) => {
        const modal = document.getElementById('aboutModal');
        if (e.target === modal) hideAbout();
    });

    console.log('绑定事件完成');
}

async function logout() {
    if (!confirm('确定要退出登录吗？')) return;
    try {
        const response = await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            window.location.href = '/login';
        } else {
            alert('退出失败：' + data.message);
        }
    } catch (error) {
        console.error('登出错误:', error);
        alert('网络错误，请稍后重试');
    }
}

function showAbout() {
    const modal = document.getElementById('aboutModal');
    if (modal) modal.classList.add('show');
}

function hideAbout() {
    const modal = document.getElementById('aboutModal');
    if (modal) modal.classList.remove('show');
}

async function loadExamples() {
    try {
        const response = await fetch('/api/parking/examples', {
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            examples = data.examples;
            renderExamples();
        } else {
            if (exampleGrid) {
                exampleGrid.innerHTML = `<div class="loading-examples">加载失败：${data.message}</div>`;
            }
        }
    } catch (error) {
        console.error('加载示例失败:', error);
        if (exampleGrid) {
            exampleGrid.innerHTML = '<div class="loading-examples">网络错误</div>';
        }
    }
}

function renderExamples() {
    if (!exampleGrid) return;
    if (examples.length === 0) {
        exampleGrid.innerHTML = '<div class="loading-examples">暂无示例图片</div>';
        return;
    }
    let html = '';
    examples.forEach(filename => {
        html += `
            <div class="example-item" data-filename="${filename}">
                <img src="/static/images_demo/images/${filename}" alt="${filename}">
            </div>
        `;
    });
    exampleGrid.innerHTML = html;

    document.querySelectorAll('.example-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            document.querySelectorAll('.example-item').forEach(el => el.classList.remove('selected'));
            item.classList.add('selected');
            const filename = item.dataset.filename;
            selectExample(filename);
        });
    });
}

function selectExample(filename) {
    selectedExample = filename;
    currentFile = null;
    if (fileInput) fileInput.value = '';
    if (recognizeBtn) recognizeBtn.disabled = false;
    if (updateTip) updateTip.style.display = 'inline-block';
    resetUploadArea();
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
}

function handleFile(file) {
    document.querySelectorAll('.example-item').forEach(el => el.classList.remove('selected'));
    selectedExample = null;
    currentFile = file;
    if (recognizeBtn) recognizeBtn.disabled = false;
    if (updateTip) updateTip.style.display = 'inline-block';
    showUploadPreview(file);
}

async function recognize() {
    if (updateTip) updateTip.style.display = 'none';

    if (!currentFile && !selectedExample) {
        alert('请先选择图片');
        return;
    }

    let fileToUpload;
    if (currentFile) {
        fileToUpload = currentFile;
    } else {
        try {
            const response = await fetch(`/static/images_demo/images/${selectedExample}`);
            const blob = await response.blob();
            fileToUpload = new File([blob], selectedExample, { type: blob.type });
        } catch (error) {
            console.error('获取示例图片失败:', error);
            alert('获取示例图片失败');
            return;
        }
    }

    const formData = new FormData();
    formData.append('image', fileToUpload);

    if (recognizeBtn) {
        recognizeBtn.disabled = true;
        recognizeBtn.textContent = '识别中...';
    }

    try {
        const response = await fetch('/api/parking/recognize', {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        const data = await response.json();

        if (data.success) {
            if (resultImg) resultImg.src = data.image;
            renderPlateList(data.plates);
            if (resultSection) resultSection.style.display = 'flex';
        } else {
            alert('识别失败：' + data.message);
        }
    } catch (error) {
        console.error('识别错误:', error);
        alert('网络错误，请稍后重试');
    } finally {
        if (recognizeBtn) {
            recognizeBtn.disabled = false;
            recognizeBtn.textContent = '开始识别';
        }
        resetUploadArea();
    }
}

function renderPlateList(plates) {
    if (!plateList) return;
    if (!plates || plates.length === 0) {
        plateList.innerHTML = '<div class="plate-item">未检测到车牌</div>';
        return;
    }
    let html = '';
    plates.forEach((plate, index) => {
        const colorClass = plate.color === '蓝色' ? 'blue' : (plate.color === '绿色' ? 'green' : 'yellow');
        html += `
            <div class="plate-item ${colorClass}">
                <div class="plate-color">${plate.color}</div>
                <div class="plate-number">${plate.number}</div>
                <div class="plate-confidence">车牌定位置信度: ${plate.confidence}</div>
            </div>
        `;
    });
    plateList.innerHTML = html;
}