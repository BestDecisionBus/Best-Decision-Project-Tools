// Receipt Capture — Camera + Dropdown Step + Mic + Upload logic
// Updated with job/category dropdown step between photo preview and voice recording

(function () {
    "use strict";

    var TOKEN = document.getElementById("capture-app").dataset.token;

    // Elements
    var steps = document.querySelectorAll(".step");
    var btnCapture = document.getElementById("btn-capture");
    var btnRetake = document.getElementById("btn-retake");
    var btnAcceptPhoto = document.getElementById("btn-accept-photo");
    var btnContinueDropdown = document.getElementById("btn-continue-dropdown");
    var btnRecord = document.getElementById("btn-record");
    var btnSubmit = document.getElementById("btn-submit");
    var btnAnother = document.getElementById("btn-another");
    var previewImg = document.getElementById("preview-img");
    var fileInput = document.getElementById("file-input");
    var recordingIndicator = document.getElementById("recording-indicator");

    // Dropdown elements
    var jobSelect = document.getElementById("job-select");
    var category1Select = document.getElementById("category1-select");
    var category2Select = document.getElementById("category2-select");

    var imageBlob = null;
    var audioBlob = null;
    var mediaRecorder = null;
    var audioChunks = [];

    function showStep(name) {
        steps.forEach(function (s) {
            s.classList.toggle("active", s.dataset.step === name);
        });
    }

    // ---- Step 1: Capture photo ----

    btnCapture.addEventListener("click", function () {
        fileInput.click();
    });

    fileInput.addEventListener("change", function (e) {
        var file = e.target.files[0];
        if (!file) return;
        imageBlob = file;
        previewImg.src = URL.createObjectURL(file);
        showStep("preview");
    });

    btnRetake.addEventListener("click", function () {
        imageBlob = null;
        fileInput.value = "";
        showStep("capture");
    });

    // ---- Step 2: Accept photo -> show dropdown step ----

    btnAcceptPhoto.addEventListener("click", function () {
        showStep("dropdown");
        loadDropdownData();
    });

    // ---- Step 2.5: Dropdown step (job + category selection) ----

    function loadDropdownData() {
        // Fetch jobs
        fetch("/api/jobs?token=" + encodeURIComponent(TOKEN))
            .then(function (r) { return r.json(); })
            .then(function (jobs) {
                jobSelect.innerHTML = '<option value="">-- Select Job --</option>';
                jobs.forEach(function (j) {
                    var opt = document.createElement("option");
                    opt.value = j.id;
                    opt.textContent = j.name;
                    jobSelect.appendChild(opt);
                });
            })
            .catch(function () {
                jobSelect.innerHTML = '<option value="">Failed to load jobs</option>';
            });

        // Fetch categories
        fetch("/api/categories?token=" + encodeURIComponent(TOKEN))
            .then(function (r) { return r.json(); })
            .then(function (cats) {
                var emptyOpt = '<option value="">-- None --</option>';
                category1Select.innerHTML = emptyOpt;
                category2Select.innerHTML = emptyOpt;
                cats.forEach(function (c) {
                    var opt1 = document.createElement("option");
                    opt1.value = c.id;
                    opt1.textContent = c.name;
                    category1Select.appendChild(opt1);

                    var opt2 = document.createElement("option");
                    opt2.value = c.id;
                    opt2.textContent = c.name;
                    category2Select.appendChild(opt2);
                });
            })
            .catch(function () {
                category1Select.innerHTML = '<option value="">Failed to load</option>';
                category2Select.innerHTML = '<option value="">Failed to load</option>';
            });
    }

    // Enable/disable continue button based on job selection
    if (jobSelect) {
        jobSelect.addEventListener("change", function () {
            btnContinueDropdown.disabled = !jobSelect.value;
        });
    }

    // Continue to voice recording
    if (btnContinueDropdown) {
        btnContinueDropdown.addEventListener("click", function () {
            if (!jobSelect.value) return;
            showStep("record");
        });
    }

    // ---- Step 3: Voice recording ----

    btnRecord.addEventListener("click", async function () {
        if (mediaRecorder && mediaRecorder.state === "recording") {
            // Stop recording
            mediaRecorder.stop();
            btnRecord.textContent = "Start Recording";
            btnRecord.classList.remove("recording");
            recordingIndicator.classList.remove("active");
            return;
        }

        // Start recording
        try {
            var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

            mediaRecorder.ondataavailable = function (e) {
                if (e.data.size > 0) audioChunks.push(e.data);
            };

            mediaRecorder.onstop = function () {
                audioBlob = new Blob(audioChunks, { type: "audio/webm" });
                stream.getTracks().forEach(function (t) { t.stop(); });
                btnSubmit.classList.remove("hidden");
            };

            mediaRecorder.start();
            btnRecord.textContent = "Stop Recording";
            btnRecord.classList.add("recording");
            recordingIndicator.classList.add("active");
            btnSubmit.classList.add("hidden");
        } catch (err) {
            alert("Microphone access is required. Please allow microphone access and try again.");
        }
    });

    // ---- Step 4: Submit ----

    btnSubmit.addEventListener("click", async function () {
        if (!imageBlob || !audioBlob) return;

        showStep("processing");

        var formData = new FormData();
        formData.append("token", TOKEN);
        formData.append("image", imageBlob, "receipt.jpg");
        formData.append("audio", audioBlob, "memo.webm");

        // Include job and category selections from the dropdown step
        if (jobSelect && jobSelect.value) {
            formData.append("job_id", jobSelect.value);
        }
        if (category1Select && category1Select.value) {
            formData.append("category_1_id", category1Select.value);
        }
        if (category2Select && category2Select.value) {
            formData.append("category_2_id", category2Select.value);
        }

        try {
            var resp = await fetch("/api/upload", { method: "POST", body: formData });
            var data = await resp.json();

            if (!resp.ok) {
                alert(data.error || "Upload failed. Please try again.");
                showStep("record");
                return;
            }

            // Upload accepted — show success immediately.
            // Transcription happens in background on the server.
            showStep("success");
        } catch (err) {
            alert("Network error. Please check your connection and try again.");
            showStep("record");
        }
    });

    // ---- Reset for another receipt ----

    btnAnother.addEventListener("click", function () {
        imageBlob = null;
        audioBlob = null;
        audioChunks = [];
        fileInput.value = "";
        btnSubmit.classList.add("hidden");
        // Reset dropdown selections
        if (jobSelect) jobSelect.value = "";
        if (category1Select) category1Select.value = "";
        if (category2Select) category2Select.value = "";
        if (btnContinueDropdown) btnContinueDropdown.disabled = true;
        showStep("capture");
    });

    // ---- Start on capture step ----
    showStep("capture");
})();
