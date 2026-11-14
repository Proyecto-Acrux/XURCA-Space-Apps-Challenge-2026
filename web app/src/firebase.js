
import { initializeApp } from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js';

import {
  getFirestore
} from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-firestore.js';

import {
  getAuth,
  onAuthStateChanged,
  signInAnonymously
} from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js';

// Configuración de nuestra aplicación Firebase
const firebaseConfig = {
  apiKey: 'AIzaSyA8LO5hJLM_0D4txzs5Si5D2DOs6LJV5Pw',
  authDomain: 'xurca-forum.firebaseapp.com',
  projectId: 'xurca-forum',
  storageBucket: 'xurca-forum.firebasestorage.app',
  messagingSenderId: '681626570835',
  appId: '1:681626570835:web:b96a82ddae10c6201336a6'
};

// Inicializar Firebase
const app = initializeApp(firebaseConfig);

// Inicializar servicios
export const db = getFirestore(app);
export const auth = getAuth(app);

// Iniciar sesión anónima automáticamente
export const authReady = new Promise((resolve, reject) => {
  const unsubscribe = onAuthStateChanged(auth, async (user) => {
    unsubscribe();

    if (user) {
      resolve(user);
      return;
    }

    try {
      const credential = await signInAnonymously(auth);
      resolve(credential.user);
    } catch (error) {
      reject(error);
    }
  }, reject);
});
