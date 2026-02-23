// Timekeeper — GPS watch, clock in/out, employee status check, today's entries
(function () {
    "use strict";

    var currentLat = null;
    var currentLng = null;
    var gpsReady = false;
    var gpsWatchId = null;

    var jobSection = document.getElementById("job-section");
    var clockInSection = document.getElementById("clock-in-section");
    var clockOutSection = document.getElementById("clock-out-section");
    var statusSection = document.getElementById("status-section");
    var statusMessage = document.getElementById("status-message");
    var resultSection = document.getElementById("result-section");
    var resultMessage = document.getElementById("result-message");
    var todaySection = document.getElementById("today-section");
    var todayEntries = document.getElementById("today-entries");
    var gpsStatus = document.getElementById("gps-status");
    var activeInfo = document.getElementById("active-info");

    // ---- GPS ----

    function startGPS() {
        if (!navigator.geolocation) {
            gpsStatus.textContent = "GPS not available on this device";
            gpsStatus.className = "gps-status gps-error";
            return;
        }
        gpsWatchId = navigator.geolocation.watchPosition(
            function (pos) {
                currentLat = pos.coords.latitude;
                currentLng = pos.coords.longitude;
                gpsReady = true;
                gpsStatus.textContent = "GPS ready (" +
                    currentLat.toFixed(5) + ", " + currentLng.toFixed(5) + ")";
                gpsStatus.className = "gps-status gps-ok";
            },
            function (err) {
                gpsStatus.textContent = "GPS error: " + err.message;
                gpsStatus.className = "gps-status gps-error";
            },
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 }
        );
    }

    // ---- Auto-init on page load ----

    function hideAll() {
        jobSection.style.display = "none";
        clockInSection.style.display = "none";
        clockOutSection.style.display = "none";
        statusSection.style.display = "none";
        resultSection.style.display = "none";
        todaySection.style.display = "none";
    }

    function checkEmployeeStatus(empId) {
        hideAll();
        fetch("/api/employee-status?employee_id=" + empId)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.active_entry) {
                    showClockedIn(data.active_entry);
                } else {
                    showClockInForm();
                }
                if (data.today_entries && data.today_entries.length > 0) {
                    showTodayEntries(data.today_entries);
                }
            })
            .catch(function () {
                showResult("Failed to check status. Please try again.", true);
            });
    }

    function showClockedIn(entry) {
        statusSection.style.display = "block";
        statusMessage.className = "status-box status-clocked-in";
        statusMessage.textContent = "Currently clocked in";

        clockOutSection.style.display = "block";
        var inTime = formatTime(entry.clock_in_time);
        activeInfo.textContent = "Clocked in at " + inTime +
            (entry.job_name ? " \u2014 " + entry.job_name : "");
    }

    function showClockInForm() {
        statusSection.style.display = "block";
        statusMessage.className = "status-box status-clocked-out";
        statusMessage.textContent = "Not clocked in";

        jobSection.style.display = "block";
        clockInSection.style.display = "block";
    }

    // ---- Clock In ----

    window.clockIn = function () {
        var jobId = document.getElementById("job-select").value;

        if (!jobId) { showResult("Please select a job.", true); return; }

        var btn = document.getElementById("clock-in-btn");
        btn.disabled = true;
        btn.textContent = "CLOCKING IN...";

        var payload = {
            employee_id: EMPLOYEE_ID,
            job_id: parseInt(jobId),
            latitude: currentLat,
            longitude: currentLng
        };

        fetch("/api/clock-in", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
        .then(function (res) {
            if (res.ok) {
                showResult("Clocked in at " + formatTime(res.data.clock_in_time), false);
                setTimeout(function () { checkEmployeeStatus(EMPLOYEE_ID); }, 1500);
            } else {
                showResult(res.data.error || "Clock in failed.", true);
                btn.disabled = false;
                btn.textContent = "CLOCK IN";
            }
        })
        .catch(function () {
            showResult("Network error. Please try again.", true);
            btn.disabled = false;
            btn.textContent = "CLOCK IN";
        });
    };

    // ---- Clock Out ----

    window.clockOut = function () {
        var btn = document.getElementById("clock-out-btn");
        btn.disabled = true;
        btn.textContent = "CLOCKING OUT...";

        var payload = {
            employee_id: EMPLOYEE_ID,
            latitude: currentLat,
            longitude: currentLng
        };

        fetch("/api/clock-out", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
        .then(function (res) {
            if (res.ok) {
                var msg = "Clocked out at " + formatTime(res.data.clock_out_time);
                if (res.data.total_hours != null) {
                    msg += " \u2014 " + res.data.total_hours + " hours";
                }
                showResult(msg, false);
                setTimeout(function () { checkEmployeeStatus(EMPLOYEE_ID); }, 1500);
            } else {
                showResult(res.data.error || "Clock out failed.", true);
                btn.disabled = false;
                btn.textContent = "CLOCK OUT";
            }
        })
        .catch(function () {
            showResult("Network error. Please try again.", true);
            btn.disabled = false;
            btn.textContent = "CLOCK OUT";
        });
    };

    // ---- Today's entries ----

    function showTodayEntries(entries) {
        todaySection.style.display = "block";
        todayEntries.innerHTML = "";
        entries.forEach(function (e) {
            var div = document.createElement("div");
            div.className = "today-entry";
            var inTime = formatTime(e.clock_in_time);
            var outTime = e.clock_out_time ? formatTime(e.clock_out_time) : "\u2014";
            var hours = e.total_hours != null ? e.total_hours + "h" : "active";
            div.innerHTML =
                '<div class="entry-job">' + escapeHtml(e.job_name || "") + '</div>' +
                '<div class="entry-times">' + inTime + " \u2192 " + outTime +
                ' <span class="entry-hours">' + hours + '</span></div>';
            todayEntries.appendChild(div);
        });
    }

    // ---- Helpers ----

    function showResult(msg, isError) {
        resultSection.style.display = "block";
        resultMessage.className = isError ? "result-error" : "result-success";
        resultMessage.textContent = msg;
        if (!isError) {
            setTimeout(function () { resultSection.style.display = "none"; }, 4000);
        }
    }

    function formatTime(iso) {
        if (!iso) return "\u2014";
        try {
            var d = new Date(iso);
            return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        } catch (e) {
            return iso;
        }
    }

    function escapeHtml(str) {
        var div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    // ---- Start on page load ----
    startGPS();
    checkEmployeeStatus(EMPLOYEE_ID);
})();
