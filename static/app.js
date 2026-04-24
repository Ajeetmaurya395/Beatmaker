// Beatmaker Web Audio Engine & UI Logic

const API_BASE = '/api';
let audioCtx = null;
let currentBundle = null;
let stemBuffers = {};
let stemSources = {};
let stemGains = {};
let isPlaying = false;
let startTime = 0;
let pauseTime = 0;
let animationFrameId = null;

// UI Elements
const els = {
    form: document.getElementById('generate-form'),
    btnSubmit: document.getElementById('btn-submit'),
    loader: document.getElementById('loader'),
    genreChips: document.getElementById('genre-chips'),
    genreInput: document.getElementById('genre'),
    historyGrid: document.getElementById('history-grid'),
    playerCard: document.getElementById('player-card'),
    stemsContainer: document.getElementById('stems-container'),
    btnPlay: document.getElementById('btn-play'),
    btnStop: document.getElementById('btn-stop'),
    canvas: document.getElementById('waveform'),
    npTitle: document.getElementById('np-title'),
    npMeta: document.getElementById('np-meta'),
    profileSummary: document.getElementById('profile-summary'),
    refUpload: document.getElementById('reference-upload'),
    btnRlhf: document.getElementById('btn-rlhf-align'),
    uploadStatus: document.getElementById('upload-status'),
    loraForm: document.getElementById('lora-form'),
    loraUpload: document.getElementById('lora-upload'),
    loraFilesCount: document.getElementById('lora-files-count'),
    btnLoraSubmit: document.getElementById('btn-lora-submit'),
    loraStatus: document.getElementById('lora-status'),
    hubRecs: document.getElementById('hub-recommendations'),
    hubRepoId: document.getElementById('hub-repo-id'),
    btnHubDownload: document.getElementById('btn-hub-download'),
    hubStatus: document.getElementById('hub-status')
};

// Canvas context
const ctx = els.canvas.getContext('2d');

// Init
async function init() {
    await fetchGenres();
    await fetchHistory();
    await fetchProfile();
    await fetchHubRecommendations();
    
    els.form.addEventListener('submit', handleGenerate);
    els.btnPlay.addEventListener('click', togglePlay);
    els.btnStop.addEventListener('click', stopAudio);
    
    // Feedback buttons
    document.querySelectorAll('.btn-feedback').forEach(btn => {
        btn.addEventListener('click', () => submitFeedback(btn.dataset.fb));
    });

    // Upload
    if (els.refUpload) {
        els.refUpload.addEventListener('change', handleReferenceUpload);
    }
    
    // RLHF Start
    if (els.btnRlhf) {
        els.btnRlhf.addEventListener('click', handleRlhfAlign);
    }
    
    // LoRA Cloud Training
    if (els.loraForm) {
        els.loraUpload.addEventListener('change', (e) => {
            const count = e.target.files.length;
            els.loraFilesCount.innerText = `${count} file${count !== 1 ? 's' : ''} selected`;
        });
        els.loraForm.addEventListener('submit', handleLoraSubmit);
    }

    // Hub Download
    if (els.btnHubDownload) {
        els.btnHubDownload.addEventListener('click', handleHubDownload);
    }

    // Export buttons
    document.getElementById('btn-download-mix')?.addEventListener('click', downloadMix);
    document.getElementById('btn-download-stems')?.addEventListener('click', downloadStemsZip);

    // Resize canvas
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();
}

function resizeCanvas() {
    els.canvas.width = els.canvas.offsetWidth;
    els.canvas.height = els.canvas.offsetHeight;
    if (!isPlaying && stemBuffers['preview']) {
        drawStaticWaveform(stemBuffers['preview']);
    }
}

// Data Fetching
async function fetchGenres() {
    const res = await fetch(`${API_BASE}/genres`);
    const data = await res.json();
    
    els.genreChips.innerHTML = data.genres.map(g => 
        `<div class="chip" data-genre="${g}">${g}</div>`
    ).join('');

    // Setup chip selection
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            els.genreInput.value = chip.dataset.genre;
        });
    });
}

async function fetchHistory() {
    const res = await fetch(`${API_BASE}/bundles`);
    const data = await res.json();
    
    els.historyGrid.innerHTML = data.bundles.map(b => `
        <div class="bundle-card" onclick="loadBundle('${b.id}')">
            <h3>${b.prompt}</h3>
            <div class="caption mono">${b.genre} • ${b.bpm} BPM</div>
        </div>
    `).join('');
}

async function fetchProfile() {
    const res = await fetch(`${API_BASE}/profile`);
    const data = await res.json();
    els.profileSummary.innerText = data.summary;
}

// Generation
async function handleGenerate(e) {
    e.preventDefault();
    
    const payload = {
        prompt: document.getElementById('prompt').value,
        genre: els.genreInput.value || undefined,
        bpm: document.getElementById('bpm').value ? parseInt(document.getElementById('bpm').value) : undefined,
        bars: document.getElementById('bars').value ? parseInt(document.getElementById('bars').value) : undefined,
        seed: document.getElementById('seed').value ? parseInt(document.getElementById('seed').value) : undefined,
    };

    els.btnSubmit.disabled = true;
    els.loader.style.display = 'block';

    try {
        const res = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error('Generation failed');
        
        const data = await res.json();
        await fetchHistory(); // refresh library
        await loadBundle(data.bundle_id); // auto-load the new beat
        
    } catch (err) {
        alert(err.message);
    } finally {
        els.btnSubmit.disabled = false;
        els.loader.style.display = 'none';
    }
}

async function handleReferenceUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    els.uploadStatus.style.display = 'block';
    els.uploadStatus.innerText = 'Analyzing reference...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API_BASE}/ingest`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) throw new Error('Upload failed');
        
        const data = await res.json();
        els.profileSummary.innerText = data.profile_summary;
        els.uploadStatus.innerText = 'Trained successfully!';
        setTimeout(() => { els.uploadStatus.style.display = 'none'; }, 3000);
    } catch (err) {
        els.uploadStatus.innerText = 'Error: ' + err.message;
    } finally {
        e.target.value = ''; // reset input
    }
}

async function handleRlhfAlign() {
    els.uploadStatus.style.display = 'block';
    els.uploadStatus.innerText = 'Connecting to Lightning Studio for DPO...';
    els.btnRlhf.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/rlhf/train`, { method: 'POST' });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || 'RLHF Alignment failed');
        
        els.uploadStatus.innerText = data.message;
        setTimeout(() => { els.uploadStatus.style.display = 'none'; }, 5000);
    } catch (err) {
        els.uploadStatus.innerText = 'Error: ' + err.message;
    } finally {
        els.btnRlhf.disabled = false;
    }
}

async function handleLoraSubmit(e) {
    e.preventDefault();
    
    const files = els.loraUpload.files;
    const name = document.getElementById('lora-name').value;
    if (files.length === 0) return;

    els.btnLoraSubmit.disabled = true;
    els.loraStatus.style.display = 'block';
    
    const formData = new FormData();
    formData.append('name', name);
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    try {
        const res = await fetch(`${API_BASE}/lora/train`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) throw new Error('Cloud Training failed');
        
        const data = await res.json();
        els.loraStatus.innerText = 'Success! Saved LoRA: ' + data.path;
        setTimeout(() => { els.loraStatus.style.display = 'none'; els.loraStatus.innerText = 'Uploading and initializing Lightning Job...'; }, 5000);
    } catch (err) {
        els.loraStatus.innerText = 'Error: ' + err.message;
    } finally {
        els.btnLoraSubmit.disabled = false;
        els.loraUpload.value = '';
        els.loraFilesCount.innerText = '0 files selected';
        document.getElementById('lora-name').value = '';
    }
}

// Audio Player & Stem Loading
async function loadBundle(bundleId) {
    stopAudio();
    currentBundle = bundleId;
    stemBuffers = {};
    
    const res = await fetch(`${API_BASE}/bundles/${bundleId}/manifest`);
    const manifest = await res.json();
    
    els.npTitle.innerText = manifest.spec.prompt;
    els.npMeta.innerText = `${manifest.spec.genre} • ${manifest.spec.bpm} BPM • ${manifest.spec.key_root} ${manifest.spec.scale}`;
    els.playerCard.style.display = 'flex';
    
    // Init AudioContext if needed
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') await audioCtx.resume();

    // Render stem UI
    const stems = manifest.spec.stems;
    els.stemsContainer.innerHTML = stems.map(stem => `
        <div class="stem-track" data-stem="${stem}">
            <div class="stem-color-indicator stem-color-${stem}"></div>
            <div class="stem-name">${stem.padEnd(8, ' ')}</div>
            <div class="stem-controls">
                <button class="stem-btn mute-btn" onclick="toggleMute('${stem}')">M</button>
                <button class="stem-btn solo-btn" onclick="toggleSolo('${stem}')">S</button>
                <input type="range" class="stem-vol" min="0" max="1" step="0.05" value="1" oninput="setGain('${stem}', this.value)">
                <button class="stem-btn tweak-toggle" onclick="toggleTweakRow('${stem}')" title="Tweak this stem">✏️</button>
                <button class="stem-btn" onclick="downloadStem('${stem}')" title="Download this stem">⬇</button>
            </div>
        </div>
        <div class="stem-tweak-row" id="tweak-row-${stem}" style="display: none;">
            <input type="text" class="stem-tweak-input" id="tweak-input-${stem}" placeholder="e.g. warmer, more acoustic, less busy...">
            <select class="stem-tweak-var" id="tweak-var-${stem}">
                <option value="low">Subtle</option>
                <option value="medium" selected>Medium</option>
                <option value="high">Wild</option>
            </select>
            <button class="btn btn-secondary stem-tweak-btn" onclick="tweakStem('${stem}')">Regenerate</button>
        </div>
    `).join('');

    // Load preview for instant waveform drawing
    loadAudioBuffer(bundleId, 'preview').then(buf => {
        stemBuffers['preview'] = buf;
        resizeCanvas(); // draw static wave
    });

    // Load individual stems in background
    stems.forEach(stem => loadAudioBuffer(bundleId, stem).then(buf => stemBuffers[stem] = buf));
}

async function loadAudioBuffer(bundleId, stem) {
    const res = await fetch(`${API_BASE}/bundles/${bundleId}/audio/${stem}?t=${Date.now()}`);
    const arrayBuffer = await res.arrayBuffer();
    return await audioCtx.decodeAudioData(arrayBuffer);
}

// Playback Control
function togglePlay() {
    if (!audioCtx) return;
    if (isPlaying) {
        pauseAudio();
    } else {
        playAudio();
    }
}

function playAudio() {
    if (isPlaying || !currentBundle) return;
    
    if (audioCtx.state === 'suspended') audioCtx.resume();
    
    // We play the individual stems if loaded, otherwise fallback to preview
    const stemsToPlay = Object.keys(stemBuffers).filter(k => k !== 'preview');
    const usePreview = stemsToPlay.length === 0;
    const tracks = usePreview ? ['preview'] : stemsToPlay;

    stemSources = {};
    stemGains = {};

    tracks.forEach(stem => {
        const source = audioCtx.createBufferSource();
        source.buffer = stemBuffers[stem];
        
        const gainNode = audioCtx.createGain();
        
        // Restore UI volume state if stem (preview is always full)
        if (stem !== 'preview') {
            const volInput = document.querySelector(`.stem-track[data-stem="${stem}"] .stem-vol`);
            const isMuted = document.querySelector(`.stem-track[data-stem="${stem}"] .mute-btn`).classList.contains('active');
            gainNode.gain.value = isMuted ? 0 : parseFloat(volInput.value);
            
            // Check solo state globally
            const anySolo = document.querySelectorAll('.solo-btn.active').length > 0;
            if (anySolo && !document.querySelector(`.stem-track[data-stem="${stem}"] .solo-btn`).classList.contains('active')) {
                gainNode.gain.value = 0;
            }
        }

        source.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        source.start(0, pauseTime);
        stemSources[stem] = source;
        stemGains[stem] = gainNode;
        
        // Loop handling
        source.loop = true; 
    });

    startTime = audioCtx.currentTime - pauseTime;
    isPlaying = true;
    els.btnPlay.innerText = '⏸';
    drawWaveformLoop();
}

function pauseAudio() {
    if (!isPlaying) return;
    
    Object.values(stemSources).forEach(source => source.stop());
    pauseTime = audioCtx.currentTime - startTime;
    isPlaying = false;
    els.btnPlay.innerText = '▶';
    cancelAnimationFrame(animationFrameId);
}

function stopAudio() {
    if (isPlaying) {
        Object.values(stemSources).forEach(source => source.stop());
        isPlaying = false;
    }
    pauseTime = 0;
    els.btnPlay.innerText = '▶';
    cancelAnimationFrame(animationFrameId);
    if (stemBuffers['preview']) drawStaticWaveform(stemBuffers['preview']);
}

// Mixer Controls
function setGain(stem, value) {
    if (stemGains[stem]) {
        // Only apply if not muted and not overridden by solo
        const isMuted = document.querySelector(`.stem-track[data-stem="${stem}"] .mute-btn`).classList.contains('active');
        const anySolo = document.querySelectorAll('.solo-btn.active').length > 0;
        const isThisSolo = document.querySelector(`.stem-track[data-stem="${stem}"] .solo-btn`).classList.contains('active');
        
        if (isMuted || (anySolo && !isThisSolo)) {
            stemGains[stem].gain.value = 0;
        } else {
            stemGains[stem].gain.setValueAtTime(value, audioCtx.currentTime);
        }
    }
}

function toggleMute(stem) {
    const btn = document.querySelector(`.stem-track[data-stem="${stem}"] .mute-btn`);
    btn.classList.toggle('active');
    
    // Auto-disable solo if muting
    if (btn.classList.contains('active')) {
        document.querySelector(`.stem-track[data-stem="${stem}"] .solo-btn`).classList.remove('active');
    }
    
    recalculateMixer();
}

function toggleSolo(stem) {
    const btn = document.querySelector(`.stem-track[data-stem="${stem}"] .solo-btn`);
    btn.classList.toggle('active');
    
    // Auto-disable mute if soloing
    if (btn.classList.contains('active')) {
        document.querySelector(`.stem-track[data-stem="${stem}"] .mute-btn`).classList.remove('active');
    }
    
    recalculateMixer();
}

function recalculateMixer() {
    if (!isPlaying) return;
    
    const anySolo = document.querySelectorAll('.solo-btn.active').length > 0;
    
    Object.keys(stemGains).forEach(stem => {
        if (stem === 'preview') return;
        
        const track = document.querySelector(`.stem-track[data-stem="${stem}"]`);
        const vol = parseFloat(track.querySelector('.stem-vol').value);
        const isMuted = track.querySelector('.mute-btn').classList.contains('active');
        const isSolo = track.querySelector('.solo-btn').classList.contains('active');
        
        if (isMuted || (anySolo && !isSolo)) {
            stemGains[stem].gain.setTargetAtTime(0, audioCtx.currentTime, 0.05);
        } else {
            stemGains[stem].gain.setTargetAtTime(vol, audioCtx.currentTime, 0.05);
        }
    });
}

// Waveform Visualization
function drawStaticWaveform(buffer) {
    const data = buffer.getChannelData(0);
    const step = Math.ceil(data.length / els.canvas.width);
    const amp = els.canvas.height / 2;
    
    ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
    ctx.fillStyle = '#555570'; // unplayed color
    
    for(let i=0; i < els.canvas.width; i++){
        let min = 1.0;
        let max = -1.0;
        for (let j=0; j<step; j++) {
            const datum = data[(i*step)+j]; 
            if (datum < min) min = datum;
            if (datum > max) max = datum;
        }
        ctx.fillRect(i, (1+min)*amp, 2, Math.max(2, (max-min)*amp));
    }
}

function drawWaveformLoop() {
    if (!isPlaying || !stemBuffers['preview']) return;
    
    const buf = stemBuffers['preview'];
    const elapsed = (audioCtx.currentTime - startTime) % buf.duration;
    const progress = elapsed / buf.duration;
    
    const data = buf.getChannelData(0);
    const step = Math.ceil(data.length / els.canvas.width);
    const amp = els.canvas.height / 2;
    const playheadX = els.canvas.width * progress;
    
    ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
    
    // Create gradient for played portion
    const grad = ctx.createLinearGradient(0, 0, els.canvas.width, 0);
    grad.addColorStop(0, '#00F0FF');
    grad.addColorStop(1, '#A855F7');

    for(let i=0; i < els.canvas.width; i++){
        let min = 1.0;
        let max = -1.0;
        for (let j=0; j<step; j++) {
            const datum = data[(i*step)+j]; 
            if (datum < min) min = datum;
            if (datum > max) max = datum;
        }
        
        ctx.fillStyle = (i < playheadX) ? grad : '#555570';
        ctx.fillRect(i, (1+min)*amp, 2, Math.max(2, (max-min)*amp));
    }
    
    animationFrameId = requestAnimationFrame(drawWaveformLoop);
}

// Feedback
async function submitFeedback(rating) {
    if (!currentBundle) return;
    
    try {
        await fetch(`${API_BASE}/bundles/${currentBundle}/rate`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({feedback: rating})
        });
        await fetchProfile(); // Update profile text
        alert('Feedback recorded!');
    } catch (e) {
        alert('Error saving feedback');
    }
}

// Export / Download
function downloadMix() {
    if (!currentBundle) return;
    window.location.href = `${API_BASE}/bundles/${currentBundle}/download/mix`;
}

function downloadStemsZip() {
    if (!currentBundle) return;
    window.location.href = `${API_BASE}/bundles/${currentBundle}/download/stems`;
}

function downloadStem(stem) {
    if (!currentBundle) return;
    window.location.href = `${API_BASE}/bundles/${currentBundle}/download/stem/${stem}`;
}

// Stem Tweaking
function toggleTweakRow(stem) {
    const row = document.getElementById(`tweak-row-${stem}`);
    row.style.display = row.style.display === 'none' ? 'flex' : 'none';
}

async function tweakStem(stem) {
    if (!currentBundle) return;
    
    const input = document.getElementById(`tweak-input-${stem}`);
    const varSelect = document.getElementById(`tweak-var-${stem}`);
    const promptHint = input.value.trim();
    const variation = varSelect.value;
    
    // Visual feedback
    const btn = input.parentElement.querySelector('.stem-tweak-btn');
    const originalText = btn.innerText;
    btn.innerText = '⏳ Working...';
    btn.disabled = true;
    
    try {
        const res = await fetch(`${API_BASE}/bundles/${currentBundle}/tweak-stem`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                stem: stem,
                prompt_hint: promptHint || null,
                variation: variation,
            })
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || 'Tweak failed');
        
        // Reload only the tweaked stem audio
        const buf = await loadAudioBuffer(currentBundle, stem);
        stemBuffers[stem] = buf;
        
        // Also reload the preview mix
        const previewBuf = await loadAudioBuffer(currentBundle, 'preview');
        stemBuffers['preview'] = previewBuf;
        resizeCanvas();
        
        btn.innerText = '✅ Done!';
        setTimeout(() => { btn.innerText = originalText; }, 2000);
    } catch (err) {
        btn.innerText = '❌ Error';
        setTimeout(() => { btn.innerText = originalText; }, 2000);
        console.error('Tweak error:', err);
    } finally {
        btn.disabled = false;
    }
}

async function fetchHubRecommendations() {
    try {
        const res = await fetch(`${API_BASE}/hub/recommendations`);
        const data = await res.json();
        
        els.hubRecs.innerHTML = data.recommendations.map(r => 
            `<div class="chip" style="background: var(--surface); color: var(--text-light); font-size: 11px;" data-id="${r.id}">${r.name}</div>`
        ).join('');

        els.hubRecs.querySelectorAll('.chip').forEach(chip => {
            chip.addEventListener('click', () => {
                els.hubRepoId.value = chip.dataset.id;
            });
        });
    } catch (e) {
        console.error('Error fetching recommendations', e);
    }
}

async function handleHubDownload() {
    let repoId = els.hubRepoId.value.trim();
    if (!repoId) return;

    // Sanitize URL if pasted
    if (repoId.includes('huggingface.co/')) {
        repoId = repoId.split('huggingface.co/')[1].replace('datasets/', '');
    }

    els.hubStatus.style.display = 'block';
    els.hubStatus.innerText = 'Connecting to Hugging Face Hub...';
    els.btnHubDownload.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/hub/download`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ repo_id: repoId })
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || 'Download failed');
        
        els.hubStatus.innerText = 'Success! Model saved to your local models/ folder.';
        setTimeout(() => { els.hubStatus.style.display = 'none'; }, 5000);
    } catch (err) {
        els.hubStatus.innerText = 'Error: ' + err.message;
    } finally {
        els.btnHubDownload.disabled = false;
    }
}

// Start
document.addEventListener('DOMContentLoaded', init);
