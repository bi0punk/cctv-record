function showToast(message, type) {
    const container = document.getElementById('toast-container') || (() => {
        const el = document.createElement('div');
        el.id = 'toast-container';
        el.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(el);
        return el;
    })();
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.role = 'alert';
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    container.appendChild(toast);
    new bootstrap.Toast(toast).show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

async function apiPost(url, successMsg) {
    try {
        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            if (successMsg) showToast(successMsg, 'success');
        } else {
            showToast(data.detail || 'Error', 'danger');
        }
    } catch (e) {
        showToast('Error de conexión', 'danger');
    }
    pollStatus();
}

function startAll() {
    apiPost('/api/start', 'Todas las cámaras iniciadas');
}

function stopAll() {
    apiPost('/api/stop', 'Todas las cámaras detenidas');
}

function startCamera(name) {
    apiPost(`/api/camera/${encodeURIComponent(name)}/start`, `Cámara "${name}" iniciada`);
}

function stopCamera(name) {
    apiPost(`/api/camera/${encodeURIComponent(name)}/stop`, `Cámara "${name}" detenida`);
}

function restartCamera(name) {
    apiPost(`/api/camera/${encodeURIComponent(name)}/restart`, `Cámara "${name}" reiniciada`);
}

function updateCard(cam) {
    const card = document.querySelector(`[data-camera="${cam.name}"]`);
    if (!card) return;
    const isRecording = cam.status === 'recording';
    const isError = cam.status === 'error';

    card.className = `col-md-6 col-lg-4 col-xl-3 mb-3`;
    const border = isRecording ? 'success' : (isError ? 'danger' : 'secondary');
    card.querySelector('.card').className = `card h-100 border-${border}`;

    const badge = card.querySelector('.status-badge');
    badge.className = `badge bg-${border}`;
    badge.textContent = isRecording ? 'Grabando' : (isError ? 'Error' : 'Detenido');

    const footerBtn = card.querySelector('.card-footer button');
    if (footerBtn) {
        if (isRecording) {
            footerBtn.className = 'btn btn-outline-danger btn-sm w-100';
            footerBtn.textContent = 'Detener';
            footerBtn.onclick = () => stopCamera(cam.name);
        } else {
            footerBtn.className = 'btn btn-outline-success btn-sm w-100';
            footerBtn.textContent = 'Iniciar';
            footerBtn.onclick = () => startCamera(cam.name);
        }
    }

    const lastFile = card.querySelector('.text-muted:last-of-type');
    if (lastFile && cam.last_file) {
        lastFile.textContent = `Último: ${cam.last_file.split('/').pop()}`;
        lastFile.title = cam.last_file;
    }
}

async function pollStatus() {
    try {
        const res = await fetch('/api/cameras');
        const cameras = await res.json();
        cameras.forEach(updateCard);

        const sysRes = await fetch('/api/status');
        const sys = await sysRes.json();
        const badge = document.getElementById('status-badge');
        if (sys.recording_count > 0) {
            badge.className = 'badge bg-success';
            badge.textContent = `${sys.recording_count}/${sys.total_cameras} grabando`;
        } else {
            badge.className = 'badge bg-secondary';
            badge.textContent = 'Detenido';
        }
    } catch (e) {
        // ignore polling errors
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    const path = window.location.pathname;
    navLinks.forEach(link => {
        if (link.getAttribute('href') === path) {
            link.classList.add('active');
        }
    });
});
