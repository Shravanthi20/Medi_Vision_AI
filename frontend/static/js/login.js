// ── Live Clock ──────────────────────────────────────
const clockTime = document.getElementById('clock-time');
const clockDay = document.getElementById('clock-day');
const clockDate = document.getElementById('clock-date');

const DAYS = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'];

function pad(n) { return String(n).padStart(2, '0'); }

function updateClock() {
    const now = new Date();
    clockTime.textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    clockDay.textContent = DAYS[now.getDay()];
    clockDate.textContent = `${pad(now.getDate())}/${pad(now.getMonth() + 1)}/${now.getFullYear()}`;
}

updateClock();
setInterval(updateClock, 1000);

// ── Password toggle ──────────────────────────────────
const pwInput = document.getElementById('password');
const toggleBtn = document.getElementById('toggle-pw');
const eyeOpen = document.getElementById('eye-open');
const eyeOff = document.getElementById('eye-off');

toggleBtn.addEventListener('click', () => {
    const show = pwInput.type === 'password';
    pwInput.type = show ? 'text' : 'password';
    eyeOpen.style.display = show ? 'none' : 'block';
    eyeOff.style.display = show ? 'block' : 'none';
});

// ── Sign In ──────────────────────────────────────────
const form = document.getElementById('login-form');
const errorMsg = document.getElementById('error-msg');
const usernameInput = document.getElementById('username');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorMsg.classList.remove('show');

    const username = usernameInput.value.trim();
    const password = pwInput.value.trim();

    if (!username || !password) {
        errorMsg.textContent = 'Please enter both username and password.';
        errorMsg.classList.add('show');
        return;
    }

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: username.toLowerCase(), password })
        });

        const result = await response.json().catch(() => ({ message: 'Server error: Invalid response' }));

        if (response.ok) {
            window.location.href = '/';
        } else {
            errorMsg.textContent = result.message || 'Invalid credentials';
            errorMsg.classList.add('show');
        }
    } catch (err) {
        console.error('Login error:', err);
        errorMsg.textContent = 'An error occurred. Please try again.';
        errorMsg.classList.add('show');
    }
});

pwInput.addEventListener('input', () => errorMsg.classList.remove('show'));
usernameInput.addEventListener('input', () => errorMsg.classList.remove('show'));