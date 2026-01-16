/**
 * パラメータシート検索機能
 */

let currentSearchTerm = '';
let currentMatches = [];
let currentMatchIndex = -1;

function performSearch() {
    const searchInput = document.getElementById('searchInput');
    const searchTerm = searchInput.value.trim();
    const clearBtn = document.getElementById('clearBtn');
    const searchResults = document.getElementById('searchResults');

    // 前の検索結果をクリア
    clearSearch();

    if (!searchTerm) {
        return;
    }

    currentSearchTerm = searchTerm;
    const regex = new RegExp(searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const sections = document.querySelectorAll('section');
    let totalMatches = 0;
    const matchedSections = [];

    sections.forEach(section => {
        const sectionText = section.textContent || section.innerText;
        const matches = sectionText.match(regex);
        if (matches) {
            totalMatches += matches.length;
            matchedSections.push(section);

            // セクションをハイライト
            section.classList.add('search-result-section');

            // セクション内のテキストをハイライト
            highlightText(section, regex);
        }
    });

    if (totalMatches > 0) {
        searchResults.textContent = `${totalMatches}件見つかりました`;
        clearBtn.style.display = 'inline-block';
        currentMatches = matchedSections;

        // 最初のマッチにスクロール
        if (matchedSections.length > 0) {
            matchedSections[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    } else {
        searchResults.textContent = '見つかりませんでした';
    }
}

function highlightText(element, regex) {
    // 既にハイライトされている場合はスキップ
    if (element.classList.contains('search-highlighted')) {
        return;
    }

    const walker = document.createTreeWalker(
        element,
        NodeFilter.SHOW_TEXT,
        {
            acceptNode: function(node) {
                // script, styleタグ内は除外
                const parent = node.parentElement;
                if (parent && (parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE')) {
                    return NodeFilter.FILTER_REJECT;
                }
                // 既にハイライトされた要素内は除外
                if (parent && parent.classList.contains('search-highlight')) {
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            }
        },
        false
    );

    const textNodes = [];
    let node;
    while (node = walker.nextNode()) {
        textNodes.push(node);
    }

    textNodes.forEach(textNode => {
        const text = textNode.textContent;
        if (regex.test(text)) {
            const highlightedText = text.replace(regex, '<span class="search-highlight">$&</span>');
            const span = document.createElement('span');
            span.innerHTML = highlightedText;
            textNode.parentNode.replaceChild(span, textNode);
        }
    });

    element.classList.add('search-highlighted');
}

function clearSearch() {
    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearBtn');
    const searchResults = document.getElementById('searchResults');

    // ハイライトを削除（元のテキストに戻す）
    const highlights = document.querySelectorAll('.search-highlight');
    highlights.forEach(el => {
        const parent = el.parentNode;
        if (parent) {
            const textNode = document.createTextNode(el.textContent);
            parent.replaceChild(textNode, el);
        }
    });

    // セクションのハイライトを削除
    document.querySelectorAll('.search-result-section').forEach(section => {
        section.classList.remove('search-result-section');
        section.classList.remove('search-highlighted');
    });

    // DOMを正規化（隣接するテキストノードを結合）
    document.querySelectorAll('section').forEach(section => {
        section.normalize();
    });

    searchInput.value = '';
    searchResults.textContent = '';
    clearBtn.style.display = 'none';
    currentSearchTerm = '';
    currentMatches = [];
    currentMatchIndex = -1;
}

// イベントリスナー設定
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        // Enterキーで検索
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performSearch();
            }
        });

        // Escapeキーでクリア
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                clearSearch();
                searchInput.blur();
            }
        });
    }
});
