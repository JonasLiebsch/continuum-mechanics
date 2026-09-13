// ------------------------------------------------------------
// FLEXURE CLASSROOM — configuration
// ------------------------------------------------------------
// 1) Replace firebaseConfig with the object Firebase gives you for your web app.
// 2) Change currentSession for a new class/year; old data remain archived.
// 3) classPassword is intentionally only a low-friction classroom password.
//    It is visible in the page source and is NOT a real security boundary.

window.FLEXURE_CONFIG = {
  firebaseConfig: {
    apiKey: "AIzaSyAyqG1tqcHcPbwld0lSEiSNHKEH_r8AHnU",
    authDomain: "coontinum-mechanics-flexure.firebaseapp.com",
    projectId: "coontinum-mechanics-flexure",
    storageBucket: "coontinum-mechanics-flexure.firebasestorage.app",
    messagingSenderId: "240730169603",
    appId: "1:240730169603:web:b8488d50b35b870a2e0936"
  },

  currentSession: "2026-geodynamics",
  classPassword: "flexure2026",

  // Starting model values. q is uniform load per area [N m^-2],
  // D is plate rigidity per unit width [N m].
  initialQ: 0.80,
  initialD: 2.5e-4,

  qMin: 0.0,
  qMax: 5.0,
  qStep: 0.01,

  // D slider is logarithmic: 10^dExponent [N m]
  dExponentMin: -5.0,
  dExponentMax: -2.0,
  dExponentStep: 0.01,

  // Used only for the empty graph before the first measurement exists.
  emptyGraphLengthCm: 40
};
