// Scheduler UI — Week navigation, schedule CRUD, modal, quick-select shifts
(function () {
    "use strict";

    // ---- Configuration (set by template) ----
    // SCHEDULER_TOKEN, SCHEDULER_EMPLOYEES, SCHEDULER_JOBS are set globally by the template

    var currentWeekStart = null;  // Date object (Monday)
    var scheduleData = [];        // Fetched schedules for current week
    var editingScheduleId = null; // null = new, integer = editing

    // ---- DOM refs ----
    var weekLabel = document.getElementById("week-label");
    var btnPrev = document.getElementById("btn-prev-week");
    var btnNext = document.getElementById("btn-next-week");
    var btnToday = document.getElementById("btn-today");
    var scheduleBody = document.getElementById("schedule-body");
    var modalOverlay = document.getElementById("schedule-modal-overlay");
    var modalTitle = document.getElementById("modal-title");
    var modalForm = document.getElementById("schedule-form");
    var modalDate = document.getElementById("modal-date");
    var modalEmployee = document.getElementById("modal-employee");
    var modalJob = document.getElementById("modal-job");
    var modalNotes = document.getElementById("modal-notes");
    var modalStartTime = document.getElementById("modal-start-time");
    var modalEndTime = document.getElementById("modal-end-time");
    var customTimeInputs = document.getElementById("custom-time-inputs");
    var btnSaveSchedule = document.getElementById("btn-save-schedule");
    var btnDeleteSchedule = document.getElementById("btn-delete-schedule");
    var btnCancelModal = document.getElementById("btn-cancel-modal");
    var quickBtns = document.querySelectorAll(".quick-select-btn");

    var selectedShiftType = "full_day";

    // ---- Date helpers ----

    function getMonday(d) {
        var date = new Date(d);
        var day = date.getDay();
        var diff = date.getDate() - day + (day === 0 ? -6 : 1);
        date.setDate(diff);
        date.setHours(0, 0, 0, 0);
        return date;
    }

    function addDays(d, n) {
        var date = new Date(d);
        date.setDate(date.getDate() + n);
        return date;
    }

    function formatDate(d) {
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, "0");
        var dd = String(d.getDate()).padStart(2, "0");
        return y + "-" + m + "-" + dd;
    }

    function formatDateShort(d) {
        var days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        return days[d.getDay()] + " " + months[d.getMonth()] + " " + d.getDate();
    }

    function formatWeekRange(monday) {
        var sunday = addDays(monday, 6);
        var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        var start = months[monday.getMonth()] + " " + monday.getDate();
        var end = months[sunday.getMonth()] + " " + sunday.getDate() + ", " + sunday.getFullYear();
        return start + " \u2013 " + end;
    }

    function isToday(d) {
        var today = new Date();
        return d.getFullYear() === today.getFullYear() &&
               d.getMonth() === today.getMonth() &&
               d.getDate() === today.getDate();
    }

    // ---- Week navigation ----

    function navigateWeek(offset) {
        currentWeekStart = addDays(currentWeekStart, offset * 7);
        updateView();
    }

    function goToToday() {
        currentWeekStart = getMonday(new Date());
        updateView();
    }

    function updateView() {
        weekLabel.textContent = formatWeekRange(currentWeekStart);
        fetchSchedules();
    }

    // ---- Fetch schedules from API ----

    function fetchSchedules() {
        var weekEnd = addDays(currentWeekStart, 6);
        var url = "/scheduler/api/schedules?week_start=" +
                  formatDate(currentWeekStart) + "&week_end=" + formatDate(weekEnd);

        fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (Array.isArray(data)) {
                    scheduleData = data;
                } else {
                    scheduleData = [];
                }
                renderGrid();
            })
            .catch(function () {
                scheduleData = [];
                renderGrid();
            });
    }

    // ---- Render week grid ----

    function renderGrid() {
        if (!scheduleBody) return;

        // Generate day columns (Mon-Sun)
        var days = [];
        for (var i = 0; i < 7; i++) {
            days.push(addDays(currentWeekStart, i));
        }

        // Update header
        var headerRow = document.getElementById("schedule-header");
        if (headerRow) {
            headerRow.innerHTML = '<th class="col-employee">Employee</th>';
            days.forEach(function (d) {
                var th = document.createElement("th");
                th.textContent = formatDateShort(d);
                if (isToday(d)) th.style.background = "#dbeafe";
                headerRow.appendChild(th);
            });
        }

        // Build schedule lookup: employeeId -> date -> [schedules]
        var lookup = {};
        scheduleData.forEach(function (s) {
            var key = s.employee_id;
            if (!lookup[key]) lookup[key] = {};
            if (!lookup[key][s.date]) lookup[key][s.date] = [];
            lookup[key][s.date].push(s);
        });

        // Render rows
        scheduleBody.innerHTML = "";

        if (typeof SCHEDULER_EMPLOYEES === "undefined" || !SCHEDULER_EMPLOYEES.length) {
            var tr = document.createElement("tr");
            var td = document.createElement("td");
            td.colSpan = 8;
            td.style.textAlign = "center";
            td.style.padding = "24px";
            td.style.color = "#6b7280";
            td.textContent = "No employees found. Add employees first.";
            tr.appendChild(td);
            scheduleBody.appendChild(tr);
            return;
        }

        SCHEDULER_EMPLOYEES.forEach(function (emp) {
            var tr = document.createElement("tr");

            // Employee name cell
            var tdName = document.createElement("td");
            tdName.style.fontWeight = "600";
            tdName.style.whiteSpace = "nowrap";
            tdName.textContent = emp.name;
            tr.appendChild(tdName);

            // Day cells
            days.forEach(function (d) {
                var td = document.createElement("td");
                td.className = "schedule-cell";
                if (isToday(d)) td.classList.add("today");

                var dateStr = formatDate(d);
                var entries = (lookup[emp.id] && lookup[emp.id][dateStr]) || [];

                entries.forEach(function (entry) {
                    var div = document.createElement("div");
                    div.className = "schedule-entry";
                    div.style.background = getShiftColor(entry.shift_type);
                    div.style.color = getShiftTextColor(entry.shift_type);

                    var timeStr = (entry.start_time || "").substring(0, 5) +
                                  "\u2013" + (entry.end_time || "").substring(0, 5);
                    div.innerHTML = '<div class="entry-time">' + timeStr + '</div>' +
                                    '<div class="entry-job">' + escapeHtml(entry.job_name || "") + '</div>';

                    div.addEventListener("click", function (e) {
                        e.stopPropagation();
                        openModal(entry, dateStr, emp.id);
                    });
                    td.appendChild(div);
                });

                // Click empty cell to add
                td.addEventListener("click", function () {
                    openModal(null, dateStr, emp.id);
                });

                tr.appendChild(td);
            });

            scheduleBody.appendChild(tr);
        });
    }

    function getShiftColor(type) {
        switch (type) {
            case "full_day":  return "#dbeafe";
            case "morning":   return "#fef3c7";
            case "afternoon": return "#fce7f3";
            default:          return "#e5e7eb";
        }
    }

    function getShiftTextColor(type) {
        switch (type) {
            case "full_day":  return "#1e40af";
            case "morning":   return "#92400e";
            case "afternoon": return "#9d174d";
            default:          return "#374151";
        }
    }

    // ---- Modal ----

    function openModal(schedule, dateStr, employeeId) {
        if (!modalOverlay) return;

        editingScheduleId = schedule ? schedule.id : null;
        modalTitle.textContent = schedule ? "Edit Schedule" : "Add Schedule";

        // Set date
        modalDate.value = dateStr || "";

        // Set employee
        if (modalEmployee) {
            modalEmployee.value = schedule ? schedule.employee_id : (employeeId || "");
        }

        // Set job
        if (modalJob) {
            modalJob.value = schedule ? schedule.job_id : "";
        }

        // Set notes
        if (modalNotes) {
            modalNotes.value = schedule ? (schedule.notes || "") : "";
        }

        // Set shift type
        var shiftType = schedule ? (schedule.shift_type || "full_day") : "full_day";
        selectShiftType(shiftType);

        // Set times
        if (modalStartTime) modalStartTime.value = schedule ? (schedule.start_time || "07:00") : "07:00";
        if (modalEndTime) modalEndTime.value = schedule ? (schedule.end_time || "17:00") : "17:00";

        // Show/hide delete button
        if (btnDeleteSchedule) {
            btnDeleteSchedule.style.display = schedule ? "inline-block" : "none";
        }

        modalOverlay.classList.add("active");
    }

    function closeModal() {
        if (modalOverlay) {
            modalOverlay.classList.remove("active");
        }
        editingScheduleId = null;
    }

    // ---- Quick-select shift presets ----

    function selectShiftType(type) {
        selectedShiftType = type;

        // Update button states
        quickBtns.forEach(function (btn) {
            btn.classList.toggle("active", btn.dataset.shift === type);
        });

        // Show/hide custom time inputs
        if (customTimeInputs) {
            customTimeInputs.style.display = type === "custom" ? "flex" : "none";
        }

        // Set preset times
        var presets = {
            "full_day":  { start: "07:00", end: "17:00" },
            "morning":   { start: "07:00", end: "12:00" },
            "afternoon": { start: "12:00", end: "17:00" },
        };

        if (presets[type]) {
            if (modalStartTime) modalStartTime.value = presets[type].start;
            if (modalEndTime) modalEndTime.value = presets[type].end;
        }
    }

    quickBtns.forEach(function (btn) {
        btn.addEventListener("click", function () {
            selectShiftType(btn.dataset.shift);
        });
    });

    // ---- Save schedule ----

    function saveSchedule() {
        var payload = {
            employee_id: parseInt(modalEmployee.value),
            job_id: parseInt(modalJob.value),
            token: SCHEDULER_TOKEN,
            date: modalDate.value,
            shift_type: selectedShiftType,
            start_time: modalStartTime.value,
            end_time: modalEndTime.value,
            notes: modalNotes ? modalNotes.value.trim() : "",
        };

        if (!payload.employee_id || !payload.job_id || !payload.date) {
            alert("Please fill in employee, job, and date.");
            return;
        }

        var url, method;
        if (editingScheduleId) {
            url = "/scheduler/api/schedules/" + editingScheduleId;
            method = "PUT";
        } else {
            url = "/scheduler/api/schedules";
            method = "POST";
        }

        btnSaveSchedule.disabled = true;
        btnSaveSchedule.textContent = "Saving...";

        fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
        .then(function (r) {
            if (!r.ok) {
                return r.json().then(function (d) { throw new Error(d.error || "Save failed"); });
            }
            return r.json();
        })
        .then(function () {
            closeModal();
            fetchSchedules();
        })
        .catch(function (err) {
            alert(err.message || "Failed to save schedule.");
        })
        .finally(function () {
            btnSaveSchedule.disabled = false;
            btnSaveSchedule.textContent = "Save";
        });
    }

    // ---- Delete schedule ----

    function deleteSchedule() {
        if (!editingScheduleId) return;
        if (!confirm("Delete this schedule entry?")) return;

        fetch("/scheduler/api/schedules/" + editingScheduleId, {
            method: "DELETE",
        })
        .then(function (r) {
            if (!r.ok) {
                return r.json().then(function (d) { throw new Error(d.error || "Delete failed"); });
            }
            return r.json();
        })
        .then(function () {
            closeModal();
            fetchSchedules();
        })
        .catch(function (err) {
            alert(err.message || "Failed to delete schedule.");
        });
    }

    // ---- Helpers ----

    function escapeHtml(str) {
        var div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    // ---- Event listeners ----

    if (btnPrev) btnPrev.addEventListener("click", function () { navigateWeek(-1); });
    if (btnNext) btnNext.addEventListener("click", function () { navigateWeek(1); });
    if (btnToday) btnToday.addEventListener("click", goToToday);
    if (btnSaveSchedule) btnSaveSchedule.addEventListener("click", saveSchedule);
    if (btnDeleteSchedule) btnDeleteSchedule.addEventListener("click", deleteSchedule);
    if (btnCancelModal) btnCancelModal.addEventListener("click", closeModal);

    // Close modal on overlay click
    if (modalOverlay) {
        modalOverlay.addEventListener("click", function (e) {
            if (e.target === modalOverlay) closeModal();
        });
    }

    // Close modal on Escape key
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeModal();
    });

    // ---- Initialize ----
    currentWeekStart = getMonday(new Date());
    updateView();
})();
