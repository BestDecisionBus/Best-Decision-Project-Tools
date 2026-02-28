// Searchable select widget
// Usage: ss_setOptions(id, [{value, label}, ...], placeholder)
//        ss_toggle(id)   — called by onclick on .ss-display
//        ss_filter(id, query) — called by oninput on .ss-search
//        ss_select(id, value, label) — called by clicking an option
//        ss_reset(id)    — resets display to placeholder

var SS_DATA = {};

function ss_setOptions(id, options, placeholder) {
    SS_DATA[id] = { options: options, placeholder: placeholder };
    var container = document.getElementById(id + '-options');
    if (!container) return;
    while (container.firstChild) { container.removeChild(container.firstChild); }
    var noneEl = document.createElement('div');
    noneEl.className = 'ss-option';
    noneEl.dataset.value = '';
    noneEl.textContent = placeholder;
    noneEl.onclick = function() { ss_select(id, '', placeholder); };
    container.appendChild(noneEl);
    options.forEach(function(opt) {
        var el = document.createElement('div');
        el.className = 'ss-option';
        el.dataset.value = String(opt.value);
        el.textContent = opt.label;
        el.onclick = function() { ss_select(id, opt.value, opt.label); };
        container.appendChild(el);
    });
}

function ss_toggle(id) {
    var dropdown = document.getElementById(id + '-dropdown');
    var display = document.getElementById(id + '-display');
    var isOpen = dropdown.style.display !== 'none';
    document.querySelectorAll('.ss-dropdown').forEach(function(d) { d.style.display = 'none'; });
    document.querySelectorAll('.ss-display').forEach(function(d) { d.classList.remove('open'); });
    if (!isOpen) {
        dropdown.style.display = '';
        display.classList.add('open');
        var inp = dropdown.querySelector('.ss-search');
        if (inp) { inp.value = ''; ss_filter(id, ''); inp.focus(); }
    }
}

function ss_filter(id, query) {
    var q = query.toLowerCase().trim();
    var container = document.getElementById(id + '-options');
    var noRes = container.querySelector('.ss-no-results');
    var visible = 0;
    container.querySelectorAll('.ss-option').forEach(function(opt) {
        var match = q === '' || opt.textContent.toLowerCase().indexOf(q) !== -1;
        opt.classList.toggle('hidden', !match);
        if (match) visible++;
    });
    if (visible === 0) {
        if (!noRes) {
            noRes = document.createElement('div');
            noRes.className = 'ss-no-results';
            noRes.textContent = 'No results found';
            container.appendChild(noRes);
        }
        noRes.style.display = '';
    } else if (noRes) {
        noRes.style.display = 'none';
    }
}

function ss_select(id, value, label) {
    document.getElementById(id).value = value;
    document.getElementById(id + '-text').textContent = label;
    document.getElementById(id + '-dropdown').style.display = 'none';
    document.getElementById(id + '-display').classList.remove('open');
}

function ss_reset(id) {
    document.getElementById(id).value = '';
    document.getElementById(id + '-text').textContent = (SS_DATA[id] || {}).placeholder || '-- Select --';
}

// Close dropdowns when clicking outside any ss-container
document.addEventListener('click', function(e) {
    if (!e.target.closest('.ss-container')) {
        document.querySelectorAll('.ss-dropdown').forEach(function(d) { d.style.display = 'none'; });
        document.querySelectorAll('.ss-display').forEach(function(d) { d.classList.remove('open'); });
    }
});
