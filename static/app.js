let activeCollection = "studies";
let allStudies = [];

document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        activeCollection = tab.dataset.collection;
    });
});

document.getElementById("search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch();
});

async function loadStats() {
    const res = await fetch("/api/stats");
    const data = await res.json();
    document.getElementById("stat-studies").textContent = data.studies;
    document.getElementById("stat-runs").textContent = data.runs;
    document.getElementById("stat-papers").textContent = data.papers;
}

async function loadFilters() {
    const res = await fetch("/api/filters");
    const data = await res.json();
    fillSelect("filter-category", data.categories);
    fillSelect("filter-instrument", data.instruments);
    fillSelect("filter-location", data.locations);
}

function fillSelect(id, items) {
    const sel = document.getElementById(id);
    const current = sel.value;
    sel.innerHTML = '<option value="">All</option>';
    items.forEach(item => {
        if (item) {
            const opt = document.createElement("option");
            opt.value = item;
            opt.textContent = item;
            sel.appendChild(opt);
        }
    });
    sel.value = current;
}

async function loadAllStudies() {
    const res = await fetch("/api/all_studies");
    const data = await res.json();
    allStudies = data.studies;
    renderStudies(allStudies);
}

function renderStudies(studies) {
    const grid = document.getElementById("studies-grid");
    grid.innerHTML = "";
    studies.sort((a, b) => (a.id > b.id ? 1 : -1));
    studies.forEach(s => {
        const meta = s.metadata;
        const card = document.createElement("div");
        card.className = "study-card";
        card.onclick = () => openStudy(s.id);
        card.innerHTML = `
            <div class="study-card-accession">${s.id}</div>
            <div class="study-card-title">${meta.study_title || "No title"}</div>
            <div class="study-card-stats">
                <span>${meta.n_runs || 0} runs</span>
                <span>${meta.n_papers || 0} papers</span>
                ${meta.has_analysis_plan ? "<span>Has plan</span>" : ""}
            </div>
        `;
        grid.appendChild(card);
    });
}

async function filterStudies() {
    const category = document.getElementById("filter-category").value;
    const instrument = document.getElementById("filter-instrument").value;
    const location = document.getElementById("filter-location").value;

    if (!category && !instrument && !location) {
        renderStudies(allStudies);
        return;
    }

    const body = {};
    if (category) body.category = category;
    if (instrument) body.instrument = instrument;
    if (location) body.location = location;

    const res = await fetch("/api/filtered_runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    const data = await res.json();

    const accessionSet = new Set();
    data.runs.forEach(r => accessionSet.add(r.metadata.accession));

    const filtered = allStudies.filter(s => accessionSet.has(s.id));
    renderStudies(filtered);
}

async function doSearch() {
    const input = document.getElementById("search-input").value.trim();
    if (!input) return;

    const section = document.getElementById("results-section");
    section.style.display = "block";
    document.getElementById("results-list").innerHTML = '<div class="loading">Searching</div>';
    document.getElementById("results-title").textContent = `Search: "${input}"`;
    document.getElementById("results-count").textContent = "";

    const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: input, collection: activeCollection, n: 10 })
    });
    const data = await res.json();

    document.getElementById("results-count").textContent = `${data.total} results`;
    const list = document.getElementById("results-list");
    list.innerHTML = "";

    if (!data.results || data.results.length === 0) {
        list.innerHTML = '<div class="loading">No results found</div>';
        return;
    }

    data.results.forEach(r => {
        const card = document.createElement("div");
        card.className = "result-card";

        let title = r.id;
        let metaTags = [];

        if (activeCollection === "studies") {
            title = r.metadata.study_title || r.id;
            if (r.metadata.n_runs) metaTags.push(`${r.metadata.n_runs} runs`);
            if (r.metadata.n_papers) metaTags.push(`${r.metadata.n_papers} papers`);
            card.onclick = () => openStudy(r.id);
        } else if (activeCollection === "runs") {
            title = r.metadata.run_accession || r.id;
            if (r.metadata.study_title) metaTags.push(r.metadata.study_title);
            if (r.metadata.organism) metaTags.push(r.metadata.organism);
            if (r.metadata.instrument) metaTags.push(r.metadata.instrument);
            if (r.metadata.location) metaTags.push(r.metadata.location);
            if (r.metadata.category) metaTags.push(r.metadata.category);
            card.onclick = () => openStudy(r.metadata.accession);
        } else {
            title = r.metadata.filename || r.id;
            if (r.metadata.study_title) metaTags.push(r.metadata.study_title);
        }

        const tagsHtml = metaTags.map(t => `<span class="meta-tag">${t}</span>`).join("");

        card.innerHTML = `
            <div class="result-card-header">
                <div class="result-card-title">${title}</div>
                <div class="result-score">Score: ${r.score}</div>
            </div>
            <div class="result-card-meta">${tagsHtml}</div>
            <div class="result-card-preview">${r.preview}</div>
        `;
        list.appendChild(card);
    });

    section.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function openStudy(accession) {
    const overlay = document.getElementById("modal-overlay");
    const content = document.getElementById("modal-content");
    overlay.style.display = "flex";
    content.innerHTML = '<div class="loading">Loading study details</div>';

    const res = await fetch(`/api/study/${accession}`);
    const data = await res.json();

    let runsHtml = "";
    if (data.runs && data.runs.length > 0) {
        runsHtml = `
            <div class="modal-section">
                <h3>Sequencing Runs (${data.runs.length})</h3>
                <div style="overflow-x:auto;">
                    <table class="run-table">
                        <tr>
                            <th>Run</th>
                            <th>Organism</th>
                            <th>Instrument</th>
                            <th>Location</th>
                            <th>Layout</th>
                        </tr>
                        ${data.runs.map(rm => {
                            const m = rm.metadata;
                            return `<tr>
                                <td>${rm.id}</td>
                                <td>${m.organism || "-"}</td>
                                <td>${m.instrument || "-"}</td>
                                <td>${m.location || "-"}</td>
                                <td>${m.layout || "-"}</td>
                            </tr>`;
                        }).join("")}
                    </table>
                </div>
            </div>
        `;
    }

    let papersHtml = "";
    if (data.papers && data.papers.length > 0) {
        papersHtml = `
            <div class="modal-section">
                <h3>Research Papers</h3>
                <div class="modal-tag-list">
                    ${data.papers.map(p => `<span class="modal-tag">${p.filename}</span>`).join("")}
                </div>
            </div>
        `;
    }

    const meta = data.metadata || {};
    content.innerHTML = `
        <h2>${accession}</h2>
        <p class="subtitle">${meta.study_title || ""}</p>

        <div class="modal-section">
            <h3>Overview</h3>
            <div class="modal-tag-list">
                <span class="modal-tag">Runs: ${meta.n_runs || 0}</span>
                <span class="modal-tag">Papers: ${meta.n_papers || 0}</span>
                ${meta.has_analysis_plan ? '<span class="modal-tag">Has Analysis Plan</span>' : ""}
            </div>
        </div>

        ${runsHtml}
        ${papersHtml}

        <div class="modal-section">
            <h3>Full Document Preview</h3>
            <pre style="white-space:pre-wrap;word-wrap:break-word;color:#8b949e;font-size:0.85em;max-height:300px;overflow-y:auto;background:#0d1117;padding:12px;border-radius:8px;">${data.document || "No document content available"}</pre>
        </div>
    `;
}

function closeModal() {
    document.getElementById("modal-overlay").style.display = "none";
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
});

loadStats();
loadFilters();
loadAllStudies();
