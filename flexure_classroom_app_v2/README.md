# Flexure Classroom App — cantilever version

A GitHub-Pages-friendly classroom tool for a paper-strip flexure experiment with one fixed end and a uniform transverse load.

## Physics implemented

The model is the Turcotte & Schubert cantilever solution for `q(x) = constant`:

```text
w(x) = (q x^2 / D) (x^2/24 - Lx/6 + L^2/4)
```

with `x=0` at the fixed end and `x=L` at the free end.

Boundary conditions:

```text
w(0) = 0
w'(0) = 0
w''(L) = 0
w'''(L) = 0
```

The largest deflection occurs at the free end:

```text
w(L) = q L^4 / (8 D)
```

The app uses downward deflection as positive.

For a plate strip, `q` is load per area and `D` is flexural rigidity per unit width. The same shape is the standard Euler-Bernoulli cantilever-beam solution if `q` is interpreted as line load and `D = EI`.

---

## What the app does

- Everyone shares measurements in real time through Firebase Firestore.
- Students need no Firebase/Google account: the webpage signs them in anonymously.
- Each measurement contains `L`, `x`, and `w` in cm.
- **Plate lengths are dynamic.** There is no fixed list in the configuration.
- As soon as the first point with a new `L` is added, a new `L = ... cm` tab appears for everyone.
- Students can correct `L`, `x`, or `w` for their own points, and can delete their own points.
- The `q` and `D` fit sliders remain local to each browser, so students can fit the same class data independently.
- The **All lengths** tab compares all currently measured lengths.
- Session data can be downloaded as JSON.
- JSON import and clearing a session use a simple classroom password from `config.js`.

### Important security note

The classroom password is intentionally **not secure**. It is visible in the public JavaScript configuration. Its purpose is only to stop accidental or zero-effort clearing/importing during class.

To make client-side clearing possible without an instructor account, the supplied Firestore rules allow any anonymously authenticated client to delete documents. A determined student who inspects the app could bypass the password. This is intentional for this low-risk classroom use case.

Normal edit controls are still ownership-based: the interface only lets students edit/delete their own measurements.

---

## 1. Preview before Firebase

The repository starts in **local preview mode** because `config.js` contains placeholder Firebase settings.

Run a small local server from the app directory:

```bash
python -m http.server 8000
```

then open:

```text
http://localhost:8000
```

Local preview stores measurements only in that browser via local storage.

---

## 2. Create Firebase project

In the Firebase console:

1. Create a project.
2. Add a **Web app**.
3. Copy its Firebase configuration object into `config.js`.
4. Create a **Cloud Firestore** database.
5. In **Authentication → Sign-in method**, enable **Anonymous** authentication.
6. In **Firestore → Rules**, paste `firestore.rules` and publish it.
7. In **Authentication → Settings → Authorized domains**, add the domain hosting the class page if needed, for example:

   ```text
   yourname.github.io
   ```

No instructor Firebase account is required in this version.

The Firebase web configuration/API key is expected to be public. Firestore rules control database access.

---

## 3. Configure the class

Edit `config.js`:

```js
currentSession: "2026-geodynamics",
classPassword: "flexure2026",
```

For a new class/year, change only the session name, e.g.:

```js
currentSession: "2027-geodynamics",
```

The old data remain in Firestore under the previous session.

There is **no `lengthsCm` list anymore**. Students create lengths simply by entering an `L` value with a measurement.

The `q` and `D` slider ranges can also be changed in `config.js`.

---

## 4. Put it on GitHub Pages

The live webpage needs these four files together:

```text
index.html
style.css
app.js
config.js
```

`firestore.rules` is deployed in the Firebase console; it does not need to be loaded by the webpage.

You can place the app in a subfolder of an existing GitHub Pages repository, for example:

```text
/
├── index.html
├── elasticity/
├── mohr/
└── flexure/
    ├── index.html
    ├── style.css
    ├── app.js
    └── config.js
```

Then link to `flexure/` from your main page.

GitHub Pages can serve the HTML/CSS/JavaScript directly; Firebase supplies the shared database/backend.

---

## 5. Classroom workflow

### Students

1. Open the shared page.
2. Enter a group name.
3. Enter `L`, `x`, and downward `w`.
4. The first measurement for a new `L` automatically creates its tab.
5. Add/correct/delete measurements.
6. Select an `L` tab and adjust `q` and `D` to fit the shared data.

### Save / restore / reset

- **Download session JSON** is available to everyone.
- Open **Instructor tools**.
- Enter the classroom password from `config.js`.
- Choose a JSON file and click **Import selected JSON** to restore archived measurements.
- To clear the current session, also type the current session name and confirm.

---

## Data structure

Measurements are stored at:

```text
sessions/{SESSION_ID}/measurements/{AUTO_ID}
```

Each document contains approximately:

```json
{
  "Lcm": 30,
  "xCm": 12.0,
  "wCm": 2.4,
  "groupName": "Group 4",
  "ownerUid": "anonymous-firebase-uid"
}
```
