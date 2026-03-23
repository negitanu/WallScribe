/**
 * ツールチップ管理 - 表の外にも表示されるようにする
 */

(function() {
    'use strict';

    let tooltipElement = null;
    let tooltipArrow = null;
    let currentTarget = null;

    /**
     * ツールチップ要素を作成
     */
    function createTooltip() {
        if (tooltipElement) {
            return;
        }

        tooltipElement = document.createElement('div');
        tooltipElement.className = 'dynamic-tooltip';
        tooltipElement.style.cssText = `
            position: fixed;
            padding: 12px 16px;
            background: #212529;
            color: #fff;
            font-size: 0.9rem;
            font-weight: normal;
            line-height: 1.6;
            border-radius: 8px;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease, visibility 0.3s ease;
            z-index: 100000;
            max-width: min(500px, calc(100vw - 40px));
            min-width: 250px;
            white-space: normal;
            word-wrap: break-word;
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3);
            pointer-events: none;
            text-align: left;
            overflow-wrap: break-word;
            word-break: keep-all;
        `;

        tooltipArrow = document.createElement('div');
        tooltipArrow.className = 'dynamic-tooltip-arrow';
        tooltipArrow.style.cssText = `
            position: fixed;
            width: 0;
            height: 0;
            border: 8px solid transparent;
            border-top-color: #212529;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease, visibility 0.3s ease;
            z-index: 100001;
            pointer-events: none;
        `;

        document.body.appendChild(tooltipElement);
        document.body.appendChild(tooltipArrow);
    }

    /**
     * ツールチップの位置を計算
     */
    function calculatePosition(target, tooltipElement) {
        const rect = target.getBoundingClientRect();
        const spacing = 8;
        const arrowSize = 8;
        const margin = 20;

        // ツールチップの実際のサイズを取得
        const tooltipWidth = tooltipElement.offsetWidth;
        const tooltipHeight = tooltipElement.offsetHeight;

        // 中央配置を試みる
        let left = rect.left + (rect.width / 2) - (tooltipWidth / 2);
        let top = rect.top - tooltipHeight - spacing - arrowSize;
        let arrowLeft = rect.left + (rect.width / 2) - arrowSize;

        // 画面左端からはみ出さないように
        if (left < margin) {
            left = margin;
            arrowLeft = Math.max(margin, Math.min(rect.left + (rect.width / 2) - arrowSize, left + tooltipWidth - arrowSize * 2));
        }

        // 画面右端からはみ出さないように
        const maxLeft = window.innerWidth - tooltipWidth - margin;
        if (left > maxLeft) {
            left = maxLeft;
            arrowLeft = Math.max(left, Math.min(rect.left + (rect.width / 2) - arrowSize, left + tooltipWidth - arrowSize * 2));
        }

        // 画面上端からはみ出す場合は下に表示
        let showBelow = false;
        if (top < margin) {
            top = rect.bottom + spacing + arrowSize;
            showBelow = true;
        }

        return {
            left: left,
            top: top,
            arrowLeft: arrowLeft,
            showBelow: showBelow
        };
    }

    /**
     * ツールチップを表示
     */
    function showTooltip(target, tooltipText) {
        if (!tooltipText || !target) {
            return;
        }

        createTooltip();
        currentTarget = target;

        // data-tooltip にはサーバー側（HTMLExporter）で生成・エスケープ済みの
        // ツールチップ用HTML（テーブル等）が入る想定。
        // textContent だとタグがそのまま表示されるため、innerHTMLで描画する。
        // 注意: ユーザー入力を直接含めないこと（XSSリスク）
        tooltipElement.innerHTML = tooltipText;
        
        // 一時的に表示してサイズを取得
        tooltipElement.style.visibility = 'hidden';
        tooltipElement.style.opacity = '0';
        tooltipElement.style.display = 'block';
        tooltipElement.style.left = '-9999px';
        tooltipElement.style.top = '-9999px';
        
        const pos = calculatePosition(target, tooltipElement);

        tooltipElement.style.left = pos.left + 'px';
        tooltipElement.style.top = pos.top + 'px';
        tooltipArrow.style.left = pos.arrowLeft + 'px';

        // 矢印の位置を設定
        const arrowSize = 8;
        if (pos.showBelow) {
            tooltipArrow.style.borderTopColor = 'transparent';
            tooltipArrow.style.borderBottomColor = '#212529';
            tooltipArrow.style.top = (pos.top - arrowSize - 1) + 'px';
        } else {
            tooltipArrow.style.borderTopColor = '#212529';
            tooltipArrow.style.borderBottomColor = 'transparent';
            tooltipArrow.style.top = (pos.top + tooltipElement.offsetHeight) + 'px';
        }

        tooltipElement.style.visibility = 'visible';
        tooltipElement.style.opacity = '1';
        tooltipArrow.style.visibility = 'visible';
        tooltipArrow.style.opacity = '1';
    }

    /**
     * ツールチップを非表示
     */
    function hideTooltip() {
        if (tooltipElement) {
            tooltipElement.style.opacity = '0';
            tooltipElement.style.visibility = 'hidden';
        }
        if (tooltipArrow) {
            tooltipArrow.style.opacity = '0';
            tooltipArrow.style.visibility = 'hidden';
        }
        currentTarget = null;
    }

    /**
     * イベントリスナーを設定
     */
    function initTooltips() {
        // 既存のCSSツールチップを無効化
        const style = document.createElement('style');
        style.textContent = `
            .has-tooltip::after,
            .has-tooltip::before {
                display: none !important;
            }
        `;
        document.head.appendChild(style);

        // マウスイベントを監視
        document.addEventListener('mouseenter', function(e) {
            const target = e.target.closest('.has-tooltip');
            if (target && target.dataset.tooltip) {
                showTooltip(target, target.dataset.tooltip);
            }
        }, true);

        document.addEventListener('mouseleave', function(e) {
            const target = e.target.closest('.has-tooltip');
            if (target) {
                hideTooltip();
            }
        }, true);

        // スクロール時にツールチップを非表示
        document.addEventListener('scroll', hideTooltip, true);
    }

    // DOMContentLoaded時に初期化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTooltips);
    } else {
        initTooltips();
    }
})();
