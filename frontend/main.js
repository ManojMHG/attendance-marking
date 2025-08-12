// Simple frontend for Attendance Marking
// captures a webcam image and sends it to the backend for signup/login with face recognition and location restriction.

const video = document.getElementById('video');
const video2 = document.getElementById('video2');

// Allowed location settings
const ALLOWED_LAT = 13.009607; // Change this to your allowed latitude
const ALLOWED_LON = 77.638065; // Change this to your allowed longitude
const ALLOWED_RADIUS_METERS = 10000; // Change this to allowed distance in meters

// Calculate distance between two lat/lon points (Haversine formula)
function getDistanceFromLatLonInMeters(lat1, lon1, lat2, lon2) {
  const R = 6371000; // radius of Earth in meters
  const toRad = (deg) => deg * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
    Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

async function startCamera(videoEl) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    videoEl.srcObject = stream;
    return true;
  } catch (err) {
    console.error('camera error', err);
    return false;
  }
}

function captureImageFromVideo(videoEl) {
  const canvas = document.createElement('canvas');
  canvas.width = videoEl.videoWidth || 640;
  canvas.height = videoEl.videoHeight || 480;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', 0.9);
}

document.addEventListener('DOMContentLoaded', async () => {
  const btnLogin = document.getElementById('btn-login');
  const btnSignup = document.getElementById('btn-signup');
  const loginForm = document.getElementById('login-form');
  const signupForm = document.getElementById('signup-form');

  btnLogin.addEventListener('click', () => {
    btnLogin.classList.add('active');
    btnSignup.classList.remove('active');
    loginForm.classList.add('active');
    signupForm.classList.remove('active');
  });

  btnSignup.addEventListener('click', () => {
    btnSignup.classList.add('active');
    btnLogin.classList.remove('active');
    signupForm.classList.add('active');
    loginForm.classList.remove('active');
  });

  await startCamera(video);
  await startCamera(video2);

  // LOGIN with location restriction
  document.getElementById('login-capture').addEventListener('click', async () => {
    const id = document.getElementById('login-id').value.trim();
    const password = document.getElementById('login-password').value;
    const msg = document.getElementById('login-msg');
    msg.textContent = '';

    if (!id || !password) {
      msg.textContent = 'enter id and password';
      return;
    }

    const image = captureImageFromVideo(video);
    msg.textContent = 'getting location...';

    navigator.geolocation.getCurrentPosition(async (position) => {
      const latitude = position.coords.latitude;
      const longitude = position.coords.longitude;

      // Location restriction check
      const distance = getDistanceFromLatLonInMeters(latitude, longitude, ALLOWED_LAT, ALLOWED_LON);
      if (distance > ALLOWED_RADIUS_METERS) {
        msg.style.color = '#b00';
        msg.textContent = 'You are outside the allowed location for login.';
        return;
      }

      msg.textContent = 'contacting server...';

      try {
        const res = await fetch('/api/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id, password, image, latitude, longitude })
        });
        const data = await res.json();

        if (data.success) {
          if (data.recognized) {
            msg.style.color = 'green';
            msg.textContent = 'Face recognized — attendance marked.';
          } else {
            msg.style.color = 'orange';
            msg.textContent = 'Face did not match registered face.';
          }
        } else {
          msg.style.color = '#b00';
          msg.textContent = `Error: ${data.error || 'unknown'}`;
        }
      } catch (err) {
        console.error(err);
        msg.style.color = '#b00';
        msg.textContent = 'network error: could not reach server';
      }
    }, (error) => {
      msg.style.color = '#b00';
      msg.textContent = 'Location access is required to mark attendance.';
      console.error('Geolocation error:', error);
    });
  });

  // SIGNUP with location restriction
  let signupCapturedImage = null;
  const signupMsg = document.getElementById('signup-msg');

  document.getElementById('signup-capture').addEventListener('click', () => {
    const id = document.getElementById('signup-id').value.trim();
    const password = document.getElementById('signup-password').value;
    if (!id || !password) {
      signupMsg.textContent = 'enter id and password first';
      return;
    }
    signupCapturedImage = captureImageFromVideo(video2);
    signupMsg.style.color = '#006';
    signupMsg.textContent = 'Face captured. Now enter owner security value to complete signup.';
    document.getElementById('owner-secret-step').style.display = 'block';
  });

  document.getElementById('complete-signup').addEventListener('click', async () => {
    const id = document.getElementById('signup-id').value.trim();
    const password = document.getElementById('signup-password').value;
    const domain = document.getElementById('signup-domain').value;
    const owner_secret = document.getElementById('owner-secret').value;
    const msg = signupMsg;
    msg.textContent = '';

    if (!signupCapturedImage) {
      msg.textContent = 'capture face first';
      return;
    }
    if (!owner_secret) {
      msg.textContent = 'enter owner security value';
      return;
    }

    msg.style.color = '#006';
    msg.textContent = 'getting location...';

    navigator.geolocation.getCurrentPosition(async (position) => {
      const latitude = position.coords.latitude;
      const longitude = position.coords.longitude;

      // Location restriction check
      const distance = getDistanceFromLatLonInMeters(latitude, longitude, ALLOWED_LAT, ALLOWED_LON);
      if (distance > ALLOWED_RADIUS_METERS) {
        msg.style.color = '#b00';
        msg.textContent = 'You are outside the allowed location for signup.';
        return;
      }

      msg.textContent = 'creating account...';

      try {
        const res = await fetch('/api/signup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id, password, domain, owner_secret, image: signupCapturedImage, latitude, longitude })
        });
        const data = await res.json();

        if (data.success) {
          msg.style.color = 'green';
          msg.textContent = 'Account created successfully. Owner has been notified.';
          document.getElementById('signup-id').value = '';
          document.getElementById('signup-password').value = '';
          document.getElementById('owner-secret').value = '';
          document.getElementById('owner-secret-step').style.display = 'none';
          signupCapturedImage = null;
        } else {
          msg.style.color = '#b00';
          msg.textContent = `Error: ${data.error || 'unknown'}`;
        }
      } catch (err) {
        console.error(err);
        msg.style.color = '#b00';
        msg.textContent = 'network error: could not reach server';
      }
    }, (error) => {
      msg.style.color = '#b00';
      msg.textContent = 'Location access is required to sign up.';
      console.error('Geolocation error:', error);
    });
  });

});
