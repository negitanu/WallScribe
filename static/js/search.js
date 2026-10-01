/** Literal, DOM-safe document search with individual result navigation. */
let currentSearchTerm = '';
let currentMatches = [];
let currentMatchIndex = -1;

function resetSearchHighlights() {
    document.querySelectorAll('mark.search-highlight').forEach(mark => {
        mark.replaceWith(document.createTextNode(mark.textContent));
    });
    document.querySelectorAll('.search-result-section').forEach(section => {
        section.classList.remove('search-result-section');
        section.normalize();
    });
    currentMatches = [];
    currentMatchIndex = -1;
    document.getElementById('searchNavigation').hidden = true;
}

function moveSearchMatch(direction) {
    if (!currentMatches.length) return;
    if (currentMatchIndex >= 0) currentMatches[currentMatchIndex].classList.remove('search-current');
    currentMatchIndex = (currentMatchIndex + direction + currentMatches.length) % currentMatches.length;
    const match = currentMatches[currentMatchIndex];
    match.classList.add('search-current');
    // Open collapsed evidence before scrolling to its result.
    for (let parent = match.parentElement; parent; parent = parent.parentElement) {
        if (parent.tagName === 'DETAILS') parent.open = true;
    }
    match.scrollIntoView({behavior: 'instant', block: 'center', inline: 'center'});
    document.getElementById('searchResults').textContent =
        `${currentMatchIndex + 1} / ${currentMatches.length} 件`;
}

function performSearch() {
    const input = document.getElementById('searchInput');
    const term = input.value.trim();
    if (term && term === currentSearchTerm && currentMatches.length) {
        moveSearchMatch(1);
        return;
    }
    resetSearchHighlights();
    currentSearchTerm = term;
    document.getElementById('clearBtn').style.display = term ? 'inline-block' : 'none';
    document.getElementById('searchResults').textContent = '';
    if (!term) return;
    const regex = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const root = document.getElementById('document-content');
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
            if (!node.textContent.trim() || node.parentElement.closest(
                'script, style, textarea, input, select, button, svg, [hidden], [aria-hidden="true"]'
            )) return NodeFilter.FILTER_REJECT;
            return NodeFilter.FILTER_ACCEPT;
        }
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
        const text = node.textContent;
        const fragment = document.createDocumentFragment();
        let end = 0;
        regex.lastIndex = 0;
        for (const match of text.matchAll(regex)) {
            fragment.append(document.createTextNode(text.slice(end, match.index)));
            const mark = document.createElement('mark');
            mark.className = 'search-highlight';
            mark.textContent = match[0];
            fragment.append(mark);
            currentMatches.push(mark);
            end = match.index + match[0].length;
        }
        if (!end) return;
        fragment.append(document.createTextNode(text.slice(end)));
        node.parentElement.closest('section')?.classList.add('search-result-section');
        node.replaceWith(fragment);
    });
    if (currentMatches.length) {
        document.getElementById('searchNavigation').hidden = false;
        moveSearchMatch(1);
    } else {
        document.getElementById('searchResults').textContent = '見つかりませんでした';
    }
}

function clearSearch() {
    resetSearchHighlights();
    document.getElementById('searchInput').value = '';
    document.getElementById('searchResults').textContent = '';
    document.getElementById('clearBtn').style.display = 'none';
    currentSearchTerm = '';
}

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('searchInput');
    if (!input) return;
    input.addEventListener('input', () => {
        if (!input.value && currentSearchTerm) clearSearch();
    });
    input.addEventListener('keydown', event => {
        if (event.isComposing) return;
        if (event.key === 'Enter') {
            event.preventDefault();
            if (event.shiftKey && input.value.trim() === currentSearchTerm && currentMatches.length) {
                moveSearchMatch(-1);
            } else performSearch();
        } else if (event.key === 'Escape') {
            clearSearch();
        }
    });
    document.addEventListener('keydown', event => {
        if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey &&
            !event.target.closest('input, textarea, select, button, [contenteditable]')) {
            event.preventDefault();
            input.focus();
            input.select();
        }
    });
});
