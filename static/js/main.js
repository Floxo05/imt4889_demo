(function () {
  'use strict';

  const MAX_SIZE = 50 * 1024 * 1024; // 50 MB
  const ALLOWED_TYPES = ['application/pdf', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'application/vnd.ms-powerpoint'];
  const ALLOWED_EXTS = ['pdf', 'pptx', 'ppt'];

  function validateFile(file) {
    if (!file) return 'No file selected.';
    const ext = file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      return 'Invalid file type. Only PDF, PPTX, and PPT are allowed.';
    }
    if (file.size > MAX_SIZE) {
      return 'File too large. Maximum size is 50 MB.';
    }
    return null;
  }

  function setupUploadForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return;

    const fileInput = form.querySelector('input[type="file"]');
    const errorDiv = document.getElementById('fileError');
    const progressWrapper = document.getElementById('progressWrapper');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const submitBtn = document.getElementById('submitBtn');

    fileInput.addEventListener('change', function () {
      const err = validateFile(fileInput.files[0]);
      if (err) {
        errorDiv.textContent = err;
        errorDiv.classList.remove('d-none');
        submitBtn.disabled = true;
      } else {
        errorDiv.classList.add('d-none');
        submitBtn.disabled = false;
      }
    });

    form.addEventListener('submit', function (e) {
      const err = validateFile(fileInput.files[0]);
      if (err) {
        e.preventDefault();
        errorDiv.textContent = err;
        errorDiv.classList.remove('d-none');
        return;
      }

      // Use XHR for progress tracking if file > 2 MB or if we want progress for all
      if (fileInput.files[0]) {
        e.preventDefault();
        const xhr = new XMLHttpRequest();
        const formData = new FormData(form);

        xhr.open('POST', form.action, true);
        xhr.timeout = 30000; // 30 seconds

        xhr.upload.addEventListener('progress', function (evt) {
          if (evt.lengthComputable) {
            const percent = Math.round((evt.loaded / evt.total) * 100);
            progressWrapper.classList.remove('d-none');
            progressBar.style.width = percent + '%';
            progressBar.textContent = percent + '%';
            progressText.textContent = `${(evt.loaded / 1024 / 1024).toFixed(1)} / ${(evt.total / 1024 / 1024).toFixed(1)} MB`;
          }
        });

        xhr.addEventListener('load', function () {
          if (xhr.status >= 200 && xhr.status < 300) {
            // Server responded; let browser render the redirect or page
            document.open();
            document.write(xhr.responseText);
            document.close();
          } else {
            progressBar.classList.remove('progress-bar-animated');
            progressBar.classList.add('bg-danger');
            progressText.textContent = 'Upload failed. Please try again.';
            submitBtn.disabled = false;
          }
        });

        xhr.addEventListener('error', function () {
          progressBar.classList.remove('progress-bar-animated');
          progressBar.classList.add('bg-danger');
          progressText.textContent = 'Network error. Please check your connection and try again.';
          submitBtn.disabled = false;
        });

        xhr.addEventListener('timeout', function () {
          progressBar.classList.remove('progress-bar-animated');
          progressBar.classList.add('bg-danger');
          progressText.textContent = 'Upload timed out. Please try again on a stable connection.';
          submitBtn.disabled = false;
        });

        submitBtn.disabled = true;
        xhr.send(formData);
      }
    });
  }

  setupUploadForm('uploadForm');

  // Batch download select-all
  const selectAll = document.getElementById('selectAll');
  if (selectAll) {
    selectAll.addEventListener('change', function () {
      document.querySelectorAll('.row-check').forEach(cb => cb.checked = selectAll.checked);
      updateBatchButton();
    });
  }

  document.querySelectorAll('.row-check').forEach(cb => {
    cb.addEventListener('change', updateBatchButton);
  });

  function updateBatchButton() {
    const btn = document.getElementById('batchDownloadBtn');
    if (!btn) return;
    const any = document.querySelectorAll('.row-check:checked').length > 0;
    btn.disabled = !any;
  }

  // Feedback edit toggle
  window.toggleEdit = function (id) {
    const form = document.getElementById('editForm' + id);
    if (form) {
      form.classList.toggle('d-none');
    }
  };
})();
