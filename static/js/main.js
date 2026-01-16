/**
 * パラメータシート生成ツール - メインJavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // 要素の取得
    const uploadForm = document.getElementById('uploadForm');
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const selectedFile = document.getElementById('selectedFile');
    const fileName = document.getElementById('fileName');
    const removeFile = document.getElementById('removeFile');
    const submitBtn = document.getElementById('submitBtn');
    const progressSection = document.getElementById('progressSection');
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');
    const errorDetails = document.getElementById('errorDetails');
    const retryBtn = document.getElementById('retryBtn');
    const progressSubtext = document.getElementById('progressSubtext');
    const sectionsGrid = document.getElementById('sectionsGrid');

    let currentFile = null;

    // プリセット定義
    const presets = {
        normal: ['device_info', 'system_settings', 'network', 'policies', 'nat'],
        detailed: ['device_info', 'system_settings', 'network', 'objects', 'policies', 'nat', 'vpn', 'security_profiles', 'ha', 'logging']
    };

    // プリセット選択の処理
    const presetRadios = document.querySelectorAll('input[name="output_preset"]');
    const sectionCheckboxes = document.querySelectorAll('input[name="sections"]');

    presetRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const preset = this.value;

            if (preset === 'custom') {
                // カスタムの場合はグリッドを有効化
                sectionsGrid.classList.remove('disabled');
            } else {
                // プリセット選択時はグリッドを無効化
                sectionsGrid.classList.add('disabled');

                // チェックボックスをプリセットに合わせて設定
                const selectedSections = presets[preset] || [];
                sectionCheckboxes.forEach(checkbox => {
                    checkbox.checked = selectedSections.includes(checkbox.value);
                });
            }
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

    // 初期状態：通常プリセットでグリッドを無効化
    sectionsGrid.classList.add('disabled');

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
            handleFile(files[0]);
        }
    });

    // ファイル選択
    fileInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // ファイル処理
    function handleFile(file) {
        const validExtensions = ['.conf', '.xml'];
        const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

        if (!validExtensions.includes(ext)) {
            showError('サポートされていないファイル形式です', '対応形式: .conf (FortiGate), .xml (Palo Alto)');
            return;
        }

        currentFile = file;
        fileName.textContent = file.name;
        selectedFile.style.display = 'flex';
        document.querySelector('.drop-zone-content').style.display = 'none';
        submitBtn.disabled = false;
    }

    // ファイル削除
    removeFile.addEventListener('click', function() {
        resetFileSelection();
    });

    function resetFileSelection() {
        currentFile = null;
        fileInput.value = '';
        fileName.textContent = '';
        selectedFile.style.display = 'none';
        document.querySelector('.drop-zone-content').style.display = 'flex';
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

        if (!currentFile) {
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
        formData.append('config_file', currentFile);
        formData.append('output_format', document.querySelector('input[name="output_format"]:checked').value);
        formData.append('sections', JSON.stringify(selectedSections));

        try {
            updateProgressText('設定ファイルを解析しています...');

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                updateProgressText('パラメータシートを生成しました');
                // 結果ページへリダイレクト
                window.location.href = '/result/' + result.file_id;
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
        document.querySelector('.upload-section').style.display = 'none';
        progressSection.style.display = 'block';
        errorSection.style.display = 'none';
    }

    function updateProgressText(text) {
        progressSubtext.textContent = text;
    }

    // エラー表示
    function showError(message, details = '') {
        document.querySelector('.upload-section').style.display = 'none';
        progressSection.style.display = 'none';
        errorSection.style.display = 'block';
        errorMessage.textContent = message;
        errorDetails.textContent = details;
    }

    // リトライ
    retryBtn.addEventListener('click', function() {
        resetFileSelection();
        document.querySelector('.upload-section').style.display = 'block';
        progressSection.style.display = 'none';
        errorSection.style.display = 'none';
    });

    // ドロップゾーンのクリックでファイル選択
    // label要素内のクリックは除外（labelが自動的にinputをトリガーするため）
    dropZone.addEventListener('click', function(e) {
        // label要素やその子要素のクリックは無視
        if (e.target.closest('label')) {
            return;
        }
        // ドロップゾーンコンテンツのクリック時のみファイル選択を開く
        if (e.target === dropZone || e.target.closest('.drop-zone-content')) {
            fileInput.click();
        }
    });
});
