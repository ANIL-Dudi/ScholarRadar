
"use strict";

// ============================================================
// ScholarRadar — frontend/script.js
// ============================================================

var API = "http://localhost:8000";

var INTERESTS = [
  ["ml", "Machine learning"],
  ["bio", "Biology"],
  ["physics", "Physics"],
  ["econ", "Economics"],
  ["oss", "Open source"],
  ["eng", "Engineering"]
];

// DEMO ONLY: Verify deadlines and programme details on official websites.
// These are sample records, not live API results.
var DEMO = [
  {
    id: 1,
    title: "DAAD WISE Research Internship",
    org: "Germany",
    funding: "Check official funding terms",
    due: "2026-12-01",
    base: 84,
    tags: ["ml", "eng", "physics"],
    why: "Your Python and machine learning experience may match relevant research projects.",
    docs: ["CV", "Transcript", "Recommendation letter", "Statement of purpose"],
    url: "https://www.daad.de"
  },
  {
    id: 2,
    title: "Mitacs Globalink Research Internship",
    org: "Canada",
    funding: "Check current programme terms",
    due: "2026-11-20",
    base: 80,
    tags: ["ml", "bio", "eng", "econ"],
    why: "Explore research opportunities related to your academic interests.",
    docs: ["CV", "Transcript", "Project ranking form", "Supervisor ranking"],
    url: "https://www.mitacs.ca"
  },
  {
    id: 3,
    title: "Summer Research Fellowship",
    org: "India",
    funding: "Verify stipend and eligibility",
    due: "2026-11-12",
    base: 76,
    tags: ["physics", "bio", "ml"],
    why: "Explore science and engineering research fellowship opportunities.",
    docs: ["CV", "Marksheets", "Recommendation letter"],
    url: "https://www.ias.ac.in"
  },
  {
    id: 4,
    title: "Google Summer of Code",
    org: "Remote",
    funding: "Stipend subject to programme rules",
    due: "2027-03-25",
    base: 70,
    tags: ["oss", "ml", "eng"],
    why: "Explore open-source development and mentorship opportunities.",
    docs: ["CV", "Project proposal", "GitHub profile"],
    url: "https://summerofcode.withgoogle.com"
  },
  {
    id: 5,
    title: "OIST Research Internship",
    org: "Japan",
    funding: "Verify current programme terms",
    due: "2026-10-15",
    base: 88,
    tags: ["bio", "physics", "ml"],
    why: "Potential research fit. This sample deadline has passed; check for a new cycle.",
    docs: ["CV", "Transcript", "Recommendation letter"],
    url: "https://www.oist.jp"
  }
];

var selectedInterests = { ml: true };
var opportunities = [];

// ============================================================
// Utilities
// ============================================================

function $(id) {
  return document.getElementById(id);
}

function setStatus(message) {
  var element = $("status");
  if (!element) return;
  element.textContent = message;
  element.classList.toggle("warn", /^SAMPLE DATA/.test(message));
}

function setHint(message) {
  var element = $("fhint");
  if (element) element.textContent = message;
}

function escapeHTML(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
    return {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[char];
  });
}

function safeUrl(value) {
  try {
    var parsed = new URL(String(value || ""));

    if (parsed.protocol === "https:" || parsed.protocol === "http:") {
      return parsed.href;
    }
  } catch (error) {
    // Invalid URL.
  }

  return null;
}

// Return the number of calendar days until a valid YYYY-MM-DD deadline.
// Returns null for missing or invalid dates.
function daysLeft(dateString) {
  var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(
    String(dateString || "")
  );

  if (!match) return null;

  var year = Number(match[1]);
  var month = Number(match[2]);
  var day = Number(match[3]);

  var dueDate = new Date(Date.UTC(year, month - 1, day));

  if (
    dueDate.getUTCFullYear() !== year ||
    dueDate.getUTCMonth() !== month - 1 ||
    dueDate.getUTCDate() !== day
  ) {
    return null;
  }

  var now = new Date();

  var today = Date.UTC(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
  );

  return Math.round((dueDate.getTime() - today) / 86400000);
}

// Heuristic score, not a validated AI eligibility prediction.
function calculateScore(item) {
  var tags = Array.isArray(item.tags) ? item.tags : [];

  var matchCount = tags.filter(function (tag) {
    return !!selectedInterests[tag];
  }).length;

  var base = Number(item.base);
  if (!Number.isFinite(base)) base = 50;

  var hasSelectedInterests = Object.keys(selectedInterests).some(
    function (key) {
      return selectedInterests[key];
    }
  );

  var result = base + matchCount * 5;

  if (hasSelectedInterests && matchCount === 0) {
    result -= 14;
  }

  return Math.max(30, Math.min(99, result));
}

function getRankedOpportunities() {
  return opportunities.map(function (item) {
    var copy = Object.assign({}, item);

    copy.score = calculateScore(copy);
    copy.left = daysLeft(copy.due);
    copy.closed = copy.left !== null && copy.left < 0;

    return copy;
  }).sort(function (a, b) {
    return Number(a.closed) - Number(b.closed) ||
      b.score - a.score;
  });
}

function highlight(id, enabled) {
  var card = $("card-" + id);
  var point = $("point-" + id);

  if (card) card.classList.toggle("hl", enabled);
  if (point) point.classList.toggle("hl", enabled);
}

// ============================================================
// Interest selector
// ============================================================

function renderInterests() {
  var container = $("chips");
  if (!container) return;

  container.replaceChildren();

  INTERESTS.forEach(function (interest) {
    var key = interest[0];
    var button = document.createElement("button");

    button.type = "button";
    button.className = "chip";
    button.textContent = interest[1];

    button.setAttribute(
      "aria-pressed",
      String(!!selectedInterests[key])
    );

    button.addEventListener("click", function () {
      selectedInterests[key] = !selectedInterests[key];

      button.setAttribute(
        "aria-pressed",
        String(!!selectedInterests[key])
      );

      if (opportunities.length) {
        renderOpportunities();
      }
    });

    container.appendChild(button);
  });
}

// ============================================================
// Opportunity cards and radar
// ============================================================

function renderOpportunities() {
  var list = $("list");
  var blips = $("blips");

  if (!list || !blips) {
    setStatus('HTML must contain elements with IDs "list" and "blips".');
    return;
  }

  list.replaceChildren();
  blips.replaceChildren();

  var items = getRankedOpportunities();

  items.forEach(function (item, index) {
    var dueText;
    var dueDetail;

    if (item.left === null) {
      dueText = "Not stated";
      dueDetail = "Rolling or not listed";
    } else if (item.closed) {
      dueText = "Past deadline";
      dueDetail = "Ended " + item.due;
    } else {
      dueText = item.left === 0 ? "Today" : item.left === 1 ? "Tomorrow" : item.left + " days";
      dueDetail = "Deadline: " + item.due;
    }

    var card = document.createElement("article");

    card.className = "card" + (item.closed ? " closed" : "");
    card.id = "card-" + item.id;

    var url = safeUrl(item.url);
    var documents = Array.isArray(item.docs) ? item.docs : [];

    card.innerHTML =
      '<div class="score" style="--s:' + item.score + '">' +
        '<span>' + item.score + '</span>' +
      '</div>' +

      '<div>' +
        '<h3>' + escapeHTML(item.title || "Untitled opportunity") + '</h3>' +
        '<div class="meta">' +
          escapeHTML(item.org || "Organization unavailable") +
          ' · ' + escapeHTML(item.funding || "Funding unverified") +
        '</div>' +
        '<p class="why">' + escapeHTML(item.why || "") + '</p>' +
        '<button class="more" type="button" aria-expanded="false">' +
          'Documents and link' +
        '</button>' +
        '<button class="remind" type="button" aria-pressed="false">Remind me</button>' +
      '</div>' +

      '<div class="due' +
        (item.left !== null && !item.closed && item.left <= 14
          ? ' soon' : '') +
        '">' +
        '<b>' + dueText + '</b>' +
        '<small>' + escapeHTML(dueDetail) + '</small>' +
      '</div>' +

      '<div class="extra">' +
        '<ul>' +
          documents.map(function (doc, docIndex) {
            return '<li><label><input type="checkbox" id="doc-' +
              escapeHTML(item.id) + '-' + docIndex + '"> ' +
              escapeHTML(doc) + '</label></li>';
          }).join("") +
        '</ul>' +

        (url
          ? '<a href="' + escapeHTML(url) +
            '" target="_blank" rel="noopener noreferrer">' +
            'Open source page</a>'
          : '<p>Source link unavailable. Verify independently.</p>') +
      '</div>';

    wireReminder(card.querySelector(".remind"), item);
    var moreButton = card.querySelector(".more");

    moreButton.addEventListener("click", function () {
      var expanded = card.classList.toggle("open");
      moreButton.setAttribute("aria-expanded", String(expanded));
    });

    card.addEventListener("mouseenter", function () {
      highlight(item.id, true);
    });

    card.addEventListener("mouseleave", function () {
      highlight(item.id, false);
    });

    list.appendChild(card);

    // Radar position.
    var radius = 48 * (1 - (item.score - 30) / 80) * 0.9 + 4;
    var angle = (index * 137.5 + 20) * Math.PI / 180;

    var point = document.createElement("button");

    point.type = "button";
    point.className = "blip" + (item.closed ? " closed" : "");
    point.id = "point-" + item.id;

    point.setAttribute(
      "aria-label",
      (item.title || "Opportunity") +
      ", " + item.score + " percent estimated match"
    );

    point.style.left = (50 + radius * Math.cos(angle)) + "%";
    point.style.top = (50 + radius * Math.sin(angle)) + "%";

    point.addEventListener("click", function () {
      card.scrollIntoView({
        behavior: "smooth",
        block: "center"
      });

      highlight(item.id, true);

      window.setTimeout(function () {
        highlight(item.id, false);
      }, 1600);
    });

    blips.appendChild(point);

    // Stagger the radar animation.
    window.setTimeout(function () {
      point.classList.add("on");
    }, 100 + index * 100);
  });
}

// ============================================================
// CV upload — PDF and TXT only
// ============================================================

function setupCVUpload() {
  var input = $("cv");
  if (!input) return;

  input.addEventListener("change", async function (event) {
    var file = event.target.files && event.target.files[0];
    if (!file) return;

    if (!/\.(pdf|txt)$/i.test(file.name)) {
      setHint("Please select a PDF or TXT file.");
      input.value = "";
      return;
    }

    var fileName = $("fname");
    if (fileName) fileName.textContent = file.name;

    setHint(
      Math.max(1, Math.round(file.size / 1024)) +
      " KB · Selected"
    );

    if (!API) {
      setHint("CV selected. Backend URL is not configured.");
      return;
    }

    try {
      setHint("Uploading CV...");

      var form = new FormData();
      form.append("cv", file);

      form.append(
        "interests",
        Object.keys(selectedInterests)
          .filter(function (key) {
            return selectedInterests[key];
          })
          .join(",")
      );

      var response = await fetch(API + "/api/profile", {
        method: "POST",
        body: form
      });

      if (!response.ok) {
        throw new Error("Upload failed: HTTP " + response.status);
      }

      setHint("CV uploaded successfully.");
    } catch (error) {
      console.error("CV upload failed:", error);
      setHint("Upload failed. Check the backend and browser console.");
    }
  });
}

// ============================================================
// Opportunity discovery
// ============================================================

async function scanOpportunities() {
  var scanButton = $("scan");
  var radar = $("radar");
  var feed = $("feed");

  if (scanButton) scanButton.disabled = true;
  if (radar) radar.classList.remove("idle");

  // Reset these values on every scan.
  var usingDemo = false;
  var demoReason = "";

  setStatus("Searching the live web with TinyFish (30-90 seconds)...");

  opportunities = [];

  if ($("list")) $("list").replaceChildren();
  if ($("blips")) $("blips").replaceChildren();

  var interests = Object.keys(selectedInterests)
    .filter(function (key) {
      return selectedInterests[key];
    })
    .join(",");

  try {
    var results;

    if (API) {
      var endpoint = API + "/api/opportunities?refresh=true&interests=" +
        encodeURIComponent(interests);

      try {
        var response = await fetch(endpoint);

        if (!response.ok) {
          throw new Error("Backend returned HTTP " + response.status);
        }

        results = await response.json();

        if (!Array.isArray(results) || results.length === 0) {
          throw new Error("Backend returned no opportunities");
        }
      } catch (error) {
        console.warn(
          "Backend unavailable; using demo data instead:",
          error
        );

        results = DEMO;
        usingDemo = true;
        demoReason = error.message || "Unknown backend error";
      }
    } else {
      results = DEMO;
      usingDemo = true;
      demoReason = "backend not configured";
    }

    opportunities = results;

    renderOpportunities();

    if (radar) radar.classList.add("idle");

    if (usingDemo) {
      setStatus(
        "SAMPLE DATA (" + (demoReason || "backend not configured") +
        "). Verify all details on official sites."
      );
    } else {
      setStatus(
        opportunities.length +
        " opportunities ranked. Verify deadlines on official sites."
      );
    }

    var note = $("note");
    if (note) {
      note.textContent = usingDemo
        ? "Sample data is shown (" + (demoReason || "backend not configured") + ")."
        : "Live results from the backend. Verify deadlines on official sites.";
    }

    if (feed) {
      feed.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    }
  } catch (error) {
    console.error("Opportunity scan failed:", error);

    setStatus(
      "Could not display opportunities. Check your HTML and console."
    );
  } finally {
    if (scanButton) scanButton.disabled = false;
  }
}

// ============================================================
// Theme toggle
// ============================================================

function setupTheme() {
  var button = $("theme");
  if (!button) return;

  button.addEventListener("click", function () {
    var root = document.documentElement;
    var current = root.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    root.setAttribute("data-theme", current === "dark" ? "light" : "dark");
  });
}

// ============================================================
// Initialization
// ============================================================

// ============================================================
// Email deadline alerts
// ============================================================

function setupAlerts() {
  var header = document.querySelector("#feed .fh");
  if (!header || !API) return;

  var bar = document.createElement("div");
  bar.className = "alertbar";

  var button = document.createElement("button");
  button.type = "button";
  button.className = "alertbtn";
  button.textContent = "Email my reminders now";

  var message = document.createElement("span");
  message.className = "alertmsg";
  message.setAttribute("role", "status");
  message.textContent =
    "Reminders are also sent automatically at 9:00 AM IST, " +
    "14, 7, 3 and 1 days before a deadline.";

  button.addEventListener("click", async function () {
    button.disabled = true;
    message.textContent = "Sending...";

    try {
      var response = await fetch(API + "/api/alerts/digest?days=30", {
        method: "POST"
      });

      if (!response.ok) throw new Error("HTTP " + response.status);

      var result = await response.json();

      if (result.sent) {
        message.textContent =
          "Email sent with " + result.count +
          " upcoming deadline(s). Check your inbox.";
      } else if (result.count === 0) {
        message.textContent =
          result.reason || "No upcoming deadlines in the next 30 days.";
      } else {
        message.textContent =
          "Could not send. Check the email settings in Backend/.env.";
      }
    } catch (error) {
      console.error("Alert request failed:", error);
      message.textContent =
        "Could not reach the backend (" + error.message + ").";
    } finally {
      button.disabled = false;
    }
  });

  bar.appendChild(button);
  bar.appendChild(message);
  header.appendChild(bar);
}

// ============================================================
// Per-opportunity email reminders
// ============================================================

var reminders = {};

function paintReminder(button, on) {
  button.setAttribute("aria-pressed", String(on));
  button.textContent = on ? "Reminder on \u2713" : "Remind me";
  button.title = on
    ? "You will be emailed 14, 7, 3 and 1 days before the deadline. Click to turn off."
    : "Email me before this deadline";
}

async function loadReminders() {
  if (!API) return;

  try {
    var response = await fetch(API + "/api/reminders");
    if (!response.ok) throw new Error("HTTP " + response.status);

    var rows = await response.json();
    reminders = {};
    rows.forEach(function (row) { reminders[row.url] = true; });

    document.querySelectorAll("button.remind[data-url]").forEach(function (button) {
      paintReminder(button, !!reminders[button.getAttribute("data-url")]);
    });
  } catch (error) {
    console.warn("Could not load reminders:", error);
  }
}

function wireReminder(button, item) {
  if (!button) return;

  var url = safeUrl(item.url);

  if (!API) {
    button.disabled = true;
    button.textContent = "Alerts need the backend";
    return;
  }
  if (item.closed) {
    button.disabled = true;
    button.textContent = "Deadline passed";
    return;
  }
  if (!url) {
    button.disabled = true;
    button.textContent = "No source link";
    return;
  }

  // No deadline found on the page: let the user type the real one.
  var dateInput = null;
  if (item.left === null) {
    dateInput = document.createElement("input");
    dateInput.type = "date";
    dateInput.className = "remind-date";
    dateInput.title = "Type the closing date from the official page";
    dateInput.setAttribute("aria-label", "Deadline for " + (item.title || "this opportunity"));
    dateInput.style.setProperty("display", "inline-block", "important");
    dateInput.style.margin = "0 8px 8px 0";
    dateInput.style.padding = "6px 8px";
    dateInput.style.border = "1px solid #888";
    dateInput.style.borderRadius = "6px";
    window.setTimeout(function () {
      if (!reminders[url]) button.textContent = "Remind me (pick a date)";
    }, 0);
    button.parentNode.insertBefore(dateInput, button);
  }

  button.setAttribute("data-url", url);
  paintReminder(button, !!reminders[url]);

  button.addEventListener("click", async function () {
    var turnOn = button.getAttribute("aria-pressed") !== "true";
    var deadline = dateInput ? dateInput.value : item.due;

    if (turnOn) {
      var left = daysLeft(deadline);
      if (left === null || left < 0) {
        button.textContent = "Pick a future deadline first";
        return;
      }
    }

    button.disabled = true;
    button.textContent = turnOn ? "Saving..." : "Removing...";

    try {
      var response = turnOn
        ? await fetch(API + "/api/reminders", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              url: url,
              title: item.title || "",
              deadline: deadline
            })
          })
        : await fetch(API + "/api/reminders?url=" + encodeURIComponent(url), {
            method: "DELETE"
          });

      if (!response.ok) throw new Error("HTTP " + response.status);

      if (turnOn) { reminders[url] = true; } else { delete reminders[url]; }
      paintReminder(button, turnOn);
      if (dateInput) dateInput.hidden = turnOn;
    } catch (error) {
      console.error("Reminder request failed:", error);
      paintReminder(button, !turnOn);
      button.textContent = "Could not save. Try again";
    } finally {
      button.disabled = false;
    }
  });
}

function wireReminderOld(button, item) {

   if (!button) return;

  var url = safeUrl(item.url);

  if (!API) {
    button.disabled = true;
    button.textContent = "Alerts need the backend";
    return;
  }
  if (item.left === null) {
    button.disabled = true;
    button.textContent = "No deadline to track";
    return;
  }
  if (item.closed) {
    button.disabled = true;
    button.textContent = "Deadline passed";
    return;
  }
  if (!url) {
    button.disabled = true;
    button.textContent = "No source link";
    return;
  }

  button.setAttribute("data-url", url);
  paintReminder(button, !!reminders[url]);

  button.addEventListener("click", async function () {
    var turnOn = button.getAttribute("aria-pressed") !== "true";
    button.disabled = true;
    button.textContent = turnOn ? "Saving..." : "Removing...";

    try {
      var response = turnOn
        ? await fetch(API + "/api/reminders", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              url: url,
              title: item.title || "",
              deadline: item.due
            })
          })
        : await fetch(API + "/api/reminders?url=" + encodeURIComponent(url), {
            method: "DELETE"
          });

      if (!response.ok) throw new Error("HTTP " + response.status);

      if (turnOn) { reminders[url] = true; } else { delete reminders[url]; }
      paintReminder(button, turnOn);
    } catch (error) {
      console.error("Reminder request failed:", error);
      paintReminder(button, !turnOn);
      button.textContent = "Could not save. Try again";
    } finally {
      button.disabled = false;
    }
  });
}

// ============================================================
// Find new opportunities (TinyFish search + deadline extraction)
// ============================================================

function setupFinder() {
  var header = document.querySelector("#feed .fh");
  if (!header || !API) return;

  var bar = document.createElement("div");
  bar.className = "findbar";

  var button = document.createElement("button");
  button.type = "button";
  button.className = "findbtn";
  button.textContent = "Find new opportunities";

  var message = document.createElement("span");
  message.className = "findmsg";
  message.setAttribute("role", "status");
  message.textContent =
    "Searches the web with TinyFish and reads each page for its deadline. " +
    "This takes a few minutes and uses TinyFish credits.";

  function poll() {
    fetch(API + "/api/discover/status")
      .then(function (r) { return r.json(); })
      .then(function (s) {
        if (s.running) {
          message.textContent =
            "Searching... " + s.queries_done + " of " + s.total +
            " searches done, " + s.added + " saved so far.";
          window.setTimeout(poll, 5000);
          return;
        }

        button.disabled = false;
        message.textContent = (s.error && !s.added)
          ? "Search failed: " + s.error
          : "Done. " + s.added + " opportunities saved. Updating the feed...";
        scanOpportunities();
      })
      .catch(function (error) {
        button.disabled = false;
        message.textContent = "Lost contact with the backend (" + error.message + ").";
      });
  }

  button.addEventListener("click", async function () {
    button.disabled = true;
    message.textContent = "Starting...";

    var picked = Object.keys(selectedInterests)
      .filter(function (key) { return selectedInterests[key]; })
      .join(",");

    try {
      var response = await fetch(
        API + "/api/discover/live?interests=" + encodeURIComponent(picked),
        { method: "POST" }
      );
      if (!response.ok) throw new Error("HTTP " + response.status);

      var result = await response.json();
      if (!result.started) {
        message.textContent = result.reason || "Could not start the search.";
      }
      poll();
    } catch (error) {
      console.error("Could not start discovery:", error);
      button.disabled = false;
      message.textContent = "Could not start the search (" + error.message + ").";
    }
  });

  bar.appendChild(button);
  bar.appendChild(message);
  header.appendChild(bar);
}

function initScholarRadar() {
  setupAlerts();
  loadReminders();
  setupFinder();
  renderInterests();
  setupCVUpload();
  setupTheme();

  var scanButton = $("scan");

  if (scanButton) {
    scanButton.addEventListener("click", scanOpportunities);
  } else {
    console.error('Missing required HTML element: id="scan".');
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initScholarRadar);
} else {
  initScholarRadar();
}




// ============================================================
// Manual reminder form (works for cards with no deadline)
// ============================================================

function setupManualReminder() {
  var header = document.querySelector("#feed .fh");
  var list = $("list");
  if (!header || !list || !API) return;

  var bar = document.createElement("div");
  bar.style.cssText = "display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0;";

  var label = document.createElement("strong");
  label.textContent = "Add a reminder:";

  var select = document.createElement("select");
  select.setAttribute("aria-label", "Opportunity");
  select.style.cssText = "max-width:100%;padding:6px 8px;";

  var dateBox = document.createElement("input");
  dateBox.type = "date";
  dateBox.setAttribute("aria-label", "Deadline");
  dateBox.style.cssText = "padding:6px 8px;";

  var button = document.createElement("button");
  button.type = "button";
  button.textContent = "Set reminder";

  var message = document.createElement("span");
  message.setAttribute("role", "status");
  message.textContent = "Pick an opportunity and its deadline from the official page.";

  function fill() {
    select.replaceChildren();
    var first = document.createElement("option");
    first.value = "";
    first.textContent = opportunities.length ? "Choose an opportunity..." : "Run a scan first";
    select.appendChild(first);

    opportunities.forEach(function (item) {
      var url = safeUrl(item.url);
      if (!url) return;
      var option = document.createElement("option");
      option.value = url;
      option.textContent = String(item.title || "Untitled").slice(0, 70);
      option.setAttribute("data-title", item.title || "");
      select.appendChild(option);
    });
  }

  button.addEventListener("click", async function () {
    var url = select.value;
    var chosen = select.options[select.selectedIndex];
    var title = chosen ? (chosen.getAttribute("data-title") || "") : "";
    var left = daysLeft(dateBox.value);

    if (!url) { message.textContent = "Choose an opportunity first."; return; }
    if (left === null || left < 0) { message.textContent = "Pick a deadline that is today or later."; return; }

    button.disabled = true;
    message.textContent = "Saving...";

    try {
      var response = await fetch(API + "/api/reminders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url, title: title, deadline: dateBox.value })
      });
      if (!response.ok) throw new Error("HTTP " + response.status);

      reminders[url] = true;
      message.textContent = "Reminder saved for " + dateBox.value +
        ". A confirmation email is on its way. You will also be emailed 14, 7, 3 and 1 days before.";
    } catch (error) {
      console.error("Manual reminder failed:", error);
      message.textContent = "Could not save (" + error.message + ").";
    } finally {
      button.disabled = false;
    }
  });

  bar.appendChild(label);
  bar.appendChild(select);
  bar.appendChild(dateBox);
  bar.appendChild(button);
  bar.appendChild(message);
  header.appendChild(bar);

  fill();
  new MutationObserver(fill).observe(list, { childList: true });
}

if (document.readyState === "complete") {
  setupManualReminder();
} else {
  window.addEventListener("load", setupManualReminder);
}
