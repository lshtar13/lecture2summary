/* ═══════════════════════════════════════════════════
   Lecture2Summary — Frontend Logic
   ═══════════════════════════════════════════════════ */

// ── State ──────────────────────────────────────────
let audioFile = null;
let pdfFile = null;
let recordedBlob = null;
let mediaRecorder = null;
let recordingChunks = [];
let isRecording = false;
let recordStartTime = null;
let recordTimerInterval = null;
let currentTaskId = null;
let pollInterval = null;

// ── View Navigation ────────────────────────────────
function showView(viewName) {
    if (viewName === 'upload') {
        resetUploadState();
    }

    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`view-${viewName}`).classList.add('active');

    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.nav-btn[data-view="${viewName}"]`);
    if (btn) btn.classList.add('active');

    if (viewName === 'history') loadHistory();
}

function resetUploadState() {
    removeAudioFile();
    removePdfFile();
    document.getElementById('lecture-title').value = '';
    switchAudioTab('file');
    drawIdleVisualizer();
}

// ── Audio Tab Switch ───────────────────────────────
function switchAudioTab(tab) {
    document.querySelectorAll('.card-audio .tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.card-audio .tab[data-tab="${tab}"]`).classList.add('active');

    document.querySelectorAll('.card-audio .tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`audio-tab-${tab}`).classList.add('active');
}

// ── Drag & Drop Setup ──────────────────────────────
function setupDropZone(zoneId, inputId, onFile) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);

    zone.addEventListener('click', () => input.click());

    zone.addEventListener('dragover', e => {
        e.preventDefault();
        zone.classList.add('drag-over');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('drag-over');
    });

    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            onFile(e.dataTransfer.files[0]);
        }
    });

    input.addEventListener('change', () => {
        if (input.files.length > 0) {
            onFile(input.files[0]);
        }
    });
}

function handleAudioFile(file) {
    audioFile = file;
    recordedBlob = null;
    document.getElementById('audio-file-name').textContent = `${file.name} (${formatSize(file.size)})`;
    document.getElementById('audio-file-info').classList.remove('hidden');
    document.getElementById('audio-drop-zone').style.display = 'none';
    updateSubmitBtn();
}

function removeAudioFile() {
    audioFile = null;
    document.getElementById('audio-file-info').classList.add('hidden');
    document.getElementById('audio-drop-zone').style.display = '';
    document.getElementById('audio-input').value = '';
    updateSubmitBtn();
}

function handlePdfFile(file) {
    pdfFile = file;
    document.getElementById('pdf-file-name').textContent = `${file.name} (${formatSize(file.size)})`;
    document.getElementById('pdf-file-info').classList.remove('hidden');
    document.getElementById('pdf-drop-zone').style.display = 'none';
}

function removePdfFile() {
    pdfFile = null;
    document.getElementById('pdf-file-info').classList.add('hidden');
    document.getElementById('pdf-drop-zone').style.display = '';
    document.getElementById('pdf-input').value = '';
}

// ── Browser Recording + Audio Visualizer ───────────
let audioContext = null;
let analyser = null;
let animationFrameId = null;
let currentStream = null;

async function toggleRecording() {
    if (isRecording) {
        stopRecording();
    } else {
        await startRecording();
    }
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        currentStream = stream;

        // Set up MediaRecorder with a supported mime type
        const mimeType = getSupportedMimeType();
        const options = mimeType ? { mimeType } : {};
        mediaRecorder = new MediaRecorder(stream, options);
        recordingChunks = [];

        mediaRecorder.ondataavailable = e => {
            if (e.data.size > 0) recordingChunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
            const usedMimeType = mediaRecorder.mimeType || 'audio/webm';
            recordedBlob = new Blob(recordingChunks, { type: usedMimeType });
            const ext = usedMimeType.includes('webm') ? 'webm' : usedMimeType.includes('mp4') ? 'm4a' : 'ogg';
            audioFile = new File([recordedBlob], `recording_${Date.now()}.${ext}`, { type: usedMimeType });

            document.getElementById('record-status').textContent = `녹음 완료 — ${formatSize(recordedBlob.size)}`;
            document.getElementById('audio-file-name').textContent = `${audioFile.name} (${formatSize(audioFile.size)})`;
            document.getElementById('audio-file-info').classList.remove('hidden');
            updateSubmitBtn();
        };

        // Set up Web Audio API AnalyserNode for visualization
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(stream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.75;
        source.connect(analyser);

        // Start recording
        mediaRecorder.start(1000);
        isRecording = true;
        recordStartTime = Date.now();

        document.querySelector('.recorder').classList.add('recording');
        document.getElementById('record-status').textContent = '녹음 중...';
        document.getElementById('record-btn').title = '정지';

        recordTimerInterval = setInterval(updateRecordTimer, 100);

        // Start visualizer
        drawVisualizer();
    } catch (err) {
        console.error('Recording error:', err);
        document.getElementById('record-status').textContent = '마이크 접근이 거부되었습니다. 브라우저 설정을 확인하세요.';
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    isRecording = false;
    clearInterval(recordTimerInterval);

    // Stop visualizer
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }

    // Stop audio context
    if (audioContext) {
        audioContext.close();
        audioContext = null;
        analyser = null;
    }

    // Stop microphone stream
    if (currentStream) {
        currentStream.getTracks().forEach(t => t.stop());
        currentStream = null;
    }

    document.querySelector('.recorder').classList.remove('recording');
    document.getElementById('record-btn').title = '녹음';

    // Draw idle state on canvas
    drawIdleVisualizer();
}

function drawVisualizer() {
    const canvas = document.getElementById('visualizer-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const WIDTH = canvas.width;
    const HEIGHT = canvas.height;

    // We only need the lower half of frequencies for human voice
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    // Number of bars on one side of the mirror
    const halfBars = 24;
    const totalBars = halfBars * 2;
    const barWidth = (WIDTH / totalBars) * 0.6;
    const gap = (WIDTH / totalBars) * 0.4;
    const centerY = HEIGHT / 2;

    // To add smoothness between frames
    const smoothedValues = new Array(halfBars).fill(0);

    function draw() {
        animationFrameId = requestAnimationFrame(draw);
        analyser.getByteFrequencyData(dataArray);

        ctx.clearRect(0, 0, WIDTH, HEIGHT);

        for (let i = 0; i < halfBars; i++) {
            // Logarithmic sampling to give more weight to lower/mid frequencies where voice lives
            // e.g. humans speak mostly 85Hz - 255Hz, harmonics up to 4kHz-8kHz.
            // pow(i/halfBars, 2) creates a curve that samples low frequencies more finely.
            const ratio = Math.pow(i / halfBars, 1.5);
            // Only look up to ~40% of the frequency bin count to ignore high frequency noise
            const dataIndex = Math.floor(ratio * (bufferLength * 0.4));

            const value = dataArray[dataIndex] || 0;

            // Smooth value differences
            smoothedValues[i] = smoothedValues[i] * 0.7 + value * 0.3;
            const smoothed = smoothedValues[i];

            const normalizedHeight = (smoothed / 255) * (HEIGHT * 0.85);
            const barHeight = Math.max(normalizedHeight, 3);

            // Color gradient: purple → blue
            const hue = 255 - (i / halfBars) * 30;
            const saturation = 70 + (smoothed / 255) * 30;
            const lightness = 55 + (smoothed / 255) * 20;
            ctx.fillStyle = `hsl(${hue}, ${saturation}%, ${lightness}%)`;

            const radius = barWidth / 2;

            // Right side (origin center, extending right)
            const xRight = (WIDTH / 2) + i * (barWidth + gap) + gap / 2;
            drawRoundedRect(ctx, xRight, centerY - barHeight / 2, barWidth, barHeight, radius);
            ctx.fill();

            // Left side (mirrored)
            const xLeft = (WIDTH / 2) - (i + 1) * (barWidth + gap) + gap / 2;
            drawRoundedRect(ctx, xLeft, centerY - barHeight / 2, barWidth, barHeight, radius);
            ctx.fill();
        }
    }

    draw();
}

function drawIdleVisualizer() {
    const canvas = document.getElementById('visualizer-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const WIDTH = canvas.width;
    const HEIGHT = canvas.height;

    ctx.clearRect(0, 0, WIDTH, HEIGHT);

    const barCount = 48;
    const barWidth = (WIDTH / barCount) * 0.6;
    const gap = (WIDTH / barCount) * 0.4;
    const centerY = HEIGHT / 2;

    for (let i = 0; i < barCount; i++) {
        ctx.fillStyle = 'rgba(85, 85, 106, 0.5)';
        const x = i * (barWidth + gap) + gap / 2;
        drawRoundedRect(ctx, x, centerY - 1.5, barWidth, 3, barWidth / 2);
        ctx.fill();
    }
}

function drawRoundedRect(ctx, x, y, width, height, radius) {
    radius = Math.min(radius, height / 2, width / 2);
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
}

function updateRecordTimer() {
    if (!recordStartTime) return;
    const elapsed = Math.floor((Date.now() - recordStartTime) / 1000);
    const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
    const secs = String(elapsed % 60).padStart(2, '0');
    document.getElementById('record-timer').textContent = `${mins}:${secs}`;
}

function getSupportedMimeType() {
    const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'];
    for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) return type;
    }
    return '';
}

// ── Submit ──────────────────────────────────────────
function updateSubmitBtn() {
    const btn = document.getElementById('submit-btn');
    btn.disabled = !audioFile;
}

async function submitTask() {
    if (!audioFile) return;

    const formData = new FormData();
    formData.append('audio', audioFile);
    if (pdfFile) formData.append('pdf', pdfFile);

    const title = document.getElementById('lecture-title').value.trim();
    if (title) formData.append('title', title);

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();

        currentTaskId = data.task_id;
        showView('processing');

        const subtitle = document.getElementById('processing-subtitle');
        subtitle.textContent = pdfFile
            ? '오디오를 텍스트로 변환하고 교안을 참고하여 교정하고 있습니다...'
            : '오디오를 텍스트로 변환하고 있습니다...';

        startPolling(data.task_id);
    } catch (err) {
        console.error('Upload error:', err);
        alert('업로드 중 오류가 발생했습니다.');
    }
}

// ── Polling ─────────────────────────────────────────
function startPolling(taskId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/status/${taskId}`);
            const data = await res.json();

            if (data.status === 'completed') {
                clearInterval(pollInterval);
                await loadResult(taskId);
            } else if (data.status === 'error') {
                clearInterval(pollInterval);
                alert('처리 중 오류가 발생했습니다.');
                showView('upload');
            }
        } catch (err) {
            console.error('Polling error:', err);
        }
    }, 3000);
}

// ── Result ──────────────────────────────────────────
async function loadResult(taskId) {
    try {
        const res = await fetch(`/api/result/${taskId}`);
        const data = await res.json();

        currentTaskId = taskId;

        document.getElementById('result-title').textContent = data.title || '결과';
        document.getElementById('result-meta').textContent = `생성일: ${new Date(data.created_at).toLocaleString('ko-KR')}`;

        document.getElementById('result-summary').textContent = data.summary || '요약 없음';
        document.getElementById('result-transcript').textContent = data.transcript || '텍스트 없음';
        document.getElementById('result-full').textContent = data.full_text || '';

        showView('result');
    } catch (err) {
        console.error('Result load error:', err);
    }
}

function switchResultTab(tab) {
    document.querySelectorAll('.result-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.result-panel').forEach(p => p.classList.remove('active'));

    event.target.classList.add('active');
    document.getElementById(`result-${tab}`).classList.add('active');
}

async function downloadResult() {
    if (!currentTaskId) return;
    window.open(`/api/download/${currentTaskId}`, '_blank');
}

// ── History ─────────────────────────────────────────
async function loadHistory() {
    try {
        const res = await fetch('/api/history');
        const data = await res.json();
        const list = document.getElementById('history-list');

        if (!data.lectures || data.lectures.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
                        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <p>아직 작업 기록이 없습니다</p>
                </div>`;
            return;
        }

        list.innerHTML = data.lectures.map(l => {
            let statusBadge = '';
            if (l.status === 'processing') {
                const progress = l.progress || 0;
                const step = l.current_step || '처리 중...';
                const model = l.active_model ? `<span class="active-model-tag">${l.active_model}</span>` : '';
                statusBadge = `
                    <div class="processing-status-info">
                        <div class="progress-bar-container">
                            <div class="progress-bar-fill" style="width: ${progress}%"></div>
                        </div>
                        <div class="status-meta">
                            <span class="step-label">${step} (${progress}%)</span>
                            ${model}
                        </div>
                    </div>`;
            } else {
                statusBadge = `<span class="status-badge status-${l.status}">${statusText(l.status)}</span>`;
            }

            return `
                <div class="history-item" onclick="handleHistoryClick('${l.id}', '${l.status}')">
                    <div class="history-item-info">
                        <h3>${escapeHtml(l.title)}</h3>
                        <div class="history-item-meta">
                            <span>${new Date(l.created_at).toLocaleString('ko-KR')}</span>
                            ${l.pdf_filename ? '<span>📄 교안 포함</span>' : ''}
                        </div>
                    </div>
                    <div class="history-item-actions">
                        ${statusBadge}
                        ${l.status === 'error' ? `<button class="retry-btn" onclick="event.stopPropagation(); retryTask('${l.id}')">재시도</button>` : ''}
                        <button class="delete-btn" onclick="event.stopPropagation(); deleteHistory('${l.id}')">삭제</button>
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) {
        console.error('History load error:', err);
    }
}

async function handleHistoryClick(id, status) {
    if (status === 'completed') {
        loadResult(id);
    } else if (status === 'processing') {
        currentTaskId = id;
        showView('processing');
        startPolling(id);
    } else if (status === 'error') {
        try {
            const res = await fetch(`/api/result/${id}`);
            const data = await res.json();
            alert(`오류 내용: ${data.summary || '상세 정보 없음'}`);
        } catch (err) {
            alert('오류 정보를 가져오지 못했습니다.');
        }
    }
}

async function deleteHistory(taskId) {
    if (!confirm('이 기록을 삭제하시겠습니까?')) return;
    try {
        await fetch(`/api/history/${taskId}`, { method: 'DELETE' });
        loadHistory();
    } catch (err) {
        console.error('Delete error:', err);
    }
}

async function retryTask(taskId) {
    try {
        const res = await fetch(`/api/retry/${taskId}`, { method: 'POST' });
        if (res.ok) {
            currentTaskId = taskId;
            showView('processing');
            startPolling(taskId);
        } else {
            const data = await res.json();
            alert(`재시도 실패: ${data.detail || '알 수 없는 오류'}`);
        }
    } catch (err) {
        console.error('Retry error:', err);
        alert('재시도 중 오류가 발생했습니다.');
    }
}

// ── Utilities ───────────────────────────────────────
function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function statusText(status) {
    const map = { completed: '완료', processing: '처리 중', error: '오류', pending: '대기 중' };
    return map[status] || status;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── Initialize ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    setupDropZone('audio-drop-zone', 'audio-input', handleAudioFile);
    setupDropZone('pdf-drop-zone', 'pdf-input', handlePdfFile);
    drawIdleVisualizer();
    initUsageDashboard();
});

// ── Usage Dashboard (WebSocket) ─────────────────────
let usageSocket = null;

function initUsageDashboard() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/usage`;

    usageSocket = new WebSocket(wsUrl);

    usageSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'usage_update') {
            updateUsageDashboard(data.stats);
        } else if (data.type === 'status_update') {
            renderHistory(data.lectures);
        }
    };

    usageSocket.onclose = () => {
        console.log('Usage WebSocket closed. Retrying in 5s...');
        setTimeout(initUsageDashboard, 5000);
    };
}

function updateUsageDashboard(stats) {
    const container = document.getElementById('usage-cards');
    if (!stats || Object.keys(stats).length === 0) {
        container.innerHTML = '<div class="usage-loading">아직 사용 기록이 없습니다. 분석을 시작해 보세요!</div>';
        return;
    }

    // Sort models by usage (most active first)
    const sortedModels = Object.keys(stats).sort((a, b) => stats[b].requests - stats[a].requests);

    container.innerHTML = sortedModels.map(model => {
        const s = stats[model];
        // Dynamic limits for visualization (adjust based on user tier usually)
        const tokenLimit = 1000000; // 1M tokens as a reference 100%
        const inputPercent = Math.min((s.input / tokenLimit) * 100, 100);
        const outputPercent = Math.min((s.output / tokenLimit) * 100, 100);

        return `
            <div class="usage-card">
                <div class="usage-card-header">
                    <span class="model-name">${model}</span>
                    <span class="request-count">${s.requests} Requests</span>
                </div>
                <div class="usage-stats">
                    <div class="stat-row">
                        <div class="stat-label">
                            <span>Input Tokens</span>
                            <span class="stat-value">${s.input.toLocaleString()}</span>
                        </div>
                        <div class="usage-bar-bg">
                            <div class="usage-bar-fill" style="width: ${inputPercent}%"></div>
                        </div>
                    </div>
                    <div class="stat-row">
                        <div class="stat-label">
                            <span>Output Tokens</span>
                            <span class="stat-value">${s.output.toLocaleString()}</span>
                        </div>
                        <div class="usage-bar-bg">
                            <div class="usage-bar-fill" style="width: ${outputPercent}%"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}
