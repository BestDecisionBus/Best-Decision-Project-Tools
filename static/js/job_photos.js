// Job Photo Capture — Job selection, camera capture, optional caption, upload
(function () {
    "use strict";

    var TOKEN = document.getElementById("job-photo-app").dataset.token;

    // DOM refs
    var jobSelect = document.getElementById("photo-job-select");
    var fileInput = document.getElementById("photo-file-input");
    var btnCapture = document.getElementById("btn-photo-capture");
    var previewContainer = document.getElementById("photo-preview-container");
    var previewImg = document.getElementById("photo-preview-img");
    var captionInput = document.getElementById("photo-caption");
    var btnUpload = document.getElementById("btn-photo-upload");
    var btnRetake = document.getElementById("btn-photo-retake");
    var statusArea = document.getElementById("photo-status");
    var formSection = document.getElementById("photo-form-section");
    var previewSection = document.getElementById("photo-preview-section");
    var successSection = document.getElementById("photo-success-section");
    var btnAnother = document.getElementById("btn-photo-another");

    var imageBlob = null;

    // ---- Initial state ----

    function resetState() {
        imageBlob = null;
        if (fileInput) fileInput.value = "";
        if (previewImg) previewImg.src = "";
        if (captionInput) captionInput.value = "";
        if (jobSelect) jobSelect.value = "";
        showSection("form");
        updateCaptureButton();
    }

    function showSection(name) {
        if (formSection) formSection.style.display = name === "form" ? "block" : "none";
        if (previewSection) previewSection.style.display = name === "preview" ? "block" : "none";
        if (successSection) successSection.style.display = name === "success" ? "flex" : "none";
        if (statusArea) statusArea.style.display = "none";
    }

    function updateCaptureButton() {
        if (btnCapture) {
            btnCapture.disabled = !jobSelect || !jobSelect.value;
        }
    }

    function showStatus(msg, isError) {
        if (!statusArea) return;
        statusArea.style.display = "block";
        statusArea.className = isError ? "result-error" : "result-success";
        statusArea.textContent = msg;
    }

    // ---- Job selection ----

    if (jobSelect) {
        jobSelect.addEventListener("change", updateCaptureButton);
    }

    // ---- Capture photo ----

    if (btnCapture) {
        btnCapture.addEventListener("click", function () {
            if (!jobSelect || !jobSelect.value) {
                showStatus("Please select a job first.", true);
                return;
            }
            fileInput.click();
        });
    }

    if (fileInput) {
        fileInput.addEventListener("change", function (e) {
            var file = e.target.files[0];
            if (!file) return;
            imageBlob = file;
            previewImg.src = URL.createObjectURL(file);
            showSection("preview");
        });
    }

    // ---- Retake ----

    if (btnRetake) {
        btnRetake.addEventListener("click", function () {
            imageBlob = null;
            fileInput.value = "";
            showSection("form");
        });
    }

    // ---- Upload ----

    if (btnUpload) {
        btnUpload.addEventListener("click", function () {
            if (!imageBlob) {
                showStatus("No photo to upload.", true);
                return;
            }
            if (!jobSelect || !jobSelect.value) {
                showStatus("Please select a job.", true);
                return;
            }

            btnUpload.disabled = true;
            btnUpload.textContent = "Uploading...";

            var formData = new FormData();
            formData.append("token", TOKEN);
            formData.append("job_id", jobSelect.value);
            formData.append("image", imageBlob, "photo.jpg");
            if (captionInput && captionInput.value.trim()) {
                formData.append("caption", captionInput.value.trim());
            }

            fetch("/api/job-photos/upload", {
                method: "POST",
                body: formData,
            })
            .then(function (r) {
                if (!r.ok) {
                    return r.json().then(function (d) {
                        throw new Error(d.error || "Upload failed");
                    });
                }
                return r.json();
            })
            .then(function (data) {
                if (data.success) {
                    showSection("success");
                } else {
                    showStatus(data.error || "Upload failed.", true);
                    showSection("preview");
                }
            })
            .catch(function (err) {
                showStatus(err.message || "Network error. Please try again.", true);
                showSection("preview");
            })
            .finally(function () {
                btnUpload.disabled = false;
                btnUpload.textContent = "Upload Photo";
            });
        });
    }

    // ---- Another photo ----

    if (btnAnother) {
        btnAnother.addEventListener("click", function () {
            resetState();
        });
    }

    // ---- Initialize ----
    showSection("form");
    updateCaptureButton();
})();
