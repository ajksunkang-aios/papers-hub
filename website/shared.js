const NOISE_HOSTS = [
  "google.com",
  "scholar.google",
  "semanticscholar.org",
  "scholar.archive.org",
  "citeseerx.ist.psu.edu",
  "pubpeer.com",
  "bsky.app",
  "reddit.com",
  "bibsonomy.org",
  "linkedin.com",
];

/** arXiv category badge, e.g. cs.OS -> arXiv.CS.OS */
export function formatArxivSourceLabel(category) {
  if (!category) return "arXiv";
  const m = String(category).match(/^cs\.(.+)$/i);
  if (m) return `arXiv.CS.${m[1]}`;
  return `arXiv.${category}`;
}

/** Monthly top picks: always badge by crawl feed (cs.OS / cs.CL), not primary_category. */
export function formatTopArxivBadge(pick) {
  const feed = pick.source_feed;
  if (feed === "cs.OS" || feed === "cs.CL") {
    return formatArxivSourceLabel(feed);
  }
  return formatArxivSourceLabel(pick.primary_category);
}

export function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const TZ_UTC8 = "Asia/Shanghai";

export function formatGeneratedAt(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateUtc8(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: TZ_UTC8,
  });
}

export function formatGeneratedAtUtc8(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: TZ_UTC8,
  });
}

export function isProceedingsRecord(paper, meta) {
  const keys = meta.skip_dblp_keys || [];
  if (paper.dblp_key && keys.includes(paper.dblp_key)) return true;

  const patterns = meta.skip_title_patterns || [];
  return patterns.some((pat) => new RegExp(pat, "i").test(paper.title));
}

export function usefulLinks(eeLinks) {
  if (!eeLinks?.length) return [];
  const seen = new Set();
  return eeLinks.filter((url) => {
    try {
      const host = new URL(url).hostname.replace(/^www\./, "");
      if (NOISE_HOSTS.some((h) => host.includes(h))) return false;
      if (url.includes("?view=bibtex") || url.endsWith(".bib")) return false;
      if (/\.(ris|nt|ttl|rdf|xml|txt)$/.test(url)) return false;
      if (seen.has(url)) return false;
      seen.add(url);
      return true;
    } catch {
      return false;
    }
  });
}

export function primaryLink(links, linkPriority = []) {
  const priorities = linkPriority.length
    ? linkPriority
    : ["usenix.org", "doi.acm.org", "dl.acm.org", "dblp.org"];

  for (const host of priorities) {
    const hit = links.find((u) => u.includes(host));
    if (hit) return hit;
  }
  return links[0];
}

export function linkLabel(url) {
  if (url.includes("usenix.org")) return "USENIX";
  if (url.includes("acm.org")) return "ACM";
  if (url.includes("dblp.org")) return "dblp";
  return "Link";
}

export function preparePapers(data) {
  return data.papers
    .filter((p) => !isProceedingsRecord(p, data))
    .sort((a, b) => a.title.localeCompare(b.title));
}

export function renderStats(papers, meta, statsEl) {
  const authors = new Set();
  for (const p of papers) {
    for (const a of p.authors) authors.add(a);
  }

  statsEl.innerHTML = `
    <div>
      <dt>Papers</dt>
      <dd>${papers.length}</dd>
    </div>
    <div>
      <dt>Authors</dt>
      <dd>${authors.size}</dd>
    </div>
    <div>
      <dt>Year</dt>
      <dd>${meta.year}</dd>
    </div>
  `;
}

export function renderPaperList(papers, meta, listEl, query = "") {
  const q = query.trim().toLowerCase();
  const filtered = papers.filter((p) => {
    if (!q) return true;
    const hay = `${p.title} ${p.authors.join(" ")}`.toLowerCase();
    return hay.includes(q);
  });

  if (!filtered.length) {
    listEl.innerHTML = '<p class="empty">No papers match your search.</p>';
    return 0;
  }

  const priority = meta.link_priority || [];
  listEl.innerHTML = filtered
    .map((paper, index) => {
      const links = usefulLinks(paper.ee_links);
      const main = primaryLink(links, priority);
      const titleHtml = main
        ? `<a href="${escapeHtml(main)}" target="_blank" rel="noopener">${escapeHtml(paper.title)}</a>`
        : escapeHtml(paper.title);

      const authorText = escapeHtml(paper.authors.join(", ") || "-");
      const linkItems = links
        .slice(0, 4)
        .map(
          (url) =>
            `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${linkLabel(url)}</a>`
        )
        .join("");

      return `
        <article class="paper-row" id="paper-${index + 1}">
          <div class="paper-row-body">
            <h2 class="paper-row-title">${titleHtml}</h2>
            <p class="paper-row-authors">${authorText}</p>
          </div>
          <div class="paper-row-meta meta">
            ${paper.pages ? `<span class="paper-pages">pp. ${escapeHtml(paper.pages)}</span>` : ""}
            ${paper.dblp_url ? `<a href="${escapeHtml(paper.dblp_url)}">dblp</a>` : ""}
            ${linkItems}
          </div>
        </article>
      `;
    })
    .join("");

  return filtered.length;
}
