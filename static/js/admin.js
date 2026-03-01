// Admin dashboard JS — merged from timekeeper + receipt-capture
(function () {
    "use strict";

    // ---- Copy URL to clipboard ----
    window.copyUrl = function (elementId, btn) {
        var text = document.getElementById(elementId).textContent.trim();
        navigator.clipboard.writeText(text).then(function () {
            var orig = btn.textContent;
            btn.textContent = "Copied!";
            setTimeout(function () { btn.textContent = orig; }, 1500);
        });
    };

    // ---- Copy credentials (username + password + login URL) ----
    window.copyCredentials = function (username, password, loginUrl, btn) {
        var text = "Login URL: " + loginUrl + "\nUsername: " + username + "\nPassword: " + password;
        navigator.clipboard.writeText(text).then(function () {
            var orig = btn.textContent;
            btn.textContent = "Copied!";
            setTimeout(function () { btn.textContent = orig; }, 1500);
        });
    };

    // ---- Inline save buttons (employees, jobs, categories) ----
    document.querySelectorAll(".save-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var row = btn.closest("tr");
            var url = btn.getAttribute("data-url");
            var contentType = btn.getAttribute("data-content-type") || "application/x-www-form-urlencoded";

            if (contentType === "application/json") {
                // JSON mode (used by categories)
                var payload = {};
                row.querySelectorAll("input[data-field], select[data-field]").forEach(function (input) {
                    payload[input.getAttribute("data-field")] = input.value.trim();
                });

                fetch(url, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: JSON.stringify(payload),
                })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        btn.textContent = "Saved!";
                        btn.style.background = "#16a34a";
                        if (window._markClean) window._markClean();
                        setTimeout(function () {
                            btn.textContent = "Save";
                            btn.style.background = "";
                        }, 1500);
                    } else {
                        alert(data.error || "Save failed.");
                    }
                })
                .catch(function () {
                    alert("Save failed. Please try again.");
                });
            } else {
                // Form-encoded mode (used by employees, jobs)
                var formData = new URLSearchParams();
                row.querySelectorAll("input[data-field], select[data-field]").forEach(function (input) {
                    formData.append(input.getAttribute("data-field"), input.value.trim());
                });

                fetch(url, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: formData.toString(),
                })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        btn.textContent = "Saved!";
                        btn.style.background = "#16a34a";
                        if (window._markClean) window._markClean();
                        setTimeout(function () {
                            btn.textContent = "Save";
                            btn.style.background = "";
                        }, 1500);
                    }
                })
                .catch(function () {
                    alert("Save failed. Please try again.");
                });
            }
        });
    });

    // ---- Inline notes save (time entry detail) ----
    var notesSaveBtn = document.getElementById("save-notes-btn");
    if (notesSaveBtn) {
        notesSaveBtn.addEventListener("click", function () {
            var notes = document.getElementById("admin-notes").value.trim();
            var url = notesSaveBtn.getAttribute("data-url");

            fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: "admin_notes=" + encodeURIComponent(notes),
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    notesSaveBtn.textContent = "Saved!";
                    notesSaveBtn.style.background = "#16a34a";
                    if (window._markClean) window._markClean();
                    setTimeout(function () {
                        notesSaveBtn.textContent = "Save Notes";
                        notesSaveBtn.style.background = "";
                    }, 1500);
                }
            })
            .catch(function () {
                alert("Save failed.");
            });
        });
    }

    // ---- Geocode button ----
    var geocodeBtn = document.getElementById("geocode-btn");
    if (geocodeBtn) {
        geocodeBtn.addEventListener("click", function () {
            var address = document.getElementById("job_address").value.trim();
            if (!address) { alert("Enter an address first."); return; }

            geocodeBtn.textContent = "Geocoding...";
            geocodeBtn.disabled = true;

            fetch("/api/geocode?address=" + encodeURIComponent(address))
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.lat) {
                        document.getElementById("latitude").value = data.lat;
                        document.getElementById("longitude").value = data.lng;
                        geocodeBtn.textContent = "Found!";
                    } else {
                        geocodeBtn.textContent = "Not Found";
                    }
                    setTimeout(function () {
                        geocodeBtn.textContent = "Geocode";
                        geocodeBtn.disabled = false;
                    }, 2000);
                })
                .catch(function () {
                    geocodeBtn.textContent = "Error";
                    setTimeout(function () {
                        geocodeBtn.textContent = "Geocode";
                        geocodeBtn.disabled = false;
                    }, 2000);
                });
        });
    }

    // ---- Token selector auto-redirect ----
    document.querySelectorAll(".token-select").forEach(function (sel) {
        sel.setAttribute("data-no-guard", "");
        sel.addEventListener("change", function () {
            window._guardBypass = true;
            var url = new URL(window.location.href);
            url.searchParams.set("token", sel.value);
            window.location.href = url.toString();
        });
    });

    // ---- Toggle edit forms ----
    window.toggleEdit = function (id) {
        var el = document.getElementById("edit-" + id);
        if (el) {
            el.style.display = el.style.display === "none" ? "block" : "none";
        }
    };

    // ---- Toggle company users section ----
    window.toggleUsers = function (tokenId) {
        var el = document.getElementById("users-" + tokenId);
        if (el) {
            el.style.display = el.style.display === "none" ? "block" : "none";
        }
    };

    // ---- Reload on bfcache ----
    window.addEventListener("pageshow", function (event) {
        if (event.persisted) window.location.reload();
    });

    // ---- Delete confirmation ----
    document.querySelectorAll(".confirm-delete").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            if (!confirm("Are you sure? This cannot be undone.")) {
                e.preventDefault();
            }
        });
    });

    // ---- Processed checkbox toggle (receipt) ----
    document.querySelectorAll(".processed-checkbox").forEach(function (cb) {
        cb.addEventListener("change", function () {
            var id = cb.dataset.id;
            var row = cb.closest("tr");
            fetch("/admin/receipts/" + id + "/toggle-processed", {
                method: "POST",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (row) {
                    if (data.processed) {
                        row.classList.add("row-processed");
                    } else {
                        row.classList.remove("row-processed");
                    }
                }
                // Update label text on detail page
                var label = cb.closest("label");
                if (label) {
                    var strong = label.querySelector("strong");
                    if (strong) strong.textContent = data.processed ? "Processed" : "Not Processed";
                }
            })
            .catch(function () {
                // Revert on error
                cb.checked = !cb.checked;
            });
        });
    });

    // ---- Delete submission AJAX (receipt) ----
    document.querySelectorAll(".delete-submission").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            e.preventDefault();
            if (!confirm("Delete this receipt? This cannot be undone.")) return;
            var id = btn.dataset.id;
            var row = btn.closest("tr");
            fetch("/admin/receipts/" + id + "/delete", {
                method: "POST",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success && row) {
                    row.remove();
                }
            })
            .catch(function () {
                alert("Failed to delete. Please try again.");
            });
        });
    });

    // ---- Copy URL buttons (token management) ----
    document.querySelectorAll(".copy-url").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var url = btn.dataset.url;
            navigator.clipboard.writeText(url).then(function () {
                var orig = btn.textContent;
                btn.textContent = "Copied!";
                setTimeout(function () { btn.textContent = orig; }, 1500);
            });
        });
    });

    // ---- Unsaved changes guard ----
    (function () {
        var layout = document.querySelector(".admin-layout");
        if (!layout) return;
        var modal = document.getElementById("unsaved-modal");
        if (!modal) return;

        var dirty = false;
        var pendingHref = null;

        // Exclude common filter elements from dirty tracking
        ["token-select", "search", "employee_id", "job_filter", "status_filter",
         "date_from", "date_to", "week-select"].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.setAttribute("data-no-guard", "");
        });

        function shouldTrack(el) {
            if (el.type === "hidden") return false;
            if (el.hasAttribute("data-no-guard")) return false;
            if (el.closest("[data-no-guard]")) return false;
            return true;
        }

        layout.addEventListener("input", function (e) {
            if (shouldTrack(e.target)) dirty = true;
        });
        layout.addEventListener("change", function (e) {
            if (shouldTrack(e.target)) dirty = true;
        });

        window._markClean = function () { dirty = false; };
        window._guardBypass = false;

        // Native browser dialog for refresh / close
        window.addEventListener("beforeunload", function (e) {
            if (dirty && !window._guardBypass) {
                e.preventDefault();
                e.returnValue = "";
            }
        });

        // Form submissions are intentional — bypass guard
        document.addEventListener("submit", function () {
            window._guardBypass = true;
        });

        // Modal helpers
        function showModal(href) {
            pendingHref = href;
            // Show / hide the Save button based on whether the page defines a save function
            var saveBtn = document.getElementById("unsaved-save-btn");
            if (saveBtn) saveBtn.style.display = window._saveBeforeLeave ? "" : "none";
            modal.style.display = "flex";
        }
        function hideModal() {
            modal.style.display = "none";
            pendingHref = null;
        }

        document.getElementById("unsaved-cancel-btn").addEventListener("click", hideModal);

        document.getElementById("unsaved-discard-btn").addEventListener("click", function () {
            dirty = false;
            window._guardBypass = true;
            hideModal();
            if (pendingHref) window.location.href = pendingHref;
        });

        document.getElementById("unsaved-save-btn").addEventListener("click", function () {
            var nav = pendingHref;
            hideModal();
            if (window._saveBeforeLeave) {
                window._saveBeforeLeave(function (ok) {
                    if (ok && nav) {
                        dirty = false;
                        window._guardBypass = true;
                        window.location.href = nav;
                    }
                });
            }
        });

        // Intercept in-page link clicks
        document.addEventListener("click", function (e) {
            var link = e.target.closest("a[href]");
            if (!link) return;
            var href = link.getAttribute("href");
            if (!href || href === "#" || href.startsWith("javascript:") || link.target === "_blank") return;
            if (dirty && !window._guardBypass) {
                e.preventDefault();
                showModal(href);
            }
        });
    })();

    // ---- Resizable table columns ----
    document.querySelectorAll("table.resizable").forEach(function (table) {
        var ths = table.querySelectorAll("thead th");
        ths.forEach(function (th) {
            // Skip empty header cells (action columns)
            if (!th.textContent.trim()) return;

            var handle = document.createElement("div");
            handle.className = "resize-handle";
            th.appendChild(handle);

            var startX, startWidth;

            handle.addEventListener("mousedown", function (e) {
                e.preventDefault();
                startX = e.pageX;
                startWidth = th.offsetWidth;
                handle.classList.add("active");

                function onMouseMove(e) {
                    th.style.width = (startWidth + e.pageX - startX) + "px";
                }
                function onMouseUp() {
                    handle.classList.remove("active");
                    document.removeEventListener("mousemove", onMouseMove);
                    document.removeEventListener("mouseup", onMouseUp);
                }
                document.addEventListener("mousemove", onMouseMove);
                document.addEventListener("mouseup", onMouseUp);
            });

            // Touch support for mobile
            handle.addEventListener("touchstart", function (e) {
                var touch = e.touches[0];
                startX = touch.pageX;
                startWidth = th.offsetWidth;
                handle.classList.add("active");

                function onTouchMove(e) {
                    var t = e.touches[0];
                    th.style.width = (startWidth + t.pageX - startX) + "px";
                }
                function onTouchEnd() {
                    handle.classList.remove("active");
                    document.removeEventListener("touchmove", onTouchMove);
                    document.removeEventListener("touchend", onTouchEnd);
                }
                document.addEventListener("touchmove", onTouchMove);
                document.addEventListener("touchend", onTouchEnd);
            });
        });
    });

    // ---- Sortable table columns ----
    document.querySelectorAll("table.sortable").forEach(function (table) {
        var ths = table.querySelectorAll("thead th");
        ths.forEach(function (th, colIndex) {
            if (th.hasAttribute("data-no-sort") || !th.textContent.trim()) return;

            th.style.cursor = "pointer";
            th.style.userSelect = "none";

            var asc = true;
            th.addEventListener("click", function (e) {
                // Don't sort when clicking the resize handle
                if (e.target.classList && e.target.classList.contains("resize-handle")) return;

                var tbody = table.querySelector("tbody");
                var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));

                // Detect column type from first non-empty cell
                var type = "string";
                for (var i = 0; i < rows.length; i++) {
                    var cell = rows[i].children[colIndex];
                    if (!cell) continue;
                    var cb = cell.querySelector("input[type=checkbox]");
                    if (cb) { type = "checkbox"; break; }
                    var txt = cell.textContent.trim();
                    if (!txt) continue;
                    if (/^-?\$?[\d,]+\.?\d*$/.test(txt.replace(/,/g, ""))) { type = "number"; break; }
                    break;
                }

                rows.sort(function (a, b) {
                    var cellA = a.children[colIndex];
                    var cellB = b.children[colIndex];
                    if (!cellA || !cellB) return 0;
                    var valA, valB;
                    if (type === "checkbox") {
                        valA = cellA.querySelector("input[type=checkbox]") ? (cellA.querySelector("input[type=checkbox]").checked ? 1 : 0) : 0;
                        valB = cellB.querySelector("input[type=checkbox]") ? (cellB.querySelector("input[type=checkbox]").checked ? 1 : 0) : 0;
                    } else if (type === "number") {
                        valA = parseFloat(cellA.textContent.replace(/[$,]/g, "")) || 0;
                        valB = parseFloat(cellB.textContent.replace(/[$,]/g, "")) || 0;
                    } else {
                        valA = cellA.textContent.trim().toLowerCase();
                        valB = cellB.textContent.trim().toLowerCase();
                    }
                    if (valA < valB) return asc ? -1 : 1;
                    if (valA > valB) return asc ? 1 : -1;
                    return 0;
                });

                rows.forEach(function (row) { tbody.appendChild(row); });

                // Update arrow indicators
                ths.forEach(function (h) {
                    var arrow = h.querySelector(".sort-arrow");
                    if (arrow) arrow.remove();
                });
                var arrow = document.createElement("span");
                arrow.className = "sort-arrow";
                arrow.textContent = asc ? " \u25B2" : " \u25BC";
                arrow.style.fontSize = "10px";
                th.appendChild(arrow);

                asc = !asc;
            });
        });
    });
})();

// Phone number formatting — (xxx) xxx-xxxx
function formatPhone(input) {
    var digits = input.value.replace(/\D/g, '').slice(0, 10);
    if (digits.length >= 7) {
        input.value = '(' + digits.slice(0,3) + ') ' + digits.slice(3,6) + '-' + digits.slice(6);
    } else if (digits.length >= 4) {
        input.value = '(' + digits.slice(0,3) + ') ' + digits.slice(3);
    } else if (digits.length > 0) {
        input.value = '(' + digits;
    }
}
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('input[type="tel"]').forEach(function(el) {
        if (el.value.trim()) formatPhone(el);
        el.addEventListener('input', function() { formatPhone(el); });
    });
});

// Inline sort order quick-save
function saveSortOrder(input) {
    var endpoint = input.dataset.endpoint;
    fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({sort_order: parseInt(input.value) || 0})
    }).then(function(resp) {
        input.style.borderColor = resp.ok ? 'var(--green)' : 'var(--red, #dc2626)';
        setTimeout(function() { input.style.borderColor = ''; }, 800);
    });
}
