/**
 * パラメータシート生成ツール - メインJavaScript
 * Bootstrap 5 + Dark Theme Version
 */

document.addEventListener('DOMContentLoaded', function() {
    // 要素の取得
    const uploadForm = document.getElementById('uploadForm');
    const dropZone = document.getElementById('dropZone');
    const dropZoneContent = document.getElementById('dropZoneContent');
    const fileInput = document.getElementById('fileInput');
    const selectedFiles = document.getElementById('selectedFiles');
    const filesList = document.getElementById('filesList');
    const clearFiles = document.getElementById('clearFiles');
    const haOptions = document.getElementById('haOptions');
    const submitBtn = document.getElementById('submitBtn');
    const uploadSection = document.getElementById('uploadSection');
    const progressSection = document.getElementById('progressSection');
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');
    const errorDetails = document.getElementById('errorDetails');
    const retryBtn = document.getElementById('retryBtn');
    const progressSubtext = document.getElementById('progressSubtext');
    const progressBarFill = document.getElementById('progressBarFill');
    const progressPercent = document.getElementById('progressPercent');
    const sectionsGrid = document.getElementById('sectionsGrid');

    let currentFiles = [];
    let progressPollTimer = null;

    // プリセット定義
    const presets = {
        normal: ['device_info', 'system_settings', 'network', 'policies', 'nat'],
        detailed: ['device_info', 'system_settings', 'network', 'objects', 'policies', 'nat', 'vpn', 'security_profiles', 'ha', 'logging']
    };

    // プリセット選択の処理
    const presetRadios = document.querySelectorAll('input[name="output_preset"]');
    const sectionCheckboxes = document.querySelectorAll('input[name="sections"]');

    function applyPresetFromCurrentSelection() {
        const current = document.querySelector('input[name="output_preset"]:checked');
        if (!current) return;
        const preset = current.value;

        if (preset === 'custom') {
            // カスタムの場合はグリッドを有効化
            sectionsGrid.classList.remove('disabled');
            return;
        }

        // プリセット選択時はグリッドを無効化
        sectionsGrid.classList.add('disabled');

        // チェックボックスをプリセットに合わせて設定
        const selectedSections = presets[preset] || [];
        sectionCheckboxes.forEach(checkbox => {
            checkbox.checked = selectedSections.includes(checkbox.value);
        });
    }

    presetRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            applyPresetFromCurrentSelection();
        });
    });

    // チェックボックス変更時にカスタムに切り替え
    sectionCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const customRadio = document.querySelector('input[name="output_preset"][value="custom"]');
            if (!customRadio.checked) {
                customRadio.checked = true;
                sectionsGrid.classList.remove('disabled');
            }
        });
    });

    // 初期状態：現在選択されているプリセットを適用
    applyPresetFromCurrentSelection();

    // ドラッグ＆ドロップイベント
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drag-over');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drag-over');
        }, false);
    });

    dropZone.addEventListener('drop', function(e) {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFiles(Array.from(files));
        }
    });

    // ファイル選択
    fileInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            handleFiles(Array.from(e.target.files));
        }
    });

    // ファイル処理（複数対応）
    function handleFiles(files) {
        const validExtensions = ['.conf', '.xml'];
        const validFiles = files.filter(file => {
            const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
            return validExtensions.includes(ext);
        });

        if (validFiles.length === 0) {
            showError('サポートされていないファイル形式です', '対応形式: .conf (FortiGate), .xml (Palo Alto)');
            return;
        }

        // 既存のファイルに追加
        currentFiles = [...currentFiles, ...validFiles];
        updateFilesList();
    }

    // ファイル一覧を更新
    function updateFilesList() {
        if (currentFiles.length === 0) {
            selectedFiles.style.display = 'none';
            dropZoneContent.style.display = 'block';
            haOptions.style.display = 'none';
            submitBtn.disabled = true;
            return;
        }

        filesList.innerHTML = '';
        currentFiles.forEach((file, index) => {
            const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
            const iconClass = ext === '.conf' ? 'text-info' : 'text-warning';

            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.innerHTML = `
                <i class="bi bi-file-earmark-code file-icon ${iconClass}"></i>
                <span class="file-name">${escapeHtml(file.name)}</span>
                <button type="button" class="remove-btn" data-index="${index}" aria-label="削除">
                    <i class="bi bi-x-lg"></i>
                </button>
            `;
            filesList.appendChild(fileItem);
        });

        // 削除ボタンのイベント
        filesList.querySelectorAll('.remove-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const idx = parseInt(this.dataset.index);
                currentFiles.splice(idx, 1);
                updateFilesList();
            });
        });

        selectedFiles.style.display = 'block';
        dropZoneContent.style.display = 'none';
        submitBtn.disabled = false;

        // HAオプションの表示（2ファイル以上選択時）
        if (currentFiles.length >= 2) {
            haOptions.style.display = 'block';
        } else {
            haOptions.style.display = 'none';
        }
    }

    // HTMLエスケープ
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // すべてのファイルを削除
    clearFiles.addEventListener('click', function() {
        resetFileSelection();
    });

    function resetFileSelection() {
        currentFiles = [];
        fileInput.value = '';
        filesList.innerHTML = '';
        selectedFiles.style.display = 'none';
        dropZoneContent.style.display = 'block';
        haOptions.style.display = 'none';
        submitBtn.disabled = true;
    }

    // 選択されたセクションを取得
    function getSelectedSections() {
        const preset = document.querySelector('input[name="output_preset"]:checked').value;

        if (preset !== 'custom') {
            return presets[preset] || presets.normal;
        }

        // カスタムの場合はチェックされたものを取得
        const selected = [];
        sectionCheckboxes.forEach(checkbox => {
            if (checkbox.checked) {
                selected.push(checkbox.value);
            }
        });
        return selected;
    }

    // フォーム送信
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        if (currentFiles.length === 0) {
            showError('ファイルが選択されていません');
            return;
        }

        const selectedSections = getSelectedSections();
        if (selectedSections.length === 0) {
            showError('出力する項目を1つ以上選択してください');
            return;
        }

        // UI状態変更
        showProgress();

        const formData = new FormData();

        // 複数ファイルを追加
        currentFiles.forEach(file => {
            formData.append('config_files[]', file);
        });

        formData.append('output_format', document.querySelector('input[name="output_format"]:checked').value);
        formData.append('sections', JSON.stringify(selectedSections));

        // HAモードを追加（2ファイル以上の場合）
        if (currentFiles.length >= 2) {
            const haMode = document.querySelector('input[name="ha_mode"]:checked');
            formData.append('ha_mode', haMode ? haMode.value : 'auto');
        }

        try {
            updateProgress(5, 'アップロードしています...');

            // 非同期アップロード（進捗取得用）
            const response = await fetch('/upload_async', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                // 進捗をポーリングして更新
                await pollProgress(result.file_id);
            } else {
                showError(
                    result.error.message || 'エラーが発生しました',
                    result.error.details || ''
                );
            }
        } catch (error) {
            console.error('Error:', error);
            showError('通信エラーが発生しました', 'サーバーに接続できません。しばらく待ってから再試行してください。');
        }
    });

    // プログレス表示
    function showProgress() {
        uploadSection.style.display = 'none';
        progressSection.style.display = 'block';
        errorSection.style.display = 'none';
    }

    function updateProgressText(text) {
        progressSubtext.textContent = text;
    }

    function updateProgress(percent, text) {
        const p = Math.max(0, Math.min(100, Number(percent) || 0));
        if (progressBarFill) {
            progressBarFill.style.width = p + '%';
            progressBarFill.setAttribute('aria-valuenow', String(Math.round(p)));
        }
        if (progressPercent) progressPercent.textContent = Math.round(p) + '%';
        if (text) updateProgressText(text);
    }

    async function pollProgress(fileId) {
        // 念のため既存タイマーを停止
        if (progressPollTimer) {
            clearTimeout(progressPollTimer);
            progressPollTimer = null;
        }

        const pollOnce = async () => {
            const res = await fetch('/api/progress/' + fileId, { cache: 'no-store' });
            const data = await res.json();

            if (!data.success) {
                showError(data.error?.message || '進捗取得に失敗しました', data.error?.details || '');
                return;
            }

            const percent = data.progress?.percent ?? 0;
            const message = data.progress?.message ?? '';
            updateProgress(percent, message);

            if (data.status === 'done') {
                updateProgress(100, 'パラメータシートを生成しました');
                window.location.href = '/result/' + fileId;
                return;
            }

            if (data.status === 'error') {
                const err = data.error || {};
                showError(err.message || 'エラーが発生しました', err.details || '');
                return;
            }

            // 継続（1秒ごと）
            progressPollTimer = setTimeout(pollOnce, 1000);
        };

        await pollOnce();
    }

    // エラー表示
    function showError(message, details = '') {
        uploadSection.style.display = 'none';
        progressSection.style.display = 'none';
        errorSection.style.display = 'block';
        errorMessage.textContent = message;
        errorDetails.textContent = details;
        if (progressPollTimer) {
            clearTimeout(progressPollTimer);
            progressPollTimer = null;
        }
    }

    // リトライ
    retryBtn.addEventListener('click', function() {
        resetFileSelection();
        uploadSection.style.display = 'block';
        progressSection.style.display = 'none';
        errorSection.style.display = 'none';
        updateProgress(0, '設定ファイルを解析しています');
    });

    // ドロップゾーンのクリックでファイル選択
    // label要素内のクリックは除外（labelが自動的にinputをトリガーするため）
    dropZone.addEventListener('click', function(e) {
        // label要素やその子要素のクリックは無視
        if (e.target.closest('label')) {
            return;
        }
        // button要素のクリックは無視
        if (e.target.closest('button')) {
            return;
        }
        // ドロップゾーンコンテンツのクリック時のみファイル選択を開く
        if (e.target === dropZone || e.target.closest('#dropZoneContent')) {
            fileInput.click();
        }
    });
});
